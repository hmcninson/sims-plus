"""
Tests for subscription pricing calculations.

Covers: per-student per-term pricing, annual discount, add-on costs.
Pure unit tests against constants -- no database needed.
"""

import pytest


class TestPricingConstants:
    """Verify pricing constants match the tiers document."""

    def test_starter_per_term_price(self):
        """Starter: GHS 5/student/term = 500 pesewas."""
        from app.constants.subscription import PRICE_PER_STUDENT_PER_TERM
        from app.models.tenant import SubscriptionTier

        assert PRICE_PER_STUDENT_PER_TERM[SubscriptionTier.STARTER] == 500

    def test_professional_per_term_price(self):
        """Professional: GHS 10/student/term = 1000 pesewas."""
        from app.constants.subscription import PRICE_PER_STUDENT_PER_TERM
        from app.models.tenant import SubscriptionTier

        assert PRICE_PER_STUDENT_PER_TERM[SubscriptionTier.PROFESSIONAL] == 1000

    def test_enterprise_per_term_price(self):
        """Enterprise: GHS 15/student/term = 1500 pesewas."""
        from app.constants.subscription import PRICE_PER_STUDENT_PER_TERM
        from app.models.tenant import SubscriptionTier

        assert PRICE_PER_STUDENT_PER_TERM[SubscriptionTier.ENTERPRISE] == 1500

    def test_annual_pricing_includes_10_percent_discount(self):
        """Annual price = 3 terms * per_term * 0.9 (10% off)."""
        from app.constants.subscription import (
            PRICE_PER_STUDENT_PER_TERM,
            PRICE_PER_STUDENT_PER_YEAR,
        )
        from app.models.tenant import SubscriptionTier

        for tier in [
            SubscriptionTier.STARTER,
            SubscriptionTier.PROFESSIONAL,
            SubscriptionTier.ENTERPRISE,
        ]:
            expected = int(PRICE_PER_STUDENT_PER_TERM[tier] * 3 * 0.9)
            assert PRICE_PER_STUDENT_PER_YEAR[tier] == expected, (
                f"{tier.value}: expected {expected}, got {PRICE_PER_STUDENT_PER_YEAR[tier]}"
            )

    def test_starter_annual_price(self):
        """Starter annual: GHS 13.50/student/year = 1350 pesewas."""
        from app.constants.subscription import PRICE_PER_STUDENT_PER_YEAR
        from app.models.tenant import SubscriptionTier

        assert PRICE_PER_STUDENT_PER_YEAR[SubscriptionTier.STARTER] == 1350


class TestAddonPricing:
    """Verify add-on pricing constants."""

    def test_boarding_addon_price(self):
        """Boarding: GHS 300/term = 30000 pesewas."""
        from app.constants.subscription import ADDON_PRICING_PER_TERM

        assert ADDON_PRICING_PER_TERM["boarding"] == 30000

    def test_transport_addon_price(self):
        """Transport: GHS 200/term = 20000 pesewas."""
        from app.constants.subscription import ADDON_PRICING_PER_TERM

        assert ADDON_PRICING_PER_TERM["transport"] == 20000

    def test_preschool_addon_price(self):
        """Preschool: GHS 200/term = 20000 pesewas."""
        from app.constants.subscription import ADDON_PRICING_PER_TERM

        assert ADDON_PRICING_PER_TERM["preschool"] == 20000


class TestCostCalculation:
    """Test SubscriptionService.calculate_upgrade_cost()."""

    @pytest.mark.asyncio
    async def test_calculate_cost_starter_term(self, app_session, admin_session):
        """Starter term cost: students * 500 pesewas."""
        from tests.conftest import create_test_tenant, set_app_tenant_context

        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService
        from app.models.tenant import SubscriptionTier

        service = SubscriptionService(app_session)
        cost = await service.calculate_upgrade_cost(
            tenant_id=tenant["id"],
            target_tier=SubscriptionTier.STARTER,
            billing_period="term",
        )

        # No students, but min 1 billable student
        assert cost["billable_students"] >= 1
        assert cost["price_per_student"] == 500
        assert cost["total"] == cost["billable_students"] * 500

    @pytest.mark.asyncio
    async def test_calculate_cost_annual_discount(self, app_session, admin_session):
        """Annual cost applies 10% discount."""
        from tests.conftest import create_test_tenant, set_app_tenant_context

        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.subscription import SubscriptionService
        from app.models.tenant import SubscriptionTier

        service = SubscriptionService(app_session)
        cost = await service.calculate_upgrade_cost(
            tenant_id=tenant["id"],
            target_tier=SubscriptionTier.STARTER,
            billing_period="year",
        )

        assert cost["price_per_student"] == 1350  # Annual price with discount
        assert cost["billing_period"] == "year"
