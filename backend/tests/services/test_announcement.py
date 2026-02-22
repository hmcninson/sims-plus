"""
SIMS Plus - Announcement Service Tests

Tests for AnnouncementService CRUD lifecycle:
- Create, update, publish, delete
- Published announcements cannot be updated
- Targeting validation (specific_class requires class_id)
- Listing with pagination and filtering
- Soft-deleted announcements excluded
- Tenant isolation at service level
"""

from datetime import datetime, timedelta, UTC
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.parent import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementTargetEnum,
    AnnouncementPriorityEnum,
)
from app.services.announcement import (
    AnnouncementService,
    AnnouncementServiceError,
)
from tests.conftest import (
    admin_session_maker,
    app_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest_asyncio.fixture
async def announcement_env(admin_session: AsyncSession, app_session: AsyncSession):
    """Seed a tenant + school + user for announcement tests."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"ann-{suffix}")
    tenant_id = tenant["id"]

    # Create school
    school_id = uuid4()
    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Announce School', :slug, 'ANN', 'basic')
    """), {"id": str(school_id), "tid": str(tenant_id), "slug": f"ann-{suffix}"})

    # Create user (author)
    user = await create_test_user(admin_session, tenant_id)
    user_id = user["id"]

    # CRITICAL: commit so app_session (separate connection) can see the data
    await admin_session.commit()

    # Set tenant context on app session for service queries
    await set_app_tenant_context(app_session, tenant_id)

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "app_session": app_session,
    }

    # CRITICAL: rollback app_session to release any row locks before cleanup
    await app_session.rollback()

    # Cleanup: remove seeded data (resilient to connection drops during long runs)
    try:
        async with admin_session_maker() as cleanup:
            for table in ["announcements", "teacher_notes", "parent_notification_preferences",
                           "users", "schools"]:
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
# Tests: Create
# =====================================================================


@pytest.mark.asyncio
async def test_create_announcement_draft(announcement_env):
    """Create an announcement -- should start as draft (published_at=NULL)."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    data = AnnouncementCreate(
        title="Test Announcement",
        content="This is a test announcement body.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
        priority=AnnouncementPriorityEnum.NORMAL,
    )

    ann = await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=data,
    )

    assert ann.id is not None
    assert ann.title == "Test Announcement"
    assert ann.published_at is None  # Draft
    assert ann.deleted_at is None


@pytest.mark.asyncio
async def test_create_specific_class_without_class_id_fails(announcement_env):
    """Creating specific_class announcement without target_class_id should fail."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    data = AnnouncementCreate(
        title="Class Announcement",
        content="Only for Class 6.",
        target_audience=AnnouncementTargetEnum.SPECIFIC_CLASS,
        # target_class_id intentionally omitted (None)
    )

    with pytest.raises(AnnouncementServiceError) as exc_info:
        await service.create_announcement(
            tenant_id=env["tenant_id"],
            school_id=env["school_id"],
            author_id=env["user_id"],
            data=data,
        )

    assert exc_info.value.code == "missing_target_class"


# =====================================================================
# Tests: Update
# =====================================================================


@pytest.mark.asyncio
async def test_update_draft_announcement(announcement_env):
    """Updating an unpublished announcement should succeed."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    # Create draft
    create_data = AnnouncementCreate(
        title="Original Title",
        content="Original content.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    ann = await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=create_data,
    )
    ann_id = ann.id

    # Update
    update_data = AnnouncementUpdate(title="Updated Title")
    updated = await service.update_announcement(
        tenant_id=env["tenant_id"],
        announcement_id=ann_id,
        data=update_data,
    )

    assert updated.title == "Updated Title"
    assert updated.content == "Original content."  # Unchanged


@pytest.mark.asyncio
async def test_update_published_announcement_fails(announcement_env):
    """Published announcements cannot be updated."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    # Create and publish
    data = AnnouncementCreate(
        title="Published",
        content="Cannot edit after publish.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    ann = await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=data,
    )
    await service.publish_announcement(env["tenant_id"], ann.id)

    # Try to update
    update_data = AnnouncementUpdate(title="Sneaky Edit")
    with pytest.raises(AnnouncementServiceError) as exc_info:
        await service.update_announcement(
            tenant_id=env["tenant_id"],
            announcement_id=ann.id,
            data=update_data,
        )

    assert exc_info.value.code == "already_published"


# =====================================================================
# Tests: Publish
# =====================================================================


@pytest.mark.asyncio
async def test_publish_announcement(announcement_env):
    """Publishing an announcement sets published_at to now."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    data = AnnouncementCreate(
        title="To Be Published",
        content="Will be published.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    ann = await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=data,
    )
    assert ann.published_at is None

    published = await service.publish_announcement(env["tenant_id"], ann.id)
    assert published.published_at is not None


@pytest.mark.asyncio
async def test_publish_already_published_fails(announcement_env):
    """Publishing an already-published announcement should raise an error."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    data = AnnouncementCreate(
        title="Already Published",
        content="Double publish test.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    ann = await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=data,
    )
    await service.publish_announcement(env["tenant_id"], ann.id)

    with pytest.raises(AnnouncementServiceError) as exc_info:
        await service.publish_announcement(env["tenant_id"], ann.id)

    assert exc_info.value.code == "already_published"


# =====================================================================
# Tests: Delete
# =====================================================================


@pytest.mark.asyncio
async def test_delete_announcement_soft_deletes(announcement_env):
    """Deleting an announcement sets deleted_at (soft delete)."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    data = AnnouncementCreate(
        title="To Be Deleted",
        content="Will be soft deleted.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    ann = await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=data,
    )

    await service.delete_announcement(env["tenant_id"], ann.id)

    # Should not be findable anymore
    with pytest.raises(AnnouncementServiceError) as exc_info:
        await service.get_announcement(env["tenant_id"], ann.id)

    assert exc_info.value.code == "not_found"


# =====================================================================
# Tests: List
# =====================================================================


@pytest.mark.asyncio
async def test_list_announcements_excludes_drafts_by_default(announcement_env):
    """list_announcements with include_drafts=False should exclude drafts."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    # Create a draft
    draft_data = AnnouncementCreate(
        title="Draft",
        content="Not published.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=draft_data,
    )

    # Create and publish another
    pub_data = AnnouncementCreate(
        title="Published",
        content="This is published.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    pub_ann = await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=pub_data,
    )
    await service.publish_announcement(env["tenant_id"], pub_ann.id)

    # List without drafts
    result = await service.list_announcements(
        tenant_id=env["tenant_id"],
        include_drafts=False,
    )

    titles = [a.title for a in result["items"]]
    assert "Published" in titles
    assert "Draft" not in titles


@pytest.mark.asyncio
async def test_list_announcements_includes_drafts_when_requested(announcement_env):
    """list_announcements with include_drafts=True should include drafts."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    data = AnnouncementCreate(
        title="My Draft",
        content="Draft content.",
        target_audience=AnnouncementTargetEnum.ALL_PARENTS,
    )
    await service.create_announcement(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        author_id=env["user_id"],
        data=data,
    )

    result = await service.list_announcements(
        tenant_id=env["tenant_id"],
        include_drafts=True,
    )

    titles = [a.title for a in result["items"]]
    assert "My Draft" in titles


# =====================================================================
# Tests: Get
# =====================================================================


@pytest.mark.asyncio
async def test_get_nonexistent_announcement_raises(announcement_env):
    """Getting a nonexistent announcement should raise not_found."""
    env = announcement_env
    service = AnnouncementService(env["app_session"])

    with pytest.raises(AnnouncementServiceError) as exc_info:
        await service.get_announcement(env["tenant_id"], uuid4())

    assert exc_info.value.code == "not_found"


# =====================================================================
# Tests: Tenant isolation
# =====================================================================


@pytest.mark.asyncio
async def test_announcement_not_visible_across_tenants(
    admin_session: AsyncSession, app_session: AsyncSession
):
    """Announcements from tenant A should NOT be visible to tenant B."""
    suffix = uuid4().hex[:8]
    # Create two tenants
    tenant_a = await create_test_tenant(admin_session, subdomain=f"ann-a-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"ann-b-{suffix}")

    # Create schools for both
    school_a_id = uuid4()
    school_b_id = uuid4()
    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'School A', :slug, 'SA', 'basic')
    """), {"id": str(school_a_id), "tid": str(tenant_a["id"]), "slug": f"sa-{suffix}"})
    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'School B', :slug, 'SB', 'basic')
    """), {"id": str(school_b_id), "tid": str(tenant_b["id"]), "slug": f"sb-{suffix}"})

    user_a = await create_test_user(admin_session, tenant_a["id"])

    # CRITICAL: commit so app_session can see the data
    await admin_session.commit()

    try:
        # Create announcement as tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service_a = AnnouncementService(app_session)

        data = AnnouncementCreate(
            title="Tenant A Only",
            content="Should not be visible to tenant B.",
            target_audience=AnnouncementTargetEnum.ALL_PARENTS,
        )
        ann = await service_a.create_announcement(
            tenant_id=tenant_a["id"],
            school_id=school_a_id,
            author_id=user_a["id"],
            data=data,
        )
        ann_id = ann.id

        # Switch to tenant B and try to find the announcement
        await set_app_tenant_context(app_session, tenant_b["id"])
        service_b = AnnouncementService(app_session)

        with pytest.raises(AnnouncementServiceError) as exc_info:
            await service_b.get_announcement(tenant_b["id"], ann_id)

        assert exc_info.value.code == "not_found"
    finally:
        # CRITICAL: rollback app_session to release row locks before cleanup
        await app_session.rollback()

        # Cleanup committed data (resilient to connection drops during long runs)
        try:
            async with admin_session_maker() as cleanup:
                for tid in [str(tenant_a["id"]), str(tenant_b["id"])]:
                    for table in ["announcements", "users", "schools"]:
                        await cleanup.execute(
                            text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                            {"tid": tid},
                        )
                    await cleanup.execute(
                        text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                        {"tid": tid},
                    )
                await cleanup.commit()
        except Exception:
            pass  # Best-effort cleanup; test DB is ephemeral
