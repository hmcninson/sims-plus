"""
Tests for onboarding gap closure changes.

Covers:
- School profile update (ges_registration_number, calendar_type, school_type, PROTECTED_FIELDS)
- Setup wizard step endpoint (forward-only progress, completion, validation)
- Plans endpoint (trial_days from settings)
- Academic year overlap (allow_overlap flag, role restriction)
"""

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fastapi import Request
from app.core.security import create_access_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_engine, app_session_maker


_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)

_PASSWORD = "TestPass123!"


@pytest_asyncio.fixture
async def tenant_and_school():
    """Create a tenant + school + admin user via admin engine."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"onbgap-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "subdomain": subdomain,
             "slug": subdomain, "name": f"Onboarding Gap Test {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), :name, :slug, 'OBG', 'basic')
            """),
            {"id": str(school_id), "tenant_id": str(tenant_id),
             "name": f"OBG School {subdomain}", "slug": subdomain},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), :email, :password_hash,
                    'Admin', 'Test', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(user_id), "tenant_id": str(tenant_id),
             "email": f"admin@{subdomain}.example.com",
             "password_hash": hash_password(_PASSWORD)},
        )
        await session.commit()

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "subdomain": subdomain,
        "email": f"admin@{subdomain}.example.com",
    }

    # Cleanup
    async with admin_session_maker() as session:
        for tbl in ["academic_years", "users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {tbl} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


def _make_token(data: dict, role: str = "school_admin", permissions=None):
    """Create a JWT token for the given tenant/user."""
    return create_access_token(
        subject=str(data["user_id"]),
        tenant_id=str(data["tenant_id"]),
        school_id=str(data["school_id"]),
        role=role,
        permissions=permissions or ["*"],
        extra_claims={"email": data["email"]},
    )


@pytest_asyncio.fixture
async def auth_client(tenant_and_school):
    """Authenticated client with school_admin role."""
    data = tenant_and_school
    token = _make_token(data)

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

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": data["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest_asyncio.fixture
async def teacher_client(tenant_and_school):
    """Authenticated client with teacher role (limited permissions)."""
    data = tenant_and_school
    token = _make_token(data, role="teacher", permissions=["academics.create", "academics.read"])

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

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": data["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest_asyncio.fixture
async def unauth_client():
    """Unauthenticated client for public/auth rejection tests."""
    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):

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

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            yield client

    app.dependency_overrides.pop(get_unscoped_db, None)


# =============================================
# School Profile Update Tests
# =============================================


class TestSchoolProfileUpdate:
    """Tests for PUT /api/v1/schools/current with new fields."""

    @pytest.mark.asyncio
    async def test_update_ges_registration_number(self, auth_client, tenant_and_school):
        """Updating ges_registration_number via school profile update works."""
        resp = await auth_client.put(
            "/api/v1/schools/current",
            json={"ges_registration_number": "GES-CR-2026-001"},
        )
        assert resp.status_code == 200
        assert resp.json()["ges_registration_number"] == "GES-CR-2026-001"

    @pytest.mark.asyncio
    async def test_update_calendar_type_valid(self, auth_client, tenant_and_school):
        """Updating calendar_type to each valid value succeeds."""
        for cal_type in ["term", "semester", "quarter"]:
            resp = await auth_client.put(
                "/api/v1/schools/current",
                json={"calendar_type": cal_type},
            )
            assert resp.status_code == 200
            assert resp.json()["calendar_type"] == cal_type

    @pytest.mark.asyncio
    async def test_update_calendar_type_invalid(self, auth_client, tenant_and_school):
        """Updating calendar_type to an invalid value returns 422."""
        resp = await auth_client.put(
            "/api/v1/schools/current",
            json={"calendar_type": "bimonthly"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_school_type_valid(self, auth_client, tenant_and_school):
        """Updating school_type to a valid value succeeds."""
        resp = await auth_client.put(
            "/api/v1/schools/current",
            json={"school_type": "shs"},
        )
        assert resp.status_code == 200
        assert resp.json()["school_type"] == "shs"

    @pytest.mark.asyncio
    async def test_update_school_type_invalid(self, auth_client, tenant_and_school):
        """Updating school_type to an invalid value returns 422."""
        resp = await auth_client.put(
            "/api/v1/schools/current",
            json={"school_type": "university"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_protected_fields_ignored(self, auth_client, tenant_and_school):
        """PROTECTED_FIELDS (tenant_id, setup_completed, etc.) cannot be modified."""
        school_id = str(tenant_and_school["school_id"])

        # Get current state
        get_resp = await auth_client.get("/api/v1/schools/current")
        assert get_resp.status_code == 200
        original = get_resp.json()

        # Try to set protected fields — they should be silently ignored
        resp = await auth_client.put(
            "/api/v1/schools/current",
            json={
                "setup_completed": True,
                "setup_wizard_step": 99,
                "motto": "New Motto",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Protected fields unchanged
        assert data["setup_completed"] == original["setup_completed"]
        assert data["setup_wizard_step"] == original["setup_wizard_step"]
        # Non-protected field updated
        assert data["motto"] == "New Motto"


# =============================================
# Wizard Step Tests
# =============================================


class TestWizardStep:
    """Tests for PUT /api/v1/schools/current/wizard-step."""

    @pytest.mark.asyncio
    async def test_set_wizard_step(self, auth_client, tenant_and_school):
        """Setting wizard step to 1 succeeds."""
        resp = await auth_client.put(
            "/api/v1/schools/current/wizard-step",
            json={"step": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_wizard_step"] == 1
        assert data["setup_completed"] is False

    @pytest.mark.asyncio
    async def test_forward_only_progress(self, auth_client, tenant_and_school):
        """Wizard step only moves forward, never backward."""
        # Set to step 3
        resp = await auth_client.put(
            "/api/v1/schools/current/wizard-step",
            json={"step": 3},
        )
        assert resp.status_code == 200
        assert resp.json()["setup_wizard_step"] == 3

        # Try to go back to step 1 — should stay at 3
        resp = await auth_client.put(
            "/api/v1/schools/current/wizard-step",
            json={"step": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["setup_wizard_step"] == 3

    @pytest.mark.asyncio
    async def test_set_completed(self, auth_client, tenant_and_school):
        """Setting completed=true marks setup_completed on the school."""
        resp = await auth_client.put(
            "/api/v1/schools/current/wizard-step",
            json={"step": 7, "completed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_wizard_step"] == 7
        assert data["setup_completed"] is True

    @pytest.mark.asyncio
    async def test_step_out_of_range_high(self, auth_client, tenant_and_school):
        """Step=8 (above max 7) returns 422."""
        resp = await auth_client.put(
            "/api/v1/schools/current/wizard-step",
            json={"step": 8},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_step_negative(self, auth_client, tenant_and_school):
        """Negative step returns 422."""
        resp = await auth_client.put(
            "/api/v1/schools/current/wizard-step",
            json={"step": -1},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_wizard_step_requires_auth(self, unauth_client):
        """Unauthenticated request to wizard-step is rejected (400 no tenant or 401 no auth)."""
        resp = await unauth_client.put(
            "/api/v1/schools/current/wizard-step",
            json={"step": 1},
        )
        # Without X-Subdomain header, the tenant middleware rejects with 400.
        # Without a Bearer token but with a valid subdomain, it would be 401.
        # Either way, the request does NOT succeed.
        assert resp.status_code in (400, 401)


# =============================================
# Plans Endpoint Test
# =============================================


class TestPlansEndpoint:
    """Tests for GET /api/v1/onboarding/plans."""

    @pytest.mark.asyncio
    async def test_plans_trial_period_matches_settings(self, unauth_client):
        """Trial plan period should use settings.TRIAL_DAYS, not a hardcoded value."""
        from app.config import get_settings
        settings = get_settings()

        resp = await unauth_client.get("/api/v1/onboarding/plans")
        assert resp.status_code == 200
        data = resp.json()

        # The top-level trial_days field
        assert data["trial_days"] == settings.TRIAL_DAYS

        # The trial plan's period string
        trial_plan = next(p for p in data["plans"] if p["id"] == "trial")
        assert trial_plan["period"] == f"{settings.TRIAL_DAYS} days"


# =============================================
# Academic Year Overlap Tests
# =============================================


class TestAcademicYearOverlap:
    """Tests for allow_overlap on academic year create."""

    @pytest.mark.asyncio
    async def test_overlapping_dates_rejected_by_default(self, auth_client, tenant_and_school):
        """Creating two academic years with overlapping dates returns 409."""
        # Create the first year
        resp1 = await auth_client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "2025/2026",
                "start_date": "2025-09-01",
                "end_date": "2026-07-31",
            },
        )
        assert resp1.status_code == 201

        # Create a second year with overlapping dates
        resp2 = await auth_client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "2025/2026 Sandwich",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_overlapping_dates_allowed_with_flag(self, auth_client, tenant_and_school):
        """Admin with allow_overlap=true can create overlapping academic years."""
        # Create the first year
        resp1 = await auth_client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "2024/2025",
                "start_date": "2024-09-01",
                "end_date": "2025-07-31",
            },
        )
        assert resp1.status_code == 201

        # Create overlapping year with allow_overlap
        resp2 = await auth_client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "2024/2025 Evening",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "allow_overlap": True,
            },
        )
        assert resp2.status_code == 201

    @pytest.mark.asyncio
    async def test_teacher_allow_overlap_silently_ignored(self, teacher_client, tenant_and_school):
        """Teacher role with allow_overlap=true should have it ignored, resulting in 409."""
        # Create the first year as teacher
        resp1 = await teacher_client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "2023/2024",
                "start_date": "2023-09-01",
                "end_date": "2024-07-31",
            },
        )
        assert resp1.status_code == 201

        # Try overlapping with allow_overlap — should be ignored for teacher
        resp2 = await teacher_client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "2023/2024 Parallel",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "allow_overlap": True,
            },
        )
        assert resp2.status_code == 409
