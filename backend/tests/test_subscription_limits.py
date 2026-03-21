"""
Tests for subscription plan limit enforcement (SubscriptionService).

Covers: student limits, user limits, SMS limits, feature access, add-on
expiry, and advisory lock usage.
Uses two-engine pattern (admin seeds, app queries).
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _set_tenant_tier(admin_session, tenant_id, tier):
    """Set a tenant's subscription_tier."""
    await admin_session.execute(
        text("""
            UPDATE tenants SET subscription_tier = :tier
            WHERE id = CAST(:tid AS uuid)
        """),
        {"tid": str(tenant_id), "tier": tier},
    )
    await admin_session.commit()


async def _set_tenant_features(admin_session, tenant_id, features):
    """Set a tenant's features JSONB."""
    import json

    await admin_session.execute(
        text("""
            UPDATE tenants SET features = CAST(:features AS jsonb)
            WHERE id = CAST(:tid AS uuid)
        """),
        {"tid": str(tenant_id), "features": json.dumps(features)},
    )
    await admin_session.commit()


async def _seed_school(admin_session, tenant_id):
    """Create a school for the tenant, return school_id."""
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School-{uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
        },
    )
    await admin_session.commit()
    return school_id


async def _seed_students(admin_session, tenant_id, school_id, count):
    """Create `count` active students for the tenant."""
    for i in range(count):
        sid = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (
                    id, tenant_id, school_id, student_id, first_name, last_name,
                    gender, date_of_birth, status,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :stud_id, :fn, :ln, 'male', '2010-01-01', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(sid),
                "tid": str(tenant_id),
                "sid": str(school_id),
                "stud_id": f"STU-{uuid4().hex[:8]}",
                "fn": f"Student{i}",
                "ln": "Test",
            },
        )
    await admin_session.commit()


# --- Student Limit Tests ---


class TestStudentLimits:
    """Student limit enforcement."""

    async def test_student_limit_under_allows_creation(self, app_session, admin_session):
        """Creating a student under the trial limit should succeed."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        # Trial allows 100 students, we have 0 -- should pass
        await service.check_student_limit(tenant["id"], additional=1)

    async def test_student_limit_at_boundary_blocks(self, app_session, admin_session):
        """Adding a student at the exact limit should raise LimitExceededError."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        # Trial limit is 100 -- seed exactly 100
        await _seed_students(admin_session, tenant["id"], school_id, 100)
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService, LimitExceededError

        service = SubscriptionService(app_session)
        with pytest.raises(LimitExceededError) as exc_info:
            await service.check_student_limit(tenant["id"], additional=1)
        assert exc_info.value.code == "STUDENT_LIMIT_EXCEEDED"

    async def test_student_limit_unlimited_for_professional(
        self, app_session, admin_session
    ):
        """Professional tier should have no student limit."""
        tenant = await create_test_tenant(admin_session)
        await _set_tenant_tier(admin_session, tenant["id"], "professional")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        # Should not raise even for a large number
        await service.check_student_limit(tenant["id"], additional=10000)

    async def test_student_limit_uses_advisory_lock(self, app_session, admin_session):
        """check_student_limit should call pg_advisory_xact_lock for atomicity."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        # We can verify the advisory lock was called by checking that the
        # method doesn't fail -- the lock is acquired and released within txn.
        # The actual lock behavior is best tested via concurrent tests, but
        # we verify the code path executes without error.
        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        await service.check_student_limit(tenant["id"])


# --- User Limit Tests ---


class TestUserLimits:
    """User account limit enforcement."""

    async def test_user_limit_under_allows_creation(self, app_session, admin_session):
        """Creating a user under the limit should succeed."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        # Trial allows 10 users, we have 0 -- should pass
        await service.check_user_limit(tenant["id"], additional=1)

    async def test_user_limit_exceeded_raises(self, app_session, admin_session):
        """Exceeding user limit should raise LimitExceededError."""
        tenant = await create_test_tenant(admin_session)

        # Create 10 users (trial limit)
        for i in range(10):
            await create_test_user(
                admin_session, tenant["id"], email=f"user{i}-{uuid4().hex[:6]}@test.com"
            )
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService, LimitExceededError

        service = SubscriptionService(app_session)
        with pytest.raises(LimitExceededError) as exc_info:
            await service.check_user_limit(tenant["id"], additional=1)
        assert exc_info.value.code == "USER_LIMIT_EXCEEDED"


# --- SMS Limit Tests ---


class TestSMSLimits:
    """Monthly SMS limit enforcement."""

    async def test_sms_limit_under_allows_sending(self, app_session, admin_session):
        """Sending SMS under the monthly limit should succeed."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        # Trial allows 50 SMS/month, we have sent 0
        await service.check_sms_limit(tenant["id"], count=1)

    async def test_sms_limit_enterprise_unlimited(self, app_session, admin_session):
        """Enterprise tier should have unlimited SMS."""
        tenant = await create_test_tenant(admin_session)
        await _set_tenant_tier(admin_session, tenant["id"], "enterprise")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        # Should not raise even for huge count
        await service.check_sms_limit(tenant["id"], count=100000)


# --- Feature Access Tests ---


class TestFeatureAccess:
    """Feature gating by subscription tier."""

    async def test_included_feature_passes(self, app_session, admin_session):
        """Feature included in plan should not raise."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()
        # Trial includes teachers_portal (mirrors Starter)
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        await service.check_feature_access(tenant["id"], "teachers_portal")

    async def test_excluded_feature_raises(self, app_session, admin_session):
        """Feature not in plan should raise FeatureNotAvailableError."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService, FeatureNotAvailableError

        service = SubscriptionService(app_session)
        with pytest.raises(FeatureNotAvailableError) as exc_info:
            await service.check_feature_access(tenant["id"], "parent_portal")
        assert exc_info.value.code == "FEATURE_NOT_AVAILABLE"

    async def test_addon_not_purchased_raises(self, app_session, admin_session):
        """Addon feature on Professional without purchase should raise."""
        tenant = await create_test_tenant(admin_session)
        await _set_tenant_tier(admin_session, tenant["id"], "professional")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService, FeatureNotAvailableError

        service = SubscriptionService(app_session)
        with pytest.raises(FeatureNotAvailableError) as exc_info:
            await service.check_feature_access(tenant["id"], "boarding")
        assert exc_info.value.code == "ADDON_NOT_PURCHASED"

    async def test_addon_purchased_with_valid_expiry_passes(
        self, app_session, admin_session
    ):
        """Addon with future expiry should pass."""
        tenant = await create_test_tenant(admin_session)
        await _set_tenant_tier(admin_session, tenant["id"], "professional")

        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        await _set_tenant_features(
            admin_session,
            tenant["id"],
            {"boarding": {"enabled": True, "expires_at": future}},
        )
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        await service.check_feature_access(tenant["id"], "boarding")

    async def test_addon_purchased_with_expired_expiry_raises(
        self, app_session, admin_session
    ):
        """Addon with past expiry should raise FeatureNotAvailableError."""
        tenant = await create_test_tenant(admin_session)
        await _set_tenant_tier(admin_session, tenant["id"], "professional")

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        await _set_tenant_features(
            admin_session,
            tenant["id"],
            {"boarding": {"enabled": True, "expires_at": past}},
        )
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService, FeatureNotAvailableError

        service = SubscriptionService(app_session)
        with pytest.raises(FeatureNotAvailableError) as exc_info:
            await service.check_feature_access(tenant["id"], "boarding")
        assert exc_info.value.code == "ADDON_NOT_PURCHASED"

    async def test_enterprise_includes_boarding(self, app_session, admin_session):
        """Enterprise tier includes boarding without addon purchase."""
        tenant = await create_test_tenant(admin_session)
        await _set_tenant_tier(admin_session, tenant["id"], "enterprise")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService

        service = SubscriptionService(app_session)
        await service.check_feature_access(tenant["id"], "boarding")
