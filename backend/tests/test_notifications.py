"""
SIMS Plus - Notification Service Tests

Tests covering:
1. CRUD operations (create, list, mark read, delete)
2. Pagination and filtering (read status, category)
3. Tenant isolation (RLS + defense-in-depth tenant_id filtering)
4. User isolation (same tenant, different users)

Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

from app.models.notification import NotificationCategory, NotificationType
from app.services.notification import NotificationService

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_notification(
    service: NotificationService,
    tenant_id,
    user_id,
    title: str = "Test Notification",
    message: str = "Test message body",
    type: NotificationType = NotificationType.INFO,
    category: NotificationCategory = NotificationCategory.GENERAL,
    reference_id=None,
    reference_type=None,
):
    """Shorthand for creating a notification with sensible defaults."""
    return await service.create(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        category=category,
        reference_id=reference_id,
        reference_type=reference_type,
    )


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------


class TestNotificationCRUD:
    """Core CRUD operations for the NotificationService."""

    async def test_create_notification(self, app_session, admin_session):
        """Creating a notification persists all fields correctly."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        ref_id = uuid4()
        notification = await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="Fee Payment Due",
            message="Your term 2 fees are overdue.",
            type=NotificationType.WARNING,
            category=NotificationCategory.FINANCE,
            reference_id=ref_id,
            reference_type="invoice",
        )

        assert notification.id is not None
        assert notification.tenant_id == tenant["id"]
        assert notification.user_id == user["id"]
        assert notification.title == "Fee Payment Due"
        assert notification.message == "Your term 2 fees are overdue."
        assert notification.type == NotificationType.WARNING
        assert notification.category == NotificationCategory.FINANCE
        assert notification.reference_id == ref_id
        assert notification.reference_type == "invoice"
        assert notification.is_read is False
        assert notification.read_at is None
        assert notification.created_at is not None

    async def test_list_notifications_pagination(self, app_session, admin_session):
        """Listing notifications respects page_size and returns correct pagination metadata."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        # Create 5 notifications
        for i in range(5):
            await _create_notification(
                service,
                tenant_id=tenant["id"],
                user_id=user["id"],
                title=f"Notification {i}",
            )

        # Page 1 with page_size=2
        result = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
            page=1,
            page_size=2,
        )

        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert result["total_pages"] == 3  # ceil(5/2)
        assert len(result["items"]) == 2

        # Page 3 should have 1 item
        result_p3 = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
            page=3,
            page_size=2,
        )
        assert len(result_p3["items"]) == 1

    async def test_list_notifications_filter_by_read(self, app_session, admin_session):
        """Filtering by is_read returns only matching notifications."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        # Create 2 notifications, mark them as read
        for i in range(2):
            n = await _create_notification(
                service,
                tenant_id=tenant["id"],
                user_id=user["id"],
                title=f"Read {i}",
            )
            await service.mark_read(tenant["id"], user["id"], n.id)

        # Create 2 unread notifications
        for i in range(2):
            await _create_notification(
                service,
                tenant_id=tenant["id"],
                user_id=user["id"],
                title=f"Unread {i}",
            )

        # Filter: unread only
        unread_result = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
            is_read=False,
        )
        assert unread_result["total"] == 2
        for item in unread_result["items"]:
            assert item.is_read is False

        # Filter: read only
        read_result = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
            is_read=True,
        )
        assert read_result["total"] == 2
        for item in read_result["items"]:
            assert item.is_read is True

    async def test_list_notifications_filter_by_category(
        self, app_session, admin_session
    ):
        """Filtering by category returns only notifications in that category."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        # Create notifications in different categories
        await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="Finance 1",
            category=NotificationCategory.FINANCE,
        )
        await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="Finance 2",
            category=NotificationCategory.FINANCE,
        )
        await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="Academic 1",
            category=NotificationCategory.ACADEMIC,
        )
        await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="Attendance 1",
            category=NotificationCategory.ATTENDANCE,
        )

        # Filter by FINANCE
        finance_result = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
            category=NotificationCategory.FINANCE,
        )
        assert finance_result["total"] == 2
        for item in finance_result["items"]:
            assert item.category == NotificationCategory.FINANCE

        # Filter by ACADEMIC
        academic_result = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
            category=NotificationCategory.ACADEMIC,
        )
        assert academic_result["total"] == 1
        assert academic_result["items"][0].title == "Academic 1"

    async def test_get_unread_count(self, app_session, admin_session):
        """Unread count reflects only unread notifications for the user."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        # Create 3 unread notifications
        for i in range(3):
            await _create_notification(
                service,
                tenant_id=tenant["id"],
                user_id=user["id"],
                title=f"Unread {i}",
            )

        # Create 1 and mark it read
        n = await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="Read one",
        )
        await service.mark_read(tenant["id"], user["id"], n.id)

        count = await service.get_unread_count(tenant["id"], user["id"])
        assert count == 3

    async def test_mark_read(self, app_session, admin_session):
        """Marking a notification as read sets is_read=True and populates read_at."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        notification = await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="To be read",
        )
        assert notification.is_read is False
        assert notification.read_at is None

        updated = await service.mark_read(tenant["id"], user["id"], notification.id)

        assert updated is not None
        assert updated.is_read is True
        assert updated.read_at is not None

    async def test_mark_read_nonexistent_returns_none(
        self, app_session, admin_session
    ):
        """Marking a non-existent notification returns None instead of raising."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        result = await service.mark_read(tenant["id"], user["id"], uuid4())
        assert result is None

    async def test_mark_all_read(self, app_session, admin_session):
        """mark_all_read updates all unread notifications and returns the count."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        # Create 3 unread notifications
        for i in range(3):
            await _create_notification(
                service,
                tenant_id=tenant["id"],
                user_id=user["id"],
                title=f"Unread {i}",
            )

        count = await service.mark_all_read(tenant["id"], user["id"])
        assert count == 3

        # Verify all are now read
        unread = await service.get_unread_count(tenant["id"], user["id"])
        assert unread == 0

        # Verify list reflects the change
        result = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
            is_read=True,
        )
        assert result["total"] == 3

    async def test_delete_notification(self, app_session, admin_session):
        """Deleting a notification removes it from the database (hard delete)."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        notification = await _create_notification(
            service,
            tenant_id=tenant["id"],
            user_id=user["id"],
            title="To be deleted",
        )
        notification_id = notification.id

        deleted = await service.delete_notification(
            tenant["id"], user["id"], notification_id
        )
        assert deleted is True

        # Verify it no longer appears in the list
        result = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user["id"],
        )
        ids = [n.id for n in result["items"]]
        assert notification_id not in ids

    async def test_delete_nonexistent_returns_false(
        self, app_session, admin_session
    ):
        """Deleting a non-existent notification returns False."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        result = await service.delete_notification(
            tenant["id"], user["id"], uuid4()
        )
        assert result is False


# ---------------------------------------------------------------------------
# Tenant Isolation Tests
# ---------------------------------------------------------------------------


class TestNotificationTenantIsolation:
    """Notifications in Tenant A must NEVER be visible to Tenant B.

    Verifies both RLS enforcement (database level) and defense-in-depth
    tenant_id filtering (service level).
    """

    async def test_notifications_in_tenant_a_not_visible_in_b(
        self, app_session, admin_session
    ):
        """A notification created in Tenant A does not appear in Tenant B's list."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])
        await admin_session.commit()

        # Create notification in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = NotificationService(app_session)

        await _create_notification(
            service,
            tenant_id=tenant_a["id"],
            user_id=user_a["id"],
            title="Tenant A Only",
        )

        # Switch to Tenant B and list
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.list_for_user(
            tenant_id=tenant_b["id"],
            user_id=user_b["id"],
        )

        assert result["total"] == 0
        assert len(result["items"]) == 0

        # Also verify unread count is 0 for Tenant B's user
        count = await service.get_unread_count(tenant_b["id"], user_b["id"])
        assert count == 0

    async def test_cannot_mark_read_cross_tenant(
        self, app_session, admin_session
    ):
        """Marking a notification as read from another tenant returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])

        # Create notification via admin session so it is committed and visible
        # for the cross-session verification query at the end.
        notification_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO notifications (id, tenant_id, user_id, title, message,
                    type, category, is_read, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:uid AS uuid),
                    :title, :msg, 'info', 'general', false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(notification_id),
                "tid": str(tenant_a["id"]),
                "uid": str(user_a["id"]),
                "title": "Cross-tenant read attempt",
                "msg": "Test message body",
            },
        )
        await admin_session.commit()

        # Switch to Tenant B and try to mark it read
        await set_app_tenant_context(app_session, tenant_b["id"])
        service = NotificationService(app_session)
        result = await service.mark_read(
            tenant_b["id"], user_b["id"], notification_id
        )

        assert result is None

        # Verify it is still unread via admin session
        row = await admin_session.execute(
            text(
                "SELECT is_read FROM notifications WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(notification_id)},
        )
        assert row.scalar() is False

    async def test_cannot_delete_cross_tenant(
        self, app_session, admin_session
    ):
        """Deleting a notification from another tenant returns False."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])

        # Create notification via admin session so it is committed and visible
        # for the cross-session verification query at the end.
        notification_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO notifications (id, tenant_id, user_id, title, message,
                    type, category, is_read, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:uid AS uuid),
                    :title, :msg, 'info', 'general', false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(notification_id),
                "tid": str(tenant_a["id"]),
                "uid": str(user_a["id"]),
                "title": "Cross-tenant delete attempt",
                "msg": "Test message body",
            },
        )
        await admin_session.commit()

        # Switch to Tenant B and try to delete
        await set_app_tenant_context(app_session, tenant_b["id"])
        service = NotificationService(app_session)
        result = await service.delete_notification(
            tenant_b["id"], user_b["id"], notification_id
        )

        assert result is False

        # Verify the notification still exists via admin session
        row = await admin_session.execute(
            text(
                "SELECT COUNT(*) FROM notifications WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(notification_id)},
        )
        assert row.scalar() == 1


# ---------------------------------------------------------------------------
# User Isolation Tests
# ---------------------------------------------------------------------------


class TestNotificationUserIsolation:
    """Within the same tenant, User A must not see User B's notifications.

    The service filters by both tenant_id and user_id, so even within a single
    tenant, notifications are private to each user.
    """

    async def test_notifications_for_user_a_not_visible_to_user_b(
        self, app_session, admin_session
    ):
        """Notifications created for User A are not listed for User B (same tenant)."""
        tenant = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant["id"])
        user_b = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)

        # Create notifications for User A
        for i in range(3):
            await _create_notification(
                service,
                tenant_id=tenant["id"],
                user_id=user_a["id"],
                title=f"User A notification {i}",
            )

        # List notifications for User B -- should be empty
        result_b = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user_b["id"],
        )
        assert result_b["total"] == 0
        assert len(result_b["items"]) == 0

        # Unread count for User B should be 0
        count_b = await service.get_unread_count(tenant["id"], user_b["id"])
        assert count_b == 0

        # Meanwhile, User A should see all 3
        result_a = await service.list_for_user(
            tenant_id=tenant["id"],
            user_id=user_a["id"],
        )
        assert result_a["total"] == 3

    async def test_cannot_mark_read_other_users_notification(
        self, app_session, admin_session
    ):
        """User B cannot mark User A's notification as read (same tenant)."""
        tenant = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant["id"])
        user_b = await create_test_user(admin_session, tenant["id"])

        # Create notification via admin session so it is committed and visible
        # for the cross-session verification query at the end.
        notification_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO notifications (id, tenant_id, user_id, title, message,
                    type, category, is_read, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:uid AS uuid),
                    :title, :msg, 'info', 'general', false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(notification_id),
                "tid": str(tenant["id"]),
                "uid": str(user_a["id"]),
                "title": "Private to User A",
                "msg": "Test message body",
            },
        )
        await admin_session.commit()

        # User B tries to mark it read -- should return None
        await set_app_tenant_context(app_session, tenant["id"])
        service = NotificationService(app_session)
        result = await service.mark_read(
            tenant["id"], user_b["id"], notification_id
        )
        assert result is None

        # Verify it is still unread via admin session
        row = await admin_session.execute(
            text(
                "SELECT is_read FROM notifications WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(notification_id)},
        )
        assert row.scalar() is False
