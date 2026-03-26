"""
SIMS Plus - TOTP-based Multi-Factor Authentication Service

Uses:
- pyotp for TOTP generation/verification (RFC 6238)
- qrcode for QR code generation
- cryptography.fernet for secret encryption at rest
- argon2 for backup code hashing

MFA Setup Flow:
1. User calls /auth/mfa/setup -> receives QR code + backup codes
2. User scans QR with authenticator app
3. User calls /auth/mfa/verify-setup with a code from the app
4. MFA is enabled

MFA Login Flow:
1. User logs in with email + password -> receives mfa_pending_token (5 min TTL)
2. User calls /auth/mfa/verify with pending token + TOTP code
3. Full access_token + refresh_token issued
"""

import base64
import io
import json
import secrets
import string

import pyotp
import qrcode
import structlog
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User

logger = structlog.get_logger()


class MFAError(Exception):
    """MFA operation failed."""

    def __init__(self, message: str, code: str = "mfa_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class MFAService:
    """TOTP-based MFA service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        # Fernet requires a URL-safe base64-encoded 32-byte key
        if not settings.MFA_SECRET_ENCRYPTION_KEY:
            raise MFAError(
                "MFA encryption key not configured. "
                "Set MFA_SECRET_ENCRYPTION_KEY environment variable.",
                "configuration_error",
            )
        try:
            self._fernet = Fernet(settings.MFA_SECRET_ENCRYPTION_KEY.encode())
        except Exception:
            raise MFAError(
                "Invalid MFA encryption key. "
                "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"",
                "configuration_error",
            )

    def _encrypt_secret(self, secret: str) -> str:
        """Encrypt TOTP secret for database storage."""
        return self._fernet.encrypt(secret.encode()).decode()

    def _decrypt_secret(self, encrypted: str) -> str:
        """Decrypt TOTP secret from database storage."""
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken:
            raise MFAError(
                "Failed to decrypt MFA secret. Key may have changed.",
                "decryption_error",
            )

    def _generate_backup_codes(self, count: int | None = None) -> list[str]:
        """
        Generate one-time backup codes.

        Each code: 8 alphanumeric characters, formatted as XXXX-XXXX.
        Ambiguous characters (0, O, I, 1, L) are excluded for readability.
        """
        count = count or settings.MFA_BACKUP_CODES_COUNT
        # Remove ambiguous characters to prevent user confusion
        alphabet = string.ascii_uppercase + string.digits
        alphabet = (
            alphabet.replace("0", "")
            .replace("O", "")
            .replace("I", "")
            .replace("1", "")
            .replace("L", "")
        )
        codes = []
        for _ in range(count):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes

    def _hash_backup_codes(self, codes: list[str]) -> str:
        """Hash backup codes with Argon2id and return as JSON string for storage."""
        # Normalize: remove dashes for hashing so users can enter with or without
        normalized = [code.replace("-", "").upper() for code in codes]
        hashed = [hash_password(code) for code in normalized]
        return json.dumps(hashed)

    def _verify_backup_code(
        self, code: str, hashed_codes_json: str
    ) -> tuple[bool, str]:
        """
        Verify a backup code against stored hashes.

        Returns (is_valid, updated_hashed_codes_json_with_used_code_removed).
        Burns the code on successful verification so it cannot be reused.
        """
        normalized = code.replace("-", "").upper()
        hashed_codes: list[str] = json.loads(hashed_codes_json)

        for i, hashed in enumerate(hashed_codes):
            if verify_password(normalized, hashed):
                # Burn the code (remove from list)
                hashed_codes.pop(i)
                return True, json.dumps(hashed_codes)

        return False, hashed_codes_json

    async def _get_user(self, user_id: UUID, tenant_id: UUID) -> User:
        """Load user with tenant_id defense-in-depth filter."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise MFAError("User not found", "user_not_found")
        return user

    async def setup_totp(self, user_id: UUID, tenant_id: UUID) -> dict:
        """
        Begin MFA setup. Generates a TOTP secret and QR code.

        The secret is stored encrypted in user.mfa_setup_pending_secret.
        MFA is NOT enabled until verify_and_enable() is called.

        Returns:
            {
                "secret": "BASE32SECRET...",
                "provisioning_uri": "otpauth://...",
                "qr_code_base64": "data:image/png;base64,...",
                "backup_codes": ["XXXX-XXXX", ...],
            }
        """
        user = await self._get_user(user_id, tenant_id)

        if user.mfa_enabled:
            raise MFAError("MFA is already enabled", "already_enabled")

        # Generate TOTP secret
        secret = pyotp.random_base32()

        # Generate provisioning URI for authenticator apps
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=settings.MFA_ISSUER_NAME,
        )

        # Generate QR code as base64 PNG
        qr = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Generate backup codes
        backup_codes = self._generate_backup_codes()

        # Store encrypted secret and hashed backup codes as pending data.
        # This is NOT moved to mfa_secret until verify_and_enable() succeeds.
        pending_payload = json.dumps(
            {
                "secret": secret,
                "backup_codes_hash": self._hash_backup_codes(backup_codes),
            }
        )
        user.mfa_setup_pending_secret = self._encrypt_secret(pending_payload)
        await self.db.flush()

        logger.info("mfa_setup_started", user_id=str(user_id))

        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code_base64": f"data:image/png;base64,{qr_base64}",
            "backup_codes": backup_codes,
        }

    async def verify_and_enable(
        self, user_id: UUID, tenant_id: UUID, code: str
    ) -> bool:
        """
        Verify a TOTP code from the authenticator app to complete MFA setup.

        On success:
        - Moves secret from mfa_setup_pending_secret to mfa_secret
        - Sets mfa_enabled = True
        - Stores hashed backup codes
        """
        user = await self._get_user(user_id, tenant_id)

        if not user.mfa_setup_pending_secret:
            raise MFAError(
                "No MFA setup in progress. Call /auth/mfa/setup first.",
                "no_pending_setup",
            )

        # Decrypt pending data
        pending_data = json.loads(
            self._decrypt_secret(user.mfa_setup_pending_secret)
        )
        secret = pending_data["secret"]

        # Verify TOTP code (valid_window=1 allows +/- 30 seconds for time skew)
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            raise MFAError("Invalid verification code", "invalid_code")

        # Enable MFA: move secret to permanent storage
        user.mfa_secret = self._encrypt_secret(secret)
        user.mfa_enabled = True
        user.mfa_backup_codes_hash = pending_data["backup_codes_hash"]
        user.mfa_setup_pending_secret = None  # Clear pending
        await self.db.flush()

        logger.info("mfa_enabled", user_id=str(user_id))
        return True

    async def verify_totp(
        self, user_id: UUID, tenant_id: UUID, code: str
    ) -> bool:
        """
        Verify a TOTP code during login.

        Accepts either:
        - 6-digit TOTP code from authenticator app
        - 8-character backup code (with or without dash)

        Backup codes are burned on use (removed from the stored list).
        """
        user = await self._get_user(user_id, tenant_id)
        if not user.mfa_enabled or not user.mfa_secret:
            raise MFAError("MFA is not enabled", "not_enabled")

        normalized_code = code.replace("-", "").strip()

        # Try TOTP first (6 digits)
        if len(normalized_code) == 6 and normalized_code.isdigit():
            secret = self._decrypt_secret(user.mfa_secret)
            totp = pyotp.TOTP(secret)
            if totp.verify(normalized_code, valid_window=1):
                logger.info("mfa_verified_totp", user_id=str(user_id))
                return True

        # Try backup code (8 alphanumeric chars, possibly with dash)
        if user.mfa_backup_codes_hash:
            is_valid, updated_hashes = self._verify_backup_code(
                normalized_code, user.mfa_backup_codes_hash
            )
            if is_valid:
                user.mfa_backup_codes_hash = updated_hashes
                await self.db.flush()
                remaining = len(json.loads(updated_hashes))
                logger.info(
                    "mfa_verified_backup_code",
                    user_id=str(user_id),
                    backup_codes_remaining=remaining,
                )
                return True

        raise MFAError("Invalid verification code", "invalid_code")

    async def disable_mfa(
        self, user_id: UUID, tenant_id: UUID, password: str
    ) -> bool:
        """
        Disable MFA for a user. Requires password confirmation.

        Clears all MFA-related fields.
        """
        user = await self._get_user(user_id, tenant_id)

        if not user.mfa_enabled:
            raise MFAError("MFA is not enabled", "not_enabled")

        # Require password confirmation for security
        if not verify_password(password, user.password_hash):
            raise MFAError("Incorrect password", "invalid_password")

        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_backup_codes_hash = None
        user.mfa_setup_pending_secret = None
        await self.db.flush()

        logger.info("mfa_disabled", user_id=str(user_id))
        return True

    async def regenerate_backup_codes(
        self, user_id: UUID, tenant_id: UUID, password: str
    ) -> list[str]:
        """
        Generate new backup codes. Old codes are invalidated.
        Requires password confirmation.
        """
        user = await self._get_user(user_id, tenant_id)

        if not user.mfa_enabled:
            raise MFAError("MFA is not enabled", "not_enabled")

        if not verify_password(password, user.password_hash):
            raise MFAError("Incorrect password", "invalid_password")

        new_codes = self._generate_backup_codes()
        user.mfa_backup_codes_hash = self._hash_backup_codes(new_codes)
        await self.db.flush()

        logger.info("mfa_backup_codes_regenerated", user_id=str(user_id))
        return new_codes

    async def admin_disable_mfa(
        self,
        target_user_id: UUID,
        tenant_id: UUID,
        admin_user_id: UUID,
    ) -> bool:
        """
        Admin force-disables MFA for a user (e.g., user lost their phone).

        Does NOT require the target user's password (admin override).
        Permission check (users.update) is enforced at the endpoint level.
        """
        user = await self._get_user(target_user_id, tenant_id)

        if not user.mfa_enabled:
            raise MFAError("MFA is not enabled for this user", "not_enabled")

        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_backup_codes_hash = None
        user.mfa_setup_pending_secret = None
        await self.db.flush()

        logger.info(
            "mfa_admin_disabled",
            target_user_id=str(target_user_id),
            admin_user_id=str(admin_user_id),
        )
        return True

    def get_backup_codes_remaining(self, hashed_codes_json: str | None) -> int:
        """Count remaining (un-burned) backup codes."""
        if not hashed_codes_json:
            return 0
        try:
            return len(json.loads(hashed_codes_json))
        except (json.JSONDecodeError, TypeError):
            return 0
