# Phase 2: Backend — Auth, Service, Endpoints

**Complexity:** Large
**Dependencies:** Phase 1 (migration + model + CLI)
**Estimated effort:** 3-4 days

---

## Summary

Implement the platform admin authentication flow, PlatformService for cross-tenant operations, and all platform admin API endpoints. This phase also modifies the tenant middleware, deps.py, and security.py to support platform admin tokens.

---

## Task 1: Add Superuser Engine for Cross-Tenant Queries

### File: `backend/app/db/session.py`

Read this file first. Currently it has one engine connecting as `sims_app_user`.

**Add a second engine using `sims_admin` credentials** for platform admin cross-tenant queries. This engine bypasses RLS because all RLS policies are defined with `TO sims_app_user` — `sims_admin` is not subject to those policies.

```python
# --- Existing code (do not modify) ---
# engine = create_async_engine(str(settings.DATABASE_URL), ...)
# async_session_maker = async_sessionmaker(engine, ...)

# --- Add below the existing engine ---

# Superuser engine for platform admin cross-tenant queries.
# Uses sims_admin role which bypasses RLS (policies target sims_app_user only).
# This engine is ONLY used by PlatformService — never exposed as a FastAPI dependency.
# Small pool to limit blast radius: 2 base + 3 overflow = 5 max connections.
_platform_admin_engine: AsyncEngine | None = None
_platform_admin_session_maker: async_sessionmaker | None = None


def get_platform_admin_session_maker() -> async_sessionmaker:
    """
    Get the superuser session factory for cross-tenant queries.

    Lazily creates the engine on first call. Uses ALEMBIC_DATABASE_URL
    (sims_admin credentials) which bypasses RLS.

    WARNING: This must ONLY be used from PlatformService methods.
    Never expose this as a FastAPI dependency or pass to route handlers.
    """
    global _platform_admin_engine, _platform_admin_session_maker

    if _platform_admin_session_maker is None:
        admin_url = settings.ALEMBIC_DATABASE_URL
        if not admin_url:
            raise RuntimeError(
                "ALEMBIC_DATABASE_URL is required for platform admin operations. "
                "Set it in .env or environment variables."
            )

        # RISK FIX (R3): ALEMBIC_DATABASE_URL may use sync driver prefix
        # (postgresql://) but create_async_engine requires postgresql+asyncpg://.
        # Convert automatically, matching the pattern in alembic/env.py.
        admin_url_str = str(admin_url)
        if admin_url_str.startswith("postgresql://"):
            admin_url_str = admin_url_str.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        _platform_admin_engine = create_async_engine(
            admin_url_str,
            echo=False,  # Never echo superuser queries
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
        )
        _platform_admin_session_maker = async_sessionmaker(
            _platform_admin_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _platform_admin_session_maker
```

**Key design points:**
- Uses `ALEMBIC_DATABASE_URL` which connects as `sims_admin` (superuser for migrations).
- Pool is deliberately small: `pool_size=2, max_overflow=3` — max 5 connections.
- Lazy initialization — engine not created until first platform admin operation.
- `echo=False` always — superuser queries should never be logged to stdout.
- The function returns a session maker, NOT a session. PlatformService creates sessions within `async with` blocks.

---

## Task 2: Add Platform Admin JWT Claims Support

### File: `backend/app/core/security.py`

Read this file first. The `create_access_token()` function (lines 56-110) already supports `extra_claims: dict`. No changes to the function signature are needed — we pass `is_platform` and `is_impersonation` via `extra_claims`.

**No changes required to security.py.** The existing `extra_claims` parameter handles all new claims:

```python
# Called by PlatformService:
access_token = create_access_token(
    subject=str(user.id),
    tenant_id=str(settings.PLATFORM_TENANT_ID),
    role="platform_admin",
    permissions=["*"],
    extra_claims={
        "email": user.email,
        "is_platform": True,
        "tenant_subdomain": "_platform",
    },
)

# Called for impersonation:
impersonation_token = create_access_token(
    subject=str(platform_admin_user.id),
    tenant_id=str(target_tenant_id),
    role="platform_admin",
    permissions=["*"],
    extra_claims={
        "email": platform_admin_user.email,
        "is_platform": True,
        "is_impersonation": True,
        "original_tenant_id": str(settings.PLATFORM_TENANT_ID),
        "tenant_subdomain": target_subdomain,
    },
    expires_delta=timedelta(minutes=settings.PLATFORM_IMPERSONATION_EXPIRY_MINUTES),
)
```

---

## Task 3: Add PlatformAdminUser Dependency

### File: `backend/app/api/deps.py`

Read this file first (it's large — ~900 lines). Add the new dependency and update public path lists.

#### 3a. Update PUBLIC_PATH_PREFIXES

Add platform paths to `_PUBLIC_PATH_PREFIXES` (around line 40):

```python
_PUBLIC_PATH_PREFIXES = (
    # ... existing entries ...
    "/api/v1/platform/login",           # Platform admin login (no tenant context)
    "/api/v1/platform/refresh",         # Platform admin token refresh
    "/api/v1/platform/mfa/",            # RISK FIX (BUG-5): MFA verify/setup (no tenant context)
)
```

Add platform paths to `_SUBSCRIPTION_EXEMPT_PATHS` (around line 480):

```python
_SUBSCRIPTION_EXEMPT_PATHS = (
    # ... existing entries ...
    "/api/v1/platform/",  # Platform admin endpoints are not tenant-subscription-gated
)
```

#### 3b. Add PlatformAdminUser Dependency

Add after the existing `ValidatedTokenTenant` dependency:

```python
async def get_platform_admin_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Dependency that validates the caller is a platform admin.

    Validates:
    1. JWT is valid, not expired, not blacklisted
    2. Token type is "access" (rejects mfa_pending tokens)
    3. role == "platform_admin"
    4. is_platform == true claim exists
    5. tenant_id matches PLATFORM_TENANT_ID
    6. is_impersonation is NOT set (impersonation tokens cannot access /platform/*)
    7. mfa_setup_required is NOT set (MFA setup tokens can only access MFA setup endpoints)
    8. User still exists and is active in the database (cached 60s in Redis)

    Does NOT check ValidatedTokenTenant (no subdomain-based tenant context
    for platform admin requests).

    Returns:
        dict with user_id, email, role, tenant_id
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Platform admin authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except Exception:
        raise credentials_exception

    # Validate token type
    if payload.get("type") != "access":
        raise credentials_exception

    # Validate platform admin claims
    if payload.get("role") != "platform_admin":
        raise credentials_exception
    if not payload.get("is_platform"):
        raise credentials_exception
    if str(payload.get("tenant_id")) != str(settings.PLATFORM_TENANT_ID):
        raise credentials_exception

    # SECURITY: Reject impersonation tokens at /platform/* endpoints.
    # Impersonation tokens have tenant_id=<target>, so they would fail the
    # PLATFORM_TENANT_ID check above. But defense-in-depth: explicitly reject.
    if payload.get("is_impersonation"):
        raise credentials_exception

    # SECURITY: Reject MFA setup tokens. These are issued on first login
    # before MFA is configured. They must ONLY be used at MFA setup endpoints,
    # not for full platform admin access.
    if payload.get("mfa_setup_required"):
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    # Check token blacklist
    redis = getattr(request.app.state, "redis", None)
    if redis:
        from app.services.token_blacklist import TokenBlacklistService
        blacklist = TokenBlacklistService(redis)
        jti = payload.get("jti")
        if jti and await blacklist.is_blacklisted(jti):
            raise credentials_exception

    # SECURITY: Verify user still exists and is active in the database.
    # Uses Redis cache (60s TTL) to avoid hitting DB on every request.
    # If Redis is unavailable, falls through to DB check.
    is_active = None
    cache_key = f"platform_admin_active:{user_id}"
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                is_active = cached == "1"
        except Exception:
            pass

    if is_active is None:
        # DB check -- use unscoped session with tenant context for platform tenant
        from app.db.session import async_session_maker
        async with async_session_maker() as check_session:
            await check_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(settings.PLATFORM_TENANT_ID)},
            )
            result = await check_session.execute(
                select(User.status).where(
                    User.id == UUID(user_id),
                    User.role == UserRole.PLATFORM_ADMIN,
                    User.deleted_at.is_(None),
                )
            )
            user_status = result.scalar_one_or_none()
            is_active = user_status == UserStatus.ACTIVE if user_status else False
            if redis:
                try:
                    await redis.set(cache_key, "1" if is_active else "0", ex=60)
                except Exception:
                    pass

    if not is_active:
        raise credentials_exception

    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": "platform_admin",
        "tenant_id": str(settings.PLATFORM_TENANT_ID),
    }


# Type alias for use in endpoint signatures
PlatformAdmin = Annotated[dict, Depends(get_platform_admin_user)]
```

---

## Task 4: Update Tenant Middleware

### File: `backend/app/middleware/tenant.py`

Read this file first. Add platform paths to the public prefixes so they skip tenant resolution.

#### 4a. Add Platform Path Prefixes

Update `PUBLIC_PATH_PREFIXES` (around line 117):

```python
PUBLIC_PATH_PREFIXES = (
    # ... existing entries ...
    "/api/v1/platform/",  # Platform admin endpoints bypass tenant resolution
)
```

#### 4b. Remove "admin" from RESERVED_SUBDOMAINS (backend middleware only)

In `RESERVED_SUBDOMAINS` (line 94), remove `"admin"`:

```python
RESERVED_SUBDOMAINS = {
    "www", "app", "api", "mail", "ftp", "status", "blog",
    # "admin" removed — now handled as platform admin portal
    "help", "support", "docs", "cdn", "assets", "staging", "dev",
    # ... rest unchanged ...
}
```

**RISK NOTE (R-BC1):** Do NOT remove "admin" from the `reserved_subdomains` database table.
The DB table is used by the onboarding service to prevent schools from registering "admin"
as their subdomain. The in-memory set in this file is only used for request routing.
These are separate concerns and should stay separate.

**Important:** "admin" must be handled as a special case in proxy.ts (Phase 3) so that visiting `admin.simsplus.io` routes to the platform portal, not to a school dashboard.

---

## Task 5: Create Platform Schemas

### New File: `backend/app/schemas/platform.py`

```python
"""Pydantic schemas for platform admin endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# Auth schemas
# ============================================================

class PlatformLoginRequest(BaseModel):
    """Platform admin login credentials."""
    email: EmailStr
    password: str = Field(..., min_length=8)


class PlatformLoginResponse(BaseModel):
    """Successful platform admin login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "PlatformUserResponse"


class PlatformMFARequiredResponse(BaseModel):
    """Returned when platform admin has MFA enabled."""
    mfa_required: bool = True
    mfa_pending_token: str


class PlatformMFASetupRequiredResponse(BaseModel):
    """Returned on first login when MFA not yet configured."""
    mfa_setup_required: bool = True
    access_token: str  # Temporary token to access MFA setup only
    message: str = "MFA setup is required for platform admin accounts"


class PlatformUserResponse(BaseModel):
    """Platform admin user profile."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str = "platform_admin"
    mfa_enabled: bool


# ============================================================
# Tenant management schemas
# ============================================================

class TenantSummary(BaseModel):
    """Tenant summary for list view."""
    id: UUID
    name: str
    subdomain: str
    tenant_type: str
    status: str
    subscription_tier: str
    is_active: bool
    max_students: int
    max_staff: int
    created_at: datetime
    # Computed
    student_count: int = 0
    staff_count: int = 0
    school_count: int = 0


class TenantListResponse(BaseModel):
    """Paginated tenant list."""
    items: list[TenantSummary]
    total: int
    page: int
    page_size: int


class TenantDetail(TenantSummary):
    """Full tenant details."""
    email: str | None = None
    phone: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    features: dict | None = None
    subscription_start: datetime | None = None
    subscription_end: datetime | None = None
    trial_ends_at: datetime | None = None
    updated_at: datetime


class TenantUpdateRequest(BaseModel):
    """Update tenant details (platform admin).

    SECURITY: `status` is deliberately excluded. Status changes must go through
    the dedicated /suspend and /activate endpoints which have proper validation,
    state machine enforcement, and specific audit logging.
    """
    name: str | None = None
    subscription_tier: str | None = None
    max_students: int | None = Field(None, ge=0)
    max_staff: int | None = Field(None, ge=0)
    features: dict | None = None


class TenantSuspendRequest(BaseModel):
    """Suspend a tenant."""
    reason: str = Field(..., min_length=1, max_length=500)


# ============================================================
# Impersonation schemas
# ============================================================

class ImpersonationResponse(BaseModel):
    """Short-lived token scoped to the target tenant."""
    access_token: str
    tenant_id: UUID
    tenant_name: str
    tenant_subdomain: str
    expires_in: int  # Seconds


# ============================================================
# Analytics schemas
# ============================================================

class PlatformAnalytics(BaseModel):
    """Platform-wide analytics."""
    total_tenants: int
    active_tenants: int
    trial_tenants: int
    suspended_tenants: int
    total_students: int
    total_staff: int
    total_schools: int
    tenants_by_plan: dict[str, int]
    recent_registrations: list[TenantSummary]


# ============================================================
# Audit log schemas
# ============================================================

class PlatformAuditEntry(BaseModel):
    """Single audit log entry."""
    id: UUID
    actor_user_id: UUID
    actor_email: str | None = None
    action: str
    target_tenant_id: UUID | None = None
    target_tenant_name: str | None = None
    target_entity_type: str | None = None
    target_entity_id: UUID | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime


class PlatformAuditLogResponse(BaseModel):
    """Paginated audit log."""
    items: list[PlatformAuditEntry]
    total: int
    page: int
    page_size: int
```

---

## Task 6: Create PlatformService

### New File: `backend/app/services/platform.py`

This is the core service. It handles:
- Platform admin authentication (separate from school auth)
- Tenant listing with cross-tenant counts (superuser engine)
- Tenant CRUD (delegating to existing services where possible)
- Impersonation token creation
- Platform analytics
- Audit logging

```python
"""
Platform admin service.

Handles authentication, tenant management, impersonation,
and analytics for platform-wide administrators.

IMPORTANT: This service uses a superuser database engine
(sims_admin role) for cross-tenant queries. The engine
bypasses RLS because policies target sims_app_user only.
The superuser engine is NEVER exposed outside this service.
"""

import structlog
from datetime import datetime, timedelta, UTC
from uuid import UUID

from sqlalchemy import select, func, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_platform_admin_session_maker
from app.models.platform_audit import PlatformAuditLog
from app.models.tenant import Tenant, TenantStatus, SubscriptionTier
from app.models.user import User, UserRole, UserStatus

logger = structlog.get_logger()


class PlatformServiceError(Exception):
    def __init__(self, message: str, code: str = "platform_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class PlatformService:
    """
    Service for platform admin operations.

    Uses two database connections:
    1. `db` (AsyncSession) — tenant-scoped session from get_unscoped_db().
       Used for: platform admin user queries, audit log inserts,
       tenant table operations (tenants table has no RLS).
    2. Superuser engine — for cross-tenant aggregate queries on
       RLS-protected tables (students, staff, schools counts).
       Created lazily, never exposed outside this class.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ================================================================
    # Authentication
    # ================================================================

    async def authenticate(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """
        Authenticate a platform admin user.

        This is separate from AuthService.authenticate() because:
        1. It queries users within the platform tenant only
        2. It does NOT require a tenant_id from the request
        3. It creates tokens with is_platform=True claim
        4. It enforces MFA setup on first login

        Returns one of:
            {"tokens": {"access_token": ..., "refresh_token": ...}, "user": User}
            {"mfa_required": True, "mfa_pending_token": ...}
            {"mfa_setup_required": True, "access_token": ..., "message": ...}

        Raises:
            PlatformServiceError on invalid credentials, locked account, etc.
        """
        platform_tenant_id = UUID(settings.PLATFORM_TENANT_ID)

        # Query user within platform tenant
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == platform_tenant_id,
                User.role == UserRole.PLATFORM_ADMIN,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise PlatformServiceError(
                "Invalid email or password", "invalid_credentials"
            )

        # Check account status
        if user.status == UserStatus.SUSPENDED:
            raise PlatformServiceError("Account suspended", "account_suspended")
        if user.status == UserStatus.DEACTIVATED:
            raise PlatformServiceError("Account deactivated", "account_deactivated")

        # Check lockout
        if user.failed_login_attempts >= 5:
            if user.locked_until and user.locked_until > datetime.now(UTC):
                raise PlatformServiceError(
                    "Account locked due to too many failed attempts",
                    "account_locked",
                )
            # Reset lockout if time has passed
            user.failed_login_attempts = 0
            user.locked_until = None

        # Verify password
        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(UTC) + timedelta(minutes=30)
            await self.db.flush()
            raise PlatformServiceError(
                "Invalid email or password", "invalid_credentials"
            )

        # Reset failed attempts on success
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(UTC)
        user.last_activity_at = datetime.now(UTC)
        await self.db.flush()

        # Check MFA
        if user.mfa_enabled:
            # User has MFA set up — require verification.
            # SECURITY: Use jose_jwt.encode directly with type="mfa_pending"
            # (NOT create_access_token which defaults to type="access").
            # This ensures the token cannot pass PlatformAdminUser validation.
            # No permissions claim — this token can ONLY be used at MFA verify endpoint.
            from jose import jwt as jose_jwt
            from uuid import uuid4 as _uuid4

            mfa_pending_token = jose_jwt.encode(
                {
                    "sub": str(user.id),
                    "tenant_id": str(platform_tenant_id),
                    "type": "mfa_pending",
                    "is_platform": True,
                    "exp": datetime.now(UTC) + timedelta(minutes=5),
                    "iat": datetime.now(UTC),
                    "jti": str(_uuid4()),
                },
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            )
            return {"mfa_required": True, "mfa_pending_token": mfa_pending_token}

        if not user.mfa_enabled:
            # MFA not yet set up — issue a temporary token that only
            # allows MFA setup endpoints, then force setup.
            # SECURITY: This token has mfa_setup_required=True which is
            # explicitly rejected by PlatformAdminUser dependency.
            # It also has NO permissions claim — defense-in-depth.
            temp_token = create_access_token(
                subject=str(user.id),
                tenant_id=str(platform_tenant_id),
                role="platform_admin",
                # SECURITY: No permissions=["*"] — MFA setup tokens should
                # not carry wildcard permissions. The MFA setup endpoint
                # validates the token independently.
                extra_claims={
                    "is_platform": True,
                    "email": user.email,
                    "mfa_setup_required": True,
                    "tenant_subdomain": "_platform",
                },
                expires_delta=timedelta(minutes=30),
            )
            return {
                "mfa_setup_required": True,
                "access_token": temp_token,
                "message": "MFA setup is required for platform admin accounts",
            }

        # RISK FIX (BUG-1): The above two branches (mfa_enabled / not mfa_enabled)
        # cover all cases. _issue_tokens() is called from verify_mfa() and
        # complete_mfa_setup() below, NOT from authenticate(). authenticate()
        # ALWAYS returns either mfa_required or mfa_setup_required.
        raise PlatformServiceError("Unreachable", "internal_error")  # pragma: no cover

    async def verify_mfa(
        self,
        mfa_pending_token: str,
        totp_code: str,
    ) -> dict:
        """
        Verify MFA code during platform admin login.

        Called after authenticate() returns mfa_required=True.
        Validates the mfa_pending_token, verifies the TOTP code,
        and issues full access + refresh tokens.

        Returns:
            {"tokens": {"access_token": ..., "refresh_token": ...}, "user": User}
        """
        from jose import jwt as jose_jwt

        try:
            payload = jose_jwt.decode(
                mfa_pending_token, settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except Exception:
            raise PlatformServiceError("Invalid or expired MFA token", "invalid_token")

        if payload.get("type") != "mfa_pending" or not payload.get("is_platform"):
            raise PlatformServiceError("Invalid token type", "invalid_token")

        user_id = payload.get("sub")
        if not user_id:
            raise PlatformServiceError("Invalid token", "invalid_token")

        result = await self.db.execute(
            select(User).where(
                User.id == UUID(user_id),
                User.tenant_id == UUID(settings.PLATFORM_TENANT_ID),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise PlatformServiceError("User not found", "not_found")

        import pyotp
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise PlatformServiceError("Invalid MFA code", "invalid_mfa_code")

        return await self._issue_tokens(user)

    async def complete_mfa_setup(
        self,
        setup_token: str,
        totp_code: str,
        mfa_secret: str,
    ) -> dict:
        """
        Complete MFA setup for a platform admin (first login).

        Called after authenticate() returns mfa_setup_required=True.
        Stores the MFA secret, verifies the first TOTP code,
        and issues full access + refresh tokens.
        """
        from jose import jwt as jose_jwt

        try:
            payload = jose_jwt.decode(
                setup_token, settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except Exception:
            raise PlatformServiceError("Invalid or expired setup token", "invalid_token")

        if not payload.get("mfa_setup_required") or not payload.get("is_platform"):
            raise PlatformServiceError("Not an MFA setup token", "invalid_token")

        user_id = payload.get("sub")
        if not user_id:
            raise PlatformServiceError("Invalid token", "invalid_token")

        result = await self.db.execute(
            select(User).where(
                User.id == UUID(user_id),
                User.tenant_id == UUID(settings.PLATFORM_TENANT_ID),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise PlatformServiceError("User not found", "not_found")

        if user.mfa_enabled:
            raise PlatformServiceError("MFA is already enabled", "already_configured")

        import pyotp
        totp = pyotp.TOTP(mfa_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise PlatformServiceError("Invalid MFA code", "invalid_mfa_code")

        user.mfa_secret = mfa_secret
        user.mfa_enabled = True
        await self.db.flush()

        return await self._issue_tokens(user)

    async def _issue_tokens(self, user: User) -> dict:
        """Issue access + refresh tokens for a platform admin."""
        platform_tenant_id = str(settings.PLATFORM_TENANT_ID)

        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=platform_tenant_id,
            role="platform_admin",
            permissions=["*"],
            extra_claims={
                "email": user.email,
                "is_platform": True,
                "tenant_subdomain": "_platform",
            },
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            tenant_id=platform_tenant_id,
        )

        return {
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
            "user": user,
        }

    # ================================================================
    # Tenant Management
    # ================================================================

    async def list_tenants(
        self,
        page: int = 1,
        page_size: int = 25,
        search: str | None = None,
        status_filter: str | None = None,
        tier_filter: str | None = None,
    ) -> dict:
        """
        List all tenants with student/staff/school counts.

        Uses superuser engine for cross-tenant COUNT queries
        on RLS-protected tables.
        """
        from app.utils.sanitize import escape_ilike

        # Base query on tenants table (no RLS)
        query = select(Tenant).where(
            Tenant.subdomain != "_platform",  # Exclude platform tenant
            Tenant.deleted_at.is_(None),
        )

        if search:
            safe_search = escape_ilike(search)
            query = query.where(
                (Tenant.name.ilike(f"%{safe_search}%"))
                | (Tenant.subdomain.ilike(f"%{safe_search}%"))
            )
        if status_filter:
            query = query.where(Tenant.status == status_filter)
        if tier_filter:
            query = query.where(Tenant.subscription_tier == tier_filter)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.order_by(Tenant.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        tenants = result.scalars().all()

        # Get counts via superuser engine (bypasses RLS)
        tenant_ids = [t.id for t in tenants]
        counts = await self._get_tenant_counts(tenant_ids) if tenant_ids else {}

        items = []
        for t in tenants:
            tc = counts.get(str(t.id), {})
            items.append({
                "id": t.id,
                "name": t.name,
                "subdomain": t.subdomain,
                "tenant_type": t.tenant_type.value if t.tenant_type else None,
                "status": t.status.value if t.status else None,
                "subscription_tier": t.subscription_tier.value if t.subscription_tier else None,
                "is_active": t.is_active,
                "max_students": t.max_students,
                "max_staff": t.max_staff,
                "created_at": t.created_at,
                "student_count": tc.get("students", 0),
                "staff_count": tc.get("staff", 0),
                "school_count": tc.get("schools", 0),
            })

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # Allowlist of tables that _get_tenant_counts may query.
    # SECURITY: table names cannot be parameterized in SQL, so they are
    # validated against this set before interpolation.
    _ALLOWED_COUNT_TABLES = frozenset({"students", "staff", "schools"})

    async def _get_tenant_counts(self, tenant_ids: list[UUID]) -> dict:
        """
        Get student/staff/school counts for multiple tenants.

        Uses the superuser engine to bypass RLS for cross-tenant reads.
        Returns dict keyed by tenant_id string.

        SECURITY: Uses parameterized queries (CAST(:ids AS uuid[])) instead
        of f-string interpolation. Table names are validated against an
        allowlist before interpolation (table names cannot be parameterized
        in SQL). This is critical because the superuser engine bypasses RLS.
        """
        session_maker = get_platform_admin_session_maker()
        async with session_maker() as admin_session:
            ids_list = [str(tid) for tid in tenant_ids]

            counts = {}
            for table_name, count_key in [
                ("students", "students"),
                ("staff", "staff"),
                ("schools", "schools"),
            ]:
                # Validate table name against allowlist (defense-in-depth)
                if table_name not in self._ALLOWED_COUNT_TABLES:
                    raise PlatformServiceError(
                        f"Invalid table name: {table_name}",
                        "internal_error",
                    )
                result = await admin_session.execute(
                    text(f"""
                        SELECT tenant_id::TEXT, COUNT(*)
                        FROM {table_name}
                        WHERE tenant_id = ANY(CAST(:ids AS uuid[]))
                        AND deleted_at IS NULL
                        GROUP BY tenant_id
                    """),
                    {"ids": ids_list},
                )
                for row in result:
                    tid = row[0]
                    if tid not in counts:
                        counts[tid] = {}
                    counts[tid][count_key] = row[1]

            return counts

    async def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        """Get a single tenant by ID."""
        result = await self.db.execute(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.subdomain != "_platform",
                Tenant.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # SECURITY: Only these fields can be modified via update_tenant.
    # Status changes MUST go through suspend_tenant/activate_tenant.
    _ALLOWED_UPDATE_FIELDS = frozenset({
        "name", "subscription_tier", "max_students", "max_staff", "features",
    })

    async def update_tenant(self, tenant_id: UUID, data: dict) -> Tenant:
        """Update tenant details (subscription, limits, etc.).

        SECURITY: Uses an allowlist of updatable fields to prevent
        status/subdomain/id modification via this generic endpoint.
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise PlatformServiceError("Tenant not found", "not_found")

        for key, value in data.items():
            if key not in self._ALLOWED_UPDATE_FIELDS:
                raise PlatformServiceError(
                    f"Field '{key}' cannot be updated via this endpoint",
                    "invalid_field",
                )
            if value is not None and hasattr(tenant, key):
                setattr(tenant, key, value)

        await self.db.flush()
        return tenant

    async def suspend_tenant(self, tenant_id: UUID, reason: str) -> Tenant:
        """Suspend a tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise PlatformServiceError("Tenant not found", "not_found")
        if tenant.status == TenantStatus.SUSPENDED:
            raise PlatformServiceError("Tenant is already suspended", "already_suspended")

        tenant.status = TenantStatus.SUSPENDED
        tenant.is_active = False
        await self.db.flush()
        return tenant

    async def activate_tenant(self, tenant_id: UUID) -> Tenant:
        """Activate a suspended tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise PlatformServiceError("Tenant not found", "not_found")

        tenant.status = TenantStatus.ACTIVE
        tenant.is_active = True
        await self.db.flush()
        return tenant

    # ================================================================
    # Impersonation
    # ================================================================

    async def create_impersonation_token(
        self,
        platform_admin: dict,
        target_tenant_id: UUID,
    ) -> dict:
        """
        Create a short-lived impersonation token scoped to a target tenant.

        The impersonation token:
        - Has tenant_id set to the TARGET tenant (not platform)
        - Has is_impersonation=True claim
        - Has original_tenant_id pointing back to platform tenant
        - Expires in PLATFORM_IMPERSONATION_EXPIRY_MINUTES (default 30)
        - CANNOT be refreshed (no refresh token issued)
        - Passes ValidatedTokenTenant because tenant_id matches target subdomain
        - All existing endpoints work unchanged with this token

        Args:
            platform_admin: dict from PlatformAdmin dependency
            target_tenant_id: UUID of the tenant to impersonate

        Returns:
            dict with access_token, tenant_id, tenant_name, tenant_subdomain, expires_in
        """
        # Validate target tenant exists
        tenant = await self.get_tenant(target_tenant_id)
        if not tenant:
            raise PlatformServiceError("Tenant not found", "not_found")

        expiry_minutes = settings.PLATFORM_IMPERSONATION_EXPIRY_MINUTES

        impersonation_token = create_access_token(
            subject=platform_admin["user_id"],
            tenant_id=str(target_tenant_id),
            role="platform_admin",
            permissions=["*"],
            extra_claims={
                "email": platform_admin["email"],
                "is_platform": True,
                "is_impersonation": True,
                "original_tenant_id": str(settings.PLATFORM_TENANT_ID),
                "tenant_subdomain": tenant.subdomain,
            },
            expires_delta=timedelta(minutes=expiry_minutes),
        )

        return {
            "access_token": impersonation_token,
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "tenant_subdomain": tenant.subdomain,
            "expires_in": expiry_minutes * 60,  # Convert to seconds
        }

    # ================================================================
    # Analytics
    # ================================================================

    async def get_analytics(self) -> dict:
        """
        Get platform-wide analytics.

        Uses superuser engine for cross-tenant counts on RLS tables.
        Uses unscoped session for tenant table queries (no RLS on tenants).
        """
        # Tenant stats (no RLS on tenants table)
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Tenant.status == TenantStatus.ACTIVE).label("active"),
                func.count().filter(Tenant.status == TenantStatus.TRIAL).label("trial"),
                func.count().filter(Tenant.status == TenantStatus.SUSPENDED).label("suspended"),
            ).where(
                Tenant.subdomain != "_platform",
                Tenant.deleted_at.is_(None),
            )
        )
        stats = result.one()

        # Plan breakdown
        result = await self.db.execute(
            select(
                Tenant.subscription_tier, func.count()
            ).where(
                Tenant.subdomain != "_platform",
                Tenant.deleted_at.is_(None),
            ).group_by(Tenant.subscription_tier)
        )
        tenants_by_plan = {
            row[0].value if row[0] else "unknown": row[1]
            for row in result
        }

        # Cross-tenant counts (superuser engine)
        session_maker = get_platform_admin_session_maker()
        async with session_maker() as admin_session:
            students_result = await admin_session.execute(
                text("SELECT COUNT(*) FROM students WHERE deleted_at IS NULL")
            )
            total_students = students_result.scalar() or 0

            staff_result = await admin_session.execute(
                text("SELECT COUNT(*) FROM staff WHERE deleted_at IS NULL")
            )
            total_staff = staff_result.scalar() or 0

            schools_result = await admin_session.execute(
                text("SELECT COUNT(*) FROM schools WHERE deleted_at IS NULL")
            )
            total_schools = schools_result.scalar() or 0

        # Recent registrations (last 10)
        result = await self.db.execute(
            select(Tenant).where(
                Tenant.subdomain != "_platform",
                Tenant.deleted_at.is_(None),
            ).order_by(Tenant.created_at.desc()).limit(10)
        )
        recent = result.scalars().all()

        return {
            "total_tenants": stats.total,
            "active_tenants": stats.active,
            "trial_tenants": stats.trial,
            "suspended_tenants": stats.suspended,
            "total_students": total_students,
            "total_staff": total_staff,
            "total_schools": total_schools,
            "tenants_by_plan": tenants_by_plan,
            "recent_registrations": [
                {
                    "id": t.id,
                    "name": t.name,
                    "subdomain": t.subdomain,
                    "tenant_type": t.tenant_type.value if t.tenant_type else None,
                    "status": t.status.value if t.status else None,
                    "subscription_tier": t.subscription_tier.value if t.subscription_tier else None,
                    "is_active": t.is_active,
                    "max_students": t.max_students,
                    "max_staff": t.max_staff,
                    "created_at": t.created_at,
                }
                for t in recent
            ],
        }

    # ================================================================
    # Audit Logging
    # ================================================================

    async def log_action(
        self,
        actor_user_id: UUID,
        action: str,
        target_tenant_id: UUID | None = None,
        target_entity_type: str | None = None,
        target_entity_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log a platform admin action to the audit log."""
        entry = PlatformAuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_tenant_id=target_tenant_id,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(entry)
        await self.db.flush()

    async def get_audit_log(
        self,
        page: int = 1,
        page_size: int = 50,
        action_filter: str | None = None,
        actor_filter: UUID | None = None,
    ) -> dict:
        """Get paginated platform audit log.

        SECURITY: Uses the superuser engine because sims_app_user only has
        INSERT (not SELECT) on platform_audit_log. This prevents SQL injection
        in school-scoped endpoints from reading platform admin activities.
        """
        session_maker = get_platform_admin_session_maker()
        async with session_maker() as admin_session:
            query = select(PlatformAuditLog)
            if action_filter:
                query = query.where(PlatformAuditLog.action == action_filter)
            if actor_filter:
                query = query.where(PlatformAuditLog.actor_user_id == actor_filter)

            count_query = select(func.count()).select_from(query.subquery())
            total = (await admin_session.execute(count_query)).scalar() or 0

            query = query.order_by(PlatformAuditLog.created_at.desc())
            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await admin_session.execute(query)
            entries = result.scalars().all()

            return {
                "items": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
```

---

## Task 7: Create Platform Endpoints

### New File: `backend/app/api/v1/endpoints/platform.py`

```python
"""
Platform admin API endpoints.

All endpoints require PlatformAdmin dependency (validates is_platform JWT claim).
These endpoints operate OUTSIDE normal tenant-scoped context.

Rate limits:
- Login: 5/min (auth tier)
- Impersonation: 5/min
- Tenant CRUD: 10/min
- Read operations: 100/min
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    PlatformAdmin,
    UnscopedDatabaseSession,
)
from app.config import settings  # RISK FIX (BUG-2): Required for ACCESS_TOKEN_EXPIRE_MINUTES
from app.schemas.platform import (
    PlatformLoginRequest,
    PlatformLoginResponse,
    PlatformMFARequiredResponse,
    PlatformMFASetupRequiredResponse,
    PlatformUserResponse,
    TenantListResponse,
    TenantDetail,
    TenantUpdateRequest,
    TenantSuspendRequest,
    ImpersonationResponse,
    PlatformAnalytics,
    PlatformAuditLogResponse,
)
from app.services.platform import PlatformService, PlatformServiceError

router = APIRouter(prefix="/platform", tags=["Platform Admin"])

logger = structlog.get_logger()


# ============================================================
# Auth endpoints (no PlatformAdmin dependency — login is public)
# ============================================================

@router.post("/login", summary="Platform admin login")
async def platform_login(
    data: PlatformLoginRequest,
    request: Request,
    db: UnscopedDatabaseSession,
):
    """
    Authenticate a platform admin.

    Returns one of:
    - PlatformLoginResponse (full tokens) — if MFA already verified
    - PlatformMFARequiredResponse — if MFA enabled, needs verification
    - PlatformMFASetupRequiredResponse — if first login, MFA not configured
    """
    service = PlatformService(db)
    try:
        result = await service.authenticate(
            email=data.email,
            password=data.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except PlatformServiceError as e:
        if e.code == "account_locked":
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Try again later.",
            )
        # SECURITY: Always return the same generic message for all auth failures
        # (invalid credentials, suspended, deactivated, nonexistent) to prevent
        # account enumeration. The specific reason is logged server-side.
        logger.warning(
            "platform_login_failed",
            error_code=e.code,
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    # MFA required (already set up)
    if result.get("mfa_required"):
        # RISK FIX (BUG-3): Extract user_id from the mfa_pending_token payload
        # instead of result["user_id"] (which does not exist). The token's "sub"
        # claim contains the user_id. We decode it here for audit logging only.
        from jose import jwt as jose_jwt
        try:
            pending_payload = jose_jwt.decode(
                result["mfa_pending_token"],
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            audit_user_id = UUID(pending_payload.get("sub", "00000000-0000-0000-0000-000000000000"))
        except Exception:
            audit_user_id = UUID("00000000-0000-0000-0000-000000000000")

        await service.log_action(
            actor_user_id=audit_user_id,
            action="platform_login_mfa_pending",
            ip_address=request.client.host if request.client else None,
        )
        return JSONResponse(content={
            "mfa_required": True,
            "mfa_pending_token": result["mfa_pending_token"],
        })

    # MFA setup required (first login)
    if result.get("mfa_setup_required"):
        return JSONResponse(content={
            "mfa_setup_required": True,
            "access_token": result["access_token"],
            "message": result["message"],
        })

    # RISK FIX (BUG-1): authenticate() ALWAYS returns mfa_required or
    # mfa_setup_required. Full token issuance happens in /mfa/verify or
    # /mfa/setup below. If we reach here, something unexpected happened.
    raise HTTPException(status_code=500, detail="Unexpected auth response")


@router.post("/mfa/verify", summary="Verify MFA code during login")
async def platform_mfa_verify(
    request: Request,
    db: UnscopedDatabaseSession,
    mfa_pending_token: str = "",
    totp_code: str = "",
):
    """
    RISK FIX (BUG-5): Missing MFA verify endpoint.

    Called after /platform/login returns mfa_required=True.
    Validates the mfa_pending_token and TOTP code, issues full tokens.
    """
    service = PlatformService(db)
    try:
        result = await service.verify_mfa(mfa_pending_token, totp_code)
    except PlatformServiceError as e:
        raise HTTPException(status_code=401, detail=e.message)

    user = result["user"]
    tokens = result["tokens"]

    await service.log_action(
        actor_user_id=user.id,
        action="platform_login",
        details={"method": "mfa_verified"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return PlatformLoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=PlatformUserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            mfa_enabled=user.mfa_enabled,
        ),
    )


@router.post("/mfa/setup", summary="Complete MFA setup on first login")
async def platform_mfa_setup(
    request: Request,
    db: UnscopedDatabaseSession,
    setup_token: str = "",
    totp_code: str = "",
    mfa_secret: str = "",
):
    """
    RISK FIX (BUG-5): Missing MFA setup endpoint.

    Called after /platform/login returns mfa_setup_required=True.
    The frontend generates a TOTP secret (or the backend provides one
    via a separate /mfa/generate endpoint), shows the QR code, and
    the user enters the code here to complete setup.
    """
    service = PlatformService(db)
    try:
        result = await service.complete_mfa_setup(
            setup_token, totp_code, mfa_secret
        )
    except PlatformServiceError as e:
        raise HTTPException(status_code=401, detail=e.message)

    user = result["user"]
    tokens = result["tokens"]

    await service.log_action(
        actor_user_id=user.id,
        action="platform_login",
        details={"method": "mfa_setup_completed"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return PlatformLoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=PlatformUserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            mfa_enabled=user.mfa_enabled,
        ),
    )


@router.get("/mfa/generate", summary="Generate MFA secret for setup")
async def platform_mfa_generate(
    db: UnscopedDatabaseSession,
):
    """
    RISK FIX (BUG-5): Missing MFA secret generation endpoint.

    Returns a TOTP secret and provisioning URI for QR code generation.
    Called during first login MFA setup flow. The setup_token from
    /platform/login (mfa_setup_required response) must be passed as
    the Bearer token in the Authorization header.

    Note: This endpoint does NOT use PlatformAdmin dependency because
    the user only has a setup_token (not a full platform token).
    Auth is validated by checking the setup_token claims directly.
    """
    import pyotp
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name="SIMS Plus Platform Admin",
        issuer_name="SIMS Plus",
    )
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
    }


# ============================================================
# Protected endpoints (require PlatformAdmin)
# ============================================================

@router.get("/me", summary="Get platform admin profile")
async def platform_me(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
):
    """Get the current platform admin's profile."""
    from app.models.user import User
    user = await db.get(User, UUID(admin["user_id"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return PlatformUserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        mfa_enabled=user.mfa_enabled,
    )


@router.get("/tenants", summary="List all tenants")
async def list_tenants(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status: str | None = None,
    tier: str | None = None,
):
    """List all tenants with student/staff/school counts."""
    if page_size > 100:
        page_size = 100
    service = PlatformService(db)
    return await service.list_tenants(
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status,
        tier_filter=tier,
    )


@router.get("/tenants/{tenant_id}", summary="Get tenant details")
async def get_tenant(
    tenant_id: UUID,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
):
    """Get detailed information about a specific tenant."""
    service = PlatformService(db)
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get counts for this single tenant
    counts = await service._get_tenant_counts([tenant_id])
    tc = counts.get(str(tenant_id), {})

    return TenantDetail(
        id=tenant.id,
        name=tenant.name,
        subdomain=tenant.subdomain,
        tenant_type=tenant.tenant_type.value if tenant.tenant_type else None,
        status=tenant.status.value if tenant.status else None,
        subscription_tier=tenant.subscription_tier.value if tenant.subscription_tier else None,
        is_active=tenant.is_active,
        max_students=tenant.max_students,
        max_staff=tenant.max_staff,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        email=tenant.email,
        phone=tenant.phone,
        logo_url=tenant.logo_url,
        primary_color=tenant.primary_color,
        features=tenant.features,
        subscription_start=tenant.subscription_start,
        subscription_end=tenant.subscription_end,
        trial_ends_at=tenant.trial_ends_at,
        student_count=tc.get("students", 0),
        staff_count=tc.get("staff", 0),
        school_count=tc.get("schools", 0),
    )


@router.patch("/tenants/{tenant_id}", summary="Update tenant")
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdateRequest,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Update tenant details (subscription tier, limits, etc.)."""
    service = PlatformService(db)
    try:
        tenant = await service.update_tenant(
            tenant_id, data.model_dump(exclude_none=True)
        )
    except PlatformServiceError as e:
        raise HTTPException(status_code=404, detail=e.message)

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="tenant_update",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        details=data.model_dump(exclude_none=True),
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Tenant updated", "tenant_id": str(tenant_id)}


@router.post("/tenants/{tenant_id}/suspend", summary="Suspend tenant")
async def suspend_tenant(
    tenant_id: UUID,
    data: TenantSuspendRequest,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Suspend a tenant (blocks all access)."""
    service = PlatformService(db)
    try:
        await service.suspend_tenant(tenant_id, data.reason)
    except PlatformServiceError as e:
        raise HTTPException(
            status_code=404 if e.code == "not_found" else 409,
            detail=e.message,
        )

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="tenant_suspend",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        details={"reason": data.reason},
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Tenant suspended", "tenant_id": str(tenant_id)}


@router.post("/tenants/{tenant_id}/activate", summary="Activate tenant")
async def activate_tenant(
    tenant_id: UUID,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Activate a suspended tenant."""
    service = PlatformService(db)
    try:
        await service.activate_tenant(tenant_id)
    except PlatformServiceError as e:
        raise HTTPException(status_code=404, detail=e.message)

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="tenant_activate",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Tenant activated", "tenant_id": str(tenant_id)}


@router.post(
    "/impersonate/{tenant_id}",
    summary="Impersonate a tenant",
    response_model=ImpersonationResponse,
)
async def impersonate_tenant(
    tenant_id: UUID,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """
    Get a short-lived impersonation token scoped to a target tenant.

    The token:
    - Has tenant_id set to the TARGET tenant
    - Works with all existing school endpoints unchanged
    - Expires in 30 minutes
    - Cannot be refreshed
    - Is fully audited
    """
    service = PlatformService(db)
    try:
        result = await service.create_impersonation_token(admin, tenant_id)
    except PlatformServiceError as e:
        raise HTTPException(status_code=404, detail=e.message)

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="impersonate_start",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return result


@router.get("/analytics", summary="Platform-wide analytics")
async def platform_analytics(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Get platform-wide analytics (total tenants, students, staff, etc.)."""
    service = PlatformService(db)
    result = await service.get_analytics()

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="analytics_view",
        ip_address=request.client.host if request.client else None,
    )

    return result


@router.get("/audit-log", summary="Platform audit log")
async def platform_audit_log(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    page: int = 1,
    page_size: int = 50,
    action: str | None = None,
):
    """View the platform admin audit log."""
    if page_size > 100:
        page_size = 100
    service = PlatformService(db)
    return await service.get_audit_log(
        page=page,
        page_size=page_size,
        action_filter=action,
    )
```

---

## Task 8: Register Platform Router

### File: `backend/app/api/v1/router.py`

Read this file first to see the pattern for router registration. Add:

```python
from app.api.v1.endpoints.platform import router as platform_router

# Add to the main router (no prefix — platform.py already has /platform prefix)
api_router.include_router(platform_router)
```

---

## Task 9: Add Rate Limits for Platform Endpoints

### File: `backend/app/middleware/rate_limit.py`

Read this file first to find `ENDPOINT_LIMITS`. Add:

```python
# Platform admin endpoints
"/api/v1/platform/login": ("auth", "auth"),          # 5/min
"/api/v1/platform/mfa/verify": ("auth", "auth"),     # 5/min
"/api/v1/platform/mfa/setup": ("auth", "auth"),      # 5/min
# RISK FIX (R12): Impersonation rate-limited to bulk tier (10/min) instead
# of auth tier (5/min). A compromised admin at 5/min could impersonate
# 150 tenants in 30 minutes. At 10/min with monitoring, the window is
# smaller and audit log alerts can trigger. Consider further reduction
# to a custom 2/min tier for production.
"/api/v1/platform/impersonate": ("bulk", "bulk"),     # 10/min
"/api/v1/platform/tenants": ("default", "default"),   # 100/min
"/api/v1/platform/analytics": ("bulk", "bulk"),       # 10/min
```

---

## Verification Checklist

- [ ] Platform admin can log in via POST /api/v1/platform/login
- [ ] Login returns MFA setup required response on first login
- [ ] Login returns MFA required response when MFA enabled
- [ ] Invalid credentials return 401
- [ ] Account lockout after 5 failed attempts
- [ ] PlatformAdmin dependency rejects non-platform tokens
- [ ] PlatformAdmin dependency rejects school-level platform_admin users
- [ ] GET /platform/tenants returns all tenants with counts
- [ ] Tenant search/filter works
- [ ] GET /platform/tenants/{id} returns full tenant details
- [ ] PATCH /platform/tenants/{id} updates tenant
- [ ] POST /platform/tenants/{id}/suspend suspends tenant
- [ ] POST /platform/tenants/{id}/activate activates tenant
- [ ] POST /platform/impersonate/{id} returns impersonation token
- [ ] Impersonation token has correct tenant_id (target, not platform)
- [ ] Impersonation token has is_impersonation=True
- [ ] Impersonation token works with existing school endpoints
- [ ] Impersonation token expires in 30 minutes
- [ ] GET /platform/analytics returns correct counts
- [ ] GET /platform/audit-log returns audit entries
- [ ] All mutating operations logged to platform_audit_log
- [ ] Superuser engine only used within PlatformService
- [ ] Rate limits applied to platform endpoints
