"""
SIMS Plus - Academic Endpoints Package

Combines all academic sub-routers into a single router for backward compatibility.
"""

from fastapi import APIRouter

from .academic_years import router as academic_years_router
from .classes import router as classes_router
from .subjects import router as subjects_router

router = APIRouter()

router.include_router(academic_years_router)
router.include_router(classes_router)
router.include_router(subjects_router)
