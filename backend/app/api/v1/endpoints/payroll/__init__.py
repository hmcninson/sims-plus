"""
SIMS Plus - Payroll Endpoints Package

Combines all payroll sub-routers into a single router.
Feature-gated behind hr_payroll.
"""

from fastapi import APIRouter

from .config import router as config_router
from .loans import router as loans_router
from .payslips import router as payslips_router
from .reports import router as reports_router
from .runs import router as runs_router

router = APIRouter(prefix="/payroll", tags=["Payroll"])

router.include_router(config_router)
router.include_router(runs_router)
router.include_router(payslips_router)
router.include_router(reports_router)
router.include_router(loans_router)
