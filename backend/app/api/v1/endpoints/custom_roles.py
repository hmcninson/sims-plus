"""
SIMS Plus - Custom Role Management Endpoints

CRUD endpoints for tenant-scoped custom roles with granular permissions.
Feature-gated to Professional and Enterprise tiers.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_feature,
    require_permissions,
)
from app.models.user import User
from app.schemas.custom_role import (
    CustomRoleAssign,
    CustomRoleCreate,
    CustomRoleListResponse,
    CustomRoleResponse,
    CustomRoleUpdate,
    PermissionsCatalogResponse,
)
from app.services.audit import AuditEventType, AuditService
from app.services.custom_role import CustomRoleError, CustomRoleService
from app.services.token_blacklist import get_token_blacklist_service

logger = structlog.get_logger()

# Feature gate: custom_roles requires Professional or Enterprise tier.
# The prefix is set in router.py via include_router(prefix="/custom-roles").
router = APIRouter(
    tags=["Custom Roles"],
    dependencies=[Depends(require_feature("custom_roles"))],
)


def _error_status_code(code: str) -> int:
    """Map CustomRoleError.code to HTTP status codes."""
    if code == "not_found":
        return 404
    if code in ("duplicate_slug", "users_assigned"):
        return 409
    if code == "system_role":
        return 403
    # invalid_permissions, invalid_base_role, forbidden_base_role, base_role_mismatch
    return 400


# ------------------------------------------------------------------
# IMPORTANT: The /permissions/catalog route MUST be registered BEFORE
# /{role_id} so FastAPI doesn't try to parse "permissions" as a UUID.
# ------------------------------------------------------------------


@router.get(
    "/permissions/catalog",
    response_model=PermissionsCatalogResponse,
    summary="Get available permissions catalog",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def get_permissions_catalog(
    base_role: str | None = Query(
        None, description="Filter to permissions allowed for this base role"
    ),
):
    """
    Get the permissions catalog grouped by module.

    If base_role is specified, only returns permissions that fall within
    that role's permission ceiling. Used by the frontend permission picker
    to determine which checkboxes are available.
    """
    catalog = CustomRoleService.get_permissions_catalog(base_role)
    return PermissionsCatalogResponse(modules=catalog)


@router.get(
    "",
    response_model=CustomRoleListResponse,
    summary="List custom roles",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def list_custom_roles(
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """List all active custom roles for the current tenant, with user counts."""
    service = CustomRoleService(db)
    roles = await service.list_roles(tenant.tenant_id)

    # Attach user counts to each role for display
    role_responses = []
    for role in roles:
        count = await service.get_role_user_count(role.id, tenant.tenant_id)
        role_responses.append(
            CustomRoleResponse(
                id=role.id,
                name=role.name,
                slug=role.slug,
                description=role.description,
                base_role=role.base_role.value,
                permissions=role.permissions,
                is_system=role.is_system,
                user_count=count,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )
        )

    return CustomRoleListResponse(roles=role_responses)


@router.post(
    "",
    response_model=CustomRoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom role",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def create_custom_role(
    data: CustomRoleCreate,
    tenant: RequestTenant,
    current_user: ValidatedUser,
    db: DatabaseSession,
):
    """
    Create a new custom role with a set of permissions.

    The base_role defines the permission ceiling — every permission
    in the list must be a subset of what the base_role statically
    grants. This prevents privilege escalation via custom roles.
    """
    service = CustomRoleService(db)
    try:
        role = await service.create_role(
            tenant_id=tenant.tenant_id,
            name=data.name,
            base_role=data.base_role,
            permissions=data.permissions,
            description=data.description,
            created_by=UUID(current_user["user_id"]),
        )
    except CustomRoleError as e:
        raise HTTPException(
            status_code=_error_status_code(e.code), detail=e.message
        )

    # Audit trail for role creation
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.PERMISSION_GRANTED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="custom_role",
        target_id=role.id,
        details={
            "action": "created",
            "name": data.name,
            "base_role": data.base_role,
            "permission_count": len(data.permissions),
        },
    )

    user_count = await service.get_role_user_count(role.id, tenant.tenant_id)
    return CustomRoleResponse(
        id=role.id,
        name=role.name,
        slug=role.slug,
        description=role.description,
        base_role=role.base_role.value,
        permissions=role.permissions,
        is_system=role.is_system,
        user_count=user_count,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get(
    "/{role_id}",
    response_model=CustomRoleResponse,
    summary="Get a custom role",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def get_custom_role(
    role_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Get a single custom role by ID, including user count."""
    service = CustomRoleService(db)
    try:
        role = await service.get_role(role_id, tenant.tenant_id)
    except CustomRoleError as e:
        raise HTTPException(
            status_code=_error_status_code(e.code), detail=e.message
        )

    user_count = await service.get_role_user_count(role.id, tenant.tenant_id)
    return CustomRoleResponse(
        id=role.id,
        name=role.name,
        slug=role.slug,
        description=role.description,
        base_role=role.base_role.value,
        permissions=role.permissions,
        is_system=role.is_system,
        user_count=user_count,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.put(
    "/{role_id}",
    response_model=CustomRoleResponse,
    summary="Update a custom role",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def update_custom_role(
    role_id: UUID,
    data: CustomRoleUpdate,
    tenant: RequestTenant,
    current_user: ValidatedUser,
    db: DatabaseSession,
):
    """
    Update a custom role's name, description, or permissions.

    Cannot change the base_role — create a new role instead.
    System roles cannot be modified.
    """
    service = CustomRoleService(db)
    try:
        role = await service.update_role(
            role_id=role_id,
            tenant_id=tenant.tenant_id,
            name=data.name,
            permissions=data.permissions,
            description=data.description,
        )
    except CustomRoleError as e:
        raise HTTPException(
            status_code=_error_status_code(e.code), detail=e.message
        )

    # Audit trail for role update
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.SETTINGS_CHANGED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="custom_role",
        target_id=role.id,
        details={
            "action": "updated",
            "updates": data.model_dump(exclude_unset=True),
        },
    )

    # Invalidate tokens for all users assigned to this custom role so they
    # pick up the updated permissions on their next login / token refresh.
    if data.permissions is not None:
        try:
            result = await db.execute(
                select(User.id).where(
                    User.custom_role_id == role_id,
                    User.tenant_id == tenant.tenant_id,
                    User.deleted_at.is_(None),
                )
            )
            affected_user_ids = result.scalars().all()

            if affected_user_ids:
                blacklist_service = await get_token_blacklist_service()
                for uid in affected_user_ids:
                    await blacklist_service.blacklist_user_tokens(str(uid))
                logger.info(
                    "tokens_blacklisted_on_custom_role_update",
                    role_id=str(role_id),
                    affected_users=len(affected_user_ids),
                )
        except Exception:
            logger.warning(
                "token_blacklist_failed_on_custom_role_update",
                role_id=str(role_id),
            )

    user_count = await service.get_role_user_count(role.id, tenant.tenant_id)
    return CustomRoleResponse(
        id=role.id,
        name=role.name,
        slug=role.slug,
        description=role.description,
        base_role=role.base_role.value,
        permissions=role.permissions,
        is_system=role.is_system,
        user_count=user_count,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom role",
    dependencies=[Depends(require_permissions("users.delete"))],
)
async def delete_custom_role(
    role_id: UUID,
    tenant: RequestTenant,
    current_user: ValidatedUser,
    db: DatabaseSession,
):
    """
    Soft-delete a custom role.

    Blocked if users are still assigned to this role (409 Conflict).
    System roles cannot be deleted.
    """
    service = CustomRoleService(db)
    try:
        await service.delete_role(role_id, tenant.tenant_id)
    except CustomRoleError as e:
        raise HTTPException(
            status_code=_error_status_code(e.code), detail=e.message
        )

    # Audit trail for role deletion
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.PERMISSION_REVOKED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="custom_role",
        target_id=role_id,
        details={"action": "deleted"},
    )
