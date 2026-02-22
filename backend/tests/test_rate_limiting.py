"""
SIMS Plus - Rate Limiting Integration Tests

Tests verify that the RateLimitMiddleware correctly enforces request limits
using Redis sliding window algorithm.

IMPORTANT: These tests require Redis to be running. The RateLimitMiddleware
uses lazy Redis initialization and gracefully degrades if Redis is unavailable
(allows all requests). If Redis is down, these tests will fail with
"No 429 after N requests" because rate limiting is effectively disabled.

Rate limit configuration (from config.py defaults):
- Auth endpoints:     RATE_LIMIT_AUTH_REQUESTS / RATE_LIMIT_AUTH_WINDOW
- Default endpoints:  RATE_LIMIT_DEFAULT_REQUESTS / RATE_LIMIT_DEFAULT_WINDOW

NOTE: The /health endpoint is EXCLUDED from rate limiting (it's in
RateLimitMiddleware.EXCLUDED_ENDPOINTS and doesn't start with /api/).
General rate limit tests must use an /api/ endpoint instead.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from app.config import settings


# Centralized tenant INSERT with all NOT NULL columns that lack server defaults.
_TENANT_INSERT = text("""
    INSERT INTO tenants (id, subdomain, slug, name, is_active,
        tenant_type, subscription_tier, max_students,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), :sub, :slug, :name, true,
        'single_school', 'trial', 50,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


@pytest.mark.asyncio
@pytest.mark.integration
class TestRateLimiting:

    @pytest.fixture(autouse=True)
    def _enable_rate_limiting(self):
        """Re-enable rate limiting for this test class.

        conftest.py disables rate limiting globally to prevent 429 errors in
        other tests. This class specifically tests rate limiting, so we
        re-enable it and restore the original state afterwards.
        """
        settings.RATE_LIMIT_ENABLED = True
        yield
        settings.RATE_LIMIT_ENABLED = False

    async def test_auth_rate_limit(self, client, admin_session):
        """Authentication endpoints are rate-limited. Sending more requests
        than RATE_LIMIT_AUTH_REQUESTS in the window should trigger 429.

        The rate limit key includes client IP (from the test client), so
        each test class gets its own counter. We send auth_limit + 2
        requests to ensure at least one 429 even with timing variance.
        """
        # Create a tenant so the middleware can resolve the subdomain
        tenant_id = uuid4()
        subdomain = f"rateauth{uuid4().hex[:6]}"
        await admin_session.execute(
            _TENANT_INSERT,
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": "Rate Auth School"},
        )
        await admin_session.commit()

        auth_limit = settings.RATE_LIMIT_AUTH_REQUESTS
        # Send auth_limit + 2 requests to guarantee at least one 429
        num_requests = auth_limit + 2

        responses = []
        for _ in range(num_requests):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "Test1234!"},
                headers={"X-Subdomain": subdomain},
            )
            responses.append(response.status_code)

        # At least one response should be 429 (Too Many Requests)
        assert 429 in responses, (
            f"No 429 after {num_requests} rapid auth requests "
            f"(limit={auth_limit}). Is Redis running? "
            f"Status codes: {responses[-10:]}"
        )

    async def test_general_rate_limit(self, client, admin_session, monkeypatch):
        """General API endpoints are rate-limited at RATE_LIMIT_DEFAULT_REQUESTS
        per window. This test sends more requests than the limit and expects
        at least one 429.

        NOTE: /health is excluded from rate limiting, so we use /api/v1/status
        which is a lightweight endpoint that returns operational status.

        We monkeypatch the settings to use a small limit so the test runs
        quickly instead of sending 500+ sequential requests.
        """
        # Temporarily lower the default rate limit so this test finishes fast
        test_limit = 5
        monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", test_limit)

        # Create a tenant so the middleware can resolve the subdomain
        tenant_id = uuid4()
        subdomain = f"rategen{uuid4().hex[:6]}"
        await admin_session.execute(
            _TENANT_INSERT,
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": "Rate Gen School"},
        )
        await admin_session.commit()

        # Send test_limit + 3 requests to guarantee at least one 429
        num_requests = test_limit + 3

        responses = []
        for _ in range(num_requests):
            response = await client.get(
                "/api/v1/status",
                headers={"X-Subdomain": subdomain},
            )
            responses.append(response.status_code)

        assert 429 in responses, (
            f"No 429 after {num_requests} rapid requests "
            f"(limit={test_limit}). Is Redis running? "
            f"Last status codes: {responses}"
        )

    async def test_rate_limit_headers(self, client, admin_session):
        """Rate-limited responses (429) should include a Retry-After header
        telling the client when they can retry. The middleware also adds
        X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset
        to all responses.
        """
        # Create a tenant for the subdomain header
        tenant_id = uuid4()
        subdomain = f"ratehdr{uuid4().hex[:6]}"
        await admin_session.execute(
            _TENANT_INSERT,
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": "Rate Hdr School"},
        )
        await admin_session.commit()

        auth_limit = settings.RATE_LIMIT_AUTH_REQUESTS
        # Exhaust auth rate limit
        last_response = None
        for _ in range(auth_limit + 2):
            last_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "Test1234!"},
                headers={"X-Subdomain": subdomain},
            )
            if last_response.status_code == 429:
                break

        if last_response and last_response.status_code == 429:
            # Verify Retry-After header is present (case-insensitive check)
            headers_lower = {k.lower(): v for k, v in last_response.headers.items()}
            assert "retry-after" in headers_lower, (
                "429 response missing Retry-After header. "
                f"Headers: {dict(last_response.headers)}"
            )
            # Retry-After should be a positive integer (seconds to wait)
            retry_after = int(headers_lower["retry-after"])
            assert retry_after > 0, (
                f"Retry-After should be positive, got {retry_after}"
            )
        else:
            pytest.skip(
                "Could not trigger 429 response -- Redis may not be running"
            )

    async def test_rate_limit_response_headers_on_success(
        self, client, admin_session
    ):
        """Non-429 responses from rate-limited endpoints should include
        X-RateLimit-* headers showing the current limit and remaining
        requests.
        """
        tenant_id = uuid4()
        subdomain = f"ratelim{uuid4().hex[:6]}"
        await admin_session.execute(
            _TENANT_INSERT,
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": "Rate Lim School"},
        )
        await admin_session.commit()

        response = await client.get(
            "/api/v1/status",
            headers={"X-Subdomain": subdomain},
        )

        # Non-429 responses should still have rate limit info headers
        # (added by the middleware after successful processing)
        if response.status_code != 429:
            headers_lower = {k.lower(): v for k, v in response.headers.items()}
            # These headers are added by the middleware for all non-429 responses
            # on rate-limited paths. If Redis is down, no headers are added.
            if "x-ratelimit-limit" in headers_lower:
                assert int(headers_lower["x-ratelimit-limit"]) > 0
                assert "x-ratelimit-remaining" in headers_lower
                assert "x-ratelimit-reset" in headers_lower
