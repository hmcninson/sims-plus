"""
SIMS Plus - Curriculum Schemas

Pydantic v2 schemas for curriculum profile, assessment structure,
assessment component, report card config, and external exam endpoints.
"""

import json
import math
import re
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
# Config Validation Helpers
# =========================


def _validate_config_size(v: dict | None) -> dict | None:
    """Prevent oversized or deeply nested JSONB payloads."""
    if v is not None:
        serialized = json.dumps(v)
        if len(serialized) > 10240:
            raise ValueError("Config must be under 10KB")

        def _check_depth(obj, depth=0):
            if depth > 5:
                raise ValueError("Config nesting depth must not exceed 5")
            if isinstance(obj, dict):
                for val in obj.values():
                    _check_depth(val, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _check_depth(item, depth + 1)

        _check_depth(v)
    return v


# =========================
# Curriculum Profile Schemas
# =========================


class CurriculumProfileCreate(BaseSchema):
    """Create a new curriculum profile."""

    name: str = Field(..., min_length=1, max_length=100)
    curriculum_type: str = Field(
        ...,
        pattern="^(ges|cambridge|edexcel|american|ib|french|montessori|custom)$",
    )
    description: str | None = None
    grading_scale_id: UUID | None = None
    academic_calendar_type: str = Field(
        default="terms", pattern="^(terms|semesters|quarters)$"
    )
    periods_per_year: int = Field(default=3, ge=1, le=6)
    score_display_mode: str = Field(
        default="grade_and_score",
        pattern="^(percentage|grade_only|grade_and_score|level|gpa|narrative|mention)$",
    )
    show_position: bool = True
    show_class_average: bool = True
    use_gpa: bool = False
    use_credits: bool = False
    use_criterion_grading: bool = False
    config: dict | None = None
    is_default: bool = False

    @field_validator("config")
    @classmethod
    def validate_config(cls, v):
        return _validate_config_size(v)


class CurriculumProfileUpdate(BaseSchema):
    """Update an existing curriculum profile."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    curriculum_type: str | None = Field(
        default=None,
        pattern="^(ges|cambridge|edexcel|american|ib|french|montessori|custom)$",
    )
    description: str | None = None
    grading_scale_id: UUID | None = None
    academic_calendar_type: str | None = Field(
        default=None, pattern="^(terms|semesters|quarters)$"
    )
    periods_per_year: int | None = Field(default=None, ge=1, le=6)
    score_display_mode: str | None = Field(
        default=None,
        pattern="^(percentage|grade_only|grade_and_score|level|gpa|narrative|mention)$",
    )
    show_position: bool | None = None
    show_class_average: bool | None = None
    use_gpa: bool | None = None
    use_credits: bool | None = None
    use_criterion_grading: bool | None = None
    config: dict | None = None
    is_active: bool | None = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, v):
        return _validate_config_size(v)


class CurriculumProfileResponse(BaseSchema):
    """Curriculum profile response."""

    id: UUID
    name: str
    curriculum_type: str
    description: str | None = None
    grading_scale_id: UUID | None = None
    academic_calendar_type: str
    periods_per_year: int
    score_display_mode: str
    show_position: bool
    show_class_average: bool
    use_gpa: bool
    use_credits: bool
    use_criterion_grading: bool
    config: dict | None = None
    is_default: bool
    is_active: bool
    school_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CurriculumProfileDetailResponse(CurriculumProfileResponse):
    """Curriculum profile with assessment structure and report config."""

    assessment_structure: Optional["AssessmentStructureResponse"] = None
    report_config: Optional["ReportCardConfigResponse"] = None


class CurriculumProfileListResponse(BaseSchema):
    """Paginated list of curriculum profiles."""

    items: list[CurriculumProfileResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Template Schemas
# =========================


class CurriculumTemplateInfo(BaseSchema):
    """Summary info about a built-in curriculum template."""

    key: str
    name: str
    curriculum_type: str
    description: str


class CreateFromTemplateRequest(BaseSchema):
    """Request to create a profile from a built-in template."""

    name_override: str | None = Field(default=None, max_length=100)


# =========================
# Assessment Component Schemas
# =========================


class AssessmentComponentCreate(BaseSchema):
    """Create an assessment component within a structure."""

    component_type: str = Field(
        ...,
        pattern=(
            "^(continuous_assessment|exam|class_work|homework|midterm|end_term"
            "|coursework|controlled_assessment|external_exam|practical|oral"
            "|internal_assessment|external_assessment|extended_essay|tok|cas"
            "|quiz|test|project|participation|final"
            "|controle_continu|epreuve"
            "|observation|narrative|portfolio)$"
        ),
    )
    name: str = Field(..., min_length=1, max_length=100)
    weight: Decimal = Field(..., ge=0, le=100)
    max_score: Decimal | None = None
    is_external: bool = False
    sequence: int = Field(default=1, ge=1)
    maps_to_ca: bool = False
    maps_to_exam: bool = False
    config: dict | None = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, v):
        return _validate_config_size(v)


class AssessmentComponentUpdate(BaseSchema):
    """Update an assessment component."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    weight: Decimal | None = Field(default=None, ge=0, le=100)
    max_score: Decimal | None = None
    is_external: bool | None = None
    sequence: int | None = Field(default=None, ge=1)
    maps_to_ca: bool | None = None
    maps_to_exam: bool | None = None
    config: dict | None = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, v):
        return _validate_config_size(v)


class AssessmentComponentResponse(BaseSchema):
    """Assessment component response."""

    id: UUID
    component_type: str
    name: str
    weight: Decimal
    max_score: Decimal | None = None
    is_external: bool
    sequence: int
    maps_to_ca: bool
    maps_to_exam: bool
    config: dict | None = None
    created_at: datetime
    updated_at: datetime


# =========================
# Assessment Structure Schemas
# =========================


class AssessmentStructureCreate(BaseSchema):
    """Create an assessment structure, optionally with components."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    academic_year_id: UUID | None = None
    components: list[AssessmentComponentCreate] = []

    @field_validator("components")
    @classmethod
    def validate_weights_sum(cls, v):
        """Validate that component weights sum to 100 when components are provided."""
        if v:
            total = sum(c.weight for c in v)
            if total != Decimal("100"):
                raise ValueError(
                    f"Component weights must sum to 100, got {total}"
                )
        return v


class AssessmentStructureUpdate(BaseSchema):
    """Update assessment structure metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class AssessmentStructureResponse(BaseSchema):
    """Assessment structure response with components."""

    id: UUID
    curriculum_profile_id: UUID
    academic_year_id: UUID | None = None
    name: str
    description: str | None = None
    is_active: bool
    components: list[AssessmentComponentResponse] = []
    created_at: datetime
    updated_at: datetime


class ValidateStructureResponse(BaseSchema):
    """Result of structure weight validation."""

    is_valid: bool
    total_weight: Decimal
    message: str


class ReorderComponentsRequest(BaseSchema):
    """Request to reorder components within a structure."""

    component_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="Ordered list of component IDs",
    )


class AssessmentComponentSync(BaseSchema):
    """Single component in a sync request. If id is present, update; otherwise create."""

    id: UUID | None = None
    component_type: str = Field(
        ...,
        pattern=(
            "^(continuous_assessment|exam|class_work|homework|midterm|end_term"
            "|coursework|controlled_assessment|external_exam|practical|oral"
            "|internal_assessment|external_assessment|extended_essay|tok|cas"
            "|quiz|test|project|participation|final"
            "|controle_continu|epreuve"
            "|observation|narrative|portfolio)$"
        ),
    )
    name: str = Field(..., min_length=1, max_length=100)
    weight: Decimal = Field(..., ge=0, le=100)
    max_score: Decimal | None = None
    is_external: bool = False
    sequence: int = Field(default=1, ge=1)
    maps_to_ca: bool = False
    maps_to_exam: bool = False
    config: dict | None = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, v):
        return _validate_config_size(v)


class AssessmentComponentSyncRequest(BaseSchema):
    """Bulk sync request for assessment components."""

    components: list[AssessmentComponentSync] = Field(
        ...,
        min_length=1,
        description="Full list of desired components; replaces existing set",
    )

    @field_validator("components")
    @classmethod
    def validate_weights_sum(cls, v):
        """Validate that component weights sum to 100."""
        if v:
            total = sum(c.weight for c in v)
            if total != Decimal("100"):
                raise ValueError(
                    f"Component weights must sum to 100, got {total}"
                )
        return v


# =========================
# Report Card Config Schemas
# =========================


class ReportCardConfigUpdate(BaseSchema):
    """Update report card configuration."""

    template_key: str | None = None
    show_position: bool | None = None
    show_class_average: bool | None = None
    show_subject_position: bool | None = None
    show_effort_grade: bool | None = None
    show_predicted_grades: bool | None = None
    show_gpa: bool | None = None
    show_credits: bool | None = None
    show_honor_roll: bool | None = None
    show_learner_profile: bool | None = None
    show_atl_skills: bool | None = None
    custom_columns: dict | None = None
    header_text: str | None = None
    footer_text: str | None = None

    @field_validator("header_text", "footer_text")
    @classmethod
    def strip_html_tags(cls, v):
        """
        Prevent stored XSS -- strip HTML tags from free-text fields.

        These fields are rendered in Jinja2 report templates. Even with
        autoescape=True, stripping at the schema level provides defense-in-depth.
        """
        if v is not None:
            v = re.sub(r"<[^>]+>", "", v)
        return v

    @field_validator("custom_columns")
    @classmethod
    def validate_custom_columns_size(cls, v):
        """Prevent oversized or deeply nested JSONB payloads."""
        if v is not None:
            serialized = json.dumps(v)
            if len(serialized) > 10240:
                raise ValueError("Custom columns config must be under 10KB")

            def _check_depth(obj, depth=0):
                if depth > 5:
                    raise ValueError("Custom columns nesting depth must not exceed 5")
                if isinstance(obj, dict):
                    for val in obj.values():
                        _check_depth(val, depth + 1)
                elif isinstance(obj, list):
                    for item in obj:
                        _check_depth(item, depth + 1)

            _check_depth(v)
        return v


class ReportCardConfigResponse(BaseSchema):
    """Report card config response."""

    id: UUID
    curriculum_profile_id: UUID
    template_key: str
    show_position: bool
    show_class_average: bool
    show_subject_position: bool
    show_effort_grade: bool
    show_predicted_grades: bool
    show_gpa: bool
    show_credits: bool
    show_honor_roll: bool
    show_learner_profile: bool
    show_atl_skills: bool
    custom_columns: dict | None = None
    header_text: str | None = None
    footer_text: str | None = None
    created_at: datetime
    updated_at: datetime


# =========================
# Grade Equivalency Schemas
# =========================


class GradeMapping(BaseSchema):
    """A single source-to-target grade mapping within a batch create."""

    source_grade_id: UUID
    target_grade_id: UUID
    notes: str | None = None


class GradeEquivalencyCreate(BaseSchema):
    """
    Create a batch of grade equivalency mappings between two scales.

    All mappings in the batch share the same source/target grading scale pair.
    """

    source_grading_scale_id: UUID
    target_grading_scale_id: UUID
    mappings: list[GradeMapping] = Field(..., min_length=1)


class GradeEquivalencyUpdate(BaseSchema):
    """Update an existing grade equivalency (notes only)."""

    notes: str | None = Field(default=None, max_length=1000)


class GradeEquivalencyResponse(BaseSchema):
    """Grade equivalency response."""

    id: UUID
    source_grading_scale_id: UUID
    target_grading_scale_id: UUID
    source_grade_id: UUID
    target_grade_id: UUID
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class GradeEquivalencyListResponse(BaseSchema):
    """Paginated list of grade equivalencies."""

    items: list[GradeEquivalencyResponse]
    total: int
    page: int
    page_size: int
    pages: int


class GradeConvertRequest(BaseSchema):
    """Request to convert a grade from one scale to another."""

    source_grade_id: UUID
    source_grading_scale_id: UUID
    target_grading_scale_id: UUID


# =========================
# Subject Curriculum Mapping Schemas
# =========================


class SubjectCurriculumMappingCreate(BaseSchema):
    """Create a subject-to-curriculum mapping."""

    subject_id: UUID
    curriculum_profile_id: UUID
    external_code: str | None = Field(default=None, max_length=20)
    external_name: str | None = Field(default=None, max_length=200)
    level: str | None = Field(default=None, max_length=50)
    credits: Decimal | None = Field(default=None, ge=0, le=999)
    coefficient: Decimal | None = Field(default=None, ge=0, le=999)
    is_hl: bool = False
    grading_scale_id: UUID | None = None
    config: dict | None = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, v):
        return _validate_config_size(v)


class SubjectCurriculumMappingUpdate(BaseSchema):
    """Update an existing subject-to-curriculum mapping."""

    external_code: str | None = Field(default=None, max_length=20)
    external_name: str | None = Field(default=None, max_length=200)
    level: str | None = Field(default=None, max_length=50)
    credits: Decimal | None = Field(default=None, ge=0, le=999)
    coefficient: Decimal | None = Field(default=None, ge=0, le=999)
    is_hl: bool | None = None
    grading_scale_id: UUID | None = None
    config: dict | None = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, v):
        return _validate_config_size(v)


class SubjectCurriculumMappingResponse(BaseSchema):
    """Subject-to-curriculum mapping response."""

    id: UUID
    subject_id: UUID
    curriculum_profile_id: UUID
    external_code: str | None = None
    external_name: str | None = None
    level: str | None = None
    credits: Decimal | None = None
    coefficient: Decimal | None = None
    is_hl: bool
    grading_scale_id: UUID | None = None
    config: dict | None = None
    created_at: datetime
    updated_at: datetime


class SubjectCurriculumMappingListResponse(BaseSchema):
    """Paginated list of subject-to-curriculum mappings."""

    items: list[SubjectCurriculumMappingResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# External Exam Registration Schemas
# =========================


class ExternalExamSubject(BaseSchema):
    """A single subject entry in an external exam registration."""

    subject_code: str = Field(..., max_length=20)
    subject_name: str | None = Field(default=None, max_length=200)
    level: str | None = Field(default=None, max_length=50)
    paper_numbers: list[str] | None = None


class ExternalExamRegistrationCreate(BaseSchema):
    """Create an external exam registration for a student."""

    student_id: UUID
    exam_board: str = Field(
        ...,
        pattern="^(waec|cambridge_international|edexcel|college_board|ibo|other)$",
    )
    exam_session: str = Field(..., max_length=20)
    subjects: list[ExternalExamSubject] = Field(..., min_length=1)
    candidate_number: str | None = Field(default=None, max_length=50)
    center_number: str | None = Field(default=None, max_length=20)
    registration_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ExternalExamRegistrationUpdate(BaseSchema):
    """Update an external exam registration (identity fields are immutable)."""

    subjects: list[ExternalExamSubject] | None = None
    candidate_number: str | None = Field(default=None, max_length=50)
    center_number: str | None = Field(default=None, max_length=20)
    registration_status: str | None = Field(
        default=None, pattern="^(pending|registered|confirmed)$"
    )
    registration_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ExternalExamRegistrationResponse(BaseSchema):
    """External exam registration response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    exam_board: str
    exam_session: str
    subjects: list[dict]  # JSONB
    candidate_number: str | None = None
    center_number: str | None = None
    registration_status: str
    results: list[dict] | None = None
    registration_date: date | None = None
    results_date: date | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ExternalExamRegistrationListResponse(BaseSchema):
    """Paginated list of external exam registrations."""

    items: list[ExternalExamRegistrationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BulkExternalExamRegistrationCreate(BaseSchema):
    """Bulk create external exam registrations (up to 200)."""

    registrations: list[ExternalExamRegistrationCreate] = Field(..., min_length=1, max_length=200)


class ResultsImportPreview(BaseSchema):
    """Preview result of a dry-run CSV results import."""

    total_rows: int
    matched: int
    unmatched: int
    errors: list[str]
    preview_rows: list[dict]


class ResultsImportCommit(BaseSchema):
    """Result of a committed CSV results import."""

    imported: int
    skipped: int
    errors: list[str]


# =========================
# Predicted Grade Schemas
# =========================


class PredictedGradeCreate(BaseSchema):
    """Create a new predicted grade."""

    student_id: UUID
    subject_id: UUID
    academic_year_id: UUID
    term_id: UUID | None = None
    predicted_grade: str | None = Field(default=None, max_length=10)
    target_grade: str | None = Field(default=None, max_length=10)
    predicted_score: Decimal | None = Field(default=None, ge=0, le=999.99)
    notes: str | None = Field(default=None, max_length=1000)


class PredictedGradeUpdate(BaseSchema):
    """Update an existing predicted grade (mutable fields only)."""

    predicted_grade: str | None = Field(default=None, max_length=10)
    target_grade: str | None = Field(default=None, max_length=10)
    predicted_score: Decimal | None = Field(default=None, ge=0, le=999.99)
    notes: str | None = Field(default=None, max_length=1000)


class PredictedGradeResponse(BaseSchema):
    """Predicted grade response."""

    id: UUID
    student_id: UUID
    subject_id: UUID
    academic_year_id: UUID
    term_id: UUID | None = None
    predicted_grade: str | None = None
    target_grade: str | None = None
    predicted_score: Decimal | None = None
    predicted_by: UUID | None = None
    predicted_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class PredictedGradeListResponse(BaseSchema):
    """Paginated list of predicted grades."""

    items: list[PredictedGradeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BulkPredictedGradeCreate(BaseSchema):
    """Bulk create predicted grades (up to 200)."""

    predictions: list[PredictedGradeCreate] = Field(..., min_length=1, max_length=200)


class MockPredictedGradeResponse(BaseSchema):
    """Response from generating predicted grades from a mock exam."""

    created: int
    updated: int
    skipped: int


# =========================
# Credit & GPA Schemas
# =========================


class StudentCreditRecordCreate(BaseSchema):
    """Create or update a student credit record."""

    student_id: UUID
    subject_id: UUID
    curriculum_profile_id: UUID
    academic_year_id: UUID
    term_id: UUID | None = None
    credits_attempted: Decimal = Field(ge=0, le=99.9)
    credits_earned: Decimal = Field(ge=0, le=99.9)
    grade_points: Decimal | None = Field(default=None, ge=0, le=99.99)
    weighted_grade_points: Decimal | None = Field(default=None, ge=0, le=99.99)
    is_ap: bool = False
    is_honors: bool = False


class StudentCreditResponse(BaseSchema):
    """Student credit record response."""

    id: UUID
    student_id: UUID
    subject_id: UUID
    curriculum_profile_id: UUID
    academic_year_id: UUID
    term_id: UUID | None = None
    credits_attempted: Decimal
    credits_earned: Decimal
    grade_points: Decimal | None = None
    weighted_grade_points: Decimal | None = None
    is_ap: bool
    is_honors: bool
    created_at: datetime


class StudentCreditListResponse(BaseSchema):
    """Paginated list of student credit records."""

    items: list[StudentCreditResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StudentGPAResponse(BaseSchema):
    """Calculated GPA response for a student."""

    student_id: UUID
    curriculum_profile_id: UUID
    term_gpa: Decimal | None = None
    weighted_gpa: Decimal | None = None
    cumulative_gpa: Decimal | None = None
    cumulative_weighted_gpa: Decimal | None = None
    total_credits_attempted: Decimal
    total_credits_earned: Decimal
    honor_roll: bool


class TranscriptSubjectRecord(BaseSchema):
    """A single subject entry within a transcript term record."""

    subject_name: str
    subject_code: str | None = None
    grade: str | None = None
    credits_attempted: Decimal
    credits_earned: Decimal
    grade_points: Decimal | None = None
    is_ap: bool = False
    is_honors: bool = False


class TranscriptTermRecord(BaseSchema):
    """A single term/semester entry within a transcript."""

    academic_year: str
    term: str | None = None
    subjects: list[TranscriptSubjectRecord]
    term_gpa: Decimal | None = None
    term_credits_earned: Decimal


class TranscriptResponse(BaseSchema):
    """Full academic transcript response."""

    student_id: UUID
    student_name: str
    curriculum_profile: str
    academic_records: list[TranscriptTermRecord]
    cumulative_gpa: Decimal | None = None
    weighted_gpa: Decimal | None = None
    total_credits_earned: Decimal
    graduation_credits_required: Decimal | None = None
    credits_remaining: Decimal | None = None
    honors: list[str]
    generated_at: datetime


# Update forward references
CurriculumProfileDetailResponse.model_rebuild()
