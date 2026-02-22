"""
Audit Log Endpoint Tests

Tests for the audit log query logic: listing, pagination, filtering by
action/user_id/date_range, and tenant isolation.

The audit_logs table does NOT use RLS -- tenant isolation is enforced at the
application layer via explicit tenant_id filtering. Because of this, all
queries can use admin_session (superuser) to reproduce the endpoint's logic.

Uses the two-engine pattern:
- admin_session: superuser, seeds audit log entries and runs queries
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.models.audit_log import AuditLog

from tests.conftest import (
    create_test_tenant,
    create_test_user,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
]


# =========================
# Helper: seed audit log entries via admin
# =========================

_AUDIT_LOG_INSERT = text("""
    INSERT INTO audit_logs (
        id, tenant_id, user_id, action, resource_type,
        resource_id, ip_address, details, created_at
    ) VALUES (
        CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:uid AS uuid),
        :action, :rtype,
        NULL, :ip, :details, :created_at
    )
""")


async def seed_audit_log(
    admin_session,
    *,
    tenant_id,
    user_id=None,
    action="auth.login.success",
    resource_type="user",
    ip_address="127.0.0.1",
    details=None,
    created_at=None,
):
    """Seed a single audit log entry. Returns the generated log id."""
    log_id = uuid4()
    ts = created_at or datetime.now(timezone.utc)

    await admin_session.execute(
        _AUDIT_LOG_INSERT,
        {
            "id": str(log_id),
            "tid": str(tenant_id),
            "uid": str(user_id) if user_id else None,
            "action": action,
            "rtype": resource_type,
            "ip": ip_address,
            "details": details,
            "created_at": ts,
        },
    )
    await admin_session.flush()
    return log_id


# =========================
# Query helpers (reproduce endpoint logic)
# =========================
# These helpers replicate the exact filtering logic from the audit endpoint
# so that tests validate the same code path the API exposes.


async def query_audit_logs(
    session,
    tenant_id,
    *,
    page=1,
    page_size=50,
    action=None,
    user_id=None,
    date_from=None,
    date_to=None,
):
    """Reproduce the list_audit_logs endpoint query logic.

    Returns (logs, total, total_pages).
    """
    # Defense-in-depth: filter by tenant_id since audit_logs has no RLS
    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    count_query = select(func.count()).select_from(AuditLog).where(
        AuditLog.tenant_id == tenant_id
    )

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)

    if date_from:
        query = query.where(func.date(AuditLog.created_at) >= date_from)
        count_query = count_query.where(func.date(AuditLog.created_at) >= date_from)

    if date_to:
        query = query.where(func.date(AuditLog.created_at) <= date_to)
        count_query = count_query.where(func.date(AuditLog.created_at) <= date_to)

    total = (await session.execute(count_query)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    offset = (page - 1) * page_size
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

    result = await session.execute(query)
    logs = list(result.scalars().all())

    return logs, total, total_pages


# =========================
# Tests
# =========================


class TestAuditLogQueries:
    """Tests for audit log listing, pagination, filtering, and tenant isolation."""

    async def test_list_audit_logs_for_tenant(self, admin_session):
        """Seeding 3 audit logs for a tenant returns exactly those 3 entries."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Seed 3 audit log entries
        log_ids = []
        for i in range(3):
            log_id = await seed_audit_log(
                admin_session,
                tenant_id=tenant["id"],
                user_id=user["id"],
                action=f"test.action.{i}",
                details=f"Test log entry {i}",
            )
            log_ids.append(log_id)
        await admin_session.commit()

        logs, total, total_pages = await query_audit_logs(
            admin_session, tenant["id"]
        )

        assert total >= 3, f"Expected at least 3 logs, got {total}"
        returned_ids = {log.id for log in logs}
        for log_id in log_ids:
            assert log_id in returned_ids, (
                f"Seeded log {log_id} not found in results"
            )

    async def test_audit_logs_pagination(self, admin_session):
        """Paginating with page_size=2 across 5 logs returns correct pages."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Seed 5 audit log entries with staggered timestamps so ordering is
        # deterministic (newest first)
        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        all_ids = []
        for i in range(5):
            log_id = await seed_audit_log(
                admin_session,
                tenant_id=tenant["id"],
                user_id=user["id"],
                action="test.pagination",
                created_at=base_time + timedelta(minutes=i),
            )
            all_ids.append(log_id)
        await admin_session.commit()

        # Page 1: should get 2 items (the two newest)
        page1_logs, total, total_pages = await query_audit_logs(
            admin_session,
            tenant["id"],
            page=1,
            page_size=2,
            action="test.pagination",
        )

        assert total == 5
        assert total_pages == 3  # ceil(5/2) = 3
        assert len(page1_logs) == 2

        # Newest first: page 1 should have logs 4, 3 (0-indexed from seeding)
        assert page1_logs[0].id == all_ids[4]
        assert page1_logs[1].id == all_ids[3]

        # Page 2: should get 2 items
        page2_logs, _, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            page=2,
            page_size=2,
            action="test.pagination",
        )
        assert len(page2_logs) == 2
        assert page2_logs[0].id == all_ids[2]
        assert page2_logs[1].id == all_ids[1]

        # Page 3: should get 1 item (the oldest)
        page3_logs, _, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            page=3,
            page_size=2,
            action="test.pagination",
        )
        assert len(page3_logs) == 1
        assert page3_logs[0].id == all_ids[0]

    async def test_filter_by_action(self, admin_session):
        """Filtering by action returns only matching entries."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Seed logs with different actions
        login_id = await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="auth.login.success",
        )
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="auth.logout",
        )
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="data.export",
        )
        await admin_session.commit()

        # Filter by auth.login.success
        logs, total, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            action="auth.login.success",
        )

        assert total >= 1
        # Every returned log must have the requested action
        for log in logs:
            assert log.action == "auth.login.success"
        assert login_id in {log.id for log in logs}

    async def test_filter_by_user_id(self, admin_session):
        """Filtering by user_id returns only logs from that user."""
        tenant = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant["id"])
        user_b = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Seed logs from both users
        user_a_log = await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user_a["id"],
            action="auth.login.success",
        )
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user_b["id"],
            action="auth.login.success",
        )
        await admin_session.commit()

        # Filter by user_a
        logs, total, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            user_id=user_a["id"],
        )

        assert total >= 1
        # Every returned log must belong to user_a
        for log in logs:
            assert log.user_id == user_a["id"]
        assert user_a_log in {log.id for log in logs}

    async def test_filter_by_date_range(self, admin_session):
        """Filtering by date_from and date_to returns only logs within that range."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Seed logs at specific dates:
        # Jan 10 -- outside range (before)
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_range",
            created_at=datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        )
        # Jan 15 -- inside range
        jan15_id = await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_range",
            created_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        # Jan 20 -- inside range
        jan20_id = await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_range",
            created_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        # Jan 25 -- outside range (after)
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_range",
            created_at=datetime(2026, 1, 25, 12, 0, 0, tzinfo=timezone.utc),
        )
        await admin_session.commit()

        # Query with date_from=Jan 14, date_to=Jan 21
        logs, total, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            action="test.date_range",
            date_from=date(2026, 1, 14),
            date_to=date(2026, 1, 21),
        )

        assert total == 2
        returned_ids = {log.id for log in logs}
        assert jan15_id in returned_ids, "Jan 15 log should be in range"
        assert jan20_id in returned_ids, "Jan 20 log should be in range"

    async def test_filter_by_date_from_only(self, admin_session):
        """Filtering with only date_from returns logs on or after that date."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Seed logs at specific dates
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_from_only",
            created_at=datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc),
        )
        mar10_id = await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_from_only",
            created_at=datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc),
        )
        await admin_session.commit()

        logs, total, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            action="test.date_from_only",
            date_from=date(2026, 3, 5),
        )

        assert total == 1
        assert logs[0].id == mar10_id

    async def test_filter_by_date_to_only(self, admin_session):
        """Filtering with only date_to returns logs on or before that date."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        apr1_id = await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_to_only",
            created_at=datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc),
        )
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user["id"],
            action="test.date_to_only",
            created_at=datetime(2026, 4, 20, 8, 0, 0, tzinfo=timezone.utc),
        )
        await admin_session.commit()

        logs, total, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            action="test.date_to_only",
            date_to=date(2026, 4, 10),
        )

        assert total == 1
        assert logs[0].id == apr1_id

    async def test_tenant_isolation(self, admin_session):
        """Tenant A's audit logs are invisible to queries scoped to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])
        await admin_session.commit()

        # Seed logs for both tenants with a unique action to isolate from
        # other test data
        unique_action = f"test.isolation.{uuid4().hex[:8]}"

        log_a = await seed_audit_log(
            admin_session,
            tenant_id=tenant_a["id"],
            user_id=user_a["id"],
            action=unique_action,
            details="Tenant A log",
        )
        log_b = await seed_audit_log(
            admin_session,
            tenant_id=tenant_b["id"],
            user_id=user_b["id"],
            action=unique_action,
            details="Tenant B log",
        )
        await admin_session.commit()

        # Query as Tenant A -- should only see Tenant A's log
        logs_a, total_a, _ = await query_audit_logs(
            admin_session,
            tenant_a["id"],
            action=unique_action,
        )
        assert total_a == 1
        assert logs_a[0].id == log_a
        assert logs_a[0].details == "Tenant A log"

        # Query as Tenant B -- should only see Tenant B's log
        logs_b, total_b, _ = await query_audit_logs(
            admin_session,
            tenant_b["id"],
            action=unique_action,
        )
        assert total_b == 1
        assert logs_b[0].id == log_b
        assert logs_b[0].details == "Tenant B log"

        # Cross-check: Tenant A's query must NOT contain Tenant B's log
        a_ids = {log.id for log in logs_a}
        assert log_b not in a_ids, "Tenant A must not see Tenant B's audit logs"

    async def test_empty_result_returns_page_one(self, admin_session):
        """Querying a tenant with no audit logs returns total=0, total_pages=1."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Use a unique action that no log will ever match
        logs, total, total_pages = await query_audit_logs(
            admin_session,
            tenant["id"],
            action=f"nonexistent.action.{uuid4().hex[:8]}",
        )

        assert total == 0
        assert total_pages == 1
        assert len(logs) == 0

    async def test_logs_ordered_newest_first(self, admin_session):
        """Audit logs are returned in descending created_at order (newest first)."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        unique_action = f"test.ordering.{uuid4().hex[:8]}"
        base_time = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)

        ids_in_chrono_order = []
        for i in range(4):
            log_id = await seed_audit_log(
                admin_session,
                tenant_id=tenant["id"],
                user_id=user["id"],
                action=unique_action,
                created_at=base_time + timedelta(hours=i),
            )
            ids_in_chrono_order.append(log_id)
        await admin_session.commit()

        logs, total, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            action=unique_action,
        )

        assert total == 4
        # Newest first means reverse chronological order
        expected_order = list(reversed(ids_in_chrono_order))
        actual_order = [log.id for log in logs]
        assert actual_order == expected_order, (
            f"Expected newest-first ordering {expected_order}, got {actual_order}"
        )

    async def test_combined_filters(self, admin_session):
        """Combining action, user_id, and date range filters works correctly."""
        tenant = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant["id"])
        user_b = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        target_action = f"test.combined.{uuid4().hex[:8]}"
        other_action = f"test.other.{uuid4().hex[:8]}"

        # Log 1: user_a, target_action, in date range -- MATCH
        match_id = await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user_a["id"],
            action=target_action,
            created_at=datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        # Log 2: user_a, target_action, out of date range -- no match
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user_a["id"],
            action=target_action,
            created_at=datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc),
        )
        # Log 3: user_b, target_action, in date range -- wrong user
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user_b["id"],
            action=target_action,
            created_at=datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        # Log 4: user_a, other_action, in date range -- wrong action
        await seed_audit_log(
            admin_session,
            tenant_id=tenant["id"],
            user_id=user_a["id"],
            action=other_action,
            created_at=datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        await admin_session.commit()

        logs, total, _ = await query_audit_logs(
            admin_session,
            tenant["id"],
            action=target_action,
            user_id=user_a["id"],
            date_from=date(2026, 5, 10),
            date_to=date(2026, 5, 20),
        )

        assert total == 1
        assert logs[0].id == match_id
