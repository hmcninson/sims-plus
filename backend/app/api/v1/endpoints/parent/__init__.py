"""
SIMS Plus - Parent Portal Endpoints Package

Combines all parent portal sub-routers into a single router for inclusion
in the main API router. Sub-modules handle children, grades, finance,
attendance, communication, payments, onboarding, preferences, dashboard,
boarding/transport views, and admin operations.
"""

from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .children import router as children_router
from .grades import router as grades_router
from .finance import router as finance_router
from .attendance import router as attendance_router
from .communication import router as communication_router
from .payment import router as payment_router
from .onboarding import router as onboarding_router
from .preferences import router as preferences_router
from .boarding_transport import router as boarding_transport_router
from .admin import router as admin_router

router = APIRouter()

# Dashboard first so /dashboard doesn't conflict with parameterized routes
router.include_router(dashboard_router)
router.include_router(children_router)
router.include_router(grades_router)
router.include_router(finance_router)
router.include_router(attendance_router)
router.include_router(communication_router)
router.include_router(payment_router)
router.include_router(onboarding_router)
router.include_router(preferences_router)
router.include_router(boarding_transport_router)
router.include_router(admin_router)
