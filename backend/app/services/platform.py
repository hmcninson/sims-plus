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

import pyotp
from jose import jwt as jose_jwt
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4 as _uuid4

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.db.session import get_platform_admin_session_maker
from app.models.platform_audit import PlatformAuditLog
from app.models.tenant import Tenant, TenantStatus, SubscriptionTier
from app.models.user import User, UserRole, UserStatus
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


class PlatformServiceError(Exception):
    """Error raised by PlatformService operations."""

    def __init__(self, message: str, code: str = "platform_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class PlatformService:
    """
    Service for platform admin operations.

    Uses two database connections:
    1. `db` (AsyncSession) — unscoped session from get_unscoped_db().
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
        4. It enforces MFA on every login (setup or verify)

        Returns one of:
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
            # Constant-time: always hash to prevent timing-based user enumeration
            verify_password(
                password,
                "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            )
            raise PlatformServiceError(
                "Invalid email or password", "invalid_credentials"
            )

        # Check lockout BEFORE password verification (safe: lockout is
        # time-based, not status-based, so no enumeration risk)
        if user.failed_login_attempts >= 5:
            if user.locked_until and user.locked_until > datetime.now(UTC):
                raise PlatformServiceError(
                    "Account locked due to too many failed attempts",
                    "account_locked",
                )
            # Reset lockout if time has passed
            user.failed_login_attempts = 0
            user.locked_until = None

        # Verify password BEFORE checking account status (timing-safe:
        # password verification always runs regardless of account state,
        # preventing timing side-channel on suspended/deactivated status)
        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(UTC) + timedelta(minutes=30)
            await self.db.flush()
            raise PlatformServiceError(
                "Invalid email or password", "invalid_credentials"
            )

        # Check account status AFTER password verification (timing-safe)
        if user.status == UserStatus.SUSPENDED:
            raise PlatformServiceError("Account suspended", "account_suspended")
        if user.status == UserStatus.DEACTIVATED:
            raise PlatformServiceError("Account deactivated", "account_deactivated")

        # Reset failed attempts on success
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(UTC)
        user.last_activity_at = datetime.now(UTC)
        await self.db.flush()

        # Check MFA status — authenticate() ALWAYS returns either
        # mfa_required or mfa_setup_required. Full token issuance happens
        # in verify_mfa() or complete_mfa_setup(), not here (BUG-1 fix).
        if user.mfa_enabled:
            # User has MFA set up — require TOTP verification.
            # SECURITY: Use jose_jwt.encode directly with type="mfa_pending"
            # (NOT create_access_token which defaults to type="access").
            # This ensures the token cannot pass PlatformAdminUser validation.
            mfa_pending_token = jose_jwt.encode(
                {
                    "sub": str(user.id),
                    "tenant_id": str(platform_tenant_id),
                    "type": "mfa_pending",
                    "is_platform": True,
                    "exp": datetime.now(UTC) + timedelta(
                        minutes=settings.MFA_PENDING_TOKEN_EXPIRY_MINUTES
                    ),
                    "iat": datetime.now(UTC),
                    "jti": str(_uuid4()),
                },
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            )
            return {"mfa_required": True, "mfa_pending_token": mfa_pending_token}

        # MFA not yet set up — issue a temporary token that only allows
        # MFA setup endpoints, then force setup.
        # SECURITY: Use jose_jwt.encode directly with type="mfa_setup"
        # (NOT create_access_token which defaults to type="access").
        # This ensures the token cannot pass PlatformAdminUser validation
        # or be used as a regular access token.
        temp_token = jose_jwt.encode(
            {
                "sub": str(user.id),
                "tenant_id": str(platform_tenant_id),
                "role": "platform_admin",
                "is_platform": True,
                "mfa_setup_required": True,
                "email": user.email,
                "tenant_subdomain": "_platform",
                "type": "mfa_setup",
                "exp": datetime.now(UTC) + timedelta(minutes=30),
                "iat": datetime.now(UTC),
                "jti": str(_uuid4()),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return {
            "mfa_setup_required": True,
            "access_token": temp_token,
            "message": "MFA setup is required for platform admin accounts",
        }

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
        try:
            payload = jose_jwt.decode(
                mfa_pending_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except Exception:
            raise PlatformServiceError(
                "Invalid or expired MFA token", "invalid_token"
            )

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

        if not user.mfa_enabled or not user.mfa_secret:
            raise PlatformServiceError("MFA is not enabled", "mfa_not_enabled")

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
        try:
            payload = jose_jwt.decode(
                setup_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except Exception:
            raise PlatformServiceError(
                "Invalid or expired setup token", "invalid_token"
            )

        # Accept both the new type="mfa_setup" tokens and legacy tokens with
        # mfa_setup_required=True claim
        is_mfa_setup_token = (
            payload.get("type") == "mfa_setup" or payload.get("mfa_setup_required")
        )
        if not is_mfa_setup_token or not payload.get("is_platform"):
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
            raise PlatformServiceError(
                "MFA is already enabled", "already_configured"
            )

        # Verify the TOTP code against the provided secret
        totp = pyotp.TOTP(mfa_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise PlatformServiceError("Invalid MFA code", "invalid_mfa_code")

        # Store the secret and enable MFA
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
        refresh_token, _jti, _expires_at = create_refresh_token(
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
            items.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "subdomain": t.subdomain,
                    "tenant_type": t.tenant_type.value if t.tenant_type else None,
                    "status": t.status.value if t.status else None,
                    "subscription_tier": (
                        t.subscription_tier.value if t.subscription_tier else None
                    ),
                    "is_active": t.is_active,
                    "max_students": t.max_students,
                    "max_staff": t.max_staff,
                    "created_at": t.created_at,
                    "student_count": tc.get("students", 0),
                    "staff_count": tc.get("staff", 0),
                    "school_count": tc.get("schools", 0),
                }
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

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
        of f-string interpolation for values. Table names are validated against
        an allowlist before interpolation (table names cannot be parameterized
        in SQL). This is critical because the superuser engine bypasses RLS.
        """
        session_maker = get_platform_admin_session_maker()
        async with session_maker() as admin_session:
            ids_list = [str(tid) for tid in tenant_ids]

            counts: dict[str, dict[str, int]] = {}
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
                    text(
                        f"""
                        SELECT tenant_id::TEXT, COUNT(*)
                        FROM {table_name}
                        WHERE tenant_id = ANY(CAST(:ids AS uuid[]))
                        AND deleted_at IS NULL
                        GROUP BY tenant_id
                    """
                    ),
                    {"ids": ids_list},
                )
                for row in result:
                    tid = row[0]
                    if tid not in counts:
                        counts[tid] = {}
                    counts[tid][count_key] = row[1]

            return counts

    async def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        """Get a single tenant by ID (excludes platform tenant)."""
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
    _ALLOWED_UPDATE_FIELDS = frozenset(
        {"name", "subscription_tier", "max_students", "max_staff", "features"}
    )

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
        """Suspend a tenant (blocks all access)."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise PlatformServiceError("Tenant not found", "not_found")
        if tenant.status == TenantStatus.SUSPENDED:
            raise PlatformServiceError(
                "Tenant is already suspended", "already_suspended"
            )

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
        """
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
                func.count()
                .filter(Tenant.status == TenantStatus.ACTIVE)
                .label("active"),
                func.count()
                .filter(Tenant.status == TenantStatus.TRIAL)
                .label("trial"),
                func.count()
                .filter(Tenant.status == TenantStatus.SUSPENDED)
                .label("suspended"),
            ).where(
                Tenant.subdomain != "_platform",
                Tenant.deleted_at.is_(None),
            )
        )
        stats = result.one()

        # Plan breakdown
        result = await self.db.execute(
            select(Tenant.subscription_tier, func.count())
            .where(
                Tenant.subdomain != "_platform",
                Tenant.deleted_at.is_(None),
            )
            .group_by(Tenant.subscription_tier)
        )
        tenants_by_plan = {
            row[0].value if row[0] else "unknown": row[1] for row in result
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
            select(Tenant)
            .where(
                Tenant.subdomain != "_platform",
                Tenant.deleted_at.is_(None),
            )
            .order_by(Tenant.created_at.desc())
            .limit(10)
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
                    "subscription_tier": (
                        t.subscription_tier.value if t.subscription_tier else None
                    ),
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
                query = query.where(
                    PlatformAuditLog.actor_user_id == actor_filter
                )

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
