"""
SIMS Plus - Examination Schemas

Pydantic schemas for examination endpoints.
"""

from datetime import date, datetime, time
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
# Exam Schemas
# =========================


class ExamCreate(BaseSchema):
    """Create exam request."""

    academic_year_id: UUID
    term_id: UUID
    name: str = Field(..., min_length=1, max_length=100, description="Exam name")
    description: Optional[str] = None
    exam_type: str = Field(..., pattern="^(quiz|midterm|end_term|mock|practical|project)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: Optional[date], info) -> Optional[date]:
        if v and "start_date" in info.data and info.data["start_date"]:
            if v < info.data["start_date"]:
                raise ValueError("End date must be on or after start date")
        return v


class ExamUpdate(BaseSchema):
    """Update exam request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    exam_type: Optional[str] = Field(None, pattern="^(quiz|midterm|end_term|mock|practical|project)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(
        None,
        pattern="^(draft|scheduled|ongoing|completed|results_published|cancelled)$"
    )


class ExamResponse(BaseSchema):
    """Exam response."""

    id: UUID
    tenant_id: UUID
    academic_year_id: UUID
    term_id: UUID
    name: str
    description: Optional[str] = None
    exam_type: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class ExamWithContextResponse(ExamResponse):
    """Exam with academic year and term info."""

    academic_year_name: Optional[str] = None
    term_name: Optional[str] = None
    subjects_count: int = 0


class ExamListResponse(BaseSchema):
    """Paginated exam list response."""

    items: list[ExamWithContextResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Exam Subject Schemas
# =========================


class ExamSubjectCreate(BaseSchema):
    """Create exam subject request."""

    subject_id: UUID
    class_id: UUID
    section_id: Optional[UUID] = Field(None, description="Optional section - if not specified, applies to whole class")
    grading_scale_id: Optional[UUID] = Field(None, description="Grading scale for auto grade calculation")
    max_score: Decimal = Field(default=Decimal("100.00"), ge=0, le=1000)
    pass_mark: Decimal = Field(default=Decimal("50.00"), ge=0)
    exam_date: Optional[date] = None
    exam_time: Optional[time] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    venue: Optional[str] = Field(None, max_length=100)


class ExamSubjectBulkCreate(BaseSchema):
    """Bulk create exam subjects for multiple classes/sections."""

    class_ids: list[UUID] = Field(..., min_length=1, description="Classes to add subjects for")
    section_ids: Optional[list[UUID]] = Field(None, description="Sections to add subjects for (optional)")
    subject_ids: list[UUID] = Field(..., min_length=1, description="Subjects to add")
    grading_scale_id: Optional[UUID] = Field(None, description="Grading scale for auto grade calculation")
    max_score: Decimal = Field(default=Decimal("100.00"), ge=0, le=1000)
    pass_mark: Decimal = Field(default=Decimal("50.00"), ge=0)


class ExamSubjectAutoPopulate(BaseSchema):
    """Auto-populate exam subjects from curriculum (ClassSubjects)."""

    class_ids: list[UUID] = Field(..., min_length=1, description="Classes to add - subjects fetched from curriculum")
    section_ids: Optional[list[UUID]] = Field(None, description="Sections to add subjects for (optional)")
    grading_scale_id: Optional[UUID] = Field(None, description="Grading scale for auto grade calculation")
    max_score: Decimal = Field(default=Decimal("100.00"), ge=0, le=1000)
    pass_mark: Decimal = Field(default=Decimal("50.00"), ge=0)


class ExamSubjectUpdate(BaseSchema):
    """Update exam subject request."""

    grading_scale_id: Optional[UUID] = Field(None, description="Grading scale for auto grade calculation")
    max_score: Optional[Decimal] = Field(None, ge=0, le=1000)
    pass_mark: Optional[Decimal] = Field(None, ge=0)
    exam_date: Optional[date] = None
    exam_time: Optional[time] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    venue: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(
        None,
        pattern="^(pending|scores_entered|submitted|published)$"
    )


class ExamSubjectResponse(BaseSchema):
    """Exam subject response."""

    id: UUID
    tenant_id: UUID
    exam_id: UUID
    subject_id: UUID
    class_id: UUID
    section_id: Optional[UUID] = None
    grading_scale_id: Optional[UUID] = None
    max_score: Decimal
    pass_mark: Decimal
    exam_date: Optional[date] = None
    exam_time: Optional[time] = None
    duration_minutes: Optional[int] = None
    venue: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ExamSubjectWithDetailsResponse(ExamSubjectResponse):
    """Exam subject with subject and class details."""

    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    class_name: Optional[str] = None
    class_sequence: int = 0
    section_name: Optional[str] = None
    grading_scale_name: Optional[str] = None
    scores_count: int = 0
    students_count: int = 0


# =========================
# Exam Score Schemas
# =========================


class ScoreEntry(BaseSchema):
    """Single score entry for bulk operations."""

    student_id: UUID
    score: Optional[Decimal] = Field(None, ge=0)
    is_absent: bool = False
    teacher_remark: Optional[str] = None


class ExamScoreBulkCreate(BaseSchema):
    """Bulk create/update scores request."""

    grading_scale_id: Optional[UUID] = Field(None, description="Grading scale for auto grade calculation")
    scores: list[ScoreEntry] = Field(..., min_length=1)


class ExamScoreUpdate(BaseSchema):
    """Update single score request."""

    score: Optional[Decimal] = Field(None, ge=0)
    is_absent: Optional[bool] = None
    teacher_remark: Optional[str] = None


class ExamScoreResponse(BaseSchema):
    """Exam score response."""

    id: UUID
    tenant_id: UUID
    exam_subject_id: UUID
    student_id: UUID
    score: Optional[Decimal] = None
    is_absent: bool
    grade: Optional[str] = None
    grade_point: Optional[Decimal] = None
    grade_remark: Optional[str] = None
    teacher_remark: Optional[str] = None
    entered_by: Optional[UUID] = None
    entered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ExamScoreWithStudentResponse(ExamScoreResponse):
    """Exam score with student details."""

    student_name: str
    student_id_number: str  # The student's ID like "STU-2025-001"


class ScoreEntryStudent(BaseSchema):
    """Student with score data for score entry form."""

    student_id: UUID
    first_name: str
    last_name: str
    student_number: str  # The student's ID like "STU-2025-001"
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    current_score: Optional[Decimal] = None
    current_grade: Optional[str] = None
    is_absent: bool = False
    teacher_remark: Optional[str] = None
    score_id: Optional[UUID] = None


class ScoreEntryFormResponse(BaseSchema):
    """Response for score entry form - exam subject details with students."""

    exam_subject_id: UUID
    subject_name: str
    subject_code: Optional[str] = None
    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    max_score: Decimal
    pass_mark: Decimal
    grading_scale_id: Optional[UUID] = None
    students: list[ScoreEntryStudent]


class BulkScoreResult(BaseSchema):
    """Result of bulk score entry."""

    created: int = 0
    updated: int = 0
    failed: int = 0
    errors: list[dict] = []


# =========================
# Score Change Log (Audit Trail)
# =========================


class ScoreChangeLogResponse(BaseSchema):
    """Response for score change log entry."""

    id: UUID
    exam_score_id: UUID
    old_score: Optional[Decimal] = None
    new_score: Optional[Decimal] = None
    old_is_absent: Optional[bool] = None
    new_is_absent: Optional[bool] = None
    change_type: str
    change_reason: Optional[str] = None
    changed_by: Optional[UUID] = None
    changed_by_name: Optional[str] = None
    changed_at: datetime
    ip_address: Optional[str] = None


class ScoreChangeLogListResponse(BaseSchema):
    """Response for list of score change logs."""

    items: list[ScoreChangeLogResponse]
    total: int


# =========================
# Continuous Assessment Schemas
# =========================


class CACreate(BaseSchema):
    """Create continuous assessment entry."""

    term_id: UUID
    class_id: UUID
    subject_id: UUID
    student_id: UUID
    assessment_type: str = Field(..., pattern="^(class_work|homework|test|project|assignment)$")
    title: str = Field(..., min_length=1, max_length=100)
    max_score: Decimal = Field(default=Decimal("10.00"), ge=0, le=100)
    score: Optional[Decimal] = Field(None, ge=0)
    assessment_date: date


class CABulkCreate(BaseSchema):
    """Bulk create CA entries for a class."""

    term_id: UUID
    class_id: UUID
    section_id: Optional[UUID] = None
    subject_id: UUID
    assessment_type: str = Field(..., pattern="^(class_work|homework|test|project|assignment)$")
    title: str = Field(..., min_length=1, max_length=100)
    max_score: Decimal = Field(default=Decimal("10.00"), ge=0, le=100)
    assessment_date: date
    scores: list[ScoreEntry] = Field(..., min_length=1)


class CAUpdate(BaseSchema):
    """Update CA entry."""

    assessment_type: Optional[str] = Field(None, pattern="^(class_work|homework|test|project|assignment)$")
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    max_score: Optional[Decimal] = Field(None, ge=0, le=100)
    score: Optional[Decimal] = Field(None, ge=0)
    assessment_date: Optional[date] = None


class CAResponse(BaseSchema):
    """CA entry response."""

    id: UUID
    tenant_id: UUID
    academic_year_id: UUID
    term_id: UUID
    class_id: UUID
    subject_id: UUID
    student_id: UUID
    assessment_type: str
    title: str
    max_score: Decimal
    score: Optional[Decimal] = None
    assessment_date: date
    entered_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class CAWithDetailsResponse(CAResponse):
    """CA with student and subject details."""

    student_name: str
    student_id_number: str
    subject_name: str
    class_name: str


class CASummaryResponse(BaseSchema):
    """CA summary for a student/subject."""

    student_id: UUID
    student_name: str
    subject_id: UUID
    subject_name: str
    total_assessments: int
    total_max_score: Decimal
    total_score: Decimal
    average_percentage: Decimal


# =========================
# Results & Rankings Schemas
# =========================


class SubjectResult(BaseSchema):
    """Result for a single subject.

    Ghana's Assessment Structure:
    - Class Score (50%): All CA components (classwork, homework, quiz, midterm, etc.)
    - Exams Score (50%): End of term examination only
    - Total Score (100%): Class Score + Exams Score
    """

    subject_id: UUID
    subject_name: str
    subject_code: Optional[str] = None
    # Raw scores for reference
    ca_score: Optional[Decimal] = None  # Combined CA raw score
    ca_max: Optional[Decimal] = None    # Combined CA max score
    end_term_score: Optional[Decimal] = None  # End term raw score
    end_term_max: Optional[Decimal] = None    # End term max score
    # Normalized scores for report card (Ghana 50/50 system)
    class_score: Optional[Decimal] = None   # CA normalized to 50
    exams_score: Optional[Decimal] = None   # End term normalized to 50
    total_score: Optional[Decimal] = None   # Total out of 100
    grade: Optional[str] = None
    grade_point: Optional[Decimal] = None
    grade_remark: Optional[str] = None
    subject_position: Optional[int] = None
    teacher_remark: Optional[str] = None


class StudentExamResult(BaseSchema):
    """Exam results for a student."""

    student_id: UUID
    student_name: str
    student_id_number: str
    class_name: str
    section_name: Optional[str] = None
    subjects: list[SubjectResult]
    total_score: Decimal
    average_score: Decimal
    subjects_count: int
    class_position: int
    section_position: Optional[int] = None
    class_size: int
    section_size: Optional[int] = None


class ClassResultsResponse(BaseSchema):
    """Class results with rankings."""

    exam_id: UUID
    exam_name: str
    class_id: UUID
    class_name: str
    term_name: str
    students: list[StudentExamResult]
    class_average: Decimal
    highest_score: Decimal
    lowest_score: Decimal


# =========================
# Term Report Schemas
# =========================


class TermReportGenerate(BaseSchema):
    """Request to generate term reports."""

    term_id: UUID
    class_id: UUID
    section_id: Optional[UUID] = None


class TermReportRemarksUpdate(BaseSchema):
    """Update term report remarks."""

    conduct_grade: Optional[str] = Field(None, max_length=50)
    interest: Optional[str] = Field(None, max_length=500)
    class_teacher_remark: Optional[str] = Field(None, max_length=1000)
    headmaster_remark: Optional[str] = Field(None, max_length=1000)


class TermReportResponse(BaseSchema):
    """Term report response."""

    id: UUID
    tenant_id: UUID
    academic_year_id: UUID
    term_id: UUID
    student_id: UUID
    class_id: UUID
    section_id: Optional[UUID] = None
    total_score: Optional[Decimal] = None
    average_score: Optional[Decimal] = None
    subjects_count: Optional[int] = None
    class_position: Optional[int] = None
    section_position: Optional[int] = None
    class_size: Optional[int] = None
    section_size: Optional[int] = None
    attendance_percentage: Optional[Decimal] = None
    days_present: Optional[int] = None
    days_absent: Optional[int] = None
    total_school_days: Optional[int] = None
    conduct_grade: Optional[str] = None
    interest: Optional[str] = None
    class_teacher_remark: Optional[str] = None
    headmaster_remark: Optional[str] = None
    is_published: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TermReportWithDetailsResponse(TermReportResponse):
    """Term report with student and academic details."""

    student_name: str
    student_id_number: str
    class_name: str
    section_name: Optional[str] = None
    term_name: str
    academic_year_name: str
    subject_results: list[SubjectResult] = []


class TermReportListResponse(BaseSchema):
    """List of term reports."""

    items: list[TermReportWithDetailsResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Analytics Schemas
# =========================


class GradeCount(BaseSchema):
    """Grade count with percentage."""

    grade: str
    count: int
    percentage: Decimal


class GradeDistributionResponse(BaseSchema):
    """Grade distribution for a class/subject."""

    exam_id: UUID
    exam_name: str
    class_id: UUID
    class_name: str
    subject_id: Optional[UUID] = None
    subject_name: Optional[str] = None
    total_students: int
    graded_students: int
    absent_students: int
    grades: list[GradeCount]


class PassFailStatistics(BaseSchema):
    """Pass/fail statistics."""

    total_students: int
    passed: int
    failed: int
    absent: int
    pass_rate: Decimal
    fail_rate: Decimal


class ClassStatisticsResponse(BaseSchema):
    """Overall class statistics for an exam."""

    exam_id: UUID
    exam_name: str
    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    total_students: int
    students_with_scores: int
    class_average: Optional[Decimal] = None
    highest_score: Optional[Decimal] = None
    lowest_score: Optional[Decimal] = None
    median_score: Optional[Decimal] = None
    pass_fail: PassFailStatistics
    grade_distribution: list[GradeCount]


class SubjectStatisticsResponse(BaseSchema):
    """Statistics for a single subject."""

    subject_id: UUID
    subject_name: str
    subject_code: Optional[str] = None
    total_students: int
    students_with_scores: int
    absent_students: int
    average_score: Optional[Decimal] = None
    highest_score: Optional[Decimal] = None
    lowest_score: Optional[Decimal] = None
    median_score: Optional[Decimal] = None
    pass_rate: Decimal
    grade_distribution: list[GradeCount]


class ExamAnalyticsResponse(BaseSchema):
    """Complete exam analytics response."""

    exam_id: UUID
    exam_name: str
    exam_type: str
    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    term_name: str
    academic_year_name: str
    overall_statistics: ClassStatisticsResponse
    subject_statistics: list[SubjectStatisticsResponse]


class SubjectRankingStudent(BaseSchema):
    """Student ranking in a subject."""

    student_id: UUID
    student_name: str
    student_id_number: str
    score: Optional[Decimal] = None
    grade: Optional[str] = None
    position: int


class SubjectRankingsResponse(BaseSchema):
    """Subject rankings response."""

    exam_id: UUID
    exam_name: str
    subject_id: UUID
    subject_name: str
    class_id: UUID
    class_name: str
    total_students: int
    rankings: list[SubjectRankingStudent]


# =========================
# Timetable Schemas
# =========================


class ExamTimetableEntry(BaseSchema):
    """Single timetable entry."""

    exam_subject_id: UUID
    subject_id: UUID
    subject_name: str
    subject_code: Optional[str] = None
    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    exam_date: Optional[date] = None
    exam_time: Optional[time] = None
    duration_minutes: Optional[int] = None
    venue: Optional[str] = None
    max_score: Decimal
    status: str


class ExamTimetableResponse(BaseSchema):
    """Full exam timetable."""

    exam_id: UUID
    exam_name: str
    exam_type: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    entries: list[ExamTimetableEntry]
    total_subjects: int
    scheduled_subjects: int
    unscheduled_subjects: int


class TimetableConflict(BaseSchema):
    """A scheduling conflict."""

    conflict_type: str  # "venue", "time_overlap", "student"
    severity: str  # "error", "warning"
    message: str
    exam_subject_1_id: UUID
    exam_subject_1_name: str
    exam_subject_2_id: Optional[UUID] = None
    exam_subject_2_name: Optional[str] = None


class TimetableConflictsResponse(BaseSchema):
    """Conflicts check response."""

    exam_id: UUID
    has_conflicts: bool
    total_conflicts: int
    conflicts: list[TimetableConflict]


class BulkTimetableUpdate(BaseSchema):
    """Bulk update timetable entries."""

    entries: list["TimetableEntryUpdate"]


class TimetableEntryUpdate(BaseSchema):
    """Single timetable entry update."""

    exam_subject_id: UUID
    exam_date: Optional[date] = None
    exam_time: Optional[time] = None
    duration_minutes: Optional[int] = None
    venue: Optional[str] = None


class BulkTimetableUpdateResult(BaseSchema):
    """Result of bulk timetable update."""

    updated: int
    failed: int
    errors: list[dict] = []
    conflicts: list[TimetableConflict] = []
