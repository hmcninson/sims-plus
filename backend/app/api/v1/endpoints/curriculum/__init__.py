"""
SIMS Plus - Curriculum Endpoints Package

Combines profile, assessment, equivalency, subject mapping,
and external exam sub-routers into a single curriculum router.
"""

from fastapi import APIRouter

from .profiles import router as profiles_router
from .assessment import router as assessment_router
from .equivalencies import router as equivalencies_router
from .subject_mappings import router as subject_mappings_router
from .external_exams import router as external_exams_router
from .credits import router as credits_router
from .predicted_grades import router as predicted_grades_router

router = APIRouter(prefix="/curriculum", tags=["Curriculum"])
router.include_router(profiles_router)
router.include_router(assessment_router)
router.include_router(equivalencies_router)
router.include_router(subject_mappings_router)
router.include_router(external_exams_router)
router.include_router(credits_router)
router.include_router(predicted_grades_router)
