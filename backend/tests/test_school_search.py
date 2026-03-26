"""
Tests for school search API.

Verifies the public /tenant/search endpoint returns safe fields,
excludes suspended/platform tenants, and handles edge cases.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.api.deps import get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker


_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


@pytest_asyncio.fixture
async def search_tenants():
    """Create a few tenants for search tests."""
    suffix = uuid4().hex[:8]
    tenant_ids = []

    async with admin_session_maker() as session:
        # Active tenant: Presec Academy
        t1_id = uuid4()
        tenant_ids.append(t1_id)
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'professional', 'active', 1000, 100, true)
        """), {"id": str(t1_id), "subdomain": f"presec-{suffix}",
               "slug": f"presec-{suffix}", "name": f"Presec Academy {suffix}"})

        # Trial tenant: Achimota School
        t2_id = uuid4()
        tenant_ids.append(t2_id)
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'starter', 'trial', 500, 50, true)
        """), {"id": str(t2_id), "subdomain": f"achimota-{suffix}",
               "slug": f"achimota-{suffix}", "name": f"Achimota School {suffix}"})

        # Suspended tenant: should NOT appear in results
        t3_id = uuid4()
        tenant_ids.append(t3_id)
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'starter', 'suspended', 500, 50, true)
        """), {"id": str(t3_id), "subdomain": f"suspended-{suffix}",
               "slug": f"suspended-{suffix}", "name": f"Suspended School {suffix}"})

        await session.commit()

    yield {"suffix": suffix, "tenant_ids": tenant_ids}

    # Cleanup
    async with admin_session_maker() as session:
        for tid in tenant_ids:
            await session.execute(
                text("DELETE FROM tenants WHERE id = CAST(:id AS uuid)"),
                {"id": str(tid)},
            )
        await session.commit()


@pytest_asyncio.fixture
async def search_client():
    """Unauthenticated client for public search endpoint."""
    async def override_get_unscoped_db():
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            yield client

    app.dependency_overrides.clear()


class TestSchoolSearch:
    @pytest.mark.asyncio
    async def test_search_by_name_returns_results(self, search_client, search_tenants):
        """Search by partial name should return matching active tenants."""
        suffix = search_tenants["suffix"]
        resp = await search_client.get(f"/api/v1/tenant/search?q=presec-{suffix}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        names = [r["name"] for r in data["results"]]
        assert any(f"Presec Academy {suffix}" in n for n in names)

    @pytest.mark.asyncio
    async def test_search_by_subdomain_returns_results(self, search_client, search_tenants):
        """Search by subdomain prefix should return matches."""
        suffix = search_tenants["suffix"]
        resp = await search_client.get(f"/api/v1/tenant/search?q=achimota-{suffix}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        subdomains = [r["subdomain"] for r in data["results"]]
        assert any(f"achimota-{suffix}" in s for s in subdomains)

    @pytest.mark.asyncio
    async def test_short_query_returns_422(self, search_client):
        """Query shorter than 2 characters should return 422."""
        resp = await search_client.get("/api/v1/tenant/search?q=a")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_results_for_nonexistent_school(self, search_client):
        """Searching for a nonexistent name returns empty results, not an error."""
        resp = await search_client.get("/api/v1/tenant/search?q=zzz_nonexistent_school_999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []

    @pytest.mark.asyncio
    async def test_suspended_tenants_excluded(self, search_client, search_tenants):
        """Suspended tenants should not appear in search results."""
        suffix = search_tenants["suffix"]
        resp = await search_client.get(f"/api/v1/tenant/search?q=Suspended {suffix}")
        assert resp.status_code == 200
        data = resp.json()
        subdomains = [r["subdomain"] for r in data["results"]]
        assert not any(f"suspended-{suffix}" in s for s in subdomains)

    @pytest.mark.asyncio
    async def test_platform_tenant_excluded(self, search_client):
        """The internal _platform tenant should never appear in results."""
        resp = await search_client.get("/api/v1/tenant/search?q=_platform")
        assert resp.status_code == 200
        data = resp.json()
        subdomains = [r["subdomain"] for r in data["results"]]
        assert "_platform" not in subdomains

    @pytest.mark.asyncio
    async def test_only_safe_fields_returned(self, search_client, search_tenants):
        """Results should contain only name, subdomain, logo_url, primary_color."""
        suffix = search_tenants["suffix"]
        resp = await search_client.get(f"/api/v1/tenant/search?q=presec-{suffix}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

        result = data["results"][0]
        allowed_fields = {"name", "subdomain", "logo_url", "primary_color"}
        assert set(result.keys()) <= allowed_fields
        # Sensitive fields must NOT be present
        for forbidden in ["tenant_id", "id", "subscription_tier", "features", "max_students"]:
            assert forbidden not in result

    @pytest.mark.asyncio
    async def test_results_capped_at_10(self, search_client):
        """Even with many matches, results should be capped at 10."""
        # Use a broad query that might match many tenants
        resp = await search_client.get("/api/v1/tenant/search?q=school")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 10

    @pytest.mark.asyncio
    async def test_special_characters_handled_safely(self, search_client):
        """ILIKE special characters (%, _) in query should be escaped, not crash."""
        resp = await search_client.get("/api/v1/tenant/search?q=100%25_test")
        assert resp.status_code == 200
        # Should return results (likely empty), not a 500 error

    @pytest.mark.asyncio
    async def test_missing_query_param_returns_422(self, search_client):
        """Missing q parameter should return 422."""
        resp = await search_client.get("/api/v1/tenant/search")
        assert resp.status_code == 422
