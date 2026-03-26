"""
SIMS Plus - Authentication Service

Business logic for user authentication and authorization.
"""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple, Union
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole, UserStatus
from app.models.tenant import Tenant, TenantType
from app.models.user_school import UserSchool
from app.services.audit import AuditService, AuditEventType
from app.services.email import email_service
from app.services.session import SessionService, parse_user_agent
from app.services.token_blacklist import get_token_blacklist_service

logger = structlog.get_logger()

# Maximum number of school UUIDs to embed in the JWT for chain tenants.
# Beyond this threshold the token uses a ["*"] sentinel meaning "all schools
# in the tenant" to keep JWTs under ~2 KB.  The DB query in get_school_context
# still validates that the requested school belongs to the tenant.
MAX_JWT_SCHOOL_IDS = 20


class AuthenticationError(Exception):
    """Authentication failed."""

    def __init__(self, message: str, code: str = "auth_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthService:
    """Service for authentication operations."""

    # Account lockout settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    # Permissions by role
    ROLE_PERMISSIONS = {
        "platform_admin": ["*"],
        "chain_admin": [
            "schools.*",
            "users.*",
            "students.*",
            "staff.*",
            "academics.*",
            "subjects.*",
            "grading.*",
            "finance.*",
            "preschool.*",
            "boarding.*",
            "transport.*",
            "communications.*",
            "reports.*",
            "admissions.*",
            "curriculum.*",
            "subscription.*",
            "hr.leave.read",
            "hr.leave.request",
            "hr.leave.approve",
            "hr.leave.manage",
            "payroll.read",
            "payroll.configure",
            "payroll.manage",
            "payroll.process",
            "payroll.approve",
            "payroll.audit",
            "payroll.loans.read",
            "payroll.loans.request",
            "payroll.loans.approve",
            "payroll.loans.disburse",
            "payroll.loans.manage",
            "payroll.loans.write_off",
        ],
        "school_admin": [
            "school.read",
            "school.update",
            "users.*",
            "students.*",
            "staff.*",
            "classes.*",
            "academics.*",
            "subjects.*",
            "grading.*",
            "attendance.*",
            "exams.*",
            "finance.*",
            "preschool.*",
            "boarding.*",
            "transport.*",
            "communications.*",
            "reports.*",
            "admissions.*",
            "curriculum.*",
            "subscription.*",
            "hr.leave.read",
            "hr.leave.request",
            "hr.leave.approve",
            "hr.leave.manage",
            "payroll.read",
            "payroll.configure",
            "payroll.manage",
            "payroll.process",
            "payroll.approve",
            "payroll.audit",
            "payroll.loans.read",
            "payroll.loans.request",
            "payroll.loans.approve",
            "payroll.loans.disburse",
            "payroll.loans.manage",
            "payroll.loans.write_off",
            # School admins have full teacher portal access (head teacher view)
            "teacher.dashboard.read",
            "teacher.schedule.read",
            "teacher.classes.read",
            "teacher.grading.read",
            "teacher.grading.write",
            "teacher.lessons.read",
            "teacher.lessons.write",
            "teacher.notes.read",
            "teacher.notes.write",
            "teacher.attendance.read",
            "teacher.reports.read",
            "teacher.reports.write",
            "teacher.reports.head_teacher",
            "teacher.performance.read",
            "teacher.communication.write",
            "teacher.notifications.read",
        ],
        "academic_head": [
            "students.read",
            "students.update",
            "classes.*",
            "academics.*",
            "subjects.*",
            "grading.*",
            "attendance.*",
            "exams.*",
            "preschool.*",
            "reports.academic",
            "admissions.read",
            "admissions.review",
            "curriculum.read",
            "hr.leave.read",
            "hr.leave.request",
            # Academic heads have full teacher portal access including head teacher features
            "teacher.dashboard.read",
            "teacher.schedule.read",
            "teacher.classes.read",
            "teacher.grading.read",
            "teacher.grading.write",
            "teacher.lessons.read",
            "teacher.lessons.write",
            "teacher.notes.read",
            "teacher.notes.write",
            "teacher.attendance.read",
            "teacher.reports.read",
            "teacher.reports.write",
            "teacher.reports.head_teacher",
            "teacher.performance.read",
            "teacher.communication.write",
            "teacher.notifications.read",
        ],
        "finance_officer": [
            "students.read",
            "finance.*",
            "transport.read",
            "reports.financial",
            "payroll.read",
            "payroll.audit",
            "payroll.loans.read",
            "payroll.loans.disburse",
            "payroll.loans.manage",
        ],
        "hr_officer": [
            "staff.*",
            "students.read",
            "attendance.read",
            "reports.hr",
            "users.read",
            "boarding.read",
            "hr.leave.read",
            "hr.leave.request",
            "hr.leave.approve",
            "hr.leave.manage",
            "payroll.read",
            "payroll.configure",
            "payroll.manage",
            "payroll.process",
            "payroll.audit",
            "payroll.loans.read",
            "payroll.loans.request",
            "payroll.loans.approve",
            "payroll.loans.manage",
        ],
        "teacher": [
            "students.read",
            "classes.read",
            "subjects.read",
            "grading.read",
            "attendance.mark",
            "exams.scores.enter",
            "exams.scores.read",
            "exams.scores.submit",
            "exams.ca.enter",
            "exams.ca.read",
            "preschool.read",
            "preschool.create",
            "preschool.update",
            "boarding.read",
            "boarding.write",
            "transport.read",
            "curriculum.read",
            "hr.leave.read",
            "hr.leave.request",
            # Teacher portal permissions
            "teacher.dashboard.read",
            "teacher.schedule.read",
            "teacher.classes.read",
            "teacher.grading.read",
            "teacher.grading.write",
            "teacher.lessons.read",
            "teacher.lessons.write",
            "teacher.notes.read",
            "teacher.notes.write",
            "teacher.attendance.read",
            "teacher.reports.read",
            "teacher.reports.write",
            "teacher.communication.write",
            "teacher.notifications.read",
        ],
        "house_parent": [
            "students.read",
            "boarding.read",
            "boarding.write",
            "boarding.exeat.approve",
        ],
        "transport_officer": [
            "transport.*",
            "students.read",
            "self.read",
            "self.update",
        ],
        "parent": [
            "children.read",
            "finance.invoices.read",
            "preschool.read",
            "parent.children.read",
            "parent.grades.read",
            "parent.finance.read",
            "parent.attendance.read",
            "parent.communication.read",
        ],
        "student": [
            "self.read",
        ],
        # Applicant role -- prospective parents with limited access
        "applicant": [
            "applicant.profile.read",
            "applicant.profile.update",
            "applicant.applications.read",
            "applicant.applications.create",
            "applicant.applications.update",
            "applicant.applications.submit",
            "applicant.applications.claim",
        ],
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.session_service = SessionService(db)

    @classmethod
    def get_role_permissions(cls, role: str) -> list[str]:
        """Get permissions for a role."""
        return cls.ROLE_PERMISSIONS.get(role, [])

    @classmethod
    async def get_effective_permissions(
        cls, user: "User", db: AsyncSession
    ) -> list[str]:
        """
        Get the effective permissions for a user.

        If user has a custom_role_id, load permissions from the custom_roles
        table. Otherwise, use the static ROLE_PERMISSIONS dict.

        This method is called during token creation (login and refresh).
        The resolved permissions are embedded in the JWT — no per-request
        DB lookup is needed at runtime.
        """
        if user.custom_role_id:
            from app.models.custom_role import CustomRole

            result = await db.execute(
                select(CustomRole.permissions).where(
                    CustomRole.id == user.custom_role_id,
                    # Defense-in-depth: tenant_id filter even though RLS handles isolation
                    CustomRole.tenant_id == user.tenant_id,
                    CustomRole.deleted_at.is_(None),
                )
            )
            custom_perms = result.scalar_one_or_none()
            if custom_perms is not None:
                return custom_perms
            # Fallback to base role if custom role was deleted or not found.
            # The ondelete=SET NULL FK should prevent this, but defense-in-depth.
            logger.warning(
                "custom_role_not_found_fallback",
                user_id=str(user.id),
                custom_role_id=str(user.custom_role_id),
            )

        return cls.get_role_permissions(user.role.value)

    async def authenticate(
        self,
        email: str,
        password: str,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        remember_me: bool = False,
    ) -> Union[Tuple[User, str, str, int], dict]:
        """
        Authenticate a user with email and password.

        Args:
            email: User email
            password: Plain text password
            tenant_id: Tenant UUID for isolation
            ip_address: Client IP address for audit logging
            user_agent: Client user agent for audit logging
            remember_me: If True, extend refresh token lifetime for persistent sessions

        Returns:
            Tuple of (User, access_token, refresh_token, refresh_token_expires_in_seconds) for normal login,
            or dict with {"mfa_required": True, "mfa_pending_token": str}
            when the user has MFA enabled.

        Raises:
            AuthenticationError: If authentication fails
        """
        # Find user by email within tenant
        user = await self._get_user_by_email(email, tenant_id)

        if not user:
            # Log failed attempt
            await self.audit.log_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason="user_not_found",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthenticationError(
                "Invalid email or password",
                code="invalid_credentials",
            )

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(UTC):
            minutes_remaining = int(
                (user.locked_until - datetime.now(UTC)).total_seconds() / 60
            )
            await self.audit.log_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason="account_locked",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthenticationError(
                f"Account locked. Try again in {minutes_remaining} minutes.",
                code="account_locked",
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            await self._record_failed_login(user, ip_address)
            await self.audit.log_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason="invalid_password",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthenticationError(
                "Invalid email or password",
                code="invalid_credentials",
            )

        # Check user status
        if user.status == UserStatus.PENDING:
            await self.audit.log_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason="email_not_verified",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthenticationError(
                "Please verify your email address",
                code="email_not_verified",
            )

        if user.status == UserStatus.SUSPENDED:
            await self.audit.log_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason="account_suspended",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthenticationError(
                "Your account has been suspended",
                code="account_suspended",
            )

        if user.status == UserStatus.DEACTIVATED:
            await self.audit.log_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason="account_deactivated",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthenticationError(
                "Your account has been deactivated",
                code="account_deactivated",
            )

        # Reset failed attempts and update last login
        await self._record_successful_login(user)

        # Log successful login
        await self.audit.log_login_success(
            user_id=user.id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # MFA check: if user has MFA enabled, issue a short-lived pending
        # token instead of full access/refresh tokens. The frontend must
        # then call /auth/mfa/verify with this token + a TOTP code.
        if user.mfa_enabled:
            from jose import jwt as jose_jwt
            from uuid import uuid4

            mfa_pending_token = jose_jwt.encode(
                {
                    "sub": str(user.id),
                    "tenant_id": str(user.tenant_id),
                    "type": "mfa_pending",
                    "exp": datetime.now(UTC)
                    + timedelta(minutes=settings.MFA_PENDING_TOKEN_EXPIRY_MINUTES),
                    "iat": datetime.now(UTC),
                    "jti": str(uuid4()),
                },
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            )
            logger.info(
                "mfa_pending_token_issued",
                user_id=str(user.id),
                tenant_id=str(tenant_id),
            )
            return {
                "mfa_required": True,
                "mfa_pending_token": mfa_pending_token,
            }

        # Get permissions — from custom role if assigned, otherwise static ROLE_PERMISSIONS
        permissions = await self.get_effective_permissions(user, self.db)

        # Build chain-aware extra claims for JWT
        extra_claims = await self._build_extra_claims(user, tenant_id)

        # Extend refresh token lifetime when "Remember Me" is checked
        refresh_days = (
            settings.REMEMBER_ME_REFRESH_TOKEN_DAYS
            if remember_me
            else settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        refresh_expires = timedelta(days=refresh_days)

        # Generate refresh token first to get JTI for session tracking
        refresh_token, jti, expires_at = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            expires_delta=refresh_expires,
            # Persist remember_me preference so token rotation preserves it
            extra_claims={"remember_me": True} if remember_me else None,
        )

        # Include JTI in access token so session endpoints can identify current session
        extra_claims["jti"] = jti

        # Generate access token with full claims
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            school_id=str(user.school_id) if user.school_id else None,
            role=user.role.value,
            permissions=permissions,
            extra_claims=extra_claims,
        )

        refresh_expires_in_seconds = refresh_days * 24 * 60 * 60

        # Track the session for device management
        device_info = parse_user_agent(user_agent)
        await self.session_service.create_session(
            user_id=user.id,
            tenant_id=tenant_id,
            jti=jti,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
        )

        return user, access_token, refresh_token, refresh_expires_in_seconds

    async def register_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        tenant_id: UUID,
        role: UserRole = UserRole.TEACHER,
        phone: Optional[str] = None,
        auto_verify: bool = False,
    ) -> User:
        """
        Register a new user within a tenant.

        Args:
            email: User email
            password: Plain text password
            first_name: First name
            last_name: Last name
            tenant_id: Tenant UUID
            role: User role (default: TEACHER)
            phone: Optional phone number
            auto_verify: Skip email verification

        Returns:
            Created User

        Raises:
            AuthenticationError: If registration fails
        """
        # Check if email already exists in tenant
        existing = await self._get_user_by_email(email, tenant_id)
        if existing:
            raise AuthenticationError(
                "An account with this email already exists",
                code="email_exists",
            )

        # Create user
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            tenant_id=tenant_id,
            role=role,
            status=UserStatus.ACTIVE if auto_verify else UserStatus.PENDING,
            email_verified=auto_verify,
            email_verified_at=datetime.now(UTC) if auto_verify else None,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def refresh_tokens(
        self,
        refresh_token: str,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, str, int]:
        """
        Refresh access and refresh tokens.

        Deactivates the old session and creates a new one with the new JTI.

        Args:
            refresh_token: Current refresh token
            tenant_id: Tenant UUID for validation
            ip_address: Client IP for new session record
            user_agent: Client user-agent for new session record

        Returns:
            Tuple of (new_access_token, new_refresh_token, refresh_token_expires_in_seconds)

        Raises:
            AuthenticationError: If refresh fails
        """
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise AuthenticationError(
                "Invalid refresh token",
                code="invalid_token",
            )

        # Verify token type
        if payload.get("type") != "refresh":
            raise AuthenticationError(
                "Invalid token type",
                code="invalid_token_type",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError(
                "Invalid token payload",
                code="invalid_token",
            )

        # Reject refresh tokens whose JTI has been blacklisted (terminated sessions)
        # Pass db session so the blacklist check can fall back to user_sessions
        # table when Redis is unavailable (fail-closed security)
        token_jti = payload.get("jti")
        if token_jti:
            blacklist_service = await get_token_blacklist_service()
            # Defense-in-depth: pass tenant_id so DB fallback query is tenant-scoped
            if await blacklist_service.is_jti_blacklisted(
                token_jti, db=self.db, tenant_id=str(tenant_id)
            ):
                raise AuthenticationError(
                    "Token has been revoked",
                    code="token_revoked",
                )

        # Get user
        user = await self._get_user_by_id(UUID(user_id))
        if not user:
            raise AuthenticationError(
                "User not found",
                code="user_not_found",
            )

        # Validate user belongs to tenant
        if str(user.tenant_id) != str(tenant_id):
            raise AuthenticationError(
                "Token not valid for this school",
                code="tenant_mismatch",
            )

        # Check user is still active
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError(
                "Account is not active",
                code="account_inactive",
            )

        # Validate tenant_id in refresh token matches request tenant
        token_tenant_id = payload.get("tenant_id")
        if token_tenant_id and str(token_tenant_id) != str(tenant_id):
            raise AuthenticationError(
                "Refresh token not valid for this school",
                code="tenant_mismatch",
            )

        # Defense-in-depth: reject refresh if user has been inactive beyond the timeout.
        # The frontend should handle timeout gracefully before this check is triggered;
        # this catches edge cases like frozen browser tabs or disabled JavaScript.
        if user.last_activity_at:
            inactive_seconds = (
                datetime.now(UTC) - user.last_activity_at
            ).total_seconds()
            inactive_minutes = inactive_seconds / 60

            if inactive_minutes > settings.SESSION_TIMEOUT_MINUTES:
                logger.info(
                    "token_refresh_rejected_inactivity",
                    user_id=str(user.id),
                    tenant_id=str(tenant_id),
                    inactive_minutes=round(inactive_minutes, 1),
                )
                raise AuthenticationError(
                    "Session expired due to inactivity",
                    code="session_inactive",
                )
        # If last_activity_at is NULL (legacy user), allow refresh to avoid
        # breaking existing sessions that predate the heartbeat feature.

        # Deactivate the old session tied to the previous refresh token
        old_jti = payload.get("jti")
        if old_jti:
            await self.session_service.deactivate_by_jti(old_jti, tenant_id=tenant_id)

        # Get permissions — from custom role if assigned, otherwise static ROLE_PERMISSIONS
        permissions = await self.get_effective_permissions(user, self.db)

        # Build chain-aware extra claims for JWT
        extra_claims = await self._build_extra_claims(user, tenant_id)

        # Preserve remember_me state across token rotations so the extended
        # session lifetime survives refresh cycles
        remember_me = payload.get("remember_me", False)
        refresh_days = (
            settings.REMEMBER_ME_REFRESH_TOKEN_DAYS
            if remember_me
            else settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        refresh_expires = timedelta(days=refresh_days)

        # Generate new refresh token first to get JTI for session tracking
        new_refresh_token, new_jti, new_expires_at = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            expires_delta=refresh_expires,
            extra_claims={"remember_me": True} if remember_me else None,
        )

        # Include JTI in access token
        extra_claims["jti"] = new_jti

        # Generate new access token with full claims
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            school_id=str(user.school_id) if user.school_id else None,
            role=user.role.value,
            permissions=permissions,
            extra_claims=extra_claims,
        )

        refresh_expires_in_seconds = refresh_days * 24 * 60 * 60

        # Create new session for the rotated refresh token
        device_info = parse_user_agent(user_agent)
        await self.session_service.create_session(
            user_id=user.id,
            tenant_id=tenant_id,
            jti=new_jti,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=new_expires_at,
        )

        return access_token, new_refresh_token, refresh_expires_in_seconds

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        return await self._get_user_by_id(user_id)

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        """
        Change user password.

        Args:
            user_id: User UUID
            current_password: Current password
            new_password: New password

        Returns:
            True if successful

        Raises:
            AuthenticationError: If password change fails
        """
        user = await self._get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found", code="user_not_found")

        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError(
                "Current password is incorrect",
                code="invalid_password",
            )

        # Update password
        user.password_hash = hash_password(new_password)
        await self.db.flush()

        return True

    async def verify_email(self, user_id: UUID) -> bool:
        """Mark user email as verified."""
        user = await self._get_user_by_id(user_id)
        if not user:
            return False

        user.email_verified = True
        user.email_verified_at = datetime.now(UTC)
        user.status = UserStatus.ACTIVE
        await self.db.flush()

        return True

    # =========================
    # User Invitation
    # =========================

    async def invite_user(
        self,
        tenant_id: UUID,
        inviter_user_id: UUID,
        email: str,
        role: UserRole,
        first_name: str,
        last_name: str,
        school_id: Optional[UUID] = None,
    ) -> User:
        """
        Invite a new user by creating their account with a temporary password
        and sending them an invitation email.

        Args:
            tenant_id: Tenant UUID for multi-tenant context
            inviter_user_id: UUID of the user sending the invitation
            email: New user's email address
            role: Role to assign to the new user
            first_name: New user's first name
            last_name: New user's last name
            school_id: Optional school UUID for school-scoped users

        Returns:
            The newly created User

        Raises:
            AuthenticationError: If the email already exists for this tenant
        """
        # Check plan limit before inviting (raises LimitExceededError if exceeded)
        from app.services.subscription import SubscriptionService
        sub_service = SubscriptionService(self.db)
        await sub_service.check_user_limit(tenant_id)

        # Defense-in-depth: check email uniqueness within tenant
        existing = await self._get_user_by_email(email, tenant_id)
        if existing:
            raise AuthenticationError(
                "A user with this email already exists in this school",
                code="email_exists",
            )

        # Generate a cryptographically secure temporary password (16 chars)
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        temp_password = "".join(secrets.choice(alphabet) for _ in range(16))

        # Create the user account as active (invite flow skips email verification)
        user = User(
            email=email.lower(),
            password_hash=hash_password(temp_password),
            first_name=first_name,
            last_name=last_name,
            tenant_id=tenant_id,
            school_id=school_id,
            role=role,
            status=UserStatus.ACTIVE,
            email_verified=True,
            email_verified_at=datetime.now(UTC),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # Look up inviter name and tenant subdomain for the email
        inviter = await self._get_user_by_id(inviter_user_id)
        inviter_name = inviter.full_name if inviter else "An administrator"
        subdomain = await self._get_tenant_subdomain(tenant_id)
        school_name = subdomain or "your school"

        # Build portal URL
        if settings.is_production:
            portal_url = f"https://{subdomain}.simsplus.io"
        else:
            portal_url = "http://localhost:3000"

        # Send invitation email (best-effort -- do not fail if email fails)
        try:
            await email_service.send_user_invite(
                to_email=email.lower(),
                inviter_name=inviter_name,
                school_name=school_name,
                temp_password=temp_password,
                role=role.value.replace("_", " ").title(),
                portal_url=portal_url,
            )
        except Exception:
            logger.warning(
                "invite_email_failed",
                user_id=str(user.id),
                email=email.lower(),
                exc_info=True,
            )

        logger.info(
            "user_invited",
            user_id=str(user.id),
            email=email.lower(),
            role=role.value,
            invited_by=str(inviter_user_id),
        )

        return user

    # =========================
    # Private Helper Methods
    # =========================

    async def _get_user_by_email(
        self,
        email: str,
        tenant_id: UUID,
    ) -> Optional[User]:
        """Get user by email within tenant."""
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_tenant_subdomain(self, tenant_id: UUID) -> str:
        """Get tenant subdomain. Used by invite_user for email URL."""
        result = await self.db.execute(
            select(Tenant.subdomain).where(Tenant.id == tenant_id)
        )
        subdomain = result.scalar_one_or_none()
        return subdomain or ""

    async def _get_accessible_school_ids(
        self, user_id: UUID, tenant_id: UUID
    ) -> tuple[list[str], dict[str, str]]:
        """
        Query user_schools to find all schools this user can access
        and the role assigned at each school.

        Returns:
            A tuple of (accessible_school_ids, school_roles) where:
            - accessible_school_ids: list of school UUID strings
            - school_roles: dict mapping school UUID string to role_at_school
              (only entries where role_at_school is not None)
        """
        result = await self.db.execute(
            select(UserSchool.school_id, UserSchool.role_at_school)
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.user_id == user_id)
            .where(UserSchool.is_active.is_(True))
        )
        rows = result.all()

        school_ids = [str(row[0]) for row in rows]
        # Only include entries where a school-specific role is explicitly set
        school_roles = {
            str(row[0]): row[1] for row in rows if row[1] is not None
        }
        return school_ids, school_roles

    async def _build_extra_claims(self, user: User, tenant_id: UUID) -> dict:
        """
        Build extra JWT claims including chain support fields.

        For single-school tenants: includes email and subdomain only.
        For chain tenants: adds tenant_type and accessible_school_ids.

        Optimized: fetches subdomain + tenant_type in a single query
        instead of two serial round-trips.
        """
        # Single query for both subdomain and tenant_type
        result = await self.db.execute(
            select(Tenant.subdomain, Tenant.tenant_type).where(Tenant.id == tenant_id)
        )
        row = result.one_or_none()
        subdomain = row[0] if row else ""
        tenant_type_raw = row[1] if row else None

        if row is None:
            # This should never happen -- the tenant should exist if the user exists.
            # Raise instead of continuing with a half-built JWT.
            logger.error(
                "tenant_not_found_during_token_build",
                tenant_id=str(tenant_id),
                user_id=str(user.id),
            )
            raise AuthenticationError(
                "Internal error: tenant configuration not found",
                code="tenant_config_error",
            )

        if tenant_type_raw is None:
            tenant_type = "single_school"
        elif isinstance(tenant_type_raw, TenantType):
            tenant_type = tenant_type_raw.value
        else:
            tenant_type = str(tenant_type_raw)

        extra_claims: dict = {
            "email": user.email,
            "tenant_subdomain": subdomain,
        }

        # Add chain-specific claims when tenant is a school chain
        if tenant_type == "school_chain":
            accessible_ids, school_roles = await self._get_accessible_school_ids(
                user.id, tenant_id
            )
            extra_claims["tenant_type"] = tenant_type

            # Keep JWT compact for large chains: when the user has access to
            # more schools than the threshold, replace the full UUID list with
            # a ["*"] sentinel.  The DB-level check in get_school_context still
            # validates that the requested school belongs to the tenant, so
            # security is not weakened.
            if len(accessible_ids) > MAX_JWT_SCHOOL_IDS:
                extra_claims["accessible_school_ids"] = ["*"]
                logger.info(
                    "jwt_school_ids_truncated",
                    user_id=str(user.id),
                    tenant_id=str(tenant_id),
                    school_count=len(accessible_ids),
                    threshold=MAX_JWT_SCHOOL_IDS,
                )
            else:
                extra_claims["accessible_school_ids"] = accessible_ids

            # Include per-school role mapping so that switching schools
            # in the frontend can update permissions without a DB round-trip.
            # The dict is keyed by school UUID string; only schools where an
            # explicit role_at_school is set are included.
            if school_roles:
                extra_claims["school_roles"] = school_roles

        return extra_claims

    async def _record_failed_login(
        self,
        user: User,
        ip_address: Optional[str] = None,
    ) -> None:
        """Record failed login attempt."""
        user.failed_login_attempts += 1

        # Lock account after too many attempts
        if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(
                minutes=self.LOCKOUT_DURATION_MINUTES
            )
            # Log account lockout
            await self.audit.log_account_locked(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
            )

        await self.db.flush()

    async def _record_successful_login(self, user: User) -> None:
        """Record successful login."""
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(UTC)
        # Initialize the session inactivity timer from login time
        user.last_activity_at = datetime.now(UTC)
        await self.db.flush()
