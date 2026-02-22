"""
Tenant Middleware Tests

Tests for subdomain extraction, validation, and tenant context setting.
These are pure unit tests -- no database or async required.
"""

import pytest
from app.middleware.tenant import (
    extract_subdomain_from_host,
    is_public_path,
    RESERVED_SUBDOMAINS,
)


class TestSubdomainExtraction:
    """Tests for extract_subdomain_from_host()."""

    def test_production_subdomain(self):
        assert extract_subdomain_from_host("presec.simsplus.io") == "presec"

    def test_production_with_port(self):
        assert extract_subdomain_from_host("presec.simsplus.io:443") == "presec"

    def test_localhost_subdomain(self):
        assert extract_subdomain_from_host("presec.localhost") == "presec"

    def test_localhost_with_port(self):
        assert extract_subdomain_from_host("presec.localhost:3000") == "presec"

    def test_bare_localhost_returns_none(self):
        assert extract_subdomain_from_host("localhost") is None

    def test_bare_localhost_with_port_returns_none(self):
        assert extract_subdomain_from_host("localhost:3000") is None

    def test_reserved_subdomain_returns_none(self):
        assert extract_subdomain_from_host("www.simsplus.io") is None
        assert extract_subdomain_from_host("api.simsplus.io") is None
        assert extract_subdomain_from_host("admin.simsplus.io") is None

    def test_reserved_subdomain_localhost_returns_none(self):
        assert extract_subdomain_from_host("www.localhost") is None
        assert extract_subdomain_from_host("api.localhost") is None

    def test_too_short_subdomain_returns_none(self):
        # Subdomains must be >= 4 characters
        assert extract_subdomain_from_host("ab.simsplus.io") is None
        assert extract_subdomain_from_host("abc.simsplus.io") is None

    def test_minimum_length_subdomain(self):
        assert extract_subdomain_from_host("abcd.simsplus.io") == "abcd"

    def test_hyphenated_subdomain(self):
        assert extract_subdomain_from_host("st-johns.simsplus.io") == "st-johns"

    def test_uppercase_normalized_to_lowercase(self):
        assert extract_subdomain_from_host("PRESEC.simsplus.io") == "presec"

    def test_ip_address_returns_none(self):
        assert extract_subdomain_from_host("127.0.0.1") is None
        assert extract_subdomain_from_host("127.0.0.1:8000") is None


class TestPublicPaths:
    """Tests for is_public_path()."""

    def test_health_is_public(self):
        assert is_public_path("/health") is True

    def test_docs_is_public(self):
        assert is_public_path("/docs") is True

    def test_tenant_validation_is_public(self):
        assert is_public_path("/api/v1/tenant/validate/presec") is True

    def test_onboarding_is_public(self):
        assert is_public_path("/api/v1/onboarding/register") is True

    def test_students_is_not_public(self):
        assert is_public_path("/api/v1/students") is False

    def test_users_is_not_public(self):
        assert is_public_path("/api/v1/users") is False


class TestReservedSubdomains:
    """Tests for reserved subdomain list completeness."""

    def test_minimum_count(self):
        assert len(RESERVED_SUBDOMAINS) >= 35

    def test_critical_subdomains_reserved(self):
        critical = {"www", "api", "admin", "app", "mail", "cdn", "status"}
        assert critical.issubset(RESERVED_SUBDOMAINS)
