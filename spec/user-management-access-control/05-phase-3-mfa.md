# Phase 3: Multi-Factor Authentication (MFA)

**Complexity:** Large
**Requirements:** UM-004
**Dependencies:** New pip packages (`pyotp`, `qrcode[pil]`)
**Estimated effort:** 3-4 days

---

## Summary

Implement TOTP-based MFA (Time-based One-Time Password, RFC 6238) compatible with Google Authenticator, Authy, and other authenticator apps. Includes 10 one-time backup codes, admin enforcement toggle, and a two-step login flow for MFA-enabled accounts.

---

## Architecture

```
Login Flow (MFA enabled):

  ┌────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Email + │     │ MFA      │     │ Verify   │     │ Issue    │
  │ Password│────▶│ Pending  │────▶│ TOTP     │────▶│ Full     │
  │         │     │ Token    │     │ Code     │     │ Tokens   │
  └────────┘     └──────────┘     └──────────┘     └──────────┘
                  (5-min TTL)       or backup code
```

**Key design points:**
- MFA secrets encrypted at rest with Fernet symmetric encryption
- Backup codes hashed with Argon2id (same as passwords)
- `mfa_pending` token is a short-lived JWT (5 min) that can only be used at the MFA verify endpoint
- School admins can optionally require MFA for admin roles via a school setting

---

## Task 1: Add pip Dependencies

### File: `backend/requirements.txt`

Add:
```
pyotp==2.9.0
qrcode[pil]==7.4.2
```

---

## Task 2: Add Configuration

### File: `backend/app/config.py`

```python
# MFA Configuration
MFA_SECRET_ENCRYPTION_KEY: str = ""  # 32-byte Fernet key (base64-encoded)
MFA_PENDING_TOKEN_EXPIRY_MINUTES: int = 5
MFA_ISSUER_NAME: str = "SIMS Plus"
MFA_BACKUP_CODES_COUNT: int = 10

# IMPORTANT: MFA_SECRET_ENCRYPTION_KEY must be set in production.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Environment variable:** `MFA_SECRET_ENCRYPTION_KEY` — add to `.env.example` with a note that it must be generated for production.

**IMPORTANT:** Add a startup validator that raises an error if `MFA_SECRET_ENCRYPTION_KEY` is empty in production. MFA will silently fail to encrypt/decrypt secrets without this key, which is worse than a loud startup error.

---

## Task 3: Add Model Columns

### File: `backend/app/models/user.py`

**Add near the existing `mfa_enabled` and `mfa_secret` fields:**

```python
# MFA fields (mfa_enabled and mfa_secret already exist)
mfa_backup_codes_hash: Mapped[str | None] = mapped_column(
    Text, nullable=True
)
# JSON-encoded list of Argon2id-hashed backup codes.
# Each code is 8 characters, alphanumeric.
# Codes are burned (removed from list) on use.

mfa_setup_pending_secret: Mapped[str | None] = mapped_column(
    Text, nullable=True
)
# Temporary encrypted TOTP secret during setup flow (uses Text, not String(255),
# because the Fernet-encrypted payload including backup code hashes can exceed 255 chars).
# Stored here until user verifies a code, then moved to mfa_secret.
# Cleared after successful verification or on timeout.
```

**Migration handled in combined migration file (see `07-migration-plan.md`).**

---

## Task 4: Add MFA Enforcement School Setting

### File: `backend/app/models/school.py` (or via `communication_settings` JSONB on schools)

Add to the school's settings/features. The cleanest approach is to use the existing `communication_settings` JSONB column on the `schools` table (or add a new `security_settings` JSONB column):

**Option A (recommended): Use existing features JSONB on the tenant model:**
```python
# In tenants.features JSONB:
{
    "require_mfa_admin_roles": false  # Default: not required
}
```

**Enforcement:** When this is `true`, users with roles `school_admin`, `academic_head`, `finance_officer`, `hr_officer` must complete MFA setup on their next login before they can access the dashboard.

---

## Task 5: Create MFA Service

### New File: `backend/app/services/mfa.py`

```python
"""
TOTP-based Multi-Factor Authentication service.

Uses:
- pyotp for TOTP generation/verification (RFC 6238)
- qrcode for QR code generation
- cryptography.fernet for secret encryption at rest
- argon2 for backup code hashing

MFA Setup Flow:
1. User calls /auth/mfa/setup → receives QR code + backup codes
2. User scans QR with authenticator app
3. User calls /auth/mfa/verify-setup with a code from the app
4. MFA is enabled

MFA Login Flow:
1. User logs in with email + password → receives mfa_pending_token (5 min TTL)
2. User calls /auth/mfa/verify with pending token + TOTP code
3. Full access_token + refresh_token issued
"""

import base64
import io
import json
import secrets
import string
import structlog
from uuid import UUID

import pyotp
import qrcode
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User

logger = structlog.get_logger()


class MFAError(Exception):
    def __init__(self, message: str, code: str = "mfa_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class MFAService:
    """TOTP-based MFA service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._fernet = Fernet(settings.MFA_SECRET_ENCRYPTION_KEY.encode())

    def _encrypt_secret(self, secret: str) -> str:
        """Encrypt TOTP secret for database storage."""
        return self._fernet.encrypt(secret.encode()).decode()

    def _decrypt_secret(self, encrypted: str) -> str:
        """Decrypt TOTP secret from database storage."""
        return self._fernet.decrypt(encrypted.encode()).decode()

    def _generate_backup_codes(self, count: int = None) -> list[str]:
        """
        Generate one-time backup codes.
        Each code: 8 alphanumeric characters, formatted as XXXX-XXXX for readability.
        """
        count = count or settings.MFA_BACKUP_CODES_COUNT
        alphabet = string.ascii_uppercase + string.digits
        # Remove ambiguous characters: 0, O, I, 1, L
        alphabet = alphabet.replace("0", "").replace("O", "").replace("I", "").replace("1", "").replace("L", "")
        codes = []
        for _ in range(count):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes

    def _hash_backup_codes(self, codes: list[str]) -> str:
        """Hash backup codes and return as JSON string for storage."""
        # Normalize: remove dashes for hashing
        normalized = [code.replace("-", "").upper() for code in codes]
        hashed = [hash_password(code) for code in normalized]
        return json.dumps(hashed)

    def _verify_backup_code(self, code: str, hashed_codes_json: str) -> tuple[bool, str]:
        """
        Verify a backup code against stored hashes.
        Returns (is_valid, updated_hashed_codes_json_with_code_removed).
        """
        normalized = code.replace("-", "").upper()
        hashed_codes = json.loads(hashed_codes_json)

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
                "secret": "BASE32SECRET...",          # For manual entry
                "provisioning_uri": "otpauth://...",  # For QR scanning
                "qr_code_base64": "data:image/png;base64,...",
                "backup_codes": ["XXXX-XXXX", ...],   # 10 codes
            }
        """
        user = await self._get_user(user_id, tenant_id)
        if not user:
            raise MFAError("User not found", "user_not_found")

        if user.mfa_enabled:
            raise MFAError("MFA is already enabled", "already_enabled")

        # Generate TOTP secret
        secret = pyotp.random_base32()

        # Generate provisioning URI
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

        # Store encrypted secret and hashed backup codes (pending)
        user.mfa_setup_pending_secret = self._encrypt_secret(
            json.dumps({
                "secret": secret,
                "backup_codes_hash": self._hash_backup_codes(backup_codes),
            })
        )
        await self.db.flush()

        logger.info("mfa_setup_started", user_id=str(user_id))

        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code_base64": f"data:image/png;base64,{qr_base64}",
            "backup_codes": backup_codes,
        }

    async def verify_and_enable(self, user_id: UUID, tenant_id: UUID, code: str) -> bool:
        """
        Verify a TOTP code from the authenticator app to complete MFA setup.

        On success:
        - Moves secret from mfa_setup_pending_secret to mfa_secret
        - Sets mfa_enabled = True
        - Stores hashed backup codes

        Args:
            user_id: User UUID
            tenant_id: Tenant UUID (defense-in-depth)
            code: 6-digit TOTP code from authenticator app

        Returns:
            True on success

        Raises:
            MFAError: If code is invalid or no pending setup exists
        """
        user = await self._get_user(user_id, tenant_id)
        if not user:
            raise MFAError("User not found", "user_not_found")

        if not user.mfa_setup_pending_secret:
            raise MFAError("No MFA setup in progress", "no_pending_setup")

        # Decrypt pending data
        pending_data = json.loads(
            self._decrypt_secret(user.mfa_setup_pending_secret)
        )
        secret = pending_data["secret"]

        # Verify TOTP code
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            raise MFAError("Invalid verification code", "invalid_code")

        # Enable MFA
        user.mfa_secret = self._encrypt_secret(secret)
        user.mfa_enabled = True
        user.mfa_backup_codes_hash = pending_data["backup_codes_hash"]
        user.mfa_setup_pending_secret = None  # Clear pending
        await self.db.flush()

        logger.info("mfa_enabled", user_id=str(user_id))
        return True

    async def verify_totp(self, user_id: UUID, tenant_id: UUID, code: str) -> bool:
        """
        Verify a TOTP code during login.

        Accepts either:
        - 6-digit TOTP code from authenticator app
        - 8-character backup code (with or without dash)

        Returns True on success.
        Raises MFAError on failure.
        """
        user = await self._get_user(user_id, tenant_id)
        if not user.mfa_enabled or not user.mfa_secret:
            raise MFAError("MFA is not enabled", "not_enabled")

        # Try TOTP first (6 digits)
        normalized_code = code.replace("-", "").strip()

        if len(normalized_code) == 6 and normalized_code.isdigit():
            secret = self._decrypt_secret(user.mfa_secret)
            totp = pyotp.TOTP(secret)
            if totp.verify(normalized_code, valid_window=1):
                logger.info("mfa_verified_totp", user_id=str(user_id))
                return True

        # Try backup code (8 alphanumeric chars)
        if user.mfa_backup_codes_hash:
            is_valid, updated_hashes = self._verify_backup_code(
                normalized_code, user.mfa_backup_codes_hash
            )
            if is_valid:
                user.mfa_backup_codes_hash = updated_hashes
                await self.db.flush()
                logger.info("mfa_verified_backup_code", user_id=str(user_id))
                return True

        raise MFAError("Invalid verification code", "invalid_code")

    async def disable_mfa(self, user_id: UUID, tenant_id: UUID, password: str) -> bool:
        """
        Disable MFA for a user. Requires password confirmation.

        Clears: mfa_enabled, mfa_secret, mfa_backup_codes_hash, mfa_setup_pending_secret
        """
        user = await self._get_user(user_id, tenant_id)
            raise MFAError("User not found", "user_not_found")

        if not user.mfa_enabled:
            raise MFAError("MFA is not enabled", "not_enabled")

        # Verify password
        if not verify_password(password, user.hashed_password):
            raise MFAError("Incorrect password", "invalid_password")

        # Disable
        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_backup_codes_hash = None
        user.mfa_setup_pending_secret = None
        await self.db.flush()

        logger.info("mfa_disabled", user_id=str(user_id))
        return True

    async def regenerate_backup_codes(self, user_id: UUID, tenant_id: UUID, password: str) -> list[str]:
        """
        Generate new backup codes. Old codes are invalidated.
        Requires password confirmation.
        """
        user = await self._get_user(user_id, tenant_id)
            raise MFAError("User not found", "user_not_found")

        if not user.mfa_enabled:
            raise MFAError("MFA is not enabled", "not_enabled")

        if not verify_password(password, user.hashed_password):
            raise MFAError("Incorrect password", "invalid_password")

        new_codes = self._generate_backup_codes()
        user.mfa_backup_codes_hash = self._hash_backup_codes(new_codes)
        await self.db.flush()

        logger.info("mfa_backup_codes_regenerated", user_id=str(user_id))
        return new_codes

    async def admin_disable_mfa(self, target_user_id: UUID, tenant_id: UUID, admin_user_id: UUID) -> bool:
        """
        Admin force-disables MFA for a user (e.g., user lost their phone).
        Requires users.update permission (checked at endpoint level).
        """
        user = await self._get_user(target_user_id, tenant_id)
            raise MFAError("User not found", "user_not_found")

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
```

---

## Task 6: Create MFA Schemas

### New File: `backend/app/schemas/mfa.py`

```python
"""Pydantic schemas for MFA endpoints."""

from pydantic import BaseModel, Field, field_validator


class MFASetupResponse(BaseModel):
    """Response from MFA setup initiation."""
    secret: str                    # Base32 secret for manual entry
    provisioning_uri: str          # otpauth:// URI for QR code
    qr_code_base64: str            # data:image/png;base64,... for display
    backup_codes: list[str]        # 10 one-time backup codes (XXXX-XXXX format)


class MFAVerifySetupRequest(BaseModel):
    """Request to verify MFA setup with a TOTP code from authenticator app."""
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit code from authenticator app",
    )

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v


class MFAVerifyLoginRequest(BaseModel):
    """Request to verify MFA during login flow."""
    mfa_pending_token: str = Field(
        ...,
        description="Token received from initial login attempt",
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=9,  # 6 digits for TOTP or 8-9 chars for backup code (with dash)
        description="TOTP code or backup code",
    )


class MFADisableRequest(BaseModel):
    """Request to disable MFA. Requires password confirmation."""
    password: str = Field(
        ...,
        min_length=1,
        description="Current password for confirmation",
    )


class MFABackupCodesResponse(BaseModel):
    """Response containing newly generated backup codes."""
    backup_codes: list[str]


class MFAStatusResponse(BaseModel):
    """MFA status for the current user."""
    mfa_enabled: bool
    backup_codes_remaining: int | None = None  # None if MFA not enabled
```

---

## Task 7: Modify Login Flow

### File: `backend/app/services/auth.py`

**Modify the `authenticate()` method to check for MFA after password verification:**

```python
# After successful password verification, BEFORE issuing tokens:

if user.mfa_enabled:
    # Generate a short-lived MFA pending token
    mfa_pending_token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "type": "mfa_pending",   # CRITICAL: token type marker
        },
        expires_delta=timedelta(minutes=settings.MFA_PENDING_TOKEN_EXPIRY_MINUTES),
    )

    # Return MFA required response (NOT an exception — a normal response)
    return {
        "mfa_required": True,
        "mfa_pending_token": mfa_pending_token,
    }

# If MFA not enabled, continue with normal token issuance...
```

**Modify the login endpoint handler** to detect and return the MFA response:

```python
# In the login endpoint:
result = await auth_service.authenticate(email, password, ...)

if isinstance(result, dict) and result.get("mfa_required"):
    return JSONResponse(
        status_code=200,
        content={
            "mfa_required": True,
            "mfa_pending_token": result["mfa_pending_token"],
        },
    )

# Otherwise, return normal login response...
```

**Create a SEPARATE MFARequiredResponse schema** (do NOT modify existing LoginResponse — avoids breaking existing API consumers):

```python
class MFARequiredResponse(BaseModel):
    """Returned when login succeeds but MFA verification is needed."""
    mfa_required: bool = True
    mfa_pending_token: str
```

The login endpoint returns `JSONResponse` with MFARequiredResponse content when MFA is needed:

```python
if isinstance(result, dict) and result.get("mfa_required"):
    return JSONResponse(
        status_code=200,
        content=MFARequiredResponse(
            mfa_pending_token=result["mfa_pending_token"],
        ).model_dump(),
    )
```

**NOTE:** The existing `type != "access"` check in `get_current_user_id` already rejects `mfa_pending` tokens at all other endpoints (defense-in-depth).

---

## Task 8: Add MFA Endpoints

### File: `backend/app/api/v1/endpoints/auth.py`

#### Setup MFA

```python
@router.post(
    "/mfa/setup",
    summary="Begin MFA setup — get QR code and backup codes",
    response_model=MFASetupResponse,
    # NOTE: No require_permissions("self.update") — "self.update" doesn't exist
    # in ROLE_PERMISSIONS. CurrentUserId dependency is sufficient auth.
)
async def mfa_setup(
    current_user_id: CurrentUserId,
    db: DatabaseSession,
):
    """
    Start TOTP MFA setup. Returns QR code for scanning with an
    authenticator app and 10 one-time backup codes.

    MFA is NOT active until /auth/mfa/verify-setup is called.
    """
    mfa_service = MFAService(db)
    try:
        return await mfa_service.setup_totp(current_user_id)
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

#### Verify MFA Setup

```python
@router.post(
    "/mfa/verify-setup",
    summary="Verify TOTP code to complete MFA setup",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mfa_verify_setup(
    data: MFAVerifySetupRequest,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    request: Request,
):
    """
    Complete MFA setup by verifying a TOTP code from the authenticator app.
    On success, MFA is enabled for the account.
    """
    mfa_service = MFAService(db)
    try:
        await mfa_service.verify_and_enable(current_user_id, tenant_id=..., code=data.code)
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_ENABLED,
        tenant_id=...,  # from current user context
        user_id=current_user_id,
        target_type="user",
        target_id=str(current_user_id),
        details={},
    )
```

#### Verify MFA During Login

```python
@router.post(
    "/mfa/verify",
    summary="Verify MFA code during login",
)
async def mfa_verify_login(
    data: MFAVerifyLoginRequest,
    request: Request,
    db: DatabaseSession,
):
    """
    Second step of MFA login flow. Verifies the TOTP code (or backup code)
    and issues full access + refresh tokens.

    The mfa_pending_token is a short-lived JWT (5 min) that can ONLY be
    used at this endpoint.
    """
    # 1. Validate mfa_pending_token
    try:
        payload = decode_token(data.mfa_pending_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA token")

    # CRITICAL: Verify token type
    if payload.get("type") != "mfa_pending":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tenant_id"])

    # Cross-tenant validation: ensure mfa_pending_token's tenant matches request
    request_tenant_id = getattr(request.state, "tenant_id", None)
    if request_tenant_id and str(tenant_id) != str(request_tenant_id):
        raise HTTPException(status_code=403, detail="Token not valid for this school")

    # MFA brute-force protection: track failed attempts per mfa_pending_token
    redis = request.app.state.redis
    mfa_attempts_key = f"mfa_attempts:{data.mfa_pending_token[:32]}"
    attempts = int(await redis.get(mfa_attempts_key) or "0")
    if attempts >= 5:
        raise HTTPException(status_code=429, detail="Too many failed MFA attempts. Please log in again.")

    # 2. Verify TOTP/backup code
    mfa_service = MFAService(db)
    try:
        await mfa_service.verify_totp(user_id, tenant_id, data.code)
    except MFAError as e:
        # Increment brute-force counter on failure
        pipe = redis.pipeline()
        pipe.incr(mfa_attempts_key)
        pipe.expire(mfa_attempts_key, 300)  # 5 min TTL matching pending token
        await pipe.execute()
        raise HTTPException(status_code=401, detail=e.message)

    # Blacklist the mfa_pending_token after successful use (one-time use)
    await redis.setex(f"mfa_used:{data.mfa_pending_token[:32]}", 300, "1")

    # 3. Load user and issue full tokens
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Issue tokens using the existing token creation logic
    # (same as the normal login flow after password verification)
    access_token = create_access_token(...)
    refresh_token = create_refresh_token(...)

    # 4. Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_VERIFIED,
        tenant_id=tenant_id,
        user_id=user_id,
        target_type="user",
        target_id=str(user_id),
        details={},
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=...,
    )
```

#### Disable MFA

```python
@router.post(
    "/mfa/disable",
    summary="Disable MFA (requires password)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mfa_disable(
    data: MFADisableRequest,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    request: Request,
):
    mfa_service = MFAService(db)
    try:
        await mfa_service.disable_mfa(current_user_id, tenant_id=..., password=data.password)
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_DISABLED,
        tenant_id=...,  # from current user context
        user_id=current_user_id,
        target_type="user",
        target_id=str(current_user_id),
        details={"method": "self_disable"},
    )
```

#### Regenerate Backup Codes

```python
@router.post(
    "/mfa/backup-codes",
    summary="Regenerate MFA backup codes (requires password)",
    response_model=MFABackupCodesResponse,
)
async def mfa_regenerate_backup_codes(
    data: MFADisableRequest,  # Reuse — both just need password
    current_user_id: CurrentUserId,
    db: DatabaseSession,
):
    mfa_service = MFAService(db)
    try:
        codes = await mfa_service.regenerate_backup_codes(current_user_id, data.password)
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    return MFABackupCodesResponse(backup_codes=codes)
```

#### Admin Force-Disable MFA

**NOTE:** This endpoint belongs on the **users router** (`backend/app/api/v1/endpoints/users.py`), NOT the auth router. Path: `DELETE /api/v1/users/{user_id}/mfa`

```python
# In backend/app/api/v1/endpoints/users.py:
@router.delete(
    "/{user_id}/mfa",
    summary="Admin: force-disable MFA for a user",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("users.update"))],
)
async def admin_disable_user_mfa(
    user_id: UUID,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    db: DatabaseSession,
    request: Request,
):
    """Force-disable MFA for a user (e.g., lost phone). Admin only."""
    mfa_service = MFAService(db)
    try:
        await mfa_service.admin_disable_mfa(
            user_id,
            tenant_id=UUID(tenant.tenant_id),
            admin_user_id=UUID(current_user["user_id"]),
        )
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_DISABLED,
        tenant_id=UUID(tenant.tenant_id),
        user_id=UUID(current_user["user_id"]),
        target_type="user",
        target_id=str(user_id),
        details={"action": "admin_force_disable"},
    )
```

---

## Task 9: Ensure mfa_pending Token Is Rejected Everywhere Else

### File: `backend/app/api/deps.py`

In the `get_current_user_id` dependency (or equivalent), add a check:

```python
# After decoding the token:
if payload.get("type") == "mfa_pending":
    raise HTTPException(
        status_code=401,
        detail="MFA verification required",
    )
```

This ensures the `mfa_pending` token can ONLY be used at `/auth/mfa/verify`.

---

## Task 10: Frontend — MFA Setup in Account Settings

### File: `frontend/app/(dashboard)/settings/account/account-settings-form.tsx`

**Replace the "Coming soon" placeholder** with a functional MFA section:

**When MFA is disabled:**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Two-Factor Authentication</CardTitle>
    <CardDescription>
      Add an extra layer of security to your account using an authenticator app.
    </CardDescription>
  </CardHeader>
  <CardContent>
    <Button onClick={() => setMfaSetupOpen(true)}>
      Enable 2FA
    </Button>
  </CardContent>
</Card>
```

**When MFA is enabled:**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Two-Factor Authentication</CardTitle>
    <Badge variant="success">Enabled</Badge>
  </CardHeader>
  <CardContent className="space-y-3">
    <Button variant="outline" onClick={() => setBackupCodesOpen(true)}>
      Regenerate Backup Codes
    </Button>
    <Button variant="destructive" onClick={() => setDisableMfaOpen(true)}>
      Disable 2FA
    </Button>
  </CardContent>
</Card>
```

---

## Task 11: Frontend — MFA Setup Dialog

### New File: `frontend/components/mfa/mfa-setup-dialog.tsx`

**3-step wizard dialog:**

1. **Step 1: QR Code**
   - Display QR code image (from base64)
   - Show manual entry secret (copyable)
   - "Next" button

2. **Step 2: Verify**
   - 6-digit code input
   - "Verify" button
   - Error state for invalid codes

3. **Step 3: Backup Codes**
   - Display all 10 backup codes
   - "Download as text file" button
   - "Copy to clipboard" button
   - Checkbox: "I have saved these codes"
   - "Done" button (only enabled when checkbox is checked)

---

## Task 12: Frontend — MFA Login Step

### File: `frontend/app/(auth)/login/page.tsx`

**After successful email/password submission, check the response:**

```typescript
const result = await login(email, password);

if (result.success && result.data?.mfa_required) {
  // Show MFA verification step
  setMfaPendingToken(result.data.mfa_pending_token);
  setShowMfaStep(true);
  return;
}
```

**MFA verification UI (shown when `showMfaStep` is true):**

```tsx
{showMfaStep && (
  <div className="space-y-4">
    <h2>Two-Factor Authentication</h2>
    <p className="text-sm text-muted-foreground">
      Enter the 6-digit code from your authenticator app
    </p>

    <InputOTP maxLength={6} value={mfaCode} onChange={setMfaCode} />

    <Button onClick={handleMfaVerify}>Verify</Button>

    <button
      className="text-sm text-muted-foreground underline"
      onClick={() => setUseBackupCode(!useBackupCode)}
    >
      {useBackupCode ? "Use authenticator code" : "Use a backup code"}
    </button>

    {useBackupCode && (
      <Input
        placeholder="XXXX-XXXX"
        value={backupCode}
        onChange={(e) => setBackupCode(e.target.value)}
        maxLength={9}
      />
    )}

    <p className="text-xs text-muted-foreground">
      Token expires in 5 minutes
    </p>
  </div>
)}
```

---

## Task 13: Frontend — Server Actions

### New File: `frontend/actions/mfa.action.ts`

```typescript
"use server";

import { apiPost, apiDelete } from "@/lib/api";
import type { ActionResult } from "@/types";

export interface MFASetupData {
  secret: string;
  provisioning_uri: string;
  qr_code_base64: string;
  backup_codes: string[];
}

export async function setupMFA(): Promise<ActionResult<MFASetupData>> {
  try {
    const response = await apiPost<MFASetupData>("/auth/mfa/setup", {});
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "MFA setup failed",
    };
  }
}

export async function verifyMFASetup(code: string): Promise<ActionResult> {
  try {
    await apiPost("/auth/mfa/verify-setup", { code });
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Verification failed",
    };
  }
}

export async function verifyMFALogin(data: {
  mfa_pending_token: string;
  code: string;
}): Promise<ActionResult<LoginResponse>> {
  try {
    const response = await apiPost<LoginResponse>("/auth/mfa/verify", data);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "MFA verification failed",
    };
  }
}

export async function disableMFA(password: string): Promise<ActionResult> {
  try {
    await apiPost("/auth/mfa/disable", { password });
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to disable MFA",
    };
  }
}

export async function regenerateBackupCodes(
  password: string,
): Promise<ActionResult<{ backup_codes: string[] }>> {
  try {
    const response = await apiPost<{ backup_codes: string[] }>(
      "/auth/mfa/backup-codes",
      { password },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to regenerate codes",
    };
  }
}
```

---

## Task 14: MFA Enforcement for Admin Roles (Optional Toggle)

**When `tenants.features.require_mfa_admin_roles` is `true`:**

After login (and MFA verification if already enabled), check if the user's role requires MFA and MFA is not yet set up. If so, redirect to a mandatory MFA setup page.

### Frontend: MFA Required Guard

```tsx
// In dashboard layout or a guard component:
if (
  tenant.features?.require_mfa_admin_roles &&
  ["school_admin", "academic_head", "finance_officer", "hr_officer"].includes(user.role) &&
  !user.mfa_enabled
) {
  redirect("/settings/account?setup_mfa=required");
}
```

On the account settings page, detect `setup_mfa=required` query param and auto-open the MFA setup dialog with a non-dismissible overlay.

### Backend: Add School Settings Endpoint

Add `require_mfa_admin_roles` to the tenant features JSONB. This can be toggled via the existing school settings or a new security settings endpoint:

```python
@router.put("/security-settings")
async def update_security_settings(
    data: SecuritySettingsUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
):
    """Update security settings (MFA enforcement, etc.)."""
    tenant_obj = await db.get(Tenant, UUID(tenant.tenant_id))
    if not tenant_obj.features:
        tenant_obj.features = {}
    tenant_obj.features["require_mfa_admin_roles"] = data.require_mfa_admin_roles
    await db.flush()
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| TOTP secret exposure | Encrypted at rest with Fernet; never returned after setup |
| Backup code brute force | Hashed with Argon2id; 8-char codes = 2.8 trillion combinations |
| mfa_pending token misuse | `type: "mfa_pending"` checked; rejected by all other endpoints |
| mfa_pending token expiry | 5-minute TTL; short window for attacks |
| Lost phone recovery | Admin force-disable + backup codes (10 codes) |
| TOTP time skew | `valid_window=1` allows +/- 30 seconds |
| QR code interception | Shown only in HTTPS session; one-time setup flow |

---

## Verification Checklist

- [ ] MFA setup generates valid QR code scannable by Google Authenticator
- [ ] Manual secret entry works in authenticator apps
- [ ] TOTP codes verify correctly (6-digit, with ±30s window)
- [ ] MFA is NOT enabled until verify-setup succeeds
- [ ] Login returns `mfa_required: true` for MFA-enabled users
- [ ] `mfa_pending_token` expires after 5 minutes
- [ ] `mfa_pending_token` rejected by all endpoints except /auth/mfa/verify
- [ ] Backup codes work (8-char, one-time use)
- [ ] Used backup codes cannot be reused
- [ ] Backup code count decreases after each use
- [ ] MFA disable requires password confirmation
- [ ] Admin can force-disable user's MFA
- [ ] Regenerated backup codes invalidate old ones
- [ ] MFA secrets encrypted in database (not plaintext)
- [ ] Audit events logged for: enable, disable, verify, admin-disable, backup-regen
- [ ] MFA enforcement redirect works when tenant setting is enabled
- [ ] Frontend MFA login step shows correctly after password step
