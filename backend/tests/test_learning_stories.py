"""
SIMS Plus - Learning Story Tests (Phase 2)

Tests exercise PreschoolPortfolioService learning story CRUD against a real
PostgreSQL database. Covers create, list (by student, shared-only), get,
update, soft delete, student-not-found validation, and RLS tenant isolation.

Uses admin_session for seeding, app_session with RLS for service calls.
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolPortfolioService, PreschoolServiceError
from app.schemas.preschool import LearningStoryCreate, LearningStoryUpdate

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)


# ============================================================
# SQL templates for test data seeding
# ============================================================

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'preschool', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_ACADEMIC_YEAR_INSERT = text("""
    INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
        status, is_current, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
        :start_date, :end_date, 'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_TERM_INSERT = text("""
    INSERT INTO terms (id, tenant_id, academic_year_id, name, short_name,
        sequence, start_date, end_date, status, is_current,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay_id AS uuid),
        :name, :short_name, :seq, :start_date, :end_date,
        'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_CLASS_INSERT = text("""
    INSERT INTO classes (id, tenant_id, name, level, sequence,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :level, :seq,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
        date_of_birth, gender, status, class_id, school_id,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
        '2021-05-10', 'female', 'active', CAST(:cid AS uuid), CAST(:school_id AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_story_env(session: AsyncSession) -> dict:
    """Seed a complete environment for learning story tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_id = uuid4()
    student1_id = uuid4()
    student2_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Little Learners Academy", "slug": f"ll-{uuid4().hex[:8]}",
    })
    await session.execute(_ACADEMIC_YEAR_INSERT, {
        "id": str(ay_id), "tid": str(tid), "name": "2025/2026",
        "start_date": date(2025, 9, 1), "end_date": date(2026, 7, 31),
    })
    await session.execute(_TERM_INSERT, {
        "id": str(term_id), "tid": str(tid), "ay_id": str(ay_id),
        "name": "First Term", "short_name": "T1", "seq": 1,
        "start_date": date(2025, 9, 1), "end_date": date(2025, 12, 20),
    })
    await session.execute(_CLASS_INSERT, {
        "id": str(class_id), "tid": str(tid),
        "name": "KG 1", "level": "kg_1", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student1_id), "tid": str(tid), "sid": "LS-001",
        "fn": "Ama", "ln": "Mensah", "cid": str(class_id),
        "school_id": str(school_id),
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student2_id), "tid": str(tid), "sid": "LS-002",
        "fn": "Yaw", "ln": "Darko", "cid": str(class_id),
        "school_id": str(school_id),
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "student1_id": student1_id,
        "student2_id": student2_id,
        "user_id": user["id"],
    }


def _make_story_data(student_id, **overrides):
    """Build a LearningStoryCreate with sensible defaults."""
    params = {
        "student_id": student_id,
        "title": "Building a block tower",
        "narrative": "Ama spent the morning building an intricate block tower, demonstrating spatial awareness and patience.",
        "is_shared_with_parents": True,
    }
    params.update(overrides)
    return LearningStoryCreate(**params)


@pytest.mark.asyncio
class TestLearningStories:
    """Test learning story CRUD."""

    async def test_create_learning_story(self, admin_session, app_session):
        """Create a learning story with title, narrative, and verify defaults."""
        env = await _seed_story_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolPortfolioService(app_session)
        data = _make_story_data(env["student1_id"])
        story = await service.create_learning_story(
            tenant_id=env["tenant_id"],
            data=data,
            created_by=env["user_id"],
        )

        assert story.title == "Building a block tower"
        assert story.narrative.startswith("Ama spent")
        assert story.created_by == env["user_id"]
        assert story.is_shared_with_parents is True
        assert story.student_id == env["student1_id"]
        assert story.tenant_id == env["tenant_id"]

    async def test_create_learning_story_student_not_found(self, admin_session, app_session):
        """Error when student_id doesn't belong to tenant."""
        env = await _seed_story_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolPortfolioService(app_session)
        data = _make_story_data(uuid4())  # random UUID

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.create_learning_story(
                tenant_id=env["tenant_id"],
                data=data,
                created_by=env["user_id"],
            )
        assert exc_info.value.code == "not_found"

    async def test_list_learning_stories_by_student(self, admin_session, app_session):
        """List stories filtered by student_id."""
        env = await _seed_story_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        # 2 stories for student_1, 1 for student_2
        for i in range(2):
            await service.create_learning_story(
                tenant_id=env["tenant_id"],
                data=_make_story_data(env["student1_id"], title=f"Story A-{i}"),
                created_by=env["user_id"],
            )
        await service.create_learning_story(
            tenant_id=env["tenant_id"],
            data=_make_story_data(env["student2_id"], title="Story B-0"),
            created_by=env["user_id"],
        )

        s1 = await service.list_learning_stories(
            env["tenant_id"], student_id=env["student1_id"],
        )
        s2 = await service.list_learning_stories(
            env["tenant_id"], student_id=env["student2_id"],
        )

        assert len(s1) == 2
        assert len(s2) == 1

    async def test_list_learning_stories_shared_only(self, admin_session, app_session):
        """Shared-only filter returns only parent-visible stories."""
        env = await _seed_story_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        # 1 shared, 1 not shared
        await service.create_learning_story(
            tenant_id=env["tenant_id"],
            data=_make_story_data(env["student1_id"], is_shared_with_parents=True, title="Shared story"),
            created_by=env["user_id"],
        )
        await service.create_learning_story(
            tenant_id=env["tenant_id"],
            data=_make_story_data(env["student1_id"], is_shared_with_parents=False, title="Internal draft"),
            created_by=env["user_id"],
        )

        shared = await service.list_learning_stories(
            env["tenant_id"],
            student_id=env["student1_id"],
            shared_only=True,
        )
        all_stories = await service.list_learning_stories(
            env["tenant_id"],
            student_id=env["student1_id"],
        )

        assert len(shared) == 1
        assert shared[0].title == "Shared story"
        assert len(all_stories) == 2

    async def test_get_learning_story(self, admin_session, app_session):
        """Get a learning story by ID and verify all fields."""
        env = await _seed_story_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        created = await service.create_learning_story(
            tenant_id=env["tenant_id"],
            data=_make_story_data(env["student1_id"], title="Painting day"),
            created_by=env["user_id"],
        )

        fetched = await service.get_learning_story(env["tenant_id"], created.id)

        assert fetched.id == created.id
        assert fetched.title == "Painting day"
        assert fetched.student_id == env["student1_id"]
        assert fetched.created_by == env["user_id"]

    async def test_update_learning_story(self, admin_session, app_session):
        """Update a learning story title and verify the change persists."""
        env = await _seed_story_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        story = await service.create_learning_story(
            tenant_id=env["tenant_id"],
            data=_make_story_data(env["student1_id"], title="Original title"),
            created_by=env["user_id"],
        )

        updated = await service.update_learning_story(
            tenant_id=env["tenant_id"],
            story_id=story.id,
            data=LearningStoryUpdate(title="Revised title"),
        )

        assert updated.title == "Revised title"
        # Narrative unchanged
        assert updated.narrative == story.narrative

    async def test_delete_learning_story(self, admin_session, app_session):
        """Soft-delete a learning story — it no longer appears in list."""
        env = await _seed_story_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        story = await service.create_learning_story(
            tenant_id=env["tenant_id"],
            data=_make_story_data(env["student1_id"]),
            created_by=env["user_id"],
        )

        await service.delete_learning_story(env["tenant_id"], story.id)

        results = await service.list_learning_stories(
            env["tenant_id"], student_id=env["student1_id"],
        )
        assert len(results) == 0

        # get_learning_story should also raise not_found for soft-deleted records
        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.get_learning_story(env["tenant_id"], story.id)
        assert exc_info.value.code == "not_found"

    async def test_learning_story_rls(self, admin_session, app_session):
        """Learning stories from tenant A are invisible when querying as tenant B."""
        # Seed tenant A
        env_a = await _seed_story_env(admin_session)

        # Insert a learning story for tenant A directly via admin (bypasses RLS)
        story_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO learning_stories (id, tenant_id, student_id, title, narrative,
                is_shared_with_parents, created_by, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'Tenant A story', 'This is tenant A narrative text for testing.',
                true, CAST(:uid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(story_id),
            "tid": str(env_a["tenant_id"]),
            "sid": str(env_a["student1_id"]),
            "uid": str(env_a["user_id"]),
        })
        await admin_session.commit()

        # Seed tenant B
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Query as tenant B — should see 0 learning stories
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM learning_stories")
        )
        count = result.scalar()
        assert count == 0, (
            f"Tenant B should see 0 learning stories but saw {count}"
        )
