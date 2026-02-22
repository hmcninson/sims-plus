"""
SIMS Plus - Boarding Endpoints Package

Combines all boarding sub-routers into a single router for inclusion
in the main API router. Sub-modules handle houses/dormitories/beds,
student assignments, roll calls, exeats, incidents, and dining.
"""

from fastapi import APIRouter

from .stats import router as stats_router
from .houses import router as houses_router
from .assignments import router as assignments_router
from .roll_calls import router as roll_calls_router
from .exeats import router as exeats_router
from .incidents import router as incidents_router
from .dining import router as dining_router

router = APIRouter()

# Stats must be first so /stats doesn't conflict with parameterized routes
router.include_router(stats_router)
router.include_router(houses_router)
router.include_router(assignments_router)
router.include_router(roll_calls_router)
router.include_router(exeats_router)
router.include_router(incidents_router)
router.include_router(dining_router)
