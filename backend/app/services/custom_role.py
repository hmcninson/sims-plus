"""
Custom role CRUD service.

Custom roles are tenant-scoped and allow school admins to create
roles with specific permission subsets of a base role. The base_role
defines a permission ceiling — no custom role can grant permissions
that exceed what the base_role would statically provide.
"""

import re
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.permissions import ALL_PERMISSION_KEYS, PERMISSIONS_CATALOG
from app.models.custom_role import CustomRole
from app.models.user import User, UserRole
from app.services.auth import AuthService

logger = structlog.get_logger()


class CustomRoleError(Exception):
    """Custom role operation failed."""

    def __init__(self, message: str, code: str = "custom_role_error"):
        self.message = message
        self.code = code
        super().__init__(message)


# Base roles that are too powerful for custom role creation.
# Platform admins and chain admins manage multi-tenant infra —
# school-level custom roles should not inherit their scope.
_FORBIDDEN_BASE_ROLES = {"platform_admin", "chain_admin"}


class CustomRoleService:
    """Service for custom role CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Slug generation
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert role name to URL-safe slug."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s-]+", "-", slug)
        return slug[:100]

    # ------------------------------------------------------------------
    # Permission validation
    # ------------------------------------------------------------------

    @staticmethod
    def _get_base_role_permissions(base_role: str) -> set[str]:
        """
        Get the full set of resolved permissions for a base role.

        Expands wildcards (e.g., "staff.*" -> all staff.X permissions
        from the catalog). The wildcard "*" (platform_admin) returns
        every permission in the catalog.
        """
        role_perms = AuthService.ROLE_PERMISSIONS.get(base_role, [])
        resolved: set[str] = set()

        for perm in role_perms:
            if perm == "*":
                # Platform admin — all permissions
                return ALL_PERMISSION_KEYS.copy()
            if perm.endswith(".*"):
                # Wildcard — expand to all catalog keys with matching prefix
                prefix = perm[:-2]  # e.g., "staff"
                for key in ALL_PERMISSION_KEYS:
                    if key.startswith(prefix + "."):
                        resolved.add(key)
            else:
                resolved.add(perm)

        return resolved

    @classmethod
    def _validate_permissions(
        cls, permissions: list[str], base_role: str
    ) -> list[str]:
        """
        Validate that:
        1. All permissions are valid keys from the catalog
        2. All permissions are within the base_role's permission ceiling

        Returns list of validation error strings (empty if valid).
        """
        errors: list[str] = []
        base_perms = cls._get_base_role_permissions(base_role)

        for perm in permissions:
            if perm not in ALL_PERMISSION_KEYS:
                errors.append(f"Unknown permission: {perm}")
            elif perm not in base_perms:
                errors.append(
                    f"Permission '{perm}' exceeds base role '{base_role}' ceiling"
                )

        return errors

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def create_role(
        self,
        tenant_id: UUID,
        name: str,
        base_role: str,
        permissions: list[str],
        description: str | None = None,
        created_by: UUID | None = None,
    ) -> CustomRole:
        """
        Create a new custom role.

        Raises:
            CustomRoleError: On validation failure or duplicate slug
        """
        # Validate base_role is a known role
        if base_role not in AuthService.ROLE_PERMISSIONS:
            raise CustomRoleError(
                f"Invalid base role: {base_role}", "invalid_base_role"
            )

        # Prevent using overly-privileged base roles
        if base_role in _FORBIDDEN_BASE_ROLES:
            raise CustomRoleError(
                f"Cannot use '{base_role}' as a base role for custom roles",
                "forbidden_base_role",
            )

        # Validate every permission against catalog AND base_role ceiling
        validation_errors = self._validate_permissions(permissions, base_role)
        if validation_errors:
            raise CustomRoleError(
                f"Invalid permissions: {'; '.join(validation_errors)}",
                "invalid_permissions",
            )

        slug = self._slugify(name)

        # Check slug uniqueness within tenant (active roles only)
        existing = await self.db.execute(
            select(CustomRole.id).where(
                CustomRole.tenant_id == tenant_id,
                CustomRole.slug == slug,
                CustomRole.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise CustomRoleError(
                f"A role with the name '{name}' already exists",
                "duplicate_slug",
            )

        role = CustomRole(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            base_role=UserRole(base_role),
            permissions=permissions,
            description=description,
            created_by=created_by,
        )
        self.db.add(role)
        await self.db.flush()
        await self.db.refresh(role)

        logger.info(
            "custom_role_created",
            role_id=str(role.id),
            name=name,
            base_role=base_role,
            permission_count=len(permissions),
        )
        return role

    async def update_role(
        self,
        role_id: UUID,
        tenant_id: UUID,
        name: str | None = None,
        permissions: list[str] | None = None,
        # Use sentinel to distinguish "not provided" from "set to None"
        description: str | None = ...,  # type: ignore[assignment]
    ) -> CustomRole:
        """
        Update a custom role.

        Cannot change base_role — create a new role instead.
        System roles (is_system=True) cannot be modified.

        Raises:
            CustomRoleError: On validation failure, not found, or system role
        """
        role = await self._get_role(role_id, tenant_id)

        if role.is_system:
            raise CustomRoleError("Cannot modify system roles", "system_role")

        if name is not None:
            new_slug = self._slugify(name)
            # Check slug uniqueness (excluding current role)
            existing = await self.db.execute(
                select(CustomRole.id).where(
                    CustomRole.tenant_id == tenant_id,
                    CustomRole.slug == new_slug,
                    CustomRole.id != role_id,
                    CustomRole.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none():
                raise CustomRoleError(
                    f"A role with the name '{name}' already exists",
                    "duplicate_slug",
                )
            role.name = name
            role.slug = new_slug

        if permissions is not None:
            # Re-validate against base_role ceiling on every update
            validation_errors = self._validate_permissions(
                permissions, role.base_role.value
            )
            if validation_errors:
                raise CustomRoleError(
                    f"Invalid permissions: {'; '.join(validation_errors)}",
                    "invalid_permissions",
                )
            role.permissions = permissions

        if description is not ...:
            role.description = description

        await self.db.flush()
        await self.db.refresh(role)

        logger.info(
            "custom_role_updated",
            role_id=str(role.id),
            name=role.name,
        )
        return role

    async def delete_role(self, role_id: UUID, tenant_id: UUID) -> bool:
        """
        Soft-delete a custom role.

        Fails if users are still assigned to it (409 Conflict).
        System roles cannot be deleted.

        Raises:
            CustomRoleError: If role not found, is system, or has assigned users
        """
        role = await self._get_role(role_id, tenant_id)

        if role.is_system:
            raise CustomRoleError("Cannot delete system roles", "system_role")

        # Check for assigned users — prevent orphaning permission config
        user_count = await self._get_user_count(role_id, tenant_id)
        if user_count > 0:
            raise CustomRoleError(
                f"Cannot delete role: {user_count} user(s) still assigned. "
                "Reassign users to another role first.",
                "users_assigned",
            )

        role.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "custom_role_deleted",
            role_id=str(role.id),
            name=role.name,
        )
        return True

    async def list_roles(self, tenant_id: UUID) -> list[CustomRole]:
        """List all active custom roles for a tenant, ordered by name."""
        result = await self.db.execute(
            select(CustomRole)
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                CustomRole.tenant_id == tenant_id,
                CustomRole.deleted_at.is_(None),
            )
            .order_by(CustomRole.name)
        )
        return list(result.scalars().all())

    async def get_role(self, role_id: UUID, tenant_id: UUID) -> CustomRole:
        """Get a single custom role by ID."""
        return await self._get_role(role_id, tenant_id)

    async def get_role_user_count(self, role_id: UUID, tenant_id: UUID) -> int:
        """Get the number of active users assigned to a custom role."""
        return await self._get_user_count(role_id, tenant_id)

    async def assign_role_to_user(
        self,
        user_id: UUID,
        custom_role_id: UUID | None,
        tenant_id: UUID,
    ) -> User:
        """
        Assign a custom role to a user (or clear it by passing None).

        When custom_role_id is set, the user's JWT permissions will be
        sourced from the custom role instead of the static ROLE_PERMISSIONS.
        Clearing it reverts to default role-based permissions.

        Raises:
            CustomRoleError: If user or role not found
        """
        # Fetch user with tenant isolation
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                # Defense-in-depth: tenant_id filter on top of RLS
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise CustomRoleError("User not found", "not_found")

        if custom_role_id is not None:
            # Validate the custom role exists and belongs to this tenant
            role = await self._get_role(custom_role_id, tenant_id)

            # Ensure the custom role's base_role matches the user's role.
            # A teacher should not be assigned a role based on school_admin.
            if role.base_role != user.role:
                raise CustomRoleError(
                    f"Custom role base '{role.base_role.value}' does not match "
                    f"user's role '{user.role.value}'",
                    "base_role_mismatch",
                )

        user.custom_role_id = custom_role_id
        await self.db.flush()
        await self.db.refresh(user)

        logger.info(
            "custom_role_assigned",
            user_id=str(user_id),
            custom_role_id=str(custom_role_id) if custom_role_id else None,
        )
        return user

    # ------------------------------------------------------------------
    # Permissions catalog (for frontend picker)
    # ------------------------------------------------------------------

    @classmethod
    def get_permissions_catalog(
        cls, base_role: str | None = None
    ) -> list[dict]:
        """
        Get the permissions catalog, optionally filtered by base_role.

        When base_role is specified, only returns permissions that fall
        within that role's ceiling — used by the frontend to show which
        checkboxes should be available vs. disabled.
        """
        if not base_role:
            return PERMISSIONS_CATALOG

        base_perms = cls._get_base_role_permissions(base_role)

        filtered_catalog = []
        for module in PERMISSIONS_CATALOG:
            filtered_perms = [
                perm
                for perm in module["permissions"]
                if perm["key"] in base_perms
            ]
            if filtered_perms:
                filtered_catalog.append(
                    {
                        "module": module["module"],
                        "permissions": filtered_perms,
                    }
                )
        return filtered_catalog

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_role(self, role_id: UUID, tenant_id: UUID) -> CustomRole:
        """Internal: get role or raise error."""
        result = await self.db.execute(
            select(CustomRole).where(
                CustomRole.id == role_id,
                # Defense-in-depth: tenant_id filter on top of RLS
                CustomRole.tenant_id == tenant_id,
                CustomRole.deleted_at.is_(None),
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise CustomRoleError("Custom role not found", "not_found")
        return role

    async def _get_user_count(self, role_id: UUID, tenant_id: UUID) -> int:
        """Get count of active users assigned to a role."""
        result = await self.db.scalar(
            select(func.count(User.id)).where(
                User.custom_role_id == role_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        return result or 0
