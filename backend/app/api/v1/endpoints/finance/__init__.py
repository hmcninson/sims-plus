"""
SIMS Plus - Finance Endpoints Package

Combines all finance sub-routers into a single router for backward compatibility.
"""

from fastapi import APIRouter

from .fee_types import router as fee_types_router
from .fee_structures import router as fee_structures_router
from .invoices import router as invoices_router
from .payments import router as payments_router
from .scholarships import router as scholarships_router
from .credit_notes import router as credit_notes_router
from .dashboard import router as dashboard_router
from .reports import router as reports_router

router = APIRouter()

# Dashboard must be first so /dashboard doesn't conflict with parameterized routes
router.include_router(dashboard_router)
router.include_router(fee_types_router)
router.include_router(fee_structures_router)
router.include_router(invoices_router)
router.include_router(payments_router)
router.include_router(scholarships_router)
router.include_router(credit_notes_router)
router.include_router(reports_router)
