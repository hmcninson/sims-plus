"""
SIMS Plus - Schools API Endpoints

API endpoints for school profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.models.school import School, SchoolCategory, BoardingType
from app.schemas.school import (
    PreschoolSettings,
    PreschoolSettingsUpdate,
    SchoolProfileResponse,
    SchoolProfileUpdate,
    SchoolBrandingUpdate,
)


def _build_school_response(school: School) -> SchoolProfileResponse:
    """Build a school profile response from a School model instance."""
    # Convert preschool_settings dict to Pydantic model
    preschool_settings = None
    if school.preschool_settings:
        preschool_settings = PreschoolSettings(**school.preschool_settings)

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
        category=school.category.value if school.category else None,
        boarding_type=school.boarding_type.value if school.boarding_type else None,
        student_id_prefix=school.student_id_prefix,
        staff_id_prefix=school.staff_id_prefix,
        preschool_settings=preschool_settings,
        is_active=school.is_active,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )

router = APIRouter()


async def _get_current_school(db: AsyncSession, tenant_id) -> School:
    """Fetch the current school for a tenant.

    For chain tenants with multiple schools, returns the first school
    (ordered by creation date) so that the setup wizard and other
    profile-dependent features have a deterministic school to work with.
    Uses order_by + limit(1) instead of scalar_one_or_none() to avoid
    MultipleResultsFound errors for chain tenants.
    """
    result = await db.execute(
        select(School)
        .where(
            School.tenant_id == tenant_id,
            School.deleted_at.is_(None),
        )
        .order_by(School.created_at.asc())
        .limit(1)
    )
    school = result.scalar_one_or_none()

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    return school


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
    school = await _get_current_school(db, tenant.tenant_id)
    return _build_school_response(school)


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
    school = await _get_current_school(db, tenant.tenant_id)

    # Update fields that are provided
    update_data = data.model_dump(exclude_unset=True)

    # Handle preschool_settings separately (merge with existing)
    if "preschool_settings" in update_data and update_data["preschool_settings"]:
        existing_settings = school.preschool_settings or {}
        existing_settings.update(update_data.pop("preschool_settings"))
        school.preschool_settings = existing_settings

    # Convert string values to enums for enum columns
    if "category" in update_data:
        val = update_data.pop("category")
        school.category = SchoolCategory(val) if val else None
    if "boarding_type" in update_data:
        val = update_data.pop("boarding_type")
        school.boarding_type = BoardingType(val) if val else None

    for field, value in update_data.items():
        setattr(school, field, value)

    await db.flush()
    await db.refresh(school)

    return _build_school_response(school)


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
    school = await _get_current_school(db, tenant.tenant_id)

    # Update branding fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(school, field, value)

    await db.flush()
    await db.refresh(school)

    return _build_school_response(school)


@router.get(
    "/current/preschool-settings",
    response_model=PreschoolSettings,
    summary="Get preschool settings",
    description="Get the preschool configuration settings for the current school.",
    dependencies=[Depends(require_permissions("school.read"))],
)
async def get_preschool_settings(
    tenant: RequestTenant,
    db: DatabaseSession,
) -> PreschoolSettings:
    """Get the current school's preschool settings."""
    school = await _get_current_school(db, tenant.tenant_id)

    # Return existing settings or defaults
    if school.preschool_settings:
        return PreschoolSettings(**school.preschool_settings)
    return PreschoolSettings()


@router.patch(
    "/current/preschool-settings",
    response_model=PreschoolSettings,
    summary="Update preschool settings",
    description="Update the preschool configuration settings for the current school.",
    dependencies=[Depends(require_permissions("school.update"))],
)
async def update_preschool_settings(
    tenant: RequestTenant,
    db: DatabaseSession,
    data: PreschoolSettingsUpdate,
) -> PreschoolSettings:
    """Update the current school's preschool settings."""
    school = await _get_current_school(db, tenant.tenant_id)

    # Merge with existing settings
    existing_settings = school.preschool_settings or {}
    update_data = data.model_dump(exclude_unset=True)

    # Handle UUID serialization for default_rating_scale_id
    if "default_rating_scale_id" in update_data and update_data["default_rating_scale_id"]:
        update_data["default_rating_scale_id"] = str(update_data["default_rating_scale_id"])

    existing_settings.update(update_data)
    school.preschool_settings = existing_settings

    # Mark JSONB field as modified so SQLAlchemy detects the change
    flag_modified(school, "preschool_settings")

    await db.flush()
    await db.refresh(school)

    return PreschoolSettings(**school.preschool_settings)
