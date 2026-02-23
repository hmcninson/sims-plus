"""
SIMS Plus - Teacher Portal Communication Endpoints

Class broadcast messaging. Teachers can send announcements targeted
at parents of students in their assigned classes.
"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import ClassBroadcastRequest, ClassBroadcastResponse
from app.services.teacher import (
    TeacherCommunicationService,
    TeacherContextService,
    TeacherServiceError,
)

from ._helpers import _get_school_id, _get_user_id, _handle_teacher_error

router = APIRouter()


@router.post(
    "/communication/broadcast",
    response_model=ClassBroadcastResponse,
    summary="Send class broadcast",
    dependencies=[Depends(require_permissions("teacher.communication.write"))],
    status_code=201,
)
async def send_class_broadcast(
    body: ClassBroadcastRequest,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassBroadcastResponse:
    """
    Send a broadcast announcement to all parents in a class.

    Creates an Announcement with target_audience=specific_class and
    publishes it immediately. The teacher must be assigned to the class.
    """
    user_id = _get_user_id(user)
    school_id = _get_school_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Verify teacher has access to the target class
        await context.verify_class_access(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=body.class_id,
        )

        comm_service = TeacherCommunicationService(db)
        result = await comm_service.send_class_broadcast(
            user_id=user_id,
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            class_id=body.class_id,
            title=body.title,
            content=body.content,
            priority=body.priority,
        )
        return ClassBroadcastResponse(**result)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)
