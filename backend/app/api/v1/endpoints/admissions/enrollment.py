"""
SIMS Plus - Enrollment Endpoints (Applicant -> Student Conversion)

Admin endpoints for converting accepted applicants into student records.
Supports both single and bulk enrollment with idempotency.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    BulkEnrollRequest,
    BulkEnrollResponse,
    EnrollRequest,
    EnrollResponse,
)
from app.services.admissions import EnrollmentError, EnrollmentService

logger = structlog.get_logger(__name__)

router = APIRouter()


def _handle_error(e: EnrollmentError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_STATUS": 422,
        "SCHOOL_NOT_FOUND": 404,
        "INVOICE_GENERATION_FAILED": 500,
        # Phase 3: checklist and deposit guards
        "CHECKLIST_INCOMPLETE": 422,
        "DEPOSIT_REQUIRED": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "/applications/{application_id}/enroll",
    response_model=EnrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll accepted applicant",
    dependencies=[Depends(require_permissions("admissions.enroll"))],
)
async def enroll_applicant(
    application_id: UUID,
    data: EnrollRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EnrollResponse:
    """
    Convert an accepted applicant into a student record.

    Atomic operation within a single transaction:
    1. Validate application status is ACCEPTED
    2. Check idempotency (converted_student_id must be NULL)
    3. Create/link Guardian records (deduplicate by email OR phone)
    4. Create Student record with auto-generated student ID
    5. Create StudentGuardian junction records
    6. Generate invoice (if generate_invoice=true and fee structure exists)
    7. Update application status to ENROLLED
    8. Create parent User account if guardian has email
    9. Send enrollment notification to guardian

    If application already has converted_student_id (idempotency),
    returns the existing student without creating a duplicate.
    """
    service = EnrollmentService(db)
    try:
        # enroll() takes positional args: tenant_id, school_id, application_id, enrolled_by
        result = await service.enroll(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            application_id=application_id,
            enrolled_by=UUID(user["user_id"]),
        )
        return result
    except EnrollmentError as e:
        raise _handle_error(e)


@router.post(
    "/enroll/bulk",
    response_model=BulkEnrollResponse,
    summary="Bulk enroll accepted applicants",
    dependencies=[Depends(require_permissions("admissions.enroll"))],
)
async def bulk_enroll(
    data: BulkEnrollRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkEnrollResponse:
    """
    Bulk enroll accepted applicants.

    Each enrollment runs in its own savepoint (session.begin_nested()):
    - Failed enrollments don't affect successful ones
    - Returns partial success: {succeeded: [...], failed: [...]}
    - If ALL fail -> HTTP 422; if some succeed -> HTTP 200
    - Max 50 applications per request

    Common failure reasons:
    - Application not in ACCEPTED status
    - Guardian email conflict with existing guardian in different record
    - Missing fee structure for target class
    """
    service = EnrollmentService(db)
    # bulk_enroll() takes positional args: tenant_id, school_id, application_ids, enrolled_by
    result = await service.bulk_enroll(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        application_ids=data.application_ids,
        enrolled_by=UUID(user["user_id"]),
    )

    succeeded = result["succeeded"]
    failed = result["failed"]

    # If every enrollment failed, return 422 to signal complete failure
    if len(succeeded) == 0 and len(failed) > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "All enrollments failed",
                "failed": failed,
            },
        )

    return BulkEnrollResponse(
        succeeded=succeeded,
        failed=failed,
        total_succeeded=len(succeeded),
        total_failed=len(failed),
    )
