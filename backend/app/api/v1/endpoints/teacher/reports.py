"""
SIMS Plus - Teacher Portal Report Comment Endpoints

Class teacher and head teacher report card comment management.
Class teachers write per-student comments for their section.
Head teachers (school_admin) write headmaster remarks.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.models.academic import ClassSection
from app.schemas.teacher import (
    HeadTeacherCommentCreate,
    ReportCommentCreate,
    ReportCommentListResponse,
    ReportCommentResponse,
)
from app.services.teacher import (
    TeacherContextService,
    TeacherReportsService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/reports/comments",
    response_model=ReportCommentListResponse,
    summary="Get report comments",
    dependencies=[Depends(require_permissions("teacher.reports.read"))],
)
async def get_report_comments(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(None, description="Term ID (defaults to current)"),
    section_id: UUID | None = Query(None, description="Filter by section"),
) -> ReportCommentListResponse:
    """
    Get report comments for a term, optionally filtered by section.

    Class teachers see comments for students in their section.
    If section_id is provided, verifies the teacher is assigned to that section.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        if not term_id:
            academic_year = await context.get_current_academic_year(tenant.tenant_id)
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id

        # Verify teacher has access to the requested section before fetching comments
        if section_id:
            section_result = await db.execute(
                select(ClassSection.class_id)
                .where(
                    and_(
                        ClassSection.id == section_id,
                        ClassSection.tenant_id == tenant.tenant_id,
                        ClassSection.deleted_at.is_(None),
                    )
                )
            )
            class_id = section_result.scalar_one_or_none()
            if not class_id:
                raise TeacherServiceError("Section not found", code="not_found")

            await context.verify_class_access(
                staff_id=staff.id,
                tenant_id=tenant.tenant_id,
                class_id=class_id,
                section_id=section_id,
            )

        # Determine if the requester is a head teacher so we know whether
        # to expose draft (unsigned) head teacher comments
        user_permissions = user.get("permissions", [])
        is_head_teacher = (
            "teacher.reports.head_teacher" in user_permissions
            or "*" in user_permissions
        )

        reports_service = TeacherReportsService(db)
        comments = await reports_service.get_report_comments(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            term_id=term_id,
            section_id=section_id,
            is_head_teacher=is_head_teacher,
        )
        return ReportCommentListResponse(
            comments=[ReportCommentResponse(**c) for c in comments],
            total=len(comments),
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.post(
    "/reports/comments/students/{student_id}",
    response_model=ReportCommentResponse,
    summary="Write class teacher comment",
    dependencies=[Depends(require_permissions("teacher.reports.write"))],
)
async def write_class_teacher_comment(
    student_id: UUID,
    body: ReportCommentCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(None, description="Term ID (defaults to current)"),
) -> ReportCommentResponse:
    """
    Write or update a class teacher comment for a student's term report.

    The authenticated teacher must be the class teacher for the student's section.
    Creates a new report comment if one doesn't exist, or updates the existing one.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)
        academic_year = await context.get_current_academic_year(tenant.tenant_id)

        if not term_id:
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id

        reports_service = TeacherReportsService(db)
        result = await reports_service.upsert_class_teacher_comment(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            student_id=student_id,
            term_id=term_id,
            academic_year_id=academic_year.id,
            comment=body.class_teacher_comment,
        )
        return ReportCommentResponse(**result)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.post(
    "/reports/comments/students/{student_id}/sign",
    response_model=ReportCommentResponse,
    summary="Sign class teacher comment",
    dependencies=[Depends(require_permissions("teacher.reports.write"))],
)
async def sign_class_teacher_comment(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(None, description="Term ID (defaults to current)"),
) -> ReportCommentResponse:
    """
    Sign off a class teacher comment for a student.

    Sets class_teacher_signed=True. The comment must exist and the teacher
    must be the class teacher for the student's section.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        if not term_id:
            academic_year = await context.get_current_academic_year(tenant.tenant_id)
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id

        reports_service = TeacherReportsService(db)
        result = await reports_service.sign_class_teacher_comment(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            student_id=student_id,
            term_id=term_id,
        )
        return ReportCommentResponse(**result)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.post(
    "/reports/comments/students/{student_id}/head-teacher",
    response_model=ReportCommentResponse,
    summary="Write head teacher comment",
    dependencies=[Depends(require_permissions("teacher.reports.head_teacher"))],
)
async def write_head_teacher_comment(
    student_id: UUID,
    body: HeadTeacherCommentCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(None, description="Term ID (defaults to current)"),
) -> ReportCommentResponse:
    """
    Write or update a head teacher comment for a student's term report.

    Requires head teacher / school admin permissions.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)
        academic_year = await context.get_current_academic_year(tenant.tenant_id)

        if not term_id:
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id

        reports_service = TeacherReportsService(db)
        result = await reports_service.upsert_head_teacher_comment(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            student_id=student_id,
            term_id=term_id,
            academic_year_id=academic_year.id,
            comment=body.head_teacher_comment,
        )
        return ReportCommentResponse(**result)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.post(
    "/reports/comments/students/{student_id}/head-teacher/sign",
    response_model=ReportCommentResponse,
    summary="Sign head teacher comment",
    dependencies=[Depends(require_permissions("teacher.reports.head_teacher"))],
)
async def sign_head_teacher_comment(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(None, description="Term ID (defaults to current)"),
) -> ReportCommentResponse:
    """
    Sign off a head teacher comment for a student.

    Requires head teacher / school admin permissions.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        if not term_id:
            academic_year = await context.get_current_academic_year(tenant.tenant_id)
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id

        reports_service = TeacherReportsService(db)
        result = await reports_service.sign_head_teacher_comment(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            student_id=student_id,
            term_id=term_id,
        )
        return ReportCommentResponse(**result)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)
