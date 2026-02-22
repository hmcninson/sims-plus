"""
SIMS Plus - Boarding Assignment Endpoints

Endpoints for assigning students to boarding houses, dormitories, and beds.
Supports individual assignment, bulk assignment, unassignment, and querying
unassigned boarders.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.boarding import (
    StudentBoardingBulkAssign,
    StudentBoardingCreate,
    StudentBoardingDetailResponse,
    StudentBoardingResponse,
    StudentBoardingUpdate,
)
from app.services.boarding import BoardingAssignmentService, BoardingServiceError

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


@router.post(
    "/assignments",
    response_model=StudentBoardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign student to boarding",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def assign_student(
    data: StudentBoardingCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentBoardingResponse:
    """Assign a student to a boarding house for an academic year."""
    school_id = _get_school_id(user)
    service = BoardingAssignmentService(db)

    try:
        assignment = await service.assign_student(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            student_id=data.student_id,
            house_id=data.house_id,
            dormitory_id=data.dormitory_id,
            bed_id=data.bed_id,
            academic_year_id=data.academic_year_id,
            check_in_date=data.check_in_date,
        )
        return StudentBoardingResponse.model_validate(assignment)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/assignments",
    response_model=list[StudentBoardingDetailResponse],
    summary="List boarding assignments",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_assignments(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    house_id: UUID | None = Query(None, description="Filter by house"),
    academic_year_id: UUID | None = Query(None, description="Filter by academic year"),
    assignment_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status (active, withdrawn, suspended, graduated)",
    ),
) -> list[StudentBoardingDetailResponse]:
    """List boarding assignments with optional filters."""
    school_id = _get_school_id(user)
    service = BoardingAssignmentService(db)

    assignments = await service.get_assignments(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        house_id=house_id,
        academic_year_id=academic_year_id,
        status=assignment_status,
    )

    results = []
    for a in assignments:
        results.append(
            StudentBoardingDetailResponse(
                id=a.id,
                tenant_id=a.tenant_id,
                school_id=a.school_id,
                student_id=a.student_id,
                house_id=a.house_id,
                dormitory_id=a.dormitory_id,
                bed_id=a.bed_id,
                academic_year_id=a.academic_year_id,
                boarding_status=a.boarding_status.value
                if hasattr(a.boarding_status, "value")
                else a.boarding_status,
                check_in_date=a.check_in_date,
                check_out_date=a.check_out_date,
                created_at=a.created_at,
                updated_at=a.updated_at,
                student_name=f"{a.student.first_name} {a.student.last_name}"
                if a.student
                else None,
                house_name=a.house.name if a.house else None,
                dormitory_name=a.dormitory.name if a.dormitory else None,
                bed_number=a.bed.bed_number if a.bed else None,
                academic_year_name=a.academic_year.name
                if a.academic_year
                else None,
            )
        )
    return results


# Static sub-paths must be declared before parameterized routes to prevent
# FastAPI from trying to parse "unassigned" or "bulk" as UUID path params.
@router.get(
    "/assignments/unassigned",
    summary="Get unassigned boarders",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_unassigned_boarders(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(..., description="Academic year to check"),
) -> list[dict]:
    """
    Get students marked as boarders who are not yet assigned to a house
    for the specified academic year.
    """
    school_id = _get_school_id(user)
    service = BoardingAssignmentService(db)

    students = await service.get_unassigned_boarders(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        academic_year_id=academic_year_id,
    )

    return [
        {
            "id": str(s.id),
            "first_name": s.first_name,
            "last_name": s.last_name,
            "student_id": s.student_id,
        }
        for s in students
    ]


@router.post(
    "/assignments/bulk",
    summary="Bulk assign students",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def bulk_assign_students(
    data: StudentBoardingBulkAssign,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """
    Assign multiple students to a house without specific bed assignments.

    This is useful for initial house allocation at the start of a term.
    Returns a summary with created, skipped, and failed counts.
    """
    school_id = _get_school_id(user)
    service = BoardingAssignmentService(db)

    try:
        result = await service.bulk_assign(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            student_ids=data.student_ids,
            house_id=data.house_id,
            academic_year_id=data.academic_year_id,
            check_in_date=data.check_in_date,
        )
        return result
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/assignments/{assignment_id}",
    response_model=StudentBoardingDetailResponse,
    summary="Get assignment detail",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_assignment(
    assignment_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentBoardingDetailResponse:
    """Get a boarding assignment by ID with full detail."""
    service = BoardingAssignmentService(db)

    try:
        a = await service.get_assignment(
            tenant_id=tenant.tenant_id,
            assignment_id=assignment_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    return StudentBoardingDetailResponse(
        id=a.id,
        tenant_id=a.tenant_id,
        school_id=a.school_id,
        student_id=a.student_id,
        house_id=a.house_id,
        dormitory_id=a.dormitory_id,
        bed_id=a.bed_id,
        academic_year_id=a.academic_year_id,
        boarding_status=a.boarding_status.value
        if hasattr(a.boarding_status, "value")
        else a.boarding_status,
        check_in_date=a.check_in_date,
        check_out_date=a.check_out_date,
        created_at=a.created_at,
        updated_at=a.updated_at,
        student_name=f"{a.student.first_name} {a.student.last_name}"
        if a.student
        else None,
        house_name=a.house.name if a.house else None,
        dormitory_name=a.dormitory.name if a.dormitory else None,
        bed_number=a.bed.bed_number if a.bed else None,
        academic_year_name=a.academic_year.name if a.academic_year else None,
    )


@router.put(
    "/assignments/{assignment_id}",
    response_model=StudentBoardingResponse,
    summary="Update assignment",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def update_assignment(
    assignment_id: UUID,
    data: StudentBoardingUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentBoardingResponse:
    """Update a boarding assignment (e.g., move to different bed or dormitory)."""
    service = BoardingAssignmentService(db)

    try:
        assignment = await service.update_assignment(
            tenant_id=tenant.tenant_id,
            assignment_id=assignment_id,
            data=data.model_dump(exclude_unset=True),
        )
        return StudentBoardingResponse.model_validate(assignment)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/assignments/{assignment_id}/unassign",
    response_model=StudentBoardingResponse,
    summary="Unassign student",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def unassign_student(
    assignment_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentBoardingResponse:
    """
    Unassign a student from boarding (check out).

    Sets the check_out_date to today and releases the assigned bed.
    """
    service = BoardingAssignmentService(db)

    try:
        assignment = await service.unassign_student(
            tenant_id=tenant.tenant_id,
            assignment_id=assignment_id,
        )
        return StudentBoardingResponse.model_validate(assignment)
    except BoardingServiceError as e:
        raise _handle_service_error(e)
