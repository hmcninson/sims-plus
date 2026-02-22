"""
SIMS Plus - Authentication Endpoints

API endpoints for user authentication.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
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
    TokenResponse,
    UserMeResponse,
    UserResponse,
    TenantInfo,
    VerifyEmailRequest,
)
from sqlalchemy import select

from app.models.user import User
from app.services.auth import AuthService, AuthenticationError
from app.services.token_blacklist import get_token_blacklist_service
from app.services.password_reset import PasswordResetService, PasswordResetError
from app.services.email_verification import EmailVerificationService, EmailVerificationError
from app.services.email import email_service

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
        user, access_token, refresh_token = await auth_service.authenticate(
            email=credentials.email,
            password=credentials.password,
            tenant_id=tenant_id,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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
        user, access_token, refresh_token = await auth_service.authenticate(
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

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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

    try:
        access_token, refresh_token = await auth_service.refresh_tokens(
            refresh_token=token_request.refresh_token,
            tenant_id=tenant_id,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        )

    # Blacklist the old refresh token to prevent reuse (token rotation security)
    blacklist_service = await get_token_blacklist_service()
    await blacklist_service.blacklist_token(token_request.refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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
) -> None:
    """
    Logout current user.

    Adds the access token to the blacklist to prevent reuse.
    The client should also discard the tokens.
    """
    # Blacklist the current access token
    blacklist_service = await get_token_blacklist_service()
    await blacklist_service.blacklist_token(token)

    # Clear any cookies if used
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

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

    # Build permissions based on role
    permissions = AuthService.get_role_permissions(user.role.value)

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


