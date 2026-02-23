"""
SIMS Plus - JWT School ID Threshold Tests

Verifies the JWT size threshold mechanism:
- Users with <=20 schools get full UUID list in JWT accessible_school_ids
- Users with >20 schools get ["*"] sentinel
- SchoolContext validation handles both cases correctly

Uses admin_session (superuser) for seeding, app_session (RLS-enforced)
for running service queries.
"""

from uuid import uuid4, UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthService, MAX_JWT_SCHOOL_IDS
from tests.conftest import (
    set_app_tenant_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_chain_tenant(session: AsyncSession, subdomain: str | None = None) -> dict:
    """Create a school_chain tenant."""
    tenant_id = uuid4()
    sub = subdomain or f"jwt-chain-{uuid4().hex[:8]}"
    await session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students, max_staff)
            VALUES (
                CAST(:id AS uuid), :sub, :slug, :name,
                true, 'school_chain', 'enterprise', 5000, 500
            )
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub, "name": f"Chain {sub}"},
    )
    await session.flush()
    return {"id": tenant_id, "subdomain": sub}


async def _create_user(session: AsyncSession, tenant_id, email: str | None = None) -> dict:
    """Create a chain_admin user."""
    user_id = uuid4()
    user_email = email or f"jwt-user-{uuid4().hex[:8]}@test.com"
    await session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'JWT', 'Test', 'chain_admin', 'active',
                true, false, 0, 'Africa/Accra'
            )
        """),
        {
            "id": str(user_id), "tid": str(tenant_id),
            "email": user_email,
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash",
        },
    )
    await session.flush()
    return {"id": user_id, "email": user_email}


async def _create_school(session: AsyncSession, tenant_id, name: str = None) -> dict:
    """Create a school for the tenant."""
    school_id = uuid4()
    name = name or f"School-{uuid4().hex[:6]}"
    slug = f"s-{uuid4().hex[:8]}"
    code = f"S-{uuid4().hex[:4]}".upper()
    await session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, code,
                school_type, student_id_prefix)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                :code, 'basic', 'STU'
            )
        """),
        {
            "id": str(school_id), "tid": str(tenant_id),
            "name": name, "slug": slug, "code": code,
        },
    )
    await session.flush()
    return {"id": school_id, "name": name}


async def _assign_user_to_school(session, tenant_id, user_id, school_id) -> None:
    """Assign a user to a school."""
    await session.execute(
        text("""
            INSERT INTO user_schools (id, tenant_id, user_id, school_id,
                role_at_school, is_primary, is_active)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:uid AS uuid), CAST(:sid AS uuid),
                'school_admin', false, true
            )
        """),
        {
            "id": str(uuid4()), "tid": str(tenant_id),
            "uid": str(user_id), "sid": str(school_id),
        },
    )
    await session.flush()


# ===========================================================================
# _build_extra_claims threshold tests
# ===========================================================================


class TestJWTThreshold:
    """Tests for the JWT accessible_school_ids threshold logic."""

    @pytest.mark.asyncio
    async def test_user_under_threshold_gets_full_list(
        self, admin_session, app_session
    ):
        """User with <=20 schools gets full UUID list in JWT claims."""
        tenant = await _create_chain_tenant(admin_session)
        user = await _create_user(admin_session, tenant["id"])

        # Create 5 schools and assign the user to all of them
        school_ids = []
        for i in range(5):
            school = await _create_school(admin_session, tenant["id"])
            school_ids.append(str(school["id"]))
            await _assign_user_to_school(
                admin_session, tenant["id"], user["id"], school["id"]
            )
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        auth_svc = AuthService(app_session)

        # Use the internal method to build claims
        # First, we need to get the ORM user object
        from sqlalchemy import select
        from app.models.user import User
        result = await app_session.execute(
            select(User).where(User.id == user_id)
        )
        orm_user = result.scalar_one()

        claims = await auth_svc._build_extra_claims(orm_user, tenant["id"])

        assert claims["tenant_type"] == "school_chain"
        assert isinstance(claims["accessible_school_ids"], list)
        assert claims["accessible_school_ids"] != ["*"]
        assert len(claims["accessible_school_ids"]) == 5
        # All school IDs should be present
        for sid in school_ids:
            assert sid in claims["accessible_school_ids"]

    @pytest.mark.asyncio
    async def test_user_at_threshold_gets_full_list(
        self, admin_session, app_session
    ):
        """User with exactly 20 schools gets full UUID list (not sentinel)."""
        tenant = await _create_chain_tenant(admin_session)
        user = await _create_user(admin_session, tenant["id"])

        # Create exactly MAX_JWT_SCHOOL_IDS schools
        for i in range(MAX_JWT_SCHOOL_IDS):
            school = await _create_school(admin_session, tenant["id"])
            await _assign_user_to_school(
                admin_session, tenant["id"], user["id"], school["id"]
            )
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        auth_svc = AuthService(app_session)

        from sqlalchemy import select
        from app.models.user import User
        result = await app_session.execute(
            select(User).where(User.id == user_id)
        )
        orm_user = result.scalar_one()

        claims = await auth_svc._build_extra_claims(orm_user, tenant["id"])

        assert claims["accessible_school_ids"] != ["*"]
        assert len(claims["accessible_school_ids"]) == MAX_JWT_SCHOOL_IDS

    @pytest.mark.asyncio
    async def test_user_over_threshold_gets_wildcard_sentinel(
        self, admin_session, app_session
    ):
        """User with >20 schools gets ["*"] sentinel in JWT claims."""
        tenant = await _create_chain_tenant(admin_session)
        user = await _create_user(admin_session, tenant["id"])

        # Create MAX_JWT_SCHOOL_IDS + 1 schools (one over threshold)
        for i in range(MAX_JWT_SCHOOL_IDS + 1):
            school = await _create_school(admin_session, tenant["id"])
            await _assign_user_to_school(
                admin_session, tenant["id"], user["id"], school["id"]
            )
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant["id"])
        auth_svc = AuthService(app_session)

        from sqlalchemy import select
        from app.models.user import User
        result = await app_session.execute(
            select(User).where(User.id == user_id)
        )
        orm_user = result.scalar_one()

        claims = await auth_svc._build_extra_claims(orm_user, tenant["id"])

        assert claims["accessible_school_ids"] == ["*"]

    @pytest.mark.asyncio
    async def test_single_school_tenant_has_no_accessible_ids(
        self, admin_session, app_session
    ):
        """Single-school tenants should not have accessible_school_ids in claims."""
        tenant_id = uuid4()
        sub = f"single-{uuid4().hex[:8]}"
        await admin_session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, is_active,
                    tenant_type, subscription_tier, max_students, max_staff)
                VALUES (
                    CAST(:id AS uuid), :sub, :slug, :name,
                    true, 'single_school', 'professional', 500, 50
                )
            """),
            {"id": str(tenant_id), "sub": sub, "slug": sub, "name": f"Single {sub}"},
        )
        user = await _create_user(admin_session, tenant_id)
        await admin_session.commit()

        user_id = user["id"]
        await set_app_tenant_context(app_session, tenant_id)
        auth_svc = AuthService(app_session)

        from sqlalchemy import select
        from app.models.user import User
        result = await app_session.execute(
            select(User).where(User.id == user_id)
        )
        orm_user = result.scalar_one()

        claims = await auth_svc._build_extra_claims(orm_user, tenant_id)

        # Single-school tenants should NOT have accessible_school_ids
        assert "accessible_school_ids" not in claims
        assert "tenant_type" not in claims


# ===========================================================================
# SchoolContext validation with ["*"] sentinel
# ===========================================================================


class TestSchoolContextWithWildcard:
    """Tests for get_school_context handling of the ["*"] sentinel.

    These tests verify the SchoolContext dependency (from app.api.deps)
    directly via the get_school_context function logic. We simulate the
    required request/user/db context.
    """

    @pytest.mark.asyncio
    async def test_wildcard_sentinel_with_valid_school_passes(
        self, admin_session, app_session
    ):
        """SchoolContext with ["*"] sentinel accepts a valid school in the tenant."""
        from unittest.mock import MagicMock
        from app.api.deps import get_school_context

        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"])
        await admin_session.commit()

        school_id = school["id"]
        tenant_id = tenant["id"]

        await set_app_tenant_context(app_session, tenant_id)

        # Build mock request and user dict
        mock_request = MagicMock()
        mock_request.state.tenant_id = tenant_id

        user_dict = {
            "user_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "tenant_type": "school_chain",
            "accessible_school_ids": ["*"],
            "role": "chain_admin",
            "permissions": ["*"],
        }

        ctx = await get_school_context(
            request=mock_request,
            db=app_session,
            user=user_dict,
            x_active_school=str(school_id),
        )

        assert ctx.school_id == school_id
        assert ctx.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_wildcard_sentinel_with_nonexistent_school_returns_404(
        self, admin_session, app_session
    ):
        """SchoolContext with ["*"] sentinel rejects a non-existent school (404)."""
        from unittest.mock import MagicMock
        from fastapi import HTTPException
        from app.api.deps import get_school_context

        tenant = await _create_chain_tenant(admin_session)
        await admin_session.commit()

        tenant_id = tenant["id"]
        fake_school_id = uuid4()

        await set_app_tenant_context(app_session, tenant_id)

        mock_request = MagicMock()
        mock_request.state.tenant_id = tenant_id

        user_dict = {
            "user_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "tenant_type": "school_chain",
            "accessible_school_ids": ["*"],
            "role": "chain_admin",
            "permissions": ["*"],
        }

        with pytest.raises(HTTPException) as exc_info:
            await get_school_context(
                request=mock_request,
                db=app_session,
                user=user_dict,
                x_active_school=str(fake_school_id),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_accessible_ids_for_chain_tenant_returns_403(
        self, admin_session, app_session
    ):
        """SchoolContext with empty accessible_ids for chain tenant returns 403."""
        from unittest.mock import MagicMock
        from fastapi import HTTPException
        from app.api.deps import get_school_context

        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"])
        await admin_session.commit()

        tenant_id = tenant["id"]
        school_id = school["id"]

        await set_app_tenant_context(app_session, tenant_id)

        mock_request = MagicMock()
        mock_request.state.tenant_id = tenant_id

        user_dict = {
            "user_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "tenant_type": "school_chain",
            "accessible_school_ids": [],  # Empty = no school access
            "role": "chain_admin",
            "permissions": ["*"],
        }

        with pytest.raises(HTTPException) as exc_info:
            await get_school_context(
                request=mock_request,
                db=app_session,
                user=user_dict,
                x_active_school=str(school_id),
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_specific_list_with_valid_school_passes(
        self, admin_session, app_session
    ):
        """SchoolContext with specific UUID list accepts a valid school from the list."""
        from unittest.mock import MagicMock
        from app.api.deps import get_school_context

        tenant = await _create_chain_tenant(admin_session)
        school = await _create_school(admin_session, tenant["id"])
        await admin_session.commit()

        school_id = school["id"]
        tenant_id = tenant["id"]

        await set_app_tenant_context(app_session, tenant_id)

        mock_request = MagicMock()
        mock_request.state.tenant_id = tenant_id

        user_dict = {
            "user_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "tenant_type": "school_chain",
            "accessible_school_ids": [str(school_id)],
            "role": "chain_admin",
            "permissions": ["*"],
        }

        ctx = await get_school_context(
            request=mock_request,
            db=app_session,
            user=user_dict,
            x_active_school=str(school_id),
        )

        assert ctx.school_id == school_id

    @pytest.mark.asyncio
    async def test_specific_list_rejects_school_not_in_list(
        self, admin_session, app_session
    ):
        """SchoolContext with specific UUID list rejects a school not in the list."""
        from unittest.mock import MagicMock
        from fastapi import HTTPException
        from app.api.deps import get_school_context

        tenant = await _create_chain_tenant(admin_session)
        school_a = await _create_school(admin_session, tenant["id"], "Allowed School")
        school_b = await _create_school(admin_session, tenant["id"], "Forbidden School")
        await admin_session.commit()

        tenant_id = tenant["id"]
        school_b_id = school_b["id"]

        await set_app_tenant_context(app_session, tenant_id)

        mock_request = MagicMock()
        mock_request.state.tenant_id = tenant_id

        user_dict = {
            "user_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "tenant_type": "school_chain",
            "accessible_school_ids": [str(school_a["id"])],  # Only school_a
            "role": "chain_admin",
            "permissions": ["*"],
        }

        with pytest.raises(HTTPException) as exc_info:
            await get_school_context(
                request=mock_request,
                db=app_session,
                user=user_dict,
                x_active_school=str(school_b_id),  # Try school_b
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_chain_tenant_without_header_returns_400(
        self, admin_session, app_session
    ):
        """Chain tenant without X-Active-School header returns 400."""
        from unittest.mock import MagicMock
        from fastapi import HTTPException
        from app.api.deps import get_school_context

        tenant = await _create_chain_tenant(admin_session)
        await admin_session.commit()

        tenant_id = tenant["id"]
        await set_app_tenant_context(app_session, tenant_id)

        mock_request = MagicMock()
        mock_request.state.tenant_id = tenant_id

        user_dict = {
            "user_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "tenant_type": "school_chain",
            "accessible_school_ids": ["*"],
            "role": "chain_admin",
            "permissions": ["*"],
        }

        with pytest.raises(HTTPException) as exc_info:
            await get_school_context(
                request=mock_request,
                db=app_session,
                user=user_dict,
                x_active_school=None,  # No header
            )
        assert exc_info.value.status_code == 400
