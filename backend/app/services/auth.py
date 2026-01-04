"""
SIMS Plus - Authentication Service

Business logic for user authentication and authorization.
"""

from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

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
from app.models.tenant import Tenant
from app.services.audit import AuditService, AuditEventType


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
            "finance.*",
            "reports.*",
        ],
        "school_admin": [
            "school.read",
            "school.update",
            "users.*",
            "students.*",
            "staff.*",
            "classes.*",
            "attendance.*",
            "exams.*",
            "finance.*",
            "reports.*",
        ],
        "academic_head": [
            "students.read",
            "students.update",
            "classes.*",
            "attendance.*",
            "exams.*",
            "reports.academic",
        ],
        "finance_officer": [
            "students.read",
            "finance.*",
            "reports.financial",
        ],
        "teacher": [
            "students.read",
            "classes.read",
            "attendance.mark",
            "exams.scores",
        ],
        "house_parent": [
            "students.read",
            "boarding.*",
        ],
        "parent": [
            "children.read",
            "finance.invoices.read",
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

        # Generate tokens with full claims
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            school_id=str(user.school_id) if user.school_id else None,
            role=user.role.value,
            permissions=permissions,
            extra_claims={
                "email": user.email,
                "tenant_subdomain": await self._get_tenant_subdomain(tenant_id),
            },
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

        # Generate new tokens with full claims
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            school_id=str(user.school_id) if user.school_id else None,
            role=user.role.value,
            permissions=permissions,
            extra_claims={
                "email": user.email,
                "tenant_subdomain": await self._get_tenant_subdomain(tenant_id),
            },
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
        """Get tenant subdomain."""
        result = await self.db.execute(
            select(Tenant.subdomain).where(Tenant.id == tenant_id)
        )
        subdomain = result.scalar_one_or_none()
        return subdomain or ""

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
