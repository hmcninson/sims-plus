"""
SIMS Plus - Academic Schemas

Pydantic schemas for academic endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
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
# Academic Year Schemas
# =========================


class AcademicYearCreate(BaseSchema):
    """Create academic year request."""

    name: str = Field(..., min_length=1, max_length=50, description="Year name, e.g., 2025/2026")
    description: Optional[str] = Field(None, max_length=255)
    start_date: date
    end_date: date
    is_current: bool = False

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: date, info) -> date:
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("End date must be after start date")
        return v


class AcademicYearUpdate(BaseSchema):
    """Update academic year request."""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(None, pattern="^(planning|active|completed)$")
    is_current: Optional[bool] = None


class AcademicYearResponse(BaseSchema):
    """Academic year response."""

    id: UUID
    name: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    status: str
    is_current: bool
    created_at: datetime
    updated_at: datetime


class AcademicYearWithTermsResponse(AcademicYearResponse):
    """Academic year with terms."""

    terms: list["TermResponse"] = []


# =========================
# Term Schemas
# =========================


class TermCreate(BaseSchema):
    """Create term request."""

    academic_year_id: UUID
    name: str = Field(..., min_length=1, max_length=50, description="Term name, e.g., First Term")
    short_name: Optional[str] = Field(None, max_length=20)
    sequence: int = Field(default=1, ge=1, le=4)
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: date, info) -> date:
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("End date must be after start date")
        return v


class TermUpdate(BaseSchema):
    """Update term request."""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    short_name: Optional[str] = Field(None, max_length=20)
    sequence: Optional[int] = Field(None, ge=1, le=4)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(None, pattern="^(upcoming|active|completed)$")
    is_current: Optional[bool] = None


class TermResponse(BaseSchema):
    """Term response."""

    id: UUID
    academic_year_id: UUID
    name: str
    short_name: Optional[str] = None
    sequence: int
    start_date: date
    end_date: date
    status: str
    is_current: bool
    created_at: datetime
    updated_at: datetime


# =========================
# Class Schemas
# =========================


class ClassCreate(BaseSchema):
    """Create class request."""

    name: str = Field(..., min_length=1, max_length=100, description="Class name, e.g., JHS 1")
    short_name: Optional[str] = Field(None, max_length=20)
    level: Optional[str] = None
    sequence: int = Field(default=1, ge=1)
    capacity: Optional[int] = Field(None, ge=1)
    school_id: Optional[UUID] = None
    curriculum_profile_id: Optional[UUID] = None


class ClassUpdate(BaseSchema):
    """Update class request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    short_name: Optional[str] = Field(None, max_length=20)
    level: Optional[str] = None
    sequence: Optional[int] = Field(None, ge=1)
    capacity: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    curriculum_profile_id: Optional[UUID] = None


class ClassResponse(BaseSchema):
    """Class response."""

    id: UUID
    name: str
    short_name: Optional[str] = None
    level: Optional[str] = None
    sequence: int
    capacity: Optional[int] = None
    school_id: Optional[UUID] = None
    curriculum_profile_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    student_count: int = 0
    male_count: int = 0
    female_count: int = 0


class ClassWithSectionsResponse(ClassResponse):
    """Class with sections."""

    sections: list["ClassSectionResponse"] = []


# =========================
# Class Section Schemas
# =========================


class ClassSectionCreate(BaseSchema):
    """Create class section request."""

    class_id: UUID
    name: str = Field(..., min_length=1, max_length=50, description="Section name, e.g., A, B")
    capacity: Optional[int] = Field(None, ge=1)
    class_teacher_id: Optional[UUID] = None


class ClassSectionUpdate(BaseSchema):
    """Update class section request."""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    capacity: Optional[int] = Field(None, ge=1)
    class_teacher_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class ClassSectionResponse(BaseSchema):
    """Class section response."""

    id: UUID
    class_id: UUID
    name: str
    capacity: Optional[int] = None
    class_teacher_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    student_count: int = 0
    male_count: int = 0
    female_count: int = 0


# =========================
# Subject Schemas
# =========================


class SubjectCreate(BaseSchema):
    """Create subject request."""

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20, description="Subject code, e.g., MATH")
    description: Optional[str] = None
    category: str = Field(default="core", pattern="^(core|elective|vocational|extra)$")
    applicable_levels: Optional[list[str]] = Field(
        None,
        description="List of class levels this subject applies to (null = all levels). Valid values: preschool, primary, jhs, shs",
    )

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.upper()

    @field_validator("applicable_levels")
    @classmethod
    def validate_levels(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        valid_levels = {"preschool", "primary", "jhs", "shs"}
        for level in v:
            if level not in valid_levels:
                raise ValueError(f"Invalid level: {level}. Must be one of: {valid_levels}")
        return v


class SubjectUpdate(BaseSchema):
    """Update subject request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    category: Optional[str] = Field(None, pattern="^(core|elective|vocational|extra)$")
    applicable_levels: Optional[list[str]] = Field(
        None,
        description="List of class levels this subject applies to (null = all levels)",
    )
    is_active: Optional[bool] = None

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else None

    @field_validator("applicable_levels")
    @classmethod
    def validate_levels(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        valid_levels = {"preschool", "primary", "jhs", "shs"}
        for level in v:
            if level not in valid_levels:
                raise ValueError(f"Invalid level: {level}. Must be one of: {valid_levels}")
        return v


class SubjectResponse(BaseSchema):
    """Subject response."""

    id: UUID
    name: str
    code: str
    description: Optional[str] = None
    category: str
    applicable_levels: Optional[list[str]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =========================
# Class Subject (Assignment) Schemas
# =========================


class ClassSubjectCreate(BaseSchema):
    """Assign subject to class."""

    class_id: UUID
    subject_id: UUID
    periods_per_week: Optional[int] = Field(None, ge=1, le=20)
    is_compulsory: bool = True


class ClassSubjectUpdate(BaseSchema):
    """Update class subject assignment."""

    periods_per_week: Optional[int] = Field(None, ge=1, le=20)
    is_compulsory: Optional[bool] = None


class ClassSubjectResponse(BaseSchema):
    """Class subject response."""

    id: UUID
    class_id: UUID
    subject_id: UUID
    periods_per_week: Optional[int] = None
    is_compulsory: bool
    created_at: datetime
    subject: Optional[SubjectResponse] = None


# =========================
# Grading Scale Schemas
# =========================


class GradeCreate(BaseSchema):
    """Create grade within a scale."""

    grade: str = Field(..., min_length=1, max_length=10, description="Grade symbol, e.g., A1")
    min_score: Decimal = Field(..., ge=0, le=100)
    max_score: Decimal = Field(..., ge=0, le=100)
    grade_point: Optional[Decimal] = Field(None, ge=0, le=4)
    remark: Optional[str] = Field(None, max_length=50)

    @field_validator("max_score")
    @classmethod
    def max_score_gte_min(cls, v: Decimal, info) -> Decimal:
        if "min_score" in info.data and v < info.data["min_score"]:
            raise ValueError("Max score must be >= min score")
        return v


class GradeUpdate(BaseSchema):
    """Update grade."""

    grade: Optional[str] = Field(None, min_length=1, max_length=10)
    min_score: Optional[Decimal] = Field(None, ge=0, le=100)
    max_score: Optional[Decimal] = Field(None, ge=0, le=100)
    grade_point: Optional[Decimal] = Field(None, ge=0, le=4)
    remark: Optional[str] = Field(None, max_length=50)


class GradeResponse(BaseSchema):
    """Grade response."""

    id: UUID
    grading_scale_id: UUID
    grade: str
    min_score: Decimal
    max_score: Decimal
    grade_point: Optional[Decimal] = None
    remark: Optional[str] = None


class GradingScaleCreate(BaseSchema):
    """Create grading scale request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    scale_type: str = Field(default="waec", pattern="^(waec|gpa|percentage|custom)$")
    is_default: bool = False
    grades: list[GradeCreate] = Field(default_factory=list)


class GradingScaleUpdate(BaseSchema):
    """Update grading scale request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    scale_type: Optional[str] = Field(None, pattern="^(waec|gpa|percentage|custom)$")
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class GradingScaleResponse(BaseSchema):
    """Grading scale response."""

    id: UUID
    name: str
    description: Optional[str] = None
    scale_type: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GradingScaleWithGradesResponse(GradingScaleResponse):
    """Grading scale with grades."""

    grades: list[GradeResponse] = []


# =========================
# Assessment Weight Schemas
# =========================


class AssessmentWeightCreate(BaseSchema):
    """Create assessment weight."""

    academic_year_id: Optional[UUID] = None
    # Individual component weights (for detailed breakdown)
    class_work_weight: Decimal = Field(default=Decimal("20"), ge=0, le=100)
    homework_weight: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    midterm_weight: Decimal = Field(default=Decimal("20"), ge=0, le=100)
    end_term_weight: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    # Report card weights (CA vs Exams split for Ghana's system)
    ca_total_weight: Decimal = Field(default=Decimal("50"), ge=0, le=100, description="Total weight for all CA components on report card")
    exam_total_weight: Decimal = Field(default=Decimal("50"), ge=0, le=100, description="Total weight for End of Term Exam on report card")

    @field_validator("end_term_weight")
    @classmethod
    def weights_sum_to_100(cls, v: Decimal, info) -> Decimal:
        total = v
        for field in ["class_work_weight", "homework_weight", "midterm_weight"]:
            if field in info.data:
                total += info.data[field]
        if total != Decimal("100"):
            raise ValueError(f"Individual weights must sum to 100, got {total}")
        return v

    @field_validator("exam_total_weight")
    @classmethod
    def report_card_weights_sum_to_100(cls, v: Decimal, info) -> Decimal:
        ca_weight = info.data.get("ca_total_weight", Decimal("50"))
        total = v + ca_weight
        if total != Decimal("100"):
            raise ValueError(f"Report card weights (CA + Exam) must sum to 100, got {total}")
        return v


class AssessmentWeightUpdate(BaseSchema):
    """Update assessment weight."""

    class_work_weight: Optional[Decimal] = Field(None, ge=0, le=100)
    homework_weight: Optional[Decimal] = Field(None, ge=0, le=100)
    midterm_weight: Optional[Decimal] = Field(None, ge=0, le=100)
    end_term_weight: Optional[Decimal] = Field(None, ge=0, le=100)
    ca_total_weight: Optional[Decimal] = Field(None, ge=0, le=100, description="Total weight for all CA components on report card")
    exam_total_weight: Optional[Decimal] = Field(None, ge=0, le=100, description="Total weight for End of Term Exam on report card")


class AssessmentWeightResponse(BaseSchema):
    """Assessment weight response."""

    id: Optional[UUID] = None  # None when returning defaults
    academic_year_id: Optional[UUID] = None
    class_work_weight: Decimal
    homework_weight: Decimal
    midterm_weight: Decimal
    end_term_weight: Decimal
    ca_total_weight: Decimal = Decimal("50")
    exam_total_weight: Decimal = Decimal("50")
    created_at: Optional[datetime] = None  # None when returning defaults
    updated_at: Optional[datetime] = None  # None when returning defaults


# =========================
# Academic Settings Schemas
# =========================


class AcademicSettingsUpdate(BaseSchema):
    """Update academic settings."""

    auto_promote_students: Optional[bool] = None
    allow_grade_amendments: Optional[bool] = None
    show_position_on_report_cards: Optional[bool] = None
    require_attendance_for_exams: Optional[bool] = None
    enable_continuous_assessment: Optional[bool] = None


class AcademicSettingsResponse(BaseSchema):
    """Academic settings response."""

    id: Optional[UUID] = None  # None when returning defaults
    auto_promote_students: bool = False
    allow_grade_amendments: bool = True
    show_position_on_report_cards: bool = True
    require_attendance_for_exams: bool = False
    enable_continuous_assessment: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =========================
# Class Timetable Schemas
# =========================


class TimetableEntryCreate(BaseSchema):
    """Create a timetable entry."""

    class_id: UUID
    section_id: Optional[UUID] = None
    academic_year_id: UUID
    term_id: Optional[UUID] = Field(None, description="Optional: if set, timetable applies only to this term")
    subject_id: Optional[UUID] = None
    teacher_id: Optional[UUID] = None
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    period_number: int = Field(..., ge=1, le=20, description="Period number within the day")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start time in HH:MM format")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="End time in HH:MM format")
    room: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

    @field_validator("end_time")
    @classmethod
    def end_time_after_start(cls, v: str, info) -> str:
        if "start_time" in info.data:
            start = info.data["start_time"]
            if v <= start:
                raise ValueError("End time must be after start time")
        return v


class TimetableEntryUpdate(BaseSchema):
    """Update a timetable entry."""

    subject_id: Optional[UUID] = None
    teacher_id: Optional[UUID] = None
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    room: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TimetableTeacherResponse(BaseSchema):
    """Simplified teacher info for timetable."""

    id: UUID
    first_name: str
    last_name: str
    staff_id: str


class TimetableSubjectResponse(BaseSchema):
    """Simplified subject info for timetable."""

    id: UUID
    name: str
    code: str


class TimetableTermResponse(BaseSchema):
    """Simplified term info for timetable."""

    id: UUID
    name: str
    short_name: Optional[str] = None


class TimetableEntryResponse(BaseSchema):
    """Timetable entry response."""

    id: UUID
    class_id: UUID
    section_id: Optional[UUID] = None
    academic_year_id: UUID
    term_id: Optional[UUID] = None
    subject_id: Optional[UUID] = None
    teacher_id: Optional[UUID] = None
    day_of_week: int
    period_number: int
    start_time: str
    end_time: str
    room: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Related data
    subject: Optional[TimetableSubjectResponse] = None
    teacher: Optional[TimetableTeacherResponse] = None
    term: Optional[TimetableTermResponse] = None


class TimetableBulkEntry(BaseSchema):
    """Entry for bulk timetable creation/update."""

    day_of_week: int = Field(..., ge=0, le=6)
    period_number: int = Field(..., ge=1, le=20)
    subject_id: Optional[UUID] = None
    teacher_id: Optional[UUID] = None
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    room: Optional[str] = None
    notes: Optional[str] = None


class TimetableBulkCreate(BaseSchema):
    """Bulk create/update timetable for a class/section."""

    class_id: UUID
    section_id: Optional[UUID] = None
    academic_year_id: UUID
    term_id: Optional[UUID] = Field(None, description="Optional: if set, timetable applies only to this term")
    entries: list[TimetableBulkEntry]


class TimetableDayResponse(BaseSchema):
    """Timetable entries grouped by day."""

    day_of_week: int
    day_name: str
    entries: list[TimetableEntryResponse]


class TimetableWeekResponse(BaseSchema):
    """Full week timetable for a class/section."""

    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    academic_year_id: UUID
    academic_year_name: str
    term_id: Optional[UUID] = None
    term_name: Optional[str] = None
    days: list[TimetableDayResponse]
    total_periods: int


class PeriodTemplate(BaseSchema):
    """Template for a period's timing."""

    period_number: int
    start_time: str
    end_time: str
    is_break: bool = False
    label: Optional[str] = None


class TimetableTemplate(BaseSchema):
    """Template for timetable periods."""

    periods: list[PeriodTemplate]


# =========================
# School Period Schemas
# =========================


class SchoolPeriodCreate(BaseSchema):
    """Create a school period.

    Period hierarchy:
    - class_id=None, section_id=None: School-wide periods (default for all classes)
    - class_id set, section_id=None: Class-specific periods
    - class_id set, section_id set: Section-specific periods
    """

    class_id: Optional[UUID] = None  # None = school-wide
    section_id: Optional[UUID] = None  # None = class-wide or school-wide
    period_number: int = Field(..., ge=1, le=20)
    name: Optional[str] = Field(None, max_length=50)
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    is_break: bool = False

    @field_validator("end_time")
    @classmethod
    def end_time_after_start(cls, v: str, info) -> str:
        if "start_time" in info.data:
            start = info.data["start_time"]
            if v <= start:
                raise ValueError("End time must be after start time")
        return v


class SchoolPeriodUpdate(BaseSchema):
    """Update a school period."""

    name: Optional[str] = Field(None, max_length=50)
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    is_break: Optional[bool] = None
    is_active: Optional[bool] = None


class SchoolPeriodResponse(BaseSchema):
    """School period response."""

    id: UUID
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    period_number: int
    name: Optional[str] = None
    start_time: str
    end_time: str
    is_break: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SchoolPeriodBulkEntry(BaseSchema):
    """Single period entry for bulk create (without class/section)."""

    period_number: int = Field(..., ge=1, le=20)
    name: Optional[str] = Field(None, max_length=50)
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    is_break: bool = False


class SchoolPeriodBulkCreate(BaseSchema):
    """Bulk create school periods at a specific level."""

    class_id: Optional[UUID] = None  # None = school-wide
    section_id: Optional[UUID] = None  # None = class-wide or school-wide
    periods: list[SchoolPeriodBulkEntry]


# =========================
# School Holiday Schemas
# =========================


class SchoolHolidayCreate(BaseSchema):
    """Create a school holiday."""

    date: date
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    holiday_type: str = Field(default="holiday", pattern="^(holiday|exam|event|vacation)$")
    academic_year_id: Optional[UUID] = None
    is_recurring: bool = False


class SchoolHolidayUpdate(BaseSchema):
    """Update a school holiday."""

    date: Optional[date] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    holiday_type: Optional[str] = Field(None, pattern="^(holiday|exam|event|vacation)$")
    academic_year_id: Optional[UUID] = None
    is_recurring: Optional[bool] = None


class SchoolHolidayResponse(BaseSchema):
    """School holiday response."""

    id: UUID
    date: date
    name: str
    description: Optional[str] = None
    holiday_type: str
    academic_year_id: Optional[UUID] = None
    is_recurring: bool
    created_at: datetime
    updated_at: datetime


# =========================
# Subject Template Schemas
# =========================


class SubjectTemplateInitRequest(BaseSchema):
    """Request to initialize subjects from a GES curriculum template."""

    school_type: str = Field(
        ...,
        description="School type: preschool, primary, jhs, shs, basic, etc.",
    )
    programmes: list[str] | None = Field(
        None,
        description="SHS elective programme names (e.g., ['General Science', 'Business'])",
    )

    @field_validator("school_type")
    @classmethod
    def validate_school_type(cls, v: str) -> str:
        from app.data.ges_subjects import SCHOOL_TYPE_SUBJECT_MAP

        if v not in SCHOOL_TYPE_SUBJECT_MAP:
            raise ValueError(
                f"Invalid school type '{v}'. "
                f"Valid options: {list(SCHOOL_TYPE_SUBJECT_MAP.keys())}"
            )
        return v

    @field_validator("programmes")
    @classmethod
    def validate_programmes(cls, v: list[str] | None) -> list[str] | None:
        if v:
            from app.data.ges_subjects import SHS_ELECTIVE_PROGRAMMES

            for p in v:
                if p not in SHS_ELECTIVE_PROGRAMMES:
                    raise ValueError(
                        f"Unknown programme '{p}'. "
                        f"Valid options: {list(SHS_ELECTIVE_PROGRAMMES.keys())}"
                    )
        return v


class SubjectTemplateSubject(BaseSchema):
    """A single subject entry in a template response."""

    name: str
    code: str
    category: str


class SubjectTemplateListItem(BaseSchema):
    """A subject template entry with applicable levels."""

    name: str
    code: str
    category: str
    applicable_levels: list[str] = []


class SubjectTemplateInitResponse(BaseSchema):
    """Response from subject template initialization."""

    created: int
    skipped: int
    subjects: list[SubjectTemplateSubject]


# Update forward references
AcademicYearWithTermsResponse.model_rebuild()
ClassWithSectionsResponse.model_rebuild()
GradingScaleWithGradesResponse.model_rebuild()
