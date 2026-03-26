"""
SIMS Plus - Preschool Endpoints Package

Combines all preschool sub-routers into a single router for backward compatibility.
The main router.py can continue to use `from app.api.v1.endpoints.preschool import router`.
"""

from fastapi import APIRouter

from .core import router as core_router
from .assessment import router as assessment_router
from .observation import router as observation_router
from .report import router as report_router
from .incident import router as incident_router
from .pickup import router as pickup_router
from .portfolio import router as portfolio_router
from .extended_care import router as extended_care_router
from .supply import router as supply_router

router = APIRouter(prefix="/preschool", tags=["Preschool"])

# Include sub-routers — order matters for route matching
router.include_router(core_router)
router.include_router(assessment_router)
router.include_router(observation_router)
router.include_router(report_router)
router.include_router(incident_router)
router.include_router(pickup_router)
router.include_router(portfolio_router)
router.include_router(extended_care_router)
router.include_router(supply_router)
