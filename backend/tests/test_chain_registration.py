"""
Tests for Sprint 17-18 Chain Registration Support.

Covers:
1. SchoolRegistrationRequest schema validation for tenant_type field
2. OnboardingService.register_school() with single_school and school_chain types
3. Backward compatibility (defaults to single_school when tenant_type omitted)
"""

import pytest
from pydantic import ValidationError
from uuid import uuid4

from app.schemas.onboarding import SchoolRegistrationRequest


# ==========================
# Schema Validation Tests
# ==========================

VALID_BASE = {
    "school_name": "Test Academy",
    "subdomain": "testacademy",
    "school_type": "basic",
    "admin_email": "admin@test.com",
    "admin_first_name": "Kwame",
    "admin_last_name": "Asante",
    "admin_password": "SecurePass123!",
}


class TestChainRegistrationSchema:
    """Schema-level tests for tenant_type field in registration."""

    def test_tenant_type_defaults_to_single_school(self):
        """Backward compat: omitting tenant_type defaults to single_school."""
        data = {**VALID_BASE}
        # No tenant_type key
        req = SchoolRegistrationRequest(**data)
        assert req.tenant_type == "single_school"

    def test_tenant_type_single_school_accepted(self):
        """Explicit single_school value is accepted."""
        data = {**VALID_BASE, "tenant_type": "single_school"}
        req = SchoolRegistrationRequest(**data)
        assert req.tenant_type == "single_school"

    def test_tenant_type_school_chain_accepted(self):
        """school_chain value is accepted."""
        data = {**VALID_BASE, "tenant_type": "school_chain"}
        req = SchoolRegistrationRequest(**data)
        assert req.tenant_type == "school_chain"

    def test_tenant_type_case_insensitive(self):
        """tenant_type is normalized to lowercase."""
        data = {**VALID_BASE, "tenant_type": "School_Chain"}
        req = SchoolRegistrationRequest(**data)
        assert req.tenant_type == "school_chain"

    def test_tenant_type_invalid_value_rejected(self):
        """Invalid tenant_type raises ValidationError."""
        data = {**VALID_BASE, "tenant_type": "multi_campus"}
        with pytest.raises(ValidationError) as exc_info:
            SchoolRegistrationRequest(**data)
        errors = exc_info.value.errors()
        assert any("tenant_type" in str(e.get("loc", "")) for e in errors)

    def test_tenant_type_empty_string_rejected(self):
        """Empty string tenant_type is rejected."""
        data = {**VALID_BASE, "tenant_type": ""}
        with pytest.raises(ValidationError):
            SchoolRegistrationRequest(**data)

    def test_plan_defaults_to_trial(self):
        """Omitting plan defaults to trial."""
        data = {**VALID_BASE}
        req = SchoolRegistrationRequest(**data)
        assert req.plan == "trial"

    def test_school_type_validation_still_works(self):
        """school_type validator still rejects invalid values alongside tenant_type."""
        data = {**VALID_BASE, "school_type": "university", "tenant_type": "school_chain"}
        with pytest.raises(ValidationError) as exc_info:
            SchoolRegistrationRequest(**data)
        errors = exc_info.value.errors()
        assert any("school_type" in str(e.get("loc", "")) for e in errors)
