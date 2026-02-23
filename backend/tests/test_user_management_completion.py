"""
Tests for Sprint 18.5 User Management completion.

Verifies token blacklisting on status changes, password resets, and deletes.
Verifies audit logging on create, update, delete, role change, and invite.
Verifies password reset email sending behaviour.

Uses E2E-style authenticated client to hit real endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from sqlalchemy import text
from tests.conftest import admin_session_maker
from tests.e2e.conftest import (
    _test_middleware_session_maker,
    E2E_PASSWORD,
    E2E_EMAIL_DOMAIN,
)

from app.core.security import create_access_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db

import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import admin_engine, app_session_maker


# ===========================
# Fixtures
# ===========================


@pytest_asyncio.fixture
async def user_mgmt_tenant():
    """Seed a tenant, school, admin user, and a target user for management tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    admin_user_id = uuid4()
    target_user_id = uuid4()
    subdomain = f"usrmgmt-{uuid4().hex[:8]}"
    pw_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"UMgmt {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'UM', 'basic')
            """),
            {"id": str(school_id), "tid": str(tenant_id), "name": f"UMgmt School {subdomain}", "slug": subdomain},
        )
        # Admin user (the one making API calls)
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'User', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(admin_user_id), "tid": str(tenant_id), "email": f"admin@{subdomain}.test", "pw": pw_hash},
        )
        # Target user (the one being managed)
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Target', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(target_user_id), "tid": str(tenant_id), "email": f"target@{subdomain}.test", "pw": pw_hash},
        )
        await session.commit()

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "admin_user_id": admin_user_id,
        "target_user_id": target_user_id,
        "subdomain": subdomain,
    }

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
async def mgmt_client(user_mgmt_tenant):
    """Authenticated client for user management tests."""
    t = user_mgmt_tenant
    token = create_access_token(
        subject=str(t["admin_user_id"]),
        tenant_id=str(t["tenant_id"]),
        school_id=str(t["school_id"]),
        role="school_admin",
        permissions=["*"],
        extra_claims={"email": f"admin@{t['subdomain']}.test"},
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

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": t["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


# ===========================
# Token Blacklisting Tests
# ===========================


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.get_token_blacklist_service")
async def test_token_blacklisted_on_suspend(mock_get_blacklist, mgmt_client, user_mgmt_tenant):
    """Suspending a user should blacklist their tokens."""
    mock_service = AsyncMock()
    mock_get_blacklist.return_value = mock_service

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.patch(
        f"/api/v1/users/{target_id}/status",
        json={"status": "suspended"},
    )
    assert resp.status_code == 200

    mock_service.blacklist_user_tokens.assert_called_once_with(target_id)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.get_token_blacklist_service")
async def test_token_blacklisted_on_deactivate(mock_get_blacklist, mgmt_client, user_mgmt_tenant):
    """Deactivating a user should blacklist their tokens."""
    mock_service = AsyncMock()
    mock_get_blacklist.return_value = mock_service

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.patch(
        f"/api/v1/users/{target_id}/status",
        json={"status": "deactivated"},
    )
    assert resp.status_code == 200

    mock_service.blacklist_user_tokens.assert_called_once_with(target_id)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.get_token_blacklist_service")
async def test_no_token_blacklist_on_activate(mock_get_blacklist, mgmt_client, user_mgmt_tenant):
    """Activating a user should NOT blacklist their tokens."""
    mock_service = AsyncMock()
    mock_get_blacklist.return_value = mock_service

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.patch(
        f"/api/v1/users/{target_id}/status",
        json={"status": "active"},
    )
    assert resp.status_code == 200

    mock_service.blacklist_user_tokens.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.get_token_blacklist_service")
async def test_token_blacklisted_on_delete(mock_get_blacklist, mgmt_client, user_mgmt_tenant):
    """Deleting a user should blacklist their tokens."""
    mock_service = AsyncMock()
    mock_get_blacklist.return_value = mock_service

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.delete(f"/api/v1/users/{target_id}")
    assert resp.status_code == 204

    mock_service.blacklist_user_tokens.assert_called_once_with(target_id)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.get_token_blacklist_service")
async def test_token_blacklisted_on_password_reset(mock_get_blacklist, mgmt_client, user_mgmt_tenant):
    """Resetting a user password should blacklist their tokens."""
    mock_service = AsyncMock()
    mock_get_blacklist.return_value = mock_service

    target_id = str(user_mgmt_tenant["target_user_id"])

    with patch("app.api.v1.endpoints.users.email_service") as mock_email:
        mock_email.send_user_credentials_email = AsyncMock(return_value=True)
        resp = await mgmt_client.post(
            f"/api/v1/users/{target_id}/reset-password",
            json={"new_password": "NewPassword1!", "send_email": False},
        )
    assert resp.status_code == 200

    mock_service.blacklist_user_tokens.assert_called_once_with(target_id)


# ===========================
# Password Reset Email Tests
# ===========================


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.get_token_blacklist_service", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.users.email_service")
async def test_password_reset_sends_email_when_requested(
    mock_email_svc, mock_get_blacklist, mgmt_client, user_mgmt_tenant
):
    """Password reset with send_email=True should call send_user_credentials_email."""
    mock_get_blacklist.return_value = AsyncMock()
    mock_email_svc.send_user_credentials_email = AsyncMock(return_value=True)

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.post(
        f"/api/v1/users/{target_id}/reset-password",
        json={"new_password": "NewPassword1!", "send_email": True},
    )
    assert resp.status_code == 200

    mock_email_svc.send_user_credentials_email.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.get_token_blacklist_service", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.users.email_service")
async def test_password_reset_skips_email_when_not_requested(
    mock_email_svc, mock_get_blacklist, mgmt_client, user_mgmt_tenant
):
    """Password reset with send_email=False should NOT call send_user_credentials_email."""
    mock_get_blacklist.return_value = AsyncMock()
    mock_email_svc.send_user_credentials_email = AsyncMock(return_value=True)

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.post(
        f"/api/v1/users/{target_id}/reset-password",
        json={"new_password": "NewPassword1!", "send_email": False},
    )
    assert resp.status_code == 200

    mock_email_svc.send_user_credentials_email.assert_not_called()


# ===========================
# Audit Logging Tests
# ===========================


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.AuditService")
@patch("app.api.v1.endpoints.users.email_service")
async def test_audit_log_on_user_create(mock_email_svc, mock_audit_cls, mgmt_client, user_mgmt_tenant):
    """Creating a user should produce an ACCOUNT_CREATED audit log."""
    mock_email_svc.send_user_credentials_email = AsyncMock(return_value=True)
    mock_audit_instance = AsyncMock()
    mock_audit_cls.return_value = mock_audit_instance

    resp = await mgmt_client.post(
        "/api/v1/users",
        json={
            "email": f"newuser-{uuid4().hex[:6]}@test.com",
            "password": "SecurePass1!",
            "first_name": "New",
            "last_name": "User",
            "role": "teacher",
        },
    )
    assert resp.status_code == 201

    mock_audit_instance.log.assert_called_once()
    call_kwargs = mock_audit_instance.log.call_args
    assert call_kwargs.kwargs["event_type"] == "account.created"
    assert call_kwargs.kwargs["target_type"] == "user"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.AuditService")
async def test_audit_log_on_user_update(mock_audit_cls, mgmt_client, user_mgmt_tenant):
    """Updating a user should produce a SETTINGS_CHANGED audit log."""
    mock_audit_instance = AsyncMock()
    mock_audit_cls.return_value = mock_audit_instance

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.put(
        f"/api/v1/users/{target_id}",
        json={"first_name": "Updated"},
    )
    assert resp.status_code == 200

    mock_audit_instance.log.assert_called_once()
    call_kwargs = mock_audit_instance.log.call_args
    assert call_kwargs.kwargs["event_type"] == "admin.settings.changed"
    assert call_kwargs.kwargs["target_type"] == "user"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.AuditService")
@patch("app.api.v1.endpoints.users.get_token_blacklist_service", new_callable=AsyncMock)
async def test_audit_log_on_user_delete(mock_get_blacklist, mock_audit_cls, mgmt_client, user_mgmt_tenant):
    """Deleting a user should produce an ACCOUNT_DEACTIVATED audit log."""
    mock_get_blacklist.return_value = AsyncMock()
    mock_audit_instance = AsyncMock()
    mock_audit_cls.return_value = mock_audit_instance

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.delete(f"/api/v1/users/{target_id}")
    assert resp.status_code == 204

    mock_audit_instance.log.assert_called_once()
    call_kwargs = mock_audit_instance.log.call_args
    assert call_kwargs.kwargs["event_type"] == "account.deactivated"
    assert call_kwargs.kwargs["target_type"] == "user"
    assert call_kwargs.kwargs["details"]["action"] == "deleted"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.AuditService")
async def test_audit_log_on_role_change(mock_audit_cls, mgmt_client, user_mgmt_tenant):
    """Changing a user's role should produce a USER_ROLE_CHANGED audit log."""
    mock_audit_instance = AsyncMock()
    mock_audit_cls.return_value = mock_audit_instance

    target_id = str(user_mgmt_tenant["target_user_id"])

    resp = await mgmt_client.patch(
        f"/api/v1/users/{target_id}/role",
        json={"role": "finance_officer"},
    )
    assert resp.status_code == 200

    mock_audit_instance.log.assert_called_once()
    call_kwargs = mock_audit_instance.log.call_args
    assert call_kwargs.kwargs["event_type"] == "admin.user.role_changed"
    assert call_kwargs.kwargs["details"]["new_role"] == "finance_officer"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.users.AuditService")
@patch("app.api.v1.endpoints.users.email_service")
async def test_audit_log_on_user_invite(mock_email_svc, mock_audit_cls, mgmt_client, user_mgmt_tenant):
    """Inviting a user should produce an ACCOUNT_CREATED audit log with method=invite."""
    mock_email_svc.send_user_invite = AsyncMock(return_value=True)
    mock_audit_instance = AsyncMock()
    mock_audit_cls.return_value = mock_audit_instance

    resp = await mgmt_client.post(
        "/api/v1/users/invite",
        json={
            "email": f"invite-{uuid4().hex[:6]}@test.com",
            "role": "teacher",
            "first_name": "Invited",
            "last_name": "User",
        },
    )
    assert resp.status_code == 201

    mock_audit_instance.log.assert_called_once()
    call_kwargs = mock_audit_instance.log.call_args
    assert call_kwargs.kwargs["event_type"] == "account.created"
    assert call_kwargs.kwargs["details"]["method"] == "invite"
