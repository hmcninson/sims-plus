"""
SIMS Plus - Staff CRUD, Import/Export, and Assignment Endpoints
"""

import csv
import io
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    StaffResponse,
    StaffListResponse,
    StaffStatsResponse,
    StaffSensitiveFieldsResponse,
    StaffWithAssignmentsResponse,
    StaffAssignmentCreate,
    StaffAssignmentUpdate,
    StaffAssignmentResponse,
)
from app.services.staff import StaffService, StaffServiceError
from app.services.staff.workload_service import StaffWorkloadService
from app.schemas.staff import (
    StaffWorkloadResponse,
    StaffWorkloadSummaryItem,
)
from app.models.school import School
from app.models.staff import Staff

router = APIRouter()


def _mask_sensitive(value: Optional[str]) -> Optional[str]:
    """Mask sensitive PII fields, showing only last 4 characters."""
    if not value:
        return None
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def _build_staff_response(staff: Staff) -> StaffResponse:
    """Build a StaffResponse from a Staff model, masking sensitive PII."""
    return StaffResponse(
        id=staff.id,
        staff_id=staff.staff_id,
        first_name=staff.first_name,
        middle_name=staff.middle_name,
        last_name=staff.last_name,
        date_of_birth=staff.date_of_birth,
        gender=staff.gender.value,
        email=staff.email,
        phone=staff.phone,
        phone_secondary=staff.phone_secondary,
        address=staff.address,
        city=staff.city,
        region=staff.region,
        emergency_contact_name=staff.emergency_contact_name,
        emergency_contact_phone=staff.emergency_contact_phone,
        emergency_contact_relationship=staff.emergency_contact_relationship,
        # Mask sensitive PII: show only last 4 digits
        ghana_card_number=_mask_sensitive(staff.ghana_card_number),
        ssnit_number=_mask_sensitive(staff.ssnit_number),
        teacher_license_number=staff.teacher_license_number,
        staff_type=staff.staff_type.value,
        status=staff.status.value,
        job_title=staff.job_title,
        department=staff.department,
        department_id=staff.department_id,
        employment_date=staff.employment_date,
        termination_date=staff.termination_date,
        qualifications=staff.qualifications,
        # Mask sensitive banking PII
        bank_name=_mask_sensitive(staff.bank_name),
        bank_branch=_mask_sensitive(staff.bank_branch),
        account_number=_mask_sensitive(staff.account_number),
        photo_url=staff.photo_url,
        notes=staff.notes,
        school_id=staff.school_id,
        user_id=staff.user_id,
        created_at=staff.created_at,
        updated_at=staff.updated_at,
        # HR gap closure fields
        tin_number=_mask_sensitive(staff.tin_number),
        employment_type=staff.employment_type.value if staff.employment_type and hasattr(staff.employment_type, "value") else staff.employment_type,
        ges_staff_id=staff.ges_staff_id,
        nationality=staff.nationality,
        marital_status=staff.marital_status,
        # Relationships
        school_name=staff.school.name if staff.school else None,
    )


# =========================
# Staff Import/Export Endpoints
# =========================


EXPORT_COLUMNS = [
    "staff_id", "first_name", "middle_name", "last_name", "email", "phone",
    "phone_secondary", "gender", "date_of_birth", "address", "city", "region",
    "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
    "ghana_card_number", "ssnit_number", "teacher_license_number",
    "staff_type", "status", "job_title", "department", "employment_date",
    "termination_date", "bank_name", "bank_branch", "account_number",
    "tin_number", "employment_type", "ges_staff_id", "nationality", "marital_status",
    "notes",
]


@router.get(
    "/export",
    summary="Export staff to CSV",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def export_staff(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    staff_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
) -> StreamingResponse:
    """Export staff to CSV format."""
    service = StaffService(db)
    staff_list, _ = await service.list_staff(
        tenant_id=tenant.tenant_id,
        staff_type=staff_type,
        status=status,
        department=department,
        page=1,
        page_size=10000,  # Export all
    )

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()

    for staff in staff_list:
        row = {
            "staff_id": staff.staff_id,
            "first_name": staff.first_name,
            "middle_name": staff.middle_name or "",
            "last_name": staff.last_name,
            "email": staff.email,
            "phone": staff.phone,
            "phone_secondary": staff.phone_secondary or "",
            "gender": staff.gender.value if hasattr(staff.gender, 'value') else staff.gender,
            "date_of_birth": str(staff.date_of_birth) if staff.date_of_birth else "",
            "address": staff.address or "",
            "city": staff.city or "",
            "region": staff.region or "",
            "emergency_contact_name": staff.emergency_contact_name or "",
            "emergency_contact_phone": staff.emergency_contact_phone or "",
            "emergency_contact_relationship": staff.emergency_contact_relationship or "",
            "ghana_card_number": staff.ghana_card_number or "",
            "ssnit_number": staff.ssnit_number or "",
            "teacher_license_number": staff.teacher_license_number or "",
            "staff_type": staff.staff_type.value if hasattr(staff.staff_type, 'value') else staff.staff_type,
            "status": staff.status.value if hasattr(staff.status, 'value') else staff.status,
            "job_title": staff.job_title,
            "department": staff.department or "",
            "employment_date": str(staff.employment_date) if staff.employment_date else "",
            "termination_date": str(staff.termination_date) if staff.termination_date else "",
            "bank_name": staff.bank_name or "",
            "bank_branch": staff.bank_branch or "",
            "account_number": staff.account_number or "",
            "tin_number": staff.tin_number or "",
            "employment_type": staff.employment_type.value if staff.employment_type and hasattr(staff.employment_type, "value") else (staff.employment_type or ""),
            "ges_staff_id": staff.ges_staff_id or "",
            "nationality": staff.nationality or "",
            "marital_status": staff.marital_status or "",
            "notes": staff.notes or "",
        }
        writer.writerow(row)

    output.seek(0)

    # Generate filename with timestamp
    filename = f"staff_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get(
    "/export/template",
    summary="Download staff import template",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def export_template() -> StreamingResponse:
    """Download a CSV template for staff import."""
    output = io.StringIO()

    # Columns for import (excluding auto-generated staff_id)
    # Note: staff_id is NOT in template - it's always auto-generated
    # previous_staff_id can be used to preserve IDs from previous/external systems
    import_columns = [
        "previous_staff_id", "first_name", "middle_name", "last_name", "email", "phone",
        "phone_secondary", "gender", "date_of_birth", "address", "city", "region",
        "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
        "ghana_card_number", "ssnit_number", "teacher_license_number",
        "staff_type", "status", "job_title", "department", "employment_date",
        "bank_name", "bank_branch", "account_number", "notes"
    ]

    writer = csv.DictWriter(output, fieldnames=import_columns)
    writer.writeheader()

    # Add example row
    example = {
        "previous_staff_id": "OLD-SYS-001",
        "first_name": "John",
        "middle_name": "Kwame",
        "last_name": "Mensah",
        "email": "john.mensah@example.com",
        "phone": "+233201234567",
        "phone_secondary": "",
        "gender": "male",
        "date_of_birth": "1990-01-15",
        "address": "123 Main Street",
        "city": "Accra",
        "region": "Greater Accra",
        "emergency_contact_name": "Mary Mensah",
        "emergency_contact_phone": "+233209876543",
        "emergency_contact_relationship": "Spouse",
        "ghana_card_number": "GHA-123456789-0",
        "ssnit_number": "A12345678",
        "teacher_license_number": "GES-2020-1234",
        "staff_type": "teaching",
        "status": "active",
        "job_title": "Mathematics Teacher",
        "department": "Science",
        "employment_date": "2020-09-01",
        "bank_name": "GCB Bank",
        "bank_branch": "Accra Main",
        "account_number": "1234567890",
        "notes": "Sample staff member",
    }
    writer.writerow(example)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=staff_import_template.csv"}
    )


@router.post(
    "/import",
    summary="Import staff from CSV",
    description="Import staff from a CSV file. Supports preview mode to validate data before importing.",
    dependencies=[Depends(require_permissions("staff.create"))],
)
async def import_staff(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    file: UploadFile = File(..., description="CSV file with staff data"),
    preview: bool = Form(default=False, description="If true, only preview without creating"),
) -> dict:
    """
    Import staff from a CSV file.

    The file should have a header row with column names. Columns are auto-mapped to staff fields.

    Supported columns:
    - previous_staff_id (optional) - ID from previous/external system
    - first_name (required)
    - middle_name
    - last_name (required)
    - email (required)
    - phone (required)
    - gender (required) - values: M/F, Male/Female
    - job_title (required)
    - employment_date (required) - formats: YYYY-MM-DD, DD/MM/YYYY
    - staff_type - values: teaching, non_teaching, administrative
    - status - values: active, on_leave, suspended, terminated, retired
    - department
    - date_of_birth
    - And many more optional fields...

    Note: Staff ID is always auto-generated by the system using the school's prefix.
    Use previous_staff_id to preserve IDs from previous/external systems.

    Set preview=true to validate data without importing.
    Returns preview data in preview mode, or import results in import mode.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )

    # Read file content
    content = await file.read()

    # Validate file is not empty
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )

    # Import staff using service
    service = StaffService(db)
    try:
        result = await service.import_staff_from_file(
            tenant_id=tenant.tenant_id,
            file_content=content,
            file_type="csv",
            preview_only=preview,
        )
        return result
    except StaffServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


# =========================
# Staff Endpoints
# =========================


@router.get(
    "/generate-id",
    response_model=dict,
    summary="Generate staff ID",
    dependencies=[Depends(require_permissions("staff.create"))],
)
async def generate_staff_id(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(default=None, description="School ID to get prefix from"),
) -> dict:
    """Generate a unique staff ID for the tenant using school's configured prefix."""
    service = StaffService(db)

    # Get the school's staff_id_prefix
    prefix = "STF"  # Default fallback

    if school_id:
        # Fetch prefix from specific school
        result = await db.execute(
            select(School.staff_id_prefix).where(School.id == school_id)
        )
        school_prefix = result.scalar_one_or_none()
        if school_prefix:
            prefix = school_prefix
    else:
        # Fetch prefix from tenant's first school (single-school tenants)
        result = await db.execute(
            select(School.staff_id_prefix).where(School.tenant_id == tenant.tenant_id).limit(1)
        )
        school_prefix = result.scalar_one_or_none()
        if school_prefix:
            prefix = school_prefix

    try:
        staff_id = await service.generate_staff_id(tenant.tenant_id, prefix)
        return {"staff_id": staff_id}
    except StaffServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create staff",
    dependencies=[Depends(require_permissions("staff.create"))],
)
async def create_staff(
    data: StaffCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffResponse:
    """Create a new staff member.

    Staff ID can be provided or will be auto-generated by the system.
    """
    service = StaffService(db)

    # Check if staff_id was provided or needs to be generated
    provided_staff_id = data.staff_id
    prefix = "STF"  # Default fallback

    if not provided_staff_id:
        # Get the school's staff_id_prefix for auto-generation
        result = await db.execute(
            select(School.staff_id_prefix).where(School.tenant_id == tenant.tenant_id).limit(1)
        )
        school_prefix = result.scalar_one_or_none()
        if school_prefix:
            prefix = school_prefix

    max_retries = 5 if not provided_staff_id else 1  # Only retry for auto-generated IDs

    # Retry loop for handling concurrent ID generation conflicts
    last_error = None
    for attempt in range(max_retries):
        try:
            # Use provided ID or generate a new one
            staff_id = provided_staff_id or await service.generate_staff_id(tenant.tenant_id, prefix)

            staff = await service.create_staff(
                tenant_id=tenant.tenant_id,
                staff_id=staff_id,
                first_name=data.first_name,
                middle_name=data.middle_name,
                last_name=data.last_name,
                date_of_birth=data.date_of_birth,
                gender=data.gender,
                email=data.email,
                phone=data.phone,
                phone_secondary=data.phone_secondary,
                address=data.address,
                city=data.city,
                region=data.region,
                emergency_contact_name=data.emergency_contact_name,
                emergency_contact_phone=data.emergency_contact_phone,
                emergency_contact_relationship=data.emergency_contact_relationship,
                ghana_card_number=data.ghana_card_number,
                ssnit_number=data.ssnit_number,
                teacher_license_number=data.teacher_license_number,
                staff_type=data.staff_type,
                status=data.status,
                job_title=data.job_title,
                department=data.department,
                department_id=data.department_id,
                employment_date=data.employment_date,
                termination_date=data.termination_date,
                qualifications=data.qualifications,
                bank_name=data.bank_name,
                bank_branch=data.bank_branch,
                account_number=data.account_number,
                photo_url=data.photo_url,
                notes=data.notes,
                school_id=data.school_id,
                user_id=data.user_id,
                tin_number=data.tin_number,
                employment_type=data.employment_type,
                ges_staff_id=data.ges_staff_id,
                nationality=data.nationality,
                marital_status=data.marital_status,
            )

            return _build_staff_response(staff)

        except StaffServiceError as e:
            last_error = e
            # Only retry on duplicate ID errors
            if e.code == "duplicate_staff_id":
                import asyncio
                await asyncio.sleep(0.01 * (attempt + 1))
                continue
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=last_error.message if last_error else "Failed to create staff after multiple attempts"
    )


@router.get(
    "/",
    response_model=dict,
    summary="List staff",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def list_staff(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    search: Optional[str] = Query(None, description="Search by name, email, or staff ID"),
    staff_type: Optional[str] = Query(None, description="Filter by staff type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    department: Optional[str] = Query(None, description="Filter by department"),
    school_id: Optional[UUID] = Query(None, description="Filter by school"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> dict:
    """List staff with filters and pagination."""
    service = StaffService(db)
    staff_list, total = await service.list_staff(
        tenant_id=tenant.tenant_id,
        search=search,
        staff_type=staff_type,
        status=status,
        gender=gender,
        department=department,
        school_id=school_id,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": [
            StaffListResponse(
                id=s.id,
                staff_id=s.staff_id,
                first_name=s.first_name,
                middle_name=s.middle_name,
                last_name=s.last_name,
                gender=s.gender.value,
                email=s.email,
                phone=s.phone,
                staff_type=s.staff_type.value,
                status=s.status.value,
                job_title=s.job_title,
                department=s.department,
                photo_url=s.photo_url,
            )
            for s in staff_list
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get(
    "/teaching",
    response_model=list[StaffListResponse],
    summary="List teaching staff",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def list_teaching_staff(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(None, description="Filter by school"),
) -> list[StaffListResponse]:
    """List all teaching staff (no pagination, for dropdowns)."""
    service = StaffService(db)
    staff_list, _ = await service.list_staff(
        tenant_id=tenant.tenant_id,
        staff_type="teaching",
        status="active",
        school_id=school_id,
        page=1,
        page_size=1000,  # Get all teaching staff
    )

    return [
        StaffListResponse(
            id=s.id,
            staff_id=s.staff_id,
            first_name=s.first_name,
            middle_name=s.middle_name,
            last_name=s.last_name,
            gender=s.gender.value,
            email=s.email,
            phone=s.phone,
            staff_type=s.staff_type.value,
            status=s.status.value,
            job_title=s.job_title,
            department=s.department,
            photo_url=s.photo_url,
        )
        for s in staff_list
    ]


@router.get(
    "/stats",
    response_model=StaffStatsResponse,
    summary="Get staff statistics",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_staff_stats(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffStatsResponse:
    """Get staff statistics for the tenant."""
    service = StaffService(db)
    stats = await service.get_staff_stats(tenant.tenant_id)
    return StaffStatsResponse(**stats)


@router.get(
    "/by-section/{section_id}",
    response_model=list[StaffAssignmentResponse],
    summary="Get staff assigned to a section",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_staff_by_section(
    section_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[StaffAssignmentResponse]:
    """Get all staff assigned to a specific class section."""
    service = StaffService(db)
    assignments = await service.get_section_staff(tenant.tenant_id, section_id)

    return [
        StaffAssignmentResponse(
            id=a.id,
            staff_id=a.staff_id,
            section_id=a.section_id,
            is_class_teacher=a.is_class_teacher,
            subject_id=a.subject_id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            section_name=a.section.name if a.section else None,
            class_name=a.section.class_.name if a.section and a.section.class_ else None,
        )
        for a in assignments
    ]


# =========================
# Workload Endpoints
# CRITICAL: These must be registered BEFORE /{staff_id} routes
# to prevent FastAPI from matching "workload" as a staff_id UUID.
# =========================


@router.get(
    "/workload/summary",
    response_model=list[StaffWorkloadSummaryItem],
    summary="Get all staff workload summary",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_all_staff_workload(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(None, description="Filter by school"),
) -> list[StaffWorkloadSummaryItem]:
    """Get workload overview for all teaching staff."""
    service = StaffWorkloadService(db)
    try:
        workloads = await service.get_all_staff_workload(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
        )
        return [StaffWorkloadSummaryItem(**w) for w in workloads]
    except StaffWorkloadService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/{staff_id}/workload",
    response_model=StaffWorkloadResponse,
    summary="Get staff workload",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_staff_workload(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffWorkloadResponse:
    """Get teaching workload for a specific staff member."""
    service = StaffWorkloadService(db)
    try:
        workload = await service.get_staff_workload(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
        )
        return StaffWorkloadResponse(**workload)
    except StaffWorkloadService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/{staff_id}/sensitive-fields",
    response_model=StaffSensitiveFieldsResponse,
    summary="Get staff sensitive fields (unmasked)",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def get_staff_sensitive_fields(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffSensitiveFieldsResponse:
    """Return unmasked sensitive PII fields (TIN, SSNIT, bank details).

    Requires staff.update permission. Users with only staff.read (academic_head,
    teacher) cannot access full financial identifiers.
    """
    service = StaffService(db)
    staff = await service.get_staff(tenant.tenant_id, staff_id)

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )

    return StaffSensitiveFieldsResponse(
        id=staff.id,
        tin_number=staff.tin_number,
        ssnit_number=staff.ssnit_number,
        ghana_card_number=staff.ghana_card_number,
        bank_name=staff.bank_name,
        bank_branch=staff.bank_branch,
        account_number=staff.account_number,
    )


@router.get(
    "/{staff_id}",
    response_model=StaffWithAssignmentsResponse,
    summary="Get staff details",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_staff(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    include_assignments: bool = Query(True, description="Include class assignments"),
) -> StaffWithAssignmentsResponse:
    """Get staff by ID with optional class assignments."""
    service = StaffService(db)
    staff = await service.get_staff(tenant.tenant_id, staff_id, include_assignments=include_assignments)

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )

    assignments = []
    if include_assignments:
        for assignment in staff.class_assignments:
            section = assignment.section
            assignments.append(
                StaffAssignmentResponse(
                    id=assignment.id,
                    staff_id=assignment.staff_id,
                    section_id=assignment.section_id,
                    is_class_teacher=assignment.is_class_teacher,
                    subject_id=assignment.subject_id,
                    created_at=assignment.created_at,
                    updated_at=assignment.updated_at,
                    section_name=section.name if section else None,
                    class_name=section.class_.name if section and section.class_ else None,
                )
            )

    # Build base response then add assignments
    base = _build_staff_response(staff)
    return StaffWithAssignmentsResponse(
        **base.model_dump(),
        assignments=assignments,
    )


@router.put(
    "/{staff_id}",
    response_model=StaffResponse,
    summary="Update staff",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def update_staff(
    staff_id: UUID,
    data: StaffUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffResponse:
    """Update a staff member."""
    service = StaffService(db)
    try:
        staff = await service.update_staff(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            current_user_id=UUID(current_user["user_id"]),
            **data.model_dump(exclude_unset=True),
        )

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found",
            )

        return _build_staff_response(staff)
    except StaffServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/{staff_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete staff",
    dependencies=[Depends(require_permissions("staff.delete"))],
)
async def delete_staff(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Soft delete a staff member."""
    service = StaffService(db)
    deleted = await service.delete_staff(tenant.tenant_id, staff_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )


# =========================
# Staff Assignment Endpoints
# =========================


@router.post(
    "/{staff_id}/assignments",
    response_model=StaffAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign staff to section",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def assign_staff_to_section(
    staff_id: UUID,
    data: StaffAssignmentCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffAssignmentResponse:
    """Assign a staff member to a class section."""
    service = StaffService(db)
    try:
        assignment = await service.assign_staff_to_section(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            section_id=data.section_id,
            is_class_teacher=data.is_class_teacher,
            subject_id=data.subject_id,
        )

        return StaffAssignmentResponse(
            id=assignment.id,
            staff_id=assignment.staff_id,
            section_id=assignment.section_id,
            is_class_teacher=assignment.is_class_teacher,
            subject_id=assignment.subject_id,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
            section_name=assignment.section.name if assignment.section else None,
            class_name=assignment.section.class_.name if assignment.section and assignment.section.class_ else None,
        )
    except StaffServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{staff_id}/assignments",
    response_model=list[StaffAssignmentResponse],
    summary="Get staff assignments",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_staff_assignments(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[StaffAssignmentResponse]:
    """Get all class assignments for a staff member."""
    service = StaffService(db)
    assignments = await service.get_staff_assignments(tenant.tenant_id, staff_id)

    return [
        StaffAssignmentResponse(
            id=a.id,
            staff_id=a.staff_id,
            section_id=a.section_id,
            is_class_teacher=a.is_class_teacher,
            subject_id=a.subject_id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            section_name=a.section.name if a.section else None,
            class_name=a.section.class_.name if a.section and a.section.class_ else None,
        )
        for a in assignments
    ]


@router.put(
    "/{staff_id}/assignments/{assignment_id}",
    response_model=StaffAssignmentResponse,
    summary="Update staff assignment",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def update_staff_assignment(
    staff_id: UUID,
    assignment_id: UUID,
    data: StaffAssignmentUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffAssignmentResponse:
    """Update a staff class assignment."""
    service = StaffService(db)
    assignment = await service.update_staff_assignment(
        assignment_id=assignment_id,
        tenant_id=tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    return StaffAssignmentResponse(
        id=assignment.id,
        staff_id=assignment.staff_id,
        section_id=assignment.section_id,
        is_class_teacher=assignment.is_class_teacher,
        subject_id=assignment.subject_id,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        section_name=assignment.section.name if assignment.section else None,
        class_name=assignment.section.class_.name if assignment.section and assignment.section.class_ else None,
    )


@router.delete(
    "/{staff_id}/assignments/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove staff from section",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def remove_staff_from_section(
    staff_id: UUID,
    section_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Remove a staff member from a class section."""
    service = StaffService(db)
    removed = await service.remove_staff_from_section(tenant.tenant_id, staff_id, section_id)

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
