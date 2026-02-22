"""
E2E tests for the onboarding/registration flow.

Tests the full school registration lifecycle: subdomain check, registration,
duplicate rejection, and reserved subdomain protection.
"""

import pytest
from uuid import uuid4

from sqlalchemy import text
from tests.conftest import admin_session_maker


@pytest.mark.asyncio
async def test_full_onboarding_register(unauth_client):
    """Register a new school via /api/v1/onboarding/register."""
    subdomain = f"onboard-{uuid4().hex[:8]}"

    reg_data = {
        "school_name": "Onboarding E2E School",
        "subdomain": subdomain,
        "school_type": "basic",
        "admin_email": f"admin@{subdomain}.test.io",
        "admin_first_name": "Test",
        "admin_last_name": "Admin",
        "admin_password": "SecurePass123!",
    }
    resp = await unauth_client.post("/api/v1/onboarding/register", json=reg_data)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"

    data = resp.json()
    assert data["success"] is True
    assert data["subdomain"] == subdomain
    assert "tenant_id" in data
    assert "school_id" in data
    assert "admin_user_id" in data

    # Cleanup the created tenant
    async with admin_session_maker() as session:
        tid = data["tenant_id"]
        for table in [
            "users", "schools",
        ]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tid)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_duplicate_subdomain_rejected(unauth_client):
    """Registering the same subdomain twice should fail."""
    subdomain = f"dup-{uuid4().hex[:8]}"

    reg_data = {
        "school_name": "Duplicate Test",
        "subdomain": subdomain,
        "school_type": "basic",
        "admin_email": f"admin1@{subdomain}.test.io",
        "admin_first_name": "Test",
        "admin_last_name": "Admin",
        "admin_password": "SecurePass123!",
    }
    resp1 = await unauth_client.post("/api/v1/onboarding/register", json=reg_data)
    assert resp1.status_code == 201, f"First registration should succeed: {resp1.text}"
    tid = resp1.json()["tenant_id"]

    # Second registration with same subdomain should fail
    reg_data["admin_email"] = f"admin2@{subdomain}.test.io"
    resp2 = await unauth_client.post("/api/v1/onboarding/register", json=reg_data)
    assert resp2.status_code == 400, f"Should reject duplicate subdomain: {resp2.text}"

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tid)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_reserved_subdomain_rejected(unauth_client):
    """Reserved subdomains (admin, api, www) should be rejected at registration."""
    # These are reserved at the validator level (min_length=4 blocks "api" and "www")
    # "admin" passes length check but should be rejected as reserved
    reg_data = {
        "school_name": "Reserved Admin",
        "subdomain": "admin",
        "school_type": "basic",
        "admin_email": "admin@admin-test.io",
        "admin_first_name": "Test",
        "admin_last_name": "Admin",
        "admin_password": "SecurePass123!",
    }
    resp = await unauth_client.post("/api/v1/onboarding/register", json=reg_data)
    # Should fail: either 400 (reserved) or 422 (validation, e.g., too short)
    assert resp.status_code in (400, 422), f"Subdomain 'admin' should be rejected: {resp.text}"


@pytest.mark.asyncio
async def test_onboarding_plans_endpoint(unauth_client):
    """The /plans endpoint should return available subscription plans."""
    resp = await unauth_client.get("/api/v1/onboarding/plans")
    assert resp.status_code == 200

    data = resp.json()
    assert "plans" in data
    plan_ids = [p["id"] for p in data["plans"]]
    assert "trial" in plan_ids
    assert "professional" in plan_ids


@pytest.mark.asyncio
async def test_suggest_subdomain(unauth_client):
    """The /suggest-subdomain endpoint should return available suggestions."""
    resp = await unauth_client.get(
        "/api/v1/onboarding/suggest-subdomain",
        params={"school_name": "Wesley Girls High School"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0


@pytest.mark.asyncio
async def test_registration_validation_errors(unauth_client):
    """Missing required fields should return 422 validation error."""
    # No school_name, no subdomain, no admin info
    resp = await unauth_client.post("/api/v1/onboarding/register", json={})
    assert resp.status_code == 422

    # Weak password should be rejected
    resp = await unauth_client.post("/api/v1/onboarding/register", json={
        "school_name": "Weak Pass School",
        "subdomain": f"weak-{uuid4().hex[:8]}",
        "school_type": "basic",
        "admin_email": "admin@weak.io",
        "admin_first_name": "Test",
        "admin_last_name": "Admin",
        "admin_password": "weak",  # Too short, no uppercase, no special char
    })
    assert resp.status_code == 422
