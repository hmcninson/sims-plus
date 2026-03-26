"""
SIMS Plus - SMS Service

Sends SMS messages via the Arkesel gateway and maintains a persistent
log in the sms_log table for delivery tracking and audit.

When Arkesel API key is not configured (dev / staging), messages
are logged with PENDING status but not actually dispatched.
"""

import math
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sms import SMSLog, SMSProvider, SMSStatus
from app.services.messaging.arkesel_client import ArkeselClient

logger = structlog.get_logger()

# Module-level singleton so we only parse settings once
_sms_client = ArkeselClient()


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
        provider: SMSProvider = SMSProvider.ARKESEL,
        sender_id: str | None = None,
        _skip_limit_check: bool = False,
    ) -> SMSLog:
        """
        Send an SMS message and log it.

        If Arkesel is configured, the message is dispatched immediately.
        Otherwise it is recorded with PENDING status for later retry or
        manual inspection.

        Args:
            sender_id: Optional override for the sender ID (from school
                       communication settings).
            _skip_limit_check: Internal flag — set by send_bulk() which does
                              a single batch-level check instead.
        """
        if not _skip_limit_check:
            # Check plan SMS limit before sending (raises LimitExceededError if exceeded)
            from app.services.subscription import SubscriptionService
            sub_service = SubscriptionService(self.db)
            await sub_service.check_sms_limit(tenant_id)

        sms_log = SMSLog(
            tenant_id=tenant_id,
            recipient_phone=recipient_phone,
            message=message,
            provider=SMSProvider.ARKESEL,
            status=SMSStatus.PENDING,
        )
        self.db.add(sms_log)
        await self.db.flush()
        await self.db.refresh(sms_log)

        # Attempt delivery via Arkesel when API key is available
        if _sms_client.is_configured:
            result = await _sms_client.send_sms(
                to=recipient_phone,
                message=message,
                sender_id=sender_id,
            )
            if result["success"]:
                sms_log.status = SMSStatus.SENT
                sms_log.external_id = result.get("message_id")
                sms_log.sent_at = datetime.now(UTC)
            else:
                sms_log.status = SMSStatus.FAILED
                sms_log.error_message = result.get("error", "Unknown error")

            await self.db.flush()
            await self.db.refresh(sms_log)
        else:
            # Gateway not configured -- log for visibility
            logger.warning(
                "sms_gateway_not_configured",
                sms_id=str(sms_log.id),
                recipient=recipient_phone,
                provider="arkesel",
            )

        return sms_log

    async def send_bulk(
        self,
        tenant_id: UUID,
        recipients: list[dict],
        message: str,
        provider: SMSProvider = SMSProvider.ARKESEL,
        sender_id: str | None = None,
    ) -> list[SMSLog]:
        """
        Send SMS to multiple recipients, creating a log entry for each.

        Args:
            recipients: List of dicts with at least a 'phone' key and
                        optionally a 'name' key.
            sender_id: Optional override for the sender ID.

        Returns:
            List of SMSLog entries (one per recipient).
        """
        # Pre-check plan SMS limit for the entire batch (avoids partial sends)
        from app.services.subscription import SubscriptionService
        sub_service = SubscriptionService(self.db)
        await sub_service.check_sms_limit(tenant_id, count=len(recipients))

        logs: list[SMSLog] = []

        for recipient in recipients:
            phone = recipient.get("phone")
            if not phone:
                continue

            log_entry = await self.send_sms(
                tenant_id=tenant_id,
                recipient_phone=phone,
                message=message,
                provider=provider,
                sender_id=sender_id,
                _skip_limit_check=True,  # Batch check already done above
            )
            logs.append(log_entry)

        return logs

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

    async def get_stats(self, tenant_id: UUID) -> dict:
        """
        Return aggregate SMS statistics for the tenant.

        Counts are grouped by status so the frontend can display a
        delivery summary.
        """
        # Defense-in-depth: always scope by tenant_id
        stmt = (
            select(SMSLog.status, func.count().label("cnt"))
            .where(SMSLog.tenant_id == tenant_id)
            .group_by(SMSLog.status)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        counts: dict[str, int] = {row.status.value: row.cnt for row in rows}

        # Approximate credit usage: 1 credit per 160-char SMS segment.
        # For accurate billing, use the provider's delivery reports.
        total_messages_stmt = (
            select(func.sum(func.ceil(func.length(SMSLog.message) / 160.0)))
            .where(SMSLog.tenant_id == tenant_id)
            .where(SMSLog.status.in_([SMSStatus.SENT, SMSStatus.DELIVERED]))
        )
        credits_result = await self.db.execute(total_messages_stmt)
        credits_used = int(credits_result.scalar() or 0)

        return {
            "total_sent": counts.get("sent", 0),
            "total_delivered": counts.get("delivered", 0),
            "total_failed": counts.get("failed", 0),
            "total_pending": counts.get("pending", 0),
            "credits_used": credits_used,
        }
