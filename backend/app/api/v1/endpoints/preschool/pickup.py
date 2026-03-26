"""
SIMS Plus - Preschool Pickup & Dietary Endpoints

API routes for authorized pickups, pickup logs, and allergy/dietary management.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    AuthorizedPickupCreate,
    AuthorizedPickupUpdate,
    AuthorizedPickupResponse,
    PickupLogCreate,
    PickupLogResponse,
    convert_uuid,
)
from app.schemas.preschool.incident import (
    DietaryRequirements,
    DietaryRequirementsUpdate,
    AllergyAlertResponse,
)

router = APIRouter()


# =========================
# Authorized Pickup Endpoints
# =========================


@router.post(
    "/students/{student_id}/authorized-pickups",
    response_model=AuthorizedPickupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add authorized pickup person",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def add_authorized_pickup(
    student_id: UUID,
    data: AuthorizedPickupCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Add an authorized pickup person for a student."""
    service = PreschoolService(db)
    try:
        pickup = await service.add_authorized_pickup(
            convert_uuid(tenant.tenant_id),
            student_id,
            data,
            added_by=convert_uuid(current_user["user_id"]),
        )
        return AuthorizedPickupResponse.model_validate(pickup)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == "STUDENT_NOT_FOUND"
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.get(
    "/students/{student_id}/authorized-pickups",
    response_model=list[AuthorizedPickupResponse],
    summary="List authorized pickup persons",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_authorized_pickups(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """List authorized pickup persons for a student."""
    service = PreschoolService(db)
    pickups = await service.list_authorized_pickups(
        convert_uuid(tenant.tenant_id), student_id
    )
    return [AuthorizedPickupResponse.model_validate(p) for p in pickups]


@router.put(
    "/authorized-pickups/{pickup_id}",
    response_model=AuthorizedPickupResponse,
    summary="Update authorized pickup person",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_authorized_pickup(
    pickup_id: UUID,
    data: AuthorizedPickupUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update an authorized pickup person."""
    service = PreschoolService(db)
    try:
        pickup = await service.update_authorized_pickup(
            convert_uuid(tenant.tenant_id), pickup_id, data
        )
        return AuthorizedPickupResponse.model_validate(pickup)
    except PreschoolServiceError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorized pickup not found",
        )


@router.delete(
    "/authorized-pickups/{pickup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete authorized pickup person",
    dependencies=[Depends(require_permissions("preschool.delete"))],
)
async def delete_authorized_pickup(
    pickup_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Soft-delete an authorized pickup person."""
    service = PreschoolService(db)
    try:
        await service.deactivate_authorized_pickup(
            convert_uuid(tenant.tenant_id), pickup_id
        )
    except PreschoolServiceError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorized pickup not found",
        )


# =========================
# Pickup Log Endpoints
# =========================


@router.post(
    "/pickup-logs",
    response_model=PickupLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a pickup event",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def record_pickup(
    data: PickupLogCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Record a student pickup event."""
    service = PreschoolService(db)
    try:
        log = await service.record_pickup(
            convert_uuid(tenant.tenant_id),
            data,
            verified_by=convert_uuid(current_user["user_id"]),
        )
        return PickupLogResponse.model_validate(log)
    except PreschoolServiceError as e:
        status_map = {
            "STUDENT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "GUARDIAN_NOT_LINKED": status.HTTP_403_FORBIDDEN,
            "GUARDIAN_PICKUP_NOT_AUTHORIZED": status.HTTP_403_FORBIDDEN,
            "AUTHORIZED_PICKUP_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        }
        raise HTTPException(
            status_code=status_map.get(e.code, status.HTTP_400_BAD_REQUEST),
            detail=e.message,
        )


@router.get(
    "/pickup-logs",
    response_model=list[PickupLogResponse],
    summary="List pickup logs",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_pickup_logs(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = None,
    class_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List pickup log entries with optional filters."""
    service = PreschoolService(db)
    logs = await service.list_pickup_logs(
        convert_uuid(tenant.tenant_id),
        student_id=student_id,
        class_id=class_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [PickupLogResponse.model_validate(log) for log in logs]


# =========================
# Allergy / Dietary Endpoints
# =========================


@router.get(
    "/students/{student_id}/dietary-requirements",
    response_model=DietaryRequirements | None,
    summary="Get dietary requirements",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_dietary_requirements(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get structured dietary requirements for a student."""
    service = PreschoolService(db)
    try:
        data = await service.get_student_dietary_requirements(
            convert_uuid(tenant.tenant_id), student_id
        )
        if data is None:
            return None
        return DietaryRequirements(**data)
    except PreschoolServiceError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )


@router.put(
    "/students/{student_id}/dietary-requirements",
    summary="Update dietary requirements",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_dietary_requirements(
    student_id: UUID,
    data: DietaryRequirementsUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update dietary requirements for a student."""
    service = PreschoolService(db)
    try:
        dietary_dict = (
            data.dietary_requirements.model_dump()
            if data.dietary_requirements
            else None
        )
        await service.update_dietary_requirements(
            convert_uuid(tenant.tenant_id), student_id, dietary_dict
        )
        return {"message": "Dietary requirements updated"}
    except PreschoolServiceError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )


@router.get(
    "/allergy-alerts",
    response_model=list[AllergyAlertResponse],
    summary="Get class allergy alerts",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_class_allergy_alerts(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    class_id: UUID = Query(..., description="Class ID to check alerts for"),
):
    """
    Get all students in a class who have allergies or dietary restrictions.

    Used to show allergy alert banners in daily log forms and class views.
    """
    service = PreschoolService(db)
    alerts = await service.get_class_allergy_alerts(
        convert_uuid(tenant.tenant_id), class_id
    )
    return alerts
