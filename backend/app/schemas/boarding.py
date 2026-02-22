"""
SIMS Plus - Boarding Schemas

Pydantic schemas for boarding house management endpoints.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# House Schemas
# =========================


class HouseCreate(BaseSchema):
    """Create house request."""

    name: str = Field(..., min_length=1, max_length=100)
    house_code: str = Field(..., min_length=1, max_length=20)
    gender: str = Field(..., pattern="^(male|female|mixed)$")
    capacity: int = Field(..., gt=0)
    house_parent_id: Optional[UUID] = None
    description: Optional[str] = None
    is_active: bool = True


class HouseUpdate(BaseSchema):
    """Update house request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    house_code: Optional[str] = Field(None, min_length=1, max_length=20)
    gender: Optional[str] = Field(None, pattern="^(male|female|mixed)$")
    capacity: Optional[int] = Field(None, gt=0)
    house_parent_id: Optional[UUID] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class HouseResponse(BaseSchema):
    """House response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    name: str
    house_code: str
    gender: str
    capacity: int
    house_parent_id: Optional[UUID] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HouseListResponse(BaseSchema):
    """Paginated house list."""

    items: list[HouseResponse]
    total: int
    page: int
    page_size: int
    pages: int


class HouseDetailResponse(HouseResponse):
    """House with nested dormitory and occupancy information."""

    house_parent_name: Optional[str] = None
    dormitory_count: int = 0
    current_occupancy: int = 0


# =========================
# Dormitory Schemas
# =========================


class DormitoryCreate(BaseSchema):
    """Create dormitory request."""

    house_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    floor: Optional[str] = Field(None, max_length=20)
    capacity: int = Field(..., gt=0)
    dormitory_type: str = Field(..., pattern="^(room|hall|cubicle)$")
    is_active: bool = True


class DormitoryUpdate(BaseSchema):
    """Update dormitory request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    floor: Optional[str] = Field(None, max_length=20)
    capacity: Optional[int] = Field(None, gt=0)
    dormitory_type: Optional[str] = Field(None, pattern="^(room|hall|cubicle)$")
    is_active: Optional[bool] = None


class DormitoryResponse(BaseSchema):
    """Dormitory response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    house_id: UUID
    name: str
    floor: Optional[str] = None
    capacity: int
    dormitory_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DormitoryDetailResponse(DormitoryResponse):
    """Dormitory with bed and occupancy info."""

    house_name: Optional[str] = None
    bed_count: int = 0
    occupied_beds: int = 0
    available_beds: int = 0


# =========================
# Bed Schemas
# =========================


class BedCreate(BaseSchema):
    """Create bed request."""

    dormitory_id: UUID
    bed_number: str = Field(..., min_length=1, max_length=20)
    bed_type: str = Field(..., pattern="^(single|bunk_upper|bunk_lower)$")
    status: str = Field(default="available", pattern="^(available|occupied|maintenance)$")
    is_active: bool = True


class BedUpdate(BaseSchema):
    """Update bed request."""

    bed_number: Optional[str] = Field(None, min_length=1, max_length=20)
    bed_type: Optional[str] = Field(None, pattern="^(single|bunk_upper|bunk_lower)$")
    status: Optional[str] = Field(None, pattern="^(available|occupied|maintenance)$")
    is_active: Optional[bool] = None


class BedResponse(BaseSchema):
    """Bed response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    dormitory_id: UUID
    bed_number: str
    bed_type: str
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BedDetailResponse(BedResponse):
    """Bed with current occupant info."""

    dormitory_name: Optional[str] = None
    house_name: Optional[str] = None
    occupant_name: Optional[str] = None
    occupant_id: Optional[UUID] = None


class BedBulkCreate(BaseSchema):
    """Bulk create beds for a dormitory."""

    dormitory_id: UUID
    bed_type: str = Field(..., pattern="^(single|bunk_upper|bunk_lower)$")
    count: int = Field(..., gt=0, le=100)
    prefix: str = Field(default="B", max_length=10, description="Prefix for bed numbers, e.g., B for B-001")


# =========================
# Student Boarding Schemas
# =========================


class StudentBoardingCreate(BaseSchema):
    """Assign student to boarding."""

    student_id: UUID
    house_id: UUID
    dormitory_id: Optional[UUID] = None
    bed_id: Optional[UUID] = None
    academic_year_id: UUID
    boarding_status: str = Field(
        default="active",
        pattern="^(active|withdrawn|suspended|graduated)$",
    )
    check_in_date: date

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: date) -> date:
        """Check-in date cannot be far in the future."""
        return v


class StudentBoardingUpdate(BaseSchema):
    """Update student boarding assignment."""

    house_id: Optional[UUID] = None
    dormitory_id: Optional[UUID] = None
    bed_id: Optional[UUID] = None
    boarding_status: Optional[str] = Field(
        None,
        pattern="^(active|withdrawn|suspended|graduated)$",
    )
    check_out_date: Optional[date] = None


class StudentBoardingResponse(BaseSchema):
    """Student boarding response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    student_id: UUID
    house_id: UUID
    dormitory_id: Optional[UUID] = None
    bed_id: Optional[UUID] = None
    academic_year_id: UUID
    boarding_status: str
    check_in_date: date
    check_out_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class StudentBoardingDetailResponse(StudentBoardingResponse):
    """Student boarding with nested info."""

    student_name: Optional[str] = None
    house_name: Optional[str] = None
    dormitory_name: Optional[str] = None
    bed_number: Optional[str] = None
    academic_year_name: Optional[str] = None


class StudentBoardingBulkAssign(BaseSchema):
    """Bulk assign students to a boarding house."""

    student_ids: list[UUID] = Field(..., min_length=1)
    house_id: UUID
    academic_year_id: UUID
    check_in_date: date


# =========================
# Roll Call Schemas
# =========================


class BoardingRollCallCreate(BaseSchema):
    """Create a roll call for a house."""

    house_id: UUID
    date: date
    roll_call_type: str = Field(..., pattern="^(morning|evening|lights_out|emergency)$")
    notes: Optional[str] = None


class RollCallEntryCreate(BaseSchema):
    """Create a single roll call entry."""

    student_id: UUID
    status: str = Field(..., pattern="^(present|absent|sick_bay|exeat|awol)$")
    notes: Optional[str] = Field(None, max_length=200)


class BoardingRollCallSubmit(BaseSchema):
    """Submit a complete roll call with all entries."""

    house_id: UUID
    date: date
    roll_call_type: str = Field(..., pattern="^(morning|evening|lights_out|emergency)$")
    notes: Optional[str] = None
    entries: list[RollCallEntryCreate] = Field(..., min_length=1)


class RollCallEntryResponse(BaseSchema):
    """Roll call entry response."""

    id: UUID
    roll_call_id: UUID
    student_id: UUID
    status: str
    notes: Optional[str] = None
    student_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BoardingRollCallResponse(BaseSchema):
    """Roll call response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    house_id: UUID
    date: date
    roll_call_type: str
    conducted_by_id: UUID
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BoardingRollCallDetailResponse(BoardingRollCallResponse):
    """Roll call with entries."""

    house_name: Optional[str] = None
    conducted_by_name: Optional[str] = None
    entries: list[RollCallEntryResponse] = []
    present_count: int = 0
    absent_count: int = 0
    total_count: int = 0


# =========================
# Exeat Schemas
# =========================


class ExeatCreate(BaseSchema):
    """Create exeat request."""

    student_id: UUID
    exeat_type: str = Field(..., pattern="^(weekend|medical|emergency|funeral|other)$")
    reason: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    guardian_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: date, info) -> date:
        """End date must be on or after start date."""
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("End date must be on or after start date")
        return v


class ExeatUpdate(BaseSchema):
    """Update exeat request."""

    exeat_type: Optional[str] = Field(None, pattern="^(weekend|medical|emergency|funeral|other)$")
    reason: Optional[str] = Field(None, min_length=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    guardian_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None


class ExeatApprovalUpdate(BaseSchema):
    """Approve or deny exeat."""

    status: str = Field(..., pattern="^(approved|denied)$")
    notes: Optional[str] = None


class ExeatReturnUpdate(BaseSchema):
    """Mark exeat as returned."""

    actual_return_date: date
    notes: Optional[str] = None


class ExeatResponse(BaseSchema):
    """Exeat response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    student_id: UUID
    requested_by_id: UUID
    approved_by_id: Optional[UUID] = None
    exeat_type: str
    reason: str
    start_date: date
    end_date: date
    actual_return_date: Optional[date] = None
    status: str
    guardian_notified: bool
    guardian_phone: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExeatDetailResponse(ExeatResponse):
    """Exeat with names."""

    student_name: Optional[str] = None
    requested_by_name: Optional[str] = None
    approved_by_name: Optional[str] = None


class ExeatListResponse(BaseSchema):
    """Paginated exeat list."""

    items: list[ExeatDetailResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Boarding Incident Schemas
# =========================


class BoardingIncidentCreate(BaseSchema):
    """Create boarding incident report."""

    student_id: UUID
    incident_type: str = Field(
        ...,
        pattern="^(disciplinary|health|property_damage|missing_student|bullying|theft|other)$",
    )
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    description: str = Field(..., min_length=1)
    action_taken: Optional[str] = None


class BoardingIncidentUpdate(BaseSchema):
    """Update boarding incident report."""

    incident_type: Optional[str] = Field(
        None,
        pattern="^(disciplinary|health|property_damage|missing_student|bullying|theft|other)$",
    )
    severity: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    description: Optional[str] = Field(None, min_length=1)
    action_taken: Optional[str] = None
    parent_notified: Optional[bool] = None


class BoardingIncidentResolve(BaseSchema):
    """Resolve a boarding incident."""

    action_taken: str = Field(..., min_length=1)
    parent_notified: bool = False


class BoardingIncidentResponse(BaseSchema):
    """Boarding incident response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    student_id: UUID
    reported_by_id: UUID
    incident_type: str
    severity: str
    description: str
    action_taken: Optional[str] = None
    resolved: bool
    resolved_by_id: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    parent_notified: bool
    created_at: datetime
    updated_at: datetime


class BoardingIncidentDetailResponse(BoardingIncidentResponse):
    """Incident with names."""

    student_name: Optional[str] = None
    reported_by_name: Optional[str] = None
    resolved_by_name: Optional[str] = None


class BoardingIncidentListResponse(BaseSchema):
    """Paginated incident list."""

    items: list[BoardingIncidentDetailResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Dining Meal Schemas
# =========================


class DiningMealCreate(BaseSchema):
    """Create dining meal record."""

    date: date
    meal_type: str = Field(..., pattern="^(breakfast|lunch|dinner|snack)$")
    menu_description: Optional[str] = None
    head_count: Optional[int] = Field(None, ge=0)
    prepared_by: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class DiningMealUpdate(BaseSchema):
    """Update dining meal record."""

    meal_type: Optional[str] = Field(None, pattern="^(breakfast|lunch|dinner|snack)$")
    menu_description: Optional[str] = None
    head_count: Optional[int] = Field(None, ge=0)
    prepared_by: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class DiningMealResponse(BaseSchema):
    """Dining meal response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    date: date
    meal_type: str
    menu_description: Optional[str] = None
    head_count: Optional[int] = None
    prepared_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DiningMealListResponse(BaseSchema):
    """Paginated dining meal list."""

    items: list[DiningMealResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Boarding Stats Schemas
# =========================


class BoardingStatsResponse(BaseSchema):
    """Boarding house statistics."""

    total_houses: int = 0
    total_dormitories: int = 0
    total_beds: int = 0
    available_beds: int = 0
    occupied_beds: int = 0
    total_boarders: int = 0
    active_exeats: int = 0
    pending_exeats: int = 0
    unresolved_incidents: int = 0
