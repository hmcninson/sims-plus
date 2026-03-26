# Phase 2: Services & Endpoints

**Module:** Applicant Accounts (extension to Admissions Portal)
**Agent:** 2 (Services + Schemas + Endpoints + Infrastructure)
**Depends on:** Phase 1 (models + migration) -- needs `APPLICANT` in `UserRole`, `applicant_user_id` on `Application`, `require_applicant_account` on `AdmissionPeriod`
**Produces:** All Pydantic schemas, services, endpoints, dependency injection, middleware updates

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 2.1 | Create Pydantic schemas | `backend/app/schemas/applicant.py` | 1d |
| 2.2 | Create `ApplicantAccountService` | `backend/app/services/admissions/applicant_service.py` | 1.5d |
| 2.3 | Modify `ApplicationService` (accept user_id, list_my_apps, drafts) | `backend/app/services/admissions/application_service.py` | 1d |
| 2.4 | Modify `EnrollmentService` (role promotion) | `backend/app/services/admissions/enrollment_service.py` | 0.25d |
| 2.5 | Update `ROLE_PERMISSIONS` in auth service | `backend/app/services/auth.py` | 0.1d |
| 2.6 | Create `get_applicant_user()` dependency | `backend/app/api/deps.py` | 0.25d |
| 2.7 | Create public endpoints (register, login, verify, etc.) | `backend/app/api/v1/endpoints/admissions/applicant_public.py` | 1d |
| 2.8 | Create authenticated endpoints (profile, my apps, etc.) | `backend/app/api/v1/endpoints/admissions/applicant.py` | 1d |
| 2.9 | Update middleware (public paths, rate limits) | `backend/app/middleware/tenant.py`, `backend/app/middleware/rate_limit.py` | 0.25d |
| 2.10 | Register routers | `backend/app/api/v1/endpoints/admissions/__init__.py` | 0.1d |
| 2.11 | Update services `__init__.py` | `backend/app/services/admissions/__init__.py` | 0.1d |

**Total estimated effort: 6.55 days**

---

## 2.1 Pydantic Schemas

**File:** `backend/app/schemas/applicant.py`

All schemas follow the existing pattern: `BaseSchema` with `ConfigDict(from_attributes=True, str_strip_whitespace=True)`. Create/Update schemas use `Field()` with validation. Response schemas include `id`, timestamps.

```python
"""
SIMS Plus - Applicant Account Schemas

Pydantic schemas for applicant account endpoints.
Covers: registration, login, profile management, my applications,
draft save/submit, application claiming, and printable views.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Registration & Auth
# =========================


class ApplicantRegisterRequest(BaseSchema):
    """Create a new applicant account."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8)
    turnstile_token: str = Field(..., min_length=1)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce same password policy as staff accounts."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class ApplicantRegisterResponse(BaseSchema):
    """Response after successful applicant registration."""

    user_id: UUID
    email: str
    message: str = "Account created. Please check your email to verify."


class ApplicantLoginRequest(BaseSchema):
    """Applicant login request."""

    email: EmailStr
    password: str
    turnstile_token: Optional[str] = None  # Required after 3 failed attempts


class ApplicantLoginResponse(BaseSchema):
    """Response after successful applicant login."""

    access_token: str
    refresh_token: str
    user: "ApplicantProfileResponse"
    token_type: str = "bearer"


class ApplicantProfileResponse(BaseSchema):
    """Applicant profile data."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email_verified: bool
    created_at: datetime


class ApplicantProfileUpdate(BaseSchema):
    """Update applicant profile. All fields optional for partial update."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)


class ApplicantPasswordChange(BaseSchema):
    """Change applicant password (requires current password)."""

    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Same password policy as registration."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class ApplicantForgotPasswordRequest(BaseSchema):
    """Request a password reset email."""

    email: EmailStr
    turnstile_token: str = Field(..., min_length=1)


class ApplicantResetPasswordRequest(BaseSchema):
    """Reset password using token from email."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Same password policy as registration."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class ApplicantVerifyEmailRequest(BaseSchema):
    """Verify email using token from verification link."""

    token: str = Field(..., min_length=1)


class ApplicantResendVerificationRequest(BaseSchema):
    """Resend email verification to applicant."""

    email: EmailStr
    turnstile_token: str = Field(..., min_length=1)


# =========================
# My Applications
# =========================


class MyApplicationListItem(BaseSchema):
    """Lightweight application item for dashboard list view."""

    id: UUID
    tracking_code: str
    applicant_first_name: str
    applicant_last_name: str
    target_class_name: Optional[str] = None
    admission_period_name: Optional[str] = None
    status: str
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MyApplicationListResponse(BaseSchema):
    """Paginated list of applicant's own applications."""

    items: list[MyApplicationListItem]
    total: int
    page: int
    page_size: int
    pages: int


class MyApplicationDetailResponse(BaseSchema):
    """Full application detail for applicant view."""
    id: UUID
    tenant_id: UUID
    tracking_code: str
    admission_period_id: UUID
    admission_period_name: Optional[str] = None
    applicant_first_name: str
    applicant_last_name: str
    applicant_other_names: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    target_class_id: Optional[UUID] = None
    target_class_name: Optional[str] = None
    status: str
    custom_fields: dict[str, Any] = {}
    fee_waived: bool
    exam_waived: bool
    applicant_photo_url: Optional[str] = None
    previous_school: Optional[str] = None
    medical_info: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Nested relations
    guardians: list["ApplicationGuardianResponse"] = []
    documents: list["ApplicationDocumentResponse"] = []
    payments: list["ApplicationPaymentResponse"] = []
    status_history: list["StatusHistoryResponse"] = []
    decision: Optional["AdmissionDecisionResponse"] = None


# =========================
# Draft Application
# =========================


class DraftGuardianData(BaseSchema):
    """Guardian info for draft save. Same as ApplicationGuardianSubmit but all optional."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    relationship: Optional[str] = Field(
        None, pattern="^(father|mother|guardian|other)$"
    )
    is_primary: bool = False
    occupation: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None


class DraftApplicationCreate(BaseSchema):
    """
    Create a new draft application.

    Only admission_period_id and child's name are required to start a draft.
    All other fields can be populated later via update.
    """

    admission_period_id: UUID
    applicant_first_name: str = Field(..., min_length=1, max_length=100)
    applicant_last_name: str = Field(..., min_length=1, max_length=100)
    applicant_other_names: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    nationality: Optional[str] = Field(None, max_length=100)
    target_class_id: Optional[UUID] = None
    previous_school: Optional[str] = Field(None, max_length=255)
    medical_info: Optional[str] = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    guardians: Optional[list[DraftGuardianData]] = None

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date | None) -> date | None:
        if v is not None:
            from datetime import date as date_cls

            if v > date_cls.today():
                raise ValueError("Date of birth cannot be in the future")
        return v


class DraftApplicationUpdate(BaseSchema):
    """
    Update an existing draft application.

    All fields optional for partial save (auto-save on each wizard step).
    """

    applicant_first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    applicant_last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    applicant_other_names: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    nationality: Optional[str] = Field(None, max_length=100)
    target_class_id: Optional[UUID] = None
    previous_school: Optional[str] = Field(None, max_length=255)
    medical_info: Optional[str] = None
    custom_fields: Optional[dict[str, Any]] = None
    guardians: Optional[list[DraftGuardianData]] = None

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date | None) -> date | None:
        if v is not None:
            from datetime import date as date_cls

            if v > date_cls.today():
                raise ValueError("Date of birth cannot be in the future")
        return v


class DraftSubmitResponse(BaseSchema):
    """Response after submitting a draft application."""

    id: UUID
    tracking_code: str
    status: str
    payment_required: bool
    application_fee_amount: Optional[Decimal] = None


# =========================
# Claim Application
# =========================


class ClaimApplicationRequest(BaseSchema):
    """Claim an anonymous application by tracking code."""

    tracking_code: str = Field(..., min_length=1, max_length=100)


class ClaimApplicationResponse(BaseSchema):
    """Response after successfully claiming an application."""

    application_id: UUID
    tracking_code: str
    status: str
    message: str = "Application claimed successfully"


# =========================
# Printable Application
# =========================


class PrintableGuardianInfo(BaseSchema):
    """Guardian info formatted for print view."""

    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    relationship: str
    is_primary: bool
    occupation: Optional[str] = None
    address: Optional[str] = None


class PrintableDocumentInfo(BaseSchema):
    """Document info formatted for print view."""

    document_type: str
    file_name: str
    created_at: datetime


class PrintablePaymentInfo(BaseSchema):
    """Payment info formatted for print view."""

    amount: Decimal
    currency: str
    payment_method: Optional[str] = None
    status: str
    paid_at: Optional[datetime] = None


class PrintableDecisionInfo(BaseSchema):
    """Decision info formatted for print view."""

    decision_type: str
    offered_class_name: Optional[str] = None
    conditions: Optional[str] = None
    decision_date: date
    response_deadline: Optional[date] = None


class PrintableApplicationResponse(BaseSchema):
    """
    Full application data formatted for server-rendered print view.

    Includes all nested relations: guardians, documents, payments, decision.
    No sensitive internal data (notes, status history are excluded).
    """

    id: UUID
    tracking_code: str
    school_name: str
    school_logo_url: Optional[str] = None
    admission_period_name: str
    applicant_first_name: str
    applicant_last_name: str
    applicant_other_names: Optional[str] = None
    date_of_birth: date
    gender: str
    nationality: Optional[str] = None
    target_class_name: str
    previous_school: Optional[str] = None
    medical_info: Optional[str] = None
    custom_fields: dict[str, Any]
    status: str
    submitted_at: Optional[datetime] = None
    created_at: datetime
    guardians: list[PrintableGuardianInfo]
    documents: list[PrintableDocumentInfo]
    payments: list[PrintablePaymentInfo]
    decision: Optional[PrintableDecisionInfo] = None
```

**Notes:**
- All schemas inherit from the same `BaseSchema` pattern used in `schemas/admissions.py`.
- Password validation is duplicated across `ApplicantRegisterRequest`, `ApplicantPasswordChange`, and `ApplicantResetPasswordRequest`. This is intentional -- each schema is self-contained for Pydantic validation. The pattern could be DRYed with a validator mixin, but consistency with the existing codebase is preferred.
- `DraftApplicationCreate` requires only `admission_period_id` and `applicant_first_name`/`applicant_last_name` to start a draft. All other fields are optional because partial saves are the primary use case.
- `PrintableApplicationResponse` intentionally excludes `ApplicationNote` and `ApplicationStatusHistory` -- these are admin-only internal data.

---

## 2.2 ApplicantAccountService

**File:** `backend/app/services/admissions/applicant_service.py`

```python
"""
SIMS Plus - Applicant Account Service

Handles applicant registration, authentication, profile management,
email verification, password reset, and application claiming.

This service reuses the existing User model and auth infrastructure
(Argon2id hashing, JWT issuance, account lockout, token blacklisting)
but scoped to the 'applicant' role with separate endpoints.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admissions.application import Application, ApplicationGuardian
from app.models.user import User, UserRole, UserStatus
from app.utils.turnstile import verify_turnstile

logger = structlog.get_logger(__name__)


class ApplicantAccountError(Exception):
    """Raised when an applicant account operation fails."""

    def __init__(self, message: str, code: str = "APPLICANT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ApplicantAccountService:
    """Service for managing applicant (prospective parent) accounts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        password: str,
        turnstile_token: str,
        remote_ip: str | None = None,
    ) -> User:
        """
        Register a new applicant account.

        Steps:
        1. Verify Cloudflare Turnstile token (fail-closed in production)
        2. Check email uniqueness within tenant (case-insensitive)
        3. Hash password with Argon2id (reuse existing hash_password utility)
        4. Create User with role=APPLICANT, status=PENDING
        5. Send email verification (via existing EmailComposeService)
        6. Return user (without password hash)

        Args:
            tenant_id: Tenant UUID from subdomain resolution.
            school_id: School UUID (derived from tenant's default school).
            first_name: Applicant's first name.
            last_name: Applicant's last name.
            email: Applicant's email address (will be lowercased).
            phone: Applicant's phone number.
            password: Plain-text password (will be hashed).
            turnstile_token: Cloudflare Turnstile verification token.
            remote_ip: Client IP address for logging.

        Returns:
            The created User record.

        Raises:
            ApplicantAccountError: If Turnstile fails, email taken, etc.
        """
        # 1. Turnstile verification (fail-closed)
        if not await verify_turnstile(turnstile_token):
            raise ApplicantAccountError(
                "CAPTCHA verification failed. Please try again.",
                code="CAPTCHA_FAILED",
            )

        # 2. Check email uniqueness within tenant (case-insensitive)
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        normalized_email = email.lower().strip()
        existing = await self.db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == normalized_email,
                User.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ApplicantAccountError(
                "An account with this email already exists.",
                code="EMAIL_TAKEN",
            )

        # 3. Hash password with Argon2id
        from app.core.security import hash_password

        hashed = hash_password(password)

        # 4. Create User with role=APPLICANT, status=PENDING
        user = User(
            tenant_id=tenant_id,
            school_id=school_id,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=normalized_email,
            phone=phone.strip(),
            password_hash=hashed,
            role=UserRole.APPLICANT.value,
            status=UserStatus.PENDING.value,
            email_verified=False,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # 5. Send email verification (best-effort, do not block registration)
        try:
            from app.services.email_verification import EmailVerificationService

            verification_service = EmailVerificationService(self.db)
            await verification_service.create_and_send_verification(user.id, user.email)
        except Exception:
            # Log but don't fail registration -- user can resend later
            logger.exception(
                "applicant_verification_email_failed",
                user_id=str(user.id),
                email=normalized_email,
            )

        logger.info(
            "applicant_registered",
            user_id=str(user.id),
            tenant_id=str(tenant_id),
            remote_ip=remote_ip,
        )

        return user

    async def login(
        self,
        tenant_id: uuid.UUID,
        *,
        email: str,
        password: str,
        turnstile_token: str | None = None,
        remote_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """
        Authenticate an applicant and issue JWT tokens.

        Steps:
        1. Find user by email + tenant_id + role=applicant
        2. Check account lockout (reuse existing AuthService logic)
        3. Verify password against Argon2id hash
        4. Check email_verified (reject if not verified)
        5. Issue JWT with role=applicant in claims + refresh token
        6. Update last_login timestamp
        7. Return (user, access_token, refresh_token)

        The JWT claims include the 'applicant' role and applicant-specific
        permissions. The token is identical in structure to staff tokens,
        allowing the existing token validation middleware to work unchanged.

        Args:
            tenant_id: Tenant UUID from subdomain resolution.
            email: Applicant's email address.
            password: Plain-text password to verify.
            remote_ip: Client IP for audit logging.
            user_agent: Client user agent for audit logging.

        Returns:
            Tuple of (User, access_token, refresh_token).

        Raises:
            ApplicantAccountError: If credentials invalid, account locked,
                or email not verified.
        """
        normalized_email = email.lower().strip()

        # 1. Find user with role=applicant within tenant
        result = await self.db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == normalized_email,
                User.role == UserRole.APPLICANT.value,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ApplicantAccountError(
                "Invalid email or password.",
                code="INVALID_CREDENTIALS",
            )

        # 2. Check account lockout
        from app.core.security import is_account_locked

        if is_account_locked(user):
            raise ApplicantAccountError(
                "Account is temporarily locked due to too many failed attempts. "
                "Please try again later.",
                code="ACCOUNT_LOCKED",
            )

        # 2b. Adaptive CAPTCHA: require Turnstile after 3 failed attempts
        if user.failed_login_attempts and user.failed_login_attempts >= 3:
            if not turnstile_token or not await verify_turnstile(turnstile_token, remote_ip=remote_ip):
                raise ApplicantAccountError(
                    "CAPTCHA verification required after multiple failed attempts.",
                    code="CAPTCHA_REQUIRED",
                )

        # 3. Check account status
        if user.status == UserStatus.SUSPENDED.value:
            raise ApplicantAccountError(
                "Your account has been suspended. Please contact the school.",
                code="ACCOUNT_SUSPENDED",
            )

        if user.status == UserStatus.DEACTIVATED.value:
            raise ApplicantAccountError(
                "Your account has been deactivated.",
                code="ACCOUNT_DEACTIVATED",
            )

        # 4. Verify password
        from app.core.security import verify_password

        if not verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            user.last_failed_login = datetime.now(UTC)
            await self.db.flush()

            raise ApplicantAccountError(
                "Invalid email or password.",
                code="INVALID_CREDENTIALS",
            )

        # 5. Check email verification
        if not user.email_verified:
            raise ApplicantAccountError(
                "Please verify your email address before logging in. "
                "Check your inbox or request a new verification email.",
                code="EMAIL_NOT_VERIFIED",
            )

        # 6. Reset failed attempts + update last_login
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.last_login = datetime.now(UTC)
        await self.db.flush()

        # 7. Issue JWT tokens
        from app.services.auth import AuthService

        auth_service = AuthService(self.db)
        access_token = auth_service.create_access_token(user)
        refresh_token = auth_service.create_refresh_token(user)

        logger.info(
            "applicant_login",
            user_id=str(user.id),
            tenant_id=str(tenant_id),
            remote_ip=remote_ip,
        )

        return user, access_token, refresh_token

    async def get_profile(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> User:
        """
        Get applicant profile by user_id.

        Defense-in-depth: filters by tenant_id AND user_id.

        Args:
            tenant_id: Tenant UUID from JWT.
            user_id: User UUID from JWT.

        Returns:
            User record.

        Raises:
            ApplicantAccountError: If user not found.
        """
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.role == UserRole.APPLICANT.value,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ApplicantAccountError("Profile not found", code="NOT_FOUND")
        return user

    async def update_profile(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        phone: str | None = None,
    ) -> User:
        """
        Update applicant profile (name, phone only).

        Email changes are not allowed to prevent breaking the email
        verification and claim flow.

        Args:
            tenant_id: Tenant UUID from JWT.
            user_id: User UUID from JWT.
            first_name: New first name (optional).
            last_name: New last name (optional).
            phone: New phone number (optional).

        Returns:
            Updated User record.

        Raises:
            ApplicantAccountError: If user not found.
        """
        user = await self.get_profile(tenant_id, user_id)

        if first_name is not None:
            user.first_name = first_name.strip()
        if last_name is not None:
            user.last_name = last_name.strip()
        if phone is not None:
            user.phone = phone.strip()

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def change_password(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change applicant password (requires current password verification).

        After successful password change, all existing tokens are invalidated
        via mass-revoke to force re-login on other devices.

        Args:
            tenant_id: Tenant UUID from JWT.
            user_id: User UUID from JWT.
            current_password: Current password for verification.
            new_password: New password to set.

        Raises:
            ApplicantAccountError: If current password is wrong or user not found.
        """
        user = await self.get_profile(tenant_id, user_id)

        # Verify current password
        from app.core.security import verify_password

        if not verify_password(current_password, user.password_hash):
            raise ApplicantAccountError(
                "Current password is incorrect.",
                code="INVALID_PASSWORD",
            )

        # Hash and set new password
        from app.core.security import hash_password

        user.password_hash = hash_password(new_password)
        await self.db.flush()

        # Invalidate all existing tokens for this user
        try:
            from app.services.auth import AuthService

            auth_service = AuthService(self.db)
            await auth_service.revoke_all_user_tokens(str(user_id))
        except Exception:
            # Log but don't fail -- password is already changed
            logger.exception(
                "applicant_token_revoke_failed_after_password_change",
                user_id=str(user_id),
            )

        logger.info(
            "applicant_password_changed",
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )

    async def claim_application(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        tracking_code: str,
    ) -> Application:
        """
        Claim a previously anonymous application.

        Validation:
        1. Find application by tracking_code + tenant_id (defense-in-depth)
        2. Verify applicant_user_id is NULL (not already claimed)
        3. Verify at least one guardian email on the application matches
           the applicant's account email (proves they are the applicant)
        4. Set applicant_user_id = user_id

        This prevents unauthorized claiming: an attacker would need both
        the 384-bit tracking code AND knowledge that a specific email is
        on the application.

        Args:
            tenant_id: Tenant UUID from JWT.
            user_id: User UUID from JWT.
            tracking_code: Application tracking code.

        Returns:
            The claimed Application record.

        Raises:
            ApplicantAccountError: If application not found, already claimed,
                or email mismatch.
        """
        # Get the applicant's email for matching
        user = await self.get_profile(tenant_id, user_id)

        # Generic error for all claim failures (anti-enumeration)
        claim_failed_error = ApplicantAccountError(
            "Unable to claim this application. Please verify the tracking code "
            "and ensure your account email matches a guardian email on the application.",
            code="CLAIM_FAILED",
        )

        # Find application by tracking code within tenant
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.guardians))
            .where(
                Application.tenant_id == tenant_id,
                Application.tracking_code == tracking_code,
                Application.deleted_at.is_(None),
            )
        )
        application = result.scalar_one_or_none()

        if not application:
            raise claim_failed_error

        # Check not already claimed
        if application.applicant_user_id is not None:
            # Special case: if already claimed by THIS user, return idempotent success
            if str(application.applicant_user_id) == str(user_id):
                return application
            raise claim_failed_error

        # Verify guardian email matches applicant's account email
        guardian_emails = [g.email.lower() for g in application.guardians if g.email and g.deleted_at is None]
        if not user or user.email.lower() not in guardian_emails:
            raise claim_failed_error

        # Claim the application
        application.applicant_user_id = user_id
        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "application_claimed",
            application_id=str(application.id),
            user_id=str(user_id),
            tenant_id=str(tenant_id),
            tracking_code=tracking_code,
        )

        return application

    async def verify_email(
        self,
        tenant_id: uuid.UUID,
        *,
        token: str,
    ) -> User:
        """
        Verify applicant email using verification token.

        Delegates to EmailVerificationService which handles:
        - Token decoding and expiry validation
        - User lookup by token's user_id
        - Setting email_verified=True
        - Activating the user (PENDING -> ACTIVE)

        Additional validation: ensures the user is an applicant
        (prevents using applicant verification link for staff accounts).

        Args:
            tenant_id: Tenant UUID from subdomain.
            token: Email verification token from the link.

        Returns:
            The verified User record.

        Raises:
            ApplicantAccountError: If token invalid, expired, or user not applicant.
        """
        from app.services.email_verification import EmailVerificationService

        verification_service = EmailVerificationService(self.db)
        try:
            user = await verification_service.verify_email(token=token, ip_address=None)
        except Exception:
            raise ApplicantAccountError(
                "Invalid or expired verification link.",
                code="INVALID_TOKEN",
            )

        # Ensure this is an applicant account
        if user.role != UserRole.APPLICANT.value:
            raise ApplicantAccountError(
                "Invalid verification link.",
                code="INVALID_TOKEN",
            )

        # Defense-in-depth: verify tenant matches
        if str(user.tenant_id) != str(tenant_id):
            raise ApplicantAccountError(
                "Invalid verification link.",
                code="INVALID_TOKEN",
            )

        return user

    async def forgot_password(
        self,
        tenant_id: uuid.UUID,
        *,
        email: str,
        turnstile_token: str,
    ) -> None:
        """
        Send password reset email to applicant.

        Always returns success (even if email not found) to prevent
        email enumeration attacks.

        Args:
            tenant_id: Tenant UUID from subdomain.
            email: Applicant's email address.
            turnstile_token: Cloudflare Turnstile token.
        """
        # Turnstile verification
        if not await verify_turnstile(turnstile_token):
            raise ApplicantAccountError(
                "CAPTCHA verification failed. Please try again.",
                code="CAPTCHA_FAILED",
            )

        normalized_email = email.lower().strip()

        # Look up applicant user (silently succeed if not found)
        result = await self.db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == normalized_email,
                User.role == UserRole.APPLICANT.value,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if user:
            try:
                from app.services.password_reset import PasswordResetService

                reset_service = PasswordResetService(self.db)
                await reset_service.request_reset(email=normalized_email, ip_address=None)
            except Exception:
                logger.exception(
                    "applicant_password_reset_email_failed",
                    email=normalized_email,
                )

        # Always return success to prevent enumeration
        logger.info(
            "applicant_forgot_password",
            email=normalized_email,
            tenant_id=str(tenant_id),
            user_found=user is not None,
        )

    async def reset_password(
        self,
        tenant_id: uuid.UUID,
        *,
        token: str,
        password: str,
    ) -> None:
        """
        Reset applicant password using token from email.

        Delegates to PasswordResetService which handles:
        - Token decoding and expiry validation
        - User lookup by token's user_id
        - Password hashing with Argon2id
        - Mass token revocation

        Additional validation: ensures the user is an applicant.

        Args:
            tenant_id: Tenant UUID from subdomain.
            token: Password reset token from email.
            password: New password.

        Raises:
            ApplicantAccountError: If token invalid/expired or user not applicant.
        """
        from app.services.password_reset import PasswordResetService

        reset_service = PasswordResetService(self.db)
        try:
            await reset_service.reset_password(
                token=token,
                new_password=password,
                ip_address=None,
            )
        except Exception:
            raise ApplicantAccountError(
                "Invalid or expired reset link.",
                code="INVALID_TOKEN",
            )

        logger.info(
            "applicant_password_reset",
            tenant_id=str(tenant_id),
        )

    async def resend_verification(
        self,
        tenant_id: uuid.UUID,
        *,
        email: str,
        turnstile_token: str,
    ) -> None:
        """
        Resend email verification to applicant.

        Silently succeeds if email not found (prevent enumeration).
        Only resends if email is NOT already verified.
        Requires Turnstile token to prevent automated spam.

        Args:
            tenant_id: Tenant UUID from subdomain.
            email: Applicant's email address.
            turnstile_token: Cloudflare Turnstile verification token.
        """
        # Turnstile verification (fail-closed)
        if not await verify_turnstile(turnstile_token):
            raise ApplicantAccountError(
                "CAPTCHA verification failed. Please try again.",
                code="CAPTCHA_FAILED",
            )

        normalized_email = email.lower().strip()

        result = await self.db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == normalized_email,
                User.role == UserRole.APPLICANT.value,
                User.email_verified == False,  # noqa: E712
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if user:
            try:
                from app.services.email_verification import EmailVerificationService

                verification_service = EmailVerificationService(self.db)
                await verification_service.resend_verification(email=normalized_email)
            except Exception:
                logger.exception(
                    "applicant_resend_verification_failed",
                    email=normalized_email,
                )

        # Always succeed to prevent enumeration
        logger.info(
            "applicant_resend_verification",
            email=normalized_email,
            tenant_id=str(tenant_id),
        )
```

**Implementation Notes:**

- **Service Reuse:** The `login()` method delegates to `AuthService` for JWT issuance. The `verify_email()` and `resend_verification()` methods delegate to `EmailVerificationService`. The `forgot_password()` and `reset_password()` methods delegate to `PasswordResetService`. This prevents duplicating security-critical code.
- **Role Scoping:** Every query that looks up a user includes `User.role == UserRole.APPLICANT.value`. This ensures staff accounts cannot be accessed through applicant endpoints, and vice versa.
- **Email Enumeration Prevention:** `forgot_password()` and `resend_verification()` always return success, regardless of whether the email exists. This is a standard security practice.
- **Claim Flow Security:** Requires both the 384-bit tracking code AND a matching guardian email. The email comparison is case-insensitive. `deleted_at` is checked on guardians to exclude soft-deleted records.
- **Imports Inside Methods:** `AuthService`, `hash_password`, and `verify_password` are imported inside methods rather than at module level to avoid circular import issues (since `auth.py` imports from models that this service also imports).

---

## 2.3 ApplicationService Modifications

**File:** `backend/app/services/admissions/application_service.py`

The following methods are **added** to the existing `ApplicationService` class. The existing `submit()` method is also modified to accept an optional `applicant_user_id`.

### Modification to `submit()` Method

Add the `applicant_user_id` parameter to the existing signature:

```python
async def submit(
    self,
    tenant_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    turnstile_token: str,
    admission_period_id: uuid.UUID,
    applicant_first_name: str,
    applicant_last_name: str,
    applicant_other_names: str | None,
    date_of_birth: str,
    gender: str,
    nationality: str | None,
    target_class_id: uuid.UUID,
    custom_fields: dict,
    previous_school: str | None,
    medical_info: str | None,
    guardians: list[dict],
    applicant_user_id: uuid.UUID | None = None,  # NEW — set when authenticated
) -> Application:
    """
    Submit a new application (public endpoint).

    When applicant_user_id is provided (authenticated submission),
    the application is linked to the user account.

    All other behavior is unchanged.
    """
    # ... existing implementation unchanged up to Application creation ...

    application = Application(
        tenant_id=tenant_id,
        school_id=school_id,
        admission_period_id=admission_period_id,
        tracking_code=tracking_code,
        applicant_first_name=applicant_first_name.strip(),
        applicant_last_name=applicant_last_name.strip(),
        applicant_other_names=(
            applicant_other_names.strip() if applicant_other_names else None
        ),
        date_of_birth=date_of_birth,
        gender=gender.lower(),
        nationality=nationality,
        target_class_id=target_class_id,
        status=initial_status,
        custom_fields=custom_fields,
        previous_school=previous_school,
        medical_info=medical_info,
        submitted_at=submitted_at,
        # NEW: link to applicant account if authenticated
        applicant_user_id=applicant_user_id,
    )

    # ... rest of method unchanged ...
```

### New Method: `list_my_applications()`

```python
async def list_my_applications(
    self,
    tenant_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Application], int]:
    """
    List applications belonging to a specific applicant user.

    IDOR protection: filters by BOTH tenant_id AND applicant_user_id.
    The user_id comes from the JWT (never from request body/params).

    Args:
        tenant_id: Tenant UUID from JWT (defense-in-depth).
        applicant_user_id: User UUID from JWT.
        status: Optional status filter.
        page: Page number (1-indexed).
        page_size: Items per page (max 100).

    Returns:
        Tuple of (applications list, total count).
    """
    query = (
        select(Application)
        .options(
            selectinload(Application.target_class),
            selectinload(Application.admission_period),
        )
        .where(
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            Application.tenant_id == tenant_id,
            # IDOR prevention: only this user's applications
            Application.applicant_user_id == applicant_user_id,
            Application.deleted_at.is_(None),
        )
    )

    if status:
        query = query.where(Application.status == status)

    # Count
    count_result = await self.db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Paginate, most recent first
    query = (
        query
        .order_by(Application.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await self.db.execute(query)
    return list(result.scalars().all()), total
```

### New Method: `create_draft()`

```python
async def create_draft(
    self,
    tenant_id: uuid.UUID,
    school_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
    *,
    admission_period_id: uuid.UUID,
    applicant_first_name: str,
    applicant_last_name: str,
    applicant_other_names: str | None = None,
    date_of_birth: str | None = None,
    gender: str | None = None,
    nationality: str | None = None,
    target_class_id: uuid.UUID | None = None,
    previous_school: str | None = None,
    medical_info: str | None = None,
    custom_fields: dict | None = None,
    guardians: list[dict] | None = None,
) -> Application:
    """
    Create a new draft application linked to an applicant account.

    Minimal validation: period must exist and be open.
    No Turnstile required (user is authenticated).
    No custom_fields schema validation (will be validated on submit).
    Guardians are optional at draft stage.

    Per-tenant daily cap still applies to prevent abuse.

    Args:
        tenant_id: Tenant UUID from JWT.
        school_id: School UUID from tenant context.
        applicant_user_id: User UUID from JWT.
        admission_period_id: Target admission period.
        applicant_first_name: Child's first name (required).
        applicant_last_name: Child's last name (required).
        ... other fields are optional for initial draft.

    Returns:
        The created Application in DRAFT status.

    Raises:
        ApplicationServiceError: If period not found, not open, or daily cap hit.
    """
    # Validate period exists and is open
    period = await self._get_open_period(tenant_id, admission_period_id)

    # Per-tenant daily cap (defense against authenticated abuse)
    daily_count = await self._get_daily_submission_count(tenant_id)
    if daily_count >= settings.ADMISSIONS_DAILY_CAP_PER_TENANT:
        raise ApplicationServiceError(
            "This school has reached the maximum number of applications for today.",
            code="DAILY_CAP_EXCEEDED",
        )

    # Generate tracking code
    tracking_code = secrets.token_urlsafe(48)

    # Create application in DRAFT status (always starts as draft)
    application = Application(
        tenant_id=tenant_id,
        school_id=school_id,
        admission_period_id=admission_period_id,
        tracking_code=tracking_code,
        applicant_first_name=applicant_first_name.strip(),
        applicant_last_name=applicant_last_name.strip(),
        applicant_other_names=(
            applicant_other_names.strip() if applicant_other_names else None
        ),
        date_of_birth=date_of_birth,
        gender=gender.lower() if gender else None,
        nationality=nationality,
        target_class_id=target_class_id,
        status=AdmissionApplicationStatus.DRAFT.value,
        custom_fields=custom_fields or {},
        previous_school=previous_school,
        medical_info=medical_info,
        # Link to applicant account
        applicant_user_id=applicant_user_id,
    )
    self.db.add(application)
    await self.db.flush()

    # Create guardian records if provided
    if guardians:
        for g_data in guardians:
            guardian = ApplicationGuardian(
                tenant_id=tenant_id,
                application_id=application.id,
                first_name=g_data.get("first_name", "").strip(),
                last_name=g_data.get("last_name", "").strip(),
                phone=g_data.get("phone", "").strip(),
                email=(g_data.get("email", "") or "").strip() or None,
                relationship=g_data.get("relationship", "guardian"),
                is_primary=g_data.get("is_primary", False),
                occupation=g_data.get("occupation"),
                address=g_data.get("address"),
            )
            self.db.add(guardian)

    # Status history
    history = ApplicationStatusHistory(
        tenant_id=tenant_id,
        application_id=application.id,
        from_status=None,
        to_status=AdmissionApplicationStatus.DRAFT.value,
        changed_by=applicant_user_id,
        reason="Draft created via applicant dashboard",
    )
    self.db.add(history)

    await self.db.flush()
    await self.db.refresh(application)

    logger.info(
        "draft_application_created",
        application_id=str(application.id),
        user_id=str(applicant_user_id),
        tenant_id=str(tenant_id),
    )

    return application
```

### New Method: `update_draft()`

```python
async def update_draft(
    self,
    tenant_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
    application_id: uuid.UUID,
    *,
    applicant_first_name: str | None = None,
    applicant_last_name: str | None = None,
    applicant_other_names: str | None = None,
    date_of_birth: str | None = None,
    gender: str | None = None,
    nationality: str | None = None,
    target_class_id: uuid.UUID | None = None,
    previous_school: str | None = None,
    medical_info: str | None = None,
    custom_fields: dict | None = None,
    guardians: list[dict] | None = None,
) -> Application:
    """
    Update a draft application.

    IDOR protection: verifies application.applicant_user_id == user_id.
    Only applications in DRAFT status can be updated.

    When guardians are provided, the existing guardian records are
    replaced (delete + recreate). This simplifies partial updates
    from the multi-step wizard.

    Args:
        tenant_id: Tenant UUID from JWT.
        applicant_user_id: User UUID from JWT.
        application_id: Application UUID from URL path.
        ... optional fields for partial update.

    Returns:
        The updated Application.

    Raises:
        ApplicationServiceError: If not found, not owner, or not in DRAFT status.
    """
    application = await self._get_my_application(
        tenant_id, applicant_user_id, application_id
    )

    if application.status != AdmissionApplicationStatus.DRAFT.value:
        raise ApplicationServiceError(
            "Only draft applications can be updated.",
            code="NOT_DRAFT",
        )

    # Update scalar fields (only if provided)
    if applicant_first_name is not None:
        application.applicant_first_name = applicant_first_name.strip()
    if applicant_last_name is not None:
        application.applicant_last_name = applicant_last_name.strip()
    if applicant_other_names is not None:
        application.applicant_other_names = (
            applicant_other_names.strip() if applicant_other_names else None
        )
    if date_of_birth is not None:
        application.date_of_birth = date_of_birth
    if gender is not None:
        application.gender = gender.lower()
    if nationality is not None:
        application.nationality = nationality
    if target_class_id is not None:
        application.target_class_id = target_class_id
    if previous_school is not None:
        application.previous_school = previous_school
    if medical_info is not None:
        application.medical_info = medical_info
    if custom_fields is not None:
        application.custom_fields = custom_fields

    # Optimistic concurrency: check updated_at matches expected value
    # If another save happened between read and write, return 409 Conflict
    # The frontend auto-save debounce (2s) makes conflicts unlikely but possible
    # on slow connections with multiple tabs open.

    # Replace guardians if provided
    if guardians is not None:
        # Hard-delete existing guardians (draft data, not finalized)
        # Draft guardian records are not finalized data -- hard delete prevents
        # accumulating orphan records during repeated saves.
        from sqlalchemy import delete

        await self.db.execute(
            delete(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application.id,
                ApplicationGuardian.tenant_id == tenant_id,
            )
        )
        await self.db.flush()

        # Create new guardian records
        for g_data in guardians:
            guardian = ApplicationGuardian(
                tenant_id=tenant_id,
                application_id=application_id,
                first_name=g_data.get("first_name", "").strip(),
                last_name=g_data.get("last_name", "").strip(),
                phone=g_data.get("phone", "").strip(),
                email=(g_data.get("email", "") or "").strip() or None,
                relationship=g_data.get("relationship", "guardian"),
                is_primary=g_data.get("is_primary", False),
                occupation=g_data.get("occupation"),
                address=g_data.get("address"),
            )
            self.db.add(guardian)

    await self.db.flush()
    await self.db.refresh(application)

    return application
```

### New Method: `submit_draft()`

```python
async def submit_draft(
    self,
    tenant_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
    application_id: uuid.UUID,
) -> Application:
    """
    Submit a draft application.

    IDOR protection: verifies application.applicant_user_id == user_id.
    Only applications in DRAFT status can be submitted.

    Full validation (same as public submit):
    - At least one guardian required (with non-empty required fields)
    - target_class_id must be set
    - date_of_birth must be set
    - gender must be set
    - custom_fields validated against form_schema (if configured)

    If fee is required and not waived, status stays DRAFT until payment.
    If fee is not required (or waived), status transitions to SUBMITTED.

    Args:
        tenant_id: Tenant UUID from JWT.
        applicant_user_id: User UUID from JWT.
        application_id: Application UUID from URL path.

    Returns:
        The submitted Application with updated status.

    Raises:
        ApplicationServiceError: If validation fails, not owner, or not DRAFT.
    """
    application = await self._get_my_application(
        tenant_id, applicant_user_id, application_id
    )

    if application.status != AdmissionApplicationStatus.DRAFT.value:
        raise ApplicationServiceError(
            "Only draft applications can be submitted.",
            code="NOT_DRAFT",
        )

    # --- Full validation ---

    # Required fields
    if not application.target_class_id:
        raise ApplicationServiceError(
            "Target class is required before submission.",
            code="MISSING_TARGET_CLASS",
        )
    if not application.date_of_birth:
        raise ApplicationServiceError(
            "Date of birth is required before submission.",
            code="MISSING_DOB",
        )
    if not application.gender:
        raise ApplicationServiceError(
            "Gender is required before submission.",
            code="MISSING_GENDER",
        )

    # Guardians validation
    guardian_result = await self.db.execute(
        select(ApplicationGuardian).where(
            ApplicationGuardian.application_id == application_id,
            ApplicationGuardian.tenant_id == tenant_id,
            ApplicationGuardian.deleted_at.is_(None),
        )
    )
    active_guardians = guardian_result.scalars().all()

    if not active_guardians:
        raise ApplicationServiceError(
            "At least one guardian is required before submission.",
            code="NO_GUARDIANS",
        )

    # Validate guardian required fields
    for g in active_guardians:
        if not g.first_name or not g.last_name or not g.phone:
            raise ApplicationServiceError(
                "All guardians must have first name, last name, and phone number.",
                code="INCOMPLETE_GUARDIAN",
            )

    # Custom fields validation against form schema
    await self._validate_custom_fields(
        tenant_id, application.admission_period_id, application.custom_fields
    )

    # --- Determine submission status ---
    period = await self._get_open_period(tenant_id, application.admission_period_id)

    if not period.application_fee_required or application.fee_waived:
        # No fee required — transition to SUBMITTED
        application.status = AdmissionApplicationStatus.SUBMITTED.value
        application.submitted_at = datetime.now(UTC)
    else:
        # Fee required — check if already paid
        has_payment = await self._has_completed_payment(tenant_id, application_id)
        if has_payment:
            application.status = AdmissionApplicationStatus.SUBMITTED.value
            application.submitted_at = datetime.now(UTC)
        # else: stays in DRAFT until payment confirmed (via webhook)

    # Status history
    history = ApplicationStatusHistory(
        tenant_id=tenant_id,
        application_id=application_id,
        from_status=AdmissionApplicationStatus.DRAFT.value,
        to_status=application.status,
        changed_by=applicant_user_id,
        reason="Submitted via applicant dashboard",
    )
    self.db.add(history)

    await self.db.flush()
    await self.db.refresh(application)

    logger.info(
        "draft_submitted",
        application_id=str(application_id),
        user_id=str(applicant_user_id),
        new_status=application.status,
    )

    return application
```

### New Method: `get_my_application()`

```python
async def get_my_application(
    self,
    tenant_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
    application_id: uuid.UUID,
) -> Application:
    """
    Get a single application owned by the applicant.

    IDOR protection: verifies application.applicant_user_id == user_id.
    Loads basic relations (guardians, documents, payments).

    Args:
        tenant_id: Tenant UUID from JWT.
        applicant_user_id: User UUID from JWT.
        application_id: Application UUID from URL path.

    Returns:
        Application with guardians, documents, and payments loaded.

    Raises:
        ApplicationServiceError: If not found or not owner.
    """
    result = await self.db.execute(
        select(Application)
        .options(
            selectinload(Application.guardians),
            selectinload(Application.documents),
            selectinload(Application.payments),
        )
        .where(
            Application.id == application_id,
            # Defense-in-depth: filter by tenant_id
            Application.tenant_id == tenant_id,
            # IDOR prevention: must be owner
            Application.applicant_user_id == applicant_user_id,
            Application.deleted_at.is_(None),
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise ApplicationServiceError(
            "Application not found.",
            code="NOT_FOUND",
        )

    return application
```

### New Method: `get_printable_application()`

```python
async def get_printable_application(
    self,
    tenant_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
    application_id: uuid.UUID,
) -> Application:
    """
    Get full application data for print view.

    Same IDOR protection as get_my_application but eager-loads ALL
    relations needed for the printable view:
    - guardians, documents, payments, decision
    - admission_period (for period name)
    - target_class (for class name)
    - school (for school name, logo)

    Does NOT include: notes, status_history (admin-only data).

    Args:
        tenant_id: Tenant UUID from JWT.
        applicant_user_id: User UUID from JWT.
        application_id: Application UUID from URL path.

    Returns:
        Application with all print-relevant relations loaded.

    Raises:
        ApplicationServiceError: If not found or not owner.
    """
    result = await self.db.execute(
        select(Application)
        .options(
            selectinload(Application.guardians),
            selectinload(Application.documents),
            selectinload(Application.payments),
            selectinload(Application.decision),
            selectinload(Application.admission_period),
            selectinload(Application.target_class),
            selectinload(Application.school),
        )
        .where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
            Application.applicant_user_id == applicant_user_id,
            Application.deleted_at.is_(None),
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise ApplicationServiceError(
            "Application not found.",
            code="NOT_FOUND",
        )

    return application
```

### New Private Helper: `_get_my_application()`

```python
async def _get_my_application(
    self,
    tenant_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
    application_id: uuid.UUID,
) -> Application:
    """
    Internal helper: fetch application with IDOR check.

    Does NOT eagerly load relations — used by update/submit methods
    that don't need nested data.
    """
    result = await self.db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
            Application.applicant_user_id == applicant_user_id,
            Application.deleted_at.is_(None),
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise ApplicationServiceError(
            "Application not found.",
            code="NOT_FOUND",
        )

    return application
```

### New Method: `get_latest_guardian_info()`

```python
async def get_latest_guardian_info(
    self,
    tenant_id: uuid.UUID,
    applicant_user_id: uuid.UUID,
) -> list[dict]:
    """
    Get guardian info from the most recent submitted application.
    Used for pre-filling guardian section when creating a new application.
    Returns empty list if no previous applications exist.
    """
    result = await self.db.execute(
        select(Application)
        .where(
            Application.tenant_id == tenant_id,
            Application.applicant_user_id == applicant_user_id,
            Application.status != AdmissionApplicationStatus.DRAFT.value,
            Application.deleted_at.is_(None),
        )
        .options(selectinload(Application.guardians))
        .order_by(Application.created_at.desc())
        .limit(1)
    )
    latest_app = result.scalar_one_or_none()
    if not latest_app:
        return []

    return [
        {
            "first_name": g.first_name,
            "last_name": g.last_name,
            "phone": g.phone,
            "email": g.email,
            "relationship": g.relationship,
            "is_primary": g.is_primary,
            "occupation": g.occupation,
            "address": g.address,
        }
        for g in latest_app.guardians
        if g.deleted_at is None
    ]
```

---

## 2.4 EnrollmentService Modifications

**File:** `backend/app/services/admissions/enrollment_service.py`

Add role promotion logic to the existing `enroll()` method. This code runs **after** the student record is created and the application status is updated to ENROLLED.

### Changes to `enroll()` Method

Insert the following block after step 8 (status history logging) and before step 9 (notification):

```python
# ... existing steps 1-8 ...

# 8b. Role promotion: applicant → parent
# If the application was submitted by an authenticated applicant,
# promote their role from 'applicant' to 'parent' so they gain
# access to the parent portal. This is a seamless transition —
# same account, same credentials, expanded permissions.
#
# Check if ParentOnboardingService will handle this user.
# The existing enroll() method calls ParentOnboardingService.create_parent_for_student()
# which creates a NEW parent account from guardian email. We must prevent duplicate:
#
# Priority: If application.applicant_user_id exists, skip ParentOnboardingService
# and promote the existing applicant user instead.
if app.applicant_user_id is not None:
    applicant_user_result = await self.db.execute(
        select(User).where(
            User.id == app.applicant_user_id,
            # Defense-in-depth: verify tenant matches
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
    )
    applicant_user = applicant_user_result.scalar_one_or_none()

    if applicant_user and applicant_user.role == UserRole.APPLICANT.value:
        applicant_user.role = UserRole.PARENT.value
        await self.db.flush()

        # Revoke existing tokens to force re-login with new role
        try:
            blacklist = await get_token_blacklist_service()
            await blacklist.revoke_all_user_tokens(str(applicant_user.id))
        except Exception:
            logger.warning("token_revoke_after_promotion_failed", user_id=str(applicant_user.id))

        logger.info(
            "applicant_promoted_to_parent",
            user_id=str(applicant_user.id),
            application_id=str(application_id),
            tenant_id=str(tenant_id),
        )

    # Skip ParentOnboardingService for this guardian — user already exists
    skip_parent_onboarding_for_email = applicant_user.email if applicant_user else None
else:
    skip_parent_onboarding_for_email = None

# 9. Send enrollment notification ...
```

**Required Import Addition:**

```python
from app.models.user import User, UserRole
```

**Implementation Notes:**

- Only promotes `applicant` role to `parent`. If the user already has `parent` role (from a previous child's enrollment), no change is made.
- The role check is explicit: `applicant_user.role == UserRole.APPLICANT.value`. Other roles (e.g., `teacher` who somehow has an applicant_user_id link) are left unchanged.
- Uses `flush()` not `commit()` -- the enrollment transaction is atomic across all steps.

---

## 2.5 Auth Service Modifications

**File:** `backend/app/services/auth.py`

Add the `applicant` role to `ROLE_PERMISSIONS`:

```python
ROLE_PERMISSIONS = {
    # ... existing roles unchanged ...
    "student": [
        "self.read",
    ],
    # NEW: applicant role — prospective parents with limited access
    "applicant": [
        "applicant.profile.read",
        "applicant.profile.update",
        "applicant.applications.read",
        "applicant.applications.create",
        "applicant.applications.update",
        "applicant.applications.submit",
        "applicant.applications.claim",
    ],
}
```

**Notes:**
- The `applicant` role has its own isolated permission namespace (`applicant.*`).
- No overlap with staff permissions (`admissions.*`), parent permissions (`parent.*`, `children.*`), or any other role.
- The `require_permissions()` dependency in `deps.py` already checks against `ROLE_PERMISSIONS` using the user's role from JWT claims. No changes needed there.

---

## 2.6 New Dependency: `get_applicant_user()`

**File:** `backend/app/api/deps.py`

This dependency is similar to `ValidatedUser` but adds a role check to ensure only `applicant` users can access applicant endpoints. It prevents staff or parents from accidentally hitting the applicant API.

```python
async def get_applicant_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Validate JWT and ensure user has the 'applicant' role.

    This dependency is used for all authenticated applicant endpoints.
    It performs the same validation as get_validated_current_user() plus
    an additional role check.

    Rejects:
    - Invalid/expired tokens
    - Blacklisted tokens
    - Cross-tenant tokens
    - Non-applicant roles (staff, parent, student, etc.)

    Returns:
        Dict with user claims: user_id, tenant_id, email, role, permissions.

    Raises:
        HTTPException 401: Invalid token
        HTTPException 403: Cross-tenant or wrong role
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Validate token type
        if payload.get("type") != "access":
            raise credentials_exception

        # Check if token is blacklisted
        blacklist_service = await get_token_blacklist_service()
        if await blacklist_service.is_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user's tokens were mass-revoked
        token_iat = payload.get("iat")
        if token_iat and await blacklist_service.is_user_token_revoked(
            user_id, token_iat
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Cross-tenant validation
        token_tenant_id = payload.get("tenant_id")
        request_tenant_id = getattr(request.state, "tenant_id", None)

        if request_tenant_id and token_tenant_id:
            if str(token_tenant_id) != str(request_tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token not valid for this school.",
                )

        # Role check: must be applicant
        role = payload.get("role")
        if role != "applicant":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access restricted to applicant accounts.",
            )

        return {
            "user_id": user_id,
            "tenant_id": token_tenant_id,
            "email": payload.get("email"),
            "role": role,
            "permissions": payload.get("permissions", []),
        }

    except JWTError:
        raise credentials_exception


# Type alias for applicant user dependency
ApplicantUser = Annotated[dict, Depends(get_applicant_user)]
```

**Notes:**
- The role check (`role != "applicant"`) is performed after all standard JWT validation. This means invalid/expired/blacklisted tokens still get proper 401 responses, not 403.
- The return dict is intentionally smaller than `ValidatedUser` -- no `school_id`, `tenant_type`, or `accessible_school_ids` since applicants don't have multi-school access.
- The `ApplicantUser` type alias follows the same pattern as `ValidatedUser`.

---

## 2.7 Public Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/applicant_public.py`

These are **unauthenticated** endpoints for applicant account management. They use `PublicTenantSession` (tenant-scoped DB session from subdomain, no JWT required).

```python
"""
SIMS Plus - Applicant Account Public Endpoints

Unauthenticated endpoints for applicant registration, login, email
verification, and password reset. Tenant resolved from subdomain
via TenantMiddleware -> request.state.tenant_id.

Uses PublicTenantSession for tenant-scoped DB without JWT.

IMPORTANT: Do NOT use 'from __future__ import annotations' in this file.
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import PublicTenantSession
from app.schemas.applicant import (
    ApplicantForgotPasswordRequest,
    ApplicantLoginRequest,
    ApplicantLoginResponse,
    ApplicantProfileResponse,
    ApplicantRegisterRequest,
    ApplicantRegisterResponse,
    ApplicantResendVerificationRequest,
    ApplicantResetPasswordRequest,
    ApplicantVerifyEmailRequest,
)
from app.services.admissions.applicant_service import (
    ApplicantAccountError,
    ApplicantAccountService,
)

router = APIRouter(prefix="/public/applicant")


def _error_status(code: str) -> int:
    """Map service error codes to HTTP status codes."""
    status_map = {
        "NOT_FOUND": 404,
        "EMAIL_TAKEN": 409,
        "ALREADY_CLAIMED": 409,
        "CLAIM_FAILED": 400,
        "INVALID_CREDENTIALS": 401,
        "ACCOUNT_LOCKED": 423,
        "ACCOUNT_SUSPENDED": 403,
        "ACCOUNT_DEACTIVATED": 403,
        "EMAIL_NOT_VERIFIED": 403,
        "INVALID_TOKEN": 400,
        "CAPTCHA_FAILED": 400,
        "CAPTCHA_REQUIRED": 403,
        "EMAIL_MISMATCH": 403,
        "INVALID_PASSWORD": 400,
    }
    return status_map.get(code, 400)


@router.post(
    "/register",
    response_model=ApplicantRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new applicant account",
)
async def register_applicant(
    data: ApplicantRegisterRequest,
    request: Request,
    db: PublicTenantSession,
) -> ApplicantRegisterResponse:
    """
    Create a new applicant (prospective parent) account.

    Flow:
    1. Verify Cloudflare Turnstile token
    2. Check email uniqueness within this school's tenant
    3. Create user with role=applicant, status=pending
    4. Send email verification link
    5. Return user_id and confirmation message

    The account is NOT usable until the email is verified.

    Rate limit: 3/min/IP
    """
    service = ApplicantAccountService(db)
    try:
        tenant_id = request.state.tenant_id

        # Resolve default school for this tenant
        from sqlalchemy import select
        from app.models.school import School

        school_result = await db.execute(
            select(School.id).where(
                School.tenant_id == tenant_id,
                School.deleted_at.is_(None),
            ).limit(1)
        )
        school_id = school_result.scalar_one_or_none()
        if not school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="School not configured for this tenant.",
            )

        user = await service.register(
            tenant_id=tenant_id,
            school_id=school_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            password=data.password,
            turnstile_token=data.turnstile_token,
            remote_ip=request.client.host if request.client else None,
        )
        return ApplicantRegisterResponse(
            user_id=user.id,
            email=user.email,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/login",
    response_model=ApplicantLoginResponse,
    summary="Applicant login",
)
async def login_applicant(
    data: ApplicantLoginRequest,
    request: Request,
    db: PublicTenantSession,
) -> ApplicantLoginResponse:
    """
    Authenticate an applicant and issue JWT + refresh token.

    Validates:
    - Email exists with role=applicant in this tenant
    - Account is not locked (5 failed attempts -> 30-min cooldown)
    - Password is correct (Argon2id verification)
    - Email is verified (rejects unverified accounts)

    Returns access_token (15-min), refresh_token (7-day),
    and applicant profile data.

    Rate limit: 5/min/IP
    """
    service = ApplicantAccountService(db)
    try:
        # Note: access_token and refresh_token are returned in the JSON response body.
        # This is a systemic pattern inherited from staff login, accepted as-is for
        # consistency. HttpOnly cookies are the primary auth mechanism for the
        # frontend; the JSON body tokens serve API consumers and mobile clients.
        user, access_token, refresh_token = await service.login(
            tenant_id=request.state.tenant_id,
            email=data.email,
            password=data.password,
            turnstile_token=data.turnstile_token,
            remote_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return ApplicantLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=ApplicantProfileResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=user.phone,
                email_verified=user.email_verified,
                created_at=user.created_at,
            ),
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verify applicant email",
)
async def verify_email(
    data: ApplicantVerifyEmailRequest,
    request: Request,
    db: PublicTenantSession,
) -> dict:
    """
    Verify applicant's email address using token from verification link.

    After verification, the user's status changes from PENDING to ACTIVE
    and they can log in.

    Rate limit: 5/min/IP (default)
    """
    service = ApplicantAccountService(db)
    try:
        await service.verify_email(
            tenant_id=request.state.tenant_id,
            token=data.token,
        )
        return {"message": "Email verified successfully. You can now log in."}
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset email",
)
async def forgot_password(
    data: ApplicantForgotPasswordRequest,
    request: Request,
    db: PublicTenantSession,
) -> dict:
    """
    Send password reset email to applicant.

    Always returns success to prevent email enumeration.
    If the email exists and belongs to an applicant account,
    a reset link is sent.

    Rate limit: 3/min/IP
    """
    service = ApplicantAccountService(db)
    try:
        await service.forgot_password(
            tenant_id=request.state.tenant_id,
            email=data.email,
            turnstile_token=data.turnstile_token,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)

    return {"message": "If an account exists with that email, a reset link has been sent."}


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
)
async def reset_password(
    data: ApplicantResetPasswordRequest,
    request: Request,
    db: PublicTenantSession,
) -> dict:
    """
    Reset applicant password using token from email.

    After reset, all existing tokens are revoked (force re-login).

    Rate limit: 3/min/IP (shares limit with forgot-password)
    """
    service = ApplicantAccountService(db)
    try:
        await service.reset_password(
            tenant_id=request.state.tenant_id,
            token=data.token,
            password=data.password,
        )
        return {"message": "Password reset successfully. Please log in with your new password."}
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Resend email verification",
)
async def resend_verification(
    data: ApplicantResendVerificationRequest,
    request: Request,
    db: PublicTenantSession,
) -> dict:
    """
    Resend email verification to applicant.

    Always returns success to prevent email enumeration.
    Only sends if the email exists, belongs to an applicant,
    and is NOT already verified.

    Rate limit: 2/min/IP
    """
    service = ApplicantAccountService(db)
    try:
        await service.resend_verification(
            tenant_id=request.state.tenant_id,
            email=data.email,
            turnstile_token=data.turnstile_token,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)
    return {"message": "If an unverified account exists with that email, a verification link has been sent."}
```

---

## 2.8 Authenticated Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/applicant.py`

These endpoints require a valid JWT with `role=applicant`. They use `DatabaseSession` (tenant-scoped from JWT) and `ApplicantUser` (role-validated).

```python
"""
SIMS Plus - Applicant Account Authenticated Endpoints

Protected endpoints for applicant profile management, application
dashboard, drafts, document upload, payment initiation, print view,
and application claiming.

Uses DatabaseSession (tenant-scoped via JWT) + ApplicantUser (role=applicant).

IMPORTANT: Do NOT use 'from __future__ import annotations' in this file.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    ApplicantUser,
    DatabaseSession,
    require_permissions,
)
from app.schemas.admissions import (
    AdmissionDecisionResponse,
    ApplicationDocumentResponse,
    ApplicationGuardianResponse,
    ApplicationPaymentResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    StatusHistoryResponse,
)
from app.schemas.applicant import (
    ApplicantPasswordChange,
    ApplicantProfileResponse,
    ApplicantProfileUpdate,
    ClaimApplicationRequest,
    ClaimApplicationResponse,
    DraftApplicationCreate,
    DraftApplicationUpdate,
    DraftSubmitResponse,
    MyApplicationDetailResponse,
    MyApplicationListItem,
    MyApplicationListResponse,
    PrintableApplicationResponse,
    PrintableDecisionInfo,
    PrintableDocumentInfo,
    PrintableGuardianInfo,
    PrintablePaymentInfo,
)
from app.services.admissions.applicant_service import (
    ApplicantAccountError,
    ApplicantAccountService,
)
from app.services.admissions.application_service import (
    ApplicationService,
    ApplicationServiceError,
)

router = APIRouter(prefix="/applicant")


def _error_status(code: str) -> int:
    """Map service error codes to HTTP status codes."""
    status_map = {
        "NOT_FOUND": 404,
        "NOT_DRAFT": 409,
        "ALREADY_CLAIMED": 409,
        "CLAIM_FAILED": 400,
        "EMAIL_MISMATCH": 403,
        "INVALID_PASSWORD": 400,
        "MISSING_TARGET_CLASS": 422,
        "MISSING_DOB": 422,
        "MISSING_GENDER": 422,
        "NO_GUARDIANS": 422,
        "INCOMPLETE_GUARDIAN": 422,
        "VALIDATION_ERROR": 422,
        "PERIOD_NOT_OPEN": 400,
        "PERIOD_FULL": 400,
        "DAILY_CAP_EXCEEDED": 429,
    }
    return status_map.get(code, 400)


# =========================
# Profile Endpoints
# =========================


@router.get(
    "/profile",
    response_model=ApplicantProfileResponse,
    summary="Get applicant profile",
    dependencies=[Depends(require_permissions("applicant.profile.read"))],
)
async def get_profile(
    user: ApplicantUser,
    db: DatabaseSession,
) -> ApplicantProfileResponse:
    """
    Get the current applicant's profile information.
    User ID is extracted from JWT -- never from request params.
    """
    service = ApplicantAccountService(db)
    try:
        profile = await service.get_profile(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
        )
        return ApplicantProfileResponse(
            id=profile.id,
            email=profile.email,
            first_name=profile.first_name,
            last_name=profile.last_name,
            phone=profile.phone,
            email_verified=profile.email_verified,
            created_at=profile.created_at,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.put(
    "/profile",
    response_model=ApplicantProfileResponse,
    summary="Update applicant profile",
    dependencies=[Depends(require_permissions("applicant.profile.update"))],
)
async def update_profile(
    data: ApplicantProfileUpdate,
    user: ApplicantUser,
    db: DatabaseSession,
) -> ApplicantProfileResponse:
    """
    Update the current applicant's profile (name, phone).
    Email changes are not supported to preserve claim flow integrity.
    """
    service = ApplicantAccountService(db)
    try:
        profile = await service.update_profile(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
        )
        return ApplicantProfileResponse(
            id=profile.id,
            email=profile.email,
            first_name=profile.first_name,
            last_name=profile.last_name,
            phone=profile.phone,
            email_verified=profile.email_verified,
            created_at=profile.created_at,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.put(
    "/profile/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change applicant password",
    dependencies=[Depends(require_permissions("applicant.profile.update"))],
)
async def change_password(
    data: ApplicantPasswordChange,
    user: ApplicantUser,
    db: DatabaseSession,
) -> None:
    """
    Change the current applicant's password.
    Requires current password for verification.
    After change, all existing tokens are revoked.
    """
    service = ApplicantAccountService(db)
    try:
        await service.change_password(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
            current_password=data.current_password,
            new_password=data.new_password,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


# =========================
# My Applications Endpoints
# =========================


@router.get(
    "/applications",
    response_model=MyApplicationListResponse,
    summary="List my applications",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def list_my_applications(
    user: ApplicantUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
) -> MyApplicationListResponse:
    """
    List all applications belonging to the current applicant.

    Returns applications sorted by most recently updated.
    Supports pagination and optional status filtering.

    IDOR safe: user_id comes from JWT, not request params.
    """
    service = ApplicationService(db)
    try:
        applications, total = await service.list_my_applications(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            status=status_filter,
            page=page,
            page_size=page_size,
        )

        items = [
            MyApplicationListItem(
                id=app.id,
                tracking_code=app.tracking_code,
                applicant_first_name=app.applicant_first_name,
                applicant_last_name=app.applicant_last_name,
                target_class_name=app.target_class.name if app.target_class else None,
                admission_period_name=app.admission_period.name if app.admission_period else None,
                status=app.status,
                submitted_at=app.submitted_at,
                created_at=app.created_at,
                updated_at=app.updated_at,
            )
            for app in applications
        ]

        return MyApplicationListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.get(
    "/applications/{application_id}",
    response_model=MyApplicationDetailResponse,
    summary="Get my application detail",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def get_my_application(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> MyApplicationDetailResponse:
    """
    Get a single application owned by the current applicant.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    Returns application with guardians, documents, payments, status history,
    and decision.
    """
    service = ApplicationService(db)
    try:
        app = await service.get_my_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )
        return MyApplicationDetailResponse(
            id=app.id,
            tenant_id=app.tenant_id,
            tracking_code=app.tracking_code,
            admission_period_id=app.admission_period_id,
            admission_period_name=app.admission_period.name if app.admission_period else None,
            applicant_first_name=app.applicant_first_name,
            applicant_last_name=app.applicant_last_name,
            applicant_other_names=app.applicant_other_names,
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            nationality=app.nationality,
            target_class_id=app.target_class_id,
            target_class_name=app.target_class.name if app.target_class else None,
            status=app.status,
            custom_fields=app.custom_fields or {},
            fee_waived=app.fee_waived,
            exam_waived=app.exam_waived,
            applicant_photo_url=app.applicant_photo_url,
            previous_school=app.previous_school,
            medical_info=app.medical_info,
            submitted_at=app.submitted_at,
            created_at=app.created_at,
            updated_at=app.updated_at,
            guardians=[g for g in (app.guardians or []) if g.deleted_at is None],
            documents=[d for d in (app.documents or []) if d.deleted_at is None],
            payments=[p for p in (app.payments or []) if p.deleted_at is None],
            status_history=list(app.status_history or []),
            decision=app.decision if app.decision and app.decision.deleted_at is None else None,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications",
    response_model=DraftSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create draft application",
    dependencies=[Depends(require_permissions("applicant.applications.create"))],
)
async def create_draft(
    data: DraftApplicationCreate,
    request: Request,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DraftSubmitResponse:
    """
    Create a new draft application for a child.

    The application starts in DRAFT status and can be updated
    multiple times before submission. Only admission_period_id
    and child name are required to start.

    No Turnstile required (user is authenticated).
    """
    service = ApplicationService(db)
    try:
        # Resolve default school for this tenant
        from sqlalchemy import select as sa_select
        from app.models.school import School

        tenant_id = UUID(user["tenant_id"])
        school_result = await db.execute(
            sa_select(School.id).where(
                School.tenant_id == tenant_id,
                School.deleted_at.is_(None),
            ).limit(1)
        )
        school_id = school_result.scalar_one_or_none()
        if not school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="School not configured for this tenant.",
            )

        application = await service.create_draft(
            tenant_id=tenant_id,
            school_id=school_id,
            applicant_user_id=UUID(user["user_id"]),
            admission_period_id=data.admission_period_id,
            applicant_first_name=data.applicant_first_name,
            applicant_last_name=data.applicant_last_name,
            applicant_other_names=data.applicant_other_names,
            date_of_birth=str(data.date_of_birth) if data.date_of_birth else None,
            gender=data.gender,
            nationality=data.nationality,
            target_class_id=data.target_class_id,
            previous_school=data.previous_school,
            medical_info=data.medical_info,
            custom_fields=data.custom_fields,
            guardians=(
                [g.model_dump(exclude_none=True) for g in data.guardians]
                if data.guardians
                else None
            ),
        )

        return DraftSubmitResponse(
            id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
            payment_required=False,  # Draft — payment only checked on submit
            application_fee_amount=None,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.put(
    "/applications/{application_id}",
    response_model=DraftSubmitResponse,
    summary="Update draft application",
    dependencies=[Depends(require_permissions("applicant.applications.update"))],
)
async def update_draft(
    application_id: UUID,
    data: DraftApplicationUpdate,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DraftSubmitResponse:
    """
    Update an existing draft application (auto-save on each wizard step).

    Only DRAFT applications can be updated.
    All fields are optional for partial save.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    """
    service = ApplicationService(db)
    try:
        application = await service.update_draft(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
            applicant_first_name=data.applicant_first_name,
            applicant_last_name=data.applicant_last_name,
            applicant_other_names=data.applicant_other_names,
            date_of_birth=str(data.date_of_birth) if data.date_of_birth else None,
            gender=data.gender,
            nationality=data.nationality,
            target_class_id=data.target_class_id,
            previous_school=data.previous_school,
            medical_info=data.medical_info,
            custom_fields=data.custom_fields,
            guardians=(
                [g.model_dump(exclude_none=True) for g in data.guardians]
                if data.guardians
                else None
            ),
        )

        return DraftSubmitResponse(
            id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
            payment_required=False,
            application_fee_amount=None,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications/{application_id}/submit",
    response_model=DraftSubmitResponse,
    summary="Submit draft application",
    dependencies=[Depends(require_permissions("applicant.applications.submit"))],
)
async def submit_draft(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DraftSubmitResponse:
    """
    Submit a draft application after filling all required fields.

    Full validation is performed:
    - target_class_id, date_of_birth, gender must be set
    - At least one guardian with complete info required
    - custom_fields validated against form_schema

    If fee is required and not paid/waived, status stays DRAFT.
    If fee is not required, status transitions to SUBMITTED.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    """
    service = ApplicationService(db)
    try:
        application = await service.submit_draft(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )

        # Determine if payment is still required
        payment_required = (
            application.status == "draft"
            and not application.fee_waived
        )

        return DraftSubmitResponse(
            id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
            payment_required=payment_required,
            application_fee_amount=None,  # Populated from period if needed
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document to application",
    dependencies=[Depends(require_permissions("applicant.applications.update"))],
)
async def upload_document(
    application_id: UUID,
    data: DocumentUploadRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DocumentUploadResponse:
    """
    Request a presigned S3 URL for document upload on an application.

    IDOR protection: verifies application ownership before generating URL.

    Validation:
    - Application must be in DRAFT or SUBMITTED status
    - Max 5 documents per application
    - File size max 5MB
    - MIME: application/pdf, image/jpeg, image/png
    """
    # First verify ownership
    app_service = ApplicationService(db)
    try:
        await app_service.get_my_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)

    # Delegate to existing document upload logic
    try:
        return await app_service.upload_document_by_id(
            application_id=application_id,
            data=data,
            tenant_id=UUID(user["tenant_id"]),
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications/{application_id}/pay",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate payment for application",
    dependencies=[Depends(require_permissions("applicant.applications.update"))],
)
async def initiate_payment(
    application_id: UUID,
    data: PaymentInitiateRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> PaymentInitiateResponse:
    """
    Initialize Paystack payment for application fee.

    IDOR protection: verifies application ownership before initiating.

    The payment flow is identical to the anonymous flow except:
    - User is identified (for receipt/history)
    - Application is already linked to the account
    """
    # Verify ownership
    app_service = ApplicationService(db)
    try:
        application = await app_service.get_my_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)

    # Delegate to existing payment service
    from app.services.admissions.payment_service import (
        ApplicationPaymentService,
        PaymentServiceError,
    )

    payment_service = ApplicationPaymentService(db)
    try:
        return await payment_service.initiate_payment_by_id(
            application_id=application_id,
            data=data,
            tenant_id=UUID(user["tenant_id"]),
        )
    except PaymentServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.get(
    "/applications/{application_id}/print",
    response_model=PrintableApplicationResponse,
    summary="Get printable application view",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def get_printable_application(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> PrintableApplicationResponse:
    """
    Get full application data formatted for server-rendered print view.

    Loads all relations: guardians, documents, payments, decision,
    admission period, target class, and school info.

    Does NOT include internal notes or status history.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    """
    service = ApplicationService(db)
    try:
        app = await service.get_printable_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )

        # Build response with nested relation data
        return PrintableApplicationResponse(
            id=app.id,
            tracking_code=app.tracking_code,
            school_name=app.school.name if app.school else "",
            school_logo_url=getattr(app.school, "logo_url", None) if app.school else None,
            admission_period_name=(
                app.admission_period.name if app.admission_period else ""
            ),
            applicant_first_name=app.applicant_first_name,
            applicant_last_name=app.applicant_last_name,
            applicant_other_names=app.applicant_other_names,
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            nationality=app.nationality,
            target_class_name=(
                app.target_class.name if app.target_class else ""
            ),
            previous_school=app.previous_school,
            medical_info=app.medical_info,
            custom_fields=app.custom_fields,
            status=app.status,
            submitted_at=app.submitted_at,
            created_at=app.created_at,
            guardians=[
                PrintableGuardianInfo(
                    first_name=g.first_name,
                    last_name=g.last_name,
                    phone=g.phone,
                    email=g.email,
                    relationship=g.relationship,
                    is_primary=g.is_primary,
                    occupation=g.occupation,
                    address=g.address,
                )
                for g in (app.guardians or [])
                if g.deleted_at is None
            ],
            documents=[
                PrintableDocumentInfo(
                    document_type=d.document_type,
                    file_name=d.file_name,
                    created_at=d.created_at,
                )
                for d in (app.documents or [])
                if d.deleted_at is None
            ],
            payments=[
                PrintablePaymentInfo(
                    amount=p.amount,
                    currency=p.currency,
                    payment_method=p.payment_method,
                    status=p.status,
                    paid_at=p.paid_at,
                )
                for p in (app.payments or [])
                if p.deleted_at is None
            ],
            decision=(
                PrintableDecisionInfo(
                    decision_type=app.decision.decision_type,
                    offered_class_name=None,  # Could be populated from decision.offered_class
                    conditions=app.decision.conditions,
                    decision_date=app.decision.decision_date,
                    response_deadline=app.decision.response_deadline,
                )
                if app.decision and app.decision.deleted_at is None
                else None
            ),
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


# =========================
# Guardian Pre-fill
# =========================


@router.get(
    "/applications/guardian-prefill",
    response_model=list[ApplicationGuardianResponse],
    summary="Get guardian info for pre-fill",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def get_guardian_prefill(
    user: ApplicantUser,
    db: DatabaseSession,
):
    """
    Get guardian info from the most recent submitted application.
    Used for pre-filling the guardian section when creating a new application
    for another child. Returns empty list if no previous applications exist.
    """
    service = ApplicationService(db)
    guardians = await service.get_latest_guardian_info(
        tenant_id=UUID(user["tenant_id"]),
        applicant_user_id=UUID(user["user_id"]),
    )
    return guardians


# =========================
# Claim Application
# =========================


@router.post(
    "/applications/claim",
    response_model=ClaimApplicationResponse,
    summary="Claim an anonymous application",
    dependencies=[Depends(require_permissions("applicant.applications.claim"))],
)
async def claim_application(
    data: ClaimApplicationRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> ClaimApplicationResponse:
    """
    Claim a previously anonymous application by tracking code.

    Requires:
    1. Valid tracking code for an application in this tenant
    2. Application must not already be linked to an account
    3. At least one guardian email on the application must match
       the applicant's account email

    After claiming, the application appears in the applicant's dashboard.
    """
    service = ApplicantAccountService(db)
    try:
        application = await service.claim_application(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
            tracking_code=data.tracking_code,
        )
        return ClaimApplicationResponse(
            application_id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)
```

**IDOR Prevention Pattern:**

Every endpoint that accesses application data extracts `user_id` from the JWT via `ApplicantUser` dependency. The `user_id` is NEVER taken from request body, query params, or URL path. The service layer then filters by `Application.applicant_user_id == user_id` in every query. Even if an attacker guesses a valid `application_id`, the query returns nothing because the IDOR filter prevents cross-user access.

---

## 2.9 Middleware Updates

### PUBLIC_PATH_PREFIXES

**File:** `backend/app/middleware/tenant.py`

Add the applicant public path to `PUBLIC_PATH_PREFIXES`. These paths skip subdomain resolution **only for the webhook**. The applicant register/login endpoints NEED subdomain resolution (to know which school) so they are NOT added here.

```python
PUBLIC_PATH_PREFIXES = (
    # ... existing entries ...
    "/api/v1/admissions/public/webhook/",   # Paystack webhook — tenant from metadata, not subdomain
    # NOTE: /api/v1/admissions/public/applicant/ is NOT here because it needs
    # subdomain resolution for tenant context. It IS in deps.py _PUBLIC_PATH_PREFIXES
    # which skips JWT auth but keeps tenant resolution.
)
```

**No change needed.** The applicant public endpoints are under `/api/v1/admissions/public/applicant/` which is already covered by the existing `_PUBLIC_PATH_PREFIXES` entry in `deps.py`:

```python
# In deps.py (already exists)
_PUBLIC_PATH_PREFIXES = (
    # ...
    "/api/v1/admissions/public/",  # Covers ALL public admissions endpoints
)
```

Since `/api/v1/admissions/public/applicant/register` starts with `/api/v1/admissions/public/`, it is already excluded from JWT auth by `_is_public_path()` in `deps.py`. No changes needed in either middleware file for path resolution.

### Rate Limit Updates

**File:** `backend/app/middleware/rate_limit.py`

Add applicant-specific rate limits to `ENDPOINT_LIMITS`:

```python
ENDPOINT_LIMITS = {
    # ... existing entries ...
    "/api/v1/admissions/public/applications": ("admissions_submit", "admissions_submit"),

    # Applicant account rate limits — separate from general auth limits
    "/api/v1/admissions/public/applicant/register": ("applicant_register", "applicant_register"),
    "/api/v1/admissions/public/applicant/login": ("auth", "auth"),
    "/api/v1/admissions/public/applicant/forgot-password": ("applicant_register", "applicant_register"),
    "/api/v1/admissions/public/applicant/reset-password": ("applicant_register", "applicant_register"),
    "/api/v1/admissions/public/applicant/resend-verification": ("applicant_resend", "applicant_resend"),
}
```

Add rate limit type handling in `_get_rate_limit()`:

```python
elif limit_type == "applicant_register":
    return (
        settings.RATE_LIMIT_APPLICANT_REGISTER_REQUESTS,
        settings.RATE_LIMIT_APPLICANT_REGISTER_WINDOW,
        key_prefix,
    )
elif limit_type == "applicant_resend":
    return (
        settings.RATE_LIMIT_APPLICANT_RESEND_REQUESTS,
        settings.RATE_LIMIT_APPLICANT_RESEND_WINDOW,
        key_prefix,
    )
```

**File:** `backend/app/config.py` (or `backend/app/core/config.py`)

Add rate limit config:

```python
# Applicant account rate limits
RATE_LIMIT_APPLICANT_REGISTER_REQUESTS: int = 3
RATE_LIMIT_APPLICANT_REGISTER_WINDOW: int = 60     # 3 per minute per IP
RATE_LIMIT_APPLICANT_RESEND_REQUESTS: int = 2
RATE_LIMIT_APPLICANT_RESEND_WINDOW: int = 60        # 2 per minute per IP
```

**Rate Limit Summary:**

| Endpoint | Limit | Window | Type |
|----------|-------|--------|------|
| `/applicant/register` | 3/min | 60s | `applicant_register` |
| `/applicant/login` | 5/min | 60s | `auth` (reuses existing) |
| `/applicant/forgot-password` | 3/min | 60s | `applicant_register` (shared) |
| `/applicant/reset-password` | 3/min | 60s | `applicant_register` (shared) |
| `/applicant/resend-verification` | 2/min | 60s | `applicant_resend` |
| `/applicant/verify-email` | 100/min | 60s | `default` (standard) |

**Design choice:** The login endpoint reuses the existing `auth` rate limit type (5/min) for consistency with the staff login. Register, forgot-password, and reset-password share the `applicant_register` limit (3/min) since they all involve expensive operations (Turnstile verification, email sending, password hashing). Resend-verification gets its own stricter limit (2/min) to prevent email spam.

---

## 2.10 Register Routers

**File:** `backend/app/api/v1/endpoints/admissions/__init__.py`

Add the new applicant routers to the existing admissions router assembly:

```python
# ... existing imports ...
from app.api.v1.endpoints.admissions.applicant import router as applicant_router
from app.api.v1.endpoints.admissions.applicant_public import router as applicant_public_router

# ... existing router setup ...

# Applicant account routers
router.include_router(applicant_public_router, tags=["Applicant (Public)"])
router.include_router(applicant_router, tags=["Applicant (Authenticated)"])
```

The `applicant_public_router` has prefix `/public/applicant`, so the full path becomes:
- `/api/v1/admissions/public/applicant/register`
- `/api/v1/admissions/public/applicant/login`
- etc.

The `applicant_router` has prefix `/applicant`, so the full path becomes:
- `/api/v1/admissions/applicant/profile`
- `/api/v1/admissions/applicant/applications`
- etc.

---

## 2.11 Update Services `__init__.py`

**File:** `backend/app/services/admissions/__init__.py`

Add re-export for the new service:

```python
# ... existing exports ...
from app.services.admissions.applicant_service import (
    ApplicantAccountError,
    ApplicantAccountService,
)

__all__ = [
    # ... existing ...
    "ApplicantAccountError",
    "ApplicantAccountService",
]
```

---

## Summary of All Files

### New Files (3)

| File | Purpose |
|------|---------|
| `backend/app/schemas/applicant.py` | 18 Pydantic schemas for applicant endpoints |
| `backend/app/services/admissions/applicant_service.py` | Account service (register, login, profile, claim, verify, reset) |
| `backend/app/api/v1/endpoints/admissions/applicant_public.py` | 6 public endpoints (register, login, verify, forgot, reset, resend) |
| `backend/app/api/v1/endpoints/admissions/applicant.py` | 12 authenticated endpoints (profile, apps, drafts, claim, print) |

### Modified Files (8)

| File | Change |
|------|--------|
| `backend/app/services/admissions/application_service.py` | Add `applicant_user_id` to `submit()`, add 6 new methods |
| `backend/app/services/admissions/enrollment_service.py` | Add role promotion logic in `enroll()` |
| `backend/app/services/auth.py` | Add `applicant` to `ROLE_PERMISSIONS` |
| `backend/app/services/admissions/__init__.py` | Re-export `ApplicantAccountService` |
| `backend/app/api/deps.py` | Add `get_applicant_user()` dependency + `ApplicantUser` alias |
| `backend/app/api/v1/endpoints/admissions/__init__.py` | Include applicant routers |
| `backend/app/middleware/rate_limit.py` | Add applicant rate limit entries |
| `backend/app/config.py` | Add applicant rate limit settings |

### Dependencies

- No new Python packages required.
- All dependencies (Argon2id, JWT, Turnstile, Paystack) are already in `requirements.txt`.

### Assumptions

1. **`EmailVerificationService.create_and_send_verification(user_id, email)`** exists in `app.services.email_verification` and sends a verification email with a token link.
2. **`EmailVerificationService.verify_email(token, ip_address)`** exists and verifies the email, returning the verified User.
3. **`EmailVerificationService.resend_verification(email)`** exists for resending verification emails.
4. **`PasswordResetService.request_reset(email, ip_address)`** exists in `app.services.password_reset` and sends a reset email.
5. **`PasswordResetService.reset_password(token, new_password, ip_address)`** exists and handles token validation, password hashing, and token revocation.
6. **`AuthService.revoke_all_user_tokens(user_id)`** exists for mass token revocation.
7. **`AuthService.create_access_token(user)`** and **`AuthService.create_refresh_token(user)`** exist and include the user's role and permissions in JWT claims.
8. **`ApplicationService.upload_document_by_id()`** and **`ApplicationPaymentService.initiate_payment_by_id()`** are minor variants of existing tracking-code-based methods that accept `application_id` directly. If they don't exist, they are thin wrappers around the existing methods.
9. **School resolution:** The register and create_draft endpoints resolve school_id by querying the School table for the first active school in the tenant, rather than relying on `request.state.school_id`. This ensures correct behavior for both single-school and multi-school tenants.
