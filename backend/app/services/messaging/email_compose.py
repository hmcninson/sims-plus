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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_log import EmailLog, EmailStatus
from app.models.school import School
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

    async def _get_branded_body(
        self,
        body: str,
        tenant_id: UUID,
        school_id: UUID | None,
    ) -> str:
        """
        Wrap the raw email body in the branded base template.

        Fetches school branding (name, logo, primary color) from the
        database and passes it to the email service's template renderer.
        Falls back to the raw body if the school lookup fails or if
        school_id is not provided.
        """
        if not school_id:
            return body

        try:
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            result = await self.db.execute(
                select(School)
                .where(School.tenant_id == tenant_id)
                .where(School.id == school_id)
                .where(School.deleted_at.is_(None))
            )
            school = result.scalar_one_or_none()
            if not school:
                return body

            return email_service.render_branded_email(
                body_html=body,
                school_name=school.name,
                school_logo_url=school.logo_url,
                school_primary_color=school.primary_color,
            )
        except Exception:
            logger.warning(
                "branded_email_fallback",
                tenant_id=str(tenant_id),
                school_id=str(school_id),
                exc_info=True,
            )
            return body

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

        The body is wrapped in the branded base template before sending,
        so all outgoing emails include consistent school branding. The
        raw body is stored in the log for auditability.
        """
        # Wrap body in branded template for the actual email delivery
        branded_body = await self._get_branded_body(body, tenant_id, school_id)

        log_entry = EmailLog(
            tenant_id=tenant_id,
            school_id=school_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            # Store the raw body in the log for simpler audit review
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
                html_content=branded_body,
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

        Fetches school branding once and reuses it for all recipients to
        avoid repeated database lookups.

        Args:
            recipients: List of dicts with at least an 'email' key and
                        optionally a 'name' key.

        Returns:
            List of EmailLog entries (one per recipient).
        """
        # Pre-compute the branded body once for all recipients
        branded_body = await self._get_branded_body(body, tenant_id, school_id)

        logs: list[EmailLog] = []

        for recipient in recipients:
            email_addr = recipient.get("email")
            if not email_addr:
                continue

            log_entry = await self._send_email_with_branded_body(
                tenant_id=tenant_id,
                school_id=school_id,
                recipient_email=email_addr,
                recipient_name=recipient.get("name"),
                subject=subject,
                raw_body=body,
                branded_body=branded_body,
                sent_by=sent_by,
            )
            logs.append(log_entry)

        return logs

    async def _send_email_with_branded_body(
        self,
        tenant_id: UUID,
        school_id: UUID | None,
        recipient_email: str,
        recipient_name: str | None,
        subject: str,
        raw_body: str,
        branded_body: str,
        sent_by: UUID | None = None,
    ) -> EmailLog:
        """
        Internal helper: send an email using a pre-computed branded body.

        Used by send_bulk to avoid re-querying school branding per recipient.
        """
        log_entry = EmailLog(
            tenant_id=tenant_id,
            school_id=school_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body=raw_body,
            status=EmailStatus.PENDING,
            sent_by=sent_by,
        )
        self.db.add(log_entry)
        await self.db.flush()

        try:
            success = await email_service.send_email(
                to_email=recipient_email,
                subject=subject,
                html_content=branded_body,
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
