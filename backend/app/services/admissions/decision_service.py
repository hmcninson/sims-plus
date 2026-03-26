"""
SIMS Plus - Decision Service

Handles admission decisions (accept/reject/waitlist/defer) for
individual and bulk applications, letter generation (PDF via WeasyPrint),
waitlist management, and waitlist promotion.
"""

import re
import uuid
from datetime import date, UTC, datetime
from io import BytesIO
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from weasyprint import HTML

from app.models.academic import Class
from app.models.admissions import (
    AdmissionApplicationStatus,
    AdmissionDecision,
    Application,
    ApplicationStatusHistory,
    DecisionType,
    VALID_TRANSITIONS,
)
from app.models.admissions.period import AdmissionPeriod
from app.models.school import School
from app.services.s3 import get_s3_service

logger = structlog.get_logger(__name__)

# Maps decision type to target application status
_DECISION_STATUS_MAP: dict[str, AdmissionApplicationStatus] = {
    DecisionType.ACCEPTED.value: AdmissionApplicationStatus.OFFERED,
    DecisionType.REJECTED.value: AdmissionApplicationStatus.REJECTED,
    DecisionType.WAITLISTED.value: AdmissionApplicationStatus.WAITLISTED,
    DecisionType.DEFERRED.value: AdmissionApplicationStatus.DEFERRED,
}

# Templates directory for admission letters
_ADMISSIONS_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "admissions"

# Validate hex color to prevent CSS injection in PDF templates (REVIEW FIX H2)
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Safe default school color when the actual color fails validation
_DEFAULT_SCHOOL_COLOR = "#1B4F72"


class DecisionServiceError(Exception):
    def __init__(self, message: str, code: str = "DECISION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class DecisionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def decide(
        self,
        tenant_id: uuid.UUID,
        *,
        application_id: uuid.UUID,
        decision_type: str,
        decided_by: uuid.UUID,
        offered_class_id: uuid.UUID | None = None,
        conditions: str | None = None,
        response_deadline: date | None = None,
    ) -> AdmissionDecision:
        """
        Make admission decision for single application.

        Creates AdmissionDecision record and transitions application status:
          accepted -> OFFERED (with optional response_deadline)
          rejected -> REJECTED
          waitlisted -> WAITLISTED
          deferred -> DEFERRED

        Sends notification to primary guardian after decision.
        """
        # Validate decision type
        try:
            dt = DecisionType(decision_type)
        except ValueError:
            raise DecisionServiceError(
                f"Invalid decision type: {decision_type}. "
                f"Must be one of: {', '.join(d.value for d in DecisionType)}",
                code="INVALID_DECISION_TYPE",
            )

        # Acceptance requires offered_class_id
        if dt == DecisionType.ACCEPTED and not offered_class_id:
            raise DecisionServiceError(
                "offered_class_id is required for acceptance decisions",
                code="MISSING_CLASS",
            )

        # Get application
        app = await self._get_application(tenant_id, application_id)

        # Determine target status from decision type
        target_status = _DECISION_STATUS_MAP[dt.value]

        # Validate the transition is allowed from the current status
        current = AdmissionApplicationStatus(app.status)
        allowed = VALID_TRANSITIONS.get(current, [])
        if target_status not in allowed:
            raise DecisionServiceError(
                f"Cannot transition from {current.value} to {target_status.value}. "
                f"Application must be in a reviewable state.",
                code="INVALID_TRANSITION",
            )

        # Check if a decision already exists
        existing_result = await self.db.execute(
            select(AdmissionDecision).where(
                AdmissionDecision.application_id == application_id,
                AdmissionDecision.tenant_id == tenant_id,
            )
        )
        existing_decision = existing_result.scalar_one_or_none()
        if existing_decision:
            raise DecisionServiceError(
                "A decision has already been made for this application",
                code="DECISION_EXISTS",
            )

        # Create decision record
        decision = AdmissionDecision(
            tenant_id=tenant_id,
            application_id=application_id,
            decision_type=dt.value,
            decided_by=decided_by,
            offered_class_id=offered_class_id,
            conditions=conditions,
            decision_date=date.today(),
            response_deadline=response_deadline,
        )
        self.db.add(decision)

        # Update application status
        old_status = app.status
        app.status = target_status.value

        # Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application_id,
            from_status=old_status,
            to_status=target_status.value,
            changed_by=decided_by,
            reason=f"Decision: {dt.value}" + (f" — {conditions}" if conditions else ""),
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(decision)

        # Send notification (best effort)
        try:
            from app.services.admissions.notification_service import (
                AdmissionNotificationService,
            )

            notifier = AdmissionNotificationService(self.db)
            extra = {}
            if response_deadline:
                extra["deadline"] = response_deadline.strftime("%d/%m/%Y")
            notification_status = (
                "offered" if dt == DecisionType.ACCEPTED else dt.value
            )
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application_id,
                new_status=notification_status,
                extra_context=extra,
            )
        except Exception:
            logger.exception("decision_notification_failed")

        logger.info(
            "admission_decision_made",
            application_id=str(application_id),
            decision_type=dt.value,
            decided_by=str(decided_by),
        )

        return decision

    async def bulk_decide(
        self,
        tenant_id: uuid.UUID,
        *,
        application_ids: list[uuid.UUID],
        decision_type: str,
        decided_by: uuid.UUID,
        offered_class_id: uuid.UUID | None = None,
        conditions: str | None = None,
        response_deadline: date | None = None,
    ) -> dict:
        """
        Bulk decide. Each application is processed in its own savepoint
        for partial success tolerance.

        Returns: { succeeded: [...], failed: [...] }
        """
        succeeded: list[dict] = []
        failed: list[dict] = []

        for app_id in application_ids:
            try:
                async with self.db.begin_nested():
                    decision = await self.decide(
                        tenant_id,
                        application_id=app_id,
                        decision_type=decision_type,
                        decided_by=decided_by,
                        offered_class_id=offered_class_id,
                        conditions=conditions,
                        response_deadline=response_deadline,
                    )
                    succeeded.append({
                        "application_id": str(app_id),
                        "decision_type": decision.decision_type,
                    })
            except Exception as e:
                error_msg = (
                    e.message
                    if isinstance(e, DecisionServiceError)
                    else "Decision failed"
                )
                failed.append({
                    "application_id": str(app_id),
                    "error": error_msg,
                })

        return {"succeeded": succeeded, "failed": failed}

    # ================================================================
    # Letter Generation (Enrollment Gap Closure Phase 2)
    # ================================================================

    async def generate_admission_letter(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
    ) -> str:
        """
        Generate admission letter PDF, upload to S3, and return presigned URL.

        Only valid for decisions with decision_type = 'accepted'.
        Uses WeasyPrint + Jinja2 template from templates/admissions/admission_letter.html.

        S3 key format: admissions/{tenant_id}/letters/{decision_id}_admission.pdf
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.ACCEPTED.value:
            raise DecisionServiceError(
                "Admission letter can only be generated for acceptance decisions",
                code="INVALID_DECISION_TYPE",
            )

        # Load application with admission period -> academic year for template
        app_result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.admission_period).selectinload(
                    AdmissionPeriod.academic_year
                ),
            )
            .filter(
                Application.id == decision.application_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise DecisionServiceError("Application not found", code="NOT_FOUND")

        # Load school branding for letterhead
        school = await self._get_school(tenant_id, application.school_id)

        # Load offered class name for the letter body
        offered_class_name = ""
        if decision.offered_class_id:
            cls_result = await self.db.execute(
                select(Class.name).filter(
                    Class.id == decision.offered_class_id,
                    Class.tenant_id == tenant_id,
                )
            )
            offered_class_name = cls_result.scalar_one_or_none() or ""

        applicant_name = f"{application.applicant_first_name} {application.applicant_last_name}"
        academic_year_name = (
            application.admission_period.academic_year.name
            if application.admission_period and application.admission_period.academic_year
            else ""
        )

        # Validate color and logo URL to prevent CSS/HTML injection (REVIEW FIX H2)
        safe_color = self._safe_color(school.primary_color)
        safe_logo_url = self._safe_logo_url(school.logo_url)

        context = {
            "school": school,
            "school_color": safe_color,
            "safe_logo_url": safe_logo_url,
            "decision": decision,
            "applicant_name": applicant_name,
            "tracking_code": application.tracking_code,
            "offered_class_name": offered_class_name,
            "academic_year_name": academic_year_name,
            "conditions": decision.conditions,
            "response_deadline": decision.response_deadline,
        }

        # Render PDF via shared helper (REVIEW FIX B7)
        pdf_bytes = self._render_pdf("admission_letter.html", context)

        # Upload to S3 -- letters are private (served via presigned URLs)
        s3_key = f"admissions/{tenant_id}/letters/{decision_id}_admission.pdf"
        s3 = get_s3_service()
        s3.upload_file(pdf_bytes, s3_key, "application/pdf")

        # Persist S3 key on decision record for future downloads
        decision.decision_letter_url = s3_key
        await self.db.flush()
        await self.db.refresh(decision)

        # Return presigned URL (1 hour TTL)
        presigned_url = s3.generate_presigned_url(s3_key, expires_in=3600)

        logger.info(
            "admission_letter_generated",
            decision_id=str(decision_id),
            application_id=str(application.id),
        )
        return presigned_url

    async def generate_rejection_letter(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        *,
        rejection_reason: str | None = None,
    ) -> str:
        """
        Generate rejection letter PDF, upload to S3, and return presigned URL.

        Only valid for decisions with decision_type = 'rejected'.
        If rejection_reason is provided, it is persisted on the decision record
        and included in the letter.

        S3 key format: admissions/{tenant_id}/letters/{decision_id}_rejection.pdf
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.REJECTED.value:
            raise DecisionServiceError(
                "Rejection letter can only be generated for rejection decisions",
                code="INVALID_DECISION_TYPE",
            )

        # Persist rejection reason if provided (overwrites previous value)
        if rejection_reason is not None:
            decision.rejection_reason = rejection_reason

        # Load application with admission period -> academic year
        app_result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.admission_period).selectinload(
                    AdmissionPeriod.academic_year
                ),
            )
            .filter(
                Application.id == decision.application_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise DecisionServiceError("Application not found", code="NOT_FOUND")

        school = await self._get_school(tenant_id, application.school_id)

        applicant_name = f"{application.applicant_first_name} {application.applicant_last_name}"
        academic_year_name = (
            application.admission_period.academic_year.name
            if application.admission_period and application.admission_period.academic_year
            else ""
        )

        # Validate color and logo URL (REVIEW FIX H2)
        safe_color = self._safe_color(school.primary_color)
        safe_logo_url = self._safe_logo_url(school.logo_url)

        context = {
            "school": school,
            "school_color": safe_color,
            "safe_logo_url": safe_logo_url,
            "decision": decision,
            "applicant_name": applicant_name,
            "tracking_code": application.tracking_code,
            "academic_year_name": academic_year_name,
            "rejection_reason": decision.rejection_reason,
        }

        pdf_bytes = self._render_pdf("rejection_letter.html", context)

        s3_key = f"admissions/{tenant_id}/letters/{decision_id}_rejection.pdf"
        s3 = get_s3_service()
        s3.upload_file(pdf_bytes, s3_key, "application/pdf")

        decision.rejection_letter_url = s3_key
        await self.db.flush()
        await self.db.refresh(decision)

        presigned_url = s3.generate_presigned_url(s3_key, expires_in=3600)

        logger.info(
            "rejection_letter_generated",
            decision_id=str(decision_id),
            application_id=str(application.id),
        )
        return presigned_url

    # ================================================================
    # Waitlist Management (Enrollment Gap Closure Phase 2)
    # ================================================================

    async def update_waitlist_rank(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        *,
        rank: int,
    ) -> AdmissionDecision:
        """
        Set or update waitlist rank for a single waitlisted decision.

        Uses pg_advisory_xact_lock to prevent concurrent rank updates
        from creating duplicate ranks within the same tenant.
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.WAITLISTED.value:
            raise DecisionServiceError(
                "Waitlist rank can only be set for waitlisted decisions",
                code="INVALID_DECISION_TYPE",
            )

        # Advisory lock scoped to tenant to prevent concurrent rank collisions
        lock_key = hash(f"{tenant_id}_waitlist_rank") & 0x7FFFFFFFFFFFFFFF
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": lock_key},
        )

        decision.waitlist_rank = rank
        await self.db.flush()
        await self.db.refresh(decision)

        logger.info(
            "waitlist_rank_updated",
            decision_id=str(decision_id),
            rank=rank,
        )
        return decision

    async def reorder_waitlist(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        period_id: uuid.UUID,
        ordered_decision_ids: list[uuid.UUID],
    ) -> list[AdmissionDecision]:
        """
        Bulk reorder waitlist by assigning sequential ranks.

        ordered_decision_ids[0] gets rank 1, ordered_decision_ids[1] gets rank 2, etc.
        All decisions must be waitlisted and belong to the specified period.

        Uses pg_advisory_xact_lock to prevent concurrent reorder operations.
        """
        # Advisory lock scoped to tenant + period for concurrency safety
        lock_key = hash(f"{tenant_id}_waitlist_reorder_{period_id}") & 0x7FFFFFFFFFFFFFFF
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": lock_key},
        )

        # Fetch all decisions in the list in one query
        result = await self.db.execute(
            select(AdmissionDecision)
            .join(Application, AdmissionDecision.application_id == Application.id)
            .filter(
                AdmissionDecision.tenant_id == tenant_id,
                AdmissionDecision.id.in_(ordered_decision_ids),
                AdmissionDecision.decision_type == DecisionType.WAITLISTED.value,
                Application.admission_period_id == period_id,
                Application.school_id == school_id,
                # Defense-in-depth: filter by tenant_id on both tables
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        decisions_by_id = {d.id: d for d in result.scalars().all()}

        # Validate all requested IDs were found and are waitlisted in this period
        missing = set(ordered_decision_ids) - set(decisions_by_id.keys())
        if missing:
            raise DecisionServiceError(
                f"Decisions not found or not waitlisted: {[str(m) for m in missing]}",
                code="NOT_FOUND",
            )

        # Assign sequential ranks based on list position
        updated = []
        for rank, decision_id in enumerate(ordered_decision_ids, start=1):
            decision = decisions_by_id[decision_id]
            decision.waitlist_rank = rank
            updated.append(decision)

        await self.db.flush()
        for d in updated:
            await self.db.refresh(d)

        logger.info(
            "waitlist_reordered",
            period_id=str(period_id),
            count=len(updated),
        )
        return updated

    async def promote_from_waitlist(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        *,
        offered_class_id: uuid.UUID,
        response_deadline: date | None = None,
        conditions: str | None = None,
        promoted_by: uuid.UUID,
    ) -> AdmissionDecision:
        """
        Promote a waitlisted applicant to 'offered' status.

        Steps:
        1. Validate decision is waitlisted
        2. Transition application status: WAITLISTED -> OFFERED
        3. Update decision: type = accepted, offered_class_id, clear waitlist fields
        4. Record status history
        5. Send notification to guardian
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.WAITLISTED.value:
            raise DecisionServiceError(
                "Only waitlisted decisions can be promoted",
                code="INVALID_DECISION_TYPE",
            )

        # Get application and validate status transition
        application = await self._get_application(tenant_id, decision.application_id)
        current_status = AdmissionApplicationStatus(application.status)
        target_status = AdmissionApplicationStatus.OFFERED

        allowed = VALID_TRANSITIONS.get(current_status, [])
        if target_status not in allowed:
            raise DecisionServiceError(
                f"Cannot transition application from {current_status.value} to {target_status.value}",
                code="INVALID_TRANSITION",
            )

        # Preserve original rank for status history before clearing
        original_rank = decision.waitlist_rank

        # Update decision fields
        decision.decision_type = DecisionType.ACCEPTED.value
        decision.offered_class_id = offered_class_id
        decision.conditions = conditions
        decision.response_deadline = response_deadline
        # Clear waitlist-specific fields (no longer on waitlist)
        decision.waitlist_rank = None
        decision.waitlist_notes = None

        # Transition application status
        old_status = application.status
        application.status = target_status.value

        # Status history with audit trail of original waitlist position
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application.id,
            from_status=old_status,
            to_status=target_status.value,
            changed_by=promoted_by,
            reason=f"Promoted from waitlist (was rank {original_rank or 'unranked'})",
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(decision)

        # Send notification (best effort)
        try:
            from app.services.admissions.notification_service import (
                AdmissionNotificationService,
            )

            notifier = AdmissionNotificationService(self.db)
            extra = {}
            if response_deadline:
                extra["deadline"] = response_deadline.strftime("%d/%m/%Y")
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application.id,
                new_status="offered",
                extra_context=extra,
            )
        except Exception:
            logger.exception("waitlist_promotion_notification_failed")

        logger.info(
            "waitlist_promoted",
            decision_id=str(decision_id),
            application_id=str(application.id),
            from_rank=original_rank,
        )
        return decision

    async def list_waitlisted(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        period_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        List waitlisted decisions ordered by rank (nulls last).

        Returns dicts with decision + application data for the response schema.
        """
        query = (
            select(AdmissionDecision, Application)
            .join(Application, AdmissionDecision.application_id == Application.id)
            .filter(
                AdmissionDecision.tenant_id == tenant_id,
                AdmissionDecision.decision_type == DecisionType.WAITLISTED.value,
                Application.school_id == school_id,
                # Defense-in-depth: filter by tenant_id on both tables
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )

        if period_id:
            query = query.filter(Application.admission_period_id == period_id)

        # Count total matching rows
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Order: ranked first (ascending), then unranked (nulls last)
        query = query.order_by(
            AdmissionDecision.waitlist_rank.asc().nullslast(),
            AdmissionDecision.created_at.asc(),
        )
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        items = []
        for decision, application in result.all():
            items.append({
                "decision_id": decision.id,
                "application_id": application.id,
                "applicant_name": f"{application.applicant_first_name} {application.applicant_last_name}",
                "tracking_code": application.tracking_code,
                "target_class_name": None,  # Populated by endpoint if needed
                "waitlist_rank": decision.waitlist_rank,
                "waitlist_notes": decision.waitlist_notes,
                "decision_date": decision.decision_date,
                "created_at": decision.created_at,
            })

        return items, total

    # ================================================================
    # Private helpers
    # ================================================================

    async def _get_application(
        self, tenant_id: uuid.UUID, app_id: uuid.UUID
    ) -> Application:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise DecisionServiceError("Application not found", code="NOT_FOUND")
        return app

    async def _get_decision(
        self, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> AdmissionDecision:
        """Get decision by ID with defense-in-depth tenant check."""
        result = await self.db.execute(
            select(AdmissionDecision).filter(
                AdmissionDecision.id == decision_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                AdmissionDecision.tenant_id == tenant_id,
            )
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise DecisionServiceError("Decision not found", code="NOT_FOUND")
        return decision

    async def _get_school(
        self, tenant_id: uuid.UUID, school_id: uuid.UUID
    ) -> School:
        """Get school for template rendering."""
        result = await self.db.execute(
            select(School).filter(
                School.id == school_id,
                School.tenant_id == tenant_id,
            )
        )
        school = result.scalar_one_or_none()
        if not school:
            raise DecisionServiceError("School not found", code="NOT_FOUND")
        return school

    @staticmethod
    def _safe_color(primary_color: str | None) -> str:
        """Validate hex color to prevent CSS injection (REVIEW FIX H2)."""
        if primary_color and _HEX_COLOR_RE.match(primary_color):
            return primary_color
        return _DEFAULT_SCHOOL_COLOR

    @staticmethod
    def _safe_logo_url(logo_url: str | None) -> str | None:
        """Validate logo URL starts with https:// to prevent injection (REVIEW FIX H2)."""
        if logo_url and logo_url.startswith("https://"):
            return logo_url
        return None

    @staticmethod
    def _render_pdf(template_name: str, context: dict) -> bytes:
        """Render a Jinja2 template to PDF bytes using WeasyPrint (REVIEW FIX B7)."""
        env = Environment(
            loader=FileSystemLoader(str(_ADMISSIONS_TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template(template_name)
        html_content = template.render(**context)

        html = HTML(string=html_content)
        pdf_buffer = BytesIO()
        html.write_pdf(pdf_buffer)
        return pdf_buffer.getvalue()
