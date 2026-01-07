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


class ClassUpdate(BaseSchema):
    """Update class request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    short_name: Optional[str] = Field(None, max_length=20)
    level: Optional[str] = None
    sequence: Optional[int] = Field(None, ge=1)
    capacity: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class ClassResponse(BaseSchema):
    """Class response."""

    id: UUID
    name: str
    short_name: Optional[str] = None
    level: Optional[str] = None
    sequence: int
    capacity: Optional[int] = None
    school_id: Optional[UUID] = None
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

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.upper()


class SubjectUpdate(BaseSchema):
    """Update subject request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    category: Optional[str] = Field(None, pattern="^(core|elective|vocational|extra)$")
    is_active: Optional[bool] = None

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else None


class SubjectResponse(BaseSchema):
    """Subject response."""

    id: UUID
    name: str
    code: str
    description: Optional[str] = None
    category: str
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
    class_work_weight: Decimal = Field(default=Decimal("20"), ge=0, le=100)
    homework_weight: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    midterm_weight: Decimal = Field(default=Decimal("20"), ge=0, le=100)
    end_term_weight: Decimal = Field(default=Decimal("50"), ge=0, le=100)

    @field_validator("end_term_weight")
    @classmethod
    def weights_sum_to_100(cls, v: Decimal, info) -> Decimal:
        total = v
        for field in ["class_work_weight", "homework_weight", "midterm_weight"]:
            if field in info.data:
                total += info.data[field]
        if total != Decimal("100"):
            raise ValueError(f"Weights must sum to 100, got {total}")
        return v


class AssessmentWeightUpdate(BaseSchema):
    """Update assessment weight."""

    class_work_weight: Optional[Decimal] = Field(None, ge=0, le=100)
    homework_weight: Optional[Decimal] = Field(None, ge=0, le=100)
    midterm_weight: Optional[Decimal] = Field(None, ge=0, le=100)
    end_term_weight: Optional[Decimal] = Field(None, ge=0, le=100)


class AssessmentWeightResponse(BaseSchema):
    """Assessment weight response."""

    id: Optional[UUID] = None  # None when returning defaults
    academic_year_id: Optional[UUID] = None
    class_work_weight: Decimal
    homework_weight: Decimal
    midterm_weight: Decimal
    end_term_weight: Decimal
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


# Update forward references
AcademicYearWithTermsResponse.model_rebuild()
ClassWithSectionsResponse.model_rebuild()
GradingScaleWithGradesResponse.model_rebuild()
