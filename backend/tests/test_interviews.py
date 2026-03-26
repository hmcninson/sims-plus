"""
Tests for InterviewService and ScreeningChecklist operations.

Covers: scheduling, overlap detection, duplicate app check, CRUD, reschedule,
feedback recording, cancellation, screening items, and screening progress.
Uses two-engine pattern.
"""

import pytest
import secrets
from datetime import date, time
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_interview_prereqs(admin_session, tenant_id, *, app_status="submitted"):
    """Seed school, year, class, period, user, and an application. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid), :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Interviewer', 'Staff', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"interviewer-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Kofi', 'Mensah',
                '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
            "status": app_status,
        },
    )
    await admin_session.commit()
    return {
        "school_id": school_id, "year_id": year_id,
        "class_id": class_id, "period_id": period_id,
        "app_id": app_id, "user_id": user_id,
    }


async def _seed_second_application(admin_session, tenant_id, school_id, period_id, class_id):
    """Seed a second application. Returns app_id."""
    app_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Ama', 'Boateng',
                '2012-06-01', 'female', CAST(:cid AS uuid), 'submitted',
                '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
        },
    )
    await admin_session.commit()
    return app_id


# --- Interview Schedule Tests ---


async def test_schedule_interview(app_session, admin_session):
    """Schedule an interview with valid data."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    interview = await svc.schedule(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        application_id=prereqs["app_id"],
        interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15),
        scheduled_time=time(10, 0),
        duration_minutes=30,
        venue="Main Hall",
    )

    assert interview.id is not None
    assert interview.status == "scheduled"
    assert interview.scheduled_date == date(2026, 7, 15)
    assert interview.venue == "Main Hall"


async def test_schedule_interview_overlap(app_session, admin_session):
    """Same interviewer, overlapping time on same day raises INTERVIEWER_CONFLICT."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    app2_id = await _seed_second_application(
        admin_session, tenant["id"],
        prereqs["school_id"], prereqs["period_id"], prereqs["class_id"],
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService, InterviewServiceError

    svc = InterviewService(app_session)

    # First interview: 10:00 - 10:30
    await svc.schedule(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        application_id=prereqs["app_id"],
        interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15),
        scheduled_time=time(10, 0),
        duration_minutes=30,
        venue="Room A",
    )

    # Second interview: 10:15 - 10:45 (overlaps with first)
    with pytest.raises(InterviewServiceError) as exc_info:
        await svc.schedule(
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            application_id=app2_id,
            interviewer_id=prereqs["user_id"],
            scheduled_date=date(2026, 7, 15),
            scheduled_time=time(10, 15),
            duration_minutes=30,
            venue="Room B",
        )
    assert exc_info.value.code == "INTERVIEWER_CONFLICT"


async def test_schedule_interview_duplicate_app(app_session, admin_session):
    """Same application cannot have two active interviews."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService, InterviewServiceError

    svc = InterviewService(app_session)

    await svc.schedule(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        application_id=prereqs["app_id"],
        interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15),
        venue="Room A",
    )

    with pytest.raises(InterviewServiceError) as exc_info:
        await svc.schedule(
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            application_id=prereqs["app_id"],
            interviewer_id=prereqs["user_id"],
            scheduled_date=date(2026, 7, 16),
            venue="Room B",
        )
    assert exc_info.value.code == "INTERVIEW_EXISTS"


# --- Interview CRUD Tests ---


async def test_list_interviews(app_session, admin_session):
    """List returns all interviews for the tenant/school."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    app2_id = await _seed_second_application(
        admin_session, tenant["id"],
        prereqs["school_id"], prereqs["period_id"], prereqs["class_id"],
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)

    await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )
    await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=app2_id, interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 16), venue="Room B",
    )

    items, total = await svc.list_interviews(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
    )
    assert total == 2
    assert len(items) == 2


async def test_list_interviews_filter_status(app_session, admin_session):
    """Filter by status returns only matching interviews."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )

    items, total = await svc.list_interviews(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        status="scheduled",
    )
    assert total == 1
    assert items[0].status == "scheduled"

    items_none, total_none = await svc.list_interviews(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        status="completed",
    )
    assert total_none == 0


async def test_list_interviews_filter_date(app_session, admin_session):
    """Filter by date range returns only matching interviews."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    app2_id = await _seed_second_application(
        admin_session, tenant["id"],
        prereqs["school_id"], prereqs["period_id"], prereqs["class_id"],
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 10), venue="Room A",
    )
    await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=app2_id, interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 8, 10), venue="Room B",
    )

    items, total = await svc.list_interviews(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        date_from=date(2026, 7, 1), date_to=date(2026, 7, 31),
    )
    assert total == 1
    assert items[0].scheduled_date == date(2026, 7, 10)


async def test_get_interview(app_session, admin_session):
    """Get interview by ID returns full detail."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    interview = await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )
    interview_id = interview.id

    fetched = await svc.get(tenant_id=tenant["id"], interview_id=interview_id)
    assert fetched.id == interview_id
    assert fetched.venue == "Room A"


# --- Update/Reschedule Tests ---


async def test_update_interview(app_session, admin_session):
    """Update venue without changing date does not change status."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    interview = await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )

    updated = await svc.update(
        tenant_id=tenant["id"],
        interview_id=interview.id,
        venue="Room B",
    )
    assert updated.venue == "Room B"
    assert updated.status == "scheduled"  # No date change, so status stays


async def test_reschedule_changes_status(app_session, admin_session):
    """Changing date transitions status to 'rescheduled'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    interview = await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )

    updated = await svc.update(
        tenant_id=tenant["id"],
        interview_id=interview.id,
        scheduled_date=date(2026, 7, 20),
    )
    assert updated.status == "rescheduled"
    assert updated.scheduled_date == date(2026, 7, 20)


# --- Feedback Tests ---


async def test_record_feedback(app_session, admin_session):
    """Record feedback with scoring criteria."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    interview = await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )

    updated = await svc.record_feedback(
        tenant_id=tenant["id"],
        interview_id=interview.id,
        status="completed",
        feedback="Great candidate",
        scoring_criteria={
            "communication": {"score": 8, "max": 10},
            "aptitude": {"score": 7, "max": 10},
        },
    )
    assert updated.status == "completed"
    assert updated.feedback == "Great candidate"
    assert updated.score == Decimal("15")
    assert updated.max_score == Decimal("20")


async def test_record_feedback_invalid_scores(app_session, admin_session):
    """Scoring criteria with score > max raises validation error at schema level."""
    from app.schemas.interview import InterviewFeedback
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        InterviewFeedback(
            status="completed",
            scoring_criteria={
                "communication": {"score": 15, "max": 10},  # score > max
            },
        )


async def test_record_feedback_sets_completed(app_session, admin_session):
    """After feedback, interview status is 'completed'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    interview = await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )

    updated = await svc.record_feedback(
        tenant_id=tenant["id"],
        interview_id=interview.id,
        status="completed",
        score=Decimal("80"),
        max_score=Decimal("100"),
    )
    assert updated.status == "completed"
    assert updated.score == Decimal("80")


# --- Cancel Tests ---


async def test_cancel_interview(app_session, admin_session):
    """Cancel a scheduled interview sets status to 'cancelled'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    interview = await svc.schedule(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        application_id=prereqs["app_id"], interviewer_id=prereqs["user_id"],
        scheduled_date=date(2026, 7, 15), venue="Room A",
    )

    cancelled = await svc.cancel(
        tenant_id=tenant["id"], interview_id=interview.id,
    )
    assert cancelled.status == "cancelled"


# --- Screening Checklist Tests ---


async def test_create_screening_item(app_session, admin_session):
    """Add a screening checklist item to an application."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    item = await svc.create_screening_item(
        tenant_id=tenant["id"],
        application_id=prereqs["app_id"],
        item_name="Birth certificate verified",
        item_category="documents",
    )

    assert item.id is not None
    assert item.item_name == "Birth certificate verified"
    assert item.item_category == "documents"
    assert item.is_completed is False


async def test_bulk_create_screening(app_session, admin_session):
    """Bulk-add screening items creates all items, skips duplicates."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)

    # Create one item first
    await svc.create_screening_item(
        tenant_id=tenant["id"],
        application_id=prereqs["app_id"],
        item_name="Birth certificate",
        item_category="documents",
    )

    # Bulk create: one duplicate, two new
    items = await svc.bulk_create_screening_items(
        tenant_id=tenant["id"],
        application_id=prereqs["app_id"],
        items=[
            {"item_name": "Birth certificate", "item_category": "documents"},  # dup
            {"item_name": "Report card", "item_category": "academic"},
            {"item_name": "Medical report", "item_category": "medical"},
        ],
    )
    assert len(items) == 2  # Only the two new ones


async def test_complete_screening_item(app_session, admin_session):
    """Mark a screening item as completed."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)
    item = await svc.create_screening_item(
        tenant_id=tenant["id"],
        application_id=prereqs["app_id"],
        item_name="Birth certificate",
        item_category="documents",
    )

    completed = await svc.complete_screening_item(
        tenant_id=tenant["id"],
        item_id=item.id,
        user_id=prereqs["user_id"],
        notes="Original seen and verified",
    )

    assert completed.is_completed is True
    assert completed.completed_by == prereqs["user_id"]
    assert completed.completed_at is not None
    assert completed.notes == "Original seen and verified"


async def test_get_screening_progress(app_session, admin_session):
    """Screening progress shows correct percentage."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_interview_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InterviewService

    svc = InterviewService(app_session)

    # Create 4 items
    items_created = []
    for name in ["Birth cert", "Report card", "Medical", "Photo"]:
        item = await svc.create_screening_item(
            tenant_id=tenant["id"],
            application_id=prereqs["app_id"],
            item_name=name,
            item_category="documents",
        )
        items_created.append(item)

    # Complete 2 of 4
    await svc.complete_screening_item(
        tenant_id=tenant["id"], item_id=items_created[0].id,
        user_id=prereqs["user_id"],
    )
    await svc.complete_screening_item(
        tenant_id=tenant["id"], item_id=items_created[1].id,
        user_id=prereqs["user_id"],
    )

    progress = await svc.get_screening_progress(
        tenant_id=tenant["id"],
        application_id=prereqs["app_id"],
    )

    assert progress["total_items"] == 4
    assert progress["completed_items"] == 2
    assert progress["progress_pct"] == 50.0
