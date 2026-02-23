"""
SIMS Plus - Communication Settings Endpoints

CRUD for per-school communication preferences stored in the
schools.communication_settings JSONB column.

Permissions:
  - GET:  school.read  (any authenticated user who can view school info)
  - PUT:  school.update (school admins, platform admins)
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.communication import (
    CommunicationSettingsResponse,
    CommunicationSettingsUpdate,
)
from app.services.communication_settings import CommunicationSettingsService

router = APIRouter()


@router.get(
    "",
    response_model=CommunicationSettingsResponse,
    summary="Get communication settings",
    dependencies=[Depends(require_permissions("school.read"))],
)
async def get_communication_settings(
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> CommunicationSettingsResponse:
    """Return the active communication settings for the current school."""
    service = CommunicationSettingsService(db)
    try:
        settings = await service.get_settings(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
        )
        return CommunicationSettingsResponse.model_validate(settings.model_dump())
    except CommunicationSettingsService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "",
    response_model=CommunicationSettingsResponse,
    summary="Update communication settings",
    dependencies=[Depends(require_permissions("school.update"))],
)
async def update_communication_settings(
    data: CommunicationSettingsUpdate,
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> CommunicationSettingsResponse:
    """
    Partially update communication settings for the current school.

    Only sections present in the request body are overwritten; other
    sections retain their current values.
    """
    service = CommunicationSettingsService(db)
    try:
        updated = await service.update_settings(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            update_data=data,
        )
        return CommunicationSettingsResponse.model_validate(updated.model_dump())
    except CommunicationSettingsService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)
