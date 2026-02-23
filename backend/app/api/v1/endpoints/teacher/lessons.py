"""
SIMS Plus - Teacher Portal Lesson Plan Endpoints

CRUD operations for lesson plans. Teachers create, update, and track
lesson plans for their assigned classes and subjects.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import (
    LessonPlanCreate,
    LessonPlanListResponse,
    LessonPlanResponse,
    LessonPlanUpdate,
)
from app.services.teacher import (
    TeacherContextService,
    TeacherLessonService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/lessons",
    response_model=LessonPlanListResponse,
    summary="List my lesson plans",
    dependencies=[Depends(require_permissions("teacher.lessons.read"))],
)
async def list_lesson_plans(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    class_id: UUID | None = Query(None, description="Filter by class"),
    subject_id: UUID | None = Query(None, description="Filter by subject"),
    date_from: date | None = Query(None, description="Start date filter"),
    date_to: date | None = Query(None, description="End date filter"),
    plan_status: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> LessonPlanListResponse:
    """
    List the authenticated teacher's lesson plans with optional filters.

    Supports filtering by class, subject, date range, and status.
    Results are paginated and sorted by date (newest first).
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        from app.models.teacher import LessonPlanStatus
        status_enum = None
        if plan_status:
            try:
                status_enum = LessonPlanStatus(plan_status)
            except ValueError:
                pass

        lesson_service = TeacherLessonService(db)
        plans, total = await lesson_service.list_lesson_plans(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            subject_id=subject_id,
            date_from=date_from,
            date_to=date_to,
            status=status_enum,
            limit=limit,
            offset=offset,
        )
        return LessonPlanListResponse(
            plans=[LessonPlanResponse(**p) for p in plans],
            total=total,
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.get(
    "/lessons/{plan_id}",
    response_model=LessonPlanResponse,
    summary="Get a lesson plan",
    dependencies=[Depends(require_permissions("teacher.lessons.read"))],
)
async def get_lesson_plan(
    plan_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> LessonPlanResponse:
    """
    Get a single lesson plan by ID.

    Only returns plans owned by the authenticated teacher.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        lesson_service = TeacherLessonService(db)
        plan = await lesson_service.get_lesson_plan(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            plan_id=plan_id,
        )
        return LessonPlanResponse(**plan)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.post(
    "/lessons",
    response_model=LessonPlanResponse,
    summary="Create a lesson plan",
    dependencies=[Depends(require_permissions("teacher.lessons.write"))],
    status_code=201,
)
async def create_lesson_plan(
    body: LessonPlanCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> LessonPlanResponse:
    """
    Create a new lesson plan.

    The teacher must be assigned to the class+subject combination.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Verify access to class and subject
        await context.verify_class_access(
            staff_id=staff.id, tenant_id=tenant.tenant_id, class_id=body.class_id,
        )
        await context.verify_subject_access(
            staff_id=staff.id, tenant_id=tenant.tenant_id,
            subject_id=body.subject_id, class_id=body.class_id,
        )

        lesson_service = TeacherLessonService(db)
        plan = await lesson_service.create_lesson_plan(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            data=body.model_dump(),
        )
        return LessonPlanResponse(**plan)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.patch(
    "/lessons/{plan_id}",
    response_model=LessonPlanResponse,
    summary="Update a lesson plan",
    dependencies=[Depends(require_permissions("teacher.lessons.write"))],
)
async def update_lesson_plan(
    plan_id: UUID,
    body: LessonPlanUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> LessonPlanResponse:
    """
    Update an existing lesson plan.

    Only the owning teacher can update their plans.
    Supports partial updates (only provided fields are changed).
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Build update data, excluding None values for partial update
        update_data = body.model_dump(exclude_none=True)
        if "status" in update_data and update_data["status"]:
            update_data["status"] = update_data["status"].value

        lesson_service = TeacherLessonService(db)
        plan = await lesson_service.update_lesson_plan(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            plan_id=plan_id,
            data=update_data,
        )
        return LessonPlanResponse(**plan)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.delete(
    "/lessons/{plan_id}",
    status_code=204,
    summary="Delete a lesson plan",
    dependencies=[Depends(require_permissions("teacher.lessons.write"))],
)
async def delete_lesson_plan(
    plan_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> Response:
    """
    Soft-delete a lesson plan.

    Only the owning teacher can delete their plans.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        lesson_service = TeacherLessonService(db)
        await lesson_service.delete_lesson_plan(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            plan_id=plan_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)
