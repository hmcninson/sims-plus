"""
Tests for TOTP MFA service.

Phase 3: Tests MFA setup, verify-setup, TOTP login, backup codes, disable.
Service-level tests (no HTTP layer) for speed and precision.
"""

import json
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import text

from app.core.security import hash_password, verify_password
from app.services.mfa import MFAService, MFAError
from tests.conftest import admin_session_maker, app_session_maker, set_app_tenant_context


# Generate a valid Fernet key for tests
TEST_FERNET_KEY = Fernet.generate_key().decode()
PASSWORD = "TestPass123!"


@pytest_asyncio.fixture
async def mfa_tenant():
    """Create tenant + user for MFA tests."""
    tenant_id = uuid4()
    user_id = uuid4()
    subdomain = f"mfa-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'professional', 'active', 1000, 100, true)
        """), {"id": str(tenant_id), "subdomain": subdomain, "slug": subdomain,
               "name": f"MFA Test {subdomain}"})

        await session.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'MF', 'basic')
        """), {"id": str(uuid4()), "tid": str(tenant_id),
               "name": f"MFA Test {subdomain}", "slug": subdomain})

        await session.execute(text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Test', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra')
        """), {"id": str(user_id), "tid": str(tenant_id),
               "email": f"user@{subdomain}.test", "pw": hash_password(PASSWORD)})

        await session.commit()

    yield {"tenant_id": tenant_id, "user_id": user_id}

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
async def mfa_app_session(mfa_tenant):
    """App session with tenant context set for MFA tests."""
    async with app_session_maker() as session:
        await set_app_tenant_context(session, mfa_tenant["tenant_id"])
        yield session
        try:
            await session.rollback()
        except Exception:
            pass


def _make_mfa_service(db):
    """Create MFAService with test encryption key."""
    from app.config import settings
    original = settings.MFA_SECRET_ENCRYPTION_KEY
    settings.MFA_SECRET_ENCRYPTION_KEY = TEST_FERNET_KEY
    try:
        return MFAService(db)
    finally:
        # Don't restore -- the service already captured the key
        pass


class TestMFASetup:
    @pytest.mark.asyncio
    async def test_setup_returns_qr_and_secret(self, mfa_tenant, mfa_app_session):
        """setup_totp should return QR code, secret, and backup codes."""
        svc = _make_mfa_service(mfa_app_session)
        result = await svc.setup_totp(mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        assert "secret" in result
        assert "qr_code_base64" in result
        assert "backup_codes" in result
        assert result["qr_code_base64"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_setup_returns_10_backup_codes(self, mfa_tenant, mfa_app_session):
        """Should return exactly 10 backup codes."""
        svc = _make_mfa_service(mfa_app_session)
        result = await svc.setup_totp(mfa_tenant["user_id"], mfa_tenant["tenant_id"])
        assert len(result["backup_codes"]) == 10

    @pytest.mark.asyncio
    async def test_mfa_not_enabled_until_verify(self, mfa_tenant, mfa_app_session):
        """mfa_enabled should remain False after setup (before verify)."""
        svc = _make_mfa_service(mfa_app_session)
        await svc.setup_totp(mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        # Check DB directly
        from app.models.user import User
        from sqlalchemy import select
        result = await mfa_app_session.execute(
            select(User).where(User.id == mfa_tenant["user_id"])
        )
        user = result.scalar_one()
        assert user.mfa_enabled is False
        assert user.mfa_setup_pending_secret is not None


class TestMFAVerifySetup:
    @pytest.mark.asyncio
    async def test_verify_with_valid_code_enables_mfa(self, mfa_tenant, mfa_app_session):
        """Valid TOTP code should enable MFA."""
        svc = _make_mfa_service(mfa_app_session)
        setup = await svc.setup_totp(mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        # Mock pyotp.TOTP.verify to return True
        with patch("app.services.mfa.pyotp.TOTP") as mock_totp_cls:
            mock_totp = mock_totp_cls.return_value
            mock_totp.verify.return_value = True

            result = await svc.verify_and_enable(
                mfa_tenant["user_id"], mfa_tenant["tenant_id"], "123456"
            )
            assert result is True

        # User should now have mfa_enabled=True
        from app.models.user import User
        from sqlalchemy import select
        result = await mfa_app_session.execute(
            select(User).where(User.id == mfa_tenant["user_id"])
        )
        user = result.scalar_one()
        assert user.mfa_enabled is True
        assert user.mfa_secret is not None
        assert user.mfa_setup_pending_secret is None

    @pytest.mark.asyncio
    async def test_verify_with_invalid_code_fails(self, mfa_tenant, mfa_app_session):
        """Invalid code should return error without enabling MFA."""
        svc = _make_mfa_service(mfa_app_session)
        await svc.setup_totp(mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        with patch("app.services.mfa.pyotp.TOTP") as mock_totp_cls:
            mock_totp = mock_totp_cls.return_value
            mock_totp.verify.return_value = False

            with pytest.raises(MFAError) as exc_info:
                await svc.verify_and_enable(
                    mfa_tenant["user_id"], mfa_tenant["tenant_id"], "000000"
                )
            assert exc_info.value.code == "invalid_code"

    @pytest.mark.asyncio
    async def test_verify_without_setup_fails(self, mfa_tenant, mfa_app_session):
        """Should fail if no setup is in progress."""
        svc = _make_mfa_service(mfa_app_session)
        with pytest.raises(MFAError) as exc_info:
            await svc.verify_and_enable(
                mfa_tenant["user_id"], mfa_tenant["tenant_id"], "123456"
            )
        assert exc_info.value.code == "no_pending_setup"


class TestMFAVerifyTOTP:
    async def _setup_and_enable_mfa(self, svc, user_id, tenant_id):
        """Helper: setup and enable MFA, return backup codes."""
        setup = await svc.setup_totp(user_id, tenant_id)
        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = True
            await svc.verify_and_enable(user_id, tenant_id, "123456")
        return setup["backup_codes"]

    @pytest.mark.asyncio
    async def test_verify_totp_with_valid_code(self, mfa_tenant, mfa_app_session):
        """Correct TOTP code should verify."""
        svc = _make_mfa_service(mfa_app_session)
        await self._setup_and_enable_mfa(svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = True
            result = await svc.verify_totp(
                mfa_tenant["user_id"], mfa_tenant["tenant_id"], "123456"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_backup_code_works(self, mfa_tenant, mfa_app_session):
        """Backup code should work for MFA verification."""
        svc = _make_mfa_service(mfa_app_session)
        backup_codes = await self._setup_and_enable_mfa(
            svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"]
        )

        # Use a backup code (mock TOTP to fail, so backup path is tried)
        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = False
            result = await svc.verify_totp(
                mfa_tenant["user_id"], mfa_tenant["tenant_id"], backup_codes[0]
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_backup_code_burned_after_use(self, mfa_tenant, mfa_app_session):
        """Used backup code should not work a second time."""
        svc = _make_mfa_service(mfa_app_session)
        backup_codes = await self._setup_and_enable_mfa(
            svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"]
        )

        code = backup_codes[0]
        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = False
            # First use succeeds
            await svc.verify_totp(
                mfa_tenant["user_id"], mfa_tenant["tenant_id"], code
            )
            # Second use fails
            with pytest.raises(MFAError) as exc_info:
                await svc.verify_totp(
                    mfa_tenant["user_id"], mfa_tenant["tenant_id"], code
                )
            assert exc_info.value.code == "invalid_code"

    @pytest.mark.asyncio
    async def test_invalid_totp_and_backup_fails(self, mfa_tenant, mfa_app_session):
        """Invalid TOTP code and invalid backup code should fail."""
        svc = _make_mfa_service(mfa_app_session)
        await self._setup_and_enable_mfa(
            svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"]
        )

        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = False
            with pytest.raises(MFAError) as exc_info:
                await svc.verify_totp(
                    mfa_tenant["user_id"], mfa_tenant["tenant_id"], "WRONG-CODE"
                )
            assert exc_info.value.code == "invalid_code"


class TestMFADisable:
    async def _setup_and_enable_mfa(self, svc, user_id, tenant_id):
        await svc.setup_totp(user_id, tenant_id)
        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = True
            await svc.verify_and_enable(user_id, tenant_id, "123456")

    @pytest.mark.asyncio
    async def test_disable_with_correct_password(self, mfa_tenant, mfa_app_session):
        """Disable MFA with correct password should succeed."""
        svc = _make_mfa_service(mfa_app_session)
        await self._setup_and_enable_mfa(svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        result = await svc.disable_mfa(
            mfa_tenant["user_id"], mfa_tenant["tenant_id"], PASSWORD
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_disable_clears_all_mfa_fields(self, mfa_tenant, mfa_app_session):
        """Should clear mfa_secret, backup codes, pending secret."""
        svc = _make_mfa_service(mfa_app_session)
        await self._setup_and_enable_mfa(svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"])
        await svc.disable_mfa(mfa_tenant["user_id"], mfa_tenant["tenant_id"], PASSWORD)

        from app.models.user import User
        from sqlalchemy import select
        result = await mfa_app_session.execute(
            select(User).where(User.id == mfa_tenant["user_id"])
        )
        user = result.scalar_one()
        assert user.mfa_enabled is False
        assert user.mfa_secret is None
        assert user.mfa_backup_codes_hash is None
        assert user.mfa_setup_pending_secret is None

    @pytest.mark.asyncio
    async def test_disable_with_wrong_password_fails(self, mfa_tenant, mfa_app_session):
        """Should fail with incorrect password."""
        svc = _make_mfa_service(mfa_app_session)
        await self._setup_and_enable_mfa(svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        with pytest.raises(MFAError) as exc_info:
            await svc.disable_mfa(
                mfa_tenant["user_id"], mfa_tenant["tenant_id"], "WrongPass123!"
            )
        assert exc_info.value.code == "invalid_password"


class TestMFABackupCodes:
    async def _setup_and_enable_mfa(self, svc, user_id, tenant_id):
        setup = await svc.setup_totp(user_id, tenant_id)
        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = True
            await svc.verify_and_enable(user_id, tenant_id, "123456")
        return setup["backup_codes"]

    @pytest.mark.asyncio
    async def test_regenerate_returns_new_codes(self, mfa_tenant, mfa_app_session):
        """Regeneration should return 10 new codes."""
        svc = _make_mfa_service(mfa_app_session)
        await self._setup_and_enable_mfa(svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"])

        new_codes = await svc.regenerate_backup_codes(
            mfa_tenant["user_id"], mfa_tenant["tenant_id"], PASSWORD
        )
        assert len(new_codes) == 10

    @pytest.mark.asyncio
    async def test_regenerate_invalidates_old_codes(self, mfa_tenant, mfa_app_session):
        """Old backup codes should no longer work after regeneration."""
        svc = _make_mfa_service(mfa_app_session)
        old_codes = await self._setup_and_enable_mfa(
            svc, mfa_tenant["user_id"], mfa_tenant["tenant_id"]
        )

        # Regenerate
        await svc.regenerate_backup_codes(
            mfa_tenant["user_id"], mfa_tenant["tenant_id"], PASSWORD
        )

        # Old code should fail
        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = False
            with pytest.raises(MFAError) as exc_info:
                await svc.verify_totp(
                    mfa_tenant["user_id"], mfa_tenant["tenant_id"], old_codes[0]
                )
            assert exc_info.value.code == "invalid_code"


class TestMFAAdminDisable:
    @pytest.mark.asyncio
    async def test_admin_can_disable_user_mfa(self, mfa_tenant, mfa_app_session):
        """Admin should be able to force-disable MFA."""
        svc = _make_mfa_service(mfa_app_session)
        # Setup and enable MFA
        await svc.setup_totp(mfa_tenant["user_id"], mfa_tenant["tenant_id"])
        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = True
            await svc.verify_and_enable(mfa_tenant["user_id"], mfa_tenant["tenant_id"], "123456")

        admin_id = uuid4()
        result = await svc.admin_disable_mfa(
            mfa_tenant["user_id"], mfa_tenant["tenant_id"], admin_id
        )
        assert result is True

        # Verify MFA is disabled
        from app.models.user import User
        from sqlalchemy import select
        db_result = await mfa_app_session.execute(
            select(User).where(User.id == mfa_tenant["user_id"])
        )
        user = db_result.scalar_one()
        assert user.mfa_enabled is False


class TestMFASecurity:
    @pytest.mark.asyncio
    async def test_secret_encrypted_in_database(self, mfa_tenant, mfa_app_session):
        """mfa_secret should be encrypted (not base32 plaintext) after setup+verify."""
        svc = _make_mfa_service(mfa_app_session)
        setup = await svc.setup_totp(mfa_tenant["user_id"], mfa_tenant["tenant_id"])
        raw_secret = setup["secret"]

        with patch("app.services.mfa.pyotp.TOTP") as mock_cls:
            mock_cls.return_value.verify.return_value = True
            await svc.verify_and_enable(mfa_tenant["user_id"], mfa_tenant["tenant_id"], "123456")

        from app.models.user import User
        from sqlalchemy import select
        result = await mfa_app_session.execute(
            select(User.mfa_secret).where(User.id == mfa_tenant["user_id"])
        )
        stored = result.scalar_one()
        # Stored value should NOT be the raw base32 secret
        assert stored != raw_secret
        # Should be a Fernet-encrypted blob (starts with gAAAA typically)
        assert len(stored) > len(raw_secret)
