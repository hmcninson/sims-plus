"""
SIMS Plus - Onboarding Endpoints

API endpoints for school registration and onboarding.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import UnscopedDatabaseSession
from app.schemas.onboarding import (
    ResendVerificationRequest,
    SchoolRegistrationRequest,
    SchoolRegistrationResponse,
)
from app.config import get_settings
from app.services.onboarding import OnboardingService, OnboardingError
from app.services.email_verification import (
    EmailVerificationService,
    EmailVerificationError,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=SchoolRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new school",
    description="Self-service school registration. Creates tenant, school, and admin user.",
)
async def register_school(
    request: Request,
    registration: SchoolRegistrationRequest,
    db: UnscopedDatabaseSession,
) -> SchoolRegistrationResponse:
    """
    Register a new school on SIMS Plus.

    This endpoint:
    1. Validates the subdomain is available
    2. Creates a new tenant (organization)
    3. Creates a school within the tenant
    4. Creates an admin user for the school
    5. Sets up a trial subscription
    6. Sends a verification email to the admin

    No authentication required - this is a public endpoint.

    **Note:** The admin must verify their email before they can log in.
    """
    # Get shared Redis client for verification token storage
    redis_client = getattr(request.app.state, "redis", None)

    service = OnboardingService(db, redis_client=redis_client)

    try:
        tenant, school, admin_user = await service.register_school(
            school_name=registration.school_name,
            subdomain=registration.subdomain,
            school_type=registration.school_type,
            admin_email=registration.admin_email,
            admin_first_name=registration.admin_first_name,
            admin_last_name=registration.admin_last_name,
            admin_password=registration.admin_password,
            admin_phone=registration.admin_phone,
            tenant_type=registration.tenant_type,
            plan=registration.plan,
            school_category=registration.school_category,
            boarding_type=registration.boarding_type,
        )
    except OnboardingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    # Get portal URL
    portal_url = await service.get_portal_url(tenant.subdomain)

    # Calculate trial end date
    trial_ends_at = None
    if tenant.subscription_end:
        from datetime import datetime, UTC
        trial_ends_at = datetime.combine(
            tenant.subscription_end,
            datetime.min.time(),
        ).replace(tzinfo=UTC)

    return SchoolRegistrationResponse(
        success=True,
        message=f"School '{school.name}' registered successfully! Please check your email to verify your account before logging in.",
        tenant_id=tenant.id,
        school_id=school.id,
        admin_user_id=admin_user.id,
        subdomain=tenant.subdomain,
        portal_url=portal_url,
        admin_email=admin_user.email,
        trial_ends_at=trial_ends_at,
    )


@router.get(
    "/suggest-subdomain",
    summary="Get subdomain suggestions",
    description="Generate available subdomain suggestions based on school name.",
)
async def suggest_subdomains(
    school_name: Annotated[
        str,
        Query(
            min_length=3,
            max_length=255,
            description="School name to base suggestions on",
        ),
    ],
    db: UnscopedDatabaseSession,
    count: Annotated[
        int,
        Query(
            ge=1,
            le=5,
            description="Number of suggestions to return",
        ),
    ] = 3,
) -> dict:
    """
    Get subdomain suggestions based on school name.

    Returns a list of available subdomain suggestions.
    """
    service = OnboardingService(db)
    suggestions = await service.generate_subdomain_suggestions(school_name, count)

    return {
        "school_name": school_name,
        "suggestions": suggestions,
    }


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Resend verification email for newly registered admin",
    description="Public endpoint for resending the verification email after registration.",
)
async def resend_onboarding_verification(
    request: Request,
    body: ResendVerificationRequest,
    db: UnscopedDatabaseSession,
) -> dict:
    """
    Resend the email verification link for a newly registered admin.

    This is a public endpoint (no tenant context required) used from the
    registration success page, which lives on the main domain without a subdomain.
    The tenant is resolved from the subdomain parameter in the request body.

    Always returns success to prevent email enumeration.
    """
    from sqlalchemy import select as sa_select
    from app.models.tenant import Tenant
    from app.middleware.tenant import set_db_tenant_context

    # Look up tenant by subdomain
    result = await db.execute(
        sa_select(Tenant).where(
            Tenant.subdomain == body.subdomain.lower(),
            Tenant.is_active.is_(True),
        )
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        # Return generic success to prevent subdomain enumeration
        return {
            "message": "If an account with this email exists, a verification link has been sent.",
        }

    # Set tenant context so RLS allows reading the user record
    await set_db_tenant_context(db, tenant.id)

    redis_client = getattr(request.app.state, "redis", None)
    verification_service = EmailVerificationService(db, redis_client=redis_client)

    try:
        client_ip = request.client.host if request.client else None
        token = await verification_service.resend_verification(
            email=body.email,
            tenant_id=tenant.id,
            ip_address=client_ip,
        )

        if token:
            await verification_service.send_verification_email(
                email=body.email,
                token=token,
                subdomain=body.subdomain.lower(),
            )

    except EmailVerificationError as e:
        if e.code == "rate_limited":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=e.message,
            )
        # For all other errors (including already_verified), fall through to
        # the generic success message to prevent email enumeration attacks.

    return {
        "message": "If an account with this email exists, a verification link has been sent.",
    }


@router.get(
    "/plans",
    summary="Get available subscription plans",
    description="Get list of available subscription plans and their features.",
)
async def get_plans() -> dict:
    """
    Get available subscription plans.

    Returns pricing and feature information for each plan.
    """
    settings = get_settings()

    return {
        "plans": [
            {
                "id": "trial",
                "name": "Free Trial",
                "price": 0,
                "currency": "GHS",
                "period": f"{settings.TRIAL_DAYS} days",
                "max_students": 100,
                "features": [
                    "Student Management",
                    "Basic Attendance",
                    "Class Management",
                    "Report Cards",
                    "50 SMS/month",
                ],
                "popular": False,
            },
            {
                "id": "starter",
                "name": "Starter",
                "price": 500,
                "currency": "GHS",
                "period": "month",
                "max_students": 300,
                "features": [
                    "Everything in Trial",
                    "Finance & Payments",
                    "Mobile Money Integration",
                    "Email Support",
                    "100 SMS/month",
                ],
                "popular": False,
            },
            {
                "id": "professional",
                "name": "Professional",
                "price": 1500,
                "currency": "GHS",
                "period": "month",
                "max_students": 1000,
                "features": [
                    "Everything in Starter",
                    "Boarding Management",
                    "Transport Management",
                    "API Access",
                    "Priority Support",
                    "500 SMS/month",
                ],
                "popular": True,
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "price": None,  # Custom pricing
                "currency": "GHS",
                "period": "month",
                "max_students": None,  # Unlimited
                "features": [
                    "Everything in Professional",
                    "Multi-School Support",
                    "Custom Domain",
                    "White Label Option",
                    "Dedicated Support",
                    "SLA Guarantee",
                    "Unlimited SMS",
                ],
                "popular": False,
            },
        ],
        "trial_days": settings.TRIAL_DAYS,
        "currency": "GHS",
    }
