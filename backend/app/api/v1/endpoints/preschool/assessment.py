"""
SIMS Plus - Preschool Assessment Endpoints

API routes for student skill assessments (single and bulk).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    StudentSkillAssessmentCreate,
    StudentSkillAssessmentBulk,
    StudentSkillAssessmentResponse,
    BulkAssessmentResult,
    convert_uuid,
)

router = APIRouter()


# =========================
# Student Assessments
# =========================


@router.get(
    "/assessments",
    response_model=list[StudentSkillAssessmentResponse],
    summary="List assessments",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_assessments(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    term_id: UUID | None = Query(None),
    learning_area_id: UUID | None = Query(None),
):
    """List assessments with optional filters."""
    service = PreschoolService(db)
    return await service.list_assessments(
        convert_uuid(tenant.tenant_id), student_id, term_id, learning_area_id
    )


@router.post(
    "/assessments",
    response_model=StudentSkillAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update assessment",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_or_update_assessment(
    data: StudentSkillAssessmentCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create or update a skill assessment."""
    service = PreschoolService(db)
    try:
        return await service.create_or_update_assessment(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/assessments/bulk",
    response_model=BulkAssessmentResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk assess",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def bulk_assess(
    data: StudentSkillAssessmentBulk,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Bulk create/update assessments for a student."""
    service = PreschoolService(db)
    try:
        result = await service.bulk_assess(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return BulkAssessmentResult(**result)


@router.get(
    "/assessments/student/{student_id}",
    response_model=list[StudentSkillAssessmentResponse],
    summary="Get student assessments",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_student_assessments(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    term_id: UUID | None = Query(None),
):
    """Get all assessments for a student."""
    service = PreschoolService(db)
    return await service.list_assessments(
        convert_uuid(tenant.tenant_id), student_id, term_id
    )
