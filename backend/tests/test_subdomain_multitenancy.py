"""
Tests for subdomain & multi-tenancy gap closure.

Covers:
- Consecutive hyphen validation in subdomain
- Cancelled tenant returns 404
- Cross-tenant audit logging
- validate_tenant status checks
- Subscription error code split
- Tenant cleanup table name validation
- Email hex color validation
- HTML escaping in email fallbacks
"""

import html
import re
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# 1. Consecutive hyphen validation — TenantService.validate_subdomain_format
# ---------------------------------------------------------------------------

class TestSubdomainFormatValidation:
    """Test TenantService.validate_subdomain_format() rejects consecutive hyphens."""

    @pytest.fixture
    def tenant_service(self):
        """TenantService with a dummy db session (not used by validate_subdomain_format)."""
        from app.services.tenant import TenantService

        return TenantService(db=AsyncMock())

    def test_consecutive_hyphens_rejected(self, tenant_service):
        """test--school must be rejected."""
        is_valid, error = tenant_service.validate_subdomain_format("test--school")
        assert is_valid is False
        assert "consecutive hyphens" in error.lower()

    def test_triple_hyphens_rejected(self, tenant_service):
        """my---school must be rejected."""
        is_valid, error = tenant_service.validate_subdomain_format("my---school")
        assert is_valid is False
        assert "consecutive hyphens" in error.lower()

    def test_single_hyphen_accepted(self, tenant_service):
        """my-school is a valid subdomain."""
        is_valid, error = tenant_service.validate_subdomain_format("my-school")
        assert is_valid is True
        assert error is None

    def test_no_hyphens_accepted(self, tenant_service):
        """myschool is a valid subdomain."""
        is_valid, error = tenant_service.validate_subdomain_format("myschool")
        assert is_valid is True
        assert error is None

    def test_too_short_rejected(self, tenant_service):
        """abc (3 chars) must be rejected."""
        is_valid, error = tenant_service.validate_subdomain_format("abc")
        assert is_valid is False
        assert "at least 4" in error.lower()

    def test_starts_with_hyphen_rejected(self, tenant_service):
        """Subdomains cannot start with a hyphen."""
        is_valid, error = tenant_service.validate_subdomain_format("-test")
        assert is_valid is False

    def test_ends_with_hyphen_rejected(self, tenant_service):
        """Subdomains cannot end with a hyphen."""
        is_valid, error = tenant_service.validate_subdomain_format("test-")
        assert is_valid is False


# ---------------------------------------------------------------------------
# 2. Consecutive hyphen validation — Pydantic schema
# ---------------------------------------------------------------------------

class TestSubdomainSchemaValidation:
    """Test SchoolRegistrationRequest schema rejects consecutive hyphens."""

    def _make_payload(self, subdomain: str) -> dict:
        return {
            "school_name": "Test School",
            "subdomain": subdomain,
            "school_type": "basic",
            "admin_email": "admin@example.com",
            "admin_first_name": "Admin",
            "admin_last_name": "User",
            "admin_password": "SecurePass1!",
        }

    def test_schema_rejects_consecutive_hyphens(self):
        from app.schemas.onboarding import SchoolRegistrationRequest

        with pytest.raises(ValidationError) as exc_info:
            SchoolRegistrationRequest(**self._make_payload("test--school"))
        assert "consecutive hyphens" in str(exc_info.value).lower()

    def test_schema_accepts_single_hyphen(self):
        from app.schemas.onboarding import SchoolRegistrationRequest

        reg = SchoolRegistrationRequest(**self._make_payload("my-school"))
        assert reg.subdomain == "my-school"


# ---------------------------------------------------------------------------
# 3. extract_subdomain_from_host rejects consecutive hyphens
# ---------------------------------------------------------------------------

class TestExtractSubdomainFromHost:
    """Test middleware extract_subdomain_from_host."""

    def test_rejects_consecutive_hyphens(self):
        from app.middleware.tenant import extract_subdomain_from_host

        result = extract_subdomain_from_host("te--st.simsplus.io")
        assert result is None

    def test_accepts_valid_subdomain(self):
        from app.middleware.tenant import extract_subdomain_from_host

        result = extract_subdomain_from_host("presec.simsplus.io")
        assert result == "presec"

    def test_rejects_reserved_subdomain(self):
        from app.middleware.tenant import extract_subdomain_from_host

        result = extract_subdomain_from_host("www.simsplus.io")
        assert result is None

    def test_rejects_short_subdomain(self):
        from app.middleware.tenant import extract_subdomain_from_host

        result = extract_subdomain_from_host("ab.simsplus.io")
        assert result is None

    def test_strips_port(self):
        from app.middleware.tenant import extract_subdomain_from_host

        result = extract_subdomain_from_host("presec.simsplus.io:8000")
        assert result == "presec"

    def test_localhost_subdomain(self):
        from app.middleware.tenant import extract_subdomain_from_host

        result = extract_subdomain_from_host("presec.localhost")
        assert result == "presec"


# ---------------------------------------------------------------------------
# 4. Cancelled tenant returns 404; suspended returns 403
# ---------------------------------------------------------------------------

class TestTenantStatusMiddleware:
    """Test TenantMiddleware handles cancelled/suspended/active statuses."""

    def _make_tenant_dict(self, status: str, is_active: bool = True) -> dict:
        return {
            "id": str(uuid4()),
            "subdomain": "testschool",
            "name": "Test School",
            "slug": "test-school",
            "is_active": is_active,
            "status": status,
            "trial_ends_at": None,
            "subscription_end": None,
        }

    @pytest.mark.anyio
    async def test_cancelled_tenant_returns_404(self):
        """A cancelled tenant should appear as 'not found'."""
        from app.middleware.tenant import TenantMiddleware

        middleware = TenantMiddleware(app=MagicMock())

        # Mock the internal method to return a cancelled tenant
        tenant_data = self._make_tenant_dict("cancelled")
        middleware._get_tenant_by_subdomain = AsyncMock(return_value=tenant_data)

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/v1/students"
        request.headers = {"x-subdomain": "testschool"}
        request.app.state = MagicMock(redis=None)

        response = await middleware.dispatch(request, AsyncMock())

        assert response.status_code == 404
        assert "not found" in response.body.decode().lower()

    @pytest.mark.anyio
    async def test_suspended_tenant_returns_403(self):
        """A suspended tenant should return 403 with TENANT_SUSPENDED code."""
        from app.middleware.tenant import TenantMiddleware

        middleware = TenantMiddleware(app=MagicMock())

        tenant_data = self._make_tenant_dict("suspended")
        middleware._get_tenant_by_subdomain = AsyncMock(return_value=tenant_data)

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/v1/students"
        request.headers = {"x-subdomain": "testschool"}
        request.app.state = MagicMock(redis=None)

        response = await middleware.dispatch(request, AsyncMock())

        assert response.status_code == 403
        import json
        body = json.loads(response.body)
        assert body["code"] == "TENANT_SUSPENDED"

    @pytest.mark.anyio
    async def test_active_tenant_passes_through(self):
        """An active tenant should proceed to the next handler."""
        from app.middleware.tenant import TenantMiddleware

        middleware = TenantMiddleware(app=MagicMock())

        tenant_data = self._make_tenant_dict("active", is_active=True)
        middleware._get_tenant_by_subdomain = AsyncMock(return_value=tenant_data)

        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/v1/students"
        request.headers = {"x-subdomain": "testschool"}
        request.app.state = MagicMock(redis=None)
        request.state = MagicMock()

        response = await middleware.dispatch(request, call_next)

        # The middleware should have called call_next (passed through)
        call_next.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. validate_tenant status checks (service level)
# ---------------------------------------------------------------------------

class TestValidateTenantService:
    """Test TenantService.validate_tenant() 4-tuple returns."""

    @pytest.mark.anyio
    async def test_cancelled_tenant_returns_not_found(self):
        from app.services.tenant import TenantService
        from app.models.tenant import TenantStatus

        mock_tenant = MagicMock()
        mock_tenant.status = TenantStatus.CANCELLED
        mock_tenant.deleted_at = None

        service = TenantService(db=AsyncMock())
        service.get_tenant_by_subdomain = AsyncMock(return_value=mock_tenant)

        is_valid, tenant, msg, code = await service.validate_tenant("cancelled-school")

        assert is_valid is False
        assert tenant is None
        assert msg == "School not found"
        assert code is None

    @pytest.mark.anyio
    async def test_suspended_tenant_returns_suspended_code(self):
        from app.services.tenant import TenantService
        from app.models.tenant import TenantStatus

        mock_tenant = MagicMock()
        mock_tenant.status = TenantStatus.SUSPENDED
        mock_tenant.deleted_at = None
        mock_tenant.is_active = True

        service = TenantService(db=AsyncMock())
        service.get_tenant_by_subdomain = AsyncMock(return_value=mock_tenant)

        is_valid, tenant, msg, code = await service.validate_tenant("suspended-school")

        assert is_valid is False
        assert tenant is None
        assert "suspended" in msg.lower()
        assert code == "TENANT_SUSPENDED"

    @pytest.mark.anyio
    async def test_active_tenant_returns_valid(self):
        from app.services.tenant import TenantService
        from app.models.tenant import TenantStatus

        mock_tenant = MagicMock()
        mock_tenant.status = TenantStatus.ACTIVE
        mock_tenant.deleted_at = None
        mock_tenant.is_active = True

        service = TenantService(db=AsyncMock())
        service.get_tenant_by_subdomain = AsyncMock(return_value=mock_tenant)

        is_valid, tenant, msg, code = await service.validate_tenant("active-school")

        assert is_valid is True
        assert tenant is mock_tenant
        assert msg is None
        assert code is None

    @pytest.mark.anyio
    async def test_nonexistent_tenant_returns_not_found(self):
        from app.services.tenant import TenantService

        service = TenantService(db=AsyncMock())
        service.get_tenant_by_subdomain = AsyncMock(return_value=None)

        is_valid, tenant, msg, code = await service.validate_tenant("no-such-school")

        assert is_valid is False
        assert tenant is None
        assert msg == "School not found"
        assert code is None

    @pytest.mark.anyio
    async def test_soft_deleted_tenant_returns_not_found(self):
        from app.services.tenant import TenantService
        from datetime import datetime, timezone

        mock_tenant = MagicMock()
        mock_tenant.deleted_at = datetime.now(timezone.utc)

        service = TenantService(db=AsyncMock())
        service.get_tenant_by_subdomain = AsyncMock(return_value=mock_tenant)

        is_valid, tenant, msg, code = await service.validate_tenant("deleted-school")

        assert is_valid is False
        assert tenant is None
        assert msg == "School not found"


# ---------------------------------------------------------------------------
# 6. Cross-tenant audit logging
# ---------------------------------------------------------------------------

class TestCrossTenantAuditLogging:
    """Test that cross-tenant JWT usage triggers audit logging."""

    @pytest.mark.anyio
    async def test_cross_tenant_creates_audit_entry(self):
        """Using tenant A's JWT on tenant B's subdomain logs auth.cross_tenant.rejected."""
        from app.api.deps import validate_token_tenant
        from app.config import settings

        tenant_a_id = str(uuid4())
        tenant_b_id = str(uuid4())
        user_id = str(uuid4())

        # Create a valid token for tenant A
        from jose import jwt as jose_jwt
        import time

        token = jose_jwt.encode(
            {
                "sub": user_id,
                "tenant_id": tenant_a_id,
                "type": "access",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        # Request comes from tenant B
        request = MagicMock()
        request.state.tenant_id = tenant_b_id
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}

        # Capture what AuditService.log receives
        captured_calls = []

        original_log = None

        async def mock_log(self_audit, **kwargs):
            captured_calls.append(kwargs)

        with patch("app.services.audit.AuditService.log", mock_log):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await validate_token_tenant(request, token)

            assert exc_info.value.status_code == 403
            assert "not valid for this school" in exc_info.value.detail.lower()

        # Verify audit log was called with correct details
        assert len(captured_calls) == 1
        call = captured_calls[0]
        assert call["event_type"] == "auth.cross_tenant.rejected"
        assert call["details"]["token_tenant_id"] == tenant_a_id
        assert call["details"]["request_tenant_id"] == tenant_b_id


# ---------------------------------------------------------------------------
# 7. Subscription error code split — same message for cancelled/suspended
# ---------------------------------------------------------------------------

class TestSubscriptionEnforcement:
    """Test enforce_subscription returns consistent message for cancelled/suspended."""

    @pytest.mark.anyio
    async def test_cancelled_tenant_gets_403(self):
        from app.api.deps import enforce_subscription
        from fastapi import HTTPException

        request = MagicMock()
        request.url.path = "/api/v1/students"
        request.state.tenant_status = "cancelled"
        request.headers = {"authorization": "Bearer some-token"}

        with pytest.raises(HTTPException) as exc_info:
            await enforce_subscription(request)

        assert exc_info.value.status_code == 403
        assert "no longer active" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_suspended_tenant_gets_403(self):
        from app.api.deps import enforce_subscription
        from fastapi import HTTPException

        request = MagicMock()
        request.url.path = "/api/v1/students"
        request.state.tenant_status = "suspended"
        request.headers = {"authorization": "Bearer some-token"}

        with pytest.raises(HTTPException) as exc_info:
            await enforce_subscription(request)

        assert exc_info.value.status_code == 403
        assert "no longer active" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_cancelled_and_suspended_same_message(self):
        """Both cancelled and suspended tenants get the same user-facing message."""
        from app.api.deps import enforce_subscription
        from fastapi import HTTPException

        messages = {}
        for status in ("cancelled", "suspended"):
            request = MagicMock()
            request.url.path = "/api/v1/students"
            request.state.tenant_status = status
            request.headers = {"authorization": "Bearer some-token"}

            with pytest.raises(HTTPException) as exc_info:
                await enforce_subscription(request)
            messages[status] = exc_info.value.detail

        assert messages["cancelled"] == messages["suspended"]

    @pytest.mark.anyio
    async def test_subscription_exempt_paths_skip_enforcement(self):
        """Subscription management paths are exempt from enforcement."""
        from app.api.deps import enforce_subscription

        request = MagicMock()
        request.url.path = "/api/v1/subscription/plans"
        request.state.tenant_status = "cancelled"
        request.headers = {"authorization": "Bearer some-token"}

        # Should NOT raise — exempt path
        await enforce_subscription(request)

    @pytest.mark.anyio
    async def test_unauthenticated_request_skips_enforcement(self):
        """Requests without Bearer token skip subscription enforcement."""
        from app.api.deps import enforce_subscription

        request = MagicMock()
        request.url.path = "/api/v1/students"
        request.state.tenant_status = "cancelled"
        request.headers = {}

        # Should NOT raise — no auth header
        await enforce_subscription(request)


# ---------------------------------------------------------------------------
# 8. Tenant cleanup — table name validation
# ---------------------------------------------------------------------------

class TestTenantCleanupTableValidation:
    """Test _delete_tenant_rows raises ValueError for invalid table names."""

    @pytest.mark.anyio
    async def test_invalid_table_name_raises_valueerror(self):
        from app.tasks.tenant_cleanup import _delete_tenant_rows

        db = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table name"):
            await _delete_tenant_rows(db, "not-a-valid-identifier", uuid4(), dry_run=True)

    @pytest.mark.anyio
    async def test_sql_injection_attempt_raises_valueerror(self):
        from app.tasks.tenant_cleanup import _delete_tenant_rows

        db = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table name"):
            await _delete_tenant_rows(db, "users; DROP TABLE tenants", uuid4(), dry_run=True)

    @pytest.mark.anyio
    async def test_valid_table_name_does_not_raise(self):
        from app.tasks.tenant_cleanup import _delete_tenant_rows

        db = AsyncMock()
        # Mock the execute to return a result with scalar
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)

        # Should not raise
        count = await _delete_tenant_rows(db, "students", uuid4(), dry_run=True)
        assert count == 0


# ---------------------------------------------------------------------------
# 9. Email hex color validation
# ---------------------------------------------------------------------------

class TestHexColorValidation:
    """Test _HEX_COLOR_RE regex matches valid hex colors and rejects injection."""

    @pytest.fixture
    def hex_re(self):
        from app.services.email import _HEX_COLOR_RE

        return _HEX_COLOR_RE

    def test_valid_6_digit_hex(self, hex_re):
        assert hex_re.match("#1B4F72")

    def test_valid_3_digit_hex(self, hex_re):
        assert hex_re.match("#fff")

    def test_valid_black(self, hex_re):
        assert hex_re.match("#000000")

    def test_valid_short_black(self, hex_re):
        assert hex_re.match("#000")

    def test_rejects_named_color(self, hex_re):
        assert hex_re.match("red") is None

    def test_rejects_invalid_hex_chars(self, hex_re):
        assert hex_re.match("#xyz") is None

    def test_rejects_css_injection(self, hex_re):
        assert hex_re.match("#1B4F72; background-image: url(evil)") is None

    def test_rejects_empty_string(self, hex_re):
        assert hex_re.match("") is None

    def test_rejects_hash_only(self, hex_re):
        assert hex_re.match("#") is None

    def test_rejects_too_long(self, hex_re):
        assert hex_re.match("#1234567") is None


# ---------------------------------------------------------------------------
# 10. HTML escaping in email fallbacks
# ---------------------------------------------------------------------------

class TestEmailHtmlEscaping:
    """Test that email fallback HTML escapes user-controlled values."""

    def test_school_name_xss_escaped_in_welcome_fallback(self):
        """XSS in school name must be escaped in fallback HTML."""
        from app.services.email import EmailService

        service = EmailService()
        malicious_name = "<script>alert('xss')</script>"

        result = service._get_welcome_email_fallback(
            admin_name="Admin",
            school_name=malicious_name,
            portal_url="https://test.simsplus.io",
            admin_email="admin@test.com",
        )

        # The raw script tag must NOT appear
        assert "<script>" not in result
        # The escaped version must appear
        assert html.escape(malicious_name) in result

    def test_admin_name_xss_escaped_in_welcome_fallback(self):
        """XSS in admin name must be escaped."""
        from app.services.email import EmailService

        service = EmailService()
        malicious_admin = '<img onerror="alert(1)" src=x>'

        result = service._get_welcome_email_fallback(
            admin_name=malicious_admin,
            school_name="Safe School",
            portal_url="https://test.simsplus.io",
            admin_email="admin@test.com",
        )

        assert 'onerror="alert(1)"' not in result
        assert html.escape(malicious_admin) in result

    def test_email_xss_escaped_in_welcome_fallback(self):
        """XSS in admin email must be escaped."""
        from app.services.email import EmailService

        service = EmailService()
        malicious_email = '"><script>alert(1)</script>'

        result = service._get_welcome_email_fallback(
            admin_name="Admin",
            school_name="Safe School",
            portal_url="https://test.simsplus.io",
            admin_email=malicious_email,
        )

        assert "<script>" not in result

    def test_trial_date_xss_escaped(self):
        """XSS in trial_ends_at must be escaped."""
        from app.services.email import EmailService

        service = EmailService()
        malicious_date = '<img src=x onerror="alert(1)">'

        result = service._get_welcome_email_fallback(
            admin_name="Admin",
            school_name="Safe School",
            portal_url="https://test.simsplus.io",
            admin_email="admin@test.com",
            trial_ends_at=malicious_date,
        )

        assert 'onerror="alert(1)"' not in result
        assert html.escape(malicious_date) in result
