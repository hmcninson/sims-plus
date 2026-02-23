"""
SIMS Plus - Email Compose Service

Composes and sends admin-initiated emails, then persists a log entry
in the email_log table for audit trail and delivery tracking.

Uses the singleton email_service from app.services.email for actual SMTP
delivery, so all transport configuration (SMTP host, TLS, dev-mode
logging) is handled there.
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_log import EmailLog, EmailStatus
from app.services.email import email_service

logger = structlog.get_logger()


class EmailComposeError(Exception):
    """Email composition or send failed."""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)


class EmailComposeService:
    """Compose, send, and log outbound emails."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_email(
        self,
        tenant_id: UUID,
        school_id: UUID | None,
        recipient_email: str,
        recipient_name: str | None,
        subject: str,
        body: str,
        sent_by: UUID | None = None,
    ) -> EmailLog:
        """
        Send a single email and create a log record.

        The SMTP delivery is attempted first; the log status reflects
        whether the send succeeded or failed. In development mode the
        email service may skip actual delivery and still return True.
        """
        log_entry = EmailLog(
            tenant_id=tenant_id,
            school_id=school_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body=body,
            status=EmailStatus.PENDING,
            sent_by=sent_by,
        )
        self.db.add(log_entry)
        await self.db.flush()

        # Attempt SMTP delivery via the shared email service
        try:
            success = await email_service.send_email(
                to_email=recipient_email,
                subject=subject,
                html_content=body,
            )
            if success:
                log_entry.status = EmailStatus.SENT
                log_entry.sent_at = datetime.now(UTC)
            else:
                log_entry.status = EmailStatus.FAILED
                log_entry.error_message = "SMTP delivery returned failure"
        except Exception:
            logger.exception(
                "email_compose_send_failed",
                recipient=recipient_email,
                tenant_id=str(tenant_id),
            )
            log_entry.status = EmailStatus.FAILED
            log_entry.error_message = "Email delivery failed"

        await self.db.flush()
        await self.db.refresh(log_entry)

        logger.info(
            "email_composed",
            log_id=str(log_entry.id),
            recipient=recipient_email,
            status=log_entry.status.value,
        )

        return log_entry

    async def send_bulk(
        self,
        tenant_id: UUID,
        school_id: UUID | None,
        recipients: list[dict],
        subject: str,
        body: str,
        sent_by: UUID | None = None,
    ) -> list[EmailLog]:
        """
        Send emails to multiple recipients, creating a log entry for each.

        Args:
            recipients: List of dicts with at least an 'email' key and
                        optionally a 'name' key.

        Returns:
            List of EmailLog entries (one per recipient).
        """
        logs: list[EmailLog] = []

        for recipient in recipients:
            email_addr = recipient.get("email")
            if not email_addr:
                continue

            log_entry = await self.send_email(
                tenant_id=tenant_id,
                school_id=school_id,
                recipient_email=email_addr,
                recipient_name=recipient.get("name"),
                subject=subject,
                body=body,
                sent_by=sent_by,
            )
            logs.append(log_entry)

        return logs
