"""
SIMS Plus - Leave Management Endpoints

Full leave management: types, balances, requests, calendar.
All endpoints gated by hr_leave feature flag and hr.leave.* permissions.

IMPORTANT: Do NOT use `from __future__ import annotations` here.
It breaks 204 No Content responses with AssertionError.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_feature,
    require_permissions,
)
from app.schemas.leave import (
    LeaveApprovalRequest,
    LeaveBalanceAdjust,
    LeaveBalanceInitialize,
    LeaveBalanceResponse,
    LeaveCalendarEntry,
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveRequestUpdate,
    LeaveTypeCreate,
    LeaveTypeResponse,
    LeaveTypeUpdate,
)
from app.services.leave import (
    LeaveBalanceService,
    LeaveRequestService,
    LeaveTypeService,
)


router = APIRouter(prefix="/leave", tags=["Leave Management"])


# =========================
# Leave Types
# =========================


@router.post(
    "/types",
    response_model=LeaveTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create leave type",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.manage")),
    ],
)
async def create_leave_type(
    data: LeaveTypeCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveTypeResponse:
    """Create a new leave type (e.g., Annual, Sick, Maternity)."""
    service = LeaveTypeService(db)
    try:
        leave_type = await service.create(
            tenant_id=tenant.tenant_id,
            data=data.model_dump(),
        )
        return LeaveTypeResponse.model_validate(leave_type)
    except LeaveTypeService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/types",
    response_model=list[LeaveTypeResponse],
    summary="List leave types",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.read")),
    ],
)
async def list_leave_types(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    active_only: bool = Query(True, description="Only return active leave types"),
) -> list[LeaveTypeResponse]:
    """List all leave types for the current tenant."""
    service = LeaveTypeService(db)
    leave_types = await service.list(
        tenant_id=tenant.tenant_id,
        active_only=active_only,
    )
    return [LeaveTypeResponse.model_validate(lt) for lt in leave_types]


@router.put(
    "/types/{type_id}",
    response_model=LeaveTypeResponse,
    summary="Update leave type",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.manage")),
    ],
)
async def update_leave_type(
    type_id: UUID,
    data: LeaveTypeUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveTypeResponse:
    """Update an existing leave type."""
    service = LeaveTypeService(db)
    try:
        leave_type = await service.update(
            tenant_id=tenant.tenant_id,
            type_id=type_id,
            data=data.model_dump(exclude_unset=True),
        )
        return LeaveTypeResponse.model_validate(leave_type)
    except LeaveTypeService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/types/{type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete leave type",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.manage")),
    ],
)
async def delete_leave_type(
    type_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Soft delete a leave type. Cannot delete if balances exist."""
    service = LeaveTypeService(db)
    try:
        await service.delete(tenant_id=tenant.tenant_id, type_id=type_id)
    except LeaveTypeService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# =========================
# Leave Balances
# =========================


@router.get(
    "/balances",
    response_model=list[LeaveBalanceResponse],
    summary="List all leave balances",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.read")),
    ],
)
async def list_leave_balances(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    academic_year_id: Optional[UUID] = Query(None, description="Filter by academic year"),
    leave_type_id: Optional[UUID] = Query(None, description="Filter by leave type"),
) -> list[LeaveBalanceResponse]:
    """List all staff leave balances, optionally filtered by year and type."""
    if not academic_year_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="academic_year_id is required",
        )
    service = LeaveBalanceService(db)
    try:
        balances = await service.get_all_balances(
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year_id,
            leave_type_id=leave_type_id,
        )
        return [LeaveBalanceResponse(**b) for b in balances]
    except LeaveBalanceService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/balances/{staff_id}",
    response_model=list[LeaveBalanceResponse],
    summary="Get staff leave balances",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.read")),
    ],
)
async def get_staff_balances(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    academic_year_id: Optional[UUID] = Query(None, description="Filter by academic year"),
) -> list[LeaveBalanceResponse]:
    """Get all leave balances for a specific staff member."""
    service = LeaveBalanceService(db)
    try:
        balances = await service.get_staff_balances(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            academic_year_id=academic_year_id,
        )
        return [LeaveBalanceResponse(**b) for b in balances]
    except LeaveBalanceService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/balances/{balance_id}",
    response_model=LeaveBalanceResponse,
    summary="Adjust leave balance",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.manage")),
    ],
)
async def adjust_leave_balance(
    balance_id: UUID,
    data: LeaveBalanceAdjust,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveBalanceResponse:
    """Admin override of entitled_days or carried_over with audit reason."""
    service = LeaveBalanceService(db)
    try:
        balance = await service.adjust(
            tenant_id=tenant.tenant_id,
            balance_id=balance_id,
            data=data.model_dump(),
        )
        return LeaveBalanceResponse(**balance)
    except LeaveBalanceService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/balances/initialize",
    status_code=status.HTTP_201_CREATED,
    summary="Initialize leave balances",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.manage")),
    ],
)
async def initialize_balances(
    data: LeaveBalanceInitialize,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> dict:
    """Bulk initialize leave balances for all active staff for an academic year."""
    service = LeaveBalanceService(db)
    try:
        result = await service.initialize_for_year(
            tenant_id=tenant.tenant_id,
            academic_year_id=data.academic_year_id,
            carry_over=data.carry_over_from_previous,
        )
        return result
    except LeaveBalanceService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# =========================
# Leave Requests
# =========================


@router.post(
    "/requests",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit leave request",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.request")),
    ],
)
async def submit_leave_request(
    data: LeaveRequestCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveRequestResponse:
    """Submit a leave request. Staff submits for themselves.

    The days_requested field is calculated server-side by counting working
    days (excluding weekends and school holidays) in the date range.
    """
    # Resolve staff_id from the current user's linked staff profile
    staff_id = await _resolve_staff_id(db, tenant.tenant_id, current_user)

    service = LeaveRequestService(db)
    try:
        request = await service.submit(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            data=data.model_dump(),
            school_id=UUID(current_user["school_id"]) if current_user.get("school_id") else None,
        )
        # Re-fetch with relations for response
        result = await service.get_request(tenant.tenant_id, request.id)
        return LeaveRequestResponse(**result)
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/requests",
    response_model=list[LeaveRequestResponse],
    summary="List leave requests",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.read")),
    ],
)
async def list_leave_requests(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    staff_id: Optional[UUID] = Query(None, description="Filter by staff member"),
    leave_type_id: Optional[UUID] = Query(None, description="Filter by leave type"),
    start_date: Optional[date] = Query(None, description="Filter by date range start"),
    end_date: Optional[date] = Query(None, description="Filter by date range end"),
) -> list[LeaveRequestResponse]:
    """List leave requests with optional filters."""
    service = LeaveRequestService(db)
    try:
        requests = await service.list_requests(
            tenant_id=tenant.tenant_id,
            status=request_status,
            staff_id=staff_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
        )
        return [LeaveRequestResponse(**r) for r in requests]
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/requests/{request_id}",
    response_model=LeaveRequestResponse,
    summary="Get leave request",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.read")),
    ],
)
async def get_leave_request(
    request_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveRequestResponse:
    """Get a specific leave request by ID."""
    service = LeaveRequestService(db)
    try:
        result = await service.get_request(
            tenant_id=tenant.tenant_id,
            request_id=request_id,
        )
        return LeaveRequestResponse(**result)
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/requests/{request_id}",
    response_model=LeaveRequestResponse,
    summary="Update leave request",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.request")),
    ],
)
async def update_leave_request(
    request_id: UUID,
    data: LeaveRequestUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveRequestResponse:
    """Update a pending leave request (before approval). Staff can only update own."""
    staff_id = await _resolve_staff_id(db, tenant.tenant_id, current_user)

    service = LeaveRequestService(db)
    try:
        request = await service.update_request(
            tenant_id=tenant.tenant_id,
            request_id=request_id,
            staff_id=staff_id,
            data=data.model_dump(exclude_unset=True),
        )
        result = await service.get_request(tenant.tenant_id, request.id)
        return LeaveRequestResponse(**result)
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/requests/{request_id}/approve",
    response_model=LeaveRequestResponse,
    summary="Approve leave request",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.approve")),
    ],
)
async def approve_leave_request(
    request_id: UUID,
    data: LeaveApprovalRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveRequestResponse:
    """Approve a pending leave request."""
    reviewer_id = UUID(current_user["user_id"])
    service = LeaveRequestService(db)
    try:
        request = await service.approve(
            tenant_id=tenant.tenant_id,
            request_id=request_id,
            reviewer_id=reviewer_id,
            notes=data.notes,
        )
        result = await service.get_request(tenant.tenant_id, request.id)
        return LeaveRequestResponse(**result)
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/requests/{request_id}/reject",
    response_model=LeaveRequestResponse,
    summary="Reject leave request",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.approve")),
    ],
)
async def reject_leave_request(
    request_id: UUID,
    data: LeaveApprovalRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveRequestResponse:
    """Reject a pending leave request."""
    reviewer_id = UUID(current_user["user_id"])
    service = LeaveRequestService(db)
    try:
        request = await service.reject(
            tenant_id=tenant.tenant_id,
            request_id=request_id,
            reviewer_id=reviewer_id,
            notes=data.notes,
        )
        result = await service.get_request(tenant.tenant_id, request.id)
        return LeaveRequestResponse(**result)
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/requests/{request_id}/cancel",
    response_model=LeaveRequestResponse,
    summary="Cancel leave request",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.request")),
    ],
)
async def cancel_leave_request(
    request_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LeaveRequestResponse:
    """Cancel own leave request (if pending or approved-but-not-started)."""
    staff_id = await _resolve_staff_id(db, tenant.tenant_id, current_user)

    service = LeaveRequestService(db)
    try:
        request = await service.cancel(
            tenant_id=tenant.tenant_id,
            request_id=request_id,
            staff_id=staff_id,
        )
        result = await service.get_request(tenant.tenant_id, request.id)
        return LeaveRequestResponse(**result)
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# =========================
# Calendar
# =========================


@router.get(
    "/calendar",
    response_model=list[LeaveCalendarEntry],
    summary="Get leave calendar",
    dependencies=[
        Depends(require_feature("hr_leave")),
        Depends(require_permissions("hr.leave.read")),
    ],
)
async def get_leave_calendar(
    start_date: date,
    end_date: date,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[LeaveCalendarEntry]:
    """Get leave calendar entries for a date range (approved + pending)."""
    service = LeaveRequestService(db)
    try:
        entries = await service.get_calendar(
            tenant_id=tenant.tenant_id,
            start_date=start_date,
            end_date=end_date,
        )
        return [LeaveCalendarEntry(**e) for e in entries]
    except LeaveRequestService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# =========================
# Helper Functions
# =========================


async def _resolve_staff_id(
    db,
    tenant_id: UUID,
    current_user: dict,
) -> UUID:
    """
    Resolve the staff_id for the current user.
    Looks up the staff record linked to this user via user_id FK.
    """
    from sqlalchemy import select as sa_select
    from app.models.staff import Staff

    user_id = UUID(current_user["user_id"])

    result = await db.execute(
        sa_select(Staff.id).where(
            Staff.user_id == user_id,
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            Staff.tenant_id == tenant_id,
            Staff.deleted_at.is_(None),
        )
    )
    staff_id = result.scalar_one_or_none()
    if not staff_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No staff profile linked to your user account. "
            "Contact your administrator.",
        )
    return staff_id
