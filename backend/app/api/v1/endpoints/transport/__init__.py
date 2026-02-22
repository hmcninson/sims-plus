"""
SIMS Plus - Transport Endpoints Package

Combines all transport sub-routers into a single router for inclusion
in the main API router. Sub-modules handle vehicles, drivers, routes,
student transport assignments, and trip logs.
"""

from fastapi import APIRouter

from .stats import router as stats_router
from .vehicles import router as vehicles_router
from .drivers import router as drivers_router
from .routes import router as routes_router
from .assignments import router as assignments_router
from .trips import router as trips_router

router = APIRouter()

# Stats must be first so /stats doesn't conflict with parameterized routes
router.include_router(stats_router)
router.include_router(vehicles_router)
router.include_router(drivers_router)
router.include_router(routes_router)
router.include_router(assignments_router)
router.include_router(trips_router)
