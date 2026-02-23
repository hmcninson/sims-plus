"""
SIMS Plus - Scholarship Endpoints

Endpoints for scholarship management: CRUD, award, bulk award, revoke, recipients.
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy import select

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    OptionalSchoolCtx,
    RequestTenant,
    SchoolCtx,
    require_permissions,
)
from app.models.academic import AcademicYear
from app.schemas.finance import (
    ScholarshipCreate,
    ScholarshipUpdate,
    ScholarshipResponse,
    ScholarshipWithStatsResponse,
    ScholarshipListResponse,
    ScholarshipAward,
    ScholarshipBulkAward,
    ScholarshipBulkAwardResult,
    ScholarshipRevoke,
    StudentScholarshipResponse,
    StudentScholarshipWithDetailsResponse,
    StudentScholarshipListResponse,
)
from app.services.finance import ScholarshipService, FinanceAuditService, FinanceServiceError

from ._helpers import (
    _build_scholarship_response,
    _build_student_scholarship_response,
)

router = APIRouter()


@router.post(
    "/scholarships",
    response_model=ScholarshipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create scholarship",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_scholarship(
    data: ScholarshipCreate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ScholarshipResponse:
    """Create a new scholarship."""
    service = ScholarshipService(db)
    try:
        scholarship = await service.create_scholarship(
            tenant_id=school_ctx.tenant_id,
            school_id=school_ctx.school_id,
            name=data.name,
            code=data.code,
            description=data.description,
            scholarship_type=data.scholarship_type,
            coverage_type=data.coverage_type,
            coverage_value=data.coverage_value,
            applicable_fees=data.applicable_fees,
            max_recipients=data.max_recipients,
            academic_year_id=data.academic_year_id,
            eligibility_criteria=data.eligibility_criteria,
            is_active=data.is_active,
            created_by=UUID(user_id),
        )
        # Log audit trail for scholarship creation
        audit_service = FinanceAuditService(db)
        await audit_service.log_create(
            tenant_id=school_ctx.tenant_id,
            entity_type="scholarship",
            entity_id=scholarship.id,
            performed_by=UUID(user_id),
            metadata={"name": scholarship.name, "code": scholarship.code},
        )
        return ScholarshipResponse(
            id=scholarship.id,
            tenant_id=scholarship.tenant_id,
            school_id=scholarship.school_id,
            name=scholarship.name,
            code=scholarship.code,
            description=scholarship.description,
            scholarship_type=scholarship.scholarship_type.value,
            coverage_type=scholarship.coverage_type.value,
            coverage_value=scholarship.coverage_value,
            applicable_fees=scholarship.applicable_fees,
            max_recipients=scholarship.max_recipients,
            academic_year_id=scholarship.academic_year_id,
            eligibility_criteria=scholarship.eligibility_criteria,
            is_active=scholarship.is_active,
            created_at=scholarship.created_at,
            updated_at=scholarship.updated_at,
        )
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/scholarships",
    response_model=ScholarshipListResponse,
    summary="List scholarships",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_scholarships(
    tenant: RequestTenant,
    db: DatabaseSession,
    school_ctx: OptionalSchoolCtx,
    academic_year_id: Optional[UUID] = Query(None),
    scholarship_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ScholarshipListResponse:
    """List all scholarships with filters."""
    # Chain support: scope to active school when header is present
    school_id = school_ctx.school_id if school_ctx else None
    service = ScholarshipService(db)
    scholarships, total = await service.list_scholarships(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        academic_year_id=academic_year_id,
        scholarship_type=scholarship_type,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return ScholarshipListResponse(
        items=[_build_scholarship_response(s) for s in scholarships],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/scholarships/{scholarship_id}",
    response_model=ScholarshipWithStatsResponse,
    summary="Get scholarship",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_scholarship(
    scholarship_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ScholarshipWithStatsResponse:
    """Get scholarship by ID."""
    service = ScholarshipService(db)
    scholarship = await service.get_scholarship(tenant.tenant_id, scholarship_id)
    if not scholarship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found",
        )
    return _build_scholarship_response(scholarship)


@router.put(
    "/scholarships/{scholarship_id}",
    response_model=ScholarshipResponse,
    summary="Update scholarship",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_scholarship(
    scholarship_id: UUID,
    data: ScholarshipUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ScholarshipResponse:
    """Update scholarship."""
    service = ScholarshipService(db)
    try:
        scholarship = await service.update_scholarship(
            tenant.tenant_id,
            scholarship_id,
            **data.model_dump(exclude_unset=True),
        )
        if not scholarship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scholarship not found",
            )
        # Log audit trail for scholarship update
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="scholarship",
            entity_id=scholarship.id,
            action="update",
            performed_by=UUID(user_id),
        )
        return ScholarshipResponse(
            id=scholarship.id,
            tenant_id=scholarship.tenant_id,
            school_id=scholarship.school_id,
            name=scholarship.name,
            code=scholarship.code,
            description=scholarship.description,
            scholarship_type=scholarship.scholarship_type.value,
            coverage_type=scholarship.coverage_type.value,
            coverage_value=scholarship.coverage_value,
            applicable_fees=scholarship.applicable_fees,
            max_recipients=scholarship.max_recipients,
            academic_year_id=scholarship.academic_year_id,
            eligibility_criteria=scholarship.eligibility_criteria,
            is_active=scholarship.is_active,
            created_at=scholarship.created_at,
            updated_at=scholarship.updated_at,
        )
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/scholarships/{scholarship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete scholarship",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_scholarship(
    scholarship_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> None:
    """Delete scholarship."""
    service = ScholarshipService(db)
    if not await service.delete_scholarship(tenant.tenant_id, scholarship_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found",
        )
    # Log audit trail for scholarship deletion (soft delete)
    audit_service = FinanceAuditService(db)
    await audit_service.log(
        tenant_id=tenant.tenant_id,
        entity_type="scholarship",
        entity_id=scholarship_id,
        action="delete",
        performed_by=UUID(user_id),
    )


@router.post(
    "/scholarships/{scholarship_id}/award",
    response_model=StudentScholarshipWithDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Award scholarship",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def award_scholarship(
    scholarship_id: UUID,
    data: ScholarshipAward,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> StudentScholarshipWithDetailsResponse:
    """Award scholarship to a student."""
    # Get current academic year
    year_result = await db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.tenant_id == tenant.tenant_id,
            AcademicYear.is_current == True,
        )
        .limit(1)
    )
    academic_year = year_result.scalar_one_or_none()
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current academic year found",
        )

    service = ScholarshipService(db)
    try:
        student_scholarship = await service.award_scholarship(
            tenant_id=tenant.tenant_id,
            scholarship_id=scholarship_id,
            student_id=data.student_id,
            academic_year_id=academic_year.id,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            coverage_override=data.coverage_override,
            notes=data.notes,
            awarded_by=UUID(user_id),
            # Enhanced award settings
            justification=data.justification,
            renewal_type=data.renewal_type,
            is_provisional=data.is_provisional,
            provisional_conditions=data.provisional_conditions,
            # Reinstatement
            reinstated_from=data.reinstated_from,
        )
        # Log audit trail for scholarship award
        audit_service = FinanceAuditService(db)
        await audit_service.log_scholarship_award(
            tenant_id=tenant.tenant_id,
            student_scholarship_id=student_scholarship.id,
            performed_by=UUID(user_id),
            metadata={
                "scholarship_id": str(scholarship_id),
                "student_id": str(data.student_id),
            },
        )
        return _build_student_scholarship_response(student_scholarship)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/scholarships/{scholarship_id}/award-bulk",
    response_model=ScholarshipBulkAwardResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk award scholarship",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def bulk_award_scholarship(
    scholarship_id: UUID,
    data: ScholarshipBulkAward,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ScholarshipBulkAwardResult:
    """Award scholarship to multiple students at once."""
    # Get current academic year
    year_result = await db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.tenant_id == tenant.tenant_id,
            AcademicYear.is_current == True,
        )
        .limit(1)
    )
    academic_year = year_result.scalar_one_or_none()
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current academic year found",
        )

    service = ScholarshipService(db)
    try:
        result = await service.bulk_award_scholarship(
            tenant_id=tenant.tenant_id,
            scholarship_id=scholarship_id,
            student_ids=data.student_ids,
            academic_year_id=academic_year.id,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            coverage_override=data.coverage_override,
            notes=data.notes,
            awarded_by=UUID(user_id),
            # Enhanced award settings
            justification=data.justification,
            renewal_type=data.renewal_type,
            is_provisional=data.is_provisional,
            provisional_conditions=data.provisional_conditions,
        )
        # Log audit trail for each successfully awarded scholarship
        audit_service = FinanceAuditService(db)
        for ss_id in result.get("student_scholarship_ids", []):
            await audit_service.log_scholarship_award(
                tenant_id=tenant.tenant_id,
                student_scholarship_id=ss_id,
                performed_by=UUID(user_id),
                metadata={
                    "scholarship_id": str(scholarship_id),
                    "bulk_award": True,
                },
            )
        return ScholarshipBulkAwardResult(**result)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/scholarships/{scholarship_id}/recipients/{student_scholarship_id}/revoke",
    response_model=StudentScholarshipResponse,
    summary="Revoke scholarship",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def revoke_scholarship(
    scholarship_id: UUID,
    student_scholarship_id: UUID,
    data: ScholarshipRevoke,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> StudentScholarshipResponse:
    """Revoke a student's scholarship."""
    service = ScholarshipService(db)
    try:
        student_scholarship = await service.revoke_scholarship(
            tenant_id=tenant.tenant_id,
            student_scholarship_id=student_scholarship_id,
            revoked_by=UUID(user_id),
            reason=data.reason,
        )
        if not student_scholarship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student scholarship not found",
            )
        # Log audit trail for scholarship revocation
        audit_service = FinanceAuditService(db)
        await audit_service.log_scholarship_revoke(
            tenant_id=tenant.tenant_id,
            student_scholarship_id=student_scholarship_id,
            performed_by=UUID(user_id),
            reason=data.reason,
        )
        return StudentScholarshipResponse.model_validate(student_scholarship)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/scholarships/{scholarship_id}/recipients",
    response_model=StudentScholarshipListResponse,
    summary="Get scholarship recipients",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_scholarship_recipients(
    scholarship_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    recipient_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StudentScholarshipListResponse:
    """Get all recipients of a scholarship."""
    service = ScholarshipService(db)
    recipients, total = await service.get_scholarship_recipients(
        tenant_id=tenant.tenant_id,
        scholarship_id=scholarship_id,
        academic_year_id=academic_year_id,
        status=recipient_status,
        page=page,
        page_size=page_size,
    )

    return StudentScholarshipListResponse(
        items=[_build_student_scholarship_response(r) for r in recipients],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/students/{student_id}/scholarships",
    response_model=StudentScholarshipListResponse,
    summary="Get student scholarships",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_student_scholarships(
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    scholarship_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StudentScholarshipListResponse:
    """Get all scholarships for a student."""
    service = ScholarshipService(db)
    scholarships = await service.get_student_scholarships(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        status=scholarship_status,
    )

    # Manual pagination since service returns all
    total = len(scholarships)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = scholarships[start:end]

    return StudentScholarshipListResponse(
        items=[_build_student_scholarship_response(s) for s in page_items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )
