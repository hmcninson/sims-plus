"""
SIMS Plus - Teacher Portal Schemas

Pydantic v2 schemas for the teacher portal: dashboard, schedule, classes,
grading, attendance, notes, reports, lesson plans, communication, and
head teacher performance views.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.parent import NoteType
from app.models.teacher import LessonPlanStatus


# =========================
# Dashboard Schemas
# =========================


class TeacherClassSummary(BaseModel):
    """Summary of a class the teacher is assigned to."""

    model_config = ConfigDict(from_attributes=True)

    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    student_count: int = 0
    is_class_teacher: bool = False


class TeacherSubjectSummary(BaseModel):
    """Summary of a subject the teacher teaches."""

    model_config = ConfigDict(from_attributes=True)

    subject_id: UUID
    subject_name: str
    class_count: int = 0


class UpcomingLesson(BaseModel):
    """A lesson on the teacher's upcoming schedule."""

    model_config = ConfigDict(from_attributes=True)

    timetable_id: UUID
    class_name: str
    section_name: Optional[str] = None
    subject_name: str
    day_of_week: int
    period_number: int
    start_time: str
    end_time: str
    room: Optional[str] = None


class PendingTask(BaseModel):
    """A pending task for the teacher's attention."""

    task_type: str = Field(..., description="e.g., score_entry, report_comment, lesson_plan")
    description: str
    count: int = 0
    link_context: Optional[dict] = None


class TeacherDashboard(BaseModel):
    """Aggregate teacher dashboard response."""

    teacher_name: str
    staff_id: str
    total_classes: int = 0
    total_subjects: int = 0
    total_students: int = 0
    classes: list[TeacherClassSummary] = []
    subjects: list[TeacherSubjectSummary] = []
    today_schedule: list[UpcomingLesson] = []
    pending_tasks: list[PendingTask] = []


# =========================
# Schedule Schemas
# =========================


class ScheduleEntry(BaseModel):
    """A single timetable entry for the teacher."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    subject_id: Optional[UUID] = None
    subject_name: Optional[str] = None
    day_of_week: int
    period_number: int
    start_time: str
    end_time: str
    room: Optional[str] = None


class DaySchedule(BaseModel):
    """All schedule entries for a specific day."""

    day_of_week: int
    day_name: str
    entries: list[ScheduleEntry] = []


class WeekSchedule(BaseModel):
    """Full weekly schedule for the teacher."""

    days: list[DaySchedule] = []


# =========================
# Class / Student Schemas
# =========================


class ClassStudentItem(BaseModel):
    """A student in a teacher's class."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: str = Field(..., description="System-generated student ID")
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    gender: str
    photo_url: Optional[str] = None
    status: str


class ClassOverview(BaseModel):
    """Detailed overview of a class the teacher teaches."""

    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    student_count: int = 0
    subjects: list[TeacherSubjectSummary] = []
    is_class_teacher: bool = False


class ClassStudentListResponse(BaseModel):
    """Paginated student list for a class."""

    students: list[ClassStudentItem] = []
    total: int = 0


# =========================
# Grading Schemas
# =========================


class PendingScoreEntry(BaseModel):
    """An exam subject pending score entry from this teacher."""

    model_config = ConfigDict(from_attributes=True)

    exam_id: UUID
    exam_name: str
    exam_subject_id: UUID
    subject_id: UUID
    subject_name: str
    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    max_score: Decimal
    total_students: int = 0
    scores_entered: int = 0
    status: str


class ScoreEntryItem(BaseModel):
    """Score entry for a single student."""

    student_id: UUID
    # Generous upper bound only; actual max_score validation is in the service layer
    # against the exam subject's configured max_score
    score: Optional[Decimal] = Field(None, ge=0, le=1000)
    is_absent: bool = False
    teacher_remark: Optional[str] = Field(None, max_length=500)


class BulkScoreEntryRequest(BaseModel):
    """Bulk score entry request for an exam subject."""

    scores: list[ScoreEntryItem] = Field(..., min_length=1)


class ScoreEntryResult(BaseModel):
    """Result of a single score entry operation."""

    student_id: UUID
    success: bool = True
    error: Optional[str] = None
    grade: Optional[str] = None
    grade_remark: Optional[str] = None


class BulkScoreEntryResponse(BaseModel):
    """Result of a bulk score entry operation."""

    total: int = 0
    successful: int = 0
    failed: int = 0
    results: list[ScoreEntryResult] = []


class StudentGradeSummary(BaseModel):
    """Summary of a student's grades in a subject for the current term."""

    student_id: UUID
    student_name: str
    exam_score: Optional[Decimal] = None
    exam_grade: Optional[str] = None
    ca_average: Optional[Decimal] = None
    total_score: Optional[Decimal] = None
    grade: Optional[str] = None
    grade_remark: Optional[str] = None


class ClassGradeSummary(BaseModel):
    """Summary of grades for a class-subject combination."""

    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    term_id: UUID
    term_name: str
    students: list[StudentGradeSummary] = []
    class_average: Optional[Decimal] = None
    highest_score: Optional[Decimal] = None
    lowest_score: Optional[Decimal] = None
    total_students: int = 0


# =========================
# Attendance Schemas
# =========================


class StudentAttendanceSummary(BaseModel):
    """Attendance summary for a student in a class."""

    student_id: UUID
    student_name: str
    days_present: int = 0
    days_absent: int = 0
    days_late: int = 0
    total_days: int = 0
    attendance_percentage: Optional[Decimal] = None


class ClassAttendanceSummary(BaseModel):
    """Attendance summary for a whole class."""

    class_id: UUID
    class_name: str
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    total_students: int = 0
    present_today: int = 0
    absent_today: int = 0
    late_today: int = 0
    attendance_percentage: Optional[Decimal] = None
    students: list[StudentAttendanceSummary] = []


# =========================
# Teacher Note Schemas
# =========================


class TeacherNoteCreate(BaseModel):
    """Request to create a teacher note about a student."""

    student_id: UUID
    subject_id: Optional[UUID] = None
    note_type: NoteType
    content: str = Field(..., min_length=1, max_length=2000)
    is_visible_to_parent: bool = True

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        return v.strip()


class TeacherNoteResponse(BaseModel):
    """Teacher note response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    student_name: Optional[str] = None
    subject_id: Optional[UUID] = None
    subject_name: Optional[str] = None
    note_type: str
    content: str
    is_visible_to_parent: bool
    parent_acknowledged: bool = False
    parent_acknowledged_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TeacherNoteListResponse(BaseModel):
    """Paginated list of teacher notes."""

    notes: list[TeacherNoteResponse] = []
    total: int = 0


# =========================
# Report Comment Schemas
# =========================


class ReportCommentCreate(BaseModel):
    """Request to create/update a class teacher comment."""

    class_teacher_comment: str = Field(..., min_length=1, max_length=1000)

    @field_validator("class_teacher_comment")
    @classmethod
    def strip_comment(cls, v: str) -> str:
        return v.strip()


class HeadTeacherCommentCreate(BaseModel):
    """Request to create/update a head teacher comment."""

    head_teacher_comment: str = Field(..., min_length=1, max_length=1000)

    @field_validator("head_teacher_comment")
    @classmethod
    def strip_comment(cls, v: str) -> str:
        return v.strip()


class ReportCommentResponse(BaseModel):
    """Report comment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    student_name: Optional[str] = None
    term_id: UUID
    academic_year_id: UUID
    class_teacher_comment: Optional[str] = None
    head_teacher_comment: Optional[str] = None
    class_teacher_signed: bool = False
    head_teacher_signed: bool = False
    created_at: datetime
    updated_at: datetime


class ReportCommentListResponse(BaseModel):
    """List of report comments for a class/term."""

    comments: list[ReportCommentResponse] = []
    total: int = 0


# =========================
# Lesson Plan Schemas
# =========================


class LessonPlanCreate(BaseModel):
    """Request to create a lesson plan."""

    class_id: UUID
    subject_id: UUID
    date: date
    period: Optional[int] = Field(None, ge=1, le=20)
    topic: str = Field(..., min_length=1, max_length=200)
    objectives: Optional[str] = Field(None, max_length=2000)
    resources: Optional[str] = Field(None, max_length=2000)
    activities: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("topic")
    @classmethod
    def strip_topic(cls, v: str) -> str:
        return v.strip()


class LessonPlanUpdate(BaseModel):
    """Request to update a lesson plan."""

    topic: Optional[str] = Field(None, min_length=1, max_length=200)
    objectives: Optional[str] = Field(None, max_length=2000)
    resources: Optional[str] = Field(None, max_length=2000)
    activities: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[LessonPlanStatus] = None

    @field_validator("topic")
    @classmethod
    def strip_topic(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class LessonPlanResponse(BaseModel):
    """Lesson plan response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_id: UUID
    class_id: UUID
    class_name: Optional[str] = None
    subject_id: UUID
    subject_name: Optional[str] = None
    date: date
    period: Optional[int] = None
    topic: str
    objectives: Optional[str] = None
    resources: Optional[str] = None
    activities: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class LessonPlanListResponse(BaseModel):
    """Paginated list of lesson plans."""

    plans: list[LessonPlanResponse] = []
    total: int = 0


# =========================
# Communication Schemas
# =========================


class ClassBroadcastRequest(BaseModel):
    """Request to send a broadcast message to all parents in a class."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    class_id: UUID
    priority: Literal["normal", "important", "urgent"] = "normal"

    @field_validator("title", "content")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class ClassBroadcastResponse(BaseModel):
    """Response after sending a class broadcast."""

    announcement_id: UUID
    message: str = "Broadcast sent successfully"


# =========================
# Head Teacher / Performance Schemas
# =========================


class TeacherPerformanceItem(BaseModel):
    """Performance metrics for a single teacher."""

    staff_id: UUID
    teacher_name: str
    total_classes: int = 0
    total_subjects: int = 0
    total_students: int = 0
    lesson_plans_created: int = 0
    lesson_plans_taught: int = 0
    scores_entered: int = 0
    scores_pending: int = 0
    notes_created: int = 0
    reports_signed: int = 0


class TeacherPerformanceSummary(BaseModel):
    """Summary of all teacher performance metrics for the head teacher."""

    total_teachers: int = 0
    teachers: list[TeacherPerformanceItem] = []
    overall_lesson_plan_completion: Optional[Decimal] = None
    overall_score_entry_completion: Optional[Decimal] = None


# =========================
# Notification Schemas
# =========================


class TeacherNotificationItem(BaseModel):
    """A single notification for the teacher portal.

    Maps from the shared Notification model but returns a simpler shape
    that matches the frontend TeacherNotification type (type and category
    as plain strings rather than enum objects).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    message: str
    type: str = Field(..., description="Notification severity: info, success, warning, error, system")
    category: str = Field(..., description="Notification category: academic, finance, attendance, etc.")
    is_read: bool = False
    created_at: datetime
    link: Optional[str] = None


class TeacherNotificationListResponse(BaseModel):
    """Paginated notification list for the teacher portal.

    Includes unread_count so the frontend can display a badge without
    making a separate request.
    """

    items: list[TeacherNotificationItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1
    unread_count: int = 0
