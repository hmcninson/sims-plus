"""
SIMS Plus - Parent Notification Preferences Service

Manages per-parent notification channel and category preferences.
Used by the NotificationDispatcher to determine which channels to
send a notification through before dispatching.
"""

from datetime import datetime, time, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parent import ParentNotificationPreference
from app.services.parent._shared import ParentServiceError

logger = structlog.get_logger()

# Map category strings to model column names for preference checking
_CATEGORY_COLUMN_MAP = {
    "attendance": "notify_attendance",
    "grades": "notify_grades",
    "finance": "notify_finance",
    "announcements": "notify_announcements",
    "transport": "notify_transport",
    "boarding": "notify_boarding",
}

# Map channel strings to model column names for preference checking
_CHANNEL_COLUMN_MAP = {
    "email": "email_enabled",
    "sms": "sms_enabled",
    "push": "push_enabled",
}


class NotificationPreferencesService:
    """
    Manages parent notification preferences.

    Provides CRUD for preference records and a fast should_notify()
    check used by the NotificationDispatcher before sending through
    each channel.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_preferences(
        self, user_id: UUID, tenant_id: UUID
    ) -> ParentNotificationPreference:
        """
        Get notification preferences for a parent, creating defaults if none exist.

        Returns:
            The ParentNotificationPreference record (existing or newly created)
        """
        result = await self.db.execute(
            select(ParentNotificationPreference).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ParentNotificationPreference.tenant_id == tenant_id,
                    ParentNotificationPreference.user_id == user_id,
                )
            )
        )
        prefs = result.scalar_one_or_none()

        if prefs:
            return prefs

        # Create default preferences on first access
        prefs = ParentNotificationPreference(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        self.db.add(prefs)
        await self.db.flush()
        await self.db.refresh(prefs)

        logger.info(
            "default_notification_preferences_created",
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )
        return prefs

    async def update_preferences(
        self, user_id: UUID, tenant_id: UUID, data: dict
    ) -> ParentNotificationPreference:
        """
        Update notification preferences using PATCH semantics.

        Only fields present in `data` are updated; absent fields are left unchanged.

        Accepted keys:
            email_enabled, sms_enabled, push_enabled,
            notify_attendance, notify_grades, notify_finance,
            notify_announcements, notify_transport, notify_boarding,
            quiet_hours_start (HH:MM string or time), quiet_hours_end (HH:MM string or time)

        Args:
            user_id: The parent user's ID
            tenant_id: Tenant UUID
            data: Dict of fields to update

        Returns:
            The updated ParentNotificationPreference

        Raises:
            ParentServiceError: If quiet hours are partially set
        """
        prefs = await self.get_preferences(user_id, tenant_id)

        # Allowed boolean fields
        bool_fields = [
            "email_enabled", "sms_enabled", "push_enabled",
            "notify_attendance", "notify_grades", "notify_finance",
            "notify_announcements", "notify_transport", "notify_boarding",
        ]

        for field in bool_fields:
            if field in data and data[field] is not None:
                setattr(prefs, field, bool(data[field]))

        # Handle quiet hours (accept HH:MM strings or time objects)
        if "quiet_hours_start" in data or "quiet_hours_end" in data:
            start = data.get("quiet_hours_start")
            end = data.get("quiet_hours_end")

            # Allow clearing quiet hours by setting both to None
            if start is None and end is None:
                prefs.quiet_hours_start = None
                prefs.quiet_hours_end = None
            else:
                # Both must be provided if either is set
                resolved_start = self._parse_time(start) if start else prefs.quiet_hours_start
                resolved_end = self._parse_time(end) if end else prefs.quiet_hours_end

                if (resolved_start is None) != (resolved_end is None):
                    raise ParentServiceError(
                        "Both quiet_hours_start and quiet_hours_end must be set together, "
                        "or both must be null to disable quiet hours",
                        code="invalid_quiet_hours",
                    )

                prefs.quiet_hours_start = resolved_start
                prefs.quiet_hours_end = resolved_end

        await self.db.flush()
        await self.db.refresh(prefs)

        logger.info(
            "notification_preferences_updated",
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )
        return prefs

    async def should_notify(
        self,
        user_id: UUID,
        tenant_id: UUID,
        channel: str,
        category: str,
    ) -> bool:
        """
        Check if a notification should be sent based on parent preferences.

        Evaluates channel preference, category preference, and quiet hours.
        Returns False if preferences do not exist (safe default: do not spam).

        Args:
            user_id: The parent user's ID
            tenant_id: Tenant UUID
            channel: 'email', 'sms', or 'push'
            category: 'attendance', 'grades', 'finance', 'announcements',
                      'transport', or 'boarding'

        Returns:
            True if the notification should be sent through this channel
        """
        result = await self.db.execute(
            select(ParentNotificationPreference).where(
                and_(
                    ParentNotificationPreference.tenant_id == tenant_id,
                    ParentNotificationPreference.user_id == user_id,
                )
            )
        )
        prefs = result.scalar_one_or_none()

        if not prefs:
            # No preferences found -- default to not sending external notifications.
            # In-app notifications are always sent regardless of preferences.
            return False

        # Check channel preference
        channel_col = _CHANNEL_COLUMN_MAP.get(channel)
        if channel_col and not getattr(prefs, channel_col, False):
            return False

        # Check category preference
        category_col = _CATEGORY_COLUMN_MAP.get(category)
        if category_col and not getattr(prefs, category_col, False):
            return False

        # Check quiet hours
        if self._is_quiet_hours(prefs):
            return False

        return True

    def _is_quiet_hours(self, prefs: ParentNotificationPreference) -> bool:
        """
        Check if the current time falls within the parent's quiet hours.

        Handles overnight ranges (e.g., 22:00 - 06:00) correctly.
        Returns False if quiet hours are not configured.
        """
        if not prefs.quiet_hours_start or not prefs.quiet_hours_end:
            return False

        # Use UTC for comparison -- timezone-aware quiet hours would require
        # per-user timezone conversion, which we can add later
        now = datetime.now(timezone.utc).time()

        start = prefs.quiet_hours_start
        end = prefs.quiet_hours_end

        if start <= end:
            # Same-day range (e.g., 08:00 - 17:00)
            return start <= now <= end
        else:
            # Overnight range (e.g., 22:00 - 06:00)
            return now >= start or now <= end

    @staticmethod
    def _parse_time(value) -> Optional[time]:
        """Parse a time value from string (HH:MM or HH:MM:SS) or time object."""
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            parts = value.strip().split(":")
            if len(parts) == 2:
                return time(int(parts[0]), int(parts[1]))
            if len(parts) == 3:
                return time(int(parts[0]), int(parts[1]), int(parts[2]))
        raise ParentServiceError(
            f"Invalid time format: {value}. Expected HH:MM or HH:MM:SS",
            code="invalid_time_format",
        )
