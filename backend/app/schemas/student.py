"""
SIMS Plus - Student and Guardian Schemas

Pydantic schemas for student management endpoints.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, EmailStr


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Guardian Schemas
# =========================


class GuardianBase(BaseSchema):
    """Base guardian fields."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    occupation: Optional[str] = Field(None, max_length=200)
    workplace: Optional[str] = Field(None, max_length=200)
    work_phone: Optional[str] = Field(None, max_length=20)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class GuardianCreate(GuardianBase):
    """Create guardian request."""

    pass


class GuardianUpdate(BaseSchema):
    """Update guardian request."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    occupation: Optional[str] = Field(None, max_length=200)
    workplace: Optional[str] = Field(None, max_length=200)
    work_phone: Optional[str] = Field(None, max_length=20)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class GuardianResponse(GuardianBase):
    """Guardian response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        """Get the guardian's full name."""
        return f"{self.first_name} {self.last_name}"


class GuardianListResponse(BaseSchema):
    """Guardian with student count for listing."""

    id: UUID
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    occupation: Optional[str] = None
    student_count: int = 0


# =========================
# Student-Guardian Link Schemas
# =========================


class StudentGuardianCreate(BaseSchema):
    """Link student to guardian request."""

    guardian_id: UUID
    relationship: str = Field(
        ...,
        pattern="^(father|mother|guardian|grandfather|grandmother|uncle|aunt|sibling|other)$",
        description="Relationship to student",
    )
    is_primary: bool = False
    is_emergency_contact: bool = True
    can_pickup: bool = True


class StudentGuardianWithNewGuardian(BaseSchema):
    """Create new guardian and link to student."""

    guardian: GuardianCreate
    relationship: str = Field(
        ...,
        pattern="^(father|mother|guardian|grandfather|grandmother|uncle|aunt|sibling|other)$",
    )
    is_primary: bool = False
    is_emergency_contact: bool = True
    can_pickup: bool = True


class StudentGuardianUpdate(BaseSchema):
    """Update student-guardian link."""

    relationship: Optional[str] = Field(
        None,
        pattern="^(father|mother|guardian|grandfather|grandmother|uncle|aunt|sibling|other)$",
    )
    is_primary: Optional[bool] = None
    is_emergency_contact: Optional[bool] = None
    can_pickup: Optional[bool] = None


class StudentGuardianResponse(BaseSchema):
    """Student-guardian link response."""

    id: UUID
    student_id: UUID
    guardian_id: UUID
    relationship: str
    is_primary: bool
    is_emergency_contact: bool
    can_pickup: bool
    guardian: GuardianResponse
    created_at: datetime
    updated_at: datetime


# =========================
# Student Schemas
# =========================


class StudentBase(BaseSchema):
    """Base student fields."""

    student_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="System-generated unique student ID (e.g., STU-2026-001)",
    )
    previous_student_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Student ID from previous/external system (for migration reference)",
    )
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern="^(male|female)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    nhis_number: Optional[str] = Field(None, max_length=50)
    school_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    admission_date: Optional[date] = None
    admission_number: Optional[str] = Field(None, max_length=50)
    status: str = Field(
        default="active",
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    is_boarder: bool = False
    blood_group: Optional[str] = Field(None, max_length=10)
    medical_conditions: Optional[str] = None
    allergies: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date) -> date:
        """Ensure date of birth is not in the future."""
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class StudentCreate(BaseSchema):
    """Create student request.

    Note: student_id is always auto-generated by the system.
    Use previous_student_id to store IDs from external/previous systems.
    """

    # previous_student_id for migration from other systems
    previous_student_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Student ID from previous/external system (for migration reference)",
    )
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern="^(male|female)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    nhis_number: Optional[str] = Field(None, max_length=50)
    school_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    admission_date: Optional[date] = None
    admission_number: Optional[str] = Field(None, max_length=50)
    status: str = Field(
        default="active",
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    is_boarder: bool = False
    blood_group: Optional[str] = Field(None, max_length=10)
    medical_conditions: Optional[str] = None
    allergies: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    # Optional: create guardians at the same time
    guardians: Optional[list[StudentGuardianWithNewGuardian]] = Field(
        default=None,
        description="Guardians to create and link to student",
    )

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date) -> date:
        """Ensure date of birth is not in the future."""
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class StudentUpdate(BaseSchema):
    """Update student request.

    Note: student_id cannot be changed as it's system-generated.
    """

    # previous_student_id can be updated
    previous_student_id: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    nhis_number: Optional[str] = Field(None, max_length=50)
    school_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    admission_date: Optional[date] = None
    admission_number: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(
        None,
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    is_boarder: Optional[bool] = None
    blood_group: Optional[str] = Field(None, max_length=10)
    medical_conditions: Optional[str] = None
    allergies: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class StudentResponse(StudentBase):
    """Student response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        """Calculate the student's age."""
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class StudentWithGuardiansResponse(StudentResponse):
    """Student with guardians."""

    guardians: list[StudentGuardianResponse] = []
    school_name: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None


class StudentListResponse(BaseSchema):
    """Simplified student response for listing."""

    id: UUID
    student_id: str
    previous_student_id: Optional[str] = None
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    gender: str
    date_of_birth: date
    status: str
    class_id: Optional[UUID] = None
    class_name: Optional[str] = None
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    photo_url: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"


class StudentBulkCreate(BaseSchema):
    """Bulk create students request."""

    students: list[StudentCreate] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of students to create (max 100)",
    )


class StudentBulkResponse(BaseSchema):
    """Bulk create response."""

    created: int
    failed: int
    errors: list[dict] = []


class StudentImportResponse(BaseSchema):
    """File import response."""

    total_rows: int
    created: int
    failed: int
    errors: list[dict] = []
    preview: list[dict] = Field(
        default=[],
        description="Preview of first few rows (only in preview mode)",
    )


class StudentImportColumnMapping(BaseSchema):
    """Column mapping for student import.

    Note: student_id from import file is mapped to previous_student_id.
    The system always auto-generates the actual student_id.
    """

    previous_student_id: Optional[str] = Field(
        None,
        description="Column name for previous_student_id (IDs from external system)",
    )
    first_name: Optional[str] = Field(None, description="Column name for first_name")
    middle_name: Optional[str] = Field(None, description="Column name for middle_name")
    last_name: Optional[str] = Field(None, description="Column name for last_name")
    date_of_birth: Optional[str] = Field(None, description="Column name for date_of_birth")
    gender: Optional[str] = Field(None, description="Column name for gender")
    email: Optional[str] = Field(None, description="Column name for email")
    phone: Optional[str] = Field(None, description="Column name for phone")
    address: Optional[str] = Field(None, description="Column name for address")
    city: Optional[str] = Field(None, description="Column name for city")
    region: Optional[str] = Field(None, description="Column name for region")
    class_name: Optional[str] = Field(None, description="Column name for class_name (will lookup class_id)")
    is_boarder: Optional[str] = Field(None, description="Column name for is_boarder")


class StudentStatsResponse(BaseSchema):
    """Student statistics response."""

    total: int
    active: int
    inactive: int
    graduated: int
    transferred: int
    withdrawn: int
    suspended: int
    male: int
    female: int
    boarders: int
    day_students: int


class StudentFilterParams(BaseSchema):
    """Student filter parameters."""

    search: Optional[str] = Field(None, description="Search by name or student ID")
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    school_id: Optional[UUID] = None
    status: Optional[str] = Field(
        None,
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    is_boarder: Optional[bool] = None


# Update forward references
StudentWithGuardiansResponse.model_rebuild()
StudentGuardianResponse.model_rebuild()
