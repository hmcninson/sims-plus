"""
SIMS Plus - Admissions Portal Endpoints Package

Combines all admissions sub-routers into a single router.
Public endpoints are under /public prefix (unauthenticated).
All other endpoints require JWT authentication + admissions permissions.
"""

from fastapi import APIRouter

from .public import router as public_router
from .webhook import router as webhook_router
from .periods import router as periods_router
from .applications import router as applications_router
from .exams import router as exams_router
from .decisions import router as decisions_router
from .enrollment import router as enrollment_router
from .enrollment_checklist import router as enrollment_checklist_router
from .promotions import router as promotions_router
from .return_intents import router as return_intents_router
from .dashboard import router as dashboard_router
from .applicant import router as applicant_router
from .applicant_public import router as applicant_public_router
from .inquiries import router as inquiries_router
from .interviews import router as interviews_router
from .cssps import router as cssps_router
from .capacity import router as capacity_router
from .events import router as events_router
from .analytics import router as analytics_router

router = APIRouter()

# Public endpoints (unauthenticated -- tenant resolved from subdomain)
router.include_router(public_router)
router.include_router(webhook_router)

# Applicant account routers
router.include_router(applicant_public_router, tags=["Applicant (Public)"])
router.include_router(applicant_router, tags=["Applicant (Authenticated)"])

# Admin endpoints (authenticated -- require JWT + permissions)
router.include_router(dashboard_router)
router.include_router(periods_router)
router.include_router(applications_router)
router.include_router(exams_router)
router.include_router(decisions_router)
router.include_router(enrollment_router)
router.include_router(enrollment_checklist_router, tags=["Admissions - Enrollment Checklist"])
router.include_router(promotions_router)
router.include_router(return_intents_router)
router.include_router(inquiries_router, tags=["Admissions - Inquiries"])
router.include_router(interviews_router, tags=["Admissions - Interviews"])
router.include_router(cssps_router, tags=["Admissions - CSSPS Import"])
router.include_router(capacity_router, tags=["Capacity Planning"])
router.include_router(events_router, tags=["School Events"])
router.include_router(analytics_router, tags=["Admissions Analytics"])
