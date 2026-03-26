"""
SIMS Plus - Staff Employment History Endpoints

View and create employment history events (promotions, transfers, etc.).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.staff import (
    StaffEmploymentHistoryCreate,
    StaffEmploymentHistoryResponse,
)
from app.services.staff import StaffHistoryService, StaffServiceError

router = APIRouter()


@router.get(
    "/{staff_id}/employment-history",
    response_model=list[StaffEmploymentHistoryResponse],
    summary="List employment history",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def list_employment_history(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[StaffEmploymentHistoryResponse]:
    """List all employment history events for a staff member, most recent first."""
    service = StaffHistoryService(db)
    try:
        events = await service.list_history(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
        )
    except StaffServiceError as e:
        code = status.HTTP_404_NOT_FOUND if e.code == "staff_not_found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=e.message)

    # Determine if the requesting user has payroll.read permission;
    # salary_changed events must redact previous_value/new_value without it.
    user_permissions = current_user.get("permissions", [])
    has_payroll_read = "payroll.read" in user_permissions or "payroll.*" in user_permissions

    result = []
    for event in events:
        event_type_str = event.event_type.value if hasattr(event.event_type, "value") else event.event_type

        # Redact salary values for users without payroll.read
        prev_val = event.previous_value
        new_val = event.new_value
        if event_type_str == "salary_changed" and not has_payroll_read:
            prev_val = "****" if prev_val else None
            new_val = "****" if new_val else None

        result.append(
            StaffEmploymentHistoryResponse(
                id=event.id,
                staff_id=event.staff_id,
                event_type=event_type_str,
                effective_date=event.effective_date,
                previous_value=prev_val,
                new_value=new_val,
                previous_department_id=event.previous_department_id,
                new_department_id=event.new_department_id,
                previous_job_title=event.previous_job_title,
                new_job_title=event.new_job_title,
                notes=event.notes,
                recorded_by=event.recorded_by,
                created_at=event.created_at,
            )
        )

    return result


@router.post(
    "/{staff_id}/employment-history",
    response_model=StaffEmploymentHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create employment history event",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def create_employment_history(
    staff_id: UUID,
    data: StaffEmploymentHistoryCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffEmploymentHistoryResponse:
    """Manually record an employment history event for a staff member."""
    service = StaffHistoryService(db)
    try:
        event = await service.record_event(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            event_type=data.event_type,
            effective_date=data.effective_date,
            recorded_by=UUID(current_user["user_id"]),
            school_id=UUID(current_user["school_id"]) if current_user.get("school_id") else None,
            previous_value=data.previous_value,
            new_value=data.new_value,
            previous_department_id=data.previous_department_id,
            new_department_id=data.new_department_id,
            previous_job_title=data.previous_job_title,
            new_job_title=data.new_job_title,
            notes=data.notes,
        )
    except StaffServiceError as e:
        code = (
            status.HTTP_404_NOT_FOUND
            if e.code == "staff_not_found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=e.message)

    return StaffEmploymentHistoryResponse(
        id=event.id,
        staff_id=event.staff_id,
        event_type=event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
        effective_date=event.effective_date,
        previous_value=event.previous_value,
        new_value=event.new_value,
        previous_department_id=event.previous_department_id,
        new_department_id=event.new_department_id,
        previous_job_title=event.previous_job_title,
        new_job_title=event.new_job_title,
        notes=event.notes,
        recorded_by=event.recorded_by,
        created_at=event.created_at,
    )
