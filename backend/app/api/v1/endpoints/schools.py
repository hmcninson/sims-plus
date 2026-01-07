"""
SIMS Plus - Schools API Endpoints

API endpoints for school profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.models.school import School
from app.schemas.school import (
    SchoolProfileResponse,
    SchoolProfileUpdate,
    SchoolBrandingUpdate,
)

router = APIRouter()


@router.get(
    "/current",
    response_model=SchoolProfileResponse,
    summary="Get current school profile",
    description="Get the profile of the current school (based on tenant context).",
    dependencies=[Depends(require_permissions("school.read"))],
)
async def get_current_school(
    tenant: RequestTenant,
    db: DatabaseSession,
) -> SchoolProfileResponse:
    """Get the current school's profile."""
    result = await db.execute(
        select(School).where(
            School.tenant_id == tenant.tenant_id,
            School.deleted_at.is_(None),
        )
    )
    school = result.scalar_one_or_none()

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    return SchoolProfileResponse(
        id=school.id,
        tenant_id=school.tenant_id,
        name=school.name,
        slug=school.slug,
        code=school.code,
        school_type=school.school_type.value,
        email=school.email,
        phone=school.phone,
        website=school.website,
        address=school.address,
        city=school.city,
        region=school.region,
        gps_address=school.gps_address,
        logo_url=school.logo_url,
        primary_color=school.primary_color,
        motto=school.motto,
        description=school.description,
        year_established=school.year_established,
        uses_boarding=school.uses_boarding,
        uses_transport=school.uses_transport,
        student_id_prefix=school.student_id_prefix,
        is_active=school.is_active,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )


@router.put(
    "/current",
    response_model=SchoolProfileResponse,
    summary="Update current school profile",
    description="Update the profile of the current school.",
    dependencies=[Depends(require_permissions("school.update"))],
)
async def update_current_school(
    tenant: RequestTenant,
    db: DatabaseSession,
    data: SchoolProfileUpdate,
) -> SchoolProfileResponse:
    """Update the current school's profile."""
    result = await db.execute(
        select(School).where(
            School.tenant_id == tenant.tenant_id,
            School.deleted_at.is_(None),
        )
    )
    school = result.scalar_one_or_none()

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Update fields that are provided
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(school, field, value)

    await db.flush()
    await db.refresh(school)

    return SchoolProfileResponse(
        id=school.id,
        tenant_id=school.tenant_id,
        name=school.name,
        slug=school.slug,
        code=school.code,
        school_type=school.school_type.value,
        email=school.email,
        phone=school.phone,
        website=school.website,
        address=school.address,
        city=school.city,
        region=school.region,
        gps_address=school.gps_address,
        logo_url=school.logo_url,
        primary_color=school.primary_color,
        motto=school.motto,
        description=school.description,
        year_established=school.year_established,
        uses_boarding=school.uses_boarding,
        uses_transport=school.uses_transport,
        student_id_prefix=school.student_id_prefix,
        is_active=school.is_active,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )


@router.patch(
    "/current/branding",
    response_model=SchoolProfileResponse,
    summary="Update school branding",
    description="Update only the branding (logo, colors) of the current school.",
    dependencies=[Depends(require_permissions("school.update"))],
)
async def update_school_branding(
    tenant: RequestTenant,
    db: DatabaseSession,
    data: SchoolBrandingUpdate,
) -> SchoolProfileResponse:
    """Update the current school's branding."""
    result = await db.execute(
        select(School).where(
            School.tenant_id == tenant.tenant_id,
            School.deleted_at.is_(None),
        )
    )
    school = result.scalar_one_or_none()

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Update branding fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(school, field, value)

    await db.flush()
    await db.refresh(school)

    return SchoolProfileResponse(
        id=school.id,
        tenant_id=school.tenant_id,
        name=school.name,
        slug=school.slug,
        code=school.code,
        school_type=school.school_type.value,
        email=school.email,
        phone=school.phone,
        website=school.website,
        address=school.address,
        city=school.city,
        region=school.region,
        gps_address=school.gps_address,
        logo_url=school.logo_url,
        primary_color=school.primary_color,
        motto=school.motto,
        description=school.description,
        year_established=school.year_established,
        uses_boarding=school.uses_boarding,
        uses_transport=school.uses_transport,
        student_id_prefix=school.student_id_prefix,
        is_active=school.is_active,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )
