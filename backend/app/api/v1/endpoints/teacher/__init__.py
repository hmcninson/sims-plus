"""
SIMS Plus - Teacher Portal Endpoints Package

Combines all teacher portal sub-routers into a single router for inclusion
in the main API router. Sub-modules handle dashboard, schedule, classes,
grading, attendance, notes, reports, lesson plans, communication,
notifications, and head teacher performance views.
"""

from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .schedule import router as schedule_router
from .classes import router as classes_router
from .grading import router as grading_router
from .attendance import router as attendance_router
from .notes import router as notes_router
from .reports import router as reports_router
from .lessons import router as lessons_router
from .communication import router as communication_router
from .notifications import router as notifications_router
from .head_teacher import router as head_teacher_router

router = APIRouter()

# Dashboard first so /dashboard doesn't conflict with parameterized routes
router.include_router(dashboard_router)
router.include_router(schedule_router)
router.include_router(classes_router)
router.include_router(grading_router)
router.include_router(attendance_router)
router.include_router(notes_router)
router.include_router(reports_router)
router.include_router(lessons_router)
router.include_router(communication_router)
router.include_router(notifications_router)
router.include_router(head_teacher_router)
