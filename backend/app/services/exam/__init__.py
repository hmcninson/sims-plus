"""
SIMS Plus - Exam Services Package

Re-exports all service classes for backward compatibility.
Existing imports like `from app.services.exam import ExamService` continue to work.
"""

from app.services.exam.exam_service import ExamService, ExamServiceError
from app.services.exam.score_service import ScoreService
from app.services.exam.ca_service import CAService
from app.services.exam.report_service import TermReportService
from app.services.exam.analytics_service import AnalyticsService

__all__ = [
    "ExamService",
    "ExamServiceError",
    "ScoreService",
    "CAService",
    "TermReportService",
    "AnalyticsService",
]
