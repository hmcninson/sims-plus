# Phase 4: Custom Roles with Granular Permissions

**Complexity:** Large
**Requirements:** UM-010
**Dependencies:** Modifies `auth.py` permission resolution (serialize with Phase 3)
**Estimated effort:** 3-4 days
**Feature gate:** Professional + Enterprise tiers only

---

## Summary

Implement database-backed custom roles that allow school admins to create roles with specific permission sets. Custom roles extend the existing RBAC system without replacing it — a custom role always has a `base_role` (one of the predefined roles) that acts as its permission ceiling.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | New `custom_roles` table with JSONB permissions | Flexible; no schema change per permission |
| Enum modification | None — `UserRole` enum unchanged | PostgreSQL enums can't have values removed |
| User assignment | `custom_role_id` FK on users table | Simple FK; one custom role per user |
| Permission ceiling | Capped at base_role | Prevents privilege escalation via misconfiguration |
| Permission format | Same string format as existing RBAC | `"module.action"` — drop-in compatible |
| Token embedding | Custom role permissions embedded in JWT | Same as current behavior; no per-request DB lookup |
| Feature gate | Professional + Enterprise only | Starter schools use predefined roles |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Permission Resolution                │
│                                                          │
│  User has custom_role_id?                                │
│    ├── YES → Load custom_roles.permissions from DB       │
│    │         → Embed in JWT token                        │
│    └── NO  → Use ROLE_PERMISSIONS[user.role] (static)    │
│              → Embed in JWT token (current behavior)     │
│                                                          │
│  At runtime, all permission checks use JWT permissions   │
│  (no change to require_permissions() or endpoint deps)   │
└──────────────────────────────────────────────────────────┘
```

---

## Task 1: Create CustomRole Model

### New File: `backend/app/models/custom_role.py`

```python
"""Custom role model for tenant-configurable RBAC."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import Base, SoftDeleteMixin, TenantMixin
from app.models.user import UserRole

# Import SQLAlchemy Enum type
from sqlalchemy import Enum as SQLEnum


class CustomRole(Base, TenantMixin, SoftDeleteMixin):
    # NOTE: Do NOT add TimestampMixin — Base already provides created_at and updated_at.
    # Do NOT define explicit id, created_at, updated_at columns — inherited from Base.
    """
    Tenant-scoped custom role with configurable permissions.

    Permissions are stored as a JSONB array of permission strings
    (same format as ROLE_PERMISSIONS in auth.py).

    Each custom role has a base_role that defines its permission ceiling —
    the custom role's permissions must be a subset of the base_role's
    permissions.
    """

    __tablename__ = "custom_roles"
    __table_args__ = (
        # NOTE: Use a partial unique index instead of a full unique constraint.
        # The partial index (WHERE deleted_at IS NULL) is created in the migration,
        # not here. This allows soft-deleted role slugs to be reused.
    )

    # id, created_at, updated_at inherited from Base — do not redefine

    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Display name (e.g., 'Head of Department')",
    )
    slug: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="URL-safe identifier (e.g., 'head-of-department')",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Optional description of the role's purpose",
    )
    base_role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name="userrole",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        comment="Parent role — defines the permission ceiling",
    )
    permissions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Array of permission strings (e.g., ['students.read', 'attendance.mark'])",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
        comment="If True, cannot be deleted (reserved for system-created roles)",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
```

### Update User Model: `backend/app/models/user.py`

Add FK column:

```python
custom_role_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("custom_roles.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
    comment="If set, user's permissions come from this custom role instead of ROLE_PERMISSIONS",
)
```

**Note:** `ondelete="SET NULL"` ensures that if a custom role is hard-deleted, users revert to their base role permissions.

---

## Task 2: Define Permissions Catalog

### New File: `backend/app/constants/permissions.py`

```python
"""
Master permissions catalog.

Defines all available permissions in the system, organized by module.
Used by:
1. CustomRoleService — validates that custom role permissions are valid
2. Frontend permission picker — displays categorized checkboxes
3. ROLE_PERMISSIONS in auth.py — references these same strings
"""

PERMISSIONS_CATALOG = [
    {
        "module": "Students",
        "permissions": [
            {"key": "students.read", "label": "View students", "description": "View student profiles and enrollment data"},
            {"key": "students.create", "label": "Create students", "description": "Register new students"},
            {"key": "students.update", "label": "Edit students", "description": "Update student profiles"},
            {"key": "students.delete", "label": "Delete students", "description": "Remove student records"},
            {"key": "students.import", "label": "Import students", "description": "Bulk import from CSV"},
            {"key": "students.export", "label": "Export students", "description": "Export student data"},
        ],
    },
    {
        "module": "Staff",
        "permissions": [
            {"key": "staff.read", "label": "View staff", "description": "View staff profiles"},
            {"key": "staff.create", "label": "Create staff", "description": "Add new staff members"},
            {"key": "staff.update", "label": "Edit staff", "description": "Update staff profiles"},
            {"key": "staff.delete", "label": "Delete staff", "description": "Remove staff records"},
        ],
    },
    {
        "module": "Academic",
        "permissions": [
            {"key": "classes.read", "label": "View classes", "description": "View class structure"},
            {"key": "classes.create", "label": "Create classes", "description": "Add new classes"},
            {"key": "classes.update", "label": "Edit classes", "description": "Modify class settings"},
            {"key": "subjects.read", "label": "View subjects", "description": "View subject catalog"},
            {"key": "subjects.update", "label": "Edit subjects", "description": "Modify subjects"},
            {"key": "academics.read", "label": "View academic settings", "description": "View grading, terms, etc."},
            {"key": "academics.update", "label": "Edit academic settings", "description": "Modify academic config"},
            {"key": "grading.read", "label": "View grading scales", "description": "View grading configuration"},
            {"key": "grading.update", "label": "Edit grading scales", "description": "Modify grading scales"},
        ],
    },
    {
        "module": "Attendance",
        "permissions": [
            {"key": "attendance.read", "label": "View attendance", "description": "View attendance records"},
            {"key": "attendance.mark", "label": "Mark attendance", "description": "Record student attendance"},
        ],
    },
    {
        "module": "Exams & Assessment",
        "permissions": [
            {"key": "exams.read", "label": "View exams", "description": "View exam definitions"},
            {"key": "exams.create", "label": "Create exams", "description": "Create new exams"},
            {"key": "exams.scores.read", "label": "View scores", "description": "View exam scores"},
            {"key": "exams.scores.enter", "label": "Enter scores", "description": "Enter/edit exam scores"},
            {"key": "exams.reports", "label": "Generate reports", "description": "Generate report cards"},
        ],
    },
    {
        "module": "Finance",
        "permissions": [
            {"key": "finance.read", "label": "View finance", "description": "View fees, invoices, payments"},
            {"key": "finance.create", "label": "Create financial records", "description": "Create invoices, record payments"},
            {"key": "finance.update", "label": "Edit financial records", "description": "Modify invoices, fee structures"},
            {"key": "finance.delete", "label": "Delete financial records", "description": "Remove financial records"},
            {"key": "finance.reports", "label": "Financial reports", "description": "Generate financial reports"},
        ],
    },
    {
        "module": "Preschool",
        "permissions": [
            {"key": "preschool.read", "label": "View preschool", "description": "View observations, logs"},
            {"key": "preschool.create", "label": "Create preschool records", "description": "Add observations, assessments"},
            {"key": "preschool.update", "label": "Edit preschool records", "description": "Modify observations"},
        ],
    },
    {
        "module": "Boarding",
        "permissions": [
            {"key": "boarding.read", "label": "View boarding", "description": "View dormitories, exeats"},
            {"key": "boarding.write", "label": "Manage boarding", "description": "Manage dormitories, assign beds"},
        ],
    },
    {
        "module": "Communication",
        "permissions": [
            {"key": "communications.read", "label": "View messages", "description": "View sent messages and history"},
            {"key": "communications.send", "label": "Send messages", "description": "Send SMS and email messages"},
        ],
    },
    {
        "module": "Reports",
        "permissions": [
            {"key": "reports.academic", "label": "Academic reports", "description": "Generate academic reports"},
            {"key": "reports.financial", "label": "Financial reports", "description": "Generate financial reports"},
            {"key": "reports.hr", "label": "HR reports", "description": "Generate HR/staff reports"},
        ],
    },
    {
        "module": "User Management",
        "permissions": [
            {"key": "users.read", "label": "View users", "description": "View user accounts"},
            {"key": "users.create", "label": "Create users", "description": "Create new user accounts"},
            {"key": "users.update", "label": "Edit users", "description": "Modify user accounts and roles"},
            {"key": "users.delete", "label": "Delete users", "description": "Deactivate/delete user accounts"},
        ],
    },
    {
        "module": "Admissions",
        "permissions": [
            {"key": "admissions.read", "label": "View admissions", "description": "View applications"},
            {"key": "admissions.create", "label": "Create admissions", "description": "Create admission periods"},
            {"key": "admissions.review", "label": "Review applications", "description": "Accept/reject applications"},
        ],
    },
    {
        "module": "Curriculum",
        "permissions": [
            {"key": "curriculum.read", "label": "View curriculum", "description": "View curriculum profiles"},
        ],
    },
    {
        "module": "Transport",
        "permissions": [
            {"key": "transport.read", "label": "View transport", "description": "View routes, vehicles"},
        ],
    },
    {
        "module": "Settings",
        "permissions": [
            {"key": "school.read", "label": "View school settings", "description": "View school configuration"},
            {"key": "school.update", "label": "Edit school settings", "description": "Modify school configuration"},
            {"key": "subscription.read", "label": "View subscription", "description": "View plan details"},
            {"key": "subscription.manage", "label": "Manage subscription", "description": "Upgrade/change plan"},
        ],
    },
]

# Flat set of all valid permission keys (for validation)
ALL_PERMISSION_KEYS = set()
for module in PERMISSIONS_CATALOG:
    for perm in module["permissions"]:
        ALL_PERMISSION_KEYS.add(perm["key"])
```

**IMPORTANT:** The PERMISSIONS_CATALOG above is incomplete. It MUST be expanded to include ALL permissions referenced in ROLE_PERMISSIONS in `auth.py`, including but not limited to:
- `teacher.*` permissions: `exams.ca.read`, `exams.ca.create`, `exams.ca.update`, `exams.scores.submit`
- `parent.*` permissions: `children.read`, `finance.invoices.read`
- `applicant.*` permissions
- `boarding.exeat.approve`
- `self.read`, `self.update`
- Any other permissions from `ROLE_PERMISSIONS` not already in the catalog

Without these, custom roles based on teacher/parent/house_parent will have empty permission pickers.

---

## Task 3: Create CustomRole Service

### New File: `backend/app/services/custom_role.py`

```python
"""
Custom role CRUD service.

Custom roles are tenant-scoped and allow school admins to create
roles with specific permission subsets of a base role.
"""

import re
import structlog
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.permissions import ALL_PERMISSION_KEYS, PERMISSIONS_CATALOG
from app.models.custom_role import CustomRole
from app.models.user import User, UserRole
from app.services.auth import AuthService  # For ROLE_PERMISSIONS

logger = structlog.get_logger()


class CustomRoleError(Exception):
    def __init__(self, message: str, code: str = "custom_role_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class CustomRoleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert role name to URL-safe slug."""
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s-]+', '-', slug)
        return slug[:100]

    @staticmethod
    def _get_base_role_permissions(base_role: str) -> set[str]:
        """
        Get the full set of resolved permissions for a base role.
        Expands wildcards (e.g., "staff.*" → all staff.* permissions).
        """
        role_perms = AuthService.ROLE_PERMISSIONS.get(base_role, [])
        resolved = set()
        for perm in role_perms:
            if perm.endswith(".*"):
                prefix = perm[:-2]  # e.g., "staff"
                for key in ALL_PERMISSION_KEYS:
                    if key.startswith(prefix + "."):
                        resolved.add(key)
            elif perm == "*":
                return ALL_PERMISSION_KEYS.copy()
            else:
                resolved.add(perm)
        return resolved

    def _validate_permissions(
        self, permissions: list[str], base_role: str
    ) -> list[str]:
        """
        Validate that:
        1. All permissions are valid keys from the catalog
        2. All permissions are within the base_role's permission ceiling

        Returns list of validation errors (empty if valid).
        """
        errors = []
        base_perms = self._get_base_role_permissions(base_role)

        for perm in permissions:
            if perm not in ALL_PERMISSION_KEYS:
                errors.append(f"Unknown permission: {perm}")
            elif perm not in base_perms:
                errors.append(
                    f"Permission '{perm}' exceeds base role '{base_role}' ceiling"
                )

        return errors

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

        Args:
            tenant_id: Tenant UUID
            name: Display name (e.g., "Head of Department")
            base_role: Base role for permission ceiling
            permissions: List of permission strings
            description: Optional description
            created_by: Admin user who created the role

        Raises:
            CustomRoleError: On validation failure or duplicate slug
        """
        # Validate base_role
        if base_role not in AuthService.ROLE_PERMISSIONS:
            raise CustomRoleError(f"Invalid base role: {base_role}", "invalid_base_role")

        # Don't allow base roles that are too powerful
        forbidden_base_roles = {"platform_admin", "chain_admin"}
        if base_role in forbidden_base_roles:
            raise CustomRoleError(
                f"Cannot use '{base_role}' as a base role for custom roles",
                "forbidden_base_role",
            )

        # Validate permissions
        validation_errors = self._validate_permissions(permissions, base_role)
        if validation_errors:
            raise CustomRoleError(
                f"Invalid permissions: {'; '.join(validation_errors)}",
                "invalid_permissions",
            )

        # Generate slug
        slug = self._slugify(name)

        # Check slug uniqueness
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
        description: str | None = ...,  # Use sentinel to distinguish None from not-provided
    ) -> CustomRole:
        """Update a custom role. Cannot change base_role (create a new role instead)."""
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
        return role

    async def delete_role(self, role_id: UUID, tenant_id: UUID) -> bool:
        """
        Soft-delete a custom role.
        Fails if users are still assigned to it.
        """
        role = await self._get_role(role_id, tenant_id)

        if role.is_system:
            raise CustomRoleError("Cannot delete system roles", "system_role")

        # Check for assigned users
        user_count = await self.db.scalar(
            select(func.count(User.id)).where(
                User.custom_role_id == role_id,
                User.deleted_at.is_(None),
            )
        )
        if user_count and user_count > 0:
            raise CustomRoleError(
                f"Cannot delete role: {user_count} user(s) still assigned. "
                "Reassign users to another role first.",
                "users_assigned",
            )

        from datetime import datetime, timezone
        role.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def list_roles(self, tenant_id: UUID) -> list[CustomRole]:
        """List all active custom roles for a tenant."""
        result = await self.db.execute(
            select(CustomRole).where(
                CustomRole.tenant_id == tenant_id,
                CustomRole.deleted_at.is_(None),
            ).order_by(CustomRole.name)
        )
        return list(result.scalars().all())

    async def get_role(self, role_id: UUID, tenant_id: UUID) -> CustomRole:
        """Get a single custom role by ID."""
        return await self._get_role(role_id, tenant_id)

    async def get_role_user_count(self, role_id: UUID, tenant_id: UUID) -> int:
        """Get the number of users assigned to a custom role."""
        result = await self.db.scalar(
            select(func.count(User.id)).where(
                User.custom_role_id == role_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        return result or 0

    async def get_available_permissions(self, base_role: str) -> list[dict]:
        """
        Get the permissions catalog filtered by what the base_role allows.
        Used by the frontend to show which checkboxes are available.
        """
        base_perms = self._get_base_role_permissions(base_role)

        filtered_catalog = []
        for module in PERMISSIONS_CATALOG:
            filtered_perms = [
                perm for perm in module["permissions"]
                if perm["key"] in base_perms
            ]
            if filtered_perms:
                filtered_catalog.append({
                    "module": module["module"],
                    "permissions": filtered_perms,
                })
        return filtered_catalog

    async def _get_role(self, role_id: UUID, tenant_id: UUID) -> CustomRole:
        """Internal: get role or raise error."""
        result = await self.db.execute(
            select(CustomRole).where(
                CustomRole.id == role_id,
                CustomRole.tenant_id == tenant_id,
                CustomRole.deleted_at.is_(None),
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise CustomRoleError("Custom role not found", "not_found")
        return role
```

---

## Task 4: Modify Permission Resolution in Auth Service

### File: `backend/app/services/auth.py`

**Add a method to resolve effective permissions:**

```python
@classmethod
async def get_effective_permissions(
    cls, user: User, db: AsyncSession
) -> list[str]:
    """
    Get the effective permissions for a user.

    If user has a custom_role_id, load permissions from the custom_roles table.
    Otherwise, use the static ROLE_PERMISSIONS dict.

    This method is called during token creation (login and refresh).
    The resolved permissions are embedded in the JWT token.
    """
    if user.custom_role_id:
        from app.models.custom_role import CustomRole
        result = await db.execute(
            select(CustomRole.permissions).where(
                CustomRole.id == user.custom_role_id,
                CustomRole.tenant_id == user.tenant_id,
                CustomRole.deleted_at.is_(None),
            )
        )
        custom_perms = result.scalar_one_or_none()
        if custom_perms is not None:
            return custom_perms
        # Fallback to base role if custom role was deleted
        # (ondelete=SET NULL should handle this, but defense-in-depth)

    return cls.get_role_permissions(user.role.value)
```

**Modify `authenticate()` and `refresh_tokens()`** to call `get_effective_permissions()` instead of the static `get_role_permissions()` when building the JWT payload:

```python
# Before (in authenticate and refresh_tokens):
permissions = self.get_role_permissions(user.role.value)

# After:
permissions = await self.get_effective_permissions(user, self.db)
```

---

## Task 5: Create Custom Role Endpoints

### New File: `backend/app/api/v1/endpoints/custom_roles.py`

```python
"""Custom role management endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.custom_role import CustomRoleService, CustomRoleError
from app.schemas.custom_role import (
    CustomRoleCreate,
    CustomRoleUpdate,
    CustomRoleResponse,
    CustomRoleListResponse,
    PermissionsCatalogResponse,
)

# NOTE: Do NOT set prefix here — prefix is set in router.py during include_router
router = APIRouter(tags=["custom-roles"])


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
    service = CustomRoleService(db)
    roles = await service.list_roles(UUID(tenant.tenant_id))

    # Get user counts for each role
    role_data = []
    for role in roles:
        count = await service.get_role_user_count(role.id, UUID(tenant.tenant_id))
        role_data.append({**role.__dict__, "user_count": count})

    return CustomRoleListResponse(roles=role_data)


@router.post(
    "",
    response_model=CustomRoleResponse,
    status_code=201,
    summary="Create a custom role",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def create_custom_role(
    data: CustomRoleCreate,
    tenant: RequestTenant,
    current_user: ValidatedUser,
    db: DatabaseSession,
    request: Request,
):
    # Feature gate: Professional + Enterprise only
    # Check tenant subscription tier
    # (use existing feature check pattern)

    service = CustomRoleService(db)
    try:
        role = await service.create_role(
            tenant_id=UUID(tenant.tenant_id),
            name=data.name,
            base_role=data.base_role,
            permissions=data.permissions,
            description=data.description,
            created_by=UUID(current_user["user_id"]),
        )
    except CustomRoleError as e:
        # Status code mapping: 409 for duplicate_slug, 404 for not_found, 400 for others
        status_code = 409 if e.code == "duplicate_slug" else 400
        raise HTTPException(status_code=status_code, detail=e.message)

    # Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ROLE_CREATED,
        tenant_id=UUID(tenant.tenant_id),
        user_id=UUID(current_user["user_id"]),
        target_type="custom_role",
        target_id=str(role.id),
        details={"name": data.name, "base_role": data.base_role},
    )

    return role


## IMPORTANT: This route MUST be registered BEFORE /{role_id} to avoid
## FastAPI treating "permissions" as a role_id UUID path parameter.

@router.get(
    "/permissions/catalog",
    response_model=PermissionsCatalogResponse,
    summary="Get available permissions catalog",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def get_permissions_catalog(
    base_role: str | None = None,
    db: DatabaseSession = None,  # Not actually needed for unfiltered catalog
):
    """
    Get the permissions catalog.
    If base_role is specified, only returns permissions allowed for that base role.
    """
    service = CustomRoleService(db)
    if base_role:
        catalog = await service.get_available_permissions(base_role)
    else:
        from app.constants.permissions import PERMISSIONS_CATALOG
        catalog = PERMISSIONS_CATALOG
    return PermissionsCatalogResponse(modules=catalog)


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
    service = CustomRoleService(db)
    try:
        return await service.get_role(role_id, UUID(tenant.tenant_id))
    except CustomRoleError as e:
        raise HTTPException(status_code=404, detail=e.message)


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
    service = CustomRoleService(db)
    try:
        # NOTE: Use model_dump(exclude_unset=True) for update operations
        # to distinguish between "field not provided" and "field set to None"
        return await service.update_role(
            role_id=role_id,
            tenant_id=UUID(tenant.tenant_id),
            name=data.name,
            permissions=data.permissions,
            description=data.description,
        )
    except CustomRoleError as e:
        status_code = 409 if e.code == "duplicate_slug" else (404 if e.code == "not_found" else 400)
        raise HTTPException(status_code=status_code, detail=e.message)

    # Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ROLE_UPDATED,
        tenant_id=UUID(tenant.tenant_id),
        user_id=UUID(current_user["user_id"]),
        target_type="custom_role",
        target_id=str(role_id),
        details={"updates": data.model_dump(exclude_unset=True)},
    )


@router.delete(
    "/{role_id}",
    status_code=204,
    summary="Delete a custom role",
    dependencies=[Depends(require_permissions("users.delete"))],
)
async def delete_custom_role(
    role_id: UUID,
    tenant: RequestTenant,
    current_user: ValidatedUser,
    db: DatabaseSession,
):
    service = CustomRoleService(db)
    try:
        await service.delete_role(role_id, UUID(tenant.tenant_id))
    except CustomRoleError as e:
        status_code = 409 if e.code in ("users_assigned", "duplicate_slug") else (404 if e.code == "not_found" else 400)
        raise HTTPException(status_code=status_code, detail=e.message)

    # Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ROLE_DELETED,
        tenant_id=UUID(tenant.tenant_id),
        user_id=UUID(current_user["user_id"]),
        target_type="custom_role",
        target_id=str(role_id),
        details={},
    )
```

### Register Router: `backend/app/api/v1/router.py`

```python
from app.api.v1.endpoints.custom_roles import router as custom_roles_router
api_router.include_router(custom_roles_router, prefix="/custom-roles")
```

---

## Task 6: Create Custom Role Schemas

### New File: `backend/app/schemas/custom_role.py`

```python
"""Pydantic schemas for custom roles."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class CustomRoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    base_role: str = Field(..., description="Parent role for permission ceiling")
    permissions: list[str] = Field(..., min_length=1)
    description: str | None = None


class CustomRoleUpdate(BaseModel):
    name: str | None = None
    permissions: list[str] | None = None
    description: str | None = None


class CustomRoleResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    base_role: str
    permissions: list[str]
    is_system: bool
    user_count: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomRoleListResponse(BaseModel):
    roles: list[CustomRoleResponse]


class PermissionItem(BaseModel):
    key: str
    label: str
    description: str


class PermissionModule(BaseModel):
    module: str
    permissions: list[PermissionItem]


class PermissionsCatalogResponse(BaseModel):
    modules: list[PermissionModule]
```

---

## Task 7: Frontend — Custom Roles Page

### New File: `frontend/app/(dashboard)/settings/roles/page.tsx`

This page lists custom roles and allows creating/editing/deleting them.

**Layout:**
- Header: "Custom Roles" title + "Create Role" button
- Feature gate banner for Starter tier: "Upgrade to Professional to create custom roles"
- Table: Name | Base Role | Permissions Count | Users | Actions

**Create/Edit Dialog:**
1. Name input
2. Base role dropdown (school_admin, academic_head, finance_officer, hr_officer, teacher, house_parent)
3. Description textarea (optional)
4. Permission picker: categorized checkboxes
   - Grouped by module (Students, Staff, Academic, etc.)
   - Only shows permissions allowed by the selected base role
   - "Select all in module" checkbox per group
   - Changes when base_role dropdown changes (re-fetches catalog)

**Delete:** Confirmation dialog. Blocked if users are assigned (show user count).

---

## Task 8: Frontend — Integrate Custom Role into User Forms

### File: `frontend/app/(dashboard)/settings/users/users-management.tsx`

**In the user create/edit dialog, add an optional "Custom Role" dropdown:**

```tsx
<FormField
  control={form.control}
  name="custom_role_id"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Custom Role (Optional)</FormLabel>
      <Select onValueChange={field.onChange} value={field.value}>
        <SelectTrigger>
          <SelectValue placeholder="Use default role permissions" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">Default permissions</SelectItem>
          {customRoles
            .filter((r) => r.base_role === selectedRole)
            .map((role) => (
              <SelectItem key={role.id} value={role.id}>
                {role.name}
              </SelectItem>
            ))}
        </SelectContent>
      </Select>
      <FormDescription>
        Override default permissions with a custom role
      </FormDescription>
    </FormItem>
  )}
/>
```

The dropdown filters to show only custom roles whose `base_role` matches the selected user role.

---

## Task 9: Frontend — Server Actions and Types

### New File: `frontend/actions/custom-roles.action.ts`

```typescript
"use server";

import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import type { ActionResult } from "@/types";
import type { CustomRole, PermissionsCatalog } from "@/types/custom-role.type";

export async function listCustomRoles(): Promise<ActionResult<{ roles: CustomRole[] }>> {
  try {
    const response = await apiGet<{ roles: CustomRole[] }>("/custom-roles");
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to load roles" };
  }
}

export async function createCustomRole(data: {
  name: string;
  base_role: string;
  permissions: string[];
  description?: string;
}): Promise<ActionResult<CustomRole>> {
  try {
    const response = await apiPost<CustomRole>("/custom-roles", data);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to create role" };
  }
}

export async function updateCustomRole(
  id: string,
  data: { name?: string; permissions?: string[]; description?: string },
): Promise<ActionResult<CustomRole>> {
  try {
    const response = await apiPut<CustomRole>(`/custom-roles/${id}`, data);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update role" };
  }
}

export async function deleteCustomRole(id: string): Promise<ActionResult> {
  try {
    await apiDelete(`/custom-roles/${id}`);
    return { success: true, data: null };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to delete role" };
  }
}

export async function getPermissionsCatalog(
  baseRole?: string,
): Promise<ActionResult<PermissionsCatalog>> {
  try {
    const url = baseRole
      ? `/custom-roles/permissions/catalog?base_role=${baseRole}`
      : "/custom-roles/permissions/catalog";
    const response = await apiGet<PermissionsCatalog>(url);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to load permissions" };
  }
}
```

### New File: `frontend/types/custom-role.type.ts`

```typescript
export interface CustomRole {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  base_role: string;
  permissions: string[];
  is_system: boolean;
  user_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface PermissionItem {
  key: string;
  label: string;
  description: string;
}

export interface PermissionModule {
  module: string;
  permissions: PermissionItem[];
}

export interface PermissionsCatalog {
  modules: PermissionModule[];
}
```

---

## Task 10: Add Sidebar Navigation

### File: `frontend/components/dashboard/app-sidebar.tsx`

Add "Roles" as a sub-item under Settings, visible to users with `users.read` permission:

```tsx
{
  title: "Roles",
  url: "/settings/roles",
  icon: Shield, // from lucide-react
}
```

---

## Task 11: Update User Schemas (Backend)

### File: `backend/app/schemas/user.py`

Add `custom_role_id` and `custom_role_name` to user response schemas:

```python
class UserResponse(BaseModel):
    # ... existing fields ...
    custom_role_id: UUID | None = None
    custom_role_name: str | None = None  # Denormalized for display
```

In the user service, when returning user data, join or include the custom role name.

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Privilege escalation | Permissions capped at base_role ceiling |
| Invalid permission injection | Validated against `ALL_PERMISSION_KEYS` catalog |
| Cross-tenant role access | RLS on `custom_roles` table + cross-tenant FK trigger (see 07-migration-plan.md) |
| Platform/Chain admin override | Cannot use platform_admin or chain_admin as base_role |
| Role deletion with users | Blocked; must reassign users first |
| Stale JWT permissions | Permissions refresh on next token refresh (same as current) |

---

## Verification Checklist

- [ ] Custom roles CRUD works (create, list, get, update, delete)
- [ ] Permissions validated against catalog (unknown keys rejected)
- [ ] Permissions capped at base_role ceiling (exceeding keys rejected)
- [ ] Slug auto-generated from name and unique per tenant
- [ ] System roles cannot be modified or deleted
- [ ] Deletion blocked when users are assigned
- [ ] RLS enforced — roles invisible across tenants
- [ ] User with custom_role_id gets custom permissions in JWT
- [ ] User without custom_role_id gets default ROLE_PERMISSIONS
- [ ] Custom role deletion sets user.custom_role_id to NULL (ondelete=SET NULL)
- [ ] Permission catalog endpoint returns correct data
- [ ] Catalog filtered by base_role when specified
- [ ] Feature gate: Starter tier sees upgrade prompt
- [ ] Frontend permission picker shows categorized checkboxes
- [ ] Frontend custom role dropdown in user form filters by base_role
- [ ] Sidebar shows "Roles" link for users with users.read permission
