"""
SIMS Plus - SMS Service

Stub implementation for SMS sending via gateway providers.
Actual provider integrations (Hubtel, Arkesel, Twilio) will be added later.
"""

import math
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sms import SMSLog, SMSProvider, SMSStatus

logger = structlog.get_logger()


class SMSError(Exception):
    """SMS operation failed."""

    def __init__(self, message: str, code: str = "sms_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class SMSService:
    """Service for sending SMS messages via gateway providers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_sms(
        self,
        tenant_id: UUID,
        recipient_phone: str,
        message: str,
        provider: SMSProvider = SMSProvider.HUBTEL,
    ) -> SMSLog:
        """
        Send an SMS message and log it.

        Currently a stub -- logs the message but does not actually send.
        The SMS log entry is persisted with PENDING status for future
        processing once provider integrations are implemented.
        """
        sms_log = SMSLog(
            tenant_id=tenant_id,
            recipient_phone=recipient_phone,
            message=message,
            provider=provider,
            status=SMSStatus.PENDING,
        )
        self.db.add(sms_log)
        await self.db.flush()
        await self.db.refresh(sms_log)

        # TODO: Integrate with Hubtel Collections API
        # TODO: Integrate with Arkesel API
        # TODO: Integrate with Twilio API
        logger.warning(
            "sms_send_stub",
            sms_id=str(sms_log.id),
            recipient=recipient_phone,
            provider=provider.value,
            message_length=len(message),
        )

        return sms_log

    async def get_sms_log(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[SMSStatus] = None,
    ) -> dict:
        """Get paginated SMS log for a tenant."""
        # Defense-in-depth: always scope by tenant_id
        base_conditions = [SMSLog.tenant_id == tenant_id]
        if status is not None:
            base_conditions.append(SMSLog.status == status)

        count_stmt = select(func.count()).select_from(SMSLog).where(*base_conditions)
        total = (await self.db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        offset = (page - 1) * page_size
        stmt = (
            select(SMSLog)
            .where(*base_conditions)
            .order_by(SMSLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
