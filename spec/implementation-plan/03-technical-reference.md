# SIMS Plus -- Technical Reference

**Document:** 03 of 04 (Technical Reference)
**Version:** 1.0
**Date:** 15 February 2026
**Author:** Harry McNinson
**Status:** Ready for Implementation

> This document contains all code patterns, SQL templates, API contracts, and configuration references that developers need. It is the authoritative "cookbook" for the SIMS Plus project. Every pattern shown here is derived from the actual codebase as of Sprint 14 (February 2026).

---

## Table of Contents

1. [Backend Code Patterns](#1-backend-code-patterns)
   - 1.1 [Base Model and Mixins](#11-base-model-and-mixins)
   - 1.2 [Model Definition Pattern](#12-model-definition-pattern)
   - 1.3 [Enum Definition Rules](#13-enum-definition-rules)
   - 1.4 [Service Layer Pattern](#14-service-layer-pattern)
   - 1.5 [Endpoint Pattern](#15-endpoint-pattern)
   - 1.6 [Pydantic Schema Pattern](#16-pydantic-schema-pattern)
   - 1.7 [Dependency Injection Reference](#17-dependency-injection-reference)
2. [Database Patterns](#2-database-patterns)
   - 2.1 [Row-Level Security Policy Template](#21-row-level-security-policy-template)
   - 2.2 [Tenant Context Functions](#22-tenant-context-functions)
   - 2.3 [Index Templates](#23-index-templates)
   - 2.4 [Migration Template](#24-migration-template)
   - 2.5 [Table Classification](#25-table-classification)
   - 2.6 [Enum Casing Rules](#26-enum-casing-rules)
3. [Authentication System](#3-authentication-system)
   - 3.1 [JWT Token Structure](#31-jwt-token-structure)
   - 3.2 [Password Hashing](#32-password-hashing)
   - 3.3 [Password Policy](#33-password-policy)
   - 3.4 [Account Lockout](#34-account-lockout)
   - 3.5 [Token Blacklisting](#35-token-blacklisting)
   - 3.6 [Cross-Tenant Token Rejection](#36-cross-tenant-token-rejection)
   - 3.7 [Role-Permission Mapping](#37-role-permission-mapping)
4. [API Contracts](#4-api-contracts)
   - 4.1 [Authentication Endpoints](#41-authentication-endpoints)
   - 4.2 [Tenant Endpoints](#42-tenant-endpoints)
   - 4.3 [Onboarding Endpoints](#43-onboarding-endpoints)
   - 4.4 [Standard Response Patterns](#44-standard-response-patterns)
   - 4.5 [Rate Limits](#45-rate-limits)
   - 4.6 [Error Response Format](#46-error-response-format)
5. [Frontend Patterns](#5-frontend-patterns)
   - 5.1 [API Client](#51-api-client)
   - 5.2 [Server Action Pattern](#52-server-action-pattern)
   - 5.3 [ActionResult Type](#53-actionresult-type)
   - 5.4 [File Naming Conventions](#54-file-naming-conventions)
   - 5.5 [Import Order](#55-import-order)
   - 5.6 [TypeScript Type Patterns](#56-typescript-type-patterns)
6. [Security Checklist](#6-security-checklist)
7. [Configuration Reference](#7-configuration-reference)
   - 7.1 [Environment Variables](#71-environment-variables)
   - 7.2 [Connection Strings](#72-connection-strings)
   - 7.3 [Redis Key Patterns](#73-redis-key-patterns)
   - 7.4 [Middleware Stack Order](#74-middleware-stack-order)
8. [Testing Patterns](#8-testing-patterns)
   - 8.1 [Test Infrastructure](#81-test-infrastructure)
   - 8.2 [Test Database Setup](#82-test-database-setup)
   - 8.3 [Raw SQL in Tests](#83-raw-sql-in-tests)

---

## 1. Backend Code Patterns

### 1.1 Base Model and Mixins

The `Base` class lives in `backend/app/models/base.py` and provides three things to every model: a UUID primary key (`id`), a `created_at` timestamp, and an `updated_at` timestamp. Table names are derived automatically from the class name by converting CamelCase to snake_case. Two additional mixins exist for multi-tenancy and soft deletion.

```python
# backend/app/models/base.py  (actual implementation)

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base model class for all SIMS Plus models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name (CamelCase -> snake_case)."""
        name = cls.__name__
        return "".join(
            ["_" + c.lower() if c.isupper() else c for c in name]
        ).lstrip("_")

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class TenantMixin:
    """Adds tenant_id to any model for multi-tenant scoping."""
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Adds soft delete support. Use for entity tables, NOT junction tables."""
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None


class AuditMixin:
    """Tracks who created and updated the record."""
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
```

**Key rules for mixins:**

| Mixin | When to use | What it adds |
|-------|-------------|--------------|
| `TenantMixin` | Every table that stores tenant-specific data | `tenant_id UUID NOT NULL` with index |
| `SoftDeleteMixin` | Entity tables (students, invoices, etc.) | `deleted_at` timestamp, `is_deleted` property |
| `AuditMixin` | Tables where you need to track who made changes | `created_by`, `updated_by` UUID fields |

**When NOT to use SoftDeleteMixin:** Junction/association tables (e.g., `student_guardians`, `class_subjects`). These use hard delete because they are links, not standalone entities.

### 1.2 Model Definition Pattern

Every tenant-scoped model follows this structure. The example below is annotated with the rules that MUST be followed.

```python
# backend/app/models/{module}.py

import uuid
from enum import Enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

# Use TYPE_CHECKING to avoid circular imports for relationship type hints
if TYPE_CHECKING:
    from app.models.school import School


class ExampleStatus(str, Enum):
    """Python name: UPPERCASE, DB value: lowercase (for all Sprint 3+ enums)."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Example(Base, TenantMixin, SoftDeleteMixin):
    """
    Example tenant-scoped model.

    Inheritance order: Base, TenantMixin, SoftDeleteMixin
    """
    __tablename__ = "examples"
    __table_args__ = (
        # Unique constraints MUST include tenant_id for multi-tenant isolation
        UniqueConstraint("tenant_id", "code", name="uq_example_code"),
    )

    # Foreign keys
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Data columns
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Unique code within tenant",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Enum column - CRITICAL: use values_callable
    status: Mapped[ExampleStatus] = mapped_column(
        SQLEnum(
            ExampleStatus,
            name="examplestatus",  # lowercase, no underscores
            values_callable=lambda x: [e.value for e in x],  # REQUIRED
        ),
        default=ExampleStatus.ACTIVE,
        nullable=False,
    )

    # Decimal columns use Numeric(12, 2) for financial amounts
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
    )

    # Boolean flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # JSONB for flexible structured data
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships - relationship loading strategy matters
    school: Mapped["School"] = relationship("School", lazy="joined")
    # Use lazy="raise" to prevent accidental N+1 queries
    # Use lazy="joined" when the related object is always needed
    # Use lazy="selectin" for collections that are typically loaded together
```

**Critical model rules:**

1. `values_callable=lambda x: [e.value for e in x]` is **MANDATORY** on all `SQLEnum` columns. Without it, SQLAlchemy sends Python enum names (UPPERCASE) instead of values (lowercase) to the database.
2. Unique constraints on tenant-scoped tables **MUST** include `tenant_id`. A constraint like `UNIQUE(code)` would leak data across tenants. Always use `UNIQUE(tenant_id, code)`.
3. The `__tablename__` can be set explicitly or omitted to use auto-generation from `Base`. When explicit, it must be a snake_case plural (e.g., `"fee_structures"`).
4. `ondelete="CASCADE"` vs `ondelete="SET NULL"`: Use CASCADE for child records that should be deleted with the parent. Use SET NULL for references that should survive parent deletion.
5. **NEVER** use `from __future__ import annotations` in endpoint files. This causes `AssertionError: Status code 204 must not have a response body` because FastAPI cannot resolve the return type at runtime.

### 1.3 Enum Definition Rules

Enums have a split casing convention for historical reasons. New enums must follow the lowercase value pattern.

| DB Enum Type Name | Values Stored in DB | Origin | Rule |
|-------------------|---------------------|--------|------|
| `userrole` | UPPERCASE (`TEACHER`, `SCHOOL_ADMIN`) | Sprint 1 | Do not change |
| `userstatus` | UPPERCASE (`ACTIVE`, `SUSPENDED`) | Sprint 1 | Do not change |
| `tenanttype` | lowercase via values_callable (`single_school`) | Sprint 1 | Do not change |
| `subscriptiontier` | lowercase via values_callable (`trial`, `starter`) | Sprint 1 | Do not change |
| `schooltype` | lowercase (`basic`, `shs`) | Sprint 2 | Do not change |
| `schoolstatus` | lowercase (`active`, `suspended`) | Sprint 2 | Do not change |
| **All Sprint 3+ enums** | lowercase | Sprint 3+ | `values_callable=lambda x: [e.value for e in x]` |

**Pattern for new enums:**

```python
class NewEnumExample(str, Enum):
    """Python names: UPPERCASE. DB values: lowercase."""
    FIRST_VALUE = "first_value"
    SECOND_VALUE = "second_value"

# On the column:
column: Mapped[NewEnumExample] = mapped_column(
    SQLEnum(
        NewEnumExample,
        name="newenumexample",  # lowercase, no underscores between words
        values_callable=lambda x: [e.value for e in x],
    ),
    nullable=False,
)
```

The DB enum type name (`name=` parameter) uses the convention: lowercase Python class name with no separators. So `InvoiceStatus` becomes `"invoicestatus"`, `PaymentMethod` becomes `"paymentmethod"`.

### 1.4 Service Layer Pattern

Services live in `backend/app/services/` and encapsulate all business logic. They follow a class-based pattern with a custom error type.

```python
# backend/app/services/{module}.py

from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.example import Example, ExampleStatus


class ExampleServiceError(Exception):
    """Custom error for Example service."""
    def __init__(self, message: str, code: str = "example_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ExampleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------
    # READ: Always filter by tenant_id AND deleted_at
    # ---------------------------------------------------

    async def get_by_id(
        self, example_id: UUID, tenant_id: UUID
    ) -> Optional[Example]:
        """Get example by ID with explicit tenant filter."""
        result = await self.db.execute(
            select(Example).where(
                Example.id == example_id,
                Example.tenant_id == tenant_id,   # DEFENSE-IN-DEPTH
                Example.deleted_at.is_(None),      # EXCLUDE SOFT-DELETED
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Example], int]:
        """List with pagination, search, and tenant filter."""
        query = select(Example).where(
            Example.tenant_id == tenant_id,
            Example.deleted_at.is_(None),
        )

        # Search - sanitize ILIKE input to prevent wildcard injection
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Example.name.ilike(search_term),
                    Example.code.ilike(search_term),
                )
            )

        # Filters
        if status:
            query = query.where(Example.status == status)

        # Count (before pagination)
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.offset(skip).limit(limit).order_by(
            Example.created_at.desc()
        )
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    # ---------------------------------------------------
    # CREATE: Always set tenant_id explicitly
    # ---------------------------------------------------

    async def create(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        code: str,
        **kwargs,
    ) -> Example:
        """Create with explicit tenant_id assignment."""
        # Check uniqueness within tenant
        existing = await self.db.execute(
            select(Example).where(
                Example.tenant_id == tenant_id,
                Example.code == code,
                Example.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ExampleServiceError(
                f"Code '{code}' already exists",
                code="duplicate_code",
            )

        example = Example(
            tenant_id=tenant_id,    # ALWAYS set explicitly
            school_id=school_id,
            name=name,
            code=code,
            **kwargs,
        )
        self.db.add(example)
        await self.db.flush()       # NOT commit()
        await self.db.refresh(example)
        return example

    # ---------------------------------------------------
    # UPDATE: Verify ownership via tenant_id
    # ---------------------------------------------------

    async def update(
        self,
        example_id: UUID,
        tenant_id: UUID,
        **data,
    ) -> Example:
        """Update with IDOR prevention."""
        example = await self.get_by_id(example_id, tenant_id)
        if not example:
            raise ExampleServiceError("Example not found", "not_found")

        for key, value in data.items():
            if value is not None:
                setattr(example, key, value)

        await self.db.flush()
        await self.db.refresh(example)
        return example

    # ---------------------------------------------------
    # DELETE: Soft delete with tenant verification
    # ---------------------------------------------------

    async def soft_delete(self, example_id: UUID, tenant_id: UUID) -> None:
        """Soft delete with tenant verification."""
        example = await self.get_by_id(example_id, tenant_id)
        if not example:
            raise ExampleServiceError("Example not found", "not_found")

        example.deleted_at = datetime.now(UTC)
        await self.db.flush()
```

**Service layer rules (MUST follow):**

| Rule | Reason |
|------|--------|
| Every query MUST include `.where(Model.tenant_id == tenant_id)` | Defense-in-depth; do not rely solely on RLS |
| Every query MUST include `.where(Model.deleted_at.is_(None))` | Exclude soft-deleted records |
| Every insert MUST set `tenant_id=tenant_id` explicitly | Prevent accidental cross-tenant data creation |
| Use `flush()` / `refresh()`, NEVER `commit()` | The `get_db()` dependency handles commit/rollback |
| ILIKE searches SHOULD sanitize `%` and `_` in user input | Prevent wildcard injection (see note below) |
| IDOR prevention: verify child belongs to parent | When URL has nested IDs like `/classes/{class_id}/sections/{section_id}` |
| Race conditions: use `pg_advisory_xact_lock` for sequential ID generation | Prevents duplicate IDs under concurrent requests |
| Race conditions: use `.with_for_update()` for count-dependent operations | Prevents stale count reads |
| Custom errors: `ServiceError(message, code)` pattern | Allows endpoints to map error codes to HTTP status codes |

**Note on ILIKE sanitization:** The current codebase uses raw `f"%{search}%"` in some services. When an `escape_ilike()` utility is added to `app/utils/sanitize.py`, all ILIKE searches should be updated to use it. The utility should escape `%`, `_`, and `\` characters in user input.

### 1.5 Endpoint Pattern

Endpoints live in `backend/app/api/v1/endpoints/` and are thin wrappers around service methods. They handle HTTP concerns (status codes, error mapping) and delegate business logic to services.

```python
# backend/app/api/v1/endpoints/{module}.py

# CRITICAL: NEVER add this line - it breaks 204 responses!
# from __future__ import annotations

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DatabaseSession, ValidatedUser, require_permissions
from app.schemas.example import (
    ExampleCreate, ExampleUpdate,
    ExampleResponse, ExampleListResponse,
)
from app.services.example import ExampleService, ExampleServiceError

router = APIRouter(prefix="/examples", tags=["Examples"])


@router.get("", response_model=ExampleListResponse)
async def list_examples(
    db: DatabaseSession,
    user: ValidatedUser,
    search: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """List examples for current tenant."""
    service = ExampleService(db)
    items, total = await service.list_all(
        tenant_id=UUID(user["tenant_id"]),
        search=search,
        status=status,
        skip=skip,
        limit=limit,
    )
    return ExampleListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{example_id}", response_model=ExampleResponse)
async def get_example(
    example_id: UUID,
    db: DatabaseSession,
    user: ValidatedUser,
):
    """Get example by ID."""
    service = ExampleService(db)
    example = await service.get_by_id(example_id, UUID(user["tenant_id"]))
    if not example:
        raise HTTPException(status_code=404, detail="Example not found")
    return example


@router.post(
    "",
    response_model=ExampleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_example(
    data: ExampleCreate,
    db: DatabaseSession,
    user: ValidatedUser,
):
    """Create new example."""
    try:
        service = ExampleService(db)
        return await service.create(
            tenant_id=UUID(user["tenant_id"]),
            **data.model_dump(),
        )
    except ExampleServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.put("/{example_id}", response_model=ExampleResponse)
async def update_example(
    example_id: UUID,
    data: ExampleUpdate,
    db: DatabaseSession,
    user: ValidatedUser,
):
    """Update example."""
    try:
        service = ExampleService(db)
        return await service.update(
            example_id=example_id,
            tenant_id=UUID(user["tenant_id"]),
            **data.model_dump(exclude_unset=True),
        )
    except ExampleServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=404, detail=e.message)
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_example(
    example_id: UUID,
    db: DatabaseSession,
    user: ValidatedUser,
):
    """Soft delete example."""
    try:
        service = ExampleService(db)
        await service.soft_delete(example_id, UUID(user["tenant_id"]))
    except ExampleServiceError as e:
        raise HTTPException(status_code=404, detail=e.message)
    # Return nothing for 204 - do NOT return a response body


# Example with permission checking:
@router.post(
    "/admin-action",
    dependencies=[require_permissions("examples.admin")],
)
async def admin_action(
    db: DatabaseSession,
    user: ValidatedUser,
):
    """Endpoint that requires specific permission."""
    pass
```

**Endpoint rules:**

1. The `ValidatedUser` dependency performs full JWT validation including token type check, blacklist check, mass revocation check, and cross-tenant validation. Use it for ALL protected endpoints.
2. `data.model_dump(exclude_unset=True)` for update operations -- this ensures only provided fields are updated (not setting None on omitted fields).
3. Error code to HTTP status mapping: `"not_found"` -> 404, everything else -> 400.
4. The 204 response for DELETE must have NO response body. The `from __future__ import annotations` import would break this.
5. Use `require_permissions()` as a dependency when RBAC is needed beyond just authentication.

### 1.6 Pydantic Schema Pattern

Schemas live in `backend/app/schemas/` and define request/response shapes.

```python
# backend/app/schemas/{module}.py

from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# ----- Request Schemas -----

class ExampleCreate(BaseModel):
    """Request schema for creating. Required fields only."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=20)
    school_id: UUID
    description: Optional[str] = None
    amount: Decimal = Field(default=Decimal("0.00"), ge=0)


class ExampleUpdate(BaseModel):
    """Request schema for updating. ALL fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)


# ----- Response Schemas -----

class ExampleResponse(BaseModel):
    """Response schema. Uses from_attributes for ORM model conversion."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    status: str
    amount: Decimal
    school_id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExampleListResponse(BaseModel):
    """Paginated list response."""
    items: list[ExampleResponse]
    total: int
    skip: int
    limit: int
```

**Schema rules:**

1. `model_config = ConfigDict(from_attributes=True)` is required on response schemas so Pydantic can read from SQLAlchemy model attributes.
2. Create schemas: required fields use `...` (Ellipsis), optional fields use `None` default.
3. Update schemas: ALL fields are `Optional` with `None` default. The endpoint uses `model_dump(exclude_unset=True)` to only update provided fields.
4. Sensitive operations (e.g., status changes, cancellations) get dedicated endpoints with their own schemas, NOT fields on the Update schema.
5. Enum fields in responses are typed as `str` (not the enum class) because the serialized value is a string.

### 1.7 Dependency Injection Reference

All dependencies are defined in `backend/app/api/deps.py`. Here is the complete reference for available dependencies.

```python
# backend/app/api/deps.py -- Available dependencies

# ===== Database Sessions =====

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
# Tenant-scoped session. Sets tenant context for RLS on every request.
# Raises HTTP 400 if no tenant context is available for non-public routes.
# Auto-commits on success, rolls back on exception.

# (No UnscopedDatabaseSession in deps.py -- use raw session maker for
#  unscoped queries like tenant lookup in middleware.)

# ===== Authentication =====

CurrentUserId = Annotated[str, Depends(get_current_user_id)]
# Decodes JWT, checks blacklist, checks mass revocation.
# Returns user ID string from token "sub" claim.
# Does NOT validate cross-tenant.

ValidatedUser = Annotated[dict, Depends(get_validated_current_user)]
# RECOMMENDED for all protected endpoints. Performs ALL checks:
#   1. Decode JWT
#   2. Verify token type is "access"
#   3. Check individual token blacklist (Redis)
#   4. Check user-level mass token revocation (Redis)
#   5. Cross-tenant validation (token.tenant_id == request.state.tenant_id)
# Returns dict: { user_id, tenant_id, school_id, role, permissions, email }

ValidatedTokenTenant = Annotated[None, Depends(validate_token_tenant)]
# Lightweight cross-tenant check only.
# Does NOT check blacklist or mass revocation.
# Returns None (used as side-effect dependency).

CurrentTenantId = Annotated[str, Depends(get_current_tenant_id)]
# Extracts tenant_id from JWT. No blacklist or cross-tenant check.

RequestTenant = Annotated[TenantContext, Depends(get_tenant_from_request)]
# Gets tenant context from request.state (set by TenantMiddleware).
# Returns TenantContext object with: tenant_id, subdomain, name, is_active.

# ===== Permission Checking =====

def require_permissions(*required_permissions: str):
    """
    Factory that returns a dependency checking user has required permissions.

    Usage:
        @router.get("/admin", dependencies=[require_permissions("users.*")])
        async def admin_endpoint(): ...

    Permission matching rules:
    - "*" in user permissions = all access (platform_admin)
    - "users.*" matches "users.read", "users.create", etc.
    - Exact match: "students.read" matches "students.read"
    """
```

**Choosing the right dependency:**

| Scenario | Dependency | Why |
|----------|-----------|------|
| Protected endpoint (most common) | `ValidatedUser` | Full auth + cross-tenant + returns user claims |
| Need user ID only | `CurrentUserId` | Lighter but no cross-tenant check |
| Need tenant info from middleware | `RequestTenant` | For endpoints that need tenant metadata |
| Permission-gated endpoint | `require_permissions(...)` | RBAC on top of ValidatedUser |

---

## 2. Database Patterns

### 2.1 Row-Level Security Policy Template

Every new tenant-scoped table MUST have RLS enabled. Use this exact template.

```sql
-- Step 1: Enable RLS (row-level security)
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

-- Step 2: Force RLS even for table owner
ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;

-- Step 3: Create isolation policy
CREATE POLICY tenant_isolation_{table_name} ON {table_name}
    FOR ALL
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

-- Step 4: Grant permissions to application user
GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user;
```

**SECURITY RULES -- violations of these rules are P0 bugs:**

| Rule | Rationale |
|------|-----------|
| NO `OR (get_current_tenant_id() IS NULL)` clause | This allows bypass when no tenant context is set |
| NO `is_platform_admin` bypass in RLS policies | Use superuser connection for admin operations instead |
| ALWAYS use `FORCE ROW LEVEL SECURITY` | Without FORCE, the table owner bypasses RLS |
| The `get_current_tenant_id()` function returns NULL when no context is set | In SQL, `tenant_id = NULL` evaluates to `FALSE` (three-valued logic), so zero rows are returned. This is safe. |

### 2.2 Tenant Context Functions

These SQL functions are used by the application to set and clear tenant context for RLS.

```sql
-- Called by get_db() dependency on every request
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false);
END;
$$ LANGUAGE plpgsql;

-- Called in get_db() finally block after each request
CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', false);
END;
$$ LANGUAGE plpgsql;

-- Used in ALL RLS policies (the core of tenant isolation)
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
DECLARE
    tenant_str TEXT;
    tenant_uuid UUID;
BEGIN
    tenant_str := current_setting('app.current_tenant_id', true);
    IF tenant_str IS NULL OR tenant_str = '' THEN
        RETURN NULL;  -- Safe: tenant_id = NULL evaluates to FALSE in RLS
    END IF;
    BEGIN
        tenant_uuid := tenant_str::UUID;
        RETURN tenant_uuid;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;  -- Invalid UUID format = no access
    END;
END;
$$ LANGUAGE plpgsql STABLE;
```

**How tenant context flows through a request:**

```
1. Browser hits presec.simsplus.io/api/v1/students
2. TenantMiddleware extracts "presec" from host
3. TenantMiddleware queries: SELECT * FROM tenants WHERE subdomain = 'presec'
4. TenantMiddleware sets request.state.tenant_id = <uuid>
5. get_db() dependency creates DB session
6. get_db() calls: SELECT set_tenant_context('<uuid>')
7. PostgreSQL stores tenant UUID in session variable
8. All subsequent queries are auto-filtered by RLS policies
9. get_db() calls commit() on success, rollback() on error
10. get_db() finally block calls: SELECT clear_tenant_context()
```

### 2.3 Index Templates

```sql
-- Every tenant-scoped table needs at minimum a tenant_id index:
CREATE INDEX ix_{table}_tenant_id ON {table} (tenant_id);

-- For active records queries (most common query pattern):
CREATE INDEX ix_{table}_tenant_active ON {table} (tenant_id)
    WHERE deleted_at IS NULL;

-- Composite indexes for common query patterns:
CREATE INDEX ix_{table}_tenant_status ON {table} (tenant_id, status)
    WHERE deleted_at IS NULL;

-- Unique constraints MUST include tenant_id:
--   WRONG: UNIQUE(student_id_number)
--   RIGHT: UNIQUE(tenant_id, student_id_number) WHERE deleted_at IS NULL
--
-- Note: Partial unique indexes (with WHERE) are not directly supported
-- by UniqueConstraint in SQLAlchemy. Use raw SQL in migrations for these.
```

### 2.4 Migration Template

All migrations live in `backend/alembic/versions/`. Use this template for new tables.

```python
"""Add {table_name} table

Revision ID: {auto_generated}
Revises: {parent_revision}
Create Date: {auto_generated}
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import text


# Helper function: copy into every migration that creates tenant-scoped tables
def enable_rls_for_table(connection, table_name: str) -> None:
    """Enable RLS with standard isolation policy."""
    # Drop existing policies (idempotent)
    connection.execute(text(f"""
        DO $$ BEGIN
            EXECUTE (
                SELECT COALESCE(
                    string_agg(
                        'DROP POLICY IF EXISTS ' || policyname || ' ON {table_name};',
                        E'\\n'
                    ),
                    ''
                )
                FROM pg_policies WHERE tablename = '{table_name}'
            );
        EXCEPTION WHEN OTHERS THEN NULL; END $$;
    """))
    connection.execute(text(
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
    ))
    connection.execute(text(
        f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"
    ))
    connection.execute(text(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
        FOR ALL
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """))
    connection.execute(text(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
    ))


def upgrade() -> None:
    # Create the table
    op.create_table(
        '{table_name}',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('school_id', UUID(as_uuid=True),
                  sa.ForeignKey('schools.id', ondelete='CASCADE'),
                  nullable=False),
        # ... other columns ...
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes
    op.create_index('ix_{table_name}_tenant_id', '{table_name}', ['tenant_id'])
    op.create_index(
        'ix_{table_name}_tenant_active', '{table_name}', ['tenant_id'],
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    # RLS (MUST be last step)
    enable_rls_for_table(op.get_bind(), '{table_name}')


def downgrade() -> None:
    op.drop_table('{table_name}')
```

**Migration naming convention:** `YYYYMMDD_HHMM_{description}.py`

Examples from the codebase:
- `20260120_0100_add_finance_tables.py`
- `20260122_0300_add_credit_notes.py`
- `20260125_0100_add_scholarship_invoice_improvements.py`

### 2.5 Table Classification

| Table | Tenant-Scoped? | RLS? | Soft Delete? | Notes |
|-------|:-:|:-:|:-:|-------|
| `tenants` | No | No | Yes | Global registry; no `tenant_id` column |
| `reserved_subdomains` | No | No | No | Platform configuration |
| `audit_logs` | No | No | No (immutable) | Has nullable `tenant_id` for filtering only |
| `schools` | Yes | Yes | Yes | One or more per tenant |
| `users` | Yes | Yes | Yes | User accounts |
| `students` | Yes | Yes | Yes | Student profiles |
| `guardians` | Yes | Yes | Yes | Parent/guardian info |
| `student_guardians` | Yes | Yes | **No** (junction) | Hard delete; links students to guardians |
| `academic_years` | Yes | Yes | Yes | Academic year definitions |
| `terms` | Yes | Yes | Yes | Term/semester within years |
| `classes` | Yes | Yes | Yes | Grade levels |
| `class_sections` | Yes | Yes | Yes | Sections within classes |
| `subjects` | Yes | Yes | Yes | Subject catalog |
| `class_subjects` | Yes | Yes | **No** (junction) | Hard delete; links subjects to classes |
| `grading_scales` | Yes | Yes | Yes | Grading system definitions |
| `grades` | Yes | Yes | **No** (junction-like) | Hard delete; grade entries within scales |
| `assessment_weights` | Yes | Yes | No | One per tenant per academic year |
| `academic_settings` | Yes | Yes | No | One per tenant |
| `school_periods` | Yes | Yes | No | Period templates |
| `school_holidays` | Yes | Yes | No | Calendar events |
| `class_timetables` | Yes | Yes | No | Weekly schedule entries |
| `staff` | Yes | Yes | Yes | Staff profiles |
| `departments` | Yes | Yes | Yes | Staff departments |
| `student_attendance` | Yes | Yes | No | Daily attendance records |
| `staff_attendance` | Yes | Yes | No | Staff attendance records |
| `exams` | Yes | Yes | Yes | Exam definitions |
| `exam_subjects` | Yes | Yes | Yes | Subjects in exams |
| `exam_scores` | Yes | Yes | No | Student scores |
| `continuous_assessments` | Yes | Yes | No | CA scores |
| `term_reports` | Yes | Yes | No | Generated report cards |
| `fee_types` | Yes | Yes | No | Fee categories |
| `fee_structures` | Yes | Yes | Yes | Fee templates |
| `fee_items` | Yes | Yes | No | Line items within structures |
| `invoices` | Yes | Yes | Yes | Student invoices |
| `invoice_items` | Yes | Yes | No | Invoice line items |
| `invoice_scholarship_items` | Yes | Yes | No | Scholarship discount tracking |
| `payments` | Yes | Yes | No | Payment records |
| `scholarships` | Yes | Yes | Yes | Scholarship programs |
| `student_scholarships` | Yes | Yes | No | Awards to students |
| `scholarship_applications` | Yes | Yes | No | Student applications |
| `credit_notes` | Yes | Yes | Yes | Credit notes |
| `finance_audit_log` | Yes | Yes | No (immutable) | Finance audit trail |
| Preschool tables | Yes | Yes | Varies | See preschool module |

### 2.6 Enum Casing Rules

This is CRITICAL for anyone writing raw SQL in tests or migrations. The values stored in the database differ based on when the enum was created.

```sql
-- Sprint 1-2 enums that store UPPERCASE values:
INSERT INTO users (role, status, ...) VALUES ('TEACHER', 'ACTIVE', ...);

-- Sprint 1-2 enums that store lowercase values (via values_callable):
INSERT INTO tenants (tenant_type, ...) VALUES ('single_school', ...);
INSERT INTO schools (school_type, school_status, ...) VALUES ('basic', 'active', ...);

-- Sprint 3+ enums always store lowercase values (via values_callable):
INSERT INTO academic_years (status, ...) VALUES ('planning', ...);
INSERT INTO invoices (status, ...) VALUES ('draft', ...);
INSERT INTO payments (payment_method, ...) VALUES ('momo_mtn', ...);
```

**Rule of thumb:** If you are writing raw SQL and are unsure about the casing, check the enum definition in the model file. If it has `values_callable=lambda x: [e.value for e in x]`, the DB values are the Python `.value` (lowercase). If there is no `values_callable`, the DB values are the Python `.name` (UPPERCASE).

---

## 3. Authentication System

### 3.1 JWT Token Structure

**Access Token (15-minute expiry):**

```json
{
  "sub": "user-uuid-string",
  "tenant_id": "tenant-uuid-string",
  "tenant_subdomain": "presec",
  "school_id": "school-uuid-string",
  "role": "school_admin",
  "permissions": ["school.read", "school.update", "users.*", "students.*"],
  "email": "admin@presec.edu.gh",
  "type": "access",
  "iat": 1739577600,
  "exp": 1739578500
}
```

**Refresh Token (7-day expiry):**

```json
{
  "sub": "user-uuid-string",
  "tenant_id": "tenant-uuid-string",
  "type": "refresh",
  "iat": 1739577600,
  "exp": 1740182400
}
```

**Key implementation details:**

- Algorithm: HS256
- Library: `python-jose` (via `jose.jwt`)
- Secret key: `settings.SECRET_KEY` (must be 64+ characters in production)
- Access tokens carry full user claims (role, permissions, tenant info)
- Refresh tokens carry minimal claims (user ID, tenant ID, type)
- The `type` claim is checked to prevent refresh tokens from being used as access tokens

### 3.2 Password Hashing

Passwords are hashed using Argon2id via the `argon2-cffi` library. The implementation lives in `backend/app/core/security.py`.

```python
from argon2 import PasswordHasher

password_hasher = PasswordHasher(
    time_cost=2,        # Number of iterations
    memory_cost=65536,  # 64 MB
    parallelism=1,      # Single-threaded
)

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_hasher.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False
```

**Why Argon2id over bcrypt:** Argon2id is resistant to both side-channel attacks (argon2i property) and GPU/ASIC attacks (argon2d property). It is the recommended algorithm per OWASP 2024 guidelines.

### 3.3 Password Policy

All passwords must meet these requirements:

| Requirement | Validation |
|-------------|-----------|
| Minimum length | 8 characters |
| Uppercase letter | At least 1 |
| Lowercase letter | At least 1 |
| Digit | At least 1 |
| Special character | At least 1 from: ``!@#$%^&*()_+-=[]{}|;:,.<>?`` |

### 3.4 Account Lockout

| Parameter | Value |
|-----------|-------|
| Max failed attempts | 5 |
| Lockout duration | 30 minutes |
| DB fields | `failed_login_attempts` (int), `locked_until` (datetime) |
| Reset trigger | Successful login resets counter to 0 |

### 3.5 Token Blacklisting

Token blacklisting is Redis-based and serves two purposes: individual token revocation (logout) and mass revocation (password change, account suspension).

| Key Pattern | Value | TTL | Trigger |
|-------------|-------|-----|---------|
| `token_blacklist:{sha256(token)}` | `"1"` | Token remaining TTL + 60s | User logout |
| `user_token_blacklist:{user_id}` | Unix timestamp | 7 days | Password change, suspension |

**How mass revocation works:** When a user changes their password, the current Unix timestamp is stored in Redis under `user_token_blacklist:{user_id}`. Every subsequent token validation checks if the token's `iat` (issued-at) is before this timestamp. If so, the token is rejected.

### 3.6 Cross-Tenant Token Rejection

The `get_validated_current_user` dependency (aliased as `ValidatedUser`) performs cross-tenant validation:

```
1. Decode JWT token
2. Extract token.tenant_id
3. Read request.state.tenant_id (set by TenantMiddleware from subdomain)
4. Compare: str(token.tenant_id) == str(request.state.tenant_id)
5. If mismatch: HTTP 403 "Token not valid for this school. Please login again."
```

This prevents a user logged into `presec.simsplus.io` from using their token on `achimota.simsplus.io`.

### 3.7 Role-Permission Mapping

This is the actual mapping from `backend/app/services/auth.py`:

```python
ROLE_PERMISSIONS = {
    "platform_admin": ["*"],
    "chain_admin": [
        "schools.*", "users.*", "students.*", "staff.*",
        "academics.*", "subjects.*", "grading.*",
        "finance.*", "reports.*",
    ],
    "school_admin": [
        "school.read", "school.update",
        "users.*", "students.*", "staff.*",
        "classes.*", "academics.*", "subjects.*", "grading.*",
        "attendance.*", "exams.*", "finance.*", "reports.*",
    ],
    "academic_head": [
        "students.read", "students.update",
        "classes.*", "academics.*", "subjects.*", "grading.*",
        "attendance.*", "exams.*", "reports.academic",
    ],
    "finance_officer": [
        "students.read", "finance.*", "reports.financial",
    ],
    "teacher": [
        "students.read", "classes.read", "subjects.read",
        "grading.read", "attendance.mark", "exams.scores",
    ],
    "house_parent": [
        "students.read", "boarding.*",
    ],
    "parent": [
        "children.read", "finance.invoices.read",
    ],
    "student": [
        "self.read",
    ],
}
```

**Permission matching logic:**
- `"*"` = all permissions (platform_admin only)
- `"users.*"` matches any permission starting with `"users."` (e.g., `"users.read"`, `"users.create"`)
- Exact string match for specific permissions (e.g., `"attendance.mark"`)

---

## 4. API Contracts

### 4.1 Authentication Endpoints

**POST `/api/v1/auth/login`**

| Property | Value |
|----------|-------|
| Auth | None (public) |
| Rate Limit | Auth tier (configurable, default 30/min dev, 5/min prod) |
| Content-Type | application/json |

Request:
```json
{
  "email": "admin@presec.edu.gh",
  "password": "SecureP@ss1"
}
```

Response (200):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "admin@presec.edu.gh",
    "first_name": "Kwame",
    "last_name": "Asante",
    "role": "school_admin",
    "school_id": "uuid"
  }
}
```

Error responses:
| Status | Condition |
|--------|-----------|
| 400 | No tenant context (not accessed via subdomain) |
| 401 | Invalid credentials |
| 401 | Account locked (5+ failed attempts) |
| 401 | Email not verified |
| 401 | Account suspended |
| 429 | Rate limit exceeded |

---

**POST `/api/v1/auth/refresh`**

| Property | Value |
|----------|-------|
| Auth | None (refresh token is the credential) |
| Rate Limit | Auth tier |

Request:
```json
{
  "refresh_token": "eyJ..."
}
```

Response (200):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

Error responses: 400 (no tenant), 401 (invalid/expired/tenant mismatch)

---

**POST `/api/v1/auth/logout`**

| Property | Value |
|----------|-------|
| Auth | Bearer token |
| Response | 204 No Content |

---

**GET `/api/v1/auth/me`**

| Property | Value |
|----------|-------|
| Auth | Bearer token + cross-tenant validation |
| Response | 200 with user details, tenant info, permissions |

### 4.2 Tenant Endpoints

**GET `/api/v1/tenant/validate/{subdomain}`**

| Property | Value |
|----------|-------|
| Auth | None (public) |
| Rate Limit | Subdomain tier (20/min) |

Response (200):
```json
{
  "valid": true,
  "tenant": {
    "id": "uuid",
    "name": "Presbyterian Boys' Secondary School",
    "subdomain": "presec",
    "branding": {
      "logo_url": "https://...",
      "primary_color": "#1B4F72"
    }
  }
}
```

---

**GET `/api/v1/tenant/check-subdomain?subdomain=presec`**

| Property | Value |
|----------|-------|
| Auth | None (public) |
| Rate Limit | Subdomain tier (20/min) |

Response (200):
```json
{
  "subdomain": "presec",
  "available": false,
  "reason": "Already registered"
}
```

### 4.3 Onboarding Endpoints

**POST `/api/v1/onboarding/register`**

| Property | Value |
|----------|-------|
| Auth | None (public) |
| Rate Limit | Auth tier |

Request:
```json
{
  "school_name": "Presbyterian Boys' Secondary School",
  "subdomain": "presec",
  "school_type": "shs",
  "admin_email": "admin@presec.edu.gh",
  "admin_first_name": "Kwame",
  "admin_last_name": "Asante",
  "admin_password": "SecureP@ss1",
  "admin_phone": "+233244123456",
  "plan": "trial"
}
```

Response (201):
```json
{
  "success": true,
  "message": "School registered successfully!",
  "tenant_id": "uuid",
  "school_id": "uuid",
  "admin_user_id": "uuid",
  "subdomain": "presec",
  "portal_url": "https://presec.simsplus.io",
  "admin_email": "admin@presec.edu.gh",
  "trial_ends_at": "2026-03-15T10:00:00Z"
}
```

Error responses: 400 (subdomain taken, email exists, invalid format), 422 (Pydantic validation failure)

---

**GET `/api/v1/onboarding/suggest-subdomain?school_name=Achimota+School&count=3`**

Response (200):
```json
{
  "school_name": "Achimota School",
  "suggestions": ["achimotaschool", "achimotaschoolgh", "achimotaschool1"]
}
```

### 4.4 Standard Response Patterns

| Operation | HTTP Status | Response Body |
|-----------|-------------|---------------|
| Get single item | 200 | Object directly |
| List items | 200 | `{ "items": [...], "total": 100, "skip": 0, "limit": 50 }` |
| Create item | 201 | Created object |
| Update item | 200 | Updated object |
| Delete item (soft) | 204 | No body |
| Validation error | 422 | `{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }` |
| Business logic error | 400 | `{ "detail": "Human-readable error message" }` |
| Not found | 404 | `{ "detail": "Resource not found" }` |
| Unauthorized | 401 | `{ "detail": "Could not validate credentials" }` |
| Forbidden | 403 | `{ "detail": "Token not valid for this school" }` |
| Rate limited | 429 | `{ "detail": "Rate limit exceeded", "retry_after": 30 }` |

### 4.5 Rate Limits

Rate limiting uses a Redis sliding window algorithm. Limits are per-client (identified by user ID if authenticated, or tenant+IP, or IP alone).

| Endpoint Type | Default (dev) | Production Target | Window |
|--------------|:--:|:--:|:--:|
| Authentication (`/auth/login`, `/auth/refresh`) | 30 req | 5 req | 60 sec |
| Subdomain check (`/tenant/check-subdomain`, `/tenant/validate`) | 20 req | 20 req | 60 sec |
| General API | 500 req | 100 req | 60 sec |
| Bulk Operations | -- | 10 req | 60 sec |
| Report Generation | -- | 5 req | 60 sec |
| File Upload | -- | 20 req | 60 sec |

Rate limit headers are included in every response:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 97
X-RateLimit-Reset: 1739578560
```

When rate limited, the response also includes:
```
Retry-After: 30
```

### 4.6 Error Response Format

All errors return a JSON body with a `detail` field. FastAPI validation errors return an array:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

Business logic errors return a simple string:

```json
{
  "detail": "Student ID 'STU-2026-001' already exists"
}
```

The frontend `apiFetch` function handles both formats and converts them to a single error message string.

---

## 5. Frontend Patterns

### 5.1 API Client

The API client lives in `frontend/lib/api.ts` and provides typed wrapper functions for all HTTP methods. It runs server-side only (used by Server Actions).

```typescript
// frontend/lib/api.ts

const API_BASE_URL = process.env.API_URL || "http://localhost:8000/api/v1";

interface ApiOptions {
  token?: string;     // JWT access token for Authorization header
  subdomain?: string; // X-Subdomain header for tenant context
}

// Available functions:
export async function apiGet<T>(endpoint: string, options?: ApiOptions): Promise<T>
export async function apiPost<T>(endpoint: string, data: unknown, options?: ApiOptions): Promise<T>
export async function apiPut<T>(endpoint: string, data: unknown, options?: ApiOptions): Promise<T>
export async function apiPatch<T>(endpoint: string, data: unknown, options?: ApiOptions): Promise<T>
export async function apiDelete<T>(endpoint: string, options?: ApiOptions): Promise<T>
export async function apiUpload<T>(endpoint: string, formData: FormData, options?: ApiOptions): Promise<T>
```

**Key behaviors:**
- All requests set `cache: "no-store"` to disable Next.js fetch caching
- `Content-Type: application/json` is set automatically (except for `apiUpload`)
- 204 responses return `undefined` (not parsed as JSON)
- Error responses are parsed and thrown as `Error` with the detail message
- FastAPI validation error arrays are flattened into a comma-separated string

### 5.2 Server Action Pattern

Server Actions live in `frontend/actions/` and follow the `{module}.action.ts` naming convention. They are the primary way the frontend communicates with the backend.

```typescript
// frontend/actions/{module}.action.ts
"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult, Example, ExampleCreate } from "@/types";

/**
 * Get auth context from cookies with token refresh.
 * This pattern is used at the top of every server action file.
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

export async function getExamples(
  search?: string,
  skip = 0,
  limit = 50,
): Promise<ActionResult<{ items: Example[]; total: number }>> {
  try {
    const auth = await getAuthContext();
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    params.set("skip", skip.toString());
    params.set("limit", limit.toString());

    const response = await apiGet<{ items: Example[]; total: number }>(
      `/examples?${params.toString()}`,
      auth,
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch examples",
    };
  }
}

export async function createExample(
  data: ExampleCreate,
): Promise<ActionResult<Example>> {
  try {
    const auth = await getAuthContext();
    const response = await apiPost<Example>("/examples", data, auth);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create example",
    };
  }
}

export async function deleteExample(
  id: string,
): Promise<ActionResult<void>> {
  try {
    const auth = await getAuthContext();
    await apiDelete(`/examples/${id}`, auth);
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete example",
    };
  }
}
```

**Server Action rules:**
1. Always start with `"use server"` directive
2. Always use `getAuthContext()` to get token and subdomain from cookies
3. Always return `ActionResult<T>` (never throw)
4. Catch all errors and return `{ success: false, error: "..." }`
5. The `getValidAccessToken()` function handles token refresh automatically

### 5.3 ActionResult Type

```typescript
// frontend/types/index.ts

export interface ActionResult<T = void> {
  success: boolean;
  data?: T;
  error?: string;
}
```

Usage in components:

```typescript
const result = await getExamples(search);
if (result.success) {
  setItems(result.data.items);
  setTotal(result.data.total);
} else {
  toast.error(result.error);
}
```

### 5.4 File Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Server Actions | `{module}.action.ts` | `auth.action.ts`, `finance.action.ts` |
| API Routes | `route.ts` in directory | `app/api/health/route.ts` |
| Page Components | `page.tsx` in directory | `app/(dashboard)/students/page.tsx` |
| Layout Components | `layout.tsx` in directory | `app/(dashboard)/layout.tsx` |
| React Components | PascalCase `.tsx` | `StudentCard.tsx`, `LoginForm.tsx` |
| Custom Hooks | camelCase with `use` prefix | `useTenant.ts`, `useAuth.ts` |
| Type Definitions | `index.ts` in types folder | `types/index.ts` |
| UI Components | Shadcn convention | `components/ui/button.tsx` |

### 5.5 Import Order

Imports in every file should follow this order (separated by blank lines):

```typescript
// 1. React / Next.js imports
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

// 2. Third-party libraries
import { format } from "date-fns";
import { toast } from "sonner";

// 3. UI components (Shadcn)
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// 4. Custom components
import { StudentCard } from "@/components/students/StudentCard";
import { DataTable } from "@/components/shared/DataTable";

// 5. Server Actions
import { getStudents, createStudent } from "@/actions/students.action";

// 6. Custom Hooks
import { useTenant } from "@/hooks/useTenant";

// 7. Types
import type { Student, ActionResult } from "@/types";

// 8. Utilities
import { cn } from "@/lib/utils";
```

### 5.6 TypeScript Type Patterns

Types for backend entities follow this structure (from `frontend/types/index.ts`):

```typescript
// Enum-like types use union of string literals
export type UserRole =
  | "platform_admin"
  | "chain_admin"
  | "school_admin"
  | "academic_head"
  | "finance_officer"
  | "teacher"
  | "house_parent"
  | "parent"
  | "student";

// Entity types mirror backend response schemas
export interface Student {
  id: string;              // UUID as string
  student_id: string;      // Human-readable ID (STU-2026-001)
  first_name: string;
  last_name: string;
  date_of_birth: string;   // ISO date string
  gender: "male" | "female";
  status: "active" | "inactive" | "graduated" | "transferred" | "withdrawn" | "suspended";
  class_id?: string;
  section_id?: string;
  tenant_id: string;
  created_at: string;      // ISO datetime string
  updated_at: string;
}

// Create types have required fields only
export interface StudentCreate {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: "male" | "female";
  school_id: string;
  // ... optional fields
}

// Update types have all fields optional
export interface StudentUpdate {
  first_name?: string;
  last_name?: string;
  // ... all optional
}

// List responses use a consistent structure
export interface StudentListResponse {
  items: Student[];
  total: number;
  skip: number;
  limit: number;
}
```

---

## 6. Security Checklist

### CRITICAL -- Must have before any deployment

- [ ] All tenant-scoped tables have `tenant_id NOT NULL`
- [ ] RLS enabled on all tenant-scoped tables with NO NULL bypass
- [ ] `FORCE ROW LEVEL SECURITY` set on all tenant-scoped tables
- [ ] `get_db()` sets tenant context via `set_tenant_context()` on every request
- [ ] All services filter by `tenant_id` explicitly (defense-in-depth)
- [ ] Application connects as `sims_app_user` (NOT `postgres` superuser)
- [ ] JWT access tokens: 15-minute expiry
- [ ] JWT refresh tokens: 7-day expiry with rotation
- [ ] Refresh token validation checks `tenant_id` match
- [ ] Token blacklisting implemented for logout and password change
- [ ] `SECRET_KEY` is 64+ characters in production
- [ ] No `from __future__ import annotations` in any endpoint file

### HIGH -- Must have before beta launch

- [ ] Account lockout: 5 failures triggers 30-minute lock
- [ ] Password policy enforced: 8+ chars, upper/lower/digit/special
- [ ] Argon2id hashing (not bcrypt)
- [ ] Rate limiting: auth endpoints have stricter limits than general API
- [ ] CORS restricted to `*.simsplus.io` pattern in production
- [ ] Security headers: X-Frame-Options, CSP, HSTS, X-Content-Type-Options
- [ ] Cross-tenant token validation on ALL protected endpoints (use `ValidatedUser`)
- [ ] Audit logging for all auth events (login, logout, failed attempts)
- [ ] Password reset endpoint does not reveal whether email exists
- [ ] Score change logging for exam modifications

### MEDIUM -- Should have before general availability

- [ ] Global exception handler sanitizes error messages in production (no stack traces)
- [ ] S3 paths use `{tenant_id}/` prefix for tenant isolation in file storage
- [ ] Redis keys use `tenant:{tenant_id}:` prefix for tenant-specific cached data
- [ ] Connection pool resets tenant context on checkout (prevents context leakage)
- [ ] ILIKE searches use `escape_ilike()` to prevent wildcard injection
- [ ] XSS prevention: all user-generated content is escaped before rendering
- [ ] CSRF protection for state-changing operations (POST/PUT/DELETE)
- [ ] File upload validation: type checking, size limits, virus scanning

---

## 7. Configuration Reference

### 7.1 Environment Variables

The Settings class lives in `backend/app/config.py` and uses Pydantic Settings v2. All values are loaded from environment variables or a `.env` file.

```bash
# ===== Required =====
DATABASE_URL=postgresql+asyncpg://sims_app_user:password@db:5432/sims_plus
SECRET_KEY=<64+ character random string, e.g., openssl rand -hex 64>

# ===== Application =====
APP_NAME=SIMS Plus
APP_VERSION=0.1.0
ENVIRONMENT=development              # development | staging | production
DEBUG=false                          # SECURITY: defaults to false

# ===== Server =====
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# ===== Database =====
DATABASE_POOL_SIZE=10                # Connection pool size (5 in debug mode)
DATABASE_MAX_OVERFLOW=20             # Max overflow connections (10 in debug)

# ===== Redis =====
REDIS_URL=redis://localhost:6379/0

# ===== Auth =====
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# ===== CORS =====
CORS_ORIGINS=["http://localhost:3000"]
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_SUBDOMAIN_PATTERN=https?://[\w-]+\.simsplus\.io

# ===== Rate Limiting =====
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_REQUESTS=500      # Dev value; use 100 in production
RATE_LIMIT_DEFAULT_WINDOW=60
RATE_LIMIT_AUTH_REQUESTS=30          # Dev value; use 5 in production
RATE_LIMIT_AUTH_WINDOW=60
RATE_LIMIT_SUBDOMAIN_CHECK_REQUESTS=20
RATE_LIMIT_SUBDOMAIN_CHECK_WINDOW=60

# ===== Email (SMTP) =====
SMTP_HOST=mailhog                    # Use actual SMTP server in production
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=false
SMTP_START_TLS=true
SMTP_FROM_EMAIL=noreply@simsplus.io
SMTP_FROM_NAME=SIMS Plus

# ===== SMS (Hubtel) =====
HUBTEL_CLIENT_ID=
HUBTEL_CLIENT_SECRET=
HUBTEL_SENDER_ID=SIMSPlus

# ===== Mobile Money (MTN MoMo) =====
MTN_MOMO_SUBSCRIPTION_KEY=
MTN_MOMO_API_USER=
MTN_MOMO_API_KEY=
MTN_MOMO_ENVIRONMENT=sandbox         # sandbox | production

# ===== AWS S3 =====
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=eu-west-1
AWS_S3_BUCKET=sims-plus-files

# ===== Monitoring =====
SENTRY_DSN=
LOG_LEVEL=INFO                       # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

### 7.2 Connection Strings

The application uses two PostgreSQL users with different privilege levels.

| Purpose | DB User | Connection String | Superuser? |
|---------|---------|-------------------|:--:|
| Application runtime | `sims_app_user` | `postgresql+asyncpg://sims_app_user:pw@db:5432/sims_plus` | No |
| Alembic migrations | `postgres` | `postgresql+asyncpg://postgres:pw@db:5432/sims_plus` | Yes |
| Test runtime | `sims_app_user` | `postgresql+asyncpg://sims_app_user:pw@localhost:5432/sims_plus_test` | No |
| Test setup (DDL) | `postgres` | `postgresql+asyncpg://postgres:pw@localhost:5432/sims_plus_test` | Yes |

**Why two users?** The application user (`sims_app_user`) is subject to RLS policies. It cannot bypass them, cannot create tables, and cannot modify schema. The superuser (`postgres`) is used only for migrations and test setup where schema changes are needed.

### 7.3 Redis Key Patterns

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `tenant:subdomain:{subdomain}` | 10 min | Subdomain-to-tenant lookup cache |
| `tenant:{tenant_id}:school:{school_id}` | 1 hour | Cached school profile |
| `tenant:{tenant_id}:user:{user_id}` | 15 min | Cached user profile |
| `tenant:{tenant_id}:students:count` | 5 min | Student count for subscription limits |
| `rate_limit:{type}:{identifier}` | Per config | Sliding window counters (sorted set) |
| `token_blacklist:{sha256(token)}` | Token TTL + 60s | Individual blacklisted JWT hashes |
| `user_token_blacklist:{user_id}` | 7 days | Mass token revocation timestamp |

**Rate limit key structure:**

The `{identifier}` in rate limit keys follows this priority:
1. `user:{user_id}` -- if request is authenticated
2. `tenant:{tenant_id}:ip:{ip_address}` -- if request has tenant context
3. `ip:{ip_address}` -- for public endpoints

### 7.4 Middleware Stack Order

Middleware is added in `backend/app/main.py`. The order matters because Starlette processes middleware in reverse registration order (last added = first executed).

```python
# Applied in reverse order of registration:
# 1. TenantMiddleware runs FIRST  (extracts tenant from subdomain)
# 2. RateLimitMiddleware runs SECOND  (checks rate limits)
# 3. CORSMiddleware runs THIRD  (handles CORS preflight)

app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
```

**Request flow through middleware:**

```
Browser Request
  -> CORSMiddleware (handle preflight, add CORS headers)
    -> RateLimitMiddleware (check rate limits, add X-RateLimit headers)
      -> TenantMiddleware (extract subdomain, validate tenant, set context)
        -> FastAPI Route Handler
          -> get_db() dependency (set RLS context)
            -> Service Layer (business logic)
```

---

## 8. Testing Patterns

### 8.1 Test Infrastructure

Tests use a two-engine pattern to properly test RLS:

| Engine | User | Purpose |
|--------|------|---------|
| Admin engine | `postgres` (superuser) | DDL operations: create/drop tables, enable RLS, set up test data |
| App engine | `sims_app_user` | Actual queries: subject to RLS policies, mirrors production |

The test configuration lives in `backend/tests/conftest.py`.

```python
# Test database URL (separate database from development)
TEST_DATABASE_URL = str(settings.DATABASE_URL).replace(
    "/sims_plus", "/sims_plus_test"
)

# Test engine uses NullPool (one connection per query, no pooling)
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

# Session factory with expire_on_commit=False
# (prevents LazyLoad errors after commit in tests)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
```

### 8.2 Test Database Setup

```python
@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables, yield session, drop tables after test."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Yield test session
    async with test_session_maker() as session:
        yield session
        await session.rollback()

    # Drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with overridden database dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

### 8.3 Raw SQL in Tests

When writing raw SQL in tests (e.g., to insert test data that bypasses the ORM), be aware of these gotchas:

1. **UUID bind parameters:** asyncpg sends Python `str` as VARCHAR, not UUID. Use `CAST(:param AS uuid)`:

```sql
-- WRONG (fails with asyncpg):
INSERT INTO students (id, tenant_id, ...) VALUES (:id, :tenant_id, ...);

-- RIGHT:
INSERT INTO students (id, tenant_id, ...)
VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), ...);
```

2. **Enum casing:** Check Section 2.6 for which enums use UPPERCASE vs lowercase values.

3. **RLS context in tests:** When the test session uses the `sims_app_user`, you must set the tenant context before inserting/querying data:

```python
await session.execute(
    text("SELECT set_tenant_context(:tid)"),
    {"tid": str(tenant_id)},
)
```

4. **Session expiry after context switch:** Always call `session.expire_all()` after switching tenant context. Capture any IDs you need before the switch:

```python
# Capture IDs BEFORE context switch
student_id = student.id

# Switch context
await session.execute(text("SELECT set_tenant_context(:tid)"), {"tid": str(other_tenant_id)})
session.expire_all()  # REQUIRED: invalidate cached objects

# Now query with new context
result = await session.execute(select(Student).where(Student.id == student_id))
assert result.scalar_one_or_none() is None  # RLS blocks cross-tenant access
```

---

## Quick Reference Card

For developers who need a fast lookup, here are the most commonly referenced rules:

| Topic | Rule |
|-------|------|
| Enum values in DB | `values_callable=lambda x: [e.value for e in x]` |
| Relationship loading | `lazy="raise"` (default), `lazy="joined"` (always needed), `lazy="selectin"` (collections) |
| Unique constraints | MUST include `tenant_id` |
| Service queries | MUST filter by `tenant_id` AND `deleted_at.is_(None)` |
| Service creates | MUST set `tenant_id` explicitly |
| Service persistence | `flush()` + `refresh()`, NEVER `commit()` |
| Endpoint auth | Use `ValidatedUser` dependency |
| Endpoint delete | Return 204, no body, no `from __future__ import annotations` |
| Frontend actions | Return `ActionResult<T>`, never throw |
| RLS policies | NO NULL bypass, NO admin bypass, FORCE enabled |
| Migration | Enable RLS as LAST step, include `enable_rls_for_table()` helper |
| Test SQL | `CAST(:param AS uuid)` for UUID bind params |
