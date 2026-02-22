"""
SIMS Plus - Parent Portal Communication Endpoints

Endpoints for parents to view announcements targeted at them and
teacher notes about their children, with acknowledgement support.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    AnnouncementResponse,
    TeacherNoteResponse,
)
from app.services.parent import (
    ParentCommunicationService,
    ParentServiceError,
)

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/announcements",
    response_model=list[AnnouncementResponse],
    summary="Get announcements for parent",
    dependencies=[Depends(require_permissions("parent.communication.read"))],
)
async def get_parent_announcements(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[AnnouncementResponse]:
    """
    Get school announcements visible to this parent.

    Announcements are filtered by targeting rules based on the parent's
    children: all_parents announcements are always shown, class-specific
    and house-specific announcements are shown when the parent has a child
    in that class or boarding house.

    Only published, non-expired announcements are returned.
    Pinned announcements appear first.
    """
    user_id = _get_user_id(user)
    service = ParentCommunicationService(db)

    results = await service.get_announcements_for_parent(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
    )

    return [AnnouncementResponse(**item) for item in results]


@router.get(
    "/children/{student_id}/notes",
    response_model=list[TeacherNoteResponse],
    summary="Get teacher notes for child",
    dependencies=[Depends(require_permissions("parent.communication.read"))],
)
async def get_child_teacher_notes(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[TeacherNoteResponse]:
    """
    Get teacher notes for a child that are visible to parents.

    Only returns notes where is_visible_to_parent is True.
    Ordered by creation date, most recent first.
    """
    user_id = _get_user_id(user)
    service = ParentCommunicationService(db)

    try:
        results = await service.get_child_teacher_notes(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return [TeacherNoteResponse(**item) for item in results]


@router.post(
    "/children/{student_id}/notes/{note_id}/acknowledge",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Acknowledge teacher note",
    dependencies=[Depends(require_permissions("parent.communication.read"))],
)
async def acknowledge_teacher_note(
    student_id: UUID,
    note_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Mark a teacher note as acknowledged by the parent.

    Idempotent: acknowledging an already-acknowledged note is a no-op.
    Includes IDOR check to verify the note belongs to the specified student.
    """
    user_id = _get_user_id(user)
    service = ParentCommunicationService(db)

    try:
        await service.acknowledge_teacher_note(
            user_id=user_id,
            student_id=student_id,
            note_id=note_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)
