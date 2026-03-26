"""
SIMS Plus - Staff Endpoints Package

Combines all staff sub-routers into a single router for backward compatibility.
"""

from fastapi import APIRouter

from .departments import router as departments_router
from .staff import router as staff_router
from .documents import router as documents_router
from .history import router as history_router

router = APIRouter()

# Department routes must come first so /departments doesn't conflict with /{staff_id}
router.include_router(departments_router)
# Document and history routes use /{staff_id}/documents and /{staff_id}/employment-history
# so they must be registered before the catch-all /{staff_id} route in staff_router
router.include_router(documents_router, tags=["Staff Documents"])
router.include_router(history_router, tags=["Staff History"])
router.include_router(staff_router)
