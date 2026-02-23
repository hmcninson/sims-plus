"""
SIMS Plus - Chain Service Tests

Tests for ChainService: school management, user-school assignments,
chain overview/dashboard, and chain user listing.

Uses admin_session (superuser) for seeding data, app_session (RLS-enforced)
for running service queries.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chain import ChainService
from tests.conftest import (
    admin_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_chain_tenant(session: AsyncSession, subdomain: str | None = None) -> dict:
    """Create a school_chain tenant via admin (bypasses RLS)."""
    tenant_id = uuid4()
    sub = subdomain or f"chain-{uuid4().hex[:8]}"
    await session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students, max_staff)
            VALUES (
                CAST(:id AS uuid), :sub, :slug, :name,
                true, 'school_chain', 'enterprise', 5000, 500
            )
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub, "name": f"Chain {sub}"},
    )
    await session.flush()
    return {"id": tenant_id, "subdomain": sub, "name": f"Chain {sub}"}


async def _create_school(
    session: AsyncSession,
    tenant_id,
    name: str,
    code: str | None = None,
    school_id=None,
    deleted: bool = False,
) -> dict:
    """Create a school for the given tenant."""
    sid = school_id or uuid4()
    c = code or f"SC-{uuid4().hex[:6]}"
    slug = name.lower().replace(" ", "-")[:100]
    await session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, code, school_type,
                student_id_prefix, deleted_at)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, :code,
                'basic', 'STU',
                CASE WHEN :deleted THEN CURRENT_TIMESTAMP ELSE NULL END
            )
        """),
        {
            "id": str(sid),
            "tid": str(tenant_id),
            "name": name,
            "slug": slug,
            "code": c,
            "deleted": deleted,
        },
    )
    await session.flush()
    return {"id": sid, "name": name, "code": c}


async def _create_student(
    session: AsyncSession,
    tenant_id,
    school_id,
    status: str = "active",
    deleted: bool = False,
) -> dict:
    """Create a student for the given school."""
    student_id = uuid4()
    sid_str = f"STU-{uuid4().hex[:6]}"
    await session.execute(
        text("""
            INSERT INTO students (
                id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender,
                status, deleted_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid), :stuid,
                'Test', 'Student', '2010-01-01', 'male',
                :status,
                CASE WHEN :deleted THEN CURRENT_TIMESTAMP ELSE NULL END
            )
        """),
        {
            "id": str(student_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "stuid": sid_str,
            "status": status,
            "deleted": deleted,
        },
    )
    await session.flush()
    return {"id": student_id}


async def _create_staff(
    session: AsyncSession,
    tenant_id,
    school_id,
    status: str = "active",
    deleted: bool = False,
) -> dict:
    """Create a staff member for the given school."""
    staff_id = uuid4()
    sid_str = f"STF-{uuid4().hex[:6]}"
    email = f"staff-{uuid4().hex[:8]}@test.com"
    await session.execute(
        text("""
            INSERT INTO staff (
                id, tenant_id, school_id, staff_id,
                first_name, last_name, email, phone, gender,
                staff_type, status, job_title, employment_date,
                deleted_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid), :stfid,
                'Test', 'Staff', :email, '0201234567', 'male',
                'teaching', :status, 'Teacher', '2024-01-01',
                CASE WHEN :deleted THEN CURRENT_TIMESTAMP ELSE NULL END
            )
        """),
        {
            "id": str(staff_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "stfid": sid_str,
            "email": email,
            "status": status,
            "deleted": deleted,
        },
    )
    await session.flush()
    return {"id": staff_id}


async def _create_user_school(
    session: AsyncSession,
    tenant_id,
    user_id,
    school_id,
    role: str = "teacher",
    is_primary: bool = False,
    is_active: bool = True,
) -> dict:
    """Create a user-school assignment via admin."""
    us_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO user_schools (
                id, tenant_id, user_id, school_id,
                role_at_school, is_primary, is_active
            )
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:uid AS uuid), CAST(:sid AS uuid),
                :role, :is_primary, :is_active
            )
        """),
        {
            "id": str(us_id),
            "tid": str(tenant_id),
            "uid": str(user_id),
            "sid": str(school_id),
            "role": role,
            "is_primary": is_primary,
            "is_active": is_active,
        },
    )
    await session.flush()
    return {"id": us_id}


# ===========================================================================
# list_schools
# ===========================================================================


class TestListSchools:
    """Tests for ChainService.list_schools."""

    @pytest.mark.asyncio
    async def test_returns_schools_with_counts(self, admin_session, app_session):
        """list_schools returns schools with correct student/staff counts."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Alpha School")
        # 2 active students, 1 active staff
        await _create_student(admin_session, tenant["id"], school["id"])
        await _create_student(admin_session, tenant["id"], school["id"])
        await _create_staff(admin_session, tenant["id"], school["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_schools(tenant["id"])

        assert result["total"] == 1
        item = result["items"][0]
        assert item["school"].name == "Alpha School"
        assert item["student_count"] == 2
        assert item["staff_count"] == 1

    @pytest.mark.asyncio
    async def test_search_filters_by_name(self, admin_session, app_session):
        """Search parameter filters schools by name (ILIKE)."""
        tenant = await _create_chain_tenant(admin_session)
        await _create_school(admin_session, tenant["id"], "Presec Legon")
        await _create_school(admin_session, tenant["id"], "Achimota School")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_schools(tenant["id"], search="presec")

        assert result["total"] == 1
        assert result["items"][0]["school"].name == "Presec Legon"

    @pytest.mark.asyncio
    async def test_pagination_works(self, admin_session, app_session):
        """Pagination returns correct page of results."""
        tenant = await _create_chain_tenant(admin_session)
        for i in range(5):
            await _create_school(admin_session, tenant["id"], f"School {i:02d}")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        # Page 1 with page_size=2
        result = await service.list_schools(tenant["id"], page=1, page_size=2)
        assert result["total"] == 5
        assert len(result["items"]) == 2

        # Page 3 with page_size=2 should have 1 item
        result = await service.list_schools(tenant["id"], page=3, page_size=2)
        assert result["total"] == 5
        assert len(result["items"]) == 1

    @pytest.mark.asyncio
    async def test_empty_result_for_tenant_with_no_schools(self, admin_session, app_session):
        """Returns empty list when tenant has no schools."""
        tenant = await _create_chain_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_schools(tenant["id"])

        assert result["total"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_soft_deleted_schools_excluded(self, admin_session, app_session):
        """Soft-deleted schools are not included in the list."""
        tenant = await _create_chain_tenant(admin_session)
        await _create_school(admin_session, tenant["id"], "Active School")
        await _create_school(admin_session, tenant["id"], "Deleted School", deleted=True)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_schools(tenant["id"])

        assert result["total"] == 1
        assert result["items"][0]["school"].name == "Active School"

    @pytest.mark.asyncio
    async def test_counts_exclude_deleted_students_staff(self, admin_session, app_session):
        """Student/staff counts exclude soft-deleted records."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Test School")
        await _create_student(admin_session, tenant["id"], school["id"])  # active
        await _create_student(admin_session, tenant["id"], school["id"], deleted=True)
        await _create_staff(admin_session, tenant["id"], school["id"])  # active
        await _create_staff(admin_session, tenant["id"], school["id"], deleted=True)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_schools(tenant["id"])

        item = result["items"][0]
        # Only active, non-deleted count. Note: list_schools also filters by
        # StudentStatus.ACTIVE, so deleted ones are excluded on two conditions.
        assert item["student_count"] == 1
        assert item["staff_count"] == 1


# ===========================================================================
# get_accessible_schools
# ===========================================================================


class TestGetAccessibleSchools:
    """Tests for ChainService.get_accessible_schools."""

    @pytest.mark.asyncio
    async def test_returns_only_assigned_schools(self, admin_session, app_session):
        """User only sees schools they are assigned to."""
        tenant = await _create_chain_tenant(admin_session)
        school_a = await _create_school(admin_session, tenant["id"], "School A")
        school_b = await _create_school(admin_session, tenant["id"], "School B")
        user = await create_test_user(admin_session, tenant["id"])
        # Assign user to school_a only
        await _create_user_school(admin_session, tenant["id"], user["id"], school_a["id"])
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        schools = await service.get_accessible_schools(user_id, tenant["id"])

        assert len(schools) == 1
        assert schools[0].name == "School A"

    @pytest.mark.asyncio
    async def test_inactive_assignments_excluded(self, admin_session, app_session):
        """Inactive user-school records are excluded."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Some School")
        user = await create_test_user(admin_session, tenant["id"])
        await _create_user_school(
            admin_session, tenant["id"], user["id"], school["id"], is_active=False
        )
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        schools = await service.get_accessible_schools(user_id, tenant["id"])

        assert len(schools) == 0

    @pytest.mark.asyncio
    async def test_primary_school_first(self, admin_session, app_session):
        """Primary school is returned first, then alphabetical."""
        tenant = await _create_chain_tenant(admin_session)
        school_z = await _create_school(admin_session, tenant["id"], "Zebra School")
        school_a = await _create_school(admin_session, tenant["id"], "Alpha School")
        user = await create_test_user(admin_session, tenant["id"])
        await _create_user_school(
            admin_session, tenant["id"], user["id"], school_a["id"], is_primary=False
        )
        await _create_user_school(
            admin_session, tenant["id"], user["id"], school_z["id"], is_primary=True
        )
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        schools = await service.get_accessible_schools(user_id, tenant["id"])

        assert len(schools) == 2
        assert schools[0].name == "Zebra School"  # primary first
        assert schools[1].name == "Alpha School"

    @pytest.mark.asyncio
    async def test_empty_for_user_with_no_assignments(self, admin_session, app_session):
        """User with no school assignments gets empty list."""
        tenant = await _create_chain_tenant(admin_session)
        await _create_school(admin_session, tenant["id"], "Some School")
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        schools = await service.get_accessible_schools(user_id, tenant["id"])

        assert len(schools) == 0


# ===========================================================================
# get_chain_dashboard
# ===========================================================================


class TestGetChainDashboard:
    """Tests for ChainService.get_chain_dashboard."""

    @pytest.mark.asyncio
    async def test_aggregates_across_schools(self, admin_session, app_session):
        """Dashboard returns aggregated student/staff counts across schools."""
        tenant = await _create_chain_tenant(admin_session)
        school_a = await _create_school(admin_session, tenant["id"], "School A")
        school_b = await _create_school(admin_session, tenant["id"], "School B")
        # 2 students in A, 1 in B
        await _create_student(admin_session, tenant["id"], school_a["id"])
        await _create_student(admin_session, tenant["id"], school_a["id"])
        await _create_student(admin_session, tenant["id"], school_b["id"])
        # 1 staff in each
        await _create_staff(admin_session, tenant["id"], school_a["id"])
        await _create_staff(admin_session, tenant["id"], school_b["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        data = await service.get_chain_dashboard(tenant["id"])

        assert data["total_schools"] == 2
        assert data["total_students"] == 3
        assert data["total_staff"] == 2
        assert len(data["schools"]) == 2

    @pytest.mark.asyncio
    async def test_handles_zero_schools(self, admin_session, app_session):
        """Dashboard returns zero metrics when tenant has no schools."""
        tenant = await _create_chain_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        data = await service.get_chain_dashboard(tenant["id"])

        assert data["total_schools"] == 0
        assert data["total_students"] == 0
        assert data["total_staff"] == 0
        assert data["total_revenue"] == 0.0
        assert data["total_outstanding"] == 0.0
        assert data["schools"] == []

    @pytest.mark.asyncio
    async def test_rejects_non_chain_tenant(self, admin_session, app_session):
        """Dashboard raises error for single_school tenants."""
        tenant = await create_test_tenant(admin_session)  # single_school by default
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        with pytest.raises(ChainService.Error) as exc_info:
            await service.get_chain_dashboard(tenant["id"])
        assert exc_info.value.code == 403


# ===========================================================================
# list_chain_users
# ===========================================================================


class TestListChainUsers:
    """Tests for ChainService.list_chain_users."""

    @pytest.mark.asyncio
    async def test_lists_users_with_pagination(self, admin_session, app_session):
        """list_chain_users returns paginated user list."""
        tenant = await _create_chain_tenant(admin_session)
        for i in range(3):
            await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_chain_users(tenant["id"], page=1, page_size=2)

        assert result["total"] == 3
        assert len(result["users"]) == 2
        assert result["total_pages"] == 2

    @pytest.mark.asyncio
    async def test_search_by_email(self, admin_session, app_session):
        """Search filters users by email."""
        tenant = await _create_chain_tenant(admin_session)
        await create_test_user(admin_session, tenant["id"], email="findme@test.com")
        await create_test_user(admin_session, tenant["id"], email="other@test.com")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_chain_users(tenant["id"], search="findme")

        assert result["total"] == 1
        assert result["users"][0].email == "findme@test.com"

    @pytest.mark.asyncio
    async def test_school_id_filter(self, admin_session, app_session):
        """school_id parameter filters to users assigned to that school."""
        tenant = await _create_chain_tenant(admin_session)
        school_a = await _create_school(admin_session, tenant["id"], "School A")
        school_b = await _create_school(admin_session, tenant["id"], "School B")
        user_a = await create_test_user(admin_session, tenant["id"])
        user_b = await create_test_user(admin_session, tenant["id"])
        await _create_user_school(admin_session, tenant["id"], user_a["id"], school_a["id"])
        await _create_user_school(admin_session, tenant["id"], user_b["id"], school_b["id"])
        await admin_session.commit()

        school_a_id = school_a["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_chain_users(
            tenant["id"], school_id=school_a_id
        )

        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_accesses_batch_loaded(self, admin_session, app_session):
        """School accesses are batch-loaded for users on the page."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "School X")
        user = await create_test_user(admin_session, tenant["id"])
        await _create_user_school(admin_session, tenant["id"], user["id"], school["id"])
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.list_chain_users(tenant["id"])

        assert user_id in result["accesses_by_user"]
        assert len(result["accesses_by_user"][user_id]) == 1


# ===========================================================================
# get_school_counts
# ===========================================================================


class TestGetSchoolCounts:
    """Tests for ChainService.get_school_counts."""

    @pytest.mark.asyncio
    async def test_correct_student_count(self, admin_session, app_session):
        """Returns correct student count for a school."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Test School")
        await _create_student(admin_session, tenant["id"], school["id"])
        await _create_student(admin_session, tenant["id"], school["id"])
        await admin_session.commit()

        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        student_count, _ = await service.get_school_counts(school_id, tenant["id"])

        assert student_count == 2

    @pytest.mark.asyncio
    async def test_correct_staff_count(self, admin_session, app_session):
        """Returns correct staff count for a school."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Test School")
        await _create_staff(admin_session, tenant["id"], school["id"])
        await admin_session.commit()

        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        _, staff_count = await service.get_school_counts(school_id, tenant["id"])

        assert staff_count == 1

    @pytest.mark.asyncio
    async def test_deleted_records_excluded(self, admin_session, app_session):
        """Soft-deleted students/staff are excluded from counts."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Test School")
        await _create_student(admin_session, tenant["id"], school["id"])
        await _create_student(admin_session, tenant["id"], school["id"], deleted=True)
        await _create_staff(admin_session, tenant["id"], school["id"])
        await _create_staff(admin_session, tenant["id"], school["id"], deleted=True)
        await admin_session.commit()

        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        student_count, staff_count = await service.get_school_counts(
            school_id, tenant["id"]
        )

        assert student_count == 1
        assert staff_count == 1


# ===========================================================================
# add_school
# ===========================================================================


class TestAddSchool:
    """Tests for ChainService.add_school."""

    @pytest.mark.asyncio
    async def test_add_school_to_chain(self, admin_session, app_session):
        """Adding a school to a chain tenant succeeds."""
        tenant = await _create_chain_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        school = await service.add_school(
            tenant_id=tenant["id"],
            name="New Branch School",
            code="NBS-001",
        )

        assert school.name == "New Branch School"
        assert school.code == "NBS-001"
        assert school.tenant_id == tenant["id"]

    @pytest.mark.asyncio
    async def test_duplicate_code_rejected(self, admin_session, app_session):
        """Duplicate school code within the same tenant is rejected."""
        tenant = await _create_chain_tenant(admin_session)
        await _create_school(admin_session, tenant["id"], "First", code="DUP-01")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        with pytest.raises(ChainService.Error) as exc_info:
            await service.add_school(
                tenant_id=tenant["id"], name="Second", code="DUP-01"
            )
        assert "already exists" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_rejects_single_school_tenant(self, admin_session, app_session):
        """Adding a school to a single_school tenant is rejected."""
        tenant = await create_test_tenant(admin_session)  # single_school
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        with pytest.raises(ChainService.Error) as exc_info:
            await service.add_school(
                tenant_id=tenant["id"], name="Extra School", code="EX-01"
            )
        assert exc_info.value.code == 403


# ===========================================================================
# update_school
# ===========================================================================


class TestUpdateSchool:
    """Tests for ChainService.update_school."""

    @pytest.mark.asyncio
    async def test_update_school_name(self, admin_session, app_session):
        """Updating a school name works."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Old Name")
        await admin_session.commit()

        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        updated = await service.update_school(
            tenant_id=tenant["id"], school_id=school_id, name="New Name"
        )

        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_nonexistent_school_404(self, admin_session, app_session):
        """Updating a non-existent school returns 404."""
        tenant = await _create_chain_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        with pytest.raises(ChainService.Error) as exc_info:
            await service.update_school(
                tenant_id=tenant["id"], school_id=uuid4(), name="Anything"
            )
        assert exc_info.value.code == 404


# ===========================================================================
# assign_user_to_school / remove_user_from_school
# ===========================================================================


class TestUserSchoolAssignment:
    """Tests for assign/remove user-school operations."""

    @pytest.mark.asyncio
    async def test_assign_user_to_school(self, admin_session, app_session):
        """Assigning a user to a school creates a UserSchool record."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "School A")
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        user_id = user["id"]
        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        us = await service.assign_user_to_school(
            tenant_id=tenant["id"],
            user_id=user_id,
            school_id=school_id,
            role_at_school="teacher",
        )

        assert us.user_id == user_id
        assert us.school_id == school_id
        assert us.role_at_school == "teacher"
        assert us.is_active is True

    @pytest.mark.asyncio
    async def test_reassign_reactivates(self, admin_session, app_session):
        """Re-assigning a deactivated user-school reactivates it."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "School B")
        user = await create_test_user(admin_session, tenant["id"])
        # Create inactive assignment
        await _create_user_school(
            admin_session, tenant["id"], user["id"], school["id"], is_active=False
        )
        await admin_session.commit()

        user_id = user["id"]
        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        us = await service.assign_user_to_school(
            tenant_id=tenant["id"],
            user_id=user_id,
            school_id=school_id,
            role_at_school="school_admin",
        )

        assert us.is_active is True
        assert us.role_at_school == "school_admin"

    @pytest.mark.asyncio
    async def test_primary_flag_clears_others(self, admin_session, app_session):
        """Setting is_primary=True clears primary on other schools for the user."""
        tenant = await _create_chain_tenant(admin_session)
        school_a = await _create_school(admin_session, tenant["id"], "School A")
        school_b = await _create_school(admin_session, tenant["id"], "School B")
        user = await create_test_user(admin_session, tenant["id"])
        await _create_user_school(
            admin_session, tenant["id"], user["id"], school_a["id"], is_primary=True
        )
        await admin_session.commit()

        user_id = user["id"]
        school_b_id = school_b["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        us_b = await service.assign_user_to_school(
            tenant_id=tenant["id"],
            user_id=user_id,
            school_id=school_b_id,
            role_at_school="teacher",
            is_primary=True,
        )

        assert us_b.is_primary is True

        # Verify school_a's primary was cleared
        user_schools = await service.list_user_schools(tenant["id"], user_id)
        for us in user_schools:
            if us.school_id == school_a["id"]:
                assert us.is_primary is False

    @pytest.mark.asyncio
    async def test_remove_user_from_school(self, admin_session, app_session):
        """Removing a user from a school sets is_active=False."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "School C")
        user = await create_test_user(admin_session, tenant["id"])
        await _create_user_school(admin_session, tenant["id"], user["id"], school["id"])
        await admin_session.commit()

        user_id = user["id"]
        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)
        result = await service.remove_user_from_school(
            tenant_id=tenant["id"], user_id=user_id, school_id=school_id
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_nonexistent_assignment_404(self, admin_session, app_session):
        """Removing a non-existent user-school assignment raises 404."""
        tenant = await _create_chain_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        with pytest.raises(ChainService.Error) as exc_info:
            await service.remove_user_from_school(
                tenant_id=tenant["id"], user_id=uuid4(), school_id=uuid4()
            )
        assert exc_info.value.code == 404

    @pytest.mark.asyncio
    async def test_assign_nonexistent_user_404(self, admin_session, app_session):
        """Assigning a non-existent user to a school raises 404."""
        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"], "Some School")
        await admin_session.commit()

        school_id = school["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        with pytest.raises(ChainService.Error) as exc_info:
            await service.assign_user_to_school(
                tenant_id=tenant["id"],
                user_id=uuid4(),
                school_id=school_id,
                role_at_school="teacher",
            )
        assert exc_info.value.code == 404

    @pytest.mark.asyncio
    async def test_assign_nonexistent_school_404(self, admin_session, app_session):
        """Assigning a user to a non-existent school raises 404."""
        tenant = await _create_chain_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        service = ChainService(app_session)

        with pytest.raises(ChainService.Error) as exc_info:
            await service.assign_user_to_school(
                tenant_id=tenant["id"],
                user_id=user_id,
                school_id=uuid4(),
                role_at_school="teacher",
            )
        assert exc_info.value.code == 404
