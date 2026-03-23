"""
SIMS Plus - Academic Year and Term Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.academic import (
    AcademicYearCreate,
    AcademicYearUpdate,
    AcademicYearResponse,
    AcademicYearWithTermsResponse,
    TermCreate,
    TermUpdate,
    TermResponse,
)
from app.services.academic import AcademicService, AcademicServiceError

router = APIRouter()


# =========================
# Academic Year Endpoints
# =========================


@router.post(
    "/academic-years",
    response_model=AcademicYearResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create academic year",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def create_academic_year(
    data: AcademicYearCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AcademicYearResponse:
    """Create a new academic year."""
    # Only admin roles may override date-overlap validation — silently
    # ignore the flag for non-admin users rather than returning a 403,
    # because the flag defaults to False and non-admins should never
    # need to know it exists.
    _ADMIN_ROLES = {"platform_admin", "chain_admin", "school_admin"}
    allow_overlap = data.allow_overlap and current_user.get("role") in _ADMIN_ROLES

    service = AcademicService(db)
    try:
        academic_year = await service.create_academic_year(
            tenant_id=tenant.tenant_id,
            name=data.name,
            description=data.description,
            start_date=data.start_date,
            end_date=data.end_date,
            is_current=data.is_current,
            allow_overlap=allow_overlap,
            school_id=data.school_id,
        )
        return AcademicYearResponse(
            id=academic_year.id,
            name=academic_year.name,
            description=academic_year.description,
            start_date=academic_year.start_date,
            end_date=academic_year.end_date,
            status=academic_year.status.value,
            is_current=academic_year.is_current,
            created_at=academic_year.created_at,
            updated_at=academic_year.updated_at,
        )
    except AcademicServiceError as e:
        # 409 Conflict for overlapping date ranges; 400 for other validation errors
        status_code = (
            status.HTTP_409_CONFLICT if e.code == "DATE_OVERLAP"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=e.message)


@router.get(
    "/academic-years",
    response_model=list[AcademicYearWithTermsResponse],
    summary="List academic years",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def list_academic_years(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    include_terms: bool = Query(False, description="Include terms in response"),
) -> list:
    """List all academic years."""
    service = AcademicService(db)
    years = await service.list_academic_years(tenant.tenant_id, include_terms=include_terms)

    response_model = AcademicYearWithTermsResponse if include_terms else AcademicYearResponse
    return [
        response_model(
            id=y.id,
            name=y.name,
            description=y.description,
            start_date=y.start_date,
            end_date=y.end_date,
            status=y.status.value,
            is_current=y.is_current,
            created_at=y.created_at,
            updated_at=y.updated_at,
            **({"terms": [
                TermResponse(
                    id=t.id,
                    academic_year_id=t.academic_year_id,
                    name=t.name,
                    short_name=t.short_name,
                    sequence=t.sequence,
                    start_date=t.start_date,
                    end_date=t.end_date,
                    status=t.status.value,
                    is_current=t.is_current,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                ) for t in y.terms
            ]} if include_terms else {}),
        )
        for y in years
    ]


@router.get(
    "/academic-years/{academic_year_id}",
    response_model=AcademicYearWithTermsResponse,
    summary="Get academic year",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_academic_year(
    academic_year_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AcademicYearWithTermsResponse:
    """Get academic year by ID with terms."""
    service = AcademicService(db)
    year = await service.get_academic_year(tenant.tenant_id, academic_year_id, include_terms=True)
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    return AcademicYearWithTermsResponse(
        id=year.id,
        name=year.name,
        description=year.description,
        start_date=year.start_date,
        end_date=year.end_date,
        status=year.status.value,
        is_current=year.is_current,
        created_at=year.created_at,
        updated_at=year.updated_at,
        terms=[
            TermResponse(
                id=t.id,
                academic_year_id=t.academic_year_id,
                name=t.name,
                short_name=t.short_name,
                sequence=t.sequence,
                start_date=t.start_date,
                end_date=t.end_date,
                status=t.status.value,
                is_current=t.is_current,
                created_at=t.created_at,
                updated_at=t.updated_at,
            ) for t in year.terms
        ],
    )


@router.put(
    "/academic-years/{academic_year_id}",
    response_model=AcademicYearResponse,
    summary="Update academic year",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_academic_year(
    academic_year_id: UUID,
    data: AcademicYearUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AcademicYearResponse:
    """Update an academic year."""
    # Only admin roles may override date-overlap validation
    _ADMIN_ROLES = {"platform_admin", "chain_admin", "school_admin"}
    update_data = data.model_dump(exclude_unset=True)
    if "allow_overlap" in update_data and current_user.get("role") not in _ADMIN_ROLES:
        update_data["allow_overlap"] = False

    service = AcademicService(db)
    try:
        year = await service.update_academic_year(
            academic_year_id,
            tenant.tenant_id,
            **update_data,
        )
    except AcademicServiceError as e:
        # 409 Conflict for overlapping date ranges; 400 for other validation errors
        status_code = (
            status.HTTP_409_CONFLICT if e.code == "DATE_OVERLAP"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=e.message)

    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    return AcademicYearResponse(
        id=year.id,
        name=year.name,
        description=year.description,
        start_date=year.start_date,
        end_date=year.end_date,
        status=year.status.value,
        is_current=year.is_current,
        created_at=year.created_at,
        updated_at=year.updated_at,
    )


@router.delete(
    "/academic-years/{academic_year_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete academic year",
    dependencies=[Depends(require_permissions("academics.delete"))],
)
async def delete_academic_year(
    academic_year_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete an academic year."""
    service = AcademicService(db)
    deleted = await service.delete_academic_year(tenant.tenant_id, academic_year_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")


@router.post(
    "/academic-years/{academic_year_id}/archive",
    response_model=AcademicYearResponse,
    summary="Archive academic year",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def archive_academic_year(
    academic_year_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AcademicYearResponse:
    """
    Archive an academic year.

    Requirements:
    - Academic year must be in 'completed' status
    - All terms within the year must be in 'completed' status
    - Cannot archive the current academic year (is_current=True)

    Once archived, the academic year and all associated data become read-only.
    """
    service = AcademicService(db)
    try:
        year = await service.archive_academic_year(
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year_id,
        )
        return AcademicYearResponse(
            id=year.id,
            name=year.name,
            description=year.description,
            start_date=year.start_date,
            end_date=year.end_date,
            status=year.status.value,
            is_current=year.is_current,
            created_at=year.created_at,
            updated_at=year.updated_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# =========================
# Term Endpoints
# =========================


@router.post(
    "/terms",
    response_model=TermResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create term",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def create_term(
    data: TermCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TermResponse:
    """Create a new term."""
    service = AcademicService(db)
    try:
        term = await service.create_term(
            tenant_id=tenant.tenant_id,
            academic_year_id=data.academic_year_id,
            name=data.name,
            short_name=data.short_name,
            sequence=data.sequence,
            start_date=data.start_date,
            end_date=data.end_date,
        )
        return TermResponse(
            id=term.id,
            academic_year_id=term.academic_year_id,
            name=term.name,
            short_name=term.short_name,
            sequence=term.sequence,
            start_date=term.start_date,
            end_date=term.end_date,
            status=term.status.value,
            is_current=term.is_current,
            created_at=term.created_at,
            updated_at=term.updated_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/terms",
    response_model=list[TermResponse],
    summary="List terms",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def list_terms(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    academic_year_id: Optional[UUID] = Query(None, description="Filter by academic year"),
) -> list[TermResponse]:
    """List all terms."""
    service = AcademicService(db)
    terms = await service.list_terms(tenant.tenant_id, academic_year_id)
    return [
        TermResponse(
            id=t.id,
            academic_year_id=t.academic_year_id,
            name=t.name,
            short_name=t.short_name,
            sequence=t.sequence,
            start_date=t.start_date,
            end_date=t.end_date,
            status=t.status.value,
            is_current=t.is_current,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in terms
    ]


@router.get(
    "/terms/{term_id}",
    response_model=TermResponse,
    summary="Get term",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_term(
    term_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TermResponse:
    """Get term by ID."""
    service = AcademicService(db)
    term = await service.get_term(tenant.tenant_id, term_id)
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

    return TermResponse(
        id=term.id,
        academic_year_id=term.academic_year_id,
        name=term.name,
        short_name=term.short_name,
        sequence=term.sequence,
        start_date=term.start_date,
        end_date=term.end_date,
        status=term.status.value,
        is_current=term.is_current,
        created_at=term.created_at,
        updated_at=term.updated_at,
    )


@router.put(
    "/terms/{term_id}",
    response_model=TermResponse,
    summary="Update term",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_term(
    term_id: UUID,
    data: TermUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TermResponse:
    """Update a term."""
    service = AcademicService(db)
    term = await service.update_term(term_id, tenant.tenant_id, **data.model_dump(exclude_unset=True))
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

    return TermResponse(
        id=term.id,
        academic_year_id=term.academic_year_id,
        name=term.name,
        short_name=term.short_name,
        sequence=term.sequence,
        start_date=term.start_date,
        end_date=term.end_date,
        status=term.status.value,
        is_current=term.is_current,
        created_at=term.created_at,
        updated_at=term.updated_at,
    )


@router.delete(
    "/terms/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete term",
    dependencies=[Depends(require_permissions("academics.delete"))],
)
async def delete_term(
    term_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a term."""
    service = AcademicService(db)
    deleted = await service.delete_term(tenant.tenant_id, term_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")
