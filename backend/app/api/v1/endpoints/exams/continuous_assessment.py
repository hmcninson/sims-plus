"""
SIMS Plus - Continuous Assessment Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.exam import (
    CACreate,
    CABulkCreate,
    CAUpdate,
    CAResponse,
    CAWithDetailsResponse,
    CASummaryResponse,
    BulkScoreResult,
)
from app.services.exam import CAService

router = APIRouter()


# =========================
# Continuous Assessment Endpoints
# =========================


@router.post(
    "/ca",
    response_model=CAResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create CA entry",
    dependencies=[Depends(require_permissions("exams.ca.enter"))],
)
async def create_ca(
    data: CACreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> CAResponse:
    """Create a continuous assessment entry."""
    from app.services.academic import AcademicService
    academic_service = AcademicService(db)
    term = await academic_service.get_term(tenant.tenant_id, data.term_id)
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = CAService(db)
    ca = await service.create_ca(
        tenant_id=tenant.tenant_id,
        academic_year_id=term.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        subject_id=data.subject_id,
        student_id=data.student_id,
        assessment_type=data.assessment_type,
        title=data.title,
        assessment_date=data.assessment_date,
        max_score=data.max_score,
        score=data.score,
        entered_by=user_id,
    )

    return CAResponse(
        id=ca.id,
        tenant_id=ca.tenant_id,
        academic_year_id=ca.academic_year_id,
        term_id=ca.term_id,
        class_id=ca.class_id,
        subject_id=ca.subject_id,
        student_id=ca.student_id,
        assessment_type=ca.assessment_type.value,
        title=ca.title,
        max_score=ca.max_score,
        score=ca.score,
        assessment_date=ca.assessment_date,
        entered_by=ca.entered_by,
        created_at=ca.created_at,
        updated_at=ca.updated_at,
    )


@router.post(
    "/ca/bulk",
    response_model=BulkScoreResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create CA entries",
    dependencies=[Depends(require_permissions("exams.ca.enter"))],
)
async def bulk_create_ca(
    data: CABulkCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> BulkScoreResult:
    """Bulk create CA entries for a class."""
    from app.services.academic import AcademicService
    academic_service = AcademicService(db)
    term = await academic_service.get_term(tenant.tenant_id, data.term_id)
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = CAService(db)
    result = await service.bulk_create_ca(
        tenant_id=tenant.tenant_id,
        academic_year_id=term.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        subject_id=data.subject_id,
        assessment_type=data.assessment_type,
        title=data.title,
        assessment_date=data.assessment_date,
        max_score=data.max_score,
        scores=[s.model_dump() for s in data.scores],
        entered_by=user_id,
    )

    return BulkScoreResult(**result)


@router.get(
    "/ca",
    response_model=list[CAWithDetailsResponse],
    summary="List CA entries",
    dependencies=[Depends(require_permissions("exams.ca.read"))],
)
async def list_ca(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: Optional[UUID] = Query(None),
    class_id: Optional[UUID] = Query(None),
    subject_id: Optional[UUID] = Query(None),
    student_id: Optional[UUID] = Query(None),
    assessment_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> list[CAWithDetailsResponse]:
    """List CA entries with filters."""
    service = CAService(db)
    entries, total = await service.list_ca(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        subject_id=subject_id,
        student_id=student_id,
        assessment_type=assessment_type,
        page=page,
        page_size=page_size,
    )

    return [
        CAWithDetailsResponse(
            id=ca.id,
            tenant_id=ca.tenant_id,
            academic_year_id=ca.academic_year_id,
            term_id=ca.term_id,
            class_id=ca.class_id,
            subject_id=ca.subject_id,
            student_id=ca.student_id,
            assessment_type=ca.assessment_type.value,
            title=ca.title,
            max_score=ca.max_score,
            score=ca.score,
            assessment_date=ca.assessment_date,
            entered_by=ca.entered_by,
            created_at=ca.created_at,
            updated_at=ca.updated_at,
            student_name=f"{ca.student.first_name} {ca.student.last_name}" if ca.student else "",
            student_id_number=ca.student.student_id if ca.student else "",
            subject_name=ca.subject.name if ca.subject else "",
            class_name=ca.class_.name if ca.class_ else "",
        )
        for ca in entries
    ]


@router.get(
    "/ca/summary",
    response_model=list[CASummaryResponse],
    summary="Get CA summary",
    dependencies=[Depends(require_permissions("exams.ca.read"))],
)
async def get_ca_summary(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: UUID = Query(...),
    subject_id: UUID = Query(...),
) -> list[CASummaryResponse]:
    """Get CA summary totals per student for a subject."""
    service = CAService(db)
    summaries = await service.get_ca_summary(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        subject_id=subject_id,
    )

    return [CASummaryResponse(**s) for s in summaries]


@router.put(
    "/ca/{ca_id}",
    response_model=CAResponse,
    summary="Update CA entry",
    dependencies=[Depends(require_permissions("exams.ca.enter"))],
)
async def update_ca(
    ca_id: UUID,
    data: CAUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> CAResponse:
    """Update a CA entry."""
    service = CAService(db)
    ca = await service.update_ca(
        ca_id=ca_id,
        tenant_id=tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )

    if not ca:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CA entry not found",
        )

    return CAResponse(
        id=ca.id,
        tenant_id=ca.tenant_id,
        academic_year_id=ca.academic_year_id,
        term_id=ca.term_id,
        class_id=ca.class_id,
        subject_id=ca.subject_id,
        student_id=ca.student_id,
        assessment_type=ca.assessment_type.value,
        title=ca.title,
        max_score=ca.max_score,
        score=ca.score,
        assessment_date=ca.assessment_date,
        entered_by=ca.entered_by,
        created_at=ca.created_at,
        updated_at=ca.updated_at,
    )


@router.delete(
    "/ca/{ca_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete CA entry",
    dependencies=[Depends(require_permissions("exams.ca.delete"))],
)
async def delete_ca(
    ca_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Delete a CA entry."""
    service = CAService(db)
    deleted = await service.delete_ca(ca_id, tenant.tenant_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CA entry not found",
        )
