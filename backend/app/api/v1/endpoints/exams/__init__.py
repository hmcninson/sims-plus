"""
SIMS Plus - Examination Endpoints Package

Combines all exam sub-routers into a single router for backward compatibility.
"""

from fastapi import APIRouter

from .continuous_assessment import router as ca_router
from .exams import router as exams_router
from .reports import router as reports_router
from .scores import router as scores_router
from .analytics import router as analytics_router

router = APIRouter()

# CA routes must come before exam CRUD so /ca doesn't conflict with /{exam_id}
router.include_router(ca_router)
# Report routes must come before exam CRUD so /reports doesn't conflict with /{exam_id}
router.include_router(reports_router)
# Score-level routes (e.g. /scores/{score_id}) must come before /{exam_id}
router.include_router(scores_router)
# Exam CRUD includes /{exam_id} dynamic routes and /{exam_id}/subjects
router.include_router(exams_router)
# Analytics routes are under /{exam_id}/analytics and /{exam_id}/timetable
router.include_router(analytics_router)
