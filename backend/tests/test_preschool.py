"""
SIMS Plus - Preschool Module Integration Tests

Tests exercise the preschool service layer directly against a real PostgreSQL database.
They verify learning area management, developmental skill CRUD, rating scales,
student skill assessments, progress observations, daily activity logs,
preschool reports, and tenant isolation.

Key behaviors tested:
- Learning area CRUD and seeding
- Developmental skill CRUD (single and bulk)
- Rating scale creation with child ratings
- Default rating scale seeding (idempotent)
- Student skill assessments (create, update, bulk)
- Progress observations (create, list with date filter, update)
- Daily activity logs (create/upsert, list by date)
- Preschool reports (create, generate, publish)
- Tenant isolation for all preschool-scoped data

NOTES:
- Uses admin_session (superuser) for both seeding and service calls.
  This bypasses RLS so we can test service-layer logic in isolation.
- For RLS-specific isolation, see test_rls_isolation.py.
- app_session is used only in tenant isolation tests where RLS enforcement matters.
- Preschool service methods accept Pydantic schema objects as input, so we
  construct them in the tests.
"""

import pytest
from datetime import date, time, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    LearningAreaCreate,
    LearningAreaUpdate,
    DevelopmentalSkillCreate,
    DevelopmentalSkillBulkCreate,
    DevelopmentalSkillBase,
    PreschoolRatingScaleCreate,
    PreschoolRatingCreate,
    StudentSkillAssessmentCreate,
    StudentSkillAssessmentBulk,
    SkillAssessmentEntry,
    ProgressObservationCreate,
    ProgressObservationUpdate,
    DailyActivityLogCreate,
    MealEntry,
    PreschoolReportCreate,
    LearningAreaSummary,
)

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
        'basic', 'active', 'STU', 'STF', true,
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
        date_of_birth, gender, status, class_id,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
        '2021-05-10', 'female', 'active', CAST(:cid AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


# ============================================================
# Seed helper functions
# ============================================================


async def _seed_preschool_environment(session: AsyncSession) -> dict:
    """
    Create a full environment for preschool tests:
    tenant, school, academic year, term, class (nursery), 2 students, 1 user.

    Returns a dict with all IDs.
    """
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
        "name": "Preschool Academy", "slug": tenant["subdomain"],
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
        "name": "Nursery 1", "level": "nursery_1", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student1_id), "tid": str(tid), "sid": "PRE-001",
        "fn": "Esi", "ln": "Owusu", "cid": str(class_id),
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student2_id), "tid": str(tid), "sid": "PRE-002",
        "fn": "Kofi", "ln": "Boateng", "cid": str(class_id),
    })

    await session.flush()

    return {
        "tenant_id": tid,
        "subdomain": tenant["subdomain"],
        "school_id": school_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "student1_id": student1_id,
        "student2_id": student2_id,
        "user_id": user["id"],
    }


# ============================================================
# Learning Area Tests
# ============================================================

@pytest.mark.asyncio
class TestLearningAreas:
    """Tests for learning area CRUD and seeding."""

    async def test_create_learning_area(self, admin_session):
        """Creating a learning area returns with correct name and code."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(
                name="Social-Emotional Development",
                code="SED",
                description="Building relationships and social skills",
                display_order=1,
            ),
        )

        assert area is not None
        assert area.name == "Social-Emotional Development"
        assert area.code == "SED"
        assert area.tenant_id == env["tenant_id"]
        assert area.is_active is True

    async def test_get_learning_area_with_skills(self, admin_session):
        """Getting a learning area loads its skills."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Language", code="LANG"),
        )

        # Add a skill
        await service.create_skill(
            tenant_id=env["tenant_id"],
            data=DevelopmentalSkillCreate(
                learning_area_id=area.id,
                name="Speaks in complete sentences",
            ),
        )

        fetched = await service.get_learning_area(env["tenant_id"], area.id)
        assert fetched is not None
        assert len(fetched.skills) == 1
        assert fetched.skills[0].name == "Speaks in complete sentences"

    async def test_list_learning_areas_excludes_inactive(self, admin_session):
        """List learning areas excludes inactive ones by default."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Active Area", code="AA", is_active=True),
        )
        area2 = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Inactive Area", code="IA", is_active=False),
        )

        areas = await service.list_learning_areas(env["tenant_id"])
        codes = [a.code for a in areas]
        assert "AA" in codes
        assert "IA" not in codes

        # Include inactive
        areas_all = await service.list_learning_areas(env["tenant_id"], include_inactive=True)
        codes_all = [a.code for a in areas_all]
        assert "IA" in codes_all

    async def test_seed_learning_areas_is_idempotent(self, admin_session):
        """Seeding learning areas twice returns existing areas without duplicates."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        areas_first = await service.seed_learning_areas(env["tenant_id"])
        areas_second = await service.seed_learning_areas(env["tenant_id"])

        assert len(areas_first) == len(areas_second)

    async def test_seed_learning_areas_includes_skills(self, admin_session):
        """Seeding with include_skills=True creates skills for each area."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        areas = await service.seed_learning_areas(env["tenant_id"], include_skills=True)

        # Verify at least one area has skills
        assert len(areas) > 0
        skills = await service.list_skills(env["tenant_id"])
        assert len(skills) > 0

    async def test_delete_learning_area_soft_deletes(self, admin_session):
        """Deleting a learning area sets deleted_at."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="To Delete", code="DEL"),
        )

        await service.delete_learning_area(area)

        with pytest.raises(PreschoolServiceError, match="not found"):
            await service.get_learning_area(env["tenant_id"], area.id)


# ============================================================
# Developmental Skill Tests
# ============================================================

@pytest.mark.asyncio
class TestDevelopmentalSkills:
    """Tests for developmental skill CRUD."""

    async def test_create_skill(self, admin_session):
        """Creating a skill assigns it to a learning area."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Motor Skills", code="MS"),
        )

        skill = await service.create_skill(
            tenant_id=env["tenant_id"],
            data=DevelopmentalSkillCreate(
                learning_area_id=area.id,
                name="Holds crayon correctly",
                age_range_months_min=36,
                age_range_months_max=60,
            ),
        )

        assert skill is not None
        assert skill.name == "Holds crayon correctly"
        assert skill.learning_area_id == area.id
        assert skill.age_range_months_min == 36

    async def test_bulk_create_skills(self, admin_session):
        """Bulk creating skills creates multiple records at once."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Numeracy", code="NUM"),
        )

        skills = await service.bulk_create_skills(
            tenant_id=env["tenant_id"],
            data=DevelopmentalSkillBulkCreate(
                learning_area_id=area.id,
                skills=[
                    DevelopmentalSkillBase(name="Counts to 10"),
                    DevelopmentalSkillBase(name="Recognizes shapes"),
                    DevelopmentalSkillBase(name="Sorts by color"),
                ],
            ),
        )

        assert len(skills) == 3
        names = {s.name for s in skills}
        assert "Counts to 10" in names
        assert "Recognizes shapes" in names

    async def test_list_skills_filtered_by_learning_area(self, admin_session):
        """Listing skills can filter by learning area."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area1 = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Area 1", code="A1"),
        )
        area2 = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Area 2", code="A2"),
        )

        await service.create_skill(
            tenant_id=env["tenant_id"],
            data=DevelopmentalSkillCreate(learning_area_id=area1.id, name="Skill A"),
        )
        await service.create_skill(
            tenant_id=env["tenant_id"],
            data=DevelopmentalSkillCreate(learning_area_id=area2.id, name="Skill B"),
        )

        skills = await service.list_skills(env["tenant_id"], learning_area_id=area1.id)
        assert len(skills) == 1
        assert skills[0].name == "Skill A"


# ============================================================
# Rating Scale Tests
# ============================================================

@pytest.mark.asyncio
class TestRatingScales:
    """Tests for rating scale creation and seeding."""

    async def test_create_rating_scale_with_ratings(self, admin_session):
        """Creating a rating scale also creates its child ratings."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        scale = await service.create_rating_scale(
            tenant_id=env["tenant_id"],
            data=PreschoolRatingScaleCreate(
                name="3-Point Scale",
                description="Simple 3-point scale",
                is_default=True,
                ratings=[
                    PreschoolRatingCreate(
                        name="Emerging", short_code="E",
                        numeric_value=1, display_order=1,
                    ),
                    PreschoolRatingCreate(
                        name="Developing", short_code="D",
                        numeric_value=2, display_order=2,
                    ),
                    PreschoolRatingCreate(
                        name="Proficient", short_code="P",
                        numeric_value=3, display_order=3,
                    ),
                ],
            ),
        )

        assert scale is not None
        assert scale.name == "3-Point Scale"
        assert scale.is_default is True

        # Refresh and load ratings
        fetched = await service.get_rating_scale(env["tenant_id"], scale.id)
        assert len(fetched.ratings) == 3

    async def test_seed_default_rating_scale(self, admin_session):
        """Seeding creates a 5-point scale with ratings."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        scale = await service.seed_rating_scale(env["tenant_id"])

        assert scale is not None
        assert scale.name == "5-Point Developmental Scale"
        assert scale.is_default is True

    async def test_seed_rating_scale_is_idempotent(self, admin_session):
        """Seeding rating scale twice returns the existing scale."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        scale1 = await service.seed_rating_scale(env["tenant_id"])
        scale2 = await service.seed_rating_scale(env["tenant_id"])

        assert scale1.id == scale2.id

    async def test_get_default_rating_scale(self, admin_session):
        """Get default rating scale returns the default scale."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.seed_rating_scale(env["tenant_id"])

        default = await service.get_default_rating_scale(env["tenant_id"])
        assert default is not None
        assert default.is_default is True

    async def test_get_default_rating_scale_raises_when_none(self, admin_session):
        """Get default raises error when no default scale exists."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        with pytest.raises(PreschoolServiceError, match="No default rating scale"):
            await service.get_default_rating_scale(env["tenant_id"])

    async def test_delete_rating_scale_soft_deletes_ratings(self, admin_session):
        """Deleting a rating scale soft-deletes its ratings too."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        scale = await service.seed_rating_scale(env["tenant_id"])
        fetched = await service.get_rating_scale(env["tenant_id"], scale.id)

        await service.delete_rating_scale(fetched)

        with pytest.raises(PreschoolServiceError, match="not found"):
            await service.get_rating_scale(env["tenant_id"], scale.id)


# ============================================================
# Student Skill Assessment Tests
# ============================================================

@pytest.mark.asyncio
class TestStudentSkillAssessments:
    """Tests for student skill assessments."""

    async def _setup_assessment_env(self, admin_session):
        """Helper: create environment with learning area, skill, and rating scale."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Language", code="LNG"),
        )
        skill = await service.create_skill(
            tenant_id=env["tenant_id"],
            data=DevelopmentalSkillCreate(
                learning_area_id=area.id,
                name="Recognizes own name",
            ),
        )
        scale = await service.seed_rating_scale(env["tenant_id"])
        fetched_scale = await service.get_rating_scale(env["tenant_id"], scale.id)
        rating = fetched_scale.ratings[2]  # "Developing" (numeric_value=2)

        env["area_id"] = area.id
        env["skill_id"] = skill.id
        env["scale_id"] = scale.id
        env["rating_id"] = rating.id
        return env

    async def test_create_assessment(self, admin_session):
        """Creating an assessment records a student's skill progress."""
        env = await self._setup_assessment_env(admin_session)
        service = PreschoolService(admin_session)

        assessment = await service.create_or_update_assessment(
            tenant_id=env["tenant_id"],
            data=StudentSkillAssessmentCreate(
                student_id=env["student1_id"],
                skill_id=env["skill_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                rating_id=env["rating_id"],
                observation_notes="Starting to recognize letters",
            ),
            user_id=env["user_id"],
        )

        assert assessment is not None
        assert assessment.student_id == env["student1_id"]
        assert assessment.rating_id == env["rating_id"]
        assert assessment.observation_notes == "Starting to recognize letters"

    async def test_update_assessment_upserts(self, admin_session):
        """Creating assessment for same student+skill+term updates existing."""
        env = await self._setup_assessment_env(admin_session)
        service = PreschoolService(admin_session)

        # Create initial
        a1 = await service.create_or_update_assessment(
            tenant_id=env["tenant_id"],
            data=StudentSkillAssessmentCreate(
                student_id=env["student1_id"],
                skill_id=env["skill_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                rating_id=env["rating_id"],
                observation_notes="First note",
            ),
            user_id=env["user_id"],
        )

        # Update (same student+skill+term)
        a2 = await service.create_or_update_assessment(
            tenant_id=env["tenant_id"],
            data=StudentSkillAssessmentCreate(
                student_id=env["student1_id"],
                skill_id=env["skill_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                rating_id=env["rating_id"],
                observation_notes="Updated note",
            ),
            user_id=env["user_id"],
        )

        assert a1.id == a2.id  # Same record, updated
        assert a2.observation_notes == "Updated note"

    async def test_bulk_assess_creates_and_updates(self, admin_session):
        """Bulk assess creates new and updates existing assessments."""
        env = await self._setup_assessment_env(admin_session)
        service = PreschoolService(admin_session)

        # Add a second skill
        skill2 = await service.create_skill(
            tenant_id=env["tenant_id"],
            data=DevelopmentalSkillCreate(
                learning_area_id=env["area_id"],
                name="Speaks in sentences",
            ),
        )

        result = await service.bulk_assess(
            tenant_id=env["tenant_id"],
            data=StudentSkillAssessmentBulk(
                student_id=env["student1_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                assessments=[
                    SkillAssessmentEntry(
                        skill_id=env["skill_id"],
                        rating_id=env["rating_id"],
                    ),
                    SkillAssessmentEntry(
                        skill_id=skill2.id,
                        rating_id=env["rating_id"],
                        observation_notes="Improving steadily",
                    ),
                ],
            ),
            user_id=env["user_id"],
        )

        assert result["created"] == 2
        assert result["updated"] == 0

    async def test_list_assessments_filtered_by_student(self, admin_session):
        """List assessments can filter by student_id."""
        env = await self._setup_assessment_env(admin_session)
        service = PreschoolService(admin_session)

        await service.create_or_update_assessment(
            tenant_id=env["tenant_id"],
            data=StudentSkillAssessmentCreate(
                student_id=env["student1_id"],
                skill_id=env["skill_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                rating_id=env["rating_id"],
            ),
            user_id=env["user_id"],
        )

        assessments = await service.list_assessments(
            tenant_id=env["tenant_id"],
            student_id=env["student1_id"],
        )

        assert len(assessments) == 1
        assert assessments[0].student_id == env["student1_id"]


# ============================================================
# Progress Observation Tests
# ============================================================

@pytest.mark.asyncio
class TestProgressObservations:
    """Tests for progress observation CRUD."""

    async def test_create_observation(self, admin_session):
        """Creating an observation returns with correct fields."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        obs = await service.create_observation(
            tenant_id=env["tenant_id"],
            data=ProgressObservationCreate(
                student_id=env["student1_id"],
                observation_type="anecdote",
                title="First day sharing toys",
                description="Esi shared crayons with a classmate without prompting.",
                observation_date=date(2025, 9, 15),
                share_with_parents=True,
                is_highlight=True,
            ),
            user_id=env["user_id"],
        )

        assert obs is not None
        assert obs.title == "First day sharing toys"
        assert obs.observation_type == "anecdote"
        assert obs.share_with_parents is True
        assert obs.is_highlight is True

    async def test_list_observations_filtered_by_date_range(self, admin_session):
        """Listing observations respects start_date and end_date filters."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.create_observation(
            tenant_id=env["tenant_id"],
            data=ProgressObservationCreate(
                student_id=env["student1_id"],
                title="September observation",
                observation_date=date(2025, 9, 10),
            ),
            user_id=env["user_id"],
        )
        await service.create_observation(
            tenant_id=env["tenant_id"],
            data=ProgressObservationCreate(
                student_id=env["student1_id"],
                title="November observation",
                observation_date=date(2025, 11, 5),
            ),
            user_id=env["user_id"],
        )

        # Filter to October-November only
        obs = await service.list_observations(
            tenant_id=env["tenant_id"],
            student_id=env["student1_id"],
            start_date=date(2025, 10, 1),
            end_date=date(2025, 11, 30),
        )

        assert len(obs) == 1
        assert obs[0].title == "November observation"

    async def test_update_observation(self, admin_session):
        """Updating an observation changes the notes."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        obs = await service.create_observation(
            tenant_id=env["tenant_id"],
            data=ProgressObservationCreate(
                student_id=env["student1_id"],
                title="Initial title",
                observation_date=date(2025, 9, 20),
            ),
            user_id=env["user_id"],
        )

        updated = await service.update_observation(
            observation=obs,
            data=ProgressObservationUpdate(title="Updated title", description="Added detail"),
        )

        assert updated.title == "Updated title"
        assert updated.description == "Added detail"

    async def test_delete_observation_soft_deletes(self, admin_session):
        """Deleting an observation sets deleted_at."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        obs = await service.create_observation(
            tenant_id=env["tenant_id"],
            data=ProgressObservationCreate(
                student_id=env["student1_id"],
                title="To Delete",
                observation_date=date(2025, 9, 25),
            ),
            user_id=env["user_id"],
        )

        await service.delete_observation(obs)

        with pytest.raises(PreschoolServiceError, match="not found"):
            await service.get_observation(env["tenant_id"], obs.id)

    async def test_create_observation_with_learning_area(self, admin_session):
        """Observation can link to a specific learning area."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Motor", code="MOT"),
        )

        obs = await service.create_observation(
            tenant_id=env["tenant_id"],
            data=ProgressObservationCreate(
                student_id=env["student1_id"],
                learning_area_id=area.id,
                title="Gross motor milestone",
                observation_date=date(2025, 10, 1),
                observation_type="milestone",
            ),
            user_id=env["user_id"],
        )

        assert obs.learning_area_id == area.id


# ============================================================
# Daily Activity Log Tests
# ============================================================

@pytest.mark.asyncio
class TestDailyActivityLogs:
    """Tests for daily activity log creation and retrieval."""

    async def test_create_daily_log(self, admin_session):
        """Creating a daily log returns with activity details."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        log = await service.create_or_update_daily_log(
            tenant_id=env["tenant_id"],
            data=DailyActivityLogCreate(
                student_id=env["student1_id"],
                log_date=date(2025, 9, 15),
                arrival_time=time(8, 0),
                arrival_mood="happy",
                departure_time=time(14, 0),
                departure_mood="tired",
                meals=[
                    MealEntry(type="breakfast", time="08:30", amount="all"),
                    MealEntry(type="lunch", time="12:00", amount="most"),
                ],
                nap_start=time(12, 30),
                nap_end=time(13, 30),
                nap_quality="good",
                activities=["outdoor_play", "art", "story_time"],
                notes="Great day overall",
                highlights="Made a beautiful drawing",
            ),
            user_id=env["user_id"],
        )

        assert log is not None
        assert log.arrival_mood == "happy"
        assert log.departure_mood == "tired"
        assert log.nap_quality == "good"
        assert len(log.meals) == 2
        assert len(log.activities) == 3
        assert log.highlights == "Made a beautiful drawing"

    async def test_create_daily_log_upserts_on_same_date(self, admin_session):
        """Creating a log for the same student+date updates the existing one."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        log1 = await service.create_or_update_daily_log(
            tenant_id=env["tenant_id"],
            data=DailyActivityLogCreate(
                student_id=env["student1_id"],
                log_date=date(2025, 9, 16),
                arrival_mood="happy",
            ),
            user_id=env["user_id"],
        )

        log2 = await service.create_or_update_daily_log(
            tenant_id=env["tenant_id"],
            data=DailyActivityLogCreate(
                student_id=env["student1_id"],
                log_date=date(2025, 9, 16),
                arrival_mood="excited",
            ),
            user_id=env["user_id"],
        )

        assert log1.id == log2.id  # Same record, updated
        assert log2.arrival_mood == "excited"

    async def test_list_daily_logs_filtered_by_date(self, admin_session):
        """Listing daily logs filters by date range."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.create_or_update_daily_log(
            tenant_id=env["tenant_id"],
            data=DailyActivityLogCreate(
                student_id=env["student1_id"],
                log_date=date(2025, 9, 10),
            ),
            user_id=env["user_id"],
        )
        await service.create_or_update_daily_log(
            tenant_id=env["tenant_id"],
            data=DailyActivityLogCreate(
                student_id=env["student1_id"],
                log_date=date(2025, 10, 5),
            ),
            user_id=env["user_id"],
        )

        logs = await service.list_daily_logs(
            tenant_id=env["tenant_id"],
            student_id=env["student1_id"],
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31),
        )

        assert len(logs) == 1
        assert logs[0].log_date == date(2025, 10, 5)

    async def test_list_daily_logs_for_specific_date(self, admin_session):
        """Listing daily logs can filter for a specific date."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.create_or_update_daily_log(
            tenant_id=env["tenant_id"],
            data=DailyActivityLogCreate(
                student_id=env["student1_id"],
                log_date=date(2025, 9, 20),
                notes="Specific day",
            ),
            user_id=env["user_id"],
        )

        logs = await service.list_daily_logs(
            tenant_id=env["tenant_id"],
            log_date=date(2025, 9, 20),
        )

        assert len(logs) == 1
        assert logs[0].notes == "Specific day"


# ============================================================
# Preschool Report Tests
# ============================================================

@pytest.mark.asyncio
class TestPreschoolReports:
    """Tests for preschool report generation and publishing."""

    async def test_create_report(self, admin_session):
        """Creating a report returns with narrative fields."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        report = await service.create_report(
            tenant_id=env["tenant_id"],
            data=PreschoolReportCreate(
                student_id=env["student1_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                class_id=env["class_id"],
                days_present=55,
                days_absent=5,
                total_school_days=60,
                overall_progress="Esi has shown excellent progress this term.",
                strengths="Strong social skills and creativity.",
                areas_for_growth="Number recognition needs more practice.",
                teacher_recommendations="Continue reading at home.",
                highlights=["Learned to tie shoes", "Made first friend"],
                next_term_goals=["Count to 20", "Write own name"],
                class_teacher_remark="A joy to have in class.",
            ),
        )

        assert report is not None
        assert report.overall_progress == "Esi has shown excellent progress this term."
        assert report.days_present == 55
        assert report.is_published is False
        assert len(report.highlights) == 2
        assert len(report.next_term_goals) == 2

    async def test_create_report_with_learning_area_summaries(self, admin_session):
        """Creating a report can include learning area summaries."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env["tenant_id"],
            data=LearningAreaCreate(name="Social", code="SOC"),
        )

        report = await service.create_report(
            tenant_id=env["tenant_id"],
            data=PreschoolReportCreate(
                student_id=env["student1_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                class_id=env["class_id"],
                learning_area_summaries=[
                    LearningAreaSummary(
                        learning_area_id=area.id,
                        learning_area_name="Social",
                        rating="proficient",
                        summary="Plays well with others.",
                    ),
                ],
            ),
        )

        assert report.learning_area_summaries is not None
        assert len(report.learning_area_summaries) == 1

    async def test_generate_reports_for_class(self, admin_session):
        """Generate reports creates blank reports for all students in a class."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        result = await service.generate_reports(
            tenant_id=env["tenant_id"],
            class_id=env["class_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
        )

        assert result["total_students"] == 2
        assert result["generated"] == 2

    async def test_generate_reports_is_idempotent(self, admin_session):
        """Generating reports twice does not create duplicates."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        result1 = await service.generate_reports(
            tenant_id=env["tenant_id"],
            class_id=env["class_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
        )
        result2 = await service.generate_reports(
            tenant_id=env["tenant_id"],
            class_id=env["class_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
        )

        assert result1["generated"] == 2
        assert result2["generated"] == 0  # Already exist

    async def test_publish_reports(self, admin_session):
        """Publishing reports sets is_published=True and published_at."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        report = await service.create_report(
            tenant_id=env["tenant_id"],
            data=PreschoolReportCreate(
                student_id=env["student1_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                class_id=env["class_id"],
            ),
        )
        assert report.is_published is False

        published = await service.publish_reports(
            tenant_id=env["tenant_id"],
            report_ids=[report.id],
        )

        assert len(published) == 1
        assert published[0].is_published is True
        assert published[0].published_at is not None

    async def test_list_reports_filtered_by_published(self, admin_session):
        """List reports can filter by published status."""
        env = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        report = await service.create_report(
            tenant_id=env["tenant_id"],
            data=PreschoolReportCreate(
                student_id=env["student1_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                class_id=env["class_id"],
            ),
        )

        # Unpublished
        unpublished = await service.list_reports(
            tenant_id=env["tenant_id"],
            is_published=False,
        )
        assert len(unpublished) == 1

        # Publish it
        await service.publish_reports(
            tenant_id=env["tenant_id"],
            report_ids=[report.id],
        )

        # Now filter published
        published = await service.list_reports(
            tenant_id=env["tenant_id"],
            is_published=True,
        )
        assert len(published) == 1


# ============================================================
# Tenant Isolation Tests
# ============================================================

@pytest.mark.asyncio
class TestPreschoolTenantIsolation:
    """Tenant A must NOT see Tenant B's preschool data.

    Uses app_session (RLS enforced) to verify isolation.
    """

    async def test_tenant_a_cannot_see_tenant_b_learning_areas(
        self, admin_session, app_session
    ):
        """Learning areas created for Tenant A are invisible to Tenant B."""
        env_a = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env_a["tenant_id"],
            data=LearningAreaCreate(name="Iso Area", code="ISO"),
        )
        area_id = area.id
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM learning_areas WHERE id = CAST(:aid AS uuid)"),
            {"aid": str(area_id)},
        )
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's learning areas"

    async def test_tenant_a_cannot_see_tenant_b_observations(
        self, admin_session, app_session
    ):
        """Observations for Tenant A are invisible to Tenant B."""
        env_a = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.create_observation(
            tenant_id=env_a["tenant_id"],
            data=ProgressObservationCreate(
                student_id=env_a["student1_id"],
                title="Tenant A observation",
                observation_date=date(2025, 9, 15),
            ),
            user_id=env_a["user_id"],
        )
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM progress_observations")
        )
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's observations"

    async def test_tenant_a_cannot_see_tenant_b_daily_logs(
        self, admin_session, app_session
    ):
        """Daily logs for Tenant A are invisible to Tenant B."""
        env_a = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.create_or_update_daily_log(
            tenant_id=env_a["tenant_id"],
            data=DailyActivityLogCreate(
                student_id=env_a["student1_id"],
                log_date=date(2025, 9, 15),
            ),
            user_id=env_a["user_id"],
        )
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM daily_activity_logs")
        )
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's daily logs"

    async def test_tenant_a_cannot_see_tenant_b_preschool_reports(
        self, admin_session, app_session
    ):
        """Preschool reports for Tenant A are invisible to Tenant B."""
        env_a = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.create_report(
            tenant_id=env_a["tenant_id"],
            data=PreschoolReportCreate(
                student_id=env_a["student1_id"],
                academic_year_id=env_a["ay_id"],
                term_id=env_a["term_id"],
                class_id=env_a["class_id"],
            ),
        )
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM preschool_reports")
        )
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's preschool reports"

    async def test_tenant_a_cannot_see_tenant_b_skill_assessments(
        self, admin_session, app_session
    ):
        """Skill assessments for Tenant A are invisible to Tenant B."""
        env_a = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        area = await service.create_learning_area(
            tenant_id=env_a["tenant_id"],
            data=LearningAreaCreate(name="Iso Skills", code="ISK"),
        )
        skill = await service.create_skill(
            tenant_id=env_a["tenant_id"],
            data=DevelopmentalSkillCreate(
                learning_area_id=area.id,
                name="Iso Skill",
            ),
        )
        scale = await service.seed_rating_scale(env_a["tenant_id"])
        fetched_scale = await service.get_rating_scale(env_a["tenant_id"], scale.id)
        rating = fetched_scale.ratings[0]

        await service.create_or_update_assessment(
            tenant_id=env_a["tenant_id"],
            data=StudentSkillAssessmentCreate(
                student_id=env_a["student1_id"],
                skill_id=skill.id,
                academic_year_id=env_a["ay_id"],
                term_id=env_a["term_id"],
                rating_id=rating.id,
            ),
            user_id=env_a["user_id"],
        )
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM student_skill_assessments")
        )
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's skill assessments"

    async def test_tenant_a_cannot_see_tenant_b_rating_scales(
        self, admin_session, app_session
    ):
        """Rating scales for Tenant A are invisible to Tenant B."""
        env_a = await _seed_preschool_environment(admin_session)
        service = PreschoolService(admin_session)

        await service.seed_rating_scale(env_a["tenant_id"])
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM preschool_rating_scales")
        )
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's rating scales"
