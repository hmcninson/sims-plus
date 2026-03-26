"""
SIMS Plus - Enrollment Checklist Endpoints

Admin endpoints for managing enrollment checklists, recording deposits,
assigning boarding status, generating confirmation PDFs, and sending
welcome packs.

The enrollment checklist is OPTIONAL (AD-3): applications without a
checklist can proceed to enrollment normally. When a checklist exists,
all required items must be completed before enrollment succeeds.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.enrollment_checklist import (
    BoardingStatusAssign,
    BoardingStatusResponse,
    ChecklistItemComplete,
    ChecklistItemResponse,
    ChecklistResponse,
    ConfirmationLetterResponse,
    EnrollmentDepositRecord,
    EnrollmentDepositResponse,
    WelcomePackResponse,
)
from app.services.admissions import EnrollmentError, EnrollmentService

logger = structlog.get_logger(__name__)

router = APIRouter()


def _handle_error(e: EnrollmentError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_STATUS": 422,
        "CHECKLIST_EXISTS": 409,
        "ALREADY_COMPLETED": 409,
        "DEPOSIT_ALREADY_PAID": 409,
        "ALREADY_SENT": 409,
        "INVALID_BOARDING_STATUS": 422,
        "NO_GUARDIAN": 422,
        "SCHOOL_NOT_FOUND": 404,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


def _build_checklist_response(checklist) -> dict:
    """Build a ChecklistResponse dict from a checklist ORM object with items loaded."""
    active_items = [i for i in checklist.items if i.deleted_at is None]
    total = len(active_items)
    completed = sum(1 for i in active_items if i.is_completed)
    required = sum(1 for i in active_items if i.is_required)
    required_completed = sum(
        1 for i in active_items if i.is_required and i.is_completed
    )
    progress_pct = round((completed / total * 100) if total > 0 else 0.0, 1)

    return {
        "id": checklist.id,
        "school_id": checklist.school_id,
        "application_id": checklist.application_id,
        "checklist_type": checklist.checklist_type,
        "completed_at": checklist.completed_at,
        "completed_by": checklist.completed_by,
        "total_items": total,
        "completed_items": completed,
        "required_items": required,
        "required_completed": required_completed,
        "progress_pct": progress_pct,
        "items": [
            {
                "id": i.id,
                "checklist_id": i.checklist_id,
                "item_type": i.item_type,
                "item_name": i.item_name,
                "description": i.description,
                "is_required": i.is_required,
                "is_completed": i.is_completed,
                "completed_at": i.completed_at,
                "completed_by": i.completed_by,
                "notes": i.notes,
                # REVIEW FIX E4: use item_metadata attribute
                "item_metadata": i.item_metadata,
                "created_at": i.created_at,
            }
            for i in active_items
        ],
        "created_at": checklist.created_at,
        "updated_at": checklist.updated_at,
    }


@router.post(
    "/applications/{application_id}/enrollment-checklist",
    response_model=ChecklistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create enrollment checklist",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def create_enrollment_checklist(
    application_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ChecklistResponse:
    """
    Create an enrollment checklist for an accepted application.

    Auto-populates items from the admission period's enrollment_checklist_template.
    If the application already has boarding_status='boarding', boarding-specific
    items are appended automatically.

    Requires: admissions.update permission
    """
    service = EnrollmentService(db)
    try:
        checklist = await service.create_enrollment_checklist(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            application_id=application_id,
        )
        # Reload with items for the response
        checklist = await service.get_checklist(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
        return _build_checklist_response(checklist)
    except EnrollmentError as e:
        raise _handle_error(e)


@router.get(
    "/applications/{application_id}/enrollment-checklist",
    response_model=ChecklistResponse,
    summary="Get enrollment checklist",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_enrollment_checklist(
    application_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ChecklistResponse:
    """
    Get the enrollment checklist for an application with all items
    and computed progress fields.

    Requires: admissions.read permission
    """
    service = EnrollmentService(db)
    try:
        checklist = await service.get_checklist(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
        return _build_checklist_response(checklist)
    except EnrollmentError as e:
        raise _handle_error(e)


@router.patch(
    "/checklist-items/{item_id}/complete",
    response_model=ChecklistItemResponse,
    summary="Complete a checklist item",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def complete_checklist_item(
    item_id: UUID,
    data: ChecklistItemComplete,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ChecklistItemResponse:
    """
    Mark a single checklist item as completed.

    If this was the last required incomplete item, the parent checklist
    is automatically marked as completed.

    Requires: admissions.update permission
    """
    service = EnrollmentService(db)
    try:
        item = await service.complete_checklist_item(
            tenant_id=UUID(user["tenant_id"]),
            item_id=item_id,
            user_id=UUID(user["user_id"]),
            notes=data.notes,
            item_metadata=data.item_metadata,
        )
        return ChecklistItemResponse(
            id=item.id,
            checklist_id=item.checklist_id,
            item_type=item.item_type,
            item_name=item.item_name,
            description=item.description,
            is_required=item.is_required,
            is_completed=item.is_completed,
            completed_at=item.completed_at,
            completed_by=item.completed_by,
            notes=item.notes,
            item_metadata=item.item_metadata,
            created_at=item.created_at,
        )
    except EnrollmentError as e:
        raise _handle_error(e)


@router.post(
    "/applications/{application_id}/enrollment-deposit",
    response_model=EnrollmentDepositResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record enrollment deposit",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def record_enrollment_deposit(
    application_id: UUID,
    data: EnrollmentDepositRecord,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EnrollmentDepositResponse:
    """
    Record a manual enrollment deposit payment.

    This is an admin-only operation for recording offline payments
    (cash, bank transfer, etc.). If a checklist exists with a deposit
    item, it is auto-completed.

    Requires: admissions.update permission
    """
    service = EnrollmentService(db)
    try:
        app = await service.record_enrollment_deposit(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            amount=data.amount,
            reference=data.reference,
        )
        return EnrollmentDepositResponse(
            application_id=app.id,
            enrollment_deposit_paid=app.enrollment_deposit_paid,
            enrollment_deposit_amount=app.enrollment_deposit_amount,
            enrollment_deposit_reference=app.enrollment_deposit_reference,
        )
    except EnrollmentError as e:
        raise _handle_error(e)


@router.patch(
    "/applications/{application_id}/boarding-status",
    response_model=BoardingStatusResponse,
    summary="Set boarding/day status",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def update_boarding_status(
    application_id: UUID,
    data: BoardingStatusAssign,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingStatusResponse:
    """
    Assign boarding or day status to an application.

    If setting to 'boarding' and a standard checklist exists, it is
    upgraded to a boarding checklist with additional items appended.

    Requires: admissions.update permission
    """
    service = EnrollmentService(db)
    try:
        app, items_added = await service.assign_boarding_status(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            boarding_status=data.boarding_status.value,
        )
        return BoardingStatusResponse(
            application_id=app.id,
            boarding_status=app.boarding_status,
            boarding_items_added=items_added,
        )
    except EnrollmentError as e:
        raise _handle_error(e)


@router.post(
    "/applications/{application_id}/enrollment-confirmation",
    response_model=ConfirmationLetterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate enrollment confirmation PDF",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def generate_enrollment_confirmation(
    application_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ConfirmationLetterResponse:
    """
    Generate an enrollment confirmation letter as a PDF and upload to S3.

    The PDF includes school branding, student details, class assignment,
    checklist summary, deposit status, and orientation information.
    Can be regenerated (overwrites previous version on S3).

    Requires: admissions.update permission
    """
    service = EnrollmentService(db)
    try:
        tenant_id = UUID(user["tenant_id"])
        url = await service.generate_enrollment_confirmation(
            tenant_id=tenant_id,
            application_id=application_id,
        )
        # Re-load application for applicant name
        app = await service._get_application(tenant_id, application_id)
        return ConfirmationLetterResponse(
            application_id=app.id,
            confirmation_url=url,
            applicant_name=f"{app.applicant_first_name} {app.applicant_last_name}",
        )
    except EnrollmentError as e:
        raise _handle_error(e)


@router.post(
    "/applications/{application_id}/welcome-pack",
    response_model=WelcomePackResponse,
    summary="Send welcome pack",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def send_welcome_pack(
    application_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> WelcomePackResponse:
    """
    Send a welcome pack email/SMS to the applicant's guardian(s).

    Includes enrollment confirmation (if generated), term dates,
    required materials, and orientation information.

    Can only be sent once per application.

    Requires: admissions.update permission
    """
    service = EnrollmentService(db)
    try:
        app, channels = await service.send_welcome_pack(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
        return WelcomePackResponse(
            application_id=app.id,
            welcome_pack_sent=app.welcome_pack_sent,
            channels=channels,
        )
    except EnrollmentError as e:
        raise _handle_error(e)
