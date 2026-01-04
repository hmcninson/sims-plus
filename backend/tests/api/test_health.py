"""
SIMS Plus - Health Check Tests

Tests for health and status endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health check endpoint returns healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data


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
