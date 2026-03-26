"""
SIMS Plus - Admission Notification Service

Sends SMS and email notifications to applicant guardians.
Uses ArkeselClient and EmailComposeService directly (NOT NotificationDispatcher,
which requires a user_id -- applicants don't have platform accounts).

All templates use string.Template.safe_substitute() for variable expansion.
This is deliberately chosen over str.format() to prevent KeyError on missing
variables and to eliminate any risk of format string injection.
"""

import uuid
from string import Template as StringTemplate

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import Application, ApplicationGuardian

logger = structlog.get_logger(__name__)

# Notification templates — use $variable syntax for safe_substitute()
TEMPLATES: dict[str, dict[str, str]] = {
    "submitted": {
        "sms": (
            "Your application to $school has been received. "
            "Tracking code: $tracking_code. Keep this code to check your application status."
        ),
        "email_subject": "Application Received -- $school",
        "email_body": (
            "Dear $guardian_name,\n\n"
            "Your application for $applicant_name to $school has been received successfully.\n\n"
            "Tracking Code: $tracking_code\n\n"
            "You can check the application status at any time using this tracking code "
            "at $status_url.\n\n"
            "Thank you for your interest in $school.\n"
        ),
    },
    "exam_scheduled": {
        "sms": (
            "Entrance exam for $applicant_name at $school: $exam_date at $venue. "
            "Please arrive 30 minutes early."
        ),
        "email_subject": "Entrance Exam Scheduled -- $school",
        "email_body": (
            "Dear $guardian_name,\n\n"
            "An entrance exam has been scheduled for $applicant_name's application to $school.\n\n"
            "Date: $exam_date\n"
            "Time: $exam_time\n"
            "Venue: $venue\n\n"
            "Please ensure the candidate arrives at least 30 minutes before the exam.\n\n"
            "Tracking Code: $tracking_code\n"
        ),
    },
    "offered": {
        "sms": (
            "Congratulations! $applicant_name has been offered admission to $school. "
            "Please respond by $deadline. Check status with code: $tracking_code"
        ),
        "email_subject": "Admission Offer -- $school",
        "email_body": (
            "Dear $guardian_name,\n\n"
            "We are pleased to inform you that $applicant_name has been offered "
            "admission to $school.\n\n"
            "Please respond to this offer by $deadline.\n\n"
            "To accept or for more details, please contact the school or check "
            "your application status using tracking code: $tracking_code\n\n"
            "Congratulations!\n"
        ),
    },
    "enrolled": {
        "sms": (
            "Welcome! $applicant_name is now enrolled at $school. "
            "Student ID: $student_id. Check your email for next steps."
        ),
        "email_subject": "Enrollment Confirmed -- Welcome to $school!",
        "email_body": (
            "Dear $guardian_name,\n\n"
            "$applicant_name has been successfully enrolled at $school.\n\n"
            "Student ID: $student_id\n\n"
            "Next steps:\n"
            "1. Complete any outstanding fee payments\n"
            "2. Submit required documents if not already done\n"
            "3. Check the school portal for orientation details\n\n"
            "Welcome to the $school family!\n"
        ),
    },
    "rejected": {
        "sms": (
            "We regret to inform you that $applicant_name's application to $school "
            "was not successful. Contact the school for more information."
        ),
        "email_subject": "Application Update -- $school",
        "email_body": (
            "Dear $guardian_name,\n\n"
            "We regret to inform you that $applicant_name's application to $school "
            "was not successful at this time.\n\n"
            "For more information, please contact the school administration.\n\n"
            "Thank you for your interest in $school.\n"
        ),
    },
}


class AdmissionNotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_status_change(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: str,
        extra_context: dict | None = None,
    ) -> None:
        """
        Send notification to primary guardian on status change.

        Only sends for statuses that have templates defined.
        Failures are logged but do not raise -- notifications are best effort
        and must never block the primary workflow.
        """
        template = TEMPLATES.get(new_status)
        if not template:
            return  # No notification for this status

        # Get application
        app_result = await self.db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if not app:
            return

        # Get primary guardian, with fallback to first guardian
        guardian = await self._get_primary_guardian(tenant_id, application_id)
        if not guardian:
            logger.warning(
                "no_guardian_for_notification",
                application_id=str(application_id),
            )
            return

        # Build template context from application and guardian data
        context = {
            "school": "the school",
            "applicant_name": f"{app.applicant_first_name} {app.applicant_last_name}",
            "guardian_name": f"{guardian.first_name} {guardian.last_name}",
            "tracking_code": app.tracking_code,
            "status_url": "https://apply.simsplus.io/status",
            **(extra_context or {}),
        }

        # Fetch school name for the notification
        try:
            from app.models.school import School

            school_result = await self.db.execute(
                select(School.name).where(
                    School.id == app.school_id,
                    School.tenant_id == tenant_id,
                )
            )
            school_name = school_result.scalar_one_or_none()
            if school_name:
                context["school"] = school_name
        except Exception:
            logger.warning("school_name_lookup_failed")

        # Send SMS (best effort)
        if guardian.phone:
            await self._send_sms(
                tenant_id=tenant_id,
                school_id=app.school_id,
                phone=guardian.phone,
                template_text=template["sms"],
                context=context,
                application_id=application_id,
            )

        # Send email (best effort)
        if guardian.email:
            await self._send_email(
                tenant_id=tenant_id,
                school_id=app.school_id,
                email=guardian.email,
                recipient_name=f"{guardian.first_name} {guardian.last_name}",
                subject_template=template["email_subject"],
                body_template=template["email_body"],
                context=context,
                application_id=application_id,
            )

    async def send_direct(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        phone: str | None,
        email: str | None,
        recipient_name: str,
        message: str,
    ) -> None:
        """
        Send a direct notification to a phone/email.
        Used by campaign services that build their own message content.
        """
        if phone:
            await self._send_sms_raw(
                tenant_id=tenant_id,
                school_id=school_id,
                phone=phone,
                message=message[:160],
            )

        if email:
            await self._send_email_raw(
                tenant_id=tenant_id,
                school_id=school_id,
                email=email,
                recipient_name=recipient_name,
                subject="SIMS Plus Notification",
                body=message,
            )

    # ---- Private helpers ----

    async def _get_primary_guardian(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> ApplicationGuardian | None:
        """Get primary guardian, with fallback to first guardian."""
        # Try primary guardian first
        result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.is_primary.is_(True),
            )
        )
        guardian = result.scalar_one_or_none()
        if guardian:
            return guardian

        # Fallback: get first guardian
        result = await self.db.execute(
            select(ApplicationGuardian)
            .where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _send_sms(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        phone: str,
        template_text: str,
        context: dict,
        application_id: uuid.UUID,
    ) -> None:
        """Render template and send SMS. Best effort -- never raises."""
        try:
            sms_text = StringTemplate(template_text).safe_substitute(context)
            await self._send_sms_raw(
                tenant_id=tenant_id,
                school_id=school_id,
                phone=phone,
                message=sms_text[:160],
            )
        except Exception:
            logger.exception(
                "admission_sms_failed",
                application_id=str(application_id),
            )

    async def _send_sms_raw(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        phone: str,
        message: str,
    ) -> None:
        """Send a raw SMS message via Arkesel. Raises on failure."""
        from app.services.messaging.arkesel_client import ArkeselClient

        client = ArkeselClient()
        await client.send_sms(to=phone, message=message)

    async def _send_email(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        email: str,
        recipient_name: str,
        subject_template: str,
        body_template: str,
        context: dict,
        application_id: uuid.UUID,
    ) -> None:
        """Render template and send email. Best effort -- never raises."""
        try:
            subject = StringTemplate(subject_template).safe_substitute(context)
            body = StringTemplate(body_template).safe_substitute(context)
            await self._send_email_raw(
                tenant_id=tenant_id,
                school_id=school_id,
                email=email,
                recipient_name=recipient_name,
                subject=subject,
                body=body,
            )
        except Exception:
            logger.exception(
                "admission_email_failed",
                application_id=str(application_id),
            )

    async def _send_email_raw(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        email: str,
        recipient_name: str,
        subject: str,
        body: str,
    ) -> None:
        """Send a raw email via EmailComposeService. Raises on failure."""
        from app.services.messaging.email_compose import EmailComposeService

        email_service = EmailComposeService(self.db)
        await email_service.send_email(
            tenant_id=tenant_id,
            school_id=school_id,
            recipient_email=email,
            recipient_name=recipient_name,
            subject=subject,
            body=body,
            sent_by=None,
        )
