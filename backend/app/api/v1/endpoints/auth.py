"""
SIMS Plus - Authentication Endpoints

API endpoints for user authentication.
"""

import logging
from typing import Annotated
from uuid import UUID as UUIDType

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    get_db,
    get_tenant_from_request,
    RequestTenant,
    ValidatedTokenTenant,
    oauth2_scheme,
)
from app.config import settings
from app.middleware.tenant import TenantContext
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdateRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    SessionListResponse,
    SessionResponse,
    TokenResponse,
    UserMeResponse,
    UserResponse,
    TenantInfo,
    VerifyEmailRequest,
)
from app.schemas.mfa import (
    MFABackupCodesResponse,
    MFADisableRequest,
    MFARequiredResponse,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyLoginRequest,
    MFAVerifySetupRequest,
)
from app.schemas.otp import (
    ForgotPasswordSMSRequest,
    ResetPasswordSMSRequest,
    SendPhoneOTPResponse,
    VerifyPhoneRequest,
)
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update

from app.models.user import User, UserStatus
from app.models.school import School
from app.services.auth import AuthService, AuthenticationError
from app.services.audit import AuditService, AuditEventType
from app.services.session import SessionService, parse_user_agent
from app.services.mfa import MFAService, MFAError
from app.services.otp import OTPService, OTPPurpose, OTPError
from app.services.token_blacklist import get_token_blacklist_service
from app.services.password_reset import PasswordResetService, PasswordResetError
from app.services.email_verification import EmailVerificationService, EmailVerificationError
from app.services.email import email_service
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, handling proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _get_user_agent(request: Request) -> str | None:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


def _get_jti_from_token(token: str) -> str | None:
    """Extract the JTI (JWT ID) from a token without full verification.

    Used to link sessions to tokens for deactivation on logout.
    """
    try:
        payload = jose_jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
        return payload.get("jti")
    except Exception:
        return None


def _get_session_context_from_token(
    token: str,
) -> tuple[UUIDType, UUIDType, str | None]:
    """Extract user_id, tenant_id, and current JTI from an access token.

    Decodes without expiry verification so it works for session management
    endpoints that need context even from near-expired tokens.

    Returns:
        Tuple of (user_id, tenant_id, current_jti)
    """
    payload = jose_jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_exp": False},
    )
    user_id = UUIDType(payload["sub"])
    tenant_id = UUIDType(payload["tenant_id"])
    current_jti = payload.get("jti")
    return user_id, tenant_id, current_jti


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
    description="Authenticate user with email and password. Returns JWT tokens.",
)
async def login(
    request: Request,
    credentials: LoginRequest,
    db: DatabaseSession,
) -> LoginResponse:
    """
    Authenticate user and return tokens.

    - **email**: User's email address
    - **password**: User's password
    - **remember_me**: If true, extends refresh token validity

    Returns access token, refresh token, and user info.
    """
    # Get tenant from request (set by middleware)
    tenant_id = getattr(request.state, "tenant_id", None)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please access your school's login page",
        )

    auth_service = AuthService(db)

    # Get client info for audit logging
    client_ip = _get_client_ip(request)
    user_agent = _get_user_agent(request)

    try:
        result = await auth_service.authenticate(
            email=credentials.email,
            password=credentials.password,
            tenant_id=tenant_id,
            ip_address=client_ip,
            user_agent=user_agent,
            remember_me=credentials.remember_me,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # MFA required: return pending token instead of full login response
    if isinstance(result, dict) and result.get("mfa_required"):
        return JSONResponse(
            status_code=200,
            content=MFARequiredResponse(
                mfa_pending_token=result["mfa_pending_token"],
            ).model_dump(),
        )

    user, access_token, refresh_token, refresh_expires_in = result

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token_expires_in=refresh_expires_in,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            role=user.role.value,
            status=user.status.value,
            tenant_id=user.tenant_id,
            school_id=user.school_id,
            avatar_url=user.avatar_url,
            email_verified=user.email_verified,
            phone_verified=user.phone_verified,
            phone_verified_at=user.phone_verified_at,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@router.post(
    "/login/form",
    response_model=LoginResponse,
    summary="OAuth2 compatible login",
    description="OAuth2 password flow compatible login endpoint.",
    include_in_schema=False,
)
async def login_form(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """OAuth2 compatible login for Swagger UI."""
    tenant_id = getattr(request.state, "tenant_id", None)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please access your school's login page",
        )

    auth_service = AuthService(db)

    try:
        result = await auth_service.authenticate(
            email=form_data.username,
            password=form_data.password,
            tenant_id=tenant_id,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # MFA required: return pending token instead of full login response
    if isinstance(result, dict) and result.get("mfa_required"):
        return JSONResponse(
            status_code=200,
            content=MFARequiredResponse(
                mfa_pending_token=result["mfa_pending_token"],
            ).model_dump(),
        )

    user, access_token, refresh_token, refresh_expires_in = result

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token_expires_in=refresh_expires_in,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            role=user.role.value,
            status=user.status.value,
            tenant_id=user.tenant_id,
            school_id=user.school_id,
            avatar_url=user.avatar_url,
            email_verified=user.email_verified,
            phone_verified=user.phone_verified,
            phone_verified_at=user.phone_verified_at,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh tokens",
    description="Get new access and refresh tokens using a valid refresh token.",
)
async def refresh_tokens(
    request: Request,
    token_request: RefreshTokenRequest,
    db: DatabaseSession,
) -> TokenResponse:
    """
    Refresh access token using refresh token.

    - **refresh_token**: Valid refresh token

    Returns new access token and refresh token (token rotation).
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )

    auth_service = AuthService(db)
    client_ip = _get_client_ip(request)
    user_agent = _get_user_agent(request)

    try:
        # Get old JTI before refresh for blacklisting
        old_jti = _get_jti_from_token(token_request.refresh_token)

        access_token, refresh_token, refresh_expires_in = await auth_service.refresh_tokens(
            refresh_token=token_request.refresh_token,
            tenant_id=tenant_id,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        # Blacklist the old refresh token to prevent reuse (token rotation security)
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_token(token_request.refresh_token)
    except AuthenticationError as e:
        # Signal inactivity-based expiry so the frontend can show an appropriate message
        headers = (
            {"X-Session-Expired": "inactivity"}
            if e.code == "session_inactive"
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers=headers,
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token_expires_in=refresh_expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User logout",
    description="Logout user and invalidate tokens.",
)
async def logout(
    response: Response,
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user_id: CurrentUserId,
    db: DatabaseSession,
) -> None:
    """
    Logout current user.

    Adds the access token to the blacklist and deactivates the session.
    The client should also discard the tokens.
    """
    # Blacklist the current access token
    blacklist_service = await get_token_blacklist_service()
    await blacklist_service.blacklist_token(token)

    # Deactivate the session record linked to this token's JTI
    _, tenant_id, jti = _get_session_context_from_token(token)
    if jti:
        session_service = SessionService(db)
        await session_service.deactivate_by_jti(jti, tenant_id=tenant_id)

    # Clear any cookies if used
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return None


@router.post(
    "/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update last activity timestamp",
)
async def heartbeat(
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    tenant: RequestTenant,
    _: ValidatedTokenTenant,
) -> None:
    """
    Update the user's last_activity_at timestamp.

    Called by the frontend every 5 minutes when user activity is detected
    (mouse movement, keyboard input, scroll, touch).

    This is a lightweight endpoint -- single UPDATE, no SELECT.
    """
    await db.execute(
        update(User)
        .where(User.id == current_user_id)
        # Defense-in-depth: ensure user belongs to current tenant
        .where(User.tenant_id == (tenant.tenant_id if isinstance(tenant.tenant_id, UUID) else UUID(tenant.tenant_id)))
        .values(last_activity_at=datetime.now(timezone.utc))
    )
    await db.flush()
    return None


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user",
    description="Get the currently authenticated user's profile and tenant info.",
)
async def get_current_user(
    request: Request,
    current_user_id: CurrentUserId,
    tenant: RequestTenant,
    db: DatabaseSession,
    _: ValidatedTokenTenant,  # Enforces cross-tenant token validation
) -> UserMeResponse:
    """
    Get current authenticated user info.

    Returns user profile, tenant info, and permissions.
    """
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(current_user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get tenant info
    from sqlalchemy import select
    from app.models.tenant import Tenant

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant_obj = tenant_result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Build permissions — from custom role if assigned, otherwise static ROLE_PERMISSIONS
    permissions = await AuthService.get_effective_permissions(user, db)

    return UserMeResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            role=user.role.value,
            status=user.status.value,
            tenant_id=user.tenant_id,
            school_id=user.school_id,
            avatar_url=user.avatar_url,
            email_verified=user.email_verified,
            phone_verified=user.phone_verified,
            phone_verified_at=user.phone_verified_at,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
        tenant=TenantInfo(
            id=tenant_obj.id,
            name=tenant_obj.name,
            subdomain=tenant_obj.subdomain,
            subscription_tier=tenant_obj.subscription_tier.value,
            logo_url=tenant_obj.logo_url,
            primary_color=tenant_obj.primary_color,
        ),
        permissions=permissions,
    )


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Update user profile",
    description="Update the current user's profile information.",
)
async def update_profile(
    current_user_id: CurrentUserId,
    profile_data: ProfileUpdateRequest,
    db: DatabaseSession,
    _: ValidatedTokenTenant,
) -> UserResponse:
    """
    Update current user's profile.

    - **first_name**: User's first name
    - **last_name**: User's last name
    - **phone**: Phone number (Ghana or international format)
    - **avatar_url**: URL to profile image
    """
    # Get current user
    result = await db.execute(
        select(User).where(
            User.id == current_user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update fields that are provided
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        role=user.role.value,
        status=user.status.value,
        tenant_id=user.tenant_id,
        school_id=user.school_id,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description="Change the current user's password.",
)
async def change_password(
    current_user_id: CurrentUserId,
    password_data: ChangePasswordRequest,
    db: DatabaseSession,
) -> None:
    """
    Change current user's password.

    - **current_password**: Current password
    - **new_password**: New password (min 8 chars, must include uppercase, lowercase, number, special char)

    Note: All existing tokens will be invalidated after password change.
    """
    auth_service = AuthService(db)

    try:
        await auth_service.change_password(
            user_id=current_user_id,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    # Invalidate all existing tokens for this user
    blacklist_service = await get_token_blacklist_service()
    await blacklist_service.blacklist_user_tokens(current_user_id)

    return None


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Request a password reset email. Always returns success to prevent email enumeration.",
)
async def forgot_password(
    request: Request,
    reset_request: PasswordResetRequest,
    db: DatabaseSession,
) -> dict:
    """
    Request a password reset.

    - **email**: Email address associated with the account

    Always returns a success message regardless of whether the email exists,
    to prevent email enumeration attacks.
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please access your school's password reset page",
        )

    client_ip = _get_client_ip(request)
    subdomain = getattr(request.state, "tenant_subdomain", "")

    reset_service = PasswordResetService(db)

    try:
        token = await reset_service.request_password_reset(
            email=reset_request.email,
            tenant_id=tenant_id,
            ip_address=client_ip,
        )

        # Send email if token was generated
        if token:
            # Get user name for email
            result = await db.execute(
                select(User).where(
                    User.email == reset_request.email.lower(),
                    User.tenant_id == tenant_id,
                )
            )
            user = result.scalar_one_or_none()
            user_name = f"{user.first_name} {user.last_name}" if user else "User"

            # Build reset URL (include subdomain for dev mode tenant detection)
            if settings.is_production:
                reset_url = f"https://{subdomain}.simsplus.io/reset-password?token={token}"
            else:
                reset_url = f"http://localhost:3000/reset-password?token={token}&subdomain={subdomain}"

            # Send via EmailService (uses SMTP)
            await email_service.send_password_reset_email(
                to_email=reset_request.email,
                user_name=user_name,
                reset_url=reset_url,
                expires_in_hours=1,  # Token expires in 30 minutes, but say 1 hour for UX
            )

    except PasswordResetError as e:
        if e.code == "rate_limited":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=e.message,
            )
        # For other errors, still return success to prevent enumeration
        pass

    return {
        "message": "If an account with this email exists, you will receive a password reset link shortly.",
    }


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
    description="Reset password using the token from the password reset email.",
)
async def reset_password(
    request: Request,
    reset_confirm: PasswordResetConfirm,
    db: DatabaseSession,
) -> dict:
    """
    Reset password using reset token.

    - **token**: Password reset token from email
    - **password**: New password (min 8 chars, uppercase, lowercase, number, special char)
    """
    client_ip = _get_client_ip(request)

    reset_service = PasswordResetService(db)

    try:
        await reset_service.reset_password(
            token=reset_confirm.token,
            new_password=reset_confirm.password,
            ip_address=client_ip,
        )
    except PasswordResetError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    return {
        "message": "Password has been reset successfully. Please log in with your new password.",
    }


@router.get(
    "/validate-reset-token",
    status_code=status.HTTP_200_OK,
    summary="Validate reset token",
    description="Check if a password reset token is valid.",
)
async def validate_reset_token(
    token: str,
    db: DatabaseSession,
) -> dict:
    """
    Validate a password reset token.

    - **token**: Password reset token to validate

    Returns whether the token is valid.
    """
    reset_service = PasswordResetService(db)
    token_data = await reset_service.validate_reset_token(token)

    return {
        "valid": token_data is not None,
    }


# =========================
# Email Verification
# =========================


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="Verify email address using the token from the verification email.",
)
async def verify_email(
    request: Request,
    verify_request: VerifyEmailRequest,
    db: DatabaseSession,
) -> dict:
    """
    Verify email address using verification token.

    - **token**: Email verification token from email
    """
    client_ip = _get_client_ip(request)

    verification_service = EmailVerificationService(db)

    try:
        await verification_service.verify_email(
            token=verify_request.token,
            ip_address=client_ip,
        )
    except EmailVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    return {
        "message": "Email verified successfully. You can now log in.",
    }


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Resend verification email",
    description="Resend the email verification link.",
)
async def resend_verification(
    request: Request,
    resend_request: ResendVerificationRequest,
    db: DatabaseSession,
) -> dict:
    """
    Resend email verification link.

    - **email**: Email address to send verification to

    Always returns success to prevent email enumeration.
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please access your school's verification page",
        )

    client_ip = _get_client_ip(request)
    subdomain = getattr(request.state, "tenant_subdomain", "")

    verification_service = EmailVerificationService(db)

    try:
        token = await verification_service.resend_verification(
            email=resend_request.email,
            tenant_id=tenant_id,
            ip_address=client_ip,
        )

        if token:
            await verification_service.send_verification_email(
                email=resend_request.email,
                token=token,
                subdomain=subdomain,
            )

    except EmailVerificationError as e:
        if e.code == "rate_limited":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=e.message,
            )
        if e.code == "already_verified":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.message,
            )
        # For other errors, return success to prevent enumeration
        pass

    return {
        "message": "If this email is registered and unverified, you will receive a verification link shortly.",
    }


@router.get(
    "/validate-verification-token",
    status_code=status.HTTP_200_OK,
    summary="Validate verification token",
    description="Check if an email verification token is valid.",
)
async def validate_verification_token(
    token: str,
    db: DatabaseSession,
) -> dict:
    """
    Validate an email verification token.

    - **token**: Email verification token to validate

    Returns whether the token is valid.
    """
    verification_service = EmailVerificationService(db)
    token_data = await verification_service.validate_verification_token(token)

    return {
        "valid": token_data is not None,
    }


# =========================
# Phone Verification & SMS Password Reset
# =========================


@router.post(
    "/send-phone-otp",
    summary="Send OTP to user's phone for verification",
    response_model=SendPhoneOTPResponse,
)
async def send_phone_otp(
    request: Request,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    _: ValidatedTokenTenant,
):
    """
    Send a 6-digit OTP to the authenticated user's registered phone number.

    Requirements:
    - User must be authenticated (JWT required)
    - User must have a phone number on their profile
    - Rate limited: 1 OTP per minute (enforced by OTP service)
    """
    # 1. Get user from DB
    result = await db.execute(
        select(User)
        .where(User.id == current_user_id)
        .where(User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Check phone number exists
    if not user.phone:
        raise HTTPException(
            status_code=400,
            detail="No phone number on your profile. Update your profile first.",
        )

    # 3. Get school name for SMS message personalization
    school_result = await db.execute(
        select(School)
        .where(School.tenant_id == user.tenant_id)
        .where(School.deleted_at.is_(None))
        .limit(1)
    )
    school = school_result.scalar_one_or_none()
    school_name = school.name if school else "SIMS Plus"

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
        raise HTTPException(
            status_code=429 if e.code == "rate_limited" else 500,
            detail=e.message,
        )

    return SendPhoneOTPResponse()


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
    tenant: RequestTenant,
    _: ValidatedTokenTenant,
) -> None:
    """
    Verify the authenticated user's phone number using a 6-digit OTP.

    On success:
    - Sets user.phone_verified = True
    - Sets user.phone_verified_at to current timestamp
    - Logs audit event
    """
    # 1. Get user
    result = await db.execute(
        select(User)
        .where(User.id == current_user_id)
        # Defense-in-depth: ensure user belongs to current tenant
        .where(User.tenant_id == (tenant.tenant_id if isinstance(tenant.tenant_id, UUID) else UUID(tenant.tenant_id)))
        .where(User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
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
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ACCOUNT_ACTIVATED,
        tenant_id=user.tenant_id,
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        details={"action": "phone_verified"},
    )

    return None


@router.post(
    "/forgot-password-sms",
    summary="Request password reset via SMS OTP",
    status_code=status.HTTP_200_OK,
)
async def forgot_password_sms(
    data: ForgotPasswordSMSRequest,
    request: Request,
    db: DatabaseSession,
) -> dict:
    """
    Send a password reset OTP to the provided phone number.

    IMPORTANT: Always returns a generic success message regardless of whether
    the phone number exists. This prevents phone number enumeration attacks.
    """
    # Generic response — always the same regardless of outcome
    response = {
        "message": "If an account with this phone number exists, a verification code has been sent.",
    }

    # Get tenant_id from request state (set by TenantMiddleware via subdomain)
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        # No tenant context — cannot look up users, return generic response
        return response

    # Normalize phone before DB lookup so the format matches what's stored
    # (OTPService also normalizes internally, but the DB query must match)
    normalized_phone = OTPService._normalize_phone(data.phone)

    # Look up user by phone within the current tenant
    result = await db.execute(
        select(User).where(
            User.phone == normalized_phone,
            User.tenant_id == (tenant_id if isinstance(tenant_id, UUID) else UUID(tenant_id)),
            User.deleted_at.is_(None),
            # Only send to active/pending users (not suspended/deactivated)
            User.status.in_([UserStatus.ACTIVE, UserStatus.PENDING]),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal whether phone exists — return generic response
        return response

    # Send OTP (silently fail on errors to prevent enumeration)
    redis = request.app.state.redis
    otp_service = OTPService(redis)
    try:
        # Get school name for SMS personalization
        school_result = await db.execute(
            select(School)
            .where(School.tenant_id == user.tenant_id)
            .where(School.deleted_at.is_(None))
            .limit(1)
        )
        school = school_result.scalar_one_or_none()
        school_name = school.name if school else "SIMS Plus"

        await otp_service.generate_and_send(
            phone=normalized_phone,
            purpose=OTPPurpose.PASSWORD_RESET,
            tenant_id=user.tenant_id,
            school_name=school_name,
        )
    except OTPError:
        # Silently fail — don't reveal anything to the caller
        pass

    # Audit log (only if user found — but response is always the same)
    try:
        audit = AuditService(db)
        await audit.log(
            event_type=AuditEventType.PASSWORD_RESET_REQUEST,
            tenant_id=user.tenant_id,
            user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            details={"method": "sms"},
        )
    except Exception:
        # Audit failure must not affect the response
        pass

    return response


@router.post(
    "/reset-password-sms",
    summary="Reset password using phone number and OTP code",
    status_code=status.HTTP_200_OK,
)
async def reset_password_sms(
    data: ResetPasswordSMSRequest,
    request: Request,
    db: DatabaseSession,
) -> dict:
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

    # Normalize phone before DB lookup so the format matches what's stored
    normalized_phone = OTPService._normalize_phone(data.phone)

    # 1. Verify OTP FIRST — prevents timing side-channel that leaks phone existence
    redis = request.app.state.redis
    otp_service = OTPService(redis)
    try:
        await otp_service.verify(
            phone=normalized_phone,
            code=data.code,
            purpose=OTPPurpose.PASSWORD_RESET,
            tenant_id=tenant_id if isinstance(tenant_id, UUID) else UUID(tenant_id),
        )
    except OTPError as e:
        status_code = 429 if e.code == "max_attempts" else 400
        raise HTTPException(status_code=status_code, detail=e.message)

    # 2. Look up user by phone (only after OTP is verified)
    _tid = tenant_id if isinstance(tenant_id, UUID) else UUID(tenant_id)
    result = await db.execute(
        select(User).where(
            User.phone == normalized_phone,
            User.tenant_id == _tid,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid phone number or code")

    # 3. Update password
    user.password_hash = hash_password(data.new_password)

    # Activate pending users on password reset (same behavior as email reset)
    if user.status == UserStatus.PENDING:
        user.status = UserStatus.ACTIVE

    await db.flush()

    # 4. Blacklist all existing tokens for this user
    blacklist_service = await get_token_blacklist_service()
    await blacklist_service.blacklist_user_tokens(str(user.id))

    # 5. Audit log
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.PASSWORD_RESET_COMPLETE,
        tenant_id=user.tenant_id,
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        details={"method": "sms"},
    )

    return {
        "message": "Password reset successful. Please log in with your new password.",
    }


# =========================
# MFA (Multi-Factor Authentication)
# =========================


@router.post(
    "/mfa/setup",
    summary="Begin MFA setup -- get QR code and backup codes",
    response_model=MFASetupResponse,
)
async def mfa_setup(
    request: Request,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    _: ValidatedTokenTenant,
):
    """
    Start TOTP MFA setup. Returns a QR code for scanning with an
    authenticator app and 10 one-time backup codes.

    MFA is NOT active until /auth/mfa/verify-setup is called with a
    valid code from the authenticator app.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )

    mfa_service = MFAService(db)
    try:
        result = await mfa_service.setup_totp(
            user_id=UUID(current_user_id),
            tenant_id=UUID(tenant_id),
        )
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    return MFASetupResponse(**result)


@router.post(
    "/mfa/verify-setup",
    summary="Verify TOTP code to complete MFA setup",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mfa_verify_setup(
    data: MFAVerifySetupRequest,
    request: Request,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    _: ValidatedTokenTenant,
) -> None:
    """
    Complete MFA setup by verifying a TOTP code from the authenticator app.
    On success, MFA is enabled for the account.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )

    mfa_service = MFAService(db)
    try:
        await mfa_service.verify_and_enable(
            user_id=UUID(current_user_id),
            tenant_id=UUID(tenant_id),
            code=data.code,
        )
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_ENABLED,
        tenant_id=UUID(tenant_id),
        user_id=UUID(current_user_id),
        target_type="user",
        target_id=str(current_user_id),
        details={},
    )

    return None


@router.post(
    "/mfa/verify",
    summary="Verify MFA code during login",
    response_model=LoginResponse,
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
    used at this endpoint. It is single-use (blacklisted after success).
    """
    # 1. Validate mfa_pending_token
    try:
        payload = decode_token(data.mfa_pending_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA token",
        )

    # CRITICAL: only accept mfa_pending tokens at this endpoint
    if payload.get("type") != "mfa_pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tenant_id"])

    # Cross-tenant validation: ensure pending token's tenant matches request
    request_tenant_id = getattr(request.state, "tenant_id", None)
    if request_tenant_id and str(tenant_id) != str(request_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token not valid for this school",
        )

    # Check if this pending token was already used (single-use enforcement)
    # Use SHA-256 of the full token to avoid key collisions — JWT prefixes
    # share the same header bytes, so token[:32] is nearly identical across tokens
    redis = request.app.state.redis
    token_hash = hashlib.sha256(data.mfa_pending_token.encode()).hexdigest()
    used_key = f"mfa_used:{token_hash}"
    if await redis.get(used_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA token has already been used. Please log in again.",
        )

    # Brute-force protection: track failed attempts per mfa_pending_token
    mfa_attempts_key = f"mfa_attempts:{token_hash}"
    attempts = int(await redis.get(mfa_attempts_key) or "0")
    if attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed MFA attempts. Please log in again.",
        )

    # 2. Verify TOTP/backup code
    mfa_service = MFAService(db)
    try:
        await mfa_service.verify_totp(user_id, tenant_id, data.code)
    except MFAError as e:
        # Increment brute-force counter on failure
        pipe = redis.pipeline()
        pipe.incr(mfa_attempts_key)
        # TTL matches the pending token expiry (5 min)
        pipe.expire(mfa_attempts_key, 300)
        await pipe.execute()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        )

    # Mark pending token as used (single-use; TTL matches pending token expiry)
    await redis.setex(used_key, 300, "1")

    # 3. Load user and issue full tokens
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            # Defense-in-depth: filter by tenant_id
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Update last_activity_at for session timeout tracking
    user.last_activity_at = datetime.now(timezone.utc)
    await db.flush()

    # Build tokens using the same flow as normal login
    auth_service = AuthService(db)
    permissions = await auth_service.get_effective_permissions(user, db)
    extra_claims = await auth_service._build_extra_claims(user, tenant_id)

    access_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        school_id=str(user.school_id) if user.school_id else None,
        role=user.role.value,
        permissions=permissions,
        extra_claims=extra_claims,
    )
    # MFA flow does not support remember_me — use default refresh token expiry
    refresh_token, jti, expires_at = create_refresh_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
    )
    refresh_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
    refresh_token_expires_in = refresh_days * 24 * 60 * 60

    # Create session record so session management and JTI DB fallback work
    session_service = SessionService(db)
    device_info = parse_user_agent(request.headers.get("user-agent", ""))
    await session_service.create_session(
        user_id=user.id,
        tenant_id=tenant_id,
        jti=jti,
        device_info=device_info,
        ip_address=request.client.host if request.client else None,
        expires_at=expires_at,
    )

    # 4. Audit log
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
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token_expires_in=refresh_token_expires_in,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            role=user.role.value,
            status=user.status.value,
            tenant_id=user.tenant_id,
            school_id=user.school_id,
            avatar_url=user.avatar_url,
            email_verified=user.email_verified,
            phone_verified=user.phone_verified,
            phone_verified_at=user.phone_verified_at,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@router.post(
    "/mfa/disable",
    summary="Disable MFA (requires password)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mfa_disable(
    data: MFADisableRequest,
    request: Request,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    _: ValidatedTokenTenant,
) -> None:
    """
    Disable MFA for the current user's account.
    Requires password confirmation for security.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )

    mfa_service = MFAService(db)
    try:
        await mfa_service.disable_mfa(
            user_id=UUID(current_user_id),
            tenant_id=UUID(tenant_id),
            password=data.password,
        )
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_DISABLED,
        tenant_id=UUID(tenant_id),
        user_id=UUID(current_user_id),
        target_type="user",
        target_id=str(current_user_id),
        details={"method": "self_disable"},
    )

    return None


@router.post(
    "/mfa/backup-codes",
    summary="Regenerate MFA backup codes (requires password)",
    response_model=MFABackupCodesResponse,
)
async def mfa_regenerate_backup_codes(
    data: MFADisableRequest,  # Reuse: both just need password
    request: Request,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    _: ValidatedTokenTenant,
):
    """
    Generate new backup codes. Old codes are immediately invalidated.
    Requires password confirmation.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )

    mfa_service = MFAService(db)
    try:
        codes = await mfa_service.regenerate_backup_codes(
            user_id=UUID(current_user_id),
            tenant_id=UUID(tenant_id),
            password=data.password,
        )
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_BACKUP_CODES_REGENERATED,
        tenant_id=UUID(tenant_id),
        user_id=UUID(current_user_id),
        target_type="user",
        target_id=str(current_user_id),
        details={},
    )

    return MFABackupCodesResponse(backup_codes=codes)


@router.get(
    "/mfa/status",
    summary="Get MFA status for current user",
    response_model=MFAStatusResponse,
)
async def mfa_status(
    request: Request,
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    _: ValidatedTokenTenant,
):
    """Get MFA status including backup codes remaining count."""
    result = await db.execute(
        select(User).where(
            User.id == UUID(current_user_id),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    backup_remaining = None
    if user.mfa_enabled:
        mfa_service = MFAService(db)
        backup_remaining = mfa_service.get_backup_codes_remaining(
            user.mfa_backup_codes_hash
        )

    return MFAStatusResponse(
        mfa_enabled=user.mfa_enabled,
        backup_codes_remaining=backup_remaining,
    )


# =========================
# Session Management
# =========================


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List active sessions",
    description="List all active sessions for the current user.",
)
async def list_sessions(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user_id: CurrentUserId,
    db: DatabaseSession,
) -> SessionListResponse:
    """
    List active sessions for the current user.

    The current session is identified by matching the JTI from the access token.
    """
    session_service = SessionService(db)

    _, tenant_id, current_jti = _get_session_context_from_token(token)

    sessions = await session_service.list_sessions(
        user_id=UUIDType(current_user_id),
        tenant_id=tenant_id,
    )

    session_responses = [
        SessionResponse(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            last_activity_at=s.last_activity_at,
            created_at=s.created_at,
            is_current=(s.jti == current_jti) if current_jti else False,
        )
        for s in sessions
    ]

    return SessionListResponse(
        sessions=session_responses,
        count=len(session_responses),
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate a session",
    description="Terminate a specific session and blacklist its refresh token.",
)
async def terminate_session(
    session_id: str,
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user_id: CurrentUserId,
    db: DatabaseSession,
) -> None:
    """
    Terminate a specific session.

    Users can only terminate their own sessions. The associated refresh
    token is blacklisted to prevent further use.
    """
    session_service = SessionService(db)

    _, tenant_id, _ = _get_session_context_from_token(token)

    try:
        jti = await session_service.terminate_session(
            session_id=UUIDType(session_id),
            user_id=UUIDType(current_user_id),
            tenant_id=tenant_id,
        )
    except SessionService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    # Blacklist the refresh token JTI tied to this session.
    # The session is already deactivated in the DB (primary mechanism);
    # Redis blacklisting is an optimization for faster rejection.
    blacklist_service = await get_token_blacklist_service()
    blacklisted = await blacklist_service.blacklist_jti(jti)
    if not blacklisted:
        logger.warning(
            "Failed to blacklist JTI in Redis for terminated session -- "
            "DB session deactivation remains as fallback",
            extra={"session_id": session_id, "jti": jti[:8]},
        )

    return None


@router.post(
    "/sessions/terminate-all",
    status_code=status.HTTP_200_OK,
    summary="Terminate all other sessions",
    description="Terminate all sessions except the current one.",
)
async def terminate_all_other_sessions(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user_id: CurrentUserId,
    db: DatabaseSession,
) -> dict:
    """
    Terminate all sessions except the current one.

    All associated refresh tokens are blacklisted. The current session
    remains active.
    """
    session_service = SessionService(db)

    _, tenant_id, current_jti = _get_session_context_from_token(token)

    if not current_jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current session cannot be identified",
        )

    jtis = await session_service.terminate_all_other_sessions(
        user_id=UUIDType(current_user_id),
        tenant_id=tenant_id,
        current_jti=current_jti,
    )

    # Blacklist all terminated refresh tokens in Redis (optimization).
    # DB session deactivation is the primary mechanism.
    blacklist_service = await get_token_blacklist_service()
    failed_count = 0
    for jti in jtis:
        blacklisted = await blacklist_service.blacklist_jti(jti)
        if not blacklisted:
            failed_count += 1

    if failed_count > 0:
        logger.warning(
            "Failed to blacklist %d/%d JTIs in Redis for bulk session "
            "termination -- DB session deactivation remains as fallback",
            failed_count,
            len(jtis),
        )

    return {
        "terminated": len(jtis),
        "message": f"Terminated {len(jtis)} other session(s)",
    }


