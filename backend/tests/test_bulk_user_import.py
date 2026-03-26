"""
Tests for bulk user CSV import.

Phase 1C: Tests the /users/import/template and /users/import endpoints.
"""

from unittest.mock import AsyncMock, patch
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


@pytest_asyncio.fixture
async def import_tenant():
    """Create tenant + school + admin user for import tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"import-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'professional', 'active', 1000, 100, true)
        """), {"id": str(tenant_id), "subdomain": subdomain, "slug": subdomain,
               "name": f"Import Test {subdomain}"})

        await session.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'IM', 'basic')
        """), {"id": str(school_id), "tid": str(tenant_id),
               "name": f"Import Test {subdomain}", "slug": subdomain})

        await session.execute(text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Admin', 'Import', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
        """), {"id": str(user_id), "tid": str(tenant_id),
               "email": f"admin@{subdomain}.test",
               "pw": hash_password("TestPass123!")})

        await session.commit()

    yield {
        "tenant_id": tenant_id, "school_id": school_id, "user_id": user_id,
        "subdomain": subdomain,
    }

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
async def import_client(import_tenant):
    """Authenticated client for import tests."""
    td = import_tenant
    token = create_access_token(
        subject=str(td["user_id"]), tenant_id=str(td["tenant_id"]),
        school_id=str(td["school_id"]), role="school_admin",
        permissions=["*"],
    )

    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                tid = getattr(getattr(request, "state", None), "tenant_id", None)
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
            transport=ASGITransport(app=app), base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": td["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.clear()


def _make_csv(rows: list[list[str]], bom: bool = False) -> bytes:
    """Build CSV bytes from rows. First row is the header."""
    lines = [",".join(row) for row in rows]
    content = "\n".join(lines)
    if bom:
        return b"\xef\xbb\xbf" + content.encode("utf-8")
    return content.encode("utf-8")


class TestImportTemplate:
    @pytest.mark.asyncio
    async def test_download_template(self, import_client):
        """GET /users/import/template should return CSV with correct headers."""
        resp = await import_client.get("/api/v1/users/import/template")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        first_line = content.strip().split("\n")[0]
        assert "email" in first_line
        assert "first_name" in first_line
        assert "last_name" in first_line
        assert "role" in first_line

    @pytest.mark.asyncio
    async def test_template_has_example_rows(self, import_client):
        """Template should include example data rows."""
        resp = await import_client.get("/api/v1/users/import/template")
        lines = resp.text.strip().split("\n")
        assert len(lines) >= 3  # header + 2 example rows


class TestImportPreview:
    @pytest.mark.asyncio
    async def test_preview_valid_csv(self, import_client):
        """Preview mode should validate without creating users."""
        csv_data = _make_csv([
            ["email", "first_name", "last_name", "role", "phone"],
            ["new.user@test.com", "New", "User", "teacher", "+233241234567"],
        ])
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "true"},
            files={"file": ("users.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["created"] == 0  # Preview doesn't create


class TestImportValidation:
    @pytest.mark.asyncio
    async def test_invalid_email_format(self, import_client):
        """Invalid email should show error for that row."""
        csv_data = _make_csv([
            ["email", "first_name", "last_name", "role", "phone"],
            ["not-an-email", "Bad", "Email", "teacher", ""],
        ])
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "true"},
            files={"file": ("users.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_role(self, import_client):
        """Invalid role value should show error."""
        csv_data = _make_csv([
            ["email", "first_name", "last_name", "role", "phone"],
            ["valid@test.com", "Good", "Name", "invalid_role", ""],
        ])
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "true"},
            files={"file": ("users.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_platform_admin_role_rejected(self, import_client):
        """platform_admin is not an importable role."""
        csv_data = _make_csv([
            ["email", "first_name", "last_name", "role", "phone"],
            ["admin@test.com", "Admin", "User", "platform_admin", ""],
        ])
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "true"},
            files={"file": ("users.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_parent_role_rejected(self, import_client):
        """parent is not an importable role (staff roles only)."""
        csv_data = _make_csv([
            ["email", "first_name", "last_name", "role", "phone"],
            ["parent@test.com", "Parent", "User", "parent", ""],
        ])
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "true"},
            files={"file": ("users.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) > 0


class TestImportExecution:
    @pytest.mark.asyncio
    async def test_import_creates_users(self, import_client):
        """Valid CSV should create users."""
        unique = uuid4().hex[:6]
        csv_data = _make_csv([
            ["email", "first_name", "last_name", "role", "phone"],
            [f"teacher1-{unique}@test.com", "Teacher", "One", "teacher", ""],
            [f"teacher2-{unique}@test.com", "Teacher", "Two", "teacher", ""],
        ])
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "false"},
            files={"file": ("users.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2


class TestImportFileValidation:
    @pytest.mark.asyncio
    async def test_non_csv_rejected(self, import_client):
        """Non-CSV file should return 400."""
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "false"},
            files={"file": ("users.txt", b"some data", "text/plain")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_utf8_bom_handled(self, import_client):
        """CSV with UTF-8 BOM (from Excel) should parse correctly."""
        unique = uuid4().hex[:6]
        csv_data = _make_csv([
            ["email", "first_name", "last_name", "role", "phone"],
            [f"bom-{unique}@test.com", "BOM", "User", "teacher", ""],
        ], bom=True)
        resp = await import_client.post(
            "/api/v1/users/import",
            data={"preview": "true"},
            files={"file": ("users.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should parse correctly despite BOM
        assert data["total"] == 1
