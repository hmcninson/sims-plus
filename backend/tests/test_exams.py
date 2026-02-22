"""
SIMS Plus - Exam Module Integration Tests

Tests exercise the exam service layer directly against a real PostgreSQL database.
They verify exam CRUD, score entry, continuous assessment, report generation,
and analytics through the service classes with the admin session (superuser).

Key behaviors tested:
- Exam CRUD with status transitions
- Exam subject management
- Score entry with grade calculation and audit logging
- Continuous assessment CRUD and summaries
- Term report generation and ranking
- Analytics: grade distribution, class/subject statistics
- Tenant isolation for all exam-scoped data

NOTES:
- Uses admin_session (superuser) for both seeding and service calls.
  This bypasses RLS so we can test service-layer logic in isolation.
- For RLS-specific isolation, see test_rls_isolation.py.
- app_session is used only in tenant isolation tests where RLS enforcement matters.
"""

import pytest
from datetime import date, datetime, UTC
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.exam.exam_service import ExamService, ExamServiceError
from app.services.exam.score_service import ScoreService
from app.services.exam.ca_service import CAService
from app.services.exam.report_service import TermReportService
from app.services.exam.analytics_service import AnalyticsService
from app.models.exam import ExamStatus, ExamSubjectStatus, ExamType

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

_SUBJECT_INSERT = text("""
    INSERT INTO subjects (id, tenant_id, name, code, category,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code, :cat,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
        date_of_birth, gender, status, class_id,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
        '2012-03-10', 'male', 'active', CAST(:cid AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_GRADING_SCALE_INSERT = text("""
    INSERT INTO grading_scales (id, tenant_id, name, description, is_default,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :desc, true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_GRADE_INSERT = text("""
    INSERT INTO grades (id, tenant_id, grading_scale_id, grade, min_score,
        max_score, grade_point, remark, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:gsid AS uuid),
        :grade, :min_score, :max_score, :gp, :remark,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


# ============================================================
# Seed helper functions
# ============================================================


async def _seed_exam_environment(session: AsyncSession) -> dict:
    """
    Create a full environment for exam tests:
    tenant, school, academic year, term, class, subject, 2 students, grading scale.

    Returns a dict with all IDs.
    """
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_id = uuid4()
    subject_id = uuid4()
    student1_id = uuid4()
    student2_id = uuid4()
    user = await create_test_user(session, tid)
    gs_id = uuid4()

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Exam School", "slug": tenant["subdomain"],
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
        "name": "Primary 6", "level": "primary", "seq": 6,
    })
    await session.execute(_SUBJECT_INSERT, {
        "id": str(subject_id), "tid": str(tid),
        "name": "Mathematics", "code": "MATH", "cat": "core",
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student1_id), "tid": str(tid), "sid": "STU-001",
        "fn": "Kwame", "ln": "Asante", "cid": str(class_id),
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student2_id), "tid": str(tid), "sid": "STU-002",
        "fn": "Ama", "ln": "Mensah", "cid": str(class_id),
    })

    # Create grading scale with grades
    await session.execute(_GRADING_SCALE_INSERT, {
        "id": str(gs_id), "tid": str(tid),
        "name": "WAEC Scale", "desc": "Standard WAEC grading",
    })
    grades_data = [
        ("A1", 80, 100, 1.0, "Excellent"),
        ("B2", 70, 79, 2.0, "Very Good"),
        ("B3", 65, 69, 3.0, "Good"),
        ("C4", 60, 64, 4.0, "Credit"),
        ("C5", 55, 59, 5.0, "Credit"),
        ("C6", 50, 54, 6.0, "Credit"),
        ("D7", 45, 49, 7.0, "Pass"),
        ("E8", 40, 44, 8.0, "Pass"),
        ("F9", 0, 39, 9.0, "Fail"),
    ]
    for grade, min_s, max_s, gp, remark in grades_data:
        await session.execute(_GRADE_INSERT, {
            "id": str(uuid4()), "tid": str(tid), "gsid": str(gs_id),
            "grade": grade, "min_score": min_s, "max_score": max_s,
            "gp": gp, "remark": remark,
        })

    await session.flush()

    return {
        "tenant_id": tid,
        "subdomain": tenant["subdomain"],
        "school_id": school_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "student1_id": student1_id,
        "student2_id": student2_id,
        "user_id": user["id"],
        "grading_scale_id": gs_id,
    }


# ============================================================
# Exam CRUD Tests
# ============================================================

@pytest.mark.asyncio
class TestExamCRUD:
    """Tests for exam create, read, update, delete operations."""

    async def test_create_exam_returns_draft_status(self, admin_session):
        """Creating an exam defaults to draft status."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Mid-Term Exam",
            exam_type="midterm",
        )

        assert exam is not None
        assert exam.name == "Mid-Term Exam"
        assert exam.status == ExamStatus.DRAFT
        assert exam.exam_type == ExamType.MIDTERM
        assert exam.tenant_id == env["tenant_id"]

    async def test_create_duplicate_exam_raises_error(self, admin_session):
        """Creating an exam with the same name in the same term raises an error."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="End of Term",
            exam_type="end_term",
        )

        with pytest.raises(ExamServiceError, match="already exists"):
            await service.create_exam(
                tenant_id=env["tenant_id"],
                academic_year_id=env["ay_id"],
                term_id=env["term_id"],
                name="End of Term",
                exam_type="end_term",
            )

    async def test_get_exam_by_id(self, admin_session):
        """Get exam by ID returns the correct exam."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        created = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Quiz 1",
            exam_type="quiz",
        )

        fetched = await service.get_exam(env["tenant_id"], created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Quiz 1"

    async def test_get_exam_wrong_tenant_returns_none(self, admin_session):
        """Getting an exam with a different tenant_id returns None."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        created = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Quiz 2",
            exam_type="quiz",
        )

        # Use a random tenant_id -- should get None from defense-in-depth filter
        result = await service.get_exam(uuid4(), created.id)
        assert result is None

    async def test_update_exam_status_transitions(self, admin_session):
        """Exam status can be updated through the lifecycle."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Status Test Exam",
            exam_type="end_term",
        )
        assert exam.status == ExamStatus.DRAFT

        # Draft -> Scheduled
        updated = await service.update_exam_status(exam.id, env["tenant_id"], "scheduled")
        assert updated.status == ExamStatus.SCHEDULED

        # Scheduled -> Ongoing
        updated = await service.update_exam_status(exam.id, env["tenant_id"], "ongoing")
        assert updated.status == ExamStatus.ONGOING

        # Ongoing -> Completed
        updated = await service.update_exam_status(exam.id, env["tenant_id"], "completed")
        assert updated.status == ExamStatus.COMPLETED

        # Completed -> Results Published
        updated = await service.update_exam_status(exam.id, env["tenant_id"], "results_published")
        assert updated.status == ExamStatus.RESULTS_PUBLISHED

    async def test_cancel_exam(self, admin_session):
        """Exam status can be set to cancelled."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Cancelled Exam",
            exam_type="quiz",
        )

        updated = await service.update_exam_status(exam.id, env["tenant_id"], "cancelled")
        assert updated.status == ExamStatus.CANCELLED

    async def test_delete_exam_soft_deletes(self, admin_session):
        """Deleting an exam sets deleted_at (soft delete)."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="To Delete",
            exam_type="quiz",
        )

        result = await service.delete_exam(exam.id, env["tenant_id"])
        assert result is True

        # Should not be retrievable anymore
        fetched = await service.get_exam(env["tenant_id"], exam.id)
        assert fetched is None

    async def test_list_exams_filtered_by_term(self, admin_session):
        """List exams returns only exams for the specified term."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Exam A",
            exam_type="midterm",
        )
        await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Exam B",
            exam_type="end_term",
        )

        exams, total = await service.list_exams(
            tenant_id=env["tenant_id"],
            term_id=env["term_id"],
        )

        assert total == 2
        assert len(exams) == 2
        names = {e.name for e in exams}
        assert "Exam A" in names
        assert "Exam B" in names

    async def test_list_exams_filtered_by_status(self, admin_session):
        """List exams can filter by status."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Scheduled Exam",
            exam_type="midterm",
        )
        await service.update_exam_status(exam.id, env["tenant_id"], "scheduled")

        await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Draft Exam",
            exam_type="quiz",
        )

        exams, total = await service.list_exams(
            tenant_id=env["tenant_id"],
            status="scheduled",
        )

        assert total == 1
        assert exams[0].name == "Scheduled Exam"


# ============================================================
# Exam Subject Tests
# ============================================================

@pytest.mark.asyncio
class TestExamSubjects:
    """Tests for adding and managing exam subjects."""

    async def test_add_exam_subject(self, admin_session):
        """Adding a subject to an exam creates an ExamSubject record."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Subject Test Exam",
            exam_type="end_term",
        )

        es = await service.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
            max_score=Decimal("100.00"),
            pass_mark=Decimal("50.00"),
            grading_scale_id=env["grading_scale_id"],
        )

        assert es is not None
        assert es.exam_id == exam.id
        assert es.subject_id == env["subject_id"]
        assert es.status == ExamSubjectStatus.PENDING
        assert es.max_score == Decimal("100.00")

    async def test_add_duplicate_exam_subject_raises_error(self, admin_session):
        """Adding the same subject+class combo to an exam raises error."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Dup Subject Exam",
            exam_type="end_term",
        )

        await service.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        with pytest.raises(ExamServiceError, match="already added"):
            await service.add_exam_subject(
                tenant_id=env["tenant_id"],
                exam_id=exam.id,
                subject_id=env["subject_id"],
                class_id=env["class_id"],
            )

    async def test_list_exam_subjects(self, admin_session):
        """Listing exam subjects returns all subjects for an exam."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        # Add a second subject
        subject2_id = uuid4()
        await admin_session.execute(_SUBJECT_INSERT, {
            "id": str(subject2_id), "tid": str(env["tenant_id"]),
            "name": "English", "code": "ENG", "cat": "core",
        })
        await admin_session.flush()

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Multi-Subject Exam",
            exam_type="end_term",
        )

        await service.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )
        await service.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=subject2_id,
            class_id=env["class_id"],
        )

        subjects = await service.list_exam_subjects(env["tenant_id"], exam.id)
        assert len(subjects) == 2

    async def test_delete_exam_subject(self, admin_session):
        """Deleting an exam subject removes it."""
        env = await _seed_exam_environment(admin_session)
        service = ExamService(admin_session)

        exam = await service.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Delete Subject Exam",
            exam_type="quiz",
        )

        es = await service.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        result = await service.delete_exam_subject(es.id, env["tenant_id"])
        assert result is True

        # Verify it is gone
        fetched = await service.get_exam_subject(env["tenant_id"], es.id)
        assert fetched is None


# ============================================================
# Score Entry Tests
# ============================================================

@pytest.mark.asyncio
class TestScoreEntry:
    """Tests for exam score entry and management."""

    async def test_bulk_enter_scores_creates_records(self, admin_session):
        """Bulk entering scores creates ExamScore records."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Score Entry Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
            grading_scale_id=env["grading_scale_id"],
        )

        result = await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 85},
                {"student_id": str(env["student2_id"]), "score": 72},
            ],
            entered_by=env["user_id"],
        )

        assert result["created"] == 2
        assert result["updated"] == 0
        assert result["failed"] == 0

    async def test_bulk_enter_scores_calculates_grades(self, admin_session):
        """Scores get auto-graded when a grading scale is set."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Grading Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
            grading_scale_id=env["grading_scale_id"],
        )

        await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 85},
            ],
            entered_by=env["user_id"],
        )

        # Fetch the score to check grade
        form = await score_svc.get_score_entry_form(env["tenant_id"], es.id)
        student = next(s for s in form["students"] if s["student_id"] == env["student1_id"])
        assert student["current_score"] == Decimal("85.00")
        assert student["current_grade"] == "A1"

    async def test_score_exceeding_max_marks_fails(self, admin_session):
        """A score exceeding max_marks is rejected."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Max Score Exam",
            exam_type="quiz",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
            max_score=Decimal("100.00"),
        )

        result = await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 150},
            ],
        )

        assert result["failed"] == 1
        assert result["created"] == 0
        assert "exceeds max score" in result["errors"][0]["error"]

    async def test_update_score_creates_audit_log(self, admin_session):
        """Updating a score creates a ScoreChangeLog entry."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Audit Log Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        # First entry
        await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 70},
            ],
            entered_by=env["user_id"],
        )

        # Update the score
        await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 80},
            ],
            entered_by=env["user_id"],
        )

        # Check audit logs
        logs, total = await score_svc.get_score_change_logs(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
        )

        # Should have at least 2 logs: created + updated
        assert total >= 2
        change_types = [log["change_type"] for log in logs]
        assert "created" in change_types
        assert "updated" in change_types

    async def test_get_score_entry_form(self, admin_session):
        """Get score entry form returns students with existing scores."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Form Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        form = await score_svc.get_score_entry_form(env["tenant_id"], es.id)

        assert form is not None
        assert form["max_score"] == Decimal("100.00")
        assert len(form["students"]) == 2  # 2 students in the class
        # Students should have no scores yet
        for student in form["students"]:
            assert student["current_score"] is None

    async def test_get_class_results_with_rankings(self, admin_session):
        """Get class results returns students ranked by total score."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Rankings Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 90},
                {"student_id": str(env["student2_id"]), "score": 75},
            ],
        )

        results = await score_svc.get_class_results(
            exam_id=exam.id,
            class_id=env["class_id"],
            tenant_id=env["tenant_id"],
        )

        assert results["exam_name"] == "Rankings Exam"
        assert len(results["students"]) == 2
        # First student (highest score) should be position 1
        assert results["students"][0]["class_position"] == 1
        assert results["students"][0]["total_score"] == Decimal("90")
        assert results["students"][1]["class_position"] == 2

    async def test_get_student_results(self, admin_session):
        """Get student results returns all subject scores for one student."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Student Results Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 88},
                {"student_id": str(env["student2_id"]), "score": 65},
            ],
        )

        results = await score_svc.get_student_results(
            exam_id=exam.id,
            student_id=env["student1_id"],
            tenant_id=env["tenant_id"],
        )

        assert results["exam_name"] == "Student Results Exam"
        assert len(results["students"]) == 1
        student = results["students"][0]
        assert student["student_id"] == env["student1_id"]
        assert student["total_score"] == Decimal("88")
        assert student["class_position"] == 1

    async def test_submit_scores_locks_exam_subject(self, admin_session):
        """Submitting scores changes exam subject status to submitted."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Submit Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        submitted = await score_svc.submit_scores(es.id, env["tenant_id"])
        assert submitted.status == ExamSubjectStatus.SUBMITTED


# ============================================================
# Continuous Assessment Tests
# ============================================================

@pytest.mark.asyncio
class TestContinuousAssessment:
    """Tests for continuous assessment CRUD and summaries."""

    async def test_create_ca_entry(self, admin_session):
        """Creating a CA entry returns with the correct type."""
        env = await _seed_exam_environment(admin_session)
        service = CAService(admin_session)

        ca = await service.create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            student_id=env["student1_id"],
            assessment_type="class_work",
            title="Week 3 Class Test",
            assessment_date=date(2025, 9, 20),
            max_score=Decimal("10.00"),
            score=Decimal("8.50"),
        )

        assert ca is not None
        assert ca.title == "Week 3 Class Test"
        assert ca.score == Decimal("8.50")
        assert ca.max_score == Decimal("10.00")

    async def test_bulk_create_ca(self, admin_session):
        """Bulk CA creates entries for multiple students."""
        env = await _seed_exam_environment(admin_session)
        service = CAService(admin_session)

        result = await service.bulk_create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            assessment_type="homework",
            title="Homework 1",
            assessment_date=date(2025, 9, 15),
            max_score=Decimal("10.00"),
            scores=[
                {"student_id": env["student1_id"], "score": Decimal("7.00")},
                {"student_id": env["student2_id"], "score": Decimal("9.00")},
            ],
        )

        assert result["success"] == 2
        assert result["failed"] == 0

    async def test_get_ca_summary_aggregates_scores(self, admin_session):
        """CA summary returns aggregated per-student scores."""
        env = await _seed_exam_environment(admin_session)
        service = CAService(admin_session)

        # Create two CA entries for the same student
        await service.create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            student_id=env["student1_id"],
            assessment_type="class_work",
            title="CW1",
            assessment_date=date(2025, 9, 10),
            max_score=Decimal("10.00"),
            score=Decimal("8.00"),
        )
        await service.create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            student_id=env["student1_id"],
            assessment_type="homework",
            title="HW1",
            assessment_date=date(2025, 9, 15),
            max_score=Decimal("10.00"),
            score=Decimal("6.00"),
        )

        summary = await service.get_ca_summary(
            tenant_id=env["tenant_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
        )

        assert len(summary) == 1
        student_summary = summary[0]
        assert student_summary["student_id"] == env["student1_id"]
        assert student_summary["total_assessments"] == 2
        assert student_summary["total_score"] == Decimal("14.00")
        assert student_summary["total_max_score"] == Decimal("20.00")
        # 14/20 * 100 = 70.00%
        assert student_summary["average_percentage"] == Decimal("70.00")

    async def test_update_ca_entry(self, admin_session):
        """Updating a CA entry changes the score."""
        env = await _seed_exam_environment(admin_session)
        service = CAService(admin_session)

        ca = await service.create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            student_id=env["student1_id"],
            assessment_type="test",
            title="Update Test",
            assessment_date=date(2025, 10, 1),
            max_score=Decimal("20.00"),
            score=Decimal("15.00"),
        )

        updated = await service.update_ca(ca.id, env["tenant_id"], score=Decimal("18.00"))
        assert updated is not None
        assert updated.score == Decimal("18.00")

    async def test_delete_ca_entry(self, admin_session):
        """Deleting a CA entry removes it."""
        env = await _seed_exam_environment(admin_session)
        service = CAService(admin_session)

        ca = await service.create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            student_id=env["student1_id"],
            assessment_type="assignment",
            title="Delete Me",
            assessment_date=date(2025, 10, 5),
        )

        result = await service.delete_ca(ca.id, env["tenant_id"])
        assert result is True

        fetched = await service.get_ca(env["tenant_id"], ca.id)
        assert fetched is None

    async def test_list_ca_filtered_by_student(self, admin_session):
        """List CA returns entries filtered by student."""
        env = await _seed_exam_environment(admin_session)
        service = CAService(admin_session)

        await service.create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            student_id=env["student1_id"],
            assessment_type="class_work",
            title="S1 CW",
            assessment_date=date(2025, 9, 10),
        )
        await service.create_ca(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
            subject_id=env["subject_id"],
            student_id=env["student2_id"],
            assessment_type="class_work",
            title="S2 CW",
            assessment_date=date(2025, 9, 10),
        )

        entries, total = await service.list_ca(
            tenant_id=env["tenant_id"],
            student_id=env["student1_id"],
        )

        assert total == 1
        assert entries[0].student_id == env["student1_id"]


# ============================================================
# Term Report Tests
# ============================================================

@pytest.mark.asyncio
class TestTermReports:
    """Tests for term report generation, ranking, and publishing."""

    async def test_generate_term_reports_creates_records(self, admin_session):
        """Generate term reports creates TermReport for each student in the class."""
        env = await _seed_exam_environment(admin_session)
        service = TermReportService(admin_session)

        reports = await service.generate_term_reports(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
        )

        assert len(reports) == 2  # 2 students in the class
        student_ids = {r.student_id for r in reports}
        assert env["student1_id"] in student_ids
        assert env["student2_id"] in student_ids

    async def test_calculate_rankings_assigns_positions(self, admin_session):
        """Calculate rankings assigns class_position and class_size."""
        env = await _seed_exam_environment(admin_session)
        report_svc = TermReportService(admin_session)

        # Generate reports (they will have None scores by default)
        reports = await report_svc.generate_term_reports(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
        )
        # Capture IDs before calculate_rankings, which calls expire_all()
        # to invalidate identity-mapped objects after raw SQL UPDATEs.
        report_id = reports[0].id

        await report_svc.calculate_rankings(
            tenant_id=env["tenant_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
        )

        # Re-fetch a report to check rankings
        report = await report_svc.get_term_report(env["tenant_id"], report_id)
        assert report is not None
        assert report.class_size == 2
        assert report.class_position is not None

    async def test_update_remarks(self, admin_session):
        """Update remarks saves teacher/headmaster comments."""
        env = await _seed_exam_environment(admin_session)
        service = TermReportService(admin_session)

        reports = await service.generate_term_reports(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
        )

        updated = await service.update_remarks(
            report_id=reports[0].id,
            tenant_id=env["tenant_id"],
            class_teacher_remark="Good effort this term.",
            headmaster_remark="Keep it up.",
            conduct_grade="Very Good",
        )

        assert updated.class_teacher_remark == "Good effort this term."
        assert updated.headmaster_remark == "Keep it up."
        assert updated.conduct_grade == "Very Good"

    async def test_publish_reports_sets_published_flag(self, admin_session):
        """Publishing reports sets is_published=True."""
        env = await _seed_exam_environment(admin_session)
        service = TermReportService(admin_session)

        await service.generate_term_reports(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
        )

        count = await service.publish_reports(
            tenant_id=env["tenant_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
        )

        assert count == 2  # Both student reports published

        # Verify published
        reports, total = await service.list_term_reports(
            tenant_id=env["tenant_id"],
            term_id=env["term_id"],
            is_published=True,
        )
        assert total == 2

    async def test_get_term_report_with_relationships(self, admin_session):
        """Get term report loads student, class, and term relationships."""
        env = await _seed_exam_environment(admin_session)
        service = TermReportService(admin_session)

        reports = await service.generate_term_reports(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            class_id=env["class_id"],
        )

        report = await service.get_term_report(env["tenant_id"], reports[0].id)
        assert report is not None
        assert report.student is not None
        assert report.class_ is not None
        assert report.term is not None


# ============================================================
# Analytics Tests
# ============================================================

@pytest.mark.asyncio
class TestExamAnalytics:
    """Tests for exam analytics and statistics."""

    async def _setup_scored_exam(self, admin_session):
        """Helper: create an exam with scores for analytics tests."""
        env = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env["tenant_id"],
            academic_year_id=env["ay_id"],
            term_id=env["term_id"],
            name="Analytics Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env["tenant_id"],
            exam_id=exam.id,
            subject_id=env["subject_id"],
            class_id=env["class_id"],
            grading_scale_id=env["grading_scale_id"],
        )

        await score_svc.bulk_enter_scores(
            tenant_id=env["tenant_id"],
            exam_subject_id=es.id,
            scores=[
                {"student_id": str(env["student1_id"]), "score": 85},
                {"student_id": str(env["student2_id"]), "score": 45},
            ],
        )

        env["exam_id"] = exam.id
        env["exam_subject_id"] = es.id
        return env

    async def test_grade_distribution(self, admin_session):
        """Grade distribution returns count per grade."""
        env = await self._setup_scored_exam(admin_session)
        service = AnalyticsService(admin_session)

        result = await service.get_grade_distribution(
            tenant_id=env["tenant_id"],
            exam_id=env["exam_id"],
            class_id=env["class_id"],
        )

        assert result is not None
        assert result["graded_students"] == 2
        assert len(result["grades"]) > 0
        # Student 1 has 85% -> A1, Student 2 has 45% -> D7
        grade_map = {g["grade"]: g["count"] for g in result["grades"]}
        assert grade_map.get("A1", 0) == 1
        assert grade_map.get("D7", 0) == 1

    async def test_class_statistics(self, admin_session):
        """Class statistics returns averages and pass rates."""
        env = await self._setup_scored_exam(admin_session)
        service = AnalyticsService(admin_session)

        stats = await service.get_class_statistics(
            tenant_id=env["tenant_id"],
            exam_id=env["exam_id"],
            class_id=env["class_id"],
        )

        assert stats is not None
        assert stats["total_students"] == 2
        assert stats["class_average"] is not None
        # (85 + 45) / 2 = 65
        assert stats["class_average"] == Decimal("65.00")
        assert stats["highest_score"] == Decimal("85.00")
        assert stats["lowest_score"] == Decimal("45.00")
        # 85 passes (>=50), 45 fails (<50) => pass_rate = 50%
        assert stats["pass_fail"]["passed"] == 1
        assert stats["pass_fail"]["failed"] == 1

    async def test_subject_statistics(self, admin_session):
        """Subject statistics returns per-subject analytics."""
        env = await self._setup_scored_exam(admin_session)
        service = AnalyticsService(admin_session)

        stats = await service.get_subject_statistics(
            tenant_id=env["tenant_id"],
            exam_id=env["exam_id"],
            class_id=env["class_id"],
        )

        assert len(stats) == 1  # One subject
        subj = stats[0]
        assert subj["students_with_scores"] == 2
        assert subj["average_score"] is not None

    async def test_subject_rankings(self, admin_session):
        """Subject rankings returns students ranked by score."""
        env = await self._setup_scored_exam(admin_session)
        service = AnalyticsService(admin_session)

        result = await service.get_subject_rankings(
            tenant_id=env["tenant_id"],
            exam_id=env["exam_id"],
            subject_id=env["subject_id"],
            class_id=env["class_id"],
        )

        assert result is not None
        assert result["total_students"] == 2
        rankings = result["rankings"]
        # First position should be the student with 85
        assert rankings[0]["position"] == 1
        assert rankings[0]["score"] == Decimal("85.00")
        assert rankings[1]["position"] == 2


# ============================================================
# Tenant Isolation Tests
# ============================================================

@pytest.mark.asyncio
class TestExamTenantIsolation:
    """Tenant A must NOT see Tenant B's exam data.

    Uses app_session (RLS enforced) to verify isolation.
    """

    async def test_tenant_a_cannot_see_tenant_b_exams(self, admin_session, app_session):
        """Exam created for Tenant A is invisible to Tenant B."""
        # Seed Tenant A with an exam
        env_a = await _seed_exam_environment(admin_session)
        exam_svc_admin = ExamService(admin_session)
        exam = await exam_svc_admin.create_exam(
            tenant_id=env_a["tenant_id"],
            academic_year_id=env_a["ay_id"],
            term_id=env_a["term_id"],
            name="Tenant A Exam",
            exam_type="end_term",
        )
        exam_id = exam.id
        await admin_session.commit()

        # Seed Tenant B
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # As Tenant B, try to see exams
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM exams WHERE id = CAST(:eid AS uuid)"),
            {"eid": str(exam_id)},
        )
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's exam"

    async def test_tenant_a_cannot_see_tenant_b_exam_scores(self, admin_session, app_session):
        """Exam scores created for Tenant A are invisible to Tenant B."""
        env_a = await _seed_exam_environment(admin_session)
        exam_svc = ExamService(admin_session)
        score_svc = ScoreService(admin_session)

        exam = await exam_svc.create_exam(
            tenant_id=env_a["tenant_id"],
            academic_year_id=env_a["ay_id"],
            term_id=env_a["term_id"],
            name="Iso Score Exam",
            exam_type="end_term",
        )
        es = await exam_svc.add_exam_subject(
            tenant_id=env_a["tenant_id"],
            exam_id=exam.id,
            subject_id=env_a["subject_id"],
            class_id=env_a["class_id"],
        )
        await score_svc.bulk_enter_scores(
            tenant_id=env_a["tenant_id"],
            exam_subject_id=es.id,
            scores=[{"student_id": str(env_a["student1_id"]), "score": 90}],
        )
        await admin_session.commit()

        # Tenant B
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM exam_scores"))
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's exam scores"

    async def test_tenant_a_cannot_see_tenant_b_ca(self, admin_session, app_session):
        """CA entries for Tenant A are invisible to Tenant B."""
        env_a = await _seed_exam_environment(admin_session)
        ca_svc = CAService(admin_session)

        await ca_svc.create_ca(
            tenant_id=env_a["tenant_id"],
            academic_year_id=env_a["ay_id"],
            term_id=env_a["term_id"],
            class_id=env_a["class_id"],
            subject_id=env_a["subject_id"],
            student_id=env_a["student1_id"],
            assessment_type="class_work",
            title="Isolation CA",
            assessment_date=date(2025, 10, 1),
        )
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM continuous_assessments"))
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's CA entries"

    async def test_tenant_a_cannot_see_tenant_b_term_reports(self, admin_session, app_session):
        """Term reports for Tenant A are invisible to Tenant B."""
        env_a = await _seed_exam_environment(admin_session)
        report_svc = TermReportService(admin_session)

        await report_svc.generate_term_reports(
            tenant_id=env_a["tenant_id"],
            academic_year_id=env_a["ay_id"],
            term_id=env_a["term_id"],
            class_id=env_a["class_id"],
        )
        await admin_session.commit()

        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM term_reports"))
        count = result.scalar()
        assert count == 0, "Tenant B should not see Tenant A's term reports"
