"""
SIMS Plus - Tenant Endpoints

API endpoints for tenant operations including subdomain validation.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.schemas.tenant import (
    SubdomainCheckRequest,
    SubdomainCheckResponse,
    TenantBranding,
    TenantPublic,
    TenantValidationResponse,
)
from app.services.tenant import TenantService


router = APIRouter()


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        yield session


@router.get(
    "/check-subdomain",
    response_model=SubdomainCheckResponse,
    summary="Check subdomain availability",
    description="Check if a subdomain is available for registration.",
)
async def check_subdomain_availability(
    subdomain: Annotated[
        str,
        Query(
            min_length=4,
            max_length=63,
            description="Subdomain to check",
        ),
    ],
    db: AsyncSession = Depends(get_db),
) -> SubdomainCheckResponse:
    """
    Check if a subdomain is available.

    - **subdomain**: The subdomain to check (4-63 characters, lowercase alphanumeric and hyphens)

    Returns availability status and reason if unavailable.
    """
    service = TenantService(db)
    available, reason = await service.check_subdomain_availability(subdomain)

    return SubdomainCheckResponse(
        subdomain=subdomain.lower(),
        available=available,
        reason=reason,
    )


@router.post(
    "/check-subdomain",
    response_model=SubdomainCheckResponse,
    summary="Check subdomain availability (POST)",
    description="Check if a subdomain is available for registration (POST method).",
)
async def check_subdomain_availability_post(
    request: SubdomainCheckRequest,
    db: AsyncSession = Depends(get_db),
) -> SubdomainCheckResponse:
    """
    Check if a subdomain is available (POST method).

    - **subdomain**: The subdomain to check

    Returns availability status and reason if unavailable.
    """
    service = TenantService(db)
    available, reason = await service.check_subdomain_availability(request.subdomain)

    return SubdomainCheckResponse(
        subdomain=request.subdomain.lower(),
        available=available,
        reason=reason,
    )


@router.get(
    "/validate/{subdomain}",
    response_model=TenantValidationResponse,
    summary="Validate tenant by subdomain",
    description="Validate that a tenant exists and is active for the given subdomain.",
)
async def validate_tenant(
    subdomain: Annotated[
        str,
        Path(
            min_length=4,
            max_length=63,
            description="Tenant subdomain to validate",
        ),
    ],
    db: AsyncSession = Depends(get_db),
) -> TenantValidationResponse:
    """
    Validate a tenant by subdomain.

    This endpoint is used by the frontend to verify that a subdomain
    corresponds to a valid, active tenant before showing the login page.

    - **subdomain**: The subdomain to validate

    Returns:
    - **valid**: Whether the tenant is valid and active
    - **tenant**: Public tenant information if valid
    - **error**: Error message if invalid
    """
    service = TenantService(db)
    is_valid, tenant, error = await service.validate_tenant(subdomain)

    if not is_valid or tenant is None:
        return TenantValidationResponse(
            valid=False,
            tenant=None,
            error=error,
        )

    return TenantValidationResponse(
        valid=True,
        tenant=TenantPublic(
            id=tenant.id,
            name=tenant.name,
            subdomain=tenant.subdomain,
            tenant_type=tenant.tenant_type.value,
            is_active=tenant.is_active,
            branding=TenantBranding(
                logo_url=tenant.logo_url,
                primary_color=tenant.primary_color,
            ),
        ),
        error=None,
    )


@router.get(
    "/current",
    response_model=TenantValidationResponse,
    summary="Get current tenant",
    description="Get the current tenant based on the X-Subdomain header.",
)
async def get_current_tenant(
    subdomain: Annotated[
        str | None,
        Query(
            alias="X-Subdomain",
            description="Subdomain header",
        ),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> TenantValidationResponse:
    """
    Get the current tenant based on subdomain.

    This endpoint is typically called by the frontend to get
    tenant information for branding and configuration.

    The subdomain can be passed via:
    - Query parameter: `?X-Subdomain=presec`
    - Header: `X-Subdomain: presec`

    Returns:
    - **valid**: Whether the tenant is valid
    - **tenant**: Public tenant information if valid
    - **error**: Error message if invalid
    """
    if not subdomain:
        return TenantValidationResponse(
            valid=False,
            tenant=None,
            error="No subdomain provided",
        )

    service = TenantService(db)
    is_valid, tenant, error = await service.validate_tenant(subdomain)

    if not is_valid or tenant is None:
        return TenantValidationResponse(
            valid=False,
            tenant=None,
            error=error,
        )

    return TenantValidationResponse(
        valid=True,
        tenant=TenantPublic(
            id=tenant.id,
            name=tenant.name,
            subdomain=tenant.subdomain,
            tenant_type=tenant.tenant_type.value,
            is_active=tenant.is_active,
            branding=TenantBranding(
                logo_url=tenant.logo_url,
                primary_color=tenant.primary_color,
            ),
        ),
        error=None,
    )
