"""
SIMS Plus - Messaging Endpoints Package

Combines SMS, email, and recipient-resolution sub-routers into a single
router mounted at /api/v1/messaging.
"""

from fastapi import APIRouter

from .sms import router as sms_router
from .email import router as email_router
from .recipients import router as recipients_router

router = APIRouter()

router.include_router(sms_router)
router.include_router(email_router)
router.include_router(recipients_router)
