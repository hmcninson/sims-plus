"""
SIMS Plus - Staff Schemas

Pydantic schemas for staff management endpoints.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Department Schemas
# =========================


class DepartmentCreate(BaseSchema):
    """Create department request."""

    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    head_id: Optional[UUID] = None


class DepartmentUpdate(BaseSchema):
    """Update department request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    head_id: Optional[UUID] = None


class DepartmentResponse(BaseSchema):
    """Department response."""

    id: UUID
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    head_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Extended fields
    head_name: Optional[str] = None
    staff_count: int = 0


class DepartmentListResponse(BaseSchema):
    """Department list item response."""

    id: UUID
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    head_name: Optional[str] = None
    staff_count: int = 0


# =========================
# Staff Schemas
# =========================


class StaffCreate(BaseSchema):
    """Create staff request."""

    # Staff ID - optional, will be auto-generated if not provided
    staff_id: Optional[str] = Field(None, max_length=50)

    # Required fields
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=1, max_length=20)
    gender: str = Field(..., pattern="^(male|female)$")
    job_title: str = Field(..., min_length=1, max_length=100)
    employment_date: date

    # Optional fields
    middle_name: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    phone_secondary: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=50)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    ssnit_number: Optional[str] = Field(None, max_length=50)
    teacher_license_number: Optional[str] = Field(None, max_length=50)
    staff_type: str = Field(default="teaching", pattern="^(teaching|non_teaching|administrative)$")
    status: str = Field(default="active", pattern="^(active|on_leave|suspended|terminated|retired)$")
    department: Optional[str] = Field(None, max_length=100)
    department_id: Optional[UUID] = None
    termination_date: Optional[date] = None
    qualifications: Optional[list] = None
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_branch: Optional[str] = Field(None, max_length=100)
    account_number: Optional[str] = Field(None, max_length=50)
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    school_id: Optional[UUID] = None
    user_id: Optional[UUID] = None

    # HR gap closure fields
    tin_number: Optional[str] = Field(None, max_length=50)
    employment_type: Optional[str] = Field(
        None,
        pattern="^(full_time|part_time|contract|temporary|intern)$",
    )
    ges_staff_id: Optional[str] = Field(None, max_length=50)
    nationality: Optional[str] = Field(None, max_length=100)
    marital_status: Optional[str] = Field(None, max_length=20)


class StaffUpdate(BaseSchema):
    """Update staff request."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=1, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=50)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    ssnit_number: Optional[str] = Field(None, max_length=50)
    teacher_license_number: Optional[str] = Field(None, max_length=50)
    staff_type: Optional[str] = Field(None, pattern="^(teaching|non_teaching|administrative)$")
    status: Optional[str] = Field(None, pattern="^(active|on_leave|suspended|terminated|retired)$")
    job_title: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    department_id: Optional[UUID] = None
    employment_date: Optional[date] = None
    termination_date: Optional[date] = None
    qualifications: Optional[list] = None
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_branch: Optional[str] = Field(None, max_length=100)
    account_number: Optional[str] = Field(None, max_length=50)
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    school_id: Optional[UUID] = None
    user_id: Optional[UUID] = None

    # HR gap closure fields
    tin_number: Optional[str] = Field(None, max_length=50)
    employment_type: Optional[str] = Field(
        None,
        pattern="^(full_time|part_time|contract|temporary|intern)$",
    )
    ges_staff_id: Optional[str] = Field(None, max_length=50)
    nationality: Optional[str] = Field(None, max_length=100)
    marital_status: Optional[str] = Field(None, max_length=20)


class StaffResponse(BaseSchema):
    """Staff response."""

    id: UUID
    staff_id: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    date_of_birth: Optional[date] = None
    gender: str
    email: str
    phone: str
    phone_secondary: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    ghana_card_number: Optional[str] = None
    ssnit_number: Optional[str] = None
    teacher_license_number: Optional[str] = None
    staff_type: str
    status: str
    job_title: str
    department: Optional[str] = None
    department_id: Optional[UUID] = None
    employment_date: date
    termination_date: Optional[date] = None
    qualifications: Optional[list] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    account_number: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    school_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # HR gap closure fields
    tin_number: Optional[str] = None
    employment_type: Optional[str] = None
    ges_staff_id: Optional[str] = None
    nationality: Optional[str] = None
    marital_status: Optional[str] = None

    # Extended fields from relationships
    school_name: Optional[str] = None
    department_name: Optional[str] = None


class StaffListResponse(BaseSchema):
    """Staff list item response (summary)."""

    id: UUID
    staff_id: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    gender: str
    email: str
    phone: str
    staff_type: str
    status: str
    job_title: str
    department: Optional[str] = None
    department_id: Optional[UUID] = None
    department_name: Optional[str] = None
    photo_url: Optional[str] = None


class StaffStatsResponse(BaseSchema):
    """Staff statistics response."""

    total: int
    active: int
    on_leave: int
    suspended: int
    terminated: int
    retired: int
    teaching: int
    non_teaching: int
    administrative: int
    male: int
    female: int


# =========================
# Staff Class Assignment Schemas
# =========================


class StaffAssignmentCreate(BaseSchema):
    """Create staff class assignment request."""

    section_id: UUID
    is_class_teacher: bool = False
    subject_id: Optional[UUID] = None


class StaffAssignmentUpdate(BaseSchema):
    """Update staff class assignment request."""

    is_class_teacher: Optional[bool] = None
    subject_id: Optional[UUID] = None


class StaffAssignmentResponse(BaseSchema):
    """Staff class assignment response."""

    id: UUID
    staff_id: UUID
    section_id: UUID
    is_class_teacher: bool
    subject_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Extended fields
    section_name: Optional[str] = None
    class_name: Optional[str] = None


class StaffWithAssignmentsResponse(StaffResponse):
    """Staff response with class assignments."""

    assignments: list[StaffAssignmentResponse] = []


# =========================
# Sensitive Fields Schema
# =========================


class StaffSensitiveFieldsResponse(BaseSchema):
    """
    Unmasked sensitive fields, returned only by the dedicated
    GET /staff/{id}/sensitive-fields endpoint (payroll.read or staff.update).
    """

    id: UUID
    tin_number: Optional[str] = None
    ssnit_number: Optional[str] = None
    ghana_card_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    account_number: Optional[str] = None


# =========================
# Staff Document Schemas
# =========================


class StaffDocumentResponse(BaseSchema):
    """Staff document response with presigned download URL."""

    id: UUID
    staff_id: UUID
    document_type: str
    file_name: str
    file_size: int
    mime_type: str
    description: Optional[str] = None
    download_url: str
    uploaded_by: Optional[UUID] = None
    created_at: datetime


# =========================
# Staff Employment History Schemas
# =========================


class StaffEmploymentHistoryCreate(BaseSchema):
    """Create a manual employment history event."""

    event_type: str = Field(..., min_length=1, max_length=50)
    effective_date: date
    previous_value: Optional[str] = Field(None, max_length=255)
    new_value: Optional[str] = Field(None, max_length=255)
    previous_department_id: Optional[UUID] = None
    new_department_id: Optional[UUID] = None
    previous_job_title: Optional[str] = Field(None, max_length=100)
    new_job_title: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


# =========================
# Workload Schemas
# =========================


class StaffWorkloadSection(BaseSchema):
    """Section detail within a staff workload response."""

    section_id: UUID
    section_name: str
    class_name: str
    subject_name: Optional[str] = None
    is_class_teacher: bool
    periods_per_week: int


class StaffWorkloadResponse(BaseSchema):
    """Full workload detail for a single staff member."""

    staff_id: UUID
    staff_name: str
    total_periods_per_week: int
    total_sections: int
    class_teacher_of: Optional[str] = None
    subjects_taught: list[str]
    sections: list[StaffWorkloadSection]


class StaffWorkloadSummaryItem(BaseSchema):
    """Workload summary for the all-staff overview."""

    staff_id: UUID
    staff_name: str
    department: Optional[str] = None
    total_sections: int
    total_periods_per_week: int
    is_class_teacher: bool
    class_teacher_of: Optional[str] = None


class StaffEmploymentHistoryResponse(BaseSchema):
    """Staff employment history event response."""

    id: UUID
    staff_id: UUID
    event_type: str
    effective_date: date
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    previous_department_id: Optional[UUID] = None
    new_department_id: Optional[UUID] = None
    previous_job_title: Optional[str] = None
    new_job_title: Optional[str] = None
    notes: Optional[str] = None
    recorded_by: Optional[UUID] = None
    created_at: datetime
