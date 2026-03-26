# Phase 1B: OTP Service + Phone Verification + SMS Password Reset

**Complexity:** Medium
**Requirements:** UM-001 (phone verification), UM-003 (SMS OTP password reset)
**Dependencies:** Arkesel SMS client (`backend/app/services/messaging/arkesel_client.py`) — see [09-arkesel-sms-migration.md](09-arkesel-sms-migration.md)
**Estimated effort:** 2-3 days

---

## Summary

Implement a shared OTP (One-Time Password) service that powers two features:
1. Phone number verification for user accounts
2. SMS-based password reset (alternative to email)

Both features use the Arkesel SMS client for delivery and Redis for OTP storage.

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Auth        │     │  OTP         │     │  Arkesel     │
│  Endpoints   │────▶│  Service     │────▶│  Client      │────▶ SMS
│  (FastAPI)   │     │  (Redis)     │     │  (existing)  │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                     ┌──────▼──────┐
                     │   Redis     │
                     │  (OTP keys) │
                     └─────────────┘
```

**Key design points:**
- OTP is hashed (SHA-256) before Redis storage (defense-in-depth against Redis data leak)
- Redis keys are tenant-scoped to prevent cross-tenant OTP reuse
- Rate limit: 1 OTP per phone per minute, max 5 verification attempts per OTP
- Phone numbers should be normalized before storage/lookup

---

## Task 1: Create OTP Service

### New File: `backend/app/services/otp.py`

```python
"""
OTP (One-Time Password) service for phone-based verification flows.

Used by:
- Phone number verification (UM-001)
- SMS password reset (UM-003)

OTPs are:
- 6 digits, randomly generated
- Hashed (SHA-256) before Redis storage
- Scoped by tenant_id to prevent cross-tenant reuse
- Rate-limited: 1 OTP per phone per minute
- Max 5 verification attempts per OTP
- 10-minute expiry
"""

import hashlib
import secrets
import structlog
from enum import Enum
from uuid import UUID

from app.services.messaging.arkesel_client import ArkeselClient

logger = structlog.get_logger()

# Module-level singleton — avoids creating a new client per OTP send
_sms_client = ArkeselClient()


class OTPPurpose(str, Enum):
    PHONE_VERIFICATION = "phone_verify"
    PASSWORD_RESET = "password_reset"


class OTPError(Exception):
    """OTP operation error with machine-readable code."""

    def __init__(self, message: str, code: str = "otp_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class OTPService:
    """OTP generation, storage (Redis), and verification."""

    OTP_LENGTH = 6
    OTP_EXPIRY_SECONDS = 600        # 10 minutes
    MAX_ATTEMPTS = 5
    RATE_LIMIT_SECONDS = 60         # 1 OTP per phone per minute

    def __init__(self, redis_client):
        """
        Args:
            redis_client: Redis client from request.app.state.redis
                          (must have decode_responses=True)
        """
        self.redis = redis_client

    def _key(self, purpose: OTPPurpose, tenant_id: UUID, phone: str, suffix: str) -> str:
        """
        Generate tenant-scoped Redis key.

        Format: otp:{purpose}:{tenant_id}:{phone}:{suffix}
        Suffixes: code, attempts, rate
        """
        return f"otp:{purpose.value}:{tenant_id}:{phone}:{suffix}"

    def _hash_otp(self, otp: str) -> str:
        """Hash OTP with SHA-256 for storage. NOT for passwords — just for OTP defense-in-depth."""
        return hashlib.sha256(otp.encode()).hexdigest()

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Normalize phone number: strip spaces/dashes and convert local
        Ghana format (0XX) to international (+233XX).
        """
        phone = phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("0") and len(phone) == 10:
            phone = "+233" + phone[1:]
        return phone

    async def generate_and_send(
        self,
        phone: str,
        purpose: OTPPurpose,
        tenant_id: UUID,
        school_name: str = "SIMS Plus",
    ) -> bool:
        """
        Generate a 6-digit OTP, store hashed in Redis, send via Arkesel SMS.

        Args:
            phone: Recipient phone number (will be normalized, e.g., +233241234567)
            purpose: What the OTP is for (phone_verify or password_reset)
            tenant_id: Current tenant UUID (for key scoping)
            school_name: School name for SMS message personalization

        Returns:
            True if OTP was sent successfully.

        Raises:
            OTPError("rate_limited"): If OTP was requested within the last 60 seconds
            OTPError("send_failed"): If SMS sending failed
        """
        phone = self._normalize_phone(phone)

        # 1. Check rate limit
        rate_key = self._key(purpose, tenant_id, phone, "rate")
        if await self.redis.exists(rate_key):
            raise OTPError(
                "Please wait before requesting another code",
                "rate_limited",
            )

        # 2. Generate OTP (cryptographically random)
        otp = "".join([str(secrets.randbelow(10)) for _ in range(self.OTP_LENGTH)])

        # 3. Store hashed OTP + attempts counter in Redis
        code_key = self._key(purpose, tenant_id, phone, "code")
        attempts_key = self._key(purpose, tenant_id, phone, "attempts")

        pipe = self.redis.pipeline()
        pipe.setex(code_key, self.OTP_EXPIRY_SECONDS, self._hash_otp(otp))
        pipe.setex(attempts_key, self.OTP_EXPIRY_SECONDS, "0")
        pipe.setex(rate_key, self.RATE_LIMIT_SECONDS, "1")
        await pipe.execute()

        # 4. Send SMS via Arkesel (module-level singleton, not per-call)
        if purpose == OTPPurpose.PHONE_VERIFICATION:
            message = f"Your {school_name} phone verification code is: {otp}. Valid for 10 minutes."
        else:
            message = f"Your {school_name} password reset code is: {otp}. Valid for 10 minutes. If you did not request this, ignore this message."

        try:
            await _sms_client.send_sms(phone, message)

            logger.info(
                "otp_sent",
                purpose=purpose.value,
                tenant_id=str(tenant_id),
                phone_last4=phone[-4:],
            )
            return True

        except Exception as e:
            # Clean up Redis keys on send failure (don't lock user out)
            await self.redis.delete(code_key, attempts_key, rate_key)
            logger.error(
                "otp_send_failed",
                purpose=purpose.value,
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise OTPError("Failed to send verification code", "send_failed")

    async def verify(
        self,
        phone: str,
        code: str,
        purpose: OTPPurpose,
        tenant_id: UUID,
    ) -> bool:
        """
        Verify an OTP code.

        Increments attempt counter on failure. Deletes all keys on success.

        Args:
            phone: Phone number the OTP was sent to
            code: 6-digit code entered by user
            purpose: Must match the purpose used during generation
            tenant_id: Must match the tenant used during generation

        Returns:
            True if code is valid.

        Raises:
            OTPError("expired"): If no OTP exists for this phone/purpose
            OTPError("max_attempts"): If 5 failed attempts have been made
            OTPError("invalid"): If the code is wrong
        """
        phone = self._normalize_phone(phone)

        code_key = self._key(purpose, tenant_id, phone, "code")
        attempts_key = self._key(purpose, tenant_id, phone, "attempts")

        # 1. Check if OTP exists
        stored_hash = await self.redis.get(code_key)
        if not stored_hash:
            raise OTPError(
                "Verification code expired or not found",
                "expired",
            )

        # 2. Check attempt count
        attempts = int(await self.redis.get(attempts_key) or "0")
        if attempts >= self.MAX_ATTEMPTS:
            # Clean up — force user to request a new OTP
            await self.redis.delete(code_key, attempts_key)
            raise OTPError(
                "Too many failed attempts. Please request a new code.",
                "max_attempts",
            )

        # 3. Verify hash
        if self._hash_otp(code) != stored_hash:
            await self.redis.incr(attempts_key)
            remaining = self.MAX_ATTEMPTS - attempts - 1
            logger.info(
                "otp_verify_failed",
                purpose=purpose.value,
                tenant_id=str(tenant_id),
                phone_last4=phone[-4:],
                attempts_remaining=remaining,
            )
            raise OTPError("Invalid verification code", "invalid")

        # 4. Success — clean up all keys
        rate_key = self._key(purpose, tenant_id, phone, "rate")
        await self.redis.delete(code_key, attempts_key, rate_key)

        logger.info(
            "otp_verified",
            purpose=purpose.value,
            tenant_id=str(tenant_id),
            phone_last4=phone[-4:],
        )
        return True
```

---

## Task 2: Create OTP Schemas

### New File: `backend/app/schemas/otp.py`

```python
"""Pydantic schemas for OTP-based flows (phone verification, SMS password reset)."""

import re
from pydantic import BaseModel, Field, field_validator

# NOTE: These schemas should extend the project's BaseSchema pattern if one exists.
# Check backend/app/schemas/ for a common base class before implementation.
# Using raw BaseModel here for clarity.


class SendPhoneOTPResponse(BaseModel):
    """Response after sending a phone verification OTP."""
    message: str = "Verification code sent"


class VerifyPhoneRequest(BaseModel):
    """Request to verify phone number with OTP."""
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit verification code",
    )

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v


class ForgotPasswordSMSRequest(BaseModel):
    """Request to initiate SMS-based password reset."""
    phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Phone number in international format (e.g., +233241234567)",
    )


class ResetPasswordSMSRequest(BaseModel):
    """Request to reset password using SMS OTP."""
    phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Phone number that received the OTP",
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit verification code",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (must meet complexity requirements)",
    )

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Use the shared password validator from schemas/auth.py."""
        from app.schemas.auth import validate_password_strength
        return validate_password_strength(v)
```

---

## Task 3: Add Phone Verification Columns to User Model

### File: `backend/app/models/user.py`

**Add near the existing `email_verified` fields (around line 111-114):**

```python
# Phone verification
phone_verified: Mapped[bool] = mapped_column(
    Boolean, default=False, server_default="false"
)
phone_verified_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

**Migration handled in combined migration file (see `07-migration-plan.md`).**

---

## Task 4: Add Phone Verification Endpoints

### File: `backend/app/api/v1/endpoints/auth.py`

Add these endpoints to the existing auth router. Read the file first to understand the existing patterns for dependencies (`ValidatedUser`, `DatabaseSession`, `Request`, etc.).

#### Endpoint 1: Send Phone OTP

```python
@router.post(
    "/send-phone-otp",
    summary="Send OTP to user's phone for verification",
    response_model=SendPhoneOTPResponse,
)
async def send_phone_otp(
    request: Request,
    current_user_id: CurrentUserId,    # Use existing dependency name
    db: DatabaseSession,               # Use existing dependency alias
    _: ValidatedTokenTenant,           # Cross-tenant token validation
):
    """
    Send a 6-digit OTP to the authenticated user's registered phone number.

    Requirements:
    - User must be authenticated (JWT required)
    - User must have a phone number on their profile
    - Rate limited: 1 OTP per minute
    """
    # 1. Get user from DB
    user = await db.get(User, current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Check phone number exists
    if not user.phone:
        raise HTTPException(
            status_code=400,
            detail="No phone number on your profile. Update your profile first.",
        )

    # 3. Get school name for message personalization
    # Query the school for this tenant to get the name
    school = await db.execute(
        select(School).where(School.tenant_id == user.tenant_id).limit(1)
    )
    school_obj = school.scalar_one_or_none()
    school_name = school_obj.name if school_obj else "SIMS Plus"

    # 4. Send OTP
    redis = request.app.state.redis
    otp_service = OTPService(redis)
    try:
        await otp_service.generate_and_send(
            phone=user.phone,
            purpose=OTPPurpose.PHONE_VERIFICATION,
            tenant_id=user.tenant_id,
            school_name=school_name,
        )
    except OTPError as e:
        raise HTTPException(status_code=429 if e.code == "rate_limited" else 500, detail=e.message)

    return SendPhoneOTPResponse()
```

#### Endpoint 2: Verify Phone

```python
@router.post(
    "/verify-phone",
    summary="Verify phone number with OTP code",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def verify_phone(
    data: VerifyPhoneRequest,
    request: Request,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    _: ValidatedTokenTenant,           # Cross-tenant token validation
):
    """
    Verify the authenticated user's phone number using a 6-digit OTP.

    On success:
    - Sets user.phone_verified = True
    - Sets user.phone_verified_at to current timestamp
    - Logs audit event
    """
    # 1. Get user
    user = await db.get(User, current_user_id)
    if not user or not user.phone:
        raise HTTPException(status_code=400, detail="No phone number to verify")

    # 2. Verify OTP
    redis = request.app.state.redis
    otp_service = OTPService(redis)
    try:
        await otp_service.verify(
            phone=user.phone,
            code=data.code,
            purpose=OTPPurpose.PHONE_VERIFICATION,
            tenant_id=user.tenant_id,
        )
    except OTPError as e:
        status_code = 429 if e.code == "max_attempts" else 400
        raise HTTPException(status_code=status_code, detail=e.message)

    # 3. Update user
    user.phone_verified = True
    user.phone_verified_at = datetime.now(timezone.utc)
    await db.flush()

    # 4. Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ACCOUNT_ACTIVATED,
        tenant_id=user.tenant_id,
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        details={"action": "phone_verified"},
    )
```

#### Endpoint 3: Forgot Password via SMS

```python
@router.post(
    "/forgot-password-sms",
    summary="Request password reset via SMS OTP",
)
async def forgot_password_sms(
    data: ForgotPasswordSMSRequest,
    request: Request,
    db: DatabaseSession,   # NOTE: Use tenant-scoped DB (tenant comes from subdomain middleware)
):
    """
    Send a password reset OTP to the provided phone number.

    IMPORTANT: Always returns a generic success message regardless of whether
    the phone number exists. This prevents phone number enumeration attacks.

    Flow:
    1. Look up user by phone number within the current tenant
    2. If found and active, send OTP
    3. If not found, still return success (prevent enumeration)
    """
    # Generic response (always the same)
    response = {"message": "If an account with this phone number exists, a verification code has been sent."}

    # Get tenant_id from request state (set by TenantMiddleware)
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return response  # No tenant context = no user lookup possible

    # Look up user by phone
    result = await db.execute(
        select(User).where(
            User.phone == data.phone,
            User.tenant_id == UUID(tenant_id),
            User.deleted_at.is_(None),
            User.status.in_(["active", "pending"]),  # Don't send to suspended/deactivated
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        return response  # Don't reveal whether phone exists

    # Send OTP
    redis = request.app.state.redis
    otp_service = OTPService(redis)
    try:
        # Get school name
        school_result = await db.execute(
            select(School).where(School.tenant_id == user.tenant_id).limit(1)
        )
        school = school_result.scalar_one_or_none()
        school_name = school.name if school else "SIMS Plus"

        await otp_service.generate_and_send(
            phone=data.phone,
            purpose=OTPPurpose.PASSWORD_RESET,
            tenant_id=user.tenant_id,
            school_name=school_name,
        )
    except OTPError:
        pass  # Silently fail — don't reveal anything to the caller

    # Audit log (only if user found — but response is always the same)
    try:
        from app.services.audit import AuditService, AuditEventType
        audit = AuditService(db)
        await audit.log(
            event_type=AuditEventType.PASSWORD_RESET_REQUESTED,
            tenant_id=user.tenant_id,
            user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            details={"method": "sms"},
        )
    except Exception:
        pass  # Audit failure must not affect response

    return response
```

#### Endpoint 4: Reset Password via SMS

```python
@router.post(
    "/reset-password-sms",
    summary="Reset password using phone number and OTP code",
)
async def reset_password_sms(
    data: ResetPasswordSMSRequest,
    request: Request,
    db: DatabaseSession,
):
    """
    Reset password using phone + OTP.

    Flow:
    1. Verify OTP for the phone number FIRST (prevents timing side-channel
       that leaks phone existence — OTP verify is constant-time)
    2. Look up user by phone
    3. Update password hash
    4. Blacklist all existing tokens
    5. Audit log
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid request")

    # 1. Verify OTP FIRST — prevents timing side-channel that leaks phone existence
    redis = request.app.state.redis
    otp_service = OTPService(redis)
    try:
        await otp_service.verify(
            phone=data.phone,
            code=data.code,
            purpose=OTPPurpose.PASSWORD_RESET,
            tenant_id=UUID(tenant_id),
        )
    except OTPError as e:
        status_code = 429 if e.code == "max_attempts" else 400
        raise HTTPException(status_code=status_code, detail=e.message)

    # 2. Look up user by phone (only after OTP is verified)
    result = await db.execute(
        select(User).where(
            User.phone == data.phone,
            User.tenant_id == UUID(tenant_id),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid phone number or code")

    # 3. Update password
    from app.core.security import hash_password
    user.password_hash = hash_password(data.new_password)

    # Activate pending users on password reset (same as email reset)
    # NOTE: Import UserStatus from app.models.user if not already imported
    from app.models.user import UserStatus
    if user.status == UserStatus.PENDING:
        user.status = UserStatus.ACTIVE

    await db.flush()

    # 4. Blacklist all existing tokens for this user
    from app.services.token_blacklist import TokenBlacklistService
    blacklist = TokenBlacklistService(redis)
    await blacklist.blacklist_user_tokens(str(user.id))

    # 5. Audit log
    from app.services.audit import AuditService, AuditEventType
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.PASSWORD_RESET_COMPLETED,
        tenant_id=user.tenant_id,
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        details={"method": "sms"},
    )

    return {"message": "Password reset successful. Please log in with your new password."}
```

---

## Task 5: Add Phone Verification Routes to PUBLIC_PATH_PREFIXES

### File: `backend/app/middleware/tenant.py`

The `forgot-password-sms` and `reset-password-sms` endpoints are unauthenticated but still need tenant context (from subdomain). Check how the existing `forgot-password` and `reset-password` endpoints handle this.

**These endpoints should NOT be added to PUBLIC_PATH_PREFIXES** — they need tenant context from the subdomain middleware. The existing auth endpoints already work this way (they're under `/api/v1/auth/` which is handled by the tenant middleware normally).

### File: `backend/app/api/deps.py`

Verify that the auth endpoints that don't require JWT (forgot-password-sms, reset-password-sms) use `get_db` (tenant-scoped) rather than `get_unscoped_db`. The tenant context comes from the subdomain middleware, and the DB session will be tenant-scoped.

**IMPORTANT:** Verify that `/api/v1/auth/forgot-password-sms` and `/api/v1/auth/reset-password-sms` do not collide with existing `PUBLIC_PATH_PREFIXES`. In particular, check that the existing prefix for `/api/v1/auth/reset-password` does not accidentally match `/api/v1/auth/reset-password-sms` via prefix matching. If `_PUBLIC_PATH_PREFIXES` uses exact path matching (not startswith), this is fine. If it uses startswith, the SMS variants are already covered.

---

## Task 6: Frontend — Phone Verification in Account Settings

### File: `frontend/app/(dashboard)/settings/account/account-settings-form.tsx`

**Add a "Phone Verification" card** between the existing password section and the MFA section.

```tsx
{/* Phone Verification */}
<Card>
  <CardHeader>
    <CardTitle className="text-lg">Phone Verification</CardTitle>
    <CardDescription>
      Verify your phone number to receive SMS notifications
    </CardDescription>
  </CardHeader>
  <CardContent>
    {user.phone ? (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <span className="text-sm">{user.phone}</span>
          {user.phone_verified ? (
            <Badge variant="success">Verified</Badge>
          ) : (
            <Badge variant="secondary">Unverified</Badge>
          )}
        </div>

        {!user.phone_verified && (
          <>
            {!showOTPInput ? (
              <Button
                onClick={handleSendPhoneOTP}
                disabled={otpCooldown > 0}
                variant="outline"
                size="sm"
              >
                {otpCooldown > 0
                  ? `Resend in ${otpCooldown}s`
                  : "Send Verification Code"}
              </Button>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Enter the 6-digit code sent to {user.phone}
                </p>
                <InputOTP maxLength={6} value={otpCode} onChange={setOtpCode}>
                  {/* 6 digit input slots */}
                </InputOTP>
                <div className="flex gap-2">
                  <Button onClick={handleVerifyPhone} size="sm">
                    Verify
                  </Button>
                  <Button
                    onClick={handleSendPhoneOTP}
                    variant="ghost"
                    size="sm"
                    disabled={otpCooldown > 0}
                  >
                    {otpCooldown > 0
                      ? `Resend in ${otpCooldown}s`
                      : "Resend Code"}
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    ) : (
      <p className="text-sm text-muted-foreground">
        No phone number on your profile. Add one in your profile settings.
      </p>
    )}
  </CardContent>
</Card>
```

**State management needed:**
```tsx
const [showOTPInput, setShowOTPInput] = useState(false);
const [otpCode, setOtpCode] = useState("");
const [otpCooldown, setOtpCooldown] = useState(0);

// Cooldown timer effect
useEffect(() => {
  if (otpCooldown > 0) {
    const timer = setTimeout(() => setOtpCooldown(otpCooldown - 1), 1000);
    return () => clearTimeout(timer);
  }
}, [otpCooldown]);

const handleSendPhoneOTP = async () => {
  const result = await sendPhoneOTP();
  if (result.success) {
    setShowOTPInput(true);
    setOtpCooldown(60); // 60-second cooldown
    toast.success("Verification code sent");
  } else {
    toast.error(result.error);
  }
};

const handleVerifyPhone = async () => {
  const result = await verifyPhone(otpCode);
  if (result.success) {
    toast.success("Phone number verified");
    setShowOTPInput(false);
    setOtpCode("");
    // Refresh user data
  } else {
    toast.error(result.error);
  }
};
```

---

## Task 7: Frontend — SMS Password Reset Tab

### File: `frontend/app/(auth)/forgot-password/page.tsx`

**Add a tab or toggle** to switch between email and SMS reset:

```tsx
<Tabs defaultValue="email" className="w-full">
  <TabsList className="grid w-full grid-cols-2">
    <TabsTrigger value="email">Email</TabsTrigger>
    <TabsTrigger value="sms">SMS</TabsTrigger>
  </TabsList>

  <TabsContent value="email">
    {/* Existing email reset form */}
  </TabsContent>

  <TabsContent value="sms">
    {!smsOtpSent ? (
      {/* Phone number input + "Send Code" button */}
    ) : (
      {/* OTP input + new password fields */}
    )}
  </TabsContent>
</Tabs>
```

**SMS reset flow (2 steps within the SMS tab):**

1. **Step 1:** Phone number input → "Send Code" button → calls `forgotPasswordSMS(phone)`
2. **Step 2:** 6-digit OTP input + new password + confirm password → "Reset Password" button → calls `resetPasswordSMS(data)`

After successful reset, redirect to login page with success message.

---

## Task 8: Frontend — Server Actions for OTP

### New File: `frontend/actions/otp.action.ts`

```typescript
"use server";

import { apiPost } from "@/lib/api";
import type { ActionResult } from "@/types";

/**
 * Send OTP to the authenticated user's phone for verification.
 * Requires: User must be logged in and have a phone number on profile.
 */
export async function sendPhoneOTP(): Promise<ActionResult> {
  try {
    await apiPost("/auth/send-phone-otp", {});
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send code",
    };
  }
}

/**
 * Verify phone number using 6-digit OTP code.
 * Requires: User must be logged in.
 */
export async function verifyPhone(code: string): Promise<ActionResult> {
  try {
    await apiPost("/auth/verify-phone", { code });
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Verification failed",
    };
  }
}

/**
 * Request SMS OTP for password reset (unauthenticated).
 * Always returns success to prevent phone enumeration.
 */
export async function forgotPasswordSMS(
  phone: string,
): Promise<ActionResult> {
  try {
    await apiPost("/auth/forgot-password-sms", { phone });
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send code",
    };
  }
}

/**
 * Reset password using phone + OTP code (unauthenticated).
 */
export async function resetPasswordSMS(data: {
  phone: string;
  code: string;
  new_password: string;
}): Promise<ActionResult> {
  try {
    await apiPost("/auth/reset-password-sms", data);
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Password reset failed",
    };
  }
}
```

---

## Task 9: Update User Type (Frontend)

### File: Where the User type/interface is defined (likely `frontend/types/index.ts`)

Add to the User type:

```typescript
phone_verified: boolean;
phone_verified_at: string | null;
```

---

## Task 10: Parent Phone Verification Prompt

### File: `frontend/app/(dashboard)/dashboard/page.tsx` (or parent dashboard)

For parent users who have an unverified phone number, show a dismissible banner:

```tsx
{user.role === "parent" && user.phone && !user.phone_verified && (
  <Alert className="mb-4">
    <Phone className="h-4 w-4" />
    <AlertTitle>Verify your phone number</AlertTitle>
    <AlertDescription>
      Verify your phone to receive SMS updates about your child.
      <Link href="/settings/account" className="ml-1 underline">
        Verify now
      </Link>
    </AlertDescription>
  </Alert>
)}
```

This should be dismissible per session (use `sessionStorage`).

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Phone enumeration on reset | Always returns generic message, regardless of phone existence |
| OTP brute force | Max 5 attempts per OTP, then invalidated |
| OTP replay | OTP deleted from Redis on successful verification |
| OTP interception (SIM swap) | SMS is inherently less secure than email — this is a convenience feature, not a security upgrade |
| Cross-tenant OTP reuse | Redis keys scoped by `tenant_id` |
| Rate limiting | 1 OTP per phone per minute; 3 requests/min on endpoints |
| OTP stored in Redis | Hashed with SHA-256 (not plaintext) |

---

## Verification Checklist

- [ ] OTPService generates 6-digit codes correctly
- [ ] OTP is hashed before Redis storage (not plaintext)
- [ ] Rate limit prevents more than 1 OTP per minute per phone
- [ ] Max 5 verification attempts, then OTP invalidated
- [ ] OTP expires after 10 minutes
- [ ] Redis keys are tenant-scoped (verified by key format)
- [ ] Phone verification updates `phone_verified` and `phone_verified_at`
- [ ] SMS password reset returns generic message (no enumeration)
- [ ] SMS password reset blacklists all existing tokens
- [ ] SMS password reset activates PENDING users
- [ ] Frontend OTP input accepts exactly 6 digits
- [ ] Frontend shows 60-second cooldown after sending OTP
- [ ] Parent dashboard shows phone verification prompt
- [ ] Audit events logged for phone verification and SMS reset
