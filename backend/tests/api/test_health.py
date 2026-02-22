"""
SIMS Plus - Health Check Tests

Tests for the /health endpoint and root/status endpoints.

Validates:
- Structured response format with dependency checks
- Latency measurements for database
- Correct status codes (200 healthy/degraded, 503 unhealthy)
- Migration revision reporting
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_structured_response(client: AsyncClient) -> None:
    """Test health check returns structured JSON with all dependency checks."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Top-level fields
    assert data["status"] in ("healthy", "degraded")
    assert "version" in data
    assert "checks" in data

    # Database check structure
    db = data["checks"]["database"]
    assert db["status"] == "up"
    assert isinstance(db["latency_ms"], (int, float))
    assert db["latency_ms"] >= 0

    # Redis check structure (may be "up", "down", or "not_configured" depending
    # on whether the test fixture triggers app lifespan)
    redis_check = data["checks"]["redis"]
    assert redis_check["status"] in ("up", "down", "not_configured")
    assert isinstance(redis_check["latency_ms"], (int, float))

    # Migrations check structure
    migrations = data["checks"]["migrations"]
    assert migrations["status"] in ("current", "no_revision", "unable_to_check")


@pytest.mark.asyncio
async def test_health_check_db_latency_reasonable(client: AsyncClient) -> None:
    """Database latency should be reasonable (sanity check, not exact target)."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    db_latency = data["checks"]["database"]["latency_ms"]
    assert db_latency < 5000, f"Database latency unexpectedly high: {db_latency}ms"


@pytest.mark.asyncio
async def test_health_check_version_matches_config(client: AsyncClient) -> None:
    """Health check version should match the configured APP_VERSION."""
    from app.config import settings

    response = await client.get("/health")
    data = response.json()

    assert data["version"] == settings.APP_VERSION

    # environment is only included in development mode
    if settings.is_development:
        assert data["environment"] == settings.ENVIRONMENT


@pytest.mark.asyncio
async def test_health_check_unhealthy_when_db_down(client: AsyncClient, monkeypatch) -> None:
    """Health check should return 503 unhealthy when database is unreachable."""
    from app.db import session as session_module

    original_maker = session_module.async_session_maker

    class FakeSessionMaker:
        """Mock session maker that simulates DB failure."""

        def __call__(self):
            return self

        async def __aenter__(self):
            raise ConnectionError("DB unreachable")

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("app.main.async_session_maker", FakeSessionMaker())

    response = await client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["checks"]["database"]["status"] == "down"

    # Restore
    monkeypatch.setattr("app.main.async_session_maker", original_maker)


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    """Test root endpoint returns API information."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "SIMS Plus"
    assert "version" in data


@pytest.mark.asyncio
async def test_api_status(client: AsyncClient) -> None:
    """Test API v1 status endpoint."""
    response = await client.get("/api/v1/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["version"] == "v1"
