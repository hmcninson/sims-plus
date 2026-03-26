"""
SIMS Plus - Applicant Account Public Endpoints

Unauthenticated endpoints for applicant registration, login, email
verification, and password reset. Tenant resolved from subdomain
via TenantMiddleware -> request.state.tenant_id.

Uses PublicTenantSession for tenant-scoped DB without JWT.

IMPORTANT: Do NOT use 'from __future__ import annotations' in this file.
"""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PublicTenantSession
from app.models.school import School
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


async def _resolve_default_school_id(db: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    """Resolve the default school for a tenant (oldest active school)."""
    result = await db.execute(
        select(School.id)
        .where(School.tenant_id == tenant_id, School.is_active.is_(True))
        .order_by(School.created_at.asc())
        .limit(1)
    )
    school_id = result.scalar_one_or_none()
    if not school_id:
        raise HTTPException(status_code=400, detail="No active school found for this tenant.")
    return school_id


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
        school_id = await _resolve_default_school_id(db, tenant_id)

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
