"""
SIMS Plus - Session Management Service

Tracks active user sessions and allows users to view/terminate
sessions from other devices.
"""

import re
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_session import UserSession


def parse_user_agent(user_agent: Optional[str]) -> str:
    """
    Parse a User-Agent string into a human-readable device description.

    Extracts browser name and OS without requiring an external dependency.
    Falls back gracefully for unrecognised strings.
    """
    if not user_agent:
        return "Unknown device"

    # Detect OS
    os_name = "Unknown OS"
    os_patterns = [
        (r"Windows NT 10\.0", "Windows 10/11"),
        (r"Windows NT 6\.3", "Windows 8.1"),
        (r"Windows NT 6\.2", "Windows 8"),
        (r"Windows NT 6\.1", "Windows 7"),
        (r"Windows", "Windows"),
        (r"Macintosh|Mac OS X", "macOS"),
        (r"iPhone", "iPhone"),
        (r"iPad", "iPad"),
        (r"Android", "Android"),
        (r"Linux", "Linux"),
        (r"CrOS", "Chrome OS"),
    ]
    for pattern, name in os_patterns:
        if re.search(pattern, user_agent):
            os_name = name
            break

    # Detect browser (order matters — check specific before generic)
    browser_name = "Unknown Browser"
    browser_patterns = [
        (r"Edg[e/]", "Edge"),
        (r"OPR/|Opera", "Opera"),
        (r"Brave", "Brave"),
        (r"Vivaldi", "Vivaldi"),
        (r"Chrome/", "Chrome"),
        (r"Firefox/", "Firefox"),
        (r"Safari/", "Safari"),
        (r"MSIE|Trident", "Internet Explorer"),
    ]
    for pattern, name in browser_patterns:
        if re.search(pattern, user_agent):
            browser_name = name
            break

    return f"{browser_name} on {os_name}"


class SessionService:
    """Service for managing user login sessions."""

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user_id: UUID,
        tenant_id: UUID,
        jti: str,
        device_info: Optional[str],
        ip_address: Optional[str],
        expires_at: datetime,
    ) -> UserSession:
        """
        Create a new session record when a user logs in.

        Args:
            user_id: The authenticated user's ID
            tenant_id: Tenant ID for multi-tenant isolation
            jti: JWT ID of the refresh token
            device_info: Parsed user-agent string
            ip_address: Client IP address
            expires_at: When the refresh token expires
        """
        session = UserSession(
            user_id=user_id,
            tenant_id=tenant_id,
            jti=jti,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def list_sessions(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> list[UserSession]:
        """
        List active, non-expired sessions for a user.

        Defense-in-depth: filters by tenant_id even though RLS handles isolation.
        """
        result = await self.db.execute(
            select(UserSession)
            .where(UserSession.tenant_id == tenant_id)
            .where(UserSession.user_id == user_id)
            .where(UserSession.is_active.is_(True))
            .where(UserSession.expires_at > datetime.now(UTC))
            .order_by(UserSession.last_activity_at.desc())
        )
        return list(result.scalars().all())

    async def terminate_session(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
    ) -> str:
        """
        Terminate a specific session.

        Returns the JTI so the caller can blacklist the corresponding refresh token.

        Raises:
            SessionService.Error: If the session is not found or doesn't belong to the user
        """
        # Defense-in-depth: filter by tenant_id and user_id to prevent IDOR
        result = await self.db.execute(
            select(UserSession)
            .where(UserSession.tenant_id == tenant_id)
            .where(UserSession.id == session_id)
            .where(UserSession.user_id == user_id)
            .where(UserSession.is_active.is_(True))
        )
        session = result.scalar_one_or_none()

        if not session:
            raise self.Error("Session not found", 404)

        session.is_active = False
        await self.db.flush()

        return session.jti

    async def terminate_all_other_sessions(
        self,
        user_id: UUID,
        tenant_id: UUID,
        current_jti: str,
    ) -> list[str]:
        """
        Terminate all sessions except the current one.

        Returns list of JTIs so the caller can blacklist the corresponding refresh tokens.
        """
        # Fetch JTIs of sessions to be terminated
        result = await self.db.execute(
            select(UserSession.jti)
            .where(UserSession.tenant_id == tenant_id)
            .where(UserSession.user_id == user_id)
            .where(UserSession.is_active.is_(True))
            .where(UserSession.jti != current_jti)
        )
        jtis = list(result.scalars().all())

        if jtis:
            # Bulk deactivate
            await self.db.execute(
                update(UserSession)
                .where(UserSession.tenant_id == tenant_id)
                .where(UserSession.user_id == user_id)
                .where(UserSession.is_active.is_(True))
                .where(UserSession.jti != current_jti)
                .values(is_active=False)
            )
            await self.db.flush()

        return jtis

    async def update_activity(self, jti: str, tenant_id: UUID) -> None:
        """
        Update last_activity_at for a session identified by its JTI.

        Called on heartbeat to track when a session was last active.
        """
        await self.db.execute(
            update(UserSession)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(UserSession.tenant_id == tenant_id)
            .where(UserSession.jti == jti)
            .where(UserSession.is_active.is_(True))
            .values(last_activity_at=datetime.now(UTC))
        )
        await self.db.flush()

    async def deactivate_by_jti(self, jti: str, tenant_id: UUID) -> None:
        """
        Deactivate a session by its JTI.

        Called on logout or token refresh to mark the old session as inactive.
        """
        await self.db.execute(
            update(UserSession)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(UserSession.tenant_id == tenant_id)
            .where(UserSession.jti == jti)
            .values(is_active=False)
        )
        await self.db.flush()
