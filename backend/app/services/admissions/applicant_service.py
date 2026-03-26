"""
SIMS Plus - Applicant Account Service

Handles applicant registration, authentication, profile management,
email verification, password reset, and application claiming.

This service reuses the existing User model and auth infrastructure
(Argon2id hashing, JWT issuance, account lockout, token blacklisting)
but scoped to the 'applicant' role with separate endpoints.
"""

import uuid
from datetime import UTC, datetime, timedelta

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
        5. Send email verification (via existing EmailVerificationService)
        6. Return user (without password hash)

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
            from app.models.tenant import Tenant

            verification_service = EmailVerificationService(self.db)

            # Create verification token (requires tenant_id for token data)
            token = await verification_service.create_verification_token(
                user_id=user.id,
                tenant_id=tenant_id,
                email=normalized_email,
            )

            if token:
                # Fetch tenant subdomain for the verification URL
                subdomain_result = await self.db.execute(
                    select(Tenant.subdomain).where(Tenant.id == tenant_id)
                )
                subdomain = subdomain_result.scalar_one_or_none() or ""

                await verification_service.send_verification_email(
                    email=normalized_email,
                    token=token,
                    subdomain=subdomain,
                    first_name=first_name.strip(),
                )
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

        Steps (anti-enumeration order -- password verified before revealing
        account state to prevent leaking email existence via error codes):
        1. Find user by email + tenant_id + role=applicant
        2. Verify password (generic error if wrong; increment failed_login_attempts)
        3. Check account lockout (only after correct password)
        4. Adaptive CAPTCHA after 3 failures
        5. Check email_verified
        6. Check suspended/deactivated (admin actions, safe after correct password)
        7. Reset failed attempts + update last_login
        8. Issue JWT + refresh token, return (user, access_token, refresh_token)

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

        # 2. Verify password FIRST (anti-enumeration: don't reveal account
        #    state before correct password -- prevents leaking email existence
        #    via differing error codes like 423 vs 401)
        from app.core.security import verify_password

        if not verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            # Lock account after too many attempts (matches AuthService lockout policy)
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(UTC) + timedelta(minutes=30)
            await self.db.flush()

            raise ApplicantAccountError(
                "Invalid email or password.",
                code="INVALID_CREDENTIALS",
            )

        # 3. Password is correct -- now check account lockout
        #    (correct password + locked = attacker already has password,
        #    safe to reveal locked status)
        if user.locked_until and user.locked_until > datetime.now(UTC):
            raise ApplicantAccountError(
                "Account is temporarily locked due to too many failed attempts. "
                "Please try again later.",
                code="ACCOUNT_LOCKED",
            )

        # 4. Adaptive CAPTCHA: require Turnstile after 3 failed attempts
        if user.failed_login_attempts and user.failed_login_attempts >= 3:
            if not turnstile_token or not await verify_turnstile(turnstile_token, remote_ip=remote_ip):
                raise ApplicantAccountError(
                    "CAPTCHA verification required after multiple failed attempts.",
                    code="CAPTCHA_REQUIRED",
                )

        # 5. Check email verification
        if not user.email_verified:
            raise ApplicantAccountError(
                "Please verify your email address before logging in. "
                "Check your inbox or request a new verification email.",
                code="EMAIL_NOT_VERIFIED",
            )

        # 6. Check account status (admin actions -- safe to reveal after correct password)
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

        # 7. Reset failed attempts + update last_login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(UTC)
        await self.db.flush()

        # 8. Issue JWT tokens matching AuthService.authenticate() structure.
        # Must include tenant_subdomain in extra_claims so downstream JWT
        # validation (e.g. ValidatedTokenTenant) works correctly.
        from app.core.security import create_access_token, create_refresh_token
        from app.models.tenant import Tenant
        from app.services.auth import AuthService

        permissions = AuthService.get_role_permissions(user.role.value)

        # Fetch tenant subdomain for JWT claims (matches AuthService._build_extra_claims)
        subdomain_result = await self.db.execute(
            select(Tenant.subdomain).where(Tenant.id == user.tenant_id)
        )
        tenant_subdomain = subdomain_result.scalar_one_or_none() or ""

        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            school_id=str(user.school_id) if user.school_id else None,
            role=user.role.value,
            permissions=permissions,
            extra_claims={
                "email": user.email,
                "tenant_subdomain": tenant_subdomain,
            },
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
        )

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
            from app.services.token_blacklist import get_token_blacklist_service

            blacklist = await get_token_blacklist_service()
            await blacklist.blacklist_user_tokens(str(user_id))
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

        Raises:
            ApplicantAccountError: If token invalid, expired, or user not applicant.
        """
        from app.services.email_verification import EmailVerificationService

        verification_service = EmailVerificationService(self.db)

        # Pre-validate token to extract user_id and tenant_id before consuming it.
        # This lets us verify the user is an applicant in the correct tenant
        # before the token gets deleted by verify_email().
        token_data = await verification_service.validate_verification_token(token)
        if not token_data:
            raise ApplicantAccountError(
                "Invalid or expired verification link.",
                code="INVALID_TOKEN",
            )

        token_user_id, token_tenant_id, _token_email = token_data

        # Defense-in-depth: verify tenant matches before consuming token
        if str(token_tenant_id) != str(tenant_id):
            raise ApplicantAccountError(
                "Invalid verification link.",
                code="INVALID_TOKEN",
            )

        # Pre-check that user is an applicant (avoid consuming token for non-applicant)
        pre_check = await self.db.execute(
            select(User).where(
                User.id == token_user_id,
                User.tenant_id == tenant_id,
                User.role == UserRole.APPLICANT.value,
                User.deleted_at.is_(None),
            )
        )
        if pre_check.scalar_one_or_none() is None:
            raise ApplicantAccountError(
                "Invalid verification link.",
                code="INVALID_TOKEN",
            )

        # Now consume the token: verify_email() returns bool, handles
        # setting email_verified=True and activating the user
        try:
            await verification_service.verify_email(token=token, ip_address=None)
        except Exception:
            raise ApplicantAccountError(
                "Invalid or expired verification link.",
                code="INVALID_TOKEN",
            )

        # Fetch the updated user to return
        result = await self.db.execute(
            select(User).where(
                User.id == token_user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
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
                await reset_service.request_password_reset(
                    email=normalized_email,
                    tenant_id=tenant_id,
                    ip_address=None,
                )
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

        Pre-validates that the token belongs to an applicant in this tenant
        before consuming the token via PasswordResetService.

        Steps:
        1. Validate token to extract user_id (non-destructive -- does not consume)
        2. Look up user and verify role=applicant + tenant_id matches
        3. Delegate to PasswordResetService.reset_password() which handles
           hashing, token deletion, and mass token revocation

        Raises:
            ApplicantAccountError: If token invalid/expired or user not applicant.
        """
        from app.services.password_reset import PasswordResetService

        reset_service = PasswordResetService(self.db)

        # 1. Pre-validate: extract user_id from token without consuming it
        token_data = await reset_service.validate_reset_token(token)
        if not token_data:
            raise ApplicantAccountError(
                "Invalid or expired reset link.",
                code="INVALID_TOKEN",
            )

        token_user_id, token_tenant_id = token_data

        # 2. Verify the user is an applicant in this tenant (defense-in-depth)
        result = await self.db.execute(
            select(User).where(
                User.id == token_user_id,
                User.tenant_id == tenant_id,
                User.role == UserRole.APPLICANT.value,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ApplicantAccountError(
                "Invalid or expired reset link.",
                code="INVALID_TOKEN",
            )

        # 3. Verify token's tenant matches request tenant
        if str(token_tenant_id) != str(tenant_id):
            raise ApplicantAccountError(
                "Invalid or expired reset link.",
                code="INVALID_TOKEN",
            )

        # 4. Proceed with actual reset (consumes the token)
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
            user_id=str(token_user_id),
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
                await verification_service.resend_verification(
                    email=normalized_email,
                    tenant_id=tenant_id,
                )
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

    # ================================================================
    # Offer Response (Enrollment Gap Closure Phase 2)
    # ================================================================

    async def respond_to_offer(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        response: str,
        notes: str | None = None,
    ) -> Application:
        """
        Accept or decline an admission offer.

        Validations:
        1. Application exists and belongs to this tenant
        2. IDOR check: application.applicant_user_id == user_id (AD-5)
        3. Application status must be 'offered'
        4. Response must be 'accepted' or 'declined'

        Effects:
        - accepted: status -> ACCEPTED, offer_responded_at, offer_response
        - declined: status -> WITHDRAWN, offer_responded_at, offer_response

        Sends notification to school admissions office.
        """
        from app.models.admissions import (
            AdmissionApplicationStatus,
            ApplicationStatusHistory,
            VALID_TRANSITIONS,
        )

        application = await self._get_applicant_application(
            tenant_id, application_id, user_id
        )

        if application.status != AdmissionApplicationStatus.OFFERED.value:
            raise ApplicantAccountError(
                "This application is not in 'offered' status. Cannot respond to offer.",
                code="INVALID_STATUS",
            )

        valid_responses = {"accepted", "declined"}
        if response not in valid_responses:
            raise ApplicantAccountError(
                f"Invalid response: must be one of {valid_responses}",
                code="INVALID_RESPONSE",
            )

        # Determine target status based on applicant's response
        if response == "accepted":
            target_status = AdmissionApplicationStatus.ACCEPTED
        else:
            target_status = AdmissionApplicationStatus.WITHDRAWN

        # Validate transition is allowed by the state machine
        current = AdmissionApplicationStatus(application.status)
        allowed = VALID_TRANSITIONS.get(current, [])
        if target_status not in allowed:
            raise ApplicantAccountError(
                f"Cannot transition from {current.value} to {target_status.value}",
                code="INVALID_TRANSITION",
            )

        # Update application with response data
        old_status = application.status
        application.status = target_status.value
        application.offer_responded_at = datetime.now(UTC)
        application.offer_response = response
        application.offer_response_notes = notes

        # Append to status history for audit trail
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application.id,
            from_status=old_status,
            to_status=target_status.value,
            changed_by=user_id,
            reason=(
                f"Applicant {'accepted' if response == 'accepted' else 'declined'} offer"
                + (f": {notes}" if notes else "")
            ),
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)

        # Send notification to school admissions office (best effort)
        try:
            from app.services.admissions.notification_service import (
                AdmissionNotificationService,
            )

            notifier = AdmissionNotificationService(self.db)
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application.id,
                new_status=f"offer_{response}",
                extra_context={},
            )
        except Exception:
            logger.exception("offer_response_notification_failed")

        logger.info(
            "offer_responded",
            application_id=str(application_id),
            response=response,
            user_id=str(user_id),
        )
        return application

    async def get_offer_details(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
    ) -> dict:
        """
        Get full offer details for the applicant portal.

        IDOR check: verifies application.applicant_user_id == user_id.
        Returns decision + conditions + deadline + letter URL + response status.
        """
        from app.models.admissions import AdmissionDecision
        from app.models.academic import Class

        application = await self._get_applicant_application(
            tenant_id, application_id, user_id
        )

        # Load associated decision record
        decision_result = await self.db.execute(
            select(AdmissionDecision).filter(
                AdmissionDecision.application_id == application.id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                AdmissionDecision.tenant_id == tenant_id,
            )
        )
        decision = decision_result.scalar_one_or_none()
        if not decision:
            raise ApplicantAccountError(
                "No decision found for this application",
                code="NOT_FOUND",
            )

        # Load school name for display
        from app.models.school import School

        school_result = await self.db.execute(
            select(School.name).filter(
                School.id == application.school_id,
                School.tenant_id == tenant_id,
            )
        )
        school_name = school_result.scalar_one_or_none() or ""

        # Load offered class name if present
        offered_class_name = None
        if decision.offered_class_id:
            cls_result = await self.db.execute(
                select(Class.name).filter(
                    Class.id == decision.offered_class_id,
                    Class.tenant_id == tenant_id,
                )
            )
            offered_class_name = cls_result.scalar_one_or_none()

        # Generate presigned URL for admission letter if it exists
        letter_url = None
        if decision.decision_letter_url:
            from app.services.s3 import get_s3_service

            s3 = get_s3_service()
            letter_url = s3.generate_presigned_url(
                decision.decision_letter_url, expires_in=3600
            )

        # Check if the offer has expired (deadline passed without response)
        is_expired = False
        if (
            decision.response_deadline
            and application.offer_responded_at is None
            and decision.response_deadline < datetime.now(UTC).date()
        ):
            is_expired = True

        return {
            "application_id": application.id,
            "applicant_name": f"{application.applicant_first_name} {application.applicant_last_name}",
            "tracking_code": application.tracking_code,
            "school_name": school_name,
            "offered_class_name": offered_class_name,
            "decision_type": decision.decision_type,
            "decision_date": decision.decision_date,
            "conditions": decision.conditions,
            "response_deadline": decision.response_deadline,
            "decision_letter_url": letter_url,
            "offer_responded_at": application.offer_responded_at,
            "offer_response": application.offer_response,
            "offer_response_notes": application.offer_response_notes,
            "is_expired": is_expired,
        }

    async def _get_applicant_application(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Application:
        """
        Get application with IDOR check: applicant_user_id must match user_id.

        Only registered applicants (AD-5) can access their applications.
        Returns generic NOT_FOUND for both missing and unauthorized to prevent
        leaking information about other applicants' applications.
        """
        result = await self.db.execute(
            select(Application).filter(
                Application.id == application_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = result.scalar_one_or_none()
        if not application:
            raise ApplicantAccountError("Application not found", code="NOT_FOUND")

        # IDOR check: only the owning applicant can interact with this application
        if str(application.applicant_user_id) != str(user_id):
            raise ApplicantAccountError("Application not found", code="NOT_FOUND")

        return application
