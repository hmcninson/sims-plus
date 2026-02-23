"""
SIMS Plus - Authentication Service

Business logic for user authentication and authorization.
"""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple
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
            "reports.*",
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
            "reports.*",
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
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    @classmethod
    def get_role_permissions(cls, role: str) -> list[str]:
        """Get permissions for a role."""
        return cls.ROLE_PERMISSIONS.get(role, [])

    async def authenticate(
        self,
        email: str,
        password: str,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, str, str]:
        """
        Authenticate a user with email and password.

        Args:
            email: User email
            password: Plain text password
            tenant_id: Tenant UUID for isolation
            ip_address: Client IP address for audit logging
            user_agent: Client user agent for audit logging

        Returns:
            Tuple of (User, access_token, refresh_token)

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

        # Get permissions for user's role
        permissions = self.get_role_permissions(user.role.value)

        # Build chain-aware extra claims for JWT
        extra_claims = await self._build_extra_claims(user, tenant_id)

        # Generate tokens with full claims
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            school_id=str(user.school_id) if user.school_id else None,
            role=user.role.value,
            permissions=permissions,
            extra_claims=extra_claims,
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
        )

        return user, access_token, refresh_token

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
    ) -> Tuple[str, str]:
        """
        Refresh access and refresh tokens.

        Args:
            refresh_token: Current refresh token
            tenant_id: Tenant UUID for validation

        Returns:
            Tuple of (new_access_token, new_refresh_token)

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

        # Get permissions for user's role
        permissions = self.get_role_permissions(user.role.value)

        # Build chain-aware extra claims for JWT
        extra_claims = await self._build_extra_claims(user, tenant_id)

        # Generate new tokens with full claims
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            school_id=str(user.school_id) if user.school_id else None,
            role=user.role.value,
            permissions=permissions,
            extra_claims=extra_claims,
        )
        new_refresh_token = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
        )

        return access_token, new_refresh_token

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

    async def _get_accessible_school_ids(self, user_id: UUID, tenant_id: UUID) -> list[str]:
        """
        Query user_schools to find all schools this user can access.

        Returns a list of school UUID strings. For chain tenants this
        determines which schools appear in the JWT accessible_school_ids
        claim and which X-Active-School values are accepted.
        """
        result = await self.db.execute(
            select(UserSchool.school_id)
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.user_id == user_id)
            .where(UserSchool.is_active.is_(True))
        )
        school_ids = result.scalars().all()
        return [str(sid) for sid in school_ids]

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
            accessible_ids = await self._get_accessible_school_ids(user.id, tenant_id)
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
        await self.db.flush()
