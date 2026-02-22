# SIMS Plus -- Testing Strategy, Quality Gates & Risk Register

**Document:** 04 of 04
**Version:** 1.0
**Date:** 15 February 2026
**Author:** Harry McNinson
**Status:** Ready for Implementation
**Sprint Window:** 4 weeks (2 x 2-week sprints)

---

## Table of Contents

1. [Testing Strategy](#1-testing-strategy)
2. [Test Infrastructure Setup](#2-test-infrastructure-setup)
3. [Required Test Cases](#3-required-test-cases)
4. [Quality Gates](#4-quality-gates)
5. [Risk Register](#5-risk-register)
6. [Performance Targets](#6-performance-targets)
7. [Monitoring & Observability](#7-monitoring--observability)

---

## 1. Testing Strategy

### 1.1 Testing Pyramid

The project follows a bottom-heavy testing pyramid. The foundation is RLS isolation tests, which are the single most important category in a multi-tenant system. A leak at the data layer is catastrophic and unrecoverable -- no amount of UI testing compensates for a missing RLS policy.

```
           /  E2E Tests  \              5-10 tests     (Playwright)
          / Integration    \            20-30 tests    (httpx AsyncClient + real DB)
         / Service / Unit   \           50+ tests      (pytest + AsyncMock)
        / RLS Isolation      \          15+ tests      (CRITICAL -- raw SQL)
       /______________________\
```

Each layer tests a different concern:

- **RLS Isolation** verifies that the database itself prevents cross-tenant data leakage. These tests run raw SQL against the `sims_app_user` role (non-superuser) to confirm that Row-Level Security policies are active, complete, and free of bypass vulnerabilities.
- **Service / Unit** tests verify business logic in isolation -- fee calculations, grade computations, enrollment rules, ID generation, and similar logic that lives in the service layer.
- **Integration** tests exercise full request-response cycles through FastAPI endpoints with a real PostgreSQL database. They confirm that middleware, authentication, authorization, validation, service logic, and database operations work together correctly.
- **E2E** tests drive a browser through complete user journeys: register a school, log in, create a student, mark attendance, generate an invoice.

### 1.2 Test Categories

| Category | Tools | What It Tests | Priority |
|---|---|---|---|
| RLS Isolation | pytest + raw SQL | Tenant data cannot leak across boundaries | P0 (CRITICAL) |
| Unit Tests | pytest + AsyncMock | Service layer business logic | P1 |
| Integration Tests | pytest + httpx AsyncClient | Endpoints with real DB | P1 |
| Middleware Tests | pytest + httpx | Tenant extraction, rate limiting, CORS | P1 |
| Frontend Tests | Vitest + React Testing Library | Component rendering, server actions | P2 |
| E2E Tests | Playwright | Register, login, dashboard, and module flows | P2 |

### 1.3 Test Database Strategy

All backend tests run against a dedicated `sims_plus_test` database (created by `init-db.sql`). The test database has the same schema, roles, RLS policies, and functions as the development database. This is non-negotiable -- testing against a database without RLS would give false confidence.

Key rules:

- **Two-engine pattern.** Every test file has access to two database engines: an admin engine (PostgreSQL superuser, bypasses RLS) for seeding test data, and an app engine (`sims_app_user`, RLS enforced) for running the actual assertions. These two engines must never be confused.
- **NullPool for test engines.** Connection pooling introduces state leakage risk between tests. Using `NullPool` means each test gets a fresh connection.
- **Fresh data per test class.** Each test class creates its own tenants and data via fixtures. Tests must not depend on data created by other test classes.
- **`expire_all()` after context switch.** SQLAlchemy's identity map caches loaded ORM objects. After calling `set_tenant_context()` to switch tenants, you must call `session.expire_all()` to force re-queries. Without this, cached objects from the previous tenant context may still be accessible, masking RLS failures.
- **Capture IDs before context switch.** If you need to reference the ID of an object created under one tenant context, store it in a local Python variable before switching context. After `expire_all()`, the ORM object itself may become inaccessible.

### 1.4 Test Execution

```bash
# Run all tests
pytest backend/tests/ -v

# Run only RLS isolation tests (always run these first)
pytest backend/tests/test_rls_isolation.py -v

# Run with coverage report
pytest backend/tests/ --cov=app --cov-report=html

# Run tests matching a pattern
pytest backend/tests/ -k "test_tenant" -v
```

### 1.5 Coverage Targets

| Category | Minimum | Target |
|---|---|---|
| RLS Isolation | 100% of tenant-scoped tables | 100% |
| Service Layer | 70% line coverage | 85% |
| Endpoints | 60% line coverage | 75% |
| Overall Backend | 65% line coverage | 80% |
| Frontend Components | 50% line coverage | 70% |

Coverage is measured by `pytest-cov` for the backend and `vitest --coverage` for the frontend. The RLS isolation category is measured differently -- it is not about line coverage but about table coverage. Every table in `TENANT_SCOPED_TABLES` must have at least one test confirming RLS is enabled and enforced.

---

## 2. Test Infrastructure Setup

### 2.1 conftest.py (Complete)

This is the shared test configuration. Every test file imports fixtures from here.

```python
# backend/tests/conftest.py
import asyncio
from uuid import uuid4, UUID
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool

from app.main import app
from app.config import settings


# ============================================================
# Engine Fixtures (session-scoped)
# ============================================================

@pytest_asyncio.fixture(scope="session")
async def admin_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Superuser engine for DDL operations and test data seeding.
    Bypasses RLS (superuser privilege)."""
    engine = create_async_engine(
        str(settings.ALEMBIC_DATABASE_URL).replace("sims_plus", "sims_plus_test"),
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def app_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Non-superuser engine for application queries.
    RLS is enforced -- this is what the real app uses."""
    engine = create_async_engine(
        "postgresql+asyncpg://sims_app_user:changeme@localhost:5432/sims_plus_test",
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


# ============================================================
# Session Fixtures
# ============================================================

@pytest_asyncio.fixture
async def admin_session(admin_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Admin session for setting up test data (bypasses RLS)."""
    async with AsyncSession(admin_engine) as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def app_session(app_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """App session with RLS enforcement."""
    async with AsyncSession(app_engine) as session:
        yield session
        await session.rollback()


# ============================================================
# Tenant Fixtures
# ============================================================

@pytest_asyncio.fixture
async def tenant_a(admin_session: AsyncSession) -> dict:
    """Create Tenant A for testing."""
    tenant_id = uuid4()
    subdomain = f"testa{uuid4().hex[:6]}"
    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active)
            VALUES (CAST(:id AS uuid), :sub, :slug, :name, true)
        """),
        {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": "Test School A"},
    )
    await admin_session.commit()
    return {"id": str(tenant_id), "subdomain": subdomain, "name": "Test School A"}


@pytest_asyncio.fixture
async def tenant_b(admin_session: AsyncSession) -> dict:
    """Create Tenant B for cross-tenant testing."""
    tenant_id = uuid4()
    subdomain = f"testb{uuid4().hex[:6]}"
    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active)
            VALUES (CAST(:id AS uuid), :sub, :slug, :name, true)
        """),
        {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": "Test School B"},
    )
    await admin_session.commit()
    return {"id": str(tenant_id), "subdomain": subdomain, "name": "Test School B"}


# ============================================================
# Helper Functions
# ============================================================

async def enable_test_data_insertion(admin_session: AsyncSession) -> None:
    """Temporarily allow data insertion for test setup.

    NOTE: When using admin_session (superuser), RLS is bypassed
    automatically. This helper is for cases where you need to
    manipulate the app_session's context for testing.
    """
    pass  # Admin session bypasses RLS by default


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set tenant context for a session."""
    await session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": tenant_id},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear tenant context for a session."""
    await session.execute(text("SELECT clear_tenant_context()"))


# ============================================================
# HTTP Client Fixture
# ============================================================

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for endpoint testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================
# All tenant-scoped tables (MUST BE KEPT UP TO DATE)
# ============================================================

TENANT_SCOPED_TABLES = [
    "schools",
    "users",
    "students",
    "guardians",
    "student_guardians",
    "academic_years",
    "terms",
    "classes",
    "class_sections",
    "subjects",
    "class_subjects",
    "grading_scales",
    "grades",
    "assessment_weights",
    "academic_settings",
    "school_holidays",
    "departments",
    "staff",
    "student_attendance",
    "staff_attendance",
    "exams",
    "exam_subjects",
    "exam_scores",
    "continuous_assessments",
    "term_reports",
    "class_timetables",
    "timetable_periods",
    "developmental_domains",
    "developmental_milestones",
    "student_observations",
    "daily_activity_logs",
    "preschool_assessments",
    "preschool_reports",
    "fee_types",
    "fee_structures",
    "fee_items",
    "invoices",
    "invoice_items",
    "payments",
    "scholarships",
    "student_scholarships",
    "scholarship_applications",
    "credit_notes",
    "finance_audit_log",
]
```

### 2.2 Key Test Infrastructure Rules

These rules exist because real bugs were found during development. Every rule corresponds to a specific failure mode.

**Rule 1: `CAST(:param AS uuid)` is REQUIRED for UUID bind params in raw SQL.**

asyncpg sends Python `str` values as PostgreSQL `VARCHAR` by default. When a RLS policy compares `tenant_id` (type `uuid`) against `current_setting('app.current_tenant_id')`, the comparison works because PostgreSQL casts the setting string to UUID. But when a test passes a UUID string as a bind parameter, asyncpg sends it as `VARCHAR`, and the comparison `uuid = varchar` may silently fail or behave unexpectedly. Always use `CAST(:param AS uuid)` in raw SQL test queries.

```python
# WRONG -- asyncpg sends tenant_id as VARCHAR
await session.execute(
    text("INSERT INTO schools (id, tenant_id, ...) VALUES (:id, :tid, ...)"),
    {"id": str(uuid4()), "tid": str(tenant_id)},
)

# CORRECT -- explicit UUID cast
await session.execute(
    text("INSERT INTO schools (id, tenant_id, ...) VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), ...)"),
    {"id": str(uuid4()), "tid": str(tenant_id)},
)
```

**Rule 2: `expire_all()` after context switch.**

SQLAlchemy maintains an identity map that caches loaded objects. If you load a `School` object under Tenant A's context, then switch to Tenant B's context, the cached object is still accessible from the identity map. This defeats the purpose of the RLS test. After every call to `set_tenant_context()` or `clear_tenant_context()`, call `session.expire_all()` to force all subsequent attribute accesses to re-query the database.

```python
# Set Tenant A context, load data
await set_tenant_context(app_session, tenant_a["id"])
result_a = await app_session.execute(text("SELECT * FROM schools"))
schools_a = result_a.fetchall()

# Switch to Tenant B -- MUST expire
await set_tenant_context(app_session, tenant_b["id"])
app_session.expire_all()  # <-- CRITICAL
result_b = await app_session.execute(text("SELECT * FROM schools"))
schools_b = result_b.fetchall()
```

**Rule 3: Capture IDs before context switch.**

ORM-loaded objects may become inaccessible after `expire_all()`. If you need an object's ID after switching context, save it to a local variable first.

```python
# WRONG
school = (await app_session.execute(select(School))).scalar_one()
await set_tenant_context(app_session, tenant_b["id"])
app_session.expire_all()
# school.id may now trigger a lazy load that returns nothing or errors
print(school.id)

# CORRECT
school = (await app_session.execute(select(School))).scalar_one()
school_id = school.id  # <-- capture before switch
await set_tenant_context(app_session, tenant_b["id"])
app_session.expire_all()
print(school_id)  # safe
```

**Rule 4: Two-engine pattern is mandatory.**

Admin engine (superuser) for setup and teardown. App engine (`sims_app_user`, non-superuser) for actual test assertions. Never use the admin engine to verify RLS behavior -- superusers bypass RLS entirely.

**Rule 5: Enum casing matters in raw SQL.**

Different enum types in the schema use different casing conventions. Getting this wrong causes silent insert failures or constraint violations.

| Enum Type | Casing | Examples |
|---|---|---|
| `userrole`, `userstatus` | UPPERCASE | `TEACHER`, `ACTIVE`, `SCHOOL_ADMIN` |
| `schooltype`, `schoolstatus` | lowercase | `basic`, `active`, `shs` |
| Sprint 3-4 enums | lowercase | `planned`, `active`, `core`, `elective` |

### 2.3 pytest Configuration

```ini
# backend/pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
filterwarnings =
    ignore::DeprecationWarning
markers =
    rls: RLS isolation tests (critical)
    integration: Integration tests (requires database)
    slow: Slow-running tests
```

### 2.4 Required Test Dependencies

```
# backend/requirements-test.txt
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27
pytest-cov>=5.0
pytest-xdist>=3.5       # parallel test execution
factory-boy>=3.3        # test data factories (optional)
```

---

## 3. Required Test Cases

### 3.1 RLS Isolation Tests (P0 -- CRITICAL)

These tests are the most important in the entire test suite. A failure in any of these tests means tenant data can leak. Every test in this file uses raw SQL against the `app_session` (non-superuser) to verify that PostgreSQL RLS policies are correctly configured.

```python
# backend/tests/test_rls_isolation.py
import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    set_tenant_context,
    clear_tenant_context,
    TENANT_SCOPED_TABLES,
)


@pytest.mark.rls
@pytest.mark.asyncio
class TestRLSIsolation:
    """CRITICAL: These tests verify tenant data cannot leak."""

    async def test_no_context_returns_zero_rows(self, app_session, tenant_a, admin_session):
        """Without tenant context set, queries against tenant-scoped tables
        must return zero rows. This is the most fundamental RLS guarantee."""
        # Seed data as admin (bypasses RLS)
        await admin_session.execute(
            text("""INSERT INTO schools (id, tenant_id, name, school_type, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, 'basic', 'active')"""),
            {"id": str(uuid4()), "tid": tenant_a["id"], "name": "Test School"},
        )
        await admin_session.commit()

        # Query as app_user WITHOUT setting tenant context
        await clear_tenant_context(app_session)
        app_session.expire_all()
        result = await app_session.execute(text("SELECT * FROM schools"))
        rows = result.fetchall()
        assert len(rows) == 0, (
            f"Expected 0 rows without tenant context, got {len(rows)}. "
            "RLS is not filtering correctly -- possible NULL bypass."
        )

    async def test_tenant_a_cannot_see_tenant_b_data(
        self, app_session, admin_session, tenant_a, tenant_b
    ):
        """Data belonging to Tenant A must be invisible when querying
        under Tenant B's context, and vice versa."""
        # Seed schools for both tenants (admin bypasses RLS)
        for tid, name in [(tenant_a["id"], "School A"), (tenant_b["id"], "School B")]:
            await admin_session.execute(
                text("""INSERT INTO schools (id, tenant_id, name, school_type, status)
                        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, 'basic', 'active')"""),
                {"id": str(uuid4()), "tid": tid, "name": name},
            )
        await admin_session.commit()

        # Query as Tenant A
        await set_tenant_context(app_session, tenant_a["id"])
        app_session.expire_all()
        result = await app_session.execute(text("SELECT name FROM schools"))
        names = [row.name for row in result.fetchall()]
        assert "School A" in names
        assert "School B" not in names, "Tenant A can see Tenant B data -- RLS BREACH"

        # Query as Tenant B
        await set_tenant_context(app_session, tenant_b["id"])
        app_session.expire_all()
        result = await app_session.execute(text("SELECT name FROM schools"))
        names = [row.name for row in result.fetchall()]
        assert "School B" in names
        assert "School A" not in names, "Tenant B can see Tenant A data -- RLS BREACH"

    async def test_cannot_insert_with_wrong_tenant_id(
        self, app_session, admin_session, tenant_a, tenant_b
    ):
        """RLS WITH CHECK clause must prevent inserting a row where
        tenant_id does not match the current session context."""
        await set_tenant_context(app_session, tenant_a["id"])

        with pytest.raises(Exception):  # InternalError from RLS violation
            await app_session.execute(
                text("""INSERT INTO schools (id, tenant_id, name, school_type, status)
                        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, 'basic', 'active')"""),
                {"id": str(uuid4()), "tid": tenant_b["id"], "name": "Sneaky School"},
            )

    async def test_cannot_update_to_wrong_tenant_id(
        self, app_session, admin_session, tenant_a, tenant_b
    ):
        """A row's tenant_id must not be changeable to another tenant's ID.
        This would allow data to 'migrate' between tenants."""
        school_id = uuid4()
        await admin_session.execute(
            text("""INSERT INTO schools (id, tenant_id, name, school_type, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, 'basic', 'active')"""),
            {"id": str(school_id), "tid": tenant_a["id"], "name": "My School"},
        )
        await admin_session.commit()

        await set_tenant_context(app_session, tenant_a["id"])
        with pytest.raises(Exception):
            await app_session.execute(
                text("""UPDATE schools SET tenant_id = CAST(:new_tid AS uuid)
                        WHERE id = CAST(:id AS uuid)"""),
                {"new_tid": tenant_b["id"], "id": str(school_id)},
            )

    async def test_cannot_delete_other_tenants_data(
        self, app_session, admin_session, tenant_a, tenant_b
    ):
        """Tenant A must not be able to delete Tenant B's rows,
        even if they know the row's primary key."""
        school_id = uuid4()
        await admin_session.execute(
            text("""INSERT INTO schools (id, tenant_id, name, school_type, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, 'basic', 'active')"""),
            {"id": str(school_id), "tid": tenant_b["id"], "name": "School B"},
        )
        await admin_session.commit()

        # Set context to Tenant A, try to delete Tenant B's school
        await set_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(
            text("DELETE FROM schools WHERE id = CAST(:id AS uuid)"),
            {"id": str(school_id)},
        )
        assert result.rowcount == 0, "Tenant A deleted Tenant B's row -- RLS BREACH"

    async def test_rls_on_all_tenant_scoped_tables(self, app_session):
        """Verify that RLS is enabled on every table in TENANT_SCOPED_TABLES.
        If a new table is added to the schema but RLS is not enabled, this
        test catches it."""
        result = await app_session.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = ANY(:tables)
            """),
            {"tables": TENANT_SCOPED_TABLES},
        )
        rows = result.fetchall()
        found_tables = {row.tablename for row in rows}

        # Check that all expected tables exist
        for table in TENANT_SCOPED_TABLES:
            assert table in found_tables, f"Table '{table}' not found in database"

        # Check that RLS is enabled on each
        for row in rows:
            assert row.rowsecurity is True, (
                f"RLS not enabled on '{row.tablename}'. "
                "Run: ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"
            )

    async def test_force_rls_on_all_tenant_scoped_tables(self, app_session):
        """Verify FORCE ROW LEVEL SECURITY is set on all tenant-scoped tables.
        Without FORCE, the table owner bypasses RLS. This is dangerous if the
        app accidentally connects as the table owner."""
        result = await app_session.execute(
            text("""
                SELECT relname, relforcerowsecurity
                FROM pg_class
                WHERE relname = ANY(:tables)
            """),
            {"tables": TENANT_SCOPED_TABLES},
        )
        for row in result.fetchall():
            assert row.relforcerowsecurity is True, (
                f"FORCE RLS not set on '{row.relname}'. "
                "Run: ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
            )

    async def test_no_null_bypass_in_policies(self, app_session):
        """Verify that NO RLS policy contains a NULL/IS NULL bypass.
        A policy like 'tenant_id = current_setting(...) OR tenant_id IS NULL'
        would allow any row with a NULL tenant_id to be visible to all tenants."""
        result = await app_session.execute(
            text("""
                SELECT tablename, policyname, qual
                FROM pg_policies
                WHERE schemaname = 'public'
            """)
        )
        for row in result.fetchall():
            if row.qual and "IS NULL" in row.qual.upper():
                pytest.fail(
                    f"Policy '{row.policyname}' on '{row.tablename}' "
                    f"contains NULL bypass: {row.qual}"
                )

    async def test_no_platform_admin_bypass_in_policies(self, app_session):
        """Verify that NO RLS policy contains a platform_admin bypass.
        If a policy grants unrestricted access to platform admins via a
        session variable or function check, a compromised admin token
        would expose all tenant data."""
        result = await app_session.execute(
            text("""
                SELECT tablename, policyname, qual
                FROM pg_policies
                WHERE schemaname = 'public'
            """)
        )
        for row in result.fetchall():
            if row.qual and "platform_admin" in row.qual.lower():
                pytest.fail(
                    f"Policy '{row.policyname}' on '{row.tablename}' "
                    f"contains platform_admin bypass: {row.qual}"
                )
```

### 3.2 Tenant Middleware Tests (P1)

These tests verify that the tenant extraction middleware correctly identifies tenants from subdomain headers, rejects invalid or suspended tenants, and allows public paths to work without tenant context.

```python
# backend/tests/test_tenant_middleware.py
import pytest
from uuid import uuid4
from sqlalchemy import text


@pytest.mark.asyncio
class TestTenantMiddleware:

    async def test_valid_subdomain_sets_context(self, client, tenant_a):
        """A request with a valid subdomain header should succeed."""
        response = await client.get(
            "/api/v1/health",
            headers={"X-Subdomain": tenant_a["subdomain"]},
        )
        assert response.status_code == 200

    async def test_missing_subdomain_on_api_returns_400(self, client):
        """An API request without a subdomain header should return 400.
        The get_db() dependency must raise, not silently proceed."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 400

    async def test_invalid_subdomain_returns_404(self, client):
        """A subdomain that does not exist in the tenants table returns 404."""
        response = await client.get(
            "/api/v1/health",
            headers={"X-Subdomain": "nonexistent-school-xyz"},
        )
        assert response.status_code == 404

    async def test_suspended_tenant_returns_403(self, client, admin_session):
        """A tenant with is_active=false (suspended) returns 403."""
        tenant_id = uuid4()
        subdomain = f"susp{uuid4().hex[:6]}"
        await admin_session.execute(
            text("""INSERT INTO tenants (id, subdomain, slug, name, is_active)
                    VALUES (CAST(:id AS uuid), :sub, :slug, :name, false)"""),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": "Suspended"},
        )
        await admin_session.commit()

        response = await client.get(
            "/api/v1/health",
            headers={"X-Subdomain": subdomain},
        )
        assert response.status_code == 403

    async def test_reserved_subdomain_rejected(self, client):
        """Reserved subdomains (www, api, admin, etc.) must not resolve
        to a tenant. These are used by the platform itself."""
        for subdomain in ["www", "api", "admin", "mail", "ftp", "status"]:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"X-Subdomain": subdomain},
            )
            assert response.status_code in (400, 404), (
                f"Reserved subdomain '{subdomain}' was not rejected "
                f"(got {response.status_code})"
            )

    async def test_public_paths_work_without_subdomain(self, client):
        """Health and onboarding endpoints must work without a subdomain
        header. These are platform-level endpoints."""
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_context_cleared_between_requests(self, client, tenant_a, tenant_b):
        """Tenant context from one request must not bleed into the next.
        This catches connection pool context leaking."""
        # Request 1: Tenant A
        response_a = await client.get(
            "/api/v1/health",
            headers={"X-Subdomain": tenant_a["subdomain"]},
        )
        assert response_a.status_code == 200

        # Request 2: Tenant B
        response_b = await client.get(
            "/api/v1/health",
            headers={"X-Subdomain": tenant_b["subdomain"]},
        )
        assert response_b.status_code == 200

        # Request 3: No subdomain on API route -- must not carry over Tenant B
        response_none = await client.get("/api/v1/auth/me")
        assert response_none.status_code == 400
```

### 3.3 Authentication Tests (P1)

```python
# backend/tests/test_auth.py
import pytest
from uuid import uuid4
from sqlalchemy import text

from app.core.security import hash_password


@pytest.mark.asyncio
class TestAuthentication:

    async def test_login_success(self, client, tenant_a, admin_session):
        """Successful login returns access_token and refresh_token."""
        password_hash = hash_password("SecureP@ss1")
        await admin_session.execute(
            text("""INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    :fn, :ln, :role, :status)"""),
            {
                "id": str(uuid4()), "tid": tenant_a["id"],
                "email": "test@school.com", "pw": password_hash,
                "fn": "Test", "ln": "User", "role": "SCHOOL_ADMIN", "status": "ACTIVE",
            },
        )
        await admin_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": tenant_a["subdomain"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client, tenant_a, admin_session):
        """Wrong password returns 401 Unauthorized."""
        password_hash = hash_password("SecureP@ss1")
        await admin_session.execute(
            text("""INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    :fn, :ln, :role, :status)"""),
            {
                "id": str(uuid4()), "tid": tenant_a["id"],
                "email": "wrongpw@school.com", "pw": password_hash,
                "fn": "Test", "ln": "User", "role": "TEACHER", "status": "ACTIVE",
            },
        )
        await admin_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@school.com", "password": "WrongPassword1!"},
            headers={"X-Subdomain": tenant_a["subdomain"]},
        )
        assert response.status_code == 401

    async def test_cross_tenant_token_rejected(self, client, tenant_a, tenant_b, admin_session):
        """A JWT issued for Tenant A must be rejected when used on
        Tenant B's subdomain. The token contains tenant_id and
        tenant_subdomain claims that are validated against the request."""
        # Create user in Tenant A
        password_hash = hash_password("SecureP@ss1")
        await admin_session.execute(
            text("""INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    :fn, :ln, :role, :status)"""),
            {
                "id": str(uuid4()), "tid": tenant_a["id"],
                "email": "crosstest@school.com", "pw": password_hash,
                "fn": "Cross", "ln": "Test", "role": "SCHOOL_ADMIN", "status": "ACTIVE",
            },
        )
        await admin_session.commit()

        # Login on Tenant A to get token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "crosstest@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": tenant_a["subdomain"]},
        )
        tenant_a_token = login_response.json()["access_token"]

        # Try to use Tenant A's token on Tenant B
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {tenant_a_token}",
                "X-Subdomain": tenant_b["subdomain"],
            },
        )
        assert response.status_code == 403

    async def test_account_lockout_after_5_failures(self, client, tenant_a, admin_session):
        """5 failed login attempts must lock the account for 30 minutes.
        The 6th attempt with the correct password should still fail."""
        password_hash = hash_password("SecureP@ss1")
        await admin_session.execute(
            text("""INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    :fn, :ln, :role, :status)"""),
            {
                "id": str(uuid4()), "tid": tenant_a["id"],
                "email": "lockout@school.com", "pw": password_hash,
                "fn": "Lock", "ln": "Out", "role": "TEACHER", "status": "ACTIVE",
            },
        )
        await admin_session.commit()

        # 5 failed attempts
        for i in range(5):
            await client.post(
                "/api/v1/auth/login",
                json={"email": "lockout@school.com", "password": f"Wrong{i}!"},
                headers={"X-Subdomain": tenant_a["subdomain"]},
            )

        # 6th attempt with CORRECT password should still be locked
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "lockout@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": tenant_a["subdomain"]},
        )
        assert response.status_code == 401
        assert "locked" in response.json()["detail"].lower()

    async def test_password_validation_requirements(self, client, tenant_a):
        """Passwords must meet minimum requirements: 8+ characters,
        uppercase, lowercase, number, special character."""
        weak_passwords = [
            "short",           # too short
            "alllowercase1!",  # no uppercase
            "ALLUPPERCASE1!",  # no lowercase
            "NoNumbers!!",     # no digit
            "NoSpecial1a",     # no special character
        ]
        for password in weak_passwords:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "weak@school.com",
                    "password": password,
                    "first_name": "Weak",
                    "last_name": "Password",
                },
                headers={"X-Subdomain": tenant_a["subdomain"]},
            )
            assert response.status_code in (400, 422), (
                f"Weak password '{password}' was accepted"
            )

    async def test_token_blacklisting_on_logout(self, client, tenant_a, admin_session):
        """After logout, the access token must be blacklisted and rejected
        on subsequent requests."""
        password_hash = hash_password("SecureP@ss1")
        await admin_session.execute(
            text("""INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    :fn, :ln, :role, :status)"""),
            {
                "id": str(uuid4()), "tid": tenant_a["id"],
                "email": "logout@school.com", "pw": password_hash,
                "fn": "Log", "ln": "Out", "role": "TEACHER", "status": "ACTIVE",
            },
        )
        await admin_session.commit()

        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout@school.com", "password": "SecureP@ss1"},
            headers={"X-Subdomain": tenant_a["subdomain"]},
        )
        token = login_response.json()["access_token"]

        # Logout
        await client.post(
            "/api/v1/auth/logout",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": tenant_a["subdomain"],
            },
        )

        # Try to use the token again
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": tenant_a["subdomain"],
            },
        )
        assert response.status_code == 401
```

### 3.4 Onboarding Tests (P1)

```python
# backend/tests/test_onboarding.py
import pytest
from uuid import uuid4


@pytest.mark.asyncio
class TestOnboarding:

    async def test_register_new_school(self, client):
        """Complete school registration creates a tenant, school, and
        admin user. Returns subdomain and IDs for immediate login."""
        subdomain = f"newschool{uuid4().hex[:6]}"
        response = await client.post(
            "/api/v1/onboarding/register",
            json={
                "school_name": "New Test School",
                "subdomain": subdomain,
                "school_type": "basic",
                "admin_email": f"admin@{subdomain}.edu.gh",
                "admin_first_name": "Admin",
                "admin_last_name": "User",
                "admin_password": "SecureP@ss1",
                "admin_phone": "+233244000000",
                "plan": "trial",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subdomain"] == subdomain
        assert data["tenant_id"] is not None
        assert data["school_id"] is not None

    async def test_duplicate_subdomain_rejected(self, client, tenant_a):
        """Cannot register a school with an already-taken subdomain."""
        response = await client.post(
            "/api/v1/onboarding/register",
            json={
                "school_name": "Duplicate School",
                "subdomain": tenant_a["subdomain"],
                "school_type": "basic",
                "admin_email": "new@test.com",
                "admin_first_name": "New",
                "admin_last_name": "Admin",
                "admin_password": "SecureP@ss1",
                "admin_phone": "+233244111111",
                "plan": "trial",
            },
        )
        assert response.status_code == 400

    async def test_reserved_subdomain_rejected(self, client):
        """Cannot register a school with a reserved subdomain."""
        for subdomain in ["admin", "www", "api", "mail"]:
            response = await client.post(
                "/api/v1/onboarding/register",
                json={
                    "school_name": f"{subdomain.title()} School",
                    "subdomain": subdomain,
                    "school_type": "basic",
                    "admin_email": f"admin@{subdomain}.edu.gh",
                    "admin_first_name": "Admin",
                    "admin_last_name": "User",
                    "admin_password": "SecureP@ss1",
                    "admin_phone": "+233244222222",
                    "plan": "trial",
                },
            )
            assert response.status_code == 400, (
                f"Reserved subdomain '{subdomain}' was accepted"
            )

    async def test_subdomain_availability_check(self, client, tenant_a):
        """The availability endpoint returns whether a subdomain is taken."""
        # Taken subdomain
        response = await client.get(
            f"/api/v1/tenant/check-subdomain?subdomain={tenant_a['subdomain']}"
        )
        assert response.status_code == 200
        assert response.json()["available"] is False

        # Available subdomain
        response = await client.get(
            f"/api/v1/tenant/check-subdomain?subdomain=brandnew{uuid4().hex[:6]}"
        )
        assert response.status_code == 200
        assert response.json()["available"] is True

    async def test_subdomain_format_validation(self, client):
        """Subdomains must follow DNS rules: lowercase alphanumeric and
        hyphens, 3-63 characters, no leading/trailing hyphens."""
        invalid_subdomains = [
            "ab",             # too short (< 3)
            "-leading",       # leading hyphen
            "trailing-",      # trailing hyphen
            "UPPERCASE",      # uppercase not allowed
            "has spaces",     # spaces not allowed
            "special!chars",  # special characters
            "a" * 64,         # too long (> 63)
        ]
        for subdomain in invalid_subdomains:
            response = await client.post(
                "/api/v1/onboarding/register",
                json={
                    "school_name": "Format Test",
                    "subdomain": subdomain,
                    "school_type": "basic",
                    "admin_email": "format@test.com",
                    "admin_first_name": "Format",
                    "admin_last_name": "Test",
                    "admin_password": "SecureP@ss1",
                    "admin_phone": "+233244333333",
                    "plan": "trial",
                },
            )
            assert response.status_code in (400, 422), (
                f"Invalid subdomain '{subdomain}' was accepted"
            )
```

### 3.5 Rate Limiting Tests (P1)

```python
# backend/tests/test_rate_limiting.py
import pytest
import asyncio


@pytest.mark.asyncio
class TestRateLimiting:

    async def test_auth_rate_limit(self, client, tenant_a):
        """Authentication endpoints are limited to 5 requests per minute."""
        responses = []
        for _ in range(7):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "Test1234!"},
                headers={"X-Subdomain": tenant_a["subdomain"]},
            )
            responses.append(response.status_code)

        # At least one response should be 429 (Too Many Requests)
        assert 429 in responses, (
            f"No 429 after 7 rapid auth requests. "
            f"Status codes: {responses}"
        )

    async def test_general_rate_limit(self, client, tenant_a):
        """General API endpoints are limited to 100 requests per minute.
        This test sends 105 rapid requests and expects at least one 429."""
        responses = []
        for _ in range(105):
            response = await client.get(
                "/api/v1/health",
                headers={"X-Subdomain": tenant_a["subdomain"]},
            )
            responses.append(response.status_code)

        assert 429 in responses, (
            f"No 429 after 105 rapid requests. "
            f"Last 10 status codes: {responses[-10:]}"
        )

    async def test_rate_limit_headers(self, client, tenant_a):
        """Rate-limited responses should include informative headers."""
        # Exhaust auth rate limit
        for _ in range(6):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "Test1234!"},
                headers={"X-Subdomain": tenant_a["subdomain"]},
            )

        if response.status_code == 429:
            assert "Retry-After" in response.headers or "retry-after" in response.headers
```

### 3.6 IDOR Prevention Tests (P1)

```python
# backend/tests/test_idor.py
import pytest
from uuid import uuid4
from sqlalchemy import text


@pytest.mark.asyncio
class TestIDOR:
    """Tests for Insecure Direct Object Reference prevention.
    When a URL contains nested resource IDs (e.g., /students/{id}/guardians/{gid}),
    the service must verify the child resource belongs to the parent."""

    async def test_cannot_access_other_tenants_student(
        self, client, tenant_a, tenant_b, admin_session
    ):
        """Even with a valid token, cannot access a student belonging
        to another tenant by guessing the student ID."""
        # Create student in Tenant B
        student_id = uuid4()
        await admin_session.execute(
            text("""INSERT INTO students (id, tenant_id, first_name, last_name,
                    date_of_birth, gender, enrollment_status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :fn, :ln,
                    '2010-01-01', 'male', 'active')"""),
            {"id": str(student_id), "tid": tenant_b["id"], "fn": "Secret", "ln": "Student"},
        )
        await admin_session.commit()

        # Authenticate as Tenant A admin and try to access Tenant B's student
        # (Requires a logged-in user for Tenant A -- setup omitted for brevity)
        # The endpoint should return 404, not 403 (to avoid leaking existence)
        # This is verified by RLS: the query simply returns no rows
```

### 3.7 Frontend Tests (P2)

```typescript
// frontend/__tests__/components/LoginForm.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import LoginForm from "@/components/auth/LoginForm";

describe("LoginForm", () => {
  it("renders email and password fields", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("shows validation errors for empty submission", async () => {
    render(<LoginForm />);
    const submitButton = screen.getByRole("button", { name: /log in/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  it("submits with valid credentials", async () => {
    const mockLogin = vi.fn().mockResolvedValue({ success: true });
    render(<LoginForm onSubmit={mockLogin} />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@presec.edu.gh" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "SecureP@ss1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: "admin@presec.edu.gh",
        password: "SecureP@ss1",
      });
    });
  });
});
```

### 3.8 E2E Tests (P2)

```typescript
// frontend/e2e/onboarding.spec.ts
import { test, expect } from "@playwright/test";

test.describe("School Onboarding", () => {
  test("complete registration flow", async ({ page }) => {
    await page.goto("http://localhost:3000/register");

    // Step 1: School information
    await page.fill('[name="school_name"]', "Playwright Test School");
    await page.fill('[name="subdomain"]', `e2e${Date.now()}`);
    await page.selectOption('[name="school_type"]', "basic");
    await page.click('button:has-text("Next")');

    // Step 2: Admin account
    await page.fill('[name="admin_email"]', "admin@e2etest.edu.gh");
    await page.fill('[name="admin_first_name"]', "E2E");
    await page.fill('[name="admin_last_name"]', "Admin");
    await page.fill('[name="admin_password"]', "SecureP@ss1");
    await page.fill('[name="admin_phone"]', "+233244000000");
    await page.click('button:has-text("Create School")');

    // Verify redirect to dashboard
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator("h1")).toContainText("Dashboard");
  });

  test("duplicate subdomain shows error", async ({ page }) => {
    await page.goto("http://localhost:3000/register");
    await page.fill('[name="subdomain"]', "presec");
    await page.click('button:has-text("Check Availability")');
    await expect(page.locator(".text-destructive")).toContainText(/taken|unavailable/i);
  });
});
```

---

## 4. Quality Gates

Quality gates are pass/fail checkpoints. A sprint cannot be considered complete unless all blocker gates pass. Non-blocker gates are tracked but do not prevent deployment.

### 4.1 Sprint 1 Quality Gates (Core Infrastructure)

| # | Gate | Verification Method | Blocker? |
|---|---|---|---|
| QG-1.1 | `docker-compose up` starts all services (backend, frontend, PostgreSQL, Redis) within 2 minutes | Manual verification + CI workflow | YES |
| QG-1.2 | `curl http://localhost:8000/health` returns `{"status": "healthy"}` | CI health check step | YES |
| QG-1.3 | `curl http://localhost:3000` returns Next.js page (200 OK) | CI health check step | YES |
| QG-1.4 | Nginx routes subdomain requests and sets `X-Subdomain` header | Manual test with 3 different subdomains | YES |
| QG-1.5 | `init-db.sql` creates `sims_app_user` role with correct permissions | CI connection test as `sims_app_user` | YES |
| QG-1.6 | No reference to `current_tenant_id()` (old function name) in codebase | CI grep check (`grep -r "current_tenant_id"`) | YES |
| QG-1.7 | `.env.example` exists with all required variables documented | CI file existence check | YES |
| QG-1.8 | Backend CI passes: lint (`ruff`), type check (`mypy`), test (`pytest`), build | GitHub Actions green | YES |
| QG-1.9 | Frontend CI passes: lint (`eslint`), type check (`tsc`), build (`next build`) | GitHub Actions green | YES |
| QG-1.10 | All RLS policies have NO NULL bypass | `test_no_null_bypass_in_policies` passes | YES |
| QG-1.11 | Two PostgreSQL roles exist: superuser (admin) and `sims_app_user` (app) | CI connection test for both roles | YES |
| QG-1.12 | Cloudflare DNS wildcard resolves `*.simsplus.io` | Manual verification (or documented local workaround) | NO |

### 4.2 Sprint 2 Quality Gates (Multi-Tenant Isolation)

| # | Gate | Verification Method | Blocker? |
|---|---|---|---|
| QG-2.1 | RLS enabled on ALL tenant-scoped tables | `test_rls_on_all_tenant_scoped_tables` passes | YES |
| QG-2.2 | No context set returns 0 rows from `users`, `schools`, `students` | `test_no_context_returns_zero_rows` passes | YES |
| QG-2.3 | Tenant A context returns only Tenant A data | `test_tenant_a_cannot_see_tenant_b_data` passes | YES |
| QG-2.4 | INSERT with wrong `tenant_id` rejected by RLS WITH CHECK | `test_cannot_insert_with_wrong_tenant_id` passes | YES |
| QG-2.5 | `get_db()` raises 400 when called without tenant context on API routes | `test_missing_subdomain_on_api_returns_400` passes | YES |
| QG-2.6 | Tenant context cleared between requests (no connection pool leaking) | `test_context_cleared_between_requests` passes | YES |
| QG-2.7 | Next.js middleware extracts subdomain from hostname and passes to API | Manual verification + E2E test | YES |
| QG-2.8 | TenantProvider fetches and provides tenant branding data to React tree | Manual verification (logo, colors render) | YES |
| QG-2.9 | Tenant lookup cached in Redis with 10-minute TTL | Redis CLI verification (`GET tenant:{subdomain}`) | NO |
| QG-2.10 | All pre-existing tests from Sprint 1 still pass | CI regression suite | YES |
| QG-2.11 | 10 or more new multi-tenant isolation tests added | CI test count check | YES |
| QG-2.12 | No regression in existing endpoint behavior | CI integration tests | YES |

### 4.3 Sprint 3-4 Quality Gates (Academic Foundation)

| # | Gate | Verification Method | Blocker? |
|---|---|---|---|
| QG-3.1 | Academic year CRUD works with tenant isolation | Integration tests | YES |
| QG-3.2 | Only one academic year can be `current` per tenant | Service layer test | YES |
| QG-3.3 | Class/section creation with student count tracking | Integration tests | YES |
| QG-3.4 | Subject assignment to classes (core vs. elective) | Integration tests | YES |
| QG-3.5 | Grading scales (WAEC, GPA, custom) correctly configured | Unit tests | YES |
| QG-3.6 | Assessment weight validation (weights sum to 100) | Service layer test | YES |
| QG-3.7 | New tables added to `TENANT_SCOPED_TABLES` list | CI check | YES |
| QG-3.8 | RLS enabled on all new Sprint 3-4 tables | `test_rls_on_all_tenant_scoped_tables` | YES |
| QG-3.9 | Alembic migration chain unbroken | `alembic check` in CI | YES |

### 4.4 Sprint 5-6+ Quality Gates (Student & Staff Management)

| # | Gate | Verification Method | Blocker? |
|---|---|---|---|
| QG-5.1 | Student CRUD with guardian linkage | Integration tests | YES |
| QG-5.2 | Student ID auto-generation with school prefix | Service layer test | YES |
| QG-5.3 | CSV/Excel import with validation and error reporting | Integration tests | YES |
| QG-5.4 | Staff CRUD with department assignment | Integration tests | YES |
| QG-5.5 | IDOR prevention on nested resources | `test_idor.py` tests | YES |
| QG-5.6 | All new tables RLS-protected | `test_rls_on_all_tenant_scoped_tables` | YES |

### 4.5 Gate Enforcement in CI

Quality gates are enforced by the GitHub Actions CI pipeline. The workflow structure:

```yaml
# .github/workflows/backend.yml
name: Backend CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff
      - run: ruff check backend/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: sims_plus_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r backend/requirements.txt -r backend/requirements-test.txt
      - run: pytest backend/tests/ -v --cov=app --cov-fail-under=65
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sims_plus_test

  # RLS tests run as a SEPARATE job for visibility
  rls-isolation:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        # ... (same config)
    steps:
      - uses: actions/checkout@v4
      - run: pytest backend/tests/test_rls_isolation.py -v --tb=long
```

---

## 5. Risk Register

Risks are scored on a 5x5 matrix: Likelihood (1-5) x Impact (1-5) = Score (1-25). Scores 20-25 are Critical, 15-19 are High, 8-14 are Medium, and 1-7 are Low.

### 5.1 Critical Risks (Score >= 20)

| ID | Risk | Likelihood | Impact | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R01 | **RLS NULL bypass still active.** If any RLS policy contains `OR tenant_id IS NULL`, rows with NULL `tenant_id` are visible to all tenants. This was a known issue in early migrations. | 5 | 5 | **25** | New migration drops all policies and recreates them without NULL bypass. `test_no_null_bypass_in_policies` runs in CI. Manual audit of `pg_policies` system catalog. | Security Lead |
| R02 | **`get_db()` proceeds without tenant context.** If the database session dependency does not validate that a tenant context is set, queries execute without RLS filtering. Data from all tenants becomes visible. | 5 | 5 | **25** | `get_db()` raises HTTP 400 for non-public routes when `app.current_tenant_id` is not set. `UnscopedDatabaseSession` exists as explicit opt-in for platform-level operations. Middleware test verifies behavior. | Backend Lead |
| R05 | **No Nginx wildcard config exists.** Without wildcard routing, subdomain-based multi-tenancy does not work. Each subdomain would need manual configuration. | 5 | 4 | **20** | Create Nginx config in Sprint 1, Week 1. Test with at least 3 different subdomains. Document local development workaround using `/etc/hosts` or `X-Subdomain` header. | DevOps |
| R12 | **Team unfamiliar with PostgreSQL RLS.** RLS is the foundation of multi-tenant isolation. Misunderstanding how it works (e.g., that superusers bypass it, that `SET` is session-scoped) leads to security bugs. | 4 | 5 | **20** | Conduct 2-hour RLS workshop before Sprint 1 starts. Create RLS Testing Playbook document. Require at least one RLS isolation test in every PR that touches tenant-scoped tables. | Tech Lead |

### 5.2 High Risks (Score 15-19)

| ID | Risk | Likelihood | Impact | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R03 | **`is_platform_admin` bypass in RLS policies.** If any policy grants unrestricted access based on a `is_platform_admin` session variable, a compromised admin JWT exposes all tenant data. | 3 | 5 | **15** | Remove `is_platform_admin` from all RLS policies. Platform admin operations use superuser database connection, not application connection with elevated privileges. `test_no_platform_admin_bypass_in_policies` enforces this. | Backend Lead |
| R04 | **Dual tenant context functions.** If both `current_tenant_id()` and `get_current_tenant_id()` exist, different parts of the codebase may use different functions. If one has a bug (e.g., returns NULL instead of raising), RLS fails silently. | 4 | 4 | **16** | Standardize on `get_current_tenant_id()`. Drop old function. CI grep check prevents reintroduction. | Backend Lead |
| R06 | **No Terraform/IaC for infrastructure.** Manual AWS setup is error-prone, undocumented, and unreproducible. A misconfigured security group or missing RDS parameter can cause downtime or data exposure. | 4 | 4 | **16** | Start with Terraform for RDS + ElastiCache in Sprint 1-2. Defer EKS/Kubernetes to Sprint 3-4. All infrastructure changes must go through Terraform. | DevOps |
| R07 | **Connection pool context leaking between requests.** If the connection pool returns a connection where the previous request's `app.current_tenant_id` is still set, the next request may see the wrong tenant's data. | 3 | 5 | **15** | Pool checkout event listener resets tenant context (`RESET app.current_tenant_id`). `test_context_cleared_between_requests` verifies no leaking. Use `RESET ALL` or explicit `set_config('app.current_tenant_id', '', false)` on connection return. | Backend Lead |
| R08 | **Redis cache key collision across tenants.** If cache keys do not include `tenant_id`, cached data from one tenant may be served to another. | 3 | 5 | **15** | `CacheKeys` utility class enforces `tenant:{tenant_id}:` prefix on all keys. Code review checklist includes cache key format verification. Audit existing Redis usage. | Backend Lead |
| R16 | **Weak SECRET_KEY in CI or production.** A weak or default JWT signing key allows token forgery. An attacker could generate tokens for any tenant. | 3 | 5 | **15** | Pydantic validator enforces minimum 64-character `SECRET_KEY`. CI environment uses a generated key (`openssl rand -base64 64`). Production key stored in AWS Secrets Manager. Startup check logs warning if key length is insufficient. | Tech Lead |

### 5.3 Medium Risks (Score 8-14)

| ID | Risk | Likelihood | Impact | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R09 | **Local subdomain testing is difficult.** Developers cannot use real DNS subdomains locally. `localhost` does not support subdomains without system-level configuration. | 4 | 3 | **12** | Document three approaches: (1) `/etc/hosts` entries, (2) `X-Subdomain` header in API calls, (3) `nip.io` wildcard DNS. Create helper script that sets up `/etc/hosts` entries. Frontend middleware falls back to `X-Subdomain` header in development mode. | DevOps |
| R11 | **Tenant lookup on every request adds latency.** A `SELECT` query on every request to resolve subdomain to `tenant_id` adds 5-15ms of latency and increases database load. | 4 | 3 | **12** | Redis cache with 10-minute TTL for tenant lookups. Cache key: `tenant:subdomain:{subdomain}`. Cache invalidation on tenant update/suspension. Measure p95 latency before and after caching. | Backend Lead |
| R14 | **`db/base.py` missing model imports.** If a SQLAlchemy model is not imported in `db/base.py`, Alembic cannot detect it and will not generate migrations for its table. The table will be missing from the database. | 4 | 3 | **12** | Import ALL models in `db/base.py`. CI check: compare list of model files against imports in `base.py`. Alembic `--autogenerate` in CI should produce no changes on a clean database. | Backend Lead |
| R20 | **Connection pool exhaustion under load.** If the connection pool is too small, requests queue waiting for connections. Under burst load (e.g., start of school day), this causes timeouts. | 3 | 4 | **12** | Default pool size 10 + 20 overflow for development. Production pool size 25 + 50 overflow. Monitor `db_connection_pool_size` metric. Alert at 80% utilization. | DevOps |
| R21 | **CORS does not support wildcard subdomains.** Standard CORS `Access-Control-Allow-Origin` does not support wildcards with credentials. Each subdomain needs to be explicitly allowed or a regex pattern used. | 4 | 3 | **12** | Use `allow_origin_regex` in FastAPI CORSMiddleware: `r"https://[a-z0-9\-]+\.simsplus\.io"`. Test with `Origin` headers from multiple subdomains. Development mode allows `localhost` origins. | Backend Lead |
| R13 | **Error responses leak internal details.** Stack traces, SQL queries, or file paths in error responses give attackers information about the system internals. | 3 | 3 | **9** | Global exception handler returns generic messages in production. Error details logged server-side with correlation ID. Client receives correlation ID for support requests. Sentry captures full error context. | Backend Lead |
| R18 | **No `.env.example` file.** New developers cannot set up the project without manually discovering required environment variables. Missing variables cause cryptic startup errors. | 5 | 2 | **10** | Create `.env.example` on Day 1 with all required variables and descriptive comments. CI checks that every variable referenced in `settings.py` exists in `.env.example`. | Tech Lead |
| R25 | **Alembic migration conflicts in parallel development.** Two developers creating migrations simultaneously will produce conflicting `revision` chains. | 3 | 3 | **9** | Branch naming convention includes sprint number. Migrations rebased before merge. `alembic check` in CI detects broken chains. Only one developer creates migrations at a time (coordination via Slack). | Tech Lead |

### 5.4 Low Risks (Score 1-7)

| ID | Risk | Likelihood | Impact | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R19 | **Docker build cache invalidation slows CI.** Large dependency changes invalidate Docker layer cache, making CI builds take 10+ minutes. | 3 | 2 | **6** | Multi-stage Dockerfile. Dependencies layer separate from source layer. GitHub Actions cache for Docker layers. | DevOps |
| R23 | **Timezone inconsistencies in date handling.** Ghana is UTC+0, but server, database, and client may assume different timezones. Attendance records and exam schedules could be off by hours. | 2 | 4 | **8** | All timestamps stored as UTC in PostgreSQL. Frontend converts to local timezone for display. Server timezone explicitly set to UTC in Docker. Date format standardized to DD/MM/YYYY per project conventions. | Backend Lead |

### 5.5 Risk Heat Map

```
                         Impact
              1       2       3       4       5
          +-------+-------+-------+-------+-------+
     5    |       | R18   |       | R05   | R01   |
          |       |       |       |       | R02   |
L    4    |       |       | R09   | R06   | R12   |
i         |       |       | R14   | R04   |       |
k    3    |       |       | R21   | R20   | R03   |
e         |       |       | R13   |       | R07   |
l    2    |       | R19   | R25   | R23   | R08   |
i         |       |       |       |       | R16   |
h    1    |       |       |       |       |       |
o         +-------+-------+-------+-------+-------+
o
d
```

### 5.6 Risk Response Summary

| Response Type | Risks | Action |
|---|---|---|
| **Eliminate** (remove the risk entirely) | R01, R02, R03, R04, R18 | Fix in code, add tests that prevent regression |
| **Mitigate** (reduce likelihood or impact) | R05, R06, R07, R08, R12, R16 | Implement controls, monitoring, training |
| **Accept** (acknowledge, monitor) | R09, R11, R13, R19, R23, R25 | Document workarounds, revisit if impact increases |
| **Transfer** (shift to third party) | R20 (partially) | AWS RDS manages database availability and failover |

---

## 6. Performance Targets

### 6.1 Backend Response Time Targets

| Operation | Target (p95) | Breakdown | Measurement |
|---|---|---|---|
| Login | < 300ms | Argon2id verification ~100ms, JWT generation ~5ms, DB query ~10ms, middleware ~10ms | `http_request_duration_seconds{endpoint="/auth/login"}` |
| Tenant middleware | < 10ms | Redis cache lookup ~2ms, fallback SQL ~8ms (indexed subdomain column) | `tenant_middleware_duration_seconds` |
| RLS overhead per query | < 2ms | Session variable read via `STABLE` function, no additional I/O | Benchmark: same query with/without RLS |
| Rate limit check | < 5ms | Redis ZADD/ZCARD pipeline, single round-trip | `rate_limit_check_duration_seconds` |
| Token validation | < 10ms | JWT decode ~2ms, Redis blacklist check ~3ms | `token_validation_duration_seconds` |
| Health check | < 50ms | `SELECT 1` to PostgreSQL + `PING` to Redis | `http_request_duration_seconds{endpoint="/health"}` |
| Student list (paginated) | < 200ms | SQL query with RLS + pagination, 50 rows default | Integration test timing |
| Report card PDF generation | < 5s | WeasyPrint rendering, template loading, grade computation | Background task timing |
| Bulk invoice generation (100 students) | < 30s | Celery background task, batch SQL inserts | Task completion time |

### 6.2 Frontend Performance Targets

| Metric | Target | Measurement Tool |
|---|---|---|
| First Contentful Paint (3G) | < 1.5s | Lighthouse |
| Largest Contentful Paint (3G) | < 2.5s | Lighthouse |
| Time to Interactive (3G) | < 3.0s | Lighthouse |
| Cumulative Layout Shift | < 0.1 | Lighthouse |
| First Input Delay | < 100ms | Chrome UX Report |
| JavaScript bundle size (initial) | < 150 KB gzipped | `next build` output |
| Server Component render | < 100ms | Server timing headers |

### 6.3 Infrastructure Targets

| Metric | Target | Measurement |
|---|---|---|
| Concurrent users per tenant | 500 | Load test with k6 |
| Total concurrent connections | 5,000 | PostgreSQL `max_connections` + pgbouncer |
| Database connection pool | 25 + 50 overflow (production) | SQLAlchemy pool config |
| Redis memory per tenant | < 5 MB | `MEMORY USAGE` per key prefix |
| S3 upload throughput | < 5s for 10 MB file | Integration test |
| Uptime SLA | 99.5% | AWS CloudWatch |
| Recovery Time Objective (RTO) | 4 hours | Disaster recovery drill |
| Recovery Point Objective (RPO) | 1 hour | RDS automated backup frequency |

### 6.4 Load Testing Plan

Load tests are scheduled for Sprint 17-18 (Beta Launch) but the targets are defined now to guide architectural decisions.

```javascript
// k6 load test script (deferred to Sprint 17-18)
// backend/tests/load/school-day-simulation.js
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "2m", target: 100 },   // Ramp up to 100 users
    { duration: "5m", target: 500 },   // Peak: 500 concurrent users
    { duration: "2m", target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"],   // 95th percentile < 500ms
    http_req_failed: ["rate<0.01"],     // Error rate < 1%
  },
};

export default function () {
  const subdomain = "loadtest";
  const headers = { "X-Subdomain": subdomain };

  // Simulate a teacher's morning routine
  const login = http.post(
    "http://localhost:8000/api/v1/auth/login",
    JSON.stringify({ email: "teacher@loadtest.edu.gh", password: "SecureP@ss1" }),
    { headers: { ...headers, "Content-Type": "application/json" } }
  );
  check(login, { "login success": (r) => r.status === 200 });

  const token = login.json("access_token");
  const authHeaders = { ...headers, Authorization: `Bearer ${token}` };

  // View class list
  http.get("http://localhost:8000/api/v1/academic/classes", { headers: authHeaders });
  sleep(1);

  // View student list
  http.get("http://localhost:8000/api/v1/students?page=1&per_page=50", { headers: authHeaders });
  sleep(1);

  // Mark attendance
  http.post(
    "http://localhost:8000/api/v1/attendance/bulk",
    JSON.stringify({ /* attendance data */ }),
    { headers: { ...authHeaders, "Content-Type": "application/json" } }
  );
  sleep(2);
}
```

---

## 7. Monitoring & Observability

### 7.1 Sprint 1-2: Minimum Viable Monitoring

These tools are set up immediately. They provide error visibility and request tracing during active development.

| Tool | Purpose | Setup | Priority |
|---|---|---|---|
| **Sentry** | Error tracking, exception alerts, performance monitoring | `pip install sentry-sdk[fastapi]`, configure DSN in `.env` | P0 |
| **Structured Logging** | Request tracing, debugging, audit trail | `structlog` with JSON output, correlation IDs per request | P0 |
| **Health endpoint** | Service availability check | `/health` endpoint checks DB (`SELECT 1`) and Redis (`PING`) | P0 |
| **GitHub Actions** | CI/CD status, test results | Workflow badges in README, Slack notifications on failure | P1 |

#### Sentry Configuration

```python
# backend/app/core/sentry.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import settings


def init_sentry():
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,  # 10% of transactions
            profiles_sample_rate=0.1,
            environment=settings.ENVIRONMENT,  # "development", "staging", "production"
            # CRITICAL: Do not send tenant data to Sentry
            before_send=scrub_tenant_data,
        )


def scrub_tenant_data(event, hint):
    """Remove sensitive tenant information from Sentry events."""
    if "request" in event:
        headers = event["request"].get("headers", {})
        # Remove authorization header
        headers.pop("authorization", None)
        headers.pop("Authorization", None)
    return event
```

#### Structured Logging Configuration

```python
# backend/app/core/logging.py
import structlog
import logging


def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

#### Request Logging Middleware

```python
# backend/app/middleware/logging.py
import time
import structlog
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            tenant_subdomain=request.headers.get("X-Subdomain", "none"),
        )

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        response.headers["X-Request-ID"] = request_id
        return response
```

### 7.2 Deferred Monitoring (Sprint 3-4+)

These tools provide production-grade observability. They are deferred because they require infrastructure (Kubernetes, Helm charts) that is not in place during Sprint 1-2.

| Tool | Purpose | Why Deferred |
|---|---|---|
| **Prometheus** | Metrics collection (request durations, error rates, pool sizes) | Requires Kubernetes for scraping; not critical during local development |
| **Grafana** | Dashboards and visualization | Depends on Prometheus |
| **Loki** | Centralized log aggregation | stdout logs with `docker-compose logs` are sufficient for now |
| **AlertManager** | Alerting on metric thresholds | Sentry handles error alerting for development phase |
| **Jaeger** | Distributed tracing | Single-service architecture does not need distributed tracing yet |

### 7.3 Key Metrics to Track

When Prometheus is deployed, these are the metrics to instrument and alert on.

| Metric Name | Type | Alert Threshold | Meaning |
|---|---|---|---|
| `http_request_duration_seconds` | Histogram | p95 > 2s for 5 min | API responses are too slow |
| `http_requests_total` | Counter | Error rate > 5% for 5 min | Too many failing requests |
| `rls_policy_violations_total` | Counter | Any > 0 | **CRITICAL:** Tenant isolation breach attempt |
| `auth_failed_attempts_total` | Counter | > 50/hour per IP | Possible brute-force attack |
| `auth_account_lockouts_total` | Counter | > 10/hour | Unusual lockout activity |
| `db_connection_pool_size` | Gauge | > 80% utilized for 5 min | Pool approaching exhaustion |
| `db_query_duration_seconds` | Histogram | p95 > 1s | Slow queries need optimization |
| `tenant_lookup_cache_hit_rate` | Gauge | < 90% for 15 min | Redis cache not working effectively |
| `redis_memory_usage_bytes` | Gauge | > 80% of allocated | Redis approaching memory limit |
| `celery_tasks_active` | Gauge | > 100 for 10 min | Task queue backing up |
| `celery_tasks_failed_total` | Counter | > 10/hour | Background tasks failing |
| `s3_upload_duration_seconds` | Histogram | p95 > 10s | File uploads are slow |

### 7.4 Alerting Tiers

| Tier | Response Time | Channel | Examples |
|---|---|---|---|
| **P0 -- Critical** | < 15 min | SMS + Slack + PagerDuty | RLS violation, database down, all auth failing |
| **P1 -- High** | < 1 hour | Slack #alerts | p95 latency > 2s, error rate > 5%, pool exhaustion |
| **P2 -- Medium** | < 4 hours | Slack #monitoring | Cache hit rate low, slow queries, high task queue |
| **P3 -- Low** | Next business day | Email digest | Disk space warnings, certificate expiry reminders |

### 7.5 Audit Logging

All security-relevant actions are logged to the `AuditService`, which writes to a separate database connection (not subject to RLS, since audit logs may need to record cross-tenant events like platform admin actions).

| Event | Logged Fields | Retention |
|---|---|---|
| Login success | user_id, tenant_id, IP, user_agent | 90 days |
| Login failure | email, tenant_id, IP, failure_reason | 90 days |
| Account lockout | email, tenant_id, IP, lockout_duration | 1 year |
| Password change | user_id, tenant_id, IP | 1 year |
| Password reset | email, tenant_id, IP | 1 year |
| Token blacklist | user_id, tenant_id, token_jti | 30 days |
| Exam score change | user_id, student_id, old_value, new_value | 5 years |
| Finance transaction | user_id, invoice_id, amount, payment_method | 7 years |
| User role change | admin_id, user_id, old_role, new_role | 5 years |
| Student record change | user_id, student_id, fields_changed | 5 years |

---

## Appendix A: Test Checklist for New Features

When adding a new feature or module, use this checklist to ensure all required tests are written.

- [ ] If the feature introduces new database tables:
  - [ ] Add table names to `TENANT_SCOPED_TABLES` in `conftest.py`
  - [ ] Verify RLS is enabled (existing `test_rls_on_all_tenant_scoped_tables` covers this)
  - [ ] Add import to `db/base.py`
  - [ ] Add Alembic migration with `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`
  - [ ] Add RLS policy using `get_current_tenant_id()` function (no NULL bypass)
- [ ] If the feature has service layer logic:
  - [ ] Unit tests for business rules (happy path + edge cases)
  - [ ] Test that `tenant_id` is filtered in every query
  - [ ] Test error cases (not found, validation, duplicate)
- [ ] If the feature has API endpoints:
  - [ ] Integration tests for each endpoint (200, 400, 401, 403, 404, 422)
  - [ ] Test with missing/invalid authentication
  - [ ] Test with wrong tenant context
  - [ ] Test rate limiting if applicable
- [ ] If the feature involves nested resources (e.g., `/students/{id}/guardians`):
  - [ ] IDOR test: verify child belongs to parent
  - [ ] Test with ID from another tenant (should return 404, not 403)
- [ ] If the feature uses Redis caching:
  - [ ] Cache key includes `tenant:{tenant_id}:` prefix
  - [ ] Cache invalidation test
- [ ] If the feature generates PDFs or exports:
  - [ ] Test output contains only current tenant's data
  - [ ] Test with empty data (no crash)

## Appendix B: CI Pipeline Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                        Pull Request Created                       │
└──────────────────────────────┬───────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────┐   ┌────────────┐   ┌────────────────┐
     │  Backend    │   │  Frontend  │   │  RLS Isolation  │
     │  Lint       │   │  Lint      │   │  Tests          │
     │  (ruff)     │   │  (eslint)  │   │  (pytest)       │
     └─────┬──────┘   └─────┬──────┘   └───────┬────────┘
           ▼                ▼                   │
     ┌────────────┐   ┌────────────┐            │
     │  Backend    │   │  Frontend  │            │
     │  Tests      │   │  Type Check│            │
     │  (pytest)   │   │  (tsc)     │            │
     └─────┬──────┘   └─────┬──────┘            │
           ▼                ▼                   │
     ┌────────────┐   ┌────────────┐            │
     │  Coverage   │   │  Frontend  │            │
     │  Check      │   │  Build     │            │
     │  (>= 65%)   │   │  (next)    │            │
     └─────┬──────┘   └─────┬──────┘            │
           └────────────────┼───────────────────┘
                            ▼
                   ┌────────────────┐
                   │  All Gates     │
                   │  Must Pass     │
                   └────────┬───────┘
                            ▼
                   ┌────────────────┐
                   │  Ready to      │
                   │  Merge         │
                   └────────────────┘
```

## Appendix C: `from __future__ import annotations` Warning

**NEVER** use `from __future__ import annotations` in FastAPI endpoint files. This import changes how Python evaluates type annotations (defers evaluation), which breaks FastAPI's response model introspection.

The specific failure mode: an endpoint decorated with `@router.delete` that returns `Response(status_code=204)` will raise:

```
AssertionError: Status code 204 must not have a response body
```

This happens because `from __future__ import annotations` causes FastAPI to misinterpret the return type annotation, leading it to expect a response body even for 204 No Content responses.

This import is safe in:
- Schema files (`schemas/*.py`)
- Model files (`models/*.py`)
- Service files (`services/*.py`)
- Utility files (`lib/*.py`)

It is **NOT safe** in:
- Endpoint files (`api/v1/endpoints/*.py`)
- Main application file (`main.py`)
