"""
SIMS Plus - Staff Endpoints Package

Combines all staff sub-routers into a single router for backward compatibility.
"""

from fastapi import APIRouter

from .departments import router as departments_router
from .staff import router as staff_router

router = APIRouter()

# Department routes must come first so /departments doesn't conflict with /{staff_id}
router.include_router(departments_router)
router.include_router(staff_router)
