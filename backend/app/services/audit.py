"""
SIMS Plus - Audit Service

Audit logging for security-relevant events.
"""

from datetime import UTC, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker


class AuditEventType:
    """Audit event types for categorization."""

    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGIN_LOCKED = "auth.login.locked"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    PASSWORD_CHANGE = "auth.password.change"
    PASSWORD_RESET_REQUEST = "auth.password.reset_request"
    PASSWORD_RESET_COMPLETE = "auth.password.reset_complete"

    # Cross-tenant / access events
    CROSS_TENANT_REJECTED = "auth.cross_tenant.rejected"
    SCHOOL_ACCESS_DENIED = "auth.school_access.denied"

    # Account events
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_ACTIVATED = "account.activated"
    ACCOUNT_DEACTIVATED = "account.deactivated"
    ACCOUNT_SUSPENDED = "account.suspended"
    ACCOUNT_UNLOCKED = "account.unlocked"

    # Data access events
    DATA_EXPORT = "data.export"
    DATA_BULK_DELETE = "data.bulk_delete"

    # MFA events
    MFA_ENABLED = "auth.mfa.enabled"
    MFA_DISABLED = "auth.mfa.disabled"
    MFA_VERIFIED = "auth.mfa.verified"
    MFA_BACKUP_CODES_REGENERATED = "auth.mfa.backup_codes_regenerated"

    # Admin events
    SETTINGS_CHANGED = "admin.settings.changed"
    USER_ROLE_CHANGED = "admin.user.role_changed"
    PERMISSION_GRANTED = "admin.permission.granted"
    PERMISSION_REVOKED = "admin.permission.revoked"


class AuditService:
    """Service for creating audit log entries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        event_type: str,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """
        Create an audit log entry.

        Uses a separate database connection to ensure audit logs are persisted
        even when the main transaction is rolled back (e.g., on auth failure).

        Args:
            event_type: Type of event (use AuditEventType constants)
            tenant_id: Tenant UUID (optional for platform-level events)
            user_id: User who performed the action
            target_type: Type of affected resource (e.g., "user", "student")
            target_id: ID of affected resource
            ip_address: Client IP address
            user_agent: Client user agent string
            details: Additional event details (JSON)
            success: Whether the action succeeded
        """
        try:
            # Format details as JSON string
            details_str = None
            if details:
                import json
                details_str = json.dumps(details)

            # Use a SEPARATE connection to ensure audit logs are committed
            # even when the main transaction fails (e.g., login failure)
            async with async_session_maker() as audit_session:
                await audit_session.execute(
                    text("""
                        INSERT INTO audit_logs (
                            tenant_id, user_id, action, resource_type, resource_id,
                            ip_address, user_agent, details
                        ) VALUES (
                            :tenant_id, :user_id, :action, :resource_type, :resource_id,
                            :ip_address, :user_agent, :details
                        )
                    """),
                    {
                        "tenant_id": str(tenant_id) if tenant_id else None,
                        "user_id": str(user_id) if user_id else None,
                        "action": event_type,
                        "resource_type": target_type or "auth",
                        "resource_id": str(target_id) if target_id else None,
                        "ip_address": ip_address[:45] if ip_address else None,
                        "user_agent": user_agent[:500] if user_agent else None,
                        "details": details_str,
                    },
                )
                # Commit immediately in the separate session
                await audit_session.commit()
        except Exception:
            # Don't let audit logging failures break the application
            pass

    async def log_login_success(
        self,
        user_id: UUID,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log successful login."""
        await self.log(
            event_type=AuditEventType.LOGIN_SUCCESS,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

    async def log_login_failed(
        self,
        email: str,
        tenant_id: Optional[UUID] = None,
        reason: str = "invalid_credentials",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log failed login attempt."""
        await self.log(
            event_type=AuditEventType.LOGIN_FAILED,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email, "reason": reason},
            success=False,
        )

    async def log_account_locked(
        self,
        user_id: UUID,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log account lockout."""
        await self.log(
            event_type=AuditEventType.LOGIN_LOCKED,
            tenant_id=tenant_id,
            user_id=user_id,
            target_type="user",
            target_id=user_id,
            ip_address=ip_address,
            details={"reason": "max_failed_attempts"},
            success=False,
        )

    async def log_logout(
        self,
        user_id: UUID,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log user logout."""
        await self.log(
            event_type=AuditEventType.LOGOUT,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            success=True,
        )

    async def log_password_change(
        self,
        user_id: UUID,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log password change."""
        await self.log(
            event_type=AuditEventType.PASSWORD_CHANGE,
            tenant_id=tenant_id,
            user_id=user_id,
            target_type="user",
            target_id=user_id,
            ip_address=ip_address,
            success=True,
        )

    async def log_token_refresh(
        self,
        user_id: UUID,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log token refresh."""
        await self.log(
            event_type=AuditEventType.TOKEN_REFRESH,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            success=True,
        )

    async def log_account_created(
        self,
        user_id: UUID,
        tenant_id: UUID,
        created_by: Optional[UUID] = None,
        role: Optional[str] = None,
    ) -> None:
        """Log account creation."""
        await self.log(
            event_type=AuditEventType.ACCOUNT_CREATED,
            tenant_id=tenant_id,
            user_id=created_by,
            target_type="user",
            target_id=user_id,
            details={"role": role},
            success=True,
        )
