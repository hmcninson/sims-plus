"""
Tests for loan feature flag gating (Phase 5D).

Covers: blocked without hr_payroll feature, accessible with feature.
Uses admin session to test SubscriptionService directly.
"""

import pytest
from uuid import uuid4
import json

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _create_tenant_with_features(admin_session, *, features=None, tier="starter"):
    """Create a tenant with specific subscription tier and features."""
    tenant = await create_test_tenant(admin_session)
    tid = str(tenant["id"])

    parts = [f"subscription_tier = '{tier}'", "status = 'active'"]
    if features is not None:
        features_json = json.dumps(features)
        parts.append(f"features = '{features_json}'::jsonb")

    set_clause = ", ".join(parts)
    await admin_session.execute(
        text(f"UPDATE tenants SET {set_clause} WHERE id = CAST(:tid AS uuid)"),
        {"tid": tid},
    )
    await admin_session.commit()
    return tenant


# --- Tests ---


async def test_loans_blocked_without_hr_payroll(admin_session):
    """Starter tier without hr_payroll addon should be blocked."""
    tenant = await _create_tenant_with_features(
        admin_session,
        features={"hr_payroll": False},
        tier="starter",
    )

    from app.services.subscription import SubscriptionService

    svc = SubscriptionService(admin_session)

    with pytest.raises(Exception) as exc_info:
        await svc.check_feature_access(tenant["id"], "hr_payroll")

    assert "hr payroll" in str(exc_info.value).lower() or "not available" in str(exc_info.value).lower()


async def test_loans_accessible_with_hr_payroll(admin_session):
    """Enterprise tier with hr_payroll addon grants access."""
    tenant = await _create_tenant_with_features(
        admin_session,
        features={"hr_payroll": True},
        tier="enterprise",
    )

    from app.services.subscription import SubscriptionService

    svc = SubscriptionService(admin_session)

    # Should NOT raise
    await svc.check_feature_access(tenant["id"], "hr_payroll")
