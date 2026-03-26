"""
Tests for the school registration/onboarding flow changes.

Covers:
1. Registration creates PENDING user with email_verified=False
2. Resend verification endpoint (success, enumeration protection, validation)
3. Redis fallback (user activated when verification email cannot be sent)
4. ResendVerificationRequest schema validation
5. Chain school query returns oldest school
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import admin_session_maker, admin_engine, app_session_maker


# ---------------------------------------------------------------------------
# Schema validation tests (no DB needed)
# ---------------------------------------------------------------------------


class TestResendVerificationSchema:
    """Validate ResendVerificationRequest input."""

    def test_valid_request(self):
        from app.schemas.onboarding import ResendVerificationRequest

        req = ResendVerificationRequest(email="admin@test.io", subdomain="my-school")
        assert req.email == "admin@test.io"
        assert req.subdomain == "my-school"

    def test_subdomain_too_short(self):
        from app.schemas.onboarding import ResendVerificationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResendVerificationRequest(email="a@b.io", subdomain="ab")

    def test_subdomain_too_long(self):
        from app.schemas.onboarding import ResendVerificationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResendVerificationRequest(email="a@b.io", subdomain="a" * 64)

    def test_subdomain_invalid_chars(self):
        from app.schemas.onboarding import ResendVerificationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResendVerificationRequest(email="a@b.io", subdomain="My_School!")

    def test_subdomain_starts_with_hyphen(self):
        from app.schemas.onboarding import ResendVerificationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResendVerificationRequest(email="a@b.io", subdomain="-school")

    def test_subdomain_ends_with_hyphen(self):
        from app.schemas.onboarding import ResendVerificationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResendVerificationRequest(email="a@b.io", subdomain="school-")

    def test_invalid_email(self):
        from app.schemas.onboarding import ResendVerificationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResendVerificationRequest(email="not-an-email", subdomain="valid-sub")

    def test_single_char_subdomain_valid(self):
        """A 3-char subdomain that matches the pattern should pass min_length but
        the pattern requires start AND end to be alphanumeric.  'abc' is valid."""
        from app.schemas.onboarding import ResendVerificationRequest

        req = ResendVerificationRequest(email="x@y.io", subdomain="abc")
        assert req.subdomain == "abc"


# ---------------------------------------------------------------------------
# E2E tests via HTTP (use unauth_client from e2e conftest)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registration_creates_pending_user(unauth_client):
    """Newly registered admin should have status=pending and email_verified=false.

    When Redis is unavailable (test env has no Redis), the fallback kicks in and
    the user is set to ACTIVE. We mock the verification service to simulate
    Redis being available so the PENDING path is exercised.
    """
    subdomain = f"regpend-{uuid4().hex[:8]}"
    reg_data = {
        "school_name": "Pending Test School",
        "subdomain": subdomain,
        "school_type": "basic",
        "admin_email": f"admin@{subdomain}.test.io",
        "admin_first_name": "Kofi",
        "admin_last_name": "Mensah",
        "admin_password": "SecurePass123!",
    }

    # Mock the EmailVerificationService so it appears to succeed
    # (returns a token and sends email), which means the user stays PENDING.
    with patch(
        "app.services.onboarding.EmailVerificationService"
    ) as MockVerifSvc:
        mock_instance = MagicMock()
        mock_instance.create_verification_token = AsyncMock(return_value="fake-token")
        mock_instance.send_verification_email = AsyncMock(return_value=True)
        MockVerifSvc.return_value = mock_instance

        resp = await unauth_client.post(
            "/api/v1/onboarding/register", json=reg_data
        )

    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    tid = data["tenant_id"]
    uid = data["admin_user_id"]

    # Verify the user record in DB has PENDING status
    async with admin_session_maker() as session:
        result = await session.execute(
            text(
                "SELECT status, email_verified FROM users "
                "WHERE id = CAST(:uid AS uuid)"
            ),
            {"uid": str(uid)},
        )
        row = result.fetchone()
        assert row is not None, "Admin user not found in DB"
        assert row[0] == "pending", f"Expected status=pending, got {row[0]}"
        assert row[1] is False, f"Expected email_verified=False, got {row[1]}"

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["users", "schools"]:
            await session.execute(
                text(
                    f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"
                ),
                {"tid": str(tid)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tid)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_pending_user_cannot_login(unauth_client):
    """A user with status=PENDING should be rejected at login with
    'Please verify your email address'."""
    subdomain = f"nologin-{uuid4().hex[:8]}"
    email = f"admin@{subdomain}.test.io"
    password = "SecurePass123!"

    # Register with verification mocked to succeed (user stays PENDING)
    with patch(
        "app.services.onboarding.EmailVerificationService"
    ) as MockVerifSvc:
        mock_instance = MagicMock()
        mock_instance.create_verification_token = AsyncMock(return_value="fake-token")
        mock_instance.send_verification_email = AsyncMock(return_value=True)
        MockVerifSvc.return_value = mock_instance

        reg = await unauth_client.post(
            "/api/v1/onboarding/register",
            json={
                "school_name": "No Login School",
                "subdomain": subdomain,
                "school_type": "basic",
                "admin_email": email,
                "admin_first_name": "Ama",
                "admin_last_name": "Asante",
                "admin_password": password,
            },
        )

    assert reg.status_code == 201
    tid = reg.json()["tenant_id"]

    # Attempt login -- should fail
    login_resp = await unauth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Subdomain": subdomain},
    )
    # Login should be rejected (401 or 403 depending on implementation)
    assert login_resp.status_code in (
        401,
        403,
    ), f"PENDING user should not log in: {login_resp.text}"

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["audit_logs", "users", "schools"]:
            await session.execute(
                text(
                    f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"
                ),
                {"tid": str(tid)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tid)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_redis_fallback_activates_user(unauth_client):
    """When Redis is unavailable, registration should still succeed and
    the user should be ACTIVE with email_verified=True (fallback path)."""
    subdomain = f"noredis-{uuid4().hex[:8]}"
    reg_data = {
        "school_name": "No Redis School",
        "subdomain": subdomain,
        "school_type": "basic",
        "admin_email": f"admin@{subdomain}.test.io",
        "admin_first_name": "Kwesi",
        "admin_last_name": "Boateng",
        "admin_password": "SecurePass123!",
    }

    # Mock EmailVerificationService to simulate Redis unavailability:
    # create_verification_token returns None (no Redis).
    with patch(
        "app.services.onboarding.EmailVerificationService"
    ) as MockVerifSvc:
        mock_instance = MagicMock()
        mock_instance.create_verification_token = AsyncMock(return_value=None)
        MockVerifSvc.return_value = mock_instance

        resp = await unauth_client.post(
            "/api/v1/onboarding/register", json=reg_data
        )

    assert resp.status_code == 201
    data = resp.json()
    tid = data["tenant_id"]
    uid = data["admin_user_id"]

    # Verify the user was activated as fallback
    async with admin_session_maker() as session:
        result = await session.execute(
            text(
                "SELECT status, email_verified FROM users "
                "WHERE id = CAST(:uid AS uuid)"
            ),
            {"uid": str(uid)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "active", f"Fallback should set status=active, got {row[0]}"
        assert row[1] is True, f"Fallback should set email_verified=True, got {row[1]}"

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["users", "schools"]:
            await session.execute(
                text(
                    f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"
                ),
                {"tid": str(tid)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tid)},
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Resend verification endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_verification_nonexistent_subdomain(unauth_client):
    """Resend with a subdomain that doesn't exist should return the generic
    success message (no enumeration leak)."""
    resp = await unauth_client.post(
        "/api/v1/onboarding/resend-verification",
        json={
            "email": "nobody@nowhere.io",
            "subdomain": "does-not-exist",
        },
    )
    assert resp.status_code == 200
    assert "verification link has been sent" in resp.json()["message"]


@pytest.mark.asyncio
async def test_resend_verification_nonexistent_email(unauth_client):
    """Resend with a real subdomain but wrong email should return the
    same generic success message."""
    subdomain = f"resend-{uuid4().hex[:8]}"

    # Create a real tenant for this test
    async with admin_session_maker() as session:
        tenant_id = uuid4()
        await session.execute(
            text(
                "INSERT INTO tenants (id, subdomain, slug, name, tenant_type, "
                "subscription_tier, status, max_students, max_staff, is_active) "
                "VALUES (CAST(:id AS uuid), :sub, :sub, :name, "
                "'single_school', 'trial', 'active', 100, 50, true)"
            ),
            {
                "id": str(tenant_id),
                "sub": subdomain,
                "name": f"Resend Test {subdomain}",
            },
        )
        await session.commit()

    resp = await unauth_client.post(
        "/api/v1/onboarding/resend-verification",
        json={
            "email": "wrong@email.io",
            "subdomain": subdomain,
        },
    )
    assert resp.status_code == 200
    assert "verification link has been sent" in resp.json()["message"]

    # Cleanup
    async with admin_session_maker() as session:
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_resend_verification_already_verified(unauth_client):
    """Resend for an already-verified user should still return the generic
    success message (no enumeration leak)."""
    subdomain = f"verified-{uuid4().hex[:8]}"
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"admin@{subdomain}.test.io"

    async with admin_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO tenants (id, subdomain, slug, name, tenant_type, "
                "subscription_tier, status, max_students, max_staff, is_active) "
                "VALUES (CAST(:id AS uuid), :sub, :sub, :name, "
                "'single_school', 'trial', 'active', 100, 50, true)"
            ),
            {
                "id": str(tenant_id),
                "sub": subdomain,
                "name": f"Verified Test {subdomain}",
            },
        )
        from app.core.security import hash_password

        await session.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, first_name, "
                "last_name, role, status, email_verified, mfa_enabled, "
                "failed_login_attempts, timezone) "
                "VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw, "
                "'Test', 'User', 'school_admin', 'active', true, false, 0, 'UTC')"
            ),
            {
                "id": str(user_id),
                "tid": str(tenant_id),
                "email": email,
                "pw": hash_password("Ignored123!"),
            },
        )
        await session.commit()

    resp = await unauth_client.post(
        "/api/v1/onboarding/resend-verification",
        json={"email": email, "subdomain": subdomain},
    )
    # The endpoint catches the "already_verified" error and returns generic success
    assert resp.status_code == 200
    assert "verification link has been sent" in resp.json()["message"]

    # Cleanup
    async with admin_session_maker() as session:
        await session.execute(
            text(
                "DELETE FROM users WHERE tenant_id = CAST(:tid AS uuid)"
            ),
            {"tid": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_resend_verification_validation_errors(unauth_client):
    """Bad input to resend-verification should return 422."""
    # Invalid email format
    resp = await unauth_client.post(
        "/api/v1/onboarding/resend-verification",
        json={"email": "not-an-email", "subdomain": "valid-sub"},
    )
    assert resp.status_code == 422

    # Subdomain too short
    resp = await unauth_client.post(
        "/api/v1/onboarding/resend-verification",
        json={"email": "a@b.io", "subdomain": "ab"},
    )
    assert resp.status_code == 422

    # Empty body
    resp = await unauth_client.post(
        "/api/v1/onboarding/resend-verification",
        json={},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Rate limiting registration
# ---------------------------------------------------------------------------


class TestRateLimitConfig:
    """The resend-verification endpoint should be registered in rate limit config."""

    def test_resend_endpoint_has_rate_limit_entry(self):
        from app.middleware.rate_limit import RateLimitMiddleware

        path = "/api/v1/onboarding/resend-verification"
        assert path in RateLimitMiddleware.ENDPOINT_LIMITS


# ---------------------------------------------------------------------------
# Chain school query: GET /schools/current returns oldest school
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_school_current_returns_oldest(auth_client, seeded_tenant):
    """GET /schools/current should return the first school (oldest created_at).

    The seeded_tenant fixture creates one school, so this verifies the basic
    case works. A full multi-school test would need a second school inserted.
    """
    resp = await auth_client.get("/api/v1/schools/current")
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == str(seeded_tenant["school_id"])
    assert data["tenant_id"] == str(seeded_tenant["tenant_id"])


@pytest.mark.asyncio
async def test_chain_school_current_returns_oldest_of_multiple(
    auth_client, seeded_tenant
):
    """When a chain tenant has multiple schools, GET /schools/current
    should return the one with the earliest created_at."""
    tenant_id = seeded_tenant["tenant_id"]
    original_school_id = seeded_tenant["school_id"]
    newer_school_id = uuid4()

    # Insert a second school with a later timestamp
    async with admin_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO schools (id, tenant_id, name, slug, school_type, "
                "created_at) "
                "VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, "
                "'basic', NOW() + interval '1 hour')"
            ),
            {
                "id": str(newer_school_id),
                "tid": str(tenant_id),
                "name": "Newer Chain School",
                "slug": f"newer-{uuid4().hex[:8]}",
            },
        )
        await session.commit()

    resp = await auth_client.get("/api/v1/schools/current")
    assert resp.status_code == 200

    data = resp.json()
    # Should return the original (older) school, not the newer one
    assert data["id"] == str(original_school_id)

    # Cleanup the extra school
    async with admin_session_maker() as session:
        await session.execute(
            text(
                "DELETE FROM schools WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(newer_school_id)},
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Registration response message references email verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registration_response_mentions_email_verification(unauth_client):
    """The registration response message should tell the user to verify email."""
    subdomain = f"msgchk-{uuid4().hex[:8]}"

    with patch(
        "app.services.onboarding.EmailVerificationService"
    ) as MockVerifSvc:
        mock_instance = MagicMock()
        mock_instance.create_verification_token = AsyncMock(return_value="t")
        mock_instance.send_verification_email = AsyncMock(return_value=True)
        MockVerifSvc.return_value = mock_instance

        resp = await unauth_client.post(
            "/api/v1/onboarding/register",
            json={
                "school_name": "Message Check School",
                "subdomain": subdomain,
                "school_type": "basic",
                "admin_email": f"admin@{subdomain}.test.io",
                "admin_first_name": "Yaw",
                "admin_last_name": "Owusu",
                "admin_password": "SecurePass123!",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "verify" in data["message"].lower()
    tid = data["tenant_id"]

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["users", "schools"]:
            await session.execute(
                text(
                    f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"
                ),
                {"tid": str(tid)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tid)},
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Fix 1: _get_current_school shared helper — chain tenants with multiple schools
# ---------------------------------------------------------------------------


_test_middleware_session_maker_local = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


@pytest_asyncio.fixture
async def chain_tenant_with_two_schools():
    """Seed a chain tenant with two schools (different created_at) + admin user.

    The first school has an earlier created_at so _get_current_school should
    always return it.
    """
    from app.core.security import create_access_token, hash_password
    from app.main import app
    from app.api.deps import get_db, get_unscoped_db

    tenant_id = uuid4()
    older_school_id = uuid4()
    newer_school_id = uuid4()
    user_id = uuid4()
    subdomain = f"chain-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :sub, :name,
                    'school_chain', 'professional', 'active', 2000, 200, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "name": f"Chain {subdomain}"},
        )
        # Older school (created first)
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, created_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', NOW() - interval '1 day')
            """),
            {
                "id": str(older_school_id),
                "tid": str(tenant_id),
                "name": "Older Campus",
                "slug": f"older-{uuid4().hex[:8]}",
            },
        )
        # Newer school
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, created_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', NOW() + interval '1 day')
            """),
            {
                "id": str(newer_school_id),
                "tid": str(tenant_id),
                "name": "Newer Campus",
                "slug": f"newer-{uuid4().hex[:8]}",
            },
        )
        # Admin user
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Chain', 'Admin', 'school_admin', 'active', true, false, 0, 'UTC')
            """),
            {
                "id": str(user_id),
                "tid": str(tenant_id),
                "email": f"admin@{subdomain}.test.io",
                "pw": hash_password("TestPass123!"),
            },
        )
        await session.commit()

    token = create_access_token(
        subject=str(user_id),
        tenant_id=str(tenant_id),
        school_id=str(older_school_id),
        role="school_admin",
        permissions=["*"],
        extra_claims={"email": f"admin@{subdomain}.test.io"},
    )

    # Build authenticated client
    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                req_state = getattr(request, "state", None)
                tid = getattr(req_state, "tenant_id", None) if req_state else None
                if tid:
                    await session.execute(
                        text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                        {"tenant_id": str(tid)},
                    )
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                try:
                    await session.execute(text("SELECT clear_tenant_context()"))
                except Exception:
                    pass
                await session.close()

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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker_local), \
         patch("app.main.async_session_maker", _test_middleware_session_maker_local):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        ) as client:
            yield {
                "client": client,
                "tenant_id": tenant_id,
                "older_school_id": older_school_id,
                "newer_school_id": newer_school_id,
                "subdomain": subdomain,
            }

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


@pytest_asyncio.fixture
async def no_school_tenant():
    """Seed a tenant with a user but NO school.

    Used to verify that /schools/current* endpoints return 404.
    """
    from app.core.security import create_access_token, hash_password
    from app.main import app
    from app.api.deps import get_db, get_unscoped_db

    tenant_id = uuid4()
    user_id = uuid4()
    subdomain = f"nosch-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :sub, :name,
                    'single_school', 'trial', 'active', 100, 50, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "name": f"No School {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'NoSchool', 'school_admin', 'active', true, false, 0, 'UTC')
            """),
            {
                "id": str(user_id),
                "tid": str(tenant_id),
                "email": f"admin@{subdomain}.test.io",
                "pw": hash_password("TestPass123!"),
            },
        )
        await session.commit()

    token = create_access_token(
        subject=str(user_id),
        tenant_id=str(tenant_id),
        school_id=str(uuid4()),  # fake school_id — no real school exists
        role="school_admin",
        permissions=["*"],
        extra_claims={"email": f"admin@{subdomain}.test.io"},
    )

    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                req_state = getattr(request, "state", None)
                tid = getattr(req_state, "tenant_id", None) if req_state else None
                if tid:
                    await session.execute(
                        text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                        {"tenant_id": str(tid)},
                    )
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                try:
                    await session.execute(text("SELECT clear_tenant_context()"))
                except Exception:
                    pass
                await session.close()

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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker_local), \
         patch("app.main.async_session_maker", _test_middleware_session_maker_local):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        ) as client:
            yield {"client": client, "tenant_id": tenant_id, "subdomain": subdomain}

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)

    # Cleanup
    async with admin_session_maker() as session:
        await session.execute(
            text("DELETE FROM users WHERE tenant_id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_put_current_school_chain_multiple_schools(chain_tenant_with_two_schools):
    """PUT /schools/current updates the oldest school for chain tenants."""
    ctx = chain_tenant_with_two_schools
    client = ctx["client"]

    resp = await client.put(
        "/api/v1/schools/current",
        json={"motto": "Excellence in Education"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(ctx["older_school_id"])
    assert data["motto"] == "Excellence in Education"


@pytest.mark.asyncio
async def test_patch_branding_chain_multiple_schools(chain_tenant_with_two_schools):
    """PATCH /schools/current/branding updates the oldest school for chain tenants."""
    ctx = chain_tenant_with_two_schools
    client = ctx["client"]

    resp = await client.patch(
        "/api/v1/schools/current/branding",
        json={"primary_color": "#FF5733"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(ctx["older_school_id"])
    assert data["primary_color"] == "#FF5733"


@pytest.mark.asyncio
async def test_get_preschool_settings_chain_multiple_schools(chain_tenant_with_two_schools):
    """GET /schools/current/preschool-settings works for chain tenants."""
    ctx = chain_tenant_with_two_schools
    client = ctx["client"]

    resp = await client.get("/api/v1/schools/current/preschool-settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data


@pytest.mark.asyncio
async def test_patch_preschool_settings_chain_multiple_schools(chain_tenant_with_two_schools):
    """PATCH /schools/current/preschool-settings works for chain tenants."""
    ctx = chain_tenant_with_two_schools
    client = ctx["client"]

    resp = await client.patch(
        "/api/v1/schools/current/preschool-settings",
        json={"enabled": True, "meal_tracking": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["meal_tracking"] is False


@pytest.mark.asyncio
async def test_get_current_school_404_when_no_school(no_school_tenant):
    """GET /schools/current returns 404 when tenant has no school."""
    client = no_school_tenant["client"]
    resp = await client.get("/api/v1/schools/current")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_current_school_404_when_no_school(no_school_tenant):
    """PUT /schools/current returns 404 when tenant has no school."""
    client = no_school_tenant["client"]
    resp = await client.put("/api/v1/schools/current", json={"motto": "Test"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_branding_404_when_no_school(no_school_tenant):
    """PATCH /schools/current/branding returns 404 when no school exists."""
    client = no_school_tenant["client"]
    resp = await client.patch(
        "/api/v1/schools/current/branding", json={"primary_color": "#000000"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_preschool_settings_404_when_no_school(no_school_tenant):
    """GET /schools/current/preschool-settings returns 404 when no school."""
    client = no_school_tenant["client"]
    resp = await client.get("/api/v1/schools/current/preschool-settings")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_preschool_settings_404_when_no_school(no_school_tenant):
    """PATCH /schools/current/preschool-settings returns 404 when no school."""
    client = no_school_tenant["client"]
    resp = await client.patch(
        "/api/v1/schools/current/preschool-settings", json={"enabled": True}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Fix 2: Empty phone string handling in registration
# ---------------------------------------------------------------------------


class TestPhoneValidatorSchema:
    """Validate SchoolRegistrationRequest phone field handling."""

    def test_empty_string_phone_becomes_none(self):
        """admin_phone='' should be treated as None (not fail validation)."""
        from app.schemas.onboarding import SchoolRegistrationRequest

        req = SchoolRegistrationRequest(
            school_name="Phone Test School",
            subdomain="phone-test",
            school_type="basic",
            admin_email="a@b.io",
            admin_first_name="Test",
            admin_last_name="User",
            admin_password="SecurePass123!",
            admin_phone="",
        )
        assert req.admin_phone is None

    def test_whitespace_only_phone_becomes_none(self):
        """admin_phone='   ' should be treated as None after stripping."""
        from app.schemas.onboarding import SchoolRegistrationRequest

        req = SchoolRegistrationRequest(
            school_name="Whitespace Phone School",
            subdomain="wsphone-test",
            school_type="basic",
            admin_email="a@b.io",
            admin_first_name="Test",
            admin_last_name="User",
            admin_password="SecurePass123!",
            admin_phone="   ",
        )
        assert req.admin_phone is None

    def test_null_phone_is_valid(self):
        """admin_phone=None should be valid."""
        from app.schemas.onboarding import SchoolRegistrationRequest

        req = SchoolRegistrationRequest(
            school_name="Null Phone School",
            subdomain="nullphone-test",
            school_type="basic",
            admin_email="a@b.io",
            admin_first_name="Test",
            admin_last_name="User",
            admin_password="SecurePass123!",
            admin_phone=None,
        )
        assert req.admin_phone is None

    def test_valid_ghana_phone_accepted(self):
        """A valid Ghana phone number should pass validation."""
        from app.schemas.onboarding import SchoolRegistrationRequest

        req = SchoolRegistrationRequest(
            school_name="Valid Phone School",
            subdomain="validphone-test",
            school_type="basic",
            admin_email="a@b.io",
            admin_first_name="Test",
            admin_last_name="User",
            admin_password="SecurePass123!",
            admin_phone="+233241234567",
        )
        assert req.admin_phone == "+233241234567"

    def test_phone_omitted_is_valid(self):
        """Not providing admin_phone at all should default to None."""
        from app.schemas.onboarding import SchoolRegistrationRequest

        req = SchoolRegistrationRequest(
            school_name="No Phone School",
            subdomain="nophone-test",
            school_type="basic",
            admin_email="a@b.io",
            admin_first_name="Test",
            admin_last_name="User",
            admin_password="SecurePass123!",
        )
        assert req.admin_phone is None


def _register_payload(subdomain, phone_value=None, include_phone=True):
    """Helper to build registration payloads with varying phone values."""
    payload = {
        "school_name": f"Phone Test {subdomain}",
        "subdomain": subdomain,
        "school_type": "basic",
        "admin_email": f"admin@{subdomain}.test.io",
        "admin_first_name": "Kofi",
        "admin_last_name": "Phone",
        "admin_password": "SecurePass123!",
    }
    if include_phone:
        payload["admin_phone"] = phone_value
    return payload


async def _register_and_cleanup(unauth_client, payload):
    """Register a school, assert success, then clean up."""
    with patch("app.services.onboarding.EmailVerificationService") as MockVS:
        mock = MagicMock()
        mock.create_verification_token = AsyncMock(return_value=None)
        MockVS.return_value = mock
        resp = await unauth_client.post("/api/v1/onboarding/register", json=payload)

    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    tid = resp.json()["tenant_id"]

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

    return resp


@pytest.mark.asyncio
async def test_registration_empty_phone_string(unauth_client):
    """Registration with admin_phone='' succeeds (treated as None)."""
    subdomain = f"emptyph-{uuid4().hex[:8]}"
    payload = _register_payload(subdomain, phone_value="")
    resp = await _register_and_cleanup(unauth_client, payload)
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_registration_null_phone(unauth_client):
    """Registration with admin_phone=null succeeds."""
    subdomain = f"nullph-{uuid4().hex[:8]}"
    payload = _register_payload(subdomain, phone_value=None)
    resp = await _register_and_cleanup(unauth_client, payload)
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_registration_whitespace_phone(unauth_client):
    """Registration with admin_phone='   ' succeeds (treated as None)."""
    subdomain = f"wsph-{uuid4().hex[:8]}"
    payload = _register_payload(subdomain, phone_value="   ")
    resp = await _register_and_cleanup(unauth_client, payload)
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_registration_valid_ghana_phone(unauth_client):
    """Registration with a valid Ghana phone number succeeds."""
    subdomain = f"ghph-{uuid4().hex[:8]}"
    payload = _register_payload(subdomain, phone_value="+233241234567")
    resp = await _register_and_cleanup(unauth_client, payload)
    assert resp.json()["success"] is True
