"""
SIMS Plus - Notification Dispatcher

Multi-channel notification dispatcher that respects parent preferences.
Sends via: in-app notification, email, SMS, push notification.
Respects: channel preferences, category preferences, quiet hours.
Urgent priority bypasses quiet hours.

All external channels are best-effort. Failure in one channel does not
block delivery through other channels. Failures are logged for
operational visibility.
"""

import html as html_mod
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import NotificationCategory, NotificationType
from app.models.parent import ParentNotificationPreference
from app.models.student import StudentGuardian
from app.models.user import User, UserRole
from app.services.email import email_service
from app.services.notification import NotificationService
from app.services.parent.notification_preferences import (
    NotificationPreferencesService,
    _CATEGORY_COLUMN_MAP,
    _CHANNEL_COLUMN_MAP,
)
from app.services.push_notification import PushNotificationService
from app.services.sms import SMSService

logger = structlog.get_logger()

# Map dispatcher category strings to NotificationCategory enum values
_CATEGORY_MAP = {
    "attendance": NotificationCategory.ATTENDANCE,
    "grades": NotificationCategory.EXAM,
    "finance": NotificationCategory.FINANCE,
    "announcements": NotificationCategory.GENERAL,
    "transport": NotificationCategory.GENERAL,
    "boarding": NotificationCategory.GENERAL,
    "academic": NotificationCategory.ACADEMIC,
    "admin": NotificationCategory.ADMIN,
    "general": NotificationCategory.GENERAL,
}

# Map priority strings to NotificationType for in-app display styling
_PRIORITY_TYPE_MAP = {
    "normal": NotificationType.INFO,
    "important": NotificationType.WARNING,
    "urgent": NotificationType.ERROR,
}

# SMS messages are truncated to this length to fit within a single segment
_SMS_MAX_LENGTH = 160


class NotificationDispatcher:
    """
    Multi-channel notification dispatcher that respects parent preferences.

    Sends via: in-app notification, email, SMS, push notification.
    Respects: channel preferences, category preferences, quiet hours.
    Urgent priority bypasses quiet hours.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._notification_service = NotificationService(db)
        self._preferences_service = NotificationPreferencesService(db)
        self._push_service = PushNotificationService(db)
        self._sms_service = SMSService(db)

    async def dispatch(
        self,
        user_id: UUID,
        tenant_id: UUID,
        title: str,
        body: str,
        category: str,
        priority: str = "normal",
        link: Optional[str] = None,
    ) -> None:
        """
        Send notification via all enabled channels for a user.

        1. Always create in-app notification (regardless of preferences).
        2. For each external channel (email, SMS, push):
           a. Check if the user is a parent with notification preferences.
           b. If urgent priority: bypass quiet hours.
           c. If channel + category enabled and not in quiet hours: send.
        3. All channels are best-effort. Failure in one does not block others.

        Args:
            user_id: Target user's ID
            tenant_id: Tenant UUID for multi-tenant scoping
            title: Notification title (displayed in-app and push)
            body: Notification body text
            category: Category string (attendance, grades, finance, etc.)
            priority: Priority level (normal, important, urgent)
            link: Optional URL/path for in-app notification click-through
        """
        # Step 1: Always create in-app notification
        notification_category = _CATEGORY_MAP.get(category, NotificationCategory.GENERAL)
        notification_type = _PRIORITY_TYPE_MAP.get(priority, NotificationType.INFO)

        try:
            await self._notification_service.create(
                tenant_id=tenant_id,
                user_id=user_id,
                title=title,
                message=body,
                type=notification_type,
                category=notification_category,
            )
        except Exception:
            # In-app notification failure is logged but should not prevent
            # other channels from firing
            logger.exception(
                "in_app_notification_failed",
                user_id=str(user_id),
                category=category,
            )

        # Step 2: Determine if this user is a parent with preference management.
        # Non-parent users only get in-app notifications through this dispatcher.
        user = await self._get_user(user_id, tenant_id)
        if not user:
            logger.warning(
                "dispatch_user_not_found",
                user_id=str(user_id),
                tenant_id=str(tenant_id),
            )
            return

        is_parent = user.role == UserRole.PARENT
        is_urgent = priority == "urgent"

        # Step 3: Email channel
        await self._try_email(
            user=user,
            tenant_id=tenant_id,
            title=title,
            body=body,
            category=category,
            is_parent=is_parent,
            is_urgent=is_urgent,
        )

        # Step 4: SMS channel
        await self._try_sms(
            user=user,
            tenant_id=tenant_id,
            title=title,
            body=body,
            category=category,
            is_parent=is_parent,
            is_urgent=is_urgent,
        )

        # Step 5: Push channel
        await self._try_push(
            user=user,
            tenant_id=tenant_id,
            title=title,
            body=body,
            category=category,
            link=link,
            is_parent=is_parent,
            is_urgent=is_urgent,
        )

    async def dispatch_to_parents_of_student(
        self,
        student_id: UUID,
        tenant_id: UUID,
        title: str,
        body: str,
        category: str,
        priority: str = "normal",
    ) -> None:
        """
        Dispatch a notification to ALL parents/guardians of a student.

        Finds all guardians linked to the student, resolves their user accounts
        via email matching (Guardian.email == User.email within tenant), and
        dispatches through all channels for each parent.

        Args:
            student_id: The student whose parents should be notified
            tenant_id: Tenant UUID for multi-tenant scoping
            title: Notification title
            body: Notification body text
            category: Category string (attendance, grades, finance, etc.)
            priority: Priority level (normal, important, urgent)
        """
        # Find all guardians linked to this student
        guardian_links = await self.db.execute(
            select(StudentGuardian)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.student_id == student_id,
                )
            )
            .options(selectinload(StudentGuardian.guardian_rel))
        )
        links = list(guardian_links.scalars().all())

        if not links:
            logger.info(
                "no_guardians_for_student",
                student_id=str(student_id),
                tenant_id=str(tenant_id),
            )
            return

        # Collect unique guardian emails and resolve to user accounts
        dispatched_user_ids: set[UUID] = set()

        for link in links:
            guardian = link.guardian_rel
            if not guardian or not guardian.email:
                continue

            # Find the parent user account by matching guardian email
            user = await self._get_user_by_email(guardian.email, tenant_id)
            if not user or user.role != UserRole.PARENT:
                continue

            # Avoid dispatching to the same user twice (a parent could be linked
            # via multiple guardian records if data is denormalized)
            if user.id in dispatched_user_ids:
                continue
            dispatched_user_ids.add(user.id)

            await self.dispatch(
                user_id=user.id,
                tenant_id=tenant_id,
                title=title,
                body=body,
                category=category,
                priority=priority,
            )

        logger.info(
            "parent_notifications_dispatched",
            student_id=str(student_id),
            parent_count=len(dispatched_user_ids),
            category=category,
            priority=priority,
        )

    # =========================
    # Private Channel Methods
    # =========================

    async def _try_email(
        self,
        user: User,
        tenant_id: UUID,
        title: str,
        body: str,
        category: str,
        is_parent: bool,
        is_urgent: bool,
    ) -> None:
        """
        Attempt to send notification via email.

        For parents: checks channel + category preferences and quiet hours.
        Urgent notifications bypass quiet hours.
        For non-parents: skips (only in-app is sent for non-parents).
        """
        if not user.email:
            return

        if is_parent:
            should_send = await self._should_notify_parent(
                user.id, tenant_id, "email", category, is_urgent
            )
            if not should_send:
                return

        # Non-parent users do not receive external channel notifications
        # through this dispatcher -- they use in-app only
        if not is_parent:
            return

        try:
            html_content = self._build_email_html(title, body)
            await email_service.send_email(
                to_email=user.email,
                subject=title,
                html_content=html_content,
            )
        except Exception:
            logger.warning(
                "dispatch_email_failed",
                user_id=str(user.id),
                category=category,
                exc_info=True,
            )

    async def _try_sms(
        self,
        user: User,
        tenant_id: UUID,
        title: str,
        body: str,
        category: str,
        is_parent: bool,
        is_urgent: bool,
    ) -> None:
        """
        Attempt to send notification via SMS.

        Truncates the message to 160 characters for single-segment delivery.
        For parents: checks channel + category preferences and quiet hours.
        Urgent notifications bypass quiet hours.
        """
        if not is_parent or not user.phone:
            return

        should_send = await self._should_notify_parent(
            user.id, tenant_id, "sms", category, is_urgent
        )
        if not should_send:
            return

        try:
            # Build SMS text: title + body, truncated to single segment
            sms_text = f"{title}: {body}"
            if len(sms_text) > _SMS_MAX_LENGTH:
                sms_text = sms_text[: _SMS_MAX_LENGTH - 3] + "..."

            await self._sms_service.send_sms(
                tenant_id=tenant_id,
                recipient_phone=user.phone,
                message=sms_text,
            )
        except Exception:
            logger.warning(
                "dispatch_sms_failed",
                user_id=str(user.id),
                category=category,
                exc_info=True,
            )

    async def _try_push(
        self,
        user: User,
        tenant_id: UUID,
        title: str,
        body: str,
        category: str,
        link: Optional[str],
        is_parent: bool,
        is_urgent: bool,
    ) -> None:
        """
        Attempt to send notification via web push.

        For parents: checks channel + category preferences and quiet hours.
        Urgent notifications bypass quiet hours.
        """
        if is_parent:
            should_send = await self._should_notify_parent(
                user.id, tenant_id, "push", category, is_urgent
            )
            if not should_send:
                return
        else:
            # Non-parents do not get push through this dispatcher
            return

        try:
            await self._push_service.send_to_user(
                user_id=user.id,
                tenant_id=tenant_id,
                title=title,
                body=body,
                url=link or "/dashboard",
                tag=category,
            )
        except Exception:
            logger.warning(
                "dispatch_push_failed",
                user_id=str(user.id),
                category=category,
                exc_info=True,
            )

    async def _should_notify_parent(
        self,
        user_id: UUID,
        tenant_id: UUID,
        channel: str,
        category: str,
        is_urgent: bool,
    ) -> bool:
        """
        Check if a parent should receive a notification through the given channel.

        Urgent notifications bypass quiet hours (but still respect channel
        and category preferences -- if a parent has disabled SMS entirely,
        urgent notifications still will not go via SMS).
        """
        if is_urgent:
            # Bypass quiet hours for urgent, but still check channel + category
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
                return False

            # Check channel enabled (urgent bypasses quiet hours, not channel toggles)
            channel_col = _CHANNEL_COLUMN_MAP.get(channel)
            if channel_col and not getattr(prefs, channel_col, False):
                return False

            # Check category enabled
            category_col = _CATEGORY_COLUMN_MAP.get(category)
            if category_col and not getattr(prefs, category_col, False):
                return False

            return True

        # Normal/important: full preference check including quiet hours
        return await self._preferences_service.should_notify(
            user_id, tenant_id, channel, category
        )

    # =========================
    # Private Helper Methods
    # =========================

    async def _get_user(
        self, user_id: UUID, tenant_id: UUID
    ) -> Optional[User]:
        """Get a user by ID within a tenant."""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == user_id,
                    User.tenant_id == tenant_id,
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_user_by_email(
        self, email: str, tenant_id: UUID
    ) -> Optional[User]:
        """Get a user by email within a tenant."""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.email == email.lower(),
                    User.tenant_id == tenant_id,
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _build_email_html(title: str, body: str) -> str:
        """Build a simple HTML email from title and body text.

        SECURITY: title and body are HTML-escaped to prevent injection attacks.
        Content may originate from user input (e.g., announcement titles,
        teacher note content) and must not be trusted as raw HTML.
        """
        safe_title = html_mod.escape(title)
        safe_body = html_mod.escape(body)
        return f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>{safe_title}</title></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1B4F72; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">SIMS Plus</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Notification</p>
                </div>
                <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <h2 style="color: #1B4F72; margin-top: 0;">{safe_title}</h2>
                    <p>{safe_body}</p>
                </div>
                <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                    <p>&copy; {datetime.now().year} SIMS Plus</p>
                </div>
            </div>
        </body>
        </html>
        """
