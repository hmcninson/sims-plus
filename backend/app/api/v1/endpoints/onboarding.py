"""
SIMS Plus - Onboarding Endpoints

API endpoints for school registration and onboarding.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import UnscopedDatabaseSession
from app.schemas.onboarding import (
    SchoolRegistrationRequest,
    SchoolRegistrationResponse,
)
from app.services.onboarding import OnboardingService, OnboardingError

router = APIRouter()


@router.post(
    "/register",
    response_model=SchoolRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new school",
    description="Self-service school registration. Creates tenant, school, and admin user.",
)
async def register_school(
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

    No authentication required - this is a public endpoint.

    **Note:** The admin will need to verify their email before full access.
    """
    service = OnboardingService(db)

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
        message=f"School '{school.name}' registered successfully! You can now login at {portal_url}",
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
    return {
        "plans": [
            {
                "id": "trial",
                "name": "Free Trial",
                "price": 0,
                "currency": "GHS",
                "period": "30 days",
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
        "trial_days": 30,
        "currency": "GHS",
    }
