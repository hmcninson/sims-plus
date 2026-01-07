"""
SIMS Plus - Attendance Schemas

Pydantic schemas for attendance management endpoints.
"""

from datetime import date, time, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Student Attendance Schemas
# =========================


class StudentAttendanceMark(BaseSchema):
    """Mark single student attendance request."""

    student_id: UUID
    section_id: UUID
    date: date
    status: str = Field(default="present", pattern="^(present|absent|late|excused|sick)$")
    term_id: Optional[UUID] = None
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    remarks: Optional[str] = Field(None, max_length=500)
    excuse_reason: Optional[str] = Field(None, max_length=255)


class StudentAttendanceRecord(BaseSchema):
    """Individual student record for bulk marking."""

    student_id: UUID
    status: str = Field(default="present", pattern="^(present|absent|late|excused|sick)$")
    check_in_time: Optional[time] = None
    remarks: Optional[str] = Field(None, max_length=500)
    excuse_reason: Optional[str] = Field(None, max_length=255)


class BulkStudentAttendanceMark(BaseSchema):
    """Bulk mark student attendance request."""

    section_id: UUID
    date: date
    term_id: Optional[UUID] = None
    records: list[StudentAttendanceRecord]


class StudentAttendanceResponse(BaseSchema):
    """Student attendance response."""

    id: UUID
    student_id: UUID
    section_id: UUID
    date: date
    status: str
    term_id: Optional[UUID] = None
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    remarks: Optional[str] = None
    excuse_reason: Optional[str] = None
    marked_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Extended fields from relationships
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    section_name: Optional[str] = None


class StudentAttendanceListItem(BaseSchema):
    """Student with attendance status for marking."""

    student_id: UUID
    student_number: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    gender: str
    photo_url: Optional[str] = None
    attendance_id: Optional[UUID] = None
    status: Optional[str] = None
    check_in_time: Optional[time] = None
    remarks: Optional[str] = None


class StudentAttendanceSummary(BaseSchema):
    """Student attendance summary statistics."""

    total_days: int
    present: int
    absent: int
    late: int
    excused: int
    sick: int
    attendance_rate: float


class SectionAttendanceSummary(BaseSchema):
    """Section attendance summary for a date."""

    date: str
    total_students: int
    marked: int
    unmarked: int
    present: int
    absent: int
    late: int
    excused: int
    sick: int
    attendance_rate: float


class DailyAttendanceReport(BaseSchema):
    """School-wide daily attendance report."""

    date: str
    total_students: int
    marked: int
    unmarked: int
    present: int
    absent: int
    late: int
    excused: int
    sick: int
    attendance_rate: float
    marking_rate: float


class BulkAttendanceResult(BaseSchema):
    """Result of bulk attendance marking."""

    created: int
    updated: int
    failed: int
    errors: list[dict] = []


# =========================
# Staff Attendance Schemas
# =========================


class StaffAttendanceMark(BaseSchema):
    """Mark single staff attendance request."""

    staff_id: UUID
    date: date
    status: str = Field(default="present", pattern="^(present|absent|late|excused|sick)$")
    term_id: Optional[UUID] = None
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    remarks: Optional[str] = Field(None, max_length=500)
    excuse_reason: Optional[str] = Field(None, max_length=255)


class StaffAttendanceRecord(BaseSchema):
    """Individual staff record for bulk marking."""

    staff_id: UUID
    status: str = Field(default="present", pattern="^(present|absent|late|excused|sick)$")
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    remarks: Optional[str] = Field(None, max_length=500)
    excuse_reason: Optional[str] = Field(None, max_length=255)


class BulkStaffAttendanceMark(BaseSchema):
    """Bulk mark staff attendance request."""

    date: date
    term_id: Optional[UUID] = None
    records: list[StaffAttendanceRecord]


class StaffAttendanceResponse(BaseSchema):
    """Staff attendance response."""

    id: UUID
    staff_id: UUID
    date: date
    status: str
    term_id: Optional[UUID] = None
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    remarks: Optional[str] = None
    excuse_reason: Optional[str] = None
    marked_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Extended fields from relationships
    staff_name: Optional[str] = None
    staff_number: Optional[str] = None


class StaffAttendanceSummary(BaseSchema):
    """Staff attendance summary statistics."""

    total_days: int
    present: int
    absent: int
    late: int
    excused: int
    sick: int
    attendance_rate: float
