"""
SIMS Plus - E2E Test Fixtures

Provides seeded tenant/school/user fixtures and authenticated HTTP clients
for full end-to-end flow testing.

Architecture:
- Seeds data via admin_session_maker (postgres superuser, bypasses RLS)
- Patches middleware and deps to use the test database
- Authenticated client uses JWT + X-Subdomain header so the real middleware
  sets request.state.tenant_id correctly
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from unittest.mock import patch

from app.core.security import create_access_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_engine, app_session_maker


E2E_PASSWORD = "TestPass123!"
E2E_EMAIL_DOMAIN = "e2etest.simsplus.io"

# Session maker for the middleware to look up tenants in the test DB
_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


@pytest_asyncio.fixture
async def seeded_tenant():
    """Create a tenant + school + admin user via admin engine (bypasses RLS).

    Yields a dict with all the IDs needed for authenticated requests.
    Cleans up all created rows after the test.
    """
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"e2e-{uuid4().hex[:8]}"
    password_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        # Create tenant
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {
                "id": str(tenant_id),
                "subdomain": subdomain,
                "slug": subdomain,
                "name": f"E2E Test School {subdomain}",
            },
        )

        # Create school
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), :name, :slug, 'E2E', 'basic')
            """),
            {
                "id": str(school_id),
                "tenant_id": str(tenant_id),
                "name": f"E2E Test School {subdomain}",
                "slug": subdomain,
            },
        )

        # Create admin user
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), :email, :password_hash,
                    'Admin', 'E2E', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {
                "id": str(user_id),
                "tenant_id": str(tenant_id),
                "email": f"admin@{subdomain}.{E2E_EMAIL_DOMAIN}",
                "password_hash": password_hash,
            },
        )

        await session.commit()

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "subdomain": subdomain,
        "email": f"admin@{subdomain}.{E2E_EMAIL_DOMAIN}",
        "password": E2E_PASSWORD,
    }

    # Cleanup: delete in reverse FK order
    async with admin_session_maker() as session:
        for table in [
            "student_attendance", "staff_attendance",
            "exam_scores", "exam_subjects", "exams",
            "continuous_assessments", "term_reports", "score_change_logs",
            "invoice_items", "invoice_scholarship_items", "payments",
            "invoices", "fee_items", "fee_structures", "fee_types",
            "credit_notes", "finance_audit_log",
            "scholarships", "student_scholarships", "scholarship_applications",
            "student_guardians", "guardians", "students",
            "class_subjects", "class_sections", "classes",
            "subjects", "grading_scales", "grades",
            "assessment_weights", "academic_settings",
            "terms", "academic_years",
            "staff_class_assignments", "staff", "departments",
            "school_holidays", "school_periods", "class_timetables",
            "notifications", "sms_log",
            "users", "schools",
        ]:
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
async def auth_client(seeded_tenant):
    """Authenticated AsyncClient with JWT and tenant context via middleware.

    Uses X-Subdomain header to trigger the real TenantMiddleware, which sets
    request.state.tenant_id. The middleware session maker is patched to use
    the test database so tenant lookups succeed.
    """
    tenant_data = seeded_tenant
    tenant_id = tenant_data["tenant_id"]

    # Create JWT token with all claims needed by ValidatedUser / CurrentUserId
    token = create_access_token(
        subject=str(tenant_data["user_id"]),
        tenant_id=str(tenant_id),
        school_id=str(tenant_data["school_id"]),
        role="school_admin",
        permissions=["*"],
        extra_claims={"email": tenant_data["email"]},
    )

    # Override get_db to use test DB with tenant context
    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                # Read tenant_id from request.state (set by middleware)
                req_tenant_id = getattr(request, "state", None)
                tid = getattr(req_tenant_id, "tenant_id", None) if req_tenant_id else None
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

    # Patch middleware + main session makers so tenant lookups use test DB
    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": tenant_data["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest_asyncio.fixture
async def unauth_client():
    """Unauthenticated HTTP client for public endpoints and auth rejection tests."""
    # Patch session makers so onboarding/tenant lookup uses test DB
    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):

        # Override get_unscoped_db for onboarding endpoints
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
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    app.dependency_overrides.pop(get_unscoped_db, None)
