"""
SIMS Plus - Teacher Portal Class Endpoints

View assigned classes, class overviews, and student lists.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import (
    ClassOverview,
    ClassStudentItem,
    ClassStudentListResponse,
    TeacherClassSummary,
)
from app.services.teacher import (
    TeacherClassroomService,
    TeacherContextService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/classes",
    response_model=list[TeacherClassSummary],
    summary="Get my assigned classes",
    dependencies=[Depends(require_permissions("teacher.classes.read"))],
)
async def get_my_classes(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[TeacherClassSummary]:
    """
    Get all classes/sections the authenticated teacher is assigned to.

    Includes student counts and class teacher status.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        classroom_service = TeacherClassroomService(db)
        classes = await classroom_service.get_my_classes(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
        )
        return [TeacherClassSummary(**c) for c in classes]

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.get(
    "/classes/{class_id}",
    response_model=ClassOverview,
    summary="Get class overview",
    dependencies=[Depends(require_permissions("teacher.classes.read"))],
)
async def get_class_overview(
    class_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    section_id: UUID | None = Query(None, description="Optional section filter"),
) -> ClassOverview:
    """
    Get detailed overview of a specific class the teacher teaches.

    Includes student count, subjects taught, and class teacher status.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Verify teacher has access to this class
        await context.verify_class_access(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            section_id=section_id,
        )

        classroom_service = TeacherClassroomService(db)
        overview = await classroom_service.get_class_overview(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            section_id=section_id,
        )
        return ClassOverview(**overview)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.get(
    "/classes/{class_id}/students",
    response_model=ClassStudentListResponse,
    summary="Get students in a class",
    dependencies=[Depends(require_permissions("teacher.classes.read"))],
)
async def get_class_students(
    class_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    section_id: UUID | None = Query(None, description="Optional section filter"),
) -> ClassStudentListResponse:
    """
    Get the list of students in a class the teacher is assigned to.

    Only returns active students sorted alphabetically by last name.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Verify teacher has access to this class
        await context.verify_class_access(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            section_id=section_id,
        )

        classroom_service = TeacherClassroomService(db)
        students = await classroom_service.get_class_students(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            section_id=section_id,
        )

        student_items = [
            ClassStudentItem(
                id=s.id,
                student_id=s.student_id,
                first_name=s.first_name,
                last_name=s.last_name,
                middle_name=s.middle_name,
                gender=s.gender.value if s.gender else "",
                photo_url=s.photo_url,
                status=s.status.value if s.status else "",
            )
            for s in students
        ]
        return ClassStudentListResponse(
            students=student_items,
            total=len(student_items),
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)
