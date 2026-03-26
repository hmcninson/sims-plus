"""
Tests for check_multi_curriculum_access across all services.

Verifies that Trial and Starter tenants are blocked from multi-curriculum features,
while Professional and Enterprise tenants are allowed.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import set_app_tenant_context

from app.services.curriculum._shared import CurriculumServiceError, check_multi_curriculum_access

pytestmark = [pytest.mark.asyncio]


async def _create_tenant_with_tier(admin_session, tier: str):
    tenant_id = uuid4()
    sub = f"test{uuid4().hex[:8]}"
    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                true, 'single_school', :tier, 500,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub,
         "name": f"School {sub}", "tier": tier},
    )
    await admin_session.flush()
    return {"id": tenant_id, "subdomain": sub}


class TestCheckMultiCurriculumAccess:
    """Test the plan gating function used by equivalency, predicted grade, and external exam services."""

    async def test_trial_tenant_blocked(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "trial")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        with pytest.raises(CurriculumServiceError) as exc:
            await check_multi_curriculum_access(app_session, tenant["id"])
        assert exc.value.code == "plan_limit"

    async def test_starter_tenant_blocked(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "starter")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        with pytest.raises(CurriculumServiceError) as exc:
            await check_multi_curriculum_access(app_session, tenant["id"])
        assert exc.value.code == "plan_limit"

    async def test_professional_tenant_allowed(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        # Should not raise
        await check_multi_curriculum_access(app_session, tenant["id"])

    async def test_enterprise_tenant_allowed(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "enterprise")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        # Should not raise
        await check_multi_curriculum_access(app_session, tenant["id"])

    async def test_nonexistent_tenant_raises_not_found(self, app_session, admin_session):
        """Passing a tenant_id that doesn't exist raises not_found."""
        await admin_session.commit()

        fake_tenant_id = uuid4()
        # We need a valid context to query, use any tenant
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        with pytest.raises(CurriculumServiceError) as exc:
            await check_multi_curriculum_access(app_session, fake_tenant_id)
        assert exc.value.code == "not_found"
