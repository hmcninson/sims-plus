"""
SIMS Plus - Sibling Groups Endpoint

Endpoint for detecting sibling groups (students sharing guardians).
Used for sibling discount workflows.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.preschool.core import convert_uuid
from app.services.finance import SiblingService

router = APIRouter()


@router.get(
    "/sibling-groups",
    summary="Detect sibling groups",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_sibling_groups(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    school_id: UUID | None = Query(None),
):
    """Detect sibling groups within the tenant.

    Returns groups of students who share a guardian, useful for
    identifying candidates for sibling discounts.
    """
    service = SiblingService(db)
    return await service.detect_sibling_groups(
        convert_uuid(tenant.tenant_id),
        school_id=school_id,
    )
