"""
SIMS Plus - Teacher Portal Services Package

Re-exports all teacher service classes and the shared error type
for convenient importing throughout the application.
"""

from ._shared import TeacherServiceError
from .teacher_attendance import TeacherAttendanceService
from .teacher_classroom import TeacherClassroomService
from .teacher_communication import TeacherCommunicationService
from .teacher_context import TeacherContextService
from .teacher_dashboard import TeacherDashboardService
from .teacher_grading import TeacherGradingService
from .teacher_lesson import TeacherLessonService
from .teacher_notes import TeacherNotesService
from .teacher_performance import TeacherPerformanceService
from .teacher_reports import TeacherReportsService
from .teacher_schedule import TeacherScheduleService

__all__ = [
    "TeacherServiceError",
    "TeacherAttendanceService",
    "TeacherClassroomService",
    "TeacherCommunicationService",
    "TeacherContextService",
    "TeacherDashboardService",
    "TeacherGradingService",
    "TeacherLessonService",
    "TeacherNotesService",
    "TeacherPerformanceService",
    "TeacherReportsService",
    "TeacherScheduleService",
]
