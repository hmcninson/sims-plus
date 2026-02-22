"""
SIMS Plus - Authentication Integration Tests

Tests exercise full request-response cycles through FastAPI auth endpoints
with a real PostgreSQL database. They confirm that middleware, authentication,
authorization, validation, service logic, and database operations work together.

Key behaviors tested:
- Successful login returns tokens
- Wrong password returns 401
- Cross-tenant token is rejected (403)
- Account lockout after 5 failed attempts
- Password validation on onboarding (no /auth/register endpoint exists)
- Token blacklisting on logout
- Refresh token rotation
- Suspended tenant login rejected (403)
- Expired JWT token rejected (401)
- Malformed JWT token rejected (401)
- Wrong-signature JWT token rejected (401)
- Refresh token cannot be used as Bearer access token (401)
"""

import pytest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password


# SQL templates for tenant and user creation, centralized to avoid duplication.
# Every raw INSERT must include all NOT NULL columns that lack server defaults.
_TENANT_INSERT = text("""
    INSERT INTO tenants (id, subdomain, slug, name, is_active,
        tenant_type, subscription_tier, max_students,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), :sub, :slug, :name, true,
        'single_school', 'trial', 50,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_USER_INSERT = text("""
    INSERT INTO users (id, tenant_id, email, password_hash,
        first_name, last_name, role, status,
        email_verified, mfa_enabled, failed_login_attempts, timezone,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
        :fn, :ln, :role, :status,
        true, false, 0, 'Africa/Accra',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

# Inactive tenant INSERT: identical to _TENANT_INSERT but with is_active = false.
# Used to test that TenantMiddleware rejects requests for suspended schools.
_INACTIVE_TENANT_INSERT = text("""
    INSERT INTO tenants (id, subdomain, slug, name, is_active,
        tenant_type, subscription_tier, max_students,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), :sub, :slug, :name, false,
        'single_school', 'trial', 50,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_tenant(
    session: AsyncSession, tenant_id: UUID, subdomain: str, name: str
) -> None:
    """Insert a tenant row with all required NOT NULL columns."""
    await session.execute(
        _TENANT_INSERT,
        {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": name},
    )


async def _seed_user(
    session: AsyncSession,
    tenant_id: UUID,
    email: str,
    password: str,
    *,
    role: str = "school_admin",
    first_name: str = "Test",
    last_name: str = "User",
) -> UUID:
    """Insert a user row with all required NOT NULL columns. Returns the user ID."""
    user_id = uuid4()
    password_hash = hash_password(password)
    await session.execute(
        _USER_INSERT,
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": email,
            "pw": password_hash,
            "fn": first_name,
            "ln": last_name,
            "role": role,
            "status": "active",
        },
    )
    return user_id


@pytest.mark.asyncio
@pytest.mark.integration
class TestAuthentication:

    async def test_login_success(self, client, admin_session):
        """Successful login returns access_token and refresh_token.

        Seeds a tenant and user via admin_session (bypasses RLS), then
        authenticates through the HTTP endpoint. The TenantMiddleware
        resolves the X-Subdomain header against the real tenants table.
        """
        tenant_id = uuid4()
        subdomain = f"authok{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Auth OK School")
        await _seed_user(
            admin_session, tenant_id, "login-ok@school.com", "SecureP@ss1",
            role="school_admin",
        )
        await admin_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login-ok@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        # User info is included in the response
        assert data["user"]["email"] == "login-ok@school.com"

    async def test_login_wrong_password(self, client, admin_session):
        """Wrong password returns 401 Unauthorized."""
        tenant_id = uuid4()
        subdomain = f"authwp{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Auth WP School")
        await _seed_user(
            admin_session, tenant_id, "wrongpw@school.com", "SecureP@ss1",
            role="teacher",
        )
        await admin_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@school.com", "password": "WrongPassword1!"},
            headers={"X-Subdomain": subdomain},
        )
        assert response.status_code == 401

    async def test_cross_tenant_token_rejected(self, client, admin_session):
        """A JWT issued for Tenant A must be rejected when used on
        Tenant B's subdomain. The token contains tenant_id and
        tenant_subdomain claims that are validated against the request.

        The /auth/me endpoint uses ValidatedTokenTenant which compares
        the token's tenant_id against request.state.tenant_id and returns
        403 on mismatch.
        """
        # Create Tenant A
        tenant_a_id = uuid4()
        subdomain_a = f"crossa{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_a_id, subdomain_a, "Cross Tenant A")

        # Create Tenant B
        tenant_b_id = uuid4()
        subdomain_b = f"crossb{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_b_id, subdomain_b, "Cross Tenant B")

        # Create user in Tenant A
        await _seed_user(
            admin_session, tenant_a_id, "crosstest@school.com", "SecureP@ss1",
            role="school_admin", first_name="Cross", last_name="Test",
        )
        await admin_session.commit()

        # Login on Tenant A to get a token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "crosstest@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain_a},
        )
        assert login_response.status_code == 200, login_response.text
        tenant_a_token = login_response.json()["access_token"]

        # Try to use Tenant A's token on Tenant B's subdomain.
        # ValidatedTokenTenant checks token.tenant_id != request.state.tenant_id
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {tenant_a_token}",
                "X-Subdomain": subdomain_b,
            },
        )
        assert response.status_code == 403, (
            f"Cross-tenant token was not rejected. "
            f"Got {response.status_code}: {response.text}"
        )

    async def test_account_lockout_after_5_failures(self, client, admin_session):
        """5 failed login attempts must lock the account for 30 minutes.
        The 6th attempt with the correct password should still fail because
        the account is locked.

        AuthService.MAX_FAILED_ATTEMPTS = 5 and LOCKOUT_DURATION_MINUTES = 30.
        """
        tenant_id = uuid4()
        subdomain = f"lockout{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Lockout School")
        await _seed_user(
            admin_session, tenant_id, "lockout@school.com", "SecureP@ss1",
            role="teacher", first_name="Lock", last_name="Out",
        )
        await admin_session.commit()

        # 5 failed attempts with wrong passwords
        for i in range(5):
            await client.post(
                "/api/v1/auth/login",
                json={"email": "lockout@school.com", "password": f"Wrong{i}Pass!"},
                headers={"X-Subdomain": subdomain},
            )

        # 6th attempt with CORRECT password -- should still be locked
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "lockout@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain},
        )
        assert response.status_code == 401, (
            f"Expected 401 for locked account, got {response.status_code}"
        )
        # AuthService raises "Account locked. Try again in X minutes."
        assert "locked" in response.json()["detail"].lower(), (
            f"Expected 'locked' in error message, got: {response.json()['detail']}"
        )

    async def test_password_validation_requirements(self, client):
        """Passwords must meet minimum requirements: 8+ characters,
        uppercase, lowercase, number, special character.

        Since there is no /auth/register endpoint, we test password
        validation through the onboarding /register endpoint, which
        applies the same validation rules via SchoolRegistrationRequest.
        """
        weak_passwords = [
            "short",           # too short (< 8 chars)
            "alllowercase1!",  # no uppercase
            "ALLUPPERCASE1!",  # no lowercase
            "NoNumbers!!aa",   # no digit
            "NoSpecial1abc",   # no special character
        ]
        for password in weak_passwords:
            subdomain = f"pwval{uuid4().hex[:6]}"
            response = await client.post(
                "/api/v1/onboarding/register",
                json={
                    "school_name": "Password Test School",
                    "subdomain": subdomain,
                    "school_type": "basic",
                    "admin_email": f"admin@{subdomain}.edu.gh",
                    "admin_first_name": "Admin",
                    "admin_last_name": "User",
                    "admin_password": password,
                    "admin_phone": "+233244000000",
                    "plan": "trial",
                },
            )
            assert response.status_code in (400, 422), (
                f"Weak password '{password}' was accepted "
                f"(got {response.status_code}: {response.text})"
            )

    async def test_token_blacklisting_on_logout(self, client, admin_session):
        """After logout, the access token must be blacklisted and rejected
        on subsequent requests. The logout endpoint adds the token to a
        Redis-based blacklist, and get_current_user_id checks the blacklist.
        """
        tenant_id = uuid4()
        subdomain = f"logout{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Logout School")
        await _seed_user(
            admin_session, tenant_id, "logout@school.com", "SecureP@ss1",
            role="teacher", first_name="Log", last_name="Out",
        )
        await admin_session.commit()

        # Login to get a token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain},
        )
        assert login_response.status_code == 200, login_response.text
        token = login_response.json()["access_token"]

        # Verify token works before logout
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert me_response.status_code == 200, (
            f"Token should work before logout, got {me_response.status_code}"
        )

        # Logout -- blacklists the token
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert logout_response.status_code == 204

        # Try to use the blacklisted token -- should be rejected
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 401, (
            f"Blacklisted token was not rejected. "
            f"Got {response.status_code}: {response.text}"
        )

    async def test_refresh_token_rotation(self, client, admin_session):
        """The /auth/refresh endpoint should return new access and refresh
        tokens when given a valid refresh token (token rotation)."""
        tenant_id = uuid4()
        subdomain = f"refresh{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Refresh School")
        await _seed_user(
            admin_session, tenant_id, "refresh@school.com", "SecureP@ss1",
            role="school_admin", first_name="Refresh", last_name="Test",
        )
        await admin_session.commit()

        # Login to get initial tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain},
        )
        assert login_response.status_code == 200, login_response.text
        original_refresh = login_response.json()["refresh_token"]
        original_access = login_response.json()["access_token"]

        # Use refresh token to get new tokens
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh},
            headers={"X-Subdomain": subdomain},
        )
        assert refresh_response.status_code == 200, refresh_response.text
        data = refresh_response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New tokens should be different from originals (rotation)
        assert data["access_token"] != original_access
        assert data["refresh_token"] != original_refresh

    async def test_login_to_suspended_tenant_rejected(self, client, admin_session):
        """Login attempt on a suspended/inactive tenant should return 403.

        TenantMiddleware checks tenant.is_active after subdomain lookup.
        When a tenant has is_active=false (suspended/cancelled), the middleware
        returns HTTP 403 with a message about the school account being suspended,
        before the request ever reaches the auth endpoint.
        """
        tenant_id = uuid4()
        subdomain = f"suspend{uuid4().hex[:6]}"

        # Create an inactive tenant (is_active = false)
        await admin_session.execute(
            _INACTIVE_TENANT_INSERT,
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": "Suspended School"},
        )
        await _seed_user(
            admin_session, tenant_id, "suspended@school.com", "SecureP@ss1",
            role="school_admin", first_name="Suspended", last_name="Admin",
        )
        await admin_session.commit()

        # Attempt to login on the suspended tenant's subdomain
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "suspended@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain},
        )
        assert response.status_code == 403, (
            f"Expected 403 for suspended tenant, got {response.status_code}: "
            f"{response.text}"
        )
        assert "suspended" in response.json()["detail"].lower(), (
            f"Expected 'suspended' in error message, got: {response.json()['detail']}"
        )

    async def test_expired_jwt_token_rejected(self, client, admin_session):
        """An expired JWT access token must be rejected with 401.

        We craft a token with an expiry in the past and verify the
        get_current_user_id dependency rejects it via JWTError (ExpiredSignatureError).
        """
        tenant_id = uuid4()
        subdomain = f"expjwt{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Expired JWT School")
        await _seed_user(
            admin_session, tenant_id, "expired@school.com", "SecureP@ss1",
            role="school_admin",
        )
        await admin_session.commit()

        # Craft an access token that expired 1 hour ago
        expired_payload = {
            "sub": str(uuid4()),
            "tenant_id": str(tenant_id),
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )

        # Use expired token to access a protected endpoint
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {expired_token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 401, (
            f"Expired token was not rejected. "
            f"Got {response.status_code}: {response.text}"
        )

    async def test_malformed_jwt_token_rejected(self, client, admin_session):
        """A malformed/garbage token string must be rejected with 401.

        jose.jwt.decode raises JWTError for non-JWT strings, which
        get_current_user_id catches and converts to 401.
        """
        tenant_id = uuid4()
        subdomain = f"badjwt{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Bad JWT School")
        await admin_session.commit()

        garbage_tokens = [
            "not-a-jwt-token",
            "eyJhbGciOiJIUzI1NiJ9.garbage.garbage",
            "",
            "a.b.c.d.e",
        ]

        for bad_token in garbage_tokens:
            response = await client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {bad_token}",
                    "X-Subdomain": subdomain,
                },
            )
            assert response.status_code == 401, (
                f"Malformed token '{bad_token[:30]}...' was not rejected. "
                f"Got {response.status_code}: {response.text}"
            )

    async def test_wrong_signature_jwt_rejected(self, client, admin_session):
        """A JWT signed with a different secret key must be rejected with 401.

        The token is structurally valid JWT but signed with a wrong key.
        jose.jwt.decode raises JWTError for signature mismatch.
        """
        tenant_id = uuid4()
        subdomain = f"badsig{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "Bad Sig School")
        await admin_session.commit()

        # Create a valid-looking token but sign with a different key
        wrong_key_payload = {
            "sub": str(uuid4()),
            "tenant_id": str(tenant_id),
            "type": "access",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        wrong_key_token = jwt.encode(
            wrong_key_payload,
            "completely-wrong-secret-key-that-is-definitely-not-the-real-one-at-all",
            algorithm=settings.ALGORITHM,
        )

        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {wrong_key_token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 401, (
            f"Token with wrong signature was not rejected. "
            f"Got {response.status_code}: {response.text}"
        )

    async def test_refresh_token_cannot_be_used_as_bearer(self, client, admin_session):
        """A refresh token must NOT be accepted as a Bearer access token.

        Refresh tokens have type="refresh" in their payload. The
        get_current_user_id dependency checks payload.get("type") != "access"
        and rejects non-access tokens with 401.
        """
        tenant_id = uuid4()
        subdomain = f"reftok{uuid4().hex[:6]}"
        await _seed_tenant(admin_session, tenant_id, subdomain, "RefTok School")
        await _seed_user(
            admin_session, tenant_id, "reftok@school.com", "SecureP@ss1",
            role="school_admin", first_name="Ref", last_name="Tok",
        )
        await admin_session.commit()

        # Login to get real tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "reftok@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain},
        )
        assert login_response.status_code == 200, login_response.text
        refresh_token = login_response.json()["refresh_token"]

        # Try to use the refresh token as a Bearer access token
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {refresh_token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 401, (
            f"Refresh token was accepted as access token. "
            f"Got {response.status_code}: {response.text}. "
            "SECURITY: Token type validation is not working."
        )
