"""
SIMS Plus - Notification Tasks (Chain-Aware)

Background tasks for smart notification triggers:
  1. Attendance reminders -- nudge teachers who haven't marked attendance
     by a configurable cutoff time.
  2. Score deadline reminders -- alert teachers when an exam score entry
     deadline is approaching.

Chain-aware: both tasks accept an optional school_id parameter.
  - When school_id is provided, process only that school.
  - When omitted, iterate over ALL active schools in the tenant so
    chain tenants get full coverage.

Celery beat schedule (defined in app.celery_app):
  - send_attendance_reminders_task: daily at 11:00 UTC
  - send_score_deadline_reminders_task: daily at 08:00 UTC
"""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import ClassSection
from app.models.attendance import StudentAttendance
from app.models.exam import Exam, ExamSubject
from app.models.notification import NotificationCategory, NotificationType
from app.models.staff import Staff, StaffClassAssignment
from app.services.notification import NotificationService
from app.tasks.utils import get_tenant_schools

logger = structlog.get_logger()


async def _send_attendance_reminders_for_school(
    db: AsyncSession,
    tenant_id: UUID,
    school_id: UUID,
    target_date: date,
) -> dict:
    """
    Send attendance reminders for a single school.

    Finds class teachers in the school who have not submitted attendance
    records for the target date and creates in-app notifications.

    Args:
        db: Database session (with tenant context already set).
        tenant_id: The tenant being processed.
        school_id: The specific school to check.
        target_date: The date to check attendance for.

    Returns:
        dict with keys: school_id, checked, reminded, errors
    """
    checked = 0
    reminded = 0
    errors = 0

    try:
        # Find class teachers assigned to sections in this school who
        # have NOT submitted any attendance records for today.
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation.
        # Filter by school_id so chain tenants process one school at a time.
        assignments_result = await db.execute(
            select(
                StaffClassAssignment.staff_id,
                StaffClassAssignment.section_id,
                ClassSection.name.label("section_name"),
                Staff.user_id,
            )
            .join(ClassSection, StaffClassAssignment.section_id == ClassSection.id)
            .join(Staff, StaffClassAssignment.staff_id == Staff.id)
            .where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.school_id == school_id,
                    StaffClassAssignment.is_class_teacher == True,  # noqa: E712
                    Staff.deleted_at.is_(None),
                )
            )
        )
        assignments = assignments_result.all()
        checked = len(assignments)

        notification_service = NotificationService(db)

        for assignment in assignments:
            try:
                staff_id, section_id, section_name, user_id = assignment

                if not user_id:
                    continue

                # Check if any attendance records exist for this section today
                attendance_count = await db.execute(
                    select(func.count(StudentAttendance.id)).where(
                        and_(
                            StudentAttendance.tenant_id == tenant_id,
                            StudentAttendance.section_id == section_id,
                            StudentAttendance.date == target_date,
                        )
                    )
                )
                count = attendance_count.scalar() or 0

                if count == 0:
                    # No attendance marked -- send reminder
                    await notification_service.create(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        title="Attendance Reminder",
                        message=(
                            f"You have not marked attendance for {section_name} today. "
                            f"Please mark attendance before end of day."
                        ),
                        type=NotificationType.WARNING,
                        category=NotificationCategory.ATTENDANCE,
                    )
                    reminded += 1

            except Exception:
                logger.exception(
                    "attendance_reminder_error",
                    staff_id=str(staff_id),
                    section_id=str(section_id),
                    school_id=str(school_id),
                )
                errors += 1

    except Exception:
        logger.exception(
            "attendance_reminders_school_failed",
            tenant_id=str(tenant_id),
            school_id=str(school_id),
        )

    return {
        "school_id": str(school_id),
        "checked": checked,
        "reminded": reminded,
        "errors": errors,
    }


async def send_attendance_reminders(
    db: AsyncSession,
    tenant_id: UUID,
    reminder_date: Optional[date] = None,
    school_id: Optional[UUID] = None,
) -> dict:
    """
    Send attendance reminders to teachers who have not marked attendance
    for their assigned sections by the time this task runs.

    Chain-aware: when school_id is None, iterates over ALL active schools
    in the tenant. This means chain tenants with 10 schools get all 10
    processed, and single-school tenants process their one school.

    Intended to be scheduled as a daily task (e.g., 11:00 AM local time).

    Args:
        db: Database session (with tenant context already set).
        tenant_id: The tenant to process reminders for.
        reminder_date: The date to check. Defaults to today.
        school_id: Optional specific school. If None, all schools.

    Returns:
        dict with keys: schools_processed (int), total_checked (int),
            total_reminded (int), total_errors (int), per_school (list)
    """
    target_date = reminder_date or date.today()

    # Determine which schools to process
    if school_id:
        school_ids = [school_id]
    else:
        schools = await get_tenant_schools(db, tenant_id)
        school_ids = [s.id for s in schools]

    per_school_results: list[dict] = []
    total_checked = 0
    total_reminded = 0
    total_errors = 0

    for sid in school_ids:
        result = await _send_attendance_reminders_for_school(
            db, tenant_id, sid, target_date,
        )
        per_school_results.append(result)
        total_checked += result["checked"]
        total_reminded += result["reminded"]
        total_errors += result["errors"]

    await db.flush()

    logger.info(
        "attendance_reminders_complete",
        tenant_id=str(tenant_id),
        date=str(target_date),
        schools_processed=len(school_ids),
        total_checked=total_checked,
        total_reminded=total_reminded,
        total_errors=total_errors,
    )

    return {
        "schools_processed": len(school_ids),
        "total_checked": total_checked,
        "total_reminded": total_reminded,
        "total_errors": total_errors,
        "per_school": per_school_results,
    }


async def _send_score_deadline_reminders_for_school(
    db: AsyncSession,
    tenant_id: UUID,
    school_id: UUID,
    today: date,
    deadline_window: date,
) -> dict:
    """
    Send score deadline reminders for a single school.

    Finds exams in this school whose end_date falls within the deadline
    window, then notifies assigned teachers with pending score entries.

    Args:
        db: Database session (with tenant context already set).
        tenant_id: The tenant being processed.
        school_id: The specific school to check.
        today: Current date for days-remaining calculation.
        deadline_window: The deadline cutoff date (today + N days).

    Returns:
        dict with keys: school_id, exams_checked, reminded, errors
    """
    exams_checked = 0
    reminded = 0
    errors = 0

    try:
        # Find exams ending within the deadline window that are still open.
        # Filter by school_id so chain tenants process one school at a time.
        # Defense-in-depth: filter by tenant_id
        exams_result = await db.execute(
            select(Exam).where(
                and_(
                    Exam.tenant_id == tenant_id,
                    Exam.school_id == school_id,
                    Exam.end_date.isnot(None),
                    Exam.end_date >= today,
                    Exam.end_date <= deadline_window,
                    Exam.deleted_at.is_(None),
                )
            )
        )
        exams = list(exams_result.scalars().all())
        exams_checked = len(exams)

        notification_service = NotificationService(db)

        for exam in exams:
            try:
                # Find exam subjects with incomplete score entry.
                # ExamSubject uses TenantMixin without SoftDeleteMixin.
                subjects_result = await db.execute(
                    select(ExamSubject).where(
                        and_(
                            ExamSubject.tenant_id == tenant_id,
                            ExamSubject.exam_id == exam.id,
                        )
                    )
                )
                subjects = list(subjects_result.scalars().all())

                for exam_subject in subjects:
                    # The teacher assigned to this exam subject needs a reminder.
                    teacher_id = getattr(exam_subject, "teacher_id", None)
                    if not teacher_id:
                        continue

                    # Find the teacher's user_id
                    staff_result = await db.execute(
                        select(Staff.user_id).where(
                            and_(
                                Staff.id == teacher_id,
                                Staff.tenant_id == tenant_id,
                                Staff.deleted_at.is_(None),
                            )
                        )
                    )
                    user_id = staff_result.scalar_one_or_none()
                    if not user_id:
                        continue

                    days_left = (exam.end_date - today).days
                    subject_name = getattr(exam_subject, "subject_name", "a subject")

                    await notification_service.create(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        title="Score Entry Deadline Approaching",
                        message=(
                            f"Scores for \"{exam.name}\" ({subject_name}) are due in "
                            f"{days_left} day{'s' if days_left != 1 else ''}. "
                            f"Please complete score entry before the deadline."
                        ),
                        type=NotificationType.WARNING,
                        category=NotificationCategory.EXAM,
                        reference_id=exam_subject.id,
                        reference_type="exam_subject",
                    )
                    reminded += 1

            except Exception:
                logger.exception(
                    "score_deadline_reminder_error",
                    exam_id=str(exam.id),
                    school_id=str(school_id),
                )
                errors += 1

    except Exception:
        logger.exception(
            "score_deadline_reminders_school_failed",
            tenant_id=str(tenant_id),
            school_id=str(school_id),
        )

    return {
        "school_id": str(school_id),
        "exams_checked": exams_checked,
        "reminded": reminded,
        "errors": errors,
    }


async def send_score_deadline_reminders(
    db: AsyncSession,
    tenant_id: UUID,
    days_before_deadline: int = 3,
    school_id: Optional[UUID] = None,
) -> dict:
    """
    Send reminders to teachers when exam score entry deadlines approach.

    Chain-aware: when school_id is None, iterates over ALL active schools
    in the tenant. Finds exams whose end_date is within
    `days_before_deadline` days and notifies assigned teachers with
    pending score entries.

    Args:
        db: Database session (with tenant context already set).
        tenant_id: The tenant to process reminders for.
        days_before_deadline: How many days before the deadline to send
            the reminder. Defaults to 3.
        school_id: Optional specific school. If None, all schools.

    Returns:
        dict with keys: schools_processed (int), total_exams_checked (int),
            total_reminded (int), total_errors (int), per_school (list)
    """
    today = date.today()
    deadline_window = today + timedelta(days=days_before_deadline)

    # Determine which schools to process
    if school_id:
        school_ids = [school_id]
    else:
        schools = await get_tenant_schools(db, tenant_id)
        school_ids = [s.id for s in schools]

    per_school_results: list[dict] = []
    total_exams_checked = 0
    total_reminded = 0
    total_errors = 0

    for sid in school_ids:
        result = await _send_score_deadline_reminders_for_school(
            db, tenant_id, sid, today, deadline_window,
        )
        per_school_results.append(result)
        total_exams_checked += result["exams_checked"]
        total_reminded += result["reminded"]
        total_errors += result["errors"]

    await db.flush()

    logger.info(
        "score_deadline_reminders_complete",
        tenant_id=str(tenant_id),
        schools_processed=len(school_ids),
        total_exams_checked=total_exams_checked,
        total_reminded=total_reminded,
        total_errors=total_errors,
    )

    return {
        "schools_processed": len(school_ids),
        "total_exams_checked": total_exams_checked,
        "total_reminded": total_reminded,
        "total_errors": total_errors,
        "per_school": per_school_results,
    }


# ---------------------------------------------------------------------------
# Celery task wrappers
# ---------------------------------------------------------------------------
# Celery tasks are synchronous. These thin wrappers bridge to the async
# business logic above via run_async(). The beat schedule references these
# task names (e.g., "app.tasks.notifications.send_attendance_reminders_task").
# ---------------------------------------------------------------------------

from app.celery_app import celery_app  # noqa: E402
from app.tasks.utils import run_async, run_for_all_tenants  # noqa: E402


@celery_app.task(name="app.tasks.notifications.send_attendance_reminders_task")
def send_attendance_reminders_task() -> list[dict]:
    """
    Celery beat task: send attendance reminders for ALL active tenants.

    Iterates every active/trial tenant, sets RLS context per-tenant,
    and calls send_attendance_reminders for all schools in each tenant.
    """
    return run_async(run_for_all_tenants(send_attendance_reminders))


@celery_app.task(name="app.tasks.notifications.send_score_deadline_reminders_task")
def send_score_deadline_reminders_task() -> list[dict]:
    """
    Celery beat task: send score deadline reminders for ALL active tenants.

    Iterates every active/trial tenant, sets RLS context per-tenant,
    and calls send_score_deadline_reminders for all schools in each tenant.
    """
    return run_async(run_for_all_tenants(send_score_deadline_reminders))
