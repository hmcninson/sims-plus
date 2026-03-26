"""
SIMS Plus - Preschool Observation Endpoints

API routes for progress observations and daily activity logs.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    ProgressObservationCreate,
    ProgressObservationUpdate,
    ProgressObservationResponse,
    DailyActivityLogCreate,
    DailyActivityLogUpdate,
    DailyActivityLogResponse,
    convert_uuid,
)


class BulkSendDailyLogsRequest(BaseModel):
    """Request body for bulk-sending daily logs to parents."""
    class_id: UUID
    log_date: date

router = APIRouter()


# =========================
# Progress Observations
# =========================


@router.get(
    "/observations",
    response_model=list[ProgressObservationResponse],
    summary="List observations",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_observations(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    observation_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(50, le=100),
):
    """List observations with filters."""
    service = PreschoolService(db)
    return await service.list_observations(
        convert_uuid(tenant.tenant_id), student_id, observation_type, start_date, end_date, limit
    )


@router.post(
    "/observations",
    response_model=ProgressObservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create observation",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_observation(
    data: ProgressObservationCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a progress observation."""
    service = PreschoolService(db)
    try:
        return await service.create_observation(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/observations/{observation_id}",
    response_model=ProgressObservationResponse,
    summary="Get observation",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_observation(
    observation_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get an observation by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_observation(convert_uuid(tenant.tenant_id), observation_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/observations/{observation_id}",
    response_model=ProgressObservationResponse,
    summary="Update observation",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_observation(
    observation_id: UUID,
    data: ProgressObservationUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update an observation."""
    service = PreschoolService(db)
    try:
        observation = await service.get_observation(convert_uuid(tenant.tenant_id), observation_id)
        return await service.update_observation(observation, data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete(
    "/observations/{observation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete observation",
    dependencies=[Depends(require_permissions("preschool.delete"))],
)
async def delete_observation(
    observation_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Delete an observation (soft delete)."""
    service = PreschoolService(db)
    try:
        observation = await service.get_observation(convert_uuid(tenant.tenant_id), observation_id)
        await service.delete_observation(observation)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/observations/student/{student_id}",
    response_model=list[ProgressObservationResponse],
    summary="Get student observations",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_student_observations(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    limit: int = Query(50, le=100),
):
    """Get all observations for a student."""
    service = PreschoolService(db)
    return await service.list_observations(
        convert_uuid(tenant.tenant_id), student_id, limit=limit
    )


# =========================
# Daily Activity Logs
# =========================


@router.get(
    "/daily-logs",
    response_model=list[DailyActivityLogResponse],
    summary="List daily logs",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_daily_logs(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    log_date: date | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    class_id: UUID | None = Query(None),
    limit: int = Query(50, le=100),
):
    """List daily logs with filters."""
    service = PreschoolService(db)
    return await service.list_daily_logs(
        convert_uuid(tenant.tenant_id), student_id, log_date, start_date, end_date, class_id, limit
    )


@router.post(
    "/daily-logs",
    response_model=DailyActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update daily log",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_or_update_daily_log(
    data: DailyActivityLogCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create or update a daily activity log."""
    service = PreschoolService(db)
    try:
        return await service.create_or_update_daily_log(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/daily-logs/{log_id}",
    response_model=DailyActivityLogResponse,
    summary="Get daily log",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_daily_log(
    log_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a daily log by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_daily_log(convert_uuid(tenant.tenant_id), log_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/daily-logs/student/{student_id}",
    response_model=list[DailyActivityLogResponse],
    summary="Get student daily logs",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_student_daily_logs(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    limit: int = Query(30, le=100),
):
    """Get daily logs for a student."""
    service = PreschoolService(db)
    return await service.list_daily_logs(
        convert_uuid(tenant.tenant_id), student_id, limit=limit
    )


# =========================
# Daily Report Sending
# =========================


@router.post(
    "/daily-logs/{log_id}/send-to-parents",
    summary="Send daily log to parents",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def send_daily_log_to_parents(
    log_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Send a daily log summary to the student's guardians via all notification channels."""
    service = PreschoolService(db)
    try:
        return await service.send_daily_log_to_parents(
            convert_uuid(tenant.tenant_id),
            log_id,
            convert_uuid(current_user["user_id"]),
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/daily-logs/bulk-send",
    summary="Bulk send daily logs to parents",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def bulk_send_daily_logs(
    data: BulkSendDailyLogsRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Send daily logs for all students in a class for a given date.

    Maximum 50 students per call. For larger classes, use background tasks.
    """
    service = PreschoolService(db)
    try:
        return await service.bulk_send_daily_logs(
            convert_uuid(tenant.tenant_id),
            data.class_id,
            data.log_date,
            convert_uuid(current_user["user_id"]),
        )
    except PreschoolServiceError as e:
        if e.code == "bulk_limit_exceeded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.message
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
