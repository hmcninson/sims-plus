"""
SIMS Plus - Parent Onboarding Service Tests

Tests for ParentOnboardingService:
- Create parent for student (new user + guardian + link)
- Invite existing parent email (just creates new link)
- Email conflict with non-parent user returns error
- Bulk invite with deduplication
- Complete profile activates account
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from app.models.user import User, UserRole, UserStatus
from app.models.student import Guardian, StudentGuardian
from app.services.parent import ParentOnboardingService, ParentServiceError
from tests.conftest import (
    admin_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest_asyncio.fixture
async def onboarding_env(admin_session: AsyncSession, app_session: AsyncSession):
    """Seed a tenant + school + 2 students for onboarding tests."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"onb-{suffix}")
    tenant_id = tenant["id"]

    school_id = uuid4()

    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Onboard School', :slug, 'ONB', 'basic')
    """), {"id": str(school_id), "tid": str(tenant_id), "slug": f"onb-{suffix}"})

    # Admin user (for invited_by)
    admin_user = await create_test_user(admin_session, tenant_id, email=f"admin-onb-{suffix}@test.com")

    # 2 students
    student_1_id = uuid4()
    student_2_id = uuid4()
    student_sql = text("""
        INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
            date_of_birth, gender, status, school_id)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
            '2015-01-15', 'male', 'active', CAST(:school_id AS uuid))
    """)
    await admin_session.execute(student_sql, {
        "id": str(student_1_id), "tid": str(tenant_id),
        "sid": f"ONB1-{suffix}", "fn": "Onboard1", "ln": "Test", "school_id": str(school_id),
    })
    await admin_session.execute(student_sql, {
        "id": str(student_2_id), "tid": str(tenant_id),
        "sid": f"ONB2-{suffix}", "fn": "Onboard2", "ln": "Test", "school_id": str(school_id),
    })

    # CRITICAL: commit so app_session (separate connection) can see the data
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant_id)

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "admin_user_id": admin_user["id"],
        "student_1_id": student_1_id,
        "student_2_id": student_2_id,
        "suffix": suffix,
        "app_session": app_session,
    }

    # CRITICAL: rollback app_session to release any row locks before cleanup
    await app_session.rollback()

    # Cleanup: remove seeded data (resilient to connection drops during long runs)
    try:
        async with admin_session_maker() as cleanup:
            for table in ["student_guardians", "guardians", "teacher_notes", "announcements",
                           "parent_notification_preferences", "students", "users", "schools"]:
                await cleanup.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                    {"tid": str(tenant_id)},
                )
            await cleanup.execute(
                text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
            await cleanup.commit()
    except Exception:
        pass  # Best-effort cleanup; test DB is ephemeral


# =====================================================================
# Tests: Create parent for student
# =====================================================================


@pytest.mark.asyncio
@patch("app.services.parent.parent_onboarding.email_service")
async def test_create_parent_new_user(mock_email, onboarding_env):
    """Creating a parent for a student should create user + guardian + link."""
    mock_email.send_user_invite = AsyncMock()

    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])
    email = f"new-parent-{env['suffix']}@test.com"

    user = await service.create_parent_for_student(
        student_id=env["student_1_id"],
        guardian_data={
            "email": email,
            "first_name": "NewParent",
            "last_name": "Test",
            "phone": "0241234567",
            "relationship": "father",
            "is_primary": True,
        },
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        invited_by=env["admin_user_id"],
    )

    assert user.id is not None
    assert user.email == email
    assert user.role == UserRole.PARENT
    assert user.status == UserStatus.PENDING

    # Verify guardian was created
    guardian_result = await env["app_session"].execute(
        select(Guardian).where(
            and_(
                Guardian.email == email,
                Guardian.tenant_id == env["tenant_id"],
                Guardian.deleted_at.is_(None),
            )
        )
    )
    guardian = guardian_result.scalar_one_or_none()
    assert guardian is not None
    assert guardian.first_name == "NewParent"

    # Verify student_guardian link
    link_result = await env["app_session"].execute(
        select(StudentGuardian).where(
            and_(
                StudentGuardian.student_id == env["student_1_id"],
                StudentGuardian.guardian_id == guardian.id,
                StudentGuardian.tenant_id == env["tenant_id"],
            )
        )
    )
    link = link_result.scalar_one_or_none()
    assert link is not None
    assert link.is_primary is True


@pytest.mark.asyncio
async def test_create_parent_missing_email_fails(onboarding_env):
    """Creating a parent without an email should raise email_required."""
    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])

    with pytest.raises(ParentServiceError) as exc_info:
        await service.create_parent_for_student(
            student_id=env["student_1_id"],
            guardian_data={
                "first_name": "NoEmail",
                "last_name": "Parent",
                # email intentionally omitted
            },
            tenant_id=env["tenant_id"],
            school_id=env["school_id"],
            invited_by=env["admin_user_id"],
        )

    assert exc_info.value.code == "email_required"


@pytest.mark.asyncio
async def test_create_parent_nonexistent_student_fails(onboarding_env):
    """Creating a parent for a nonexistent student should raise student_not_found."""
    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])

    with pytest.raises(ParentServiceError) as exc_info:
        await service.create_parent_for_student(
            student_id=uuid4(),
            guardian_data={
                "email": f"ghost-{uuid4().hex[:6]}@test.com",
                "first_name": "Ghost",
                "last_name": "Parent",
            },
            tenant_id=env["tenant_id"],
            school_id=env["school_id"],
            invited_by=env["admin_user_id"],
        )

    assert exc_info.value.code == "student_not_found"


# =====================================================================
# Tests: Invite existing parent (additional child)
# =====================================================================


@pytest.mark.asyncio
@patch("app.services.parent.parent_onboarding.email_service")
async def test_invite_existing_parent_links_additional_child(mock_email, onboarding_env):
    """If a parent user already exists, adding another child should just create the link."""
    mock_email.send_user_invite = AsyncMock()

    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])
    email = f"existing-parent-{env['suffix']}@test.com"

    # First invite: creates user + guardian + link to student_1
    user1 = await service.create_parent_for_student(
        student_id=env["student_1_id"],
        guardian_data={
            "email": email,
            "first_name": "Existing",
            "last_name": "Parent",
            "relationship": "mother",
        },
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        invited_by=env["admin_user_id"],
    )

    # Second invite: same email, different student (student_2)
    user2 = await service.create_parent_for_student(
        student_id=env["student_2_id"],
        guardian_data={
            "email": email,
            "first_name": "Existing",
            "last_name": "Parent",
            "relationship": "mother",
        },
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        invited_by=env["admin_user_id"],
    )

    # Same user returned both times
    assert user1.id == user2.id

    # Both students should be linked
    links = await env["app_session"].execute(
        select(StudentGuardian).where(
            and_(
                StudentGuardian.tenant_id == env["tenant_id"],
                StudentGuardian.guardian_id.isnot(None),
            )
        ).join(Guardian, StudentGuardian.guardian_id == Guardian.id)
        .where(Guardian.email == email)
    )
    link_list = list(links.scalars().all())
    linked_student_ids = {link.student_id for link in link_list}
    assert env["student_1_id"] in linked_student_ids
    assert env["student_2_id"] in linked_student_ids


# =====================================================================
# Tests: Email conflict with non-parent user
# =====================================================================


@pytest.mark.asyncio
async def test_email_conflict_with_teacher_fails(onboarding_env):
    """If the email belongs to a teacher, creating a parent should fail."""
    env = onboarding_env
    # The admin_user we created has role=teacher (default from create_test_user)
    # Let's use that email
    admin_result = await env["app_session"].execute(
        select(User).where(User.id == env["admin_user_id"])
    )
    admin_user = admin_result.scalar_one()
    teacher_email = admin_user.email

    service = ParentOnboardingService(env["app_session"])

    with pytest.raises(ParentServiceError) as exc_info:
        await service.create_parent_for_student(
            student_id=env["student_1_id"],
            guardian_data={
                "email": teacher_email,
                "first_name": "Conflict",
                "last_name": "Parent",
            },
            tenant_id=env["tenant_id"],
            school_id=env["school_id"],
            invited_by=env["admin_user_id"],
        )

    assert exc_info.value.code == "email_role_conflict"


# =====================================================================
# Tests: Bulk invite
# =====================================================================


@pytest.mark.asyncio
@patch("app.services.parent.parent_onboarding.email_service")
async def test_bulk_invite_with_deduplication(mock_email, onboarding_env):
    """Bulk invite should deduplicate by email: same email for 2 students = 1 user, 2 links."""
    mock_email.send_user_invite = AsyncMock()

    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])
    shared_email = f"bulk-parent-{env['suffix']}@test.com"

    result = await service.bulk_create_parents(
        invitations=[
            {
                "student_id": str(env["student_1_id"]),
                "email": shared_email,
                "first_name": "Bulk",
                "last_name": "Parent",
                "relationship": "guardian",
            },
            {
                "student_id": str(env["student_2_id"]),
                "email": shared_email,
                "first_name": "Bulk",
                "last_name": "Parent",
                "relationship": "guardian",
            },
        ],
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        invited_by=env["admin_user_id"],
    )

    assert result["created"] + result["linked"] >= 2
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
@patch("app.services.parent.parent_onboarding.email_service")
async def test_bulk_invite_missing_email_reported_as_error(mock_email, onboarding_env):
    """Bulk invite with missing email should report an error, not crash."""
    mock_email.send_user_invite = AsyncMock()

    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])

    result = await service.bulk_create_parents(
        invitations=[
            {
                "student_id": str(env["student_1_id"]),
                # email missing
                "first_name": "No",
                "last_name": "Email",
            },
        ],
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        invited_by=env["admin_user_id"],
    )

    assert len(result["errors"]) == 1
    assert "Email is required" in result["errors"][0]["error"]


# =====================================================================
# Tests: Complete profile
# =====================================================================


@pytest.mark.asyncio
@patch("app.services.parent.parent_onboarding.email_service")
async def test_complete_profile_activates_account(mock_email, onboarding_env):
    """Completing profile for a PENDING parent should set status to ACTIVE."""
    mock_email.send_user_invite = AsyncMock()

    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])
    email = f"profile-{env['suffix']}@test.com"

    # Create parent (PENDING status)
    user = await service.create_parent_for_student(
        student_id=env["student_1_id"],
        guardian_data={
            "email": email,
            "first_name": "Profile",
            "last_name": "Test",
        },
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        invited_by=env["admin_user_id"],
    )
    assert user.status == UserStatus.PENDING

    # Complete profile
    await service.complete_profile(
        user_id=user.id,
        tenant_id=env["tenant_id"],
        data={"phone": "0241234567"},
    )

    # Refresh user
    await env["app_session"].refresh(user)
    assert user.status == UserStatus.ACTIVE
    assert user.email_verified is True
    assert user.phone == "0241234567"


@pytest.mark.asyncio
async def test_complete_profile_non_parent_fails(onboarding_env):
    """Completing profile for a non-parent user should fail."""
    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])

    # admin_user has role=teacher
    with pytest.raises(ParentServiceError) as exc_info:
        await service.complete_profile(
            user_id=env["admin_user_id"],
            tenant_id=env["tenant_id"],
            data={"phone": "0241234567"},
        )

    assert exc_info.value.code == "not_a_parent"


@pytest.mark.asyncio
async def test_complete_profile_nonexistent_user_fails(onboarding_env):
    """Completing profile for a nonexistent user should fail."""
    env = onboarding_env
    service = ParentOnboardingService(env["app_session"])

    with pytest.raises(ParentServiceError) as exc_info:
        await service.complete_profile(
            user_id=uuid4(),
            tenant_id=env["tenant_id"],
            data={"phone": "0241234567"},
        )

    assert exc_info.value.code == "user_not_found"
