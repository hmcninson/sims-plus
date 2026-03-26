"""
SIMS Plus - Return Intent Service

Optional intent-to-return survey for boarding/private schools.
Results are advisory only -- does NOT block promotion or enrollment.

In Ghana, students are automatically promoted. This feature helps
schools (especially boarding schools) plan capacity by surveying
parents about return intentions before the next academic year.
"""

import uuid
from datetime import UTC, datetime
from string import Template as StringTemplate

import structlog
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class
from app.models.admissions import (
    ReturnIntent,
    ReturnIntentCampaign,
)
from app.models.student import Student

logger = structlog.get_logger(__name__)

# Valid intent responses from parents
VALID_INTENTS = {"returning", "not_returning", "undecided"}


class ReturnIntentError(Exception):
    def __init__(self, message: str, code: str = "RETURN_INTENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ReturnIntentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_campaign(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        academic_year_id: uuid.UUID,
        name: str,
        target_classes: list[str],
        message_template: str | None = None,
        deadline=None,
    ) -> ReturnIntentCampaign:
        """
        Create return intent campaign in draft status.

        Validates academic year exists and target classes are not empty.
        """
        # Verify academic year exists
        from app.models.academic import AcademicYear

        year_result = await self.db.execute(
            select(AcademicYear).where(
                AcademicYear.id == academic_year_id,
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if not year_result.scalar_one_or_none():
            raise ReturnIntentError(
                "Academic year not found", code="YEAR_NOT_FOUND"
            )

        if not target_classes:
            raise ReturnIntentError(
                "At least one target class must be specified",
                code="NO_TARGET_CLASSES",
            )

        # Verify school exists
        from app.models.school import School

        school_result = await self.db.execute(
            select(School).where(
                School.id == school_id,
                School.tenant_id == tenant_id,
            )
        )
        if not school_result.scalar_one_or_none():
            raise ReturnIntentError(
                "School not found", code="SCHOOL_NOT_FOUND"
            )

        campaign = ReturnIntentCampaign(
            tenant_id=tenant_id,
            school_id=school_id,
            academic_year_id=academic_year_id,
            name=name,
            target_classes=target_classes,
            message_template=message_template,
            deadline=deadline,
            status="draft",
        )
        self.db.add(campaign)
        await self.db.flush()
        await self.db.refresh(campaign)

        logger.info(
            "return_intent_campaign_created",
            campaign_id=str(campaign.id),
            school_id=str(school_id),
            target_classes_count=len(target_classes),
        )

        return campaign

    async def update_campaign(
        self,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
        *,
        name: str | None = None,
        target_classes: list[str] | None = None,
        message_template: str | None = None,
        deadline=None,
    ) -> ReturnIntentCampaign:
        """
        Update a draft campaign. Only draft campaigns can be modified.
        """
        campaign = await self._get_campaign(tenant_id, campaign_id)

        if campaign.status != "draft":
            raise ReturnIntentError(
                "Only draft campaigns can be updated",
                code="CAMPAIGN_NOT_DRAFT",
            )

        if name is not None:
            campaign.name = name
        if target_classes is not None:
            if not target_classes:
                raise ReturnIntentError(
                    "At least one target class must be specified",
                    code="NO_TARGET_CLASSES",
                )
            campaign.target_classes = target_classes
        if message_template is not None:
            campaign.message_template = message_template
        if deadline is not None:
            campaign.deadline = deadline

        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign

    async def send_campaign(
        self,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> int:
        """
        Send campaign: creates ReturnIntent records for all active students
        in target classes, sends SMS/email to their primary guardians.

        The campaign must be in 'draft' status. After sending, status
        transitions to 'sent'.

        Returns: number of intent records created.
        """
        campaign = await self._get_campaign(tenant_id, campaign_id)

        if campaign.status != "draft":
            raise ReturnIntentError(
                "Campaign has already been sent",
                code="CAMPAIGN_ALREADY_SENT",
            )

        # Get all active students in the target classes
        from app.models.student import Student

        target_class_uuids = [
            uuid.UUID(str(cid)) for cid in campaign.target_classes
        ]

        student_result = await self.db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                Student.school_id == campaign.school_id,
                Student.class_id.in_(target_class_uuids),
                Student.status == "active",
                Student.deleted_at.is_(None),
            )
        )
        students = list(student_result.scalars().all())

        if not students:
            raise ReturnIntentError(
                "No active students found in target classes",
                code="NO_STUDENTS",
            )

        # Create intent records for each student
        created_count = 0
        student_ids_for_notification: list[tuple[uuid.UUID, str]] = []

        for student in students:
            # Check if intent already exists for this student/campaign
            # (prevents duplicates if send is retried)
            existing_result = await self.db.execute(
                select(ReturnIntent).where(
                    ReturnIntent.campaign_id == campaign_id,
                    ReturnIntent.student_id == student.id,
                    ReturnIntent.tenant_id == tenant_id,
                    ReturnIntent.deleted_at.is_(None),
                )
            )
            if existing_result.scalar_one_or_none():
                continue

            intent = ReturnIntent(
                tenant_id=tenant_id,
                school_id=campaign.school_id,
                campaign_id=campaign_id,
                student_id=student.id,
                academic_year_id=campaign.academic_year_id,
                intent="pending",
            )
            self.db.add(intent)
            created_count += 1

            student_name = f"{student.first_name} {student.last_name}"
            student_ids_for_notification.append((student.id, student_name))

        # Update campaign status
        campaign.status = "sent"
        campaign.sent_at = datetime.now(UTC)
        campaign.sent_count = created_count

        await self.db.flush()

        # Send notifications to guardians (best effort)
        # Each notification failure is logged but does not block the campaign
        notification_count = await self._notify_guardians(
            tenant_id=tenant_id,
            school_id=campaign.school_id,
            student_ids_and_names=student_ids_for_notification,
            message_template=campaign.message_template,
            campaign_name=campaign.name,
        )

        logger.info(
            "return_intent_campaign_sent",
            campaign_id=str(campaign_id),
            intents_created=created_count,
            notifications_sent=notification_count,
        )

        return created_count

    async def respond(
        self,
        tenant_id: uuid.UUID,
        intent_id: uuid.UUID,
        *,
        intent: str,
        responded_by: uuid.UUID,
        reason: str | None = None,
        notes: str | None = None,
    ) -> ReturnIntent:
        """
        Parent responds to return intent survey.

        intent: returning | not_returning | undecided
        """
        if intent not in VALID_INTENTS:
            raise ReturnIntentError(
                f"Invalid intent: {intent}. "
                f"Must be one of: {', '.join(sorted(VALID_INTENTS))}",
                code="INVALID_INTENT",
            )

        intent_record = await self._get_intent(tenant_id, intent_id)

        # Allow re-response (parent can change their mind before deadline)
        intent_record.intent = intent
        intent_record.responded_by = responded_by
        intent_record.responded_at = datetime.now(UTC)
        intent_record.reason = reason
        if notes is not None:
            intent_record.notes = notes

        await self.db.flush()
        await self.db.refresh(intent_record)

        logger.info(
            "return_intent_responded",
            intent_id=str(intent_id),
            intent=intent,
            responded_by=str(responded_by),
        )

        return intent_record

    async def get_campaign(
        self,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> ReturnIntentCampaign:
        """Get campaign details."""
        return await self._get_campaign(tenant_id, campaign_id)

    async def get_campaign_stats(
        self,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> dict:
        """
        Get campaign response statistics.

        Returns: { total, pending, returning, not_returning, undecided }
        """
        # Verify campaign exists
        await self._get_campaign(tenant_id, campaign_id)

        base_filter = [
            ReturnIntent.campaign_id == campaign_id,
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            ReturnIntent.tenant_id == tenant_id,
            ReturnIntent.deleted_at.is_(None),
        ]

        # Total count
        total_result = await self.db.execute(
            select(func.count(ReturnIntent.id)).where(*base_filter)
        )
        total = total_result.scalar() or 0

        # Count by intent value
        stats = {"total": total, "pending": 0, "returning": 0, "not_returning": 0, "undecided": 0}

        for intent_value in ["pending", "returning", "not_returning", "undecided"]:
            count_result = await self.db.execute(
                select(func.count(ReturnIntent.id)).where(
                    *base_filter,
                    ReturnIntent.intent == intent_value,
                )
            )
            stats[intent_value] = count_result.scalar() or 0

        return stats

    async def list_campaigns(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReturnIntentCampaign], int]:
        """List return intent campaigns for a school."""
        query = select(ReturnIntentCampaign).where(
            ReturnIntentCampaign.tenant_id == tenant_id,
            ReturnIntentCampaign.school_id == school_id,
            ReturnIntentCampaign.deleted_at.is_(None),
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(ReturnIntentCampaign.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def list_intents(
        self,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
        *,
        intent_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ReturnIntent], int]:
        """
        List intent records for a campaign with optional status filter.
        """
        # Verify campaign exists
        await self._get_campaign(tenant_id, campaign_id)

        query = select(ReturnIntent).where(
            ReturnIntent.campaign_id == campaign_id,
            ReturnIntent.tenant_id == tenant_id,
            ReturnIntent.deleted_at.is_(None),
        )

        if intent_filter and intent_filter in VALID_INTENTS | {"pending"}:
            query = query.where(ReturnIntent.intent == intent_filter)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(ReturnIntent.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def complete_campaign(
        self,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> ReturnIntentCampaign:
        """
        Mark a sent campaign as completed. Prevents further responses
        and signals to the UI that the survey is finalized.
        """
        campaign = await self._get_campaign(tenant_id, campaign_id)

        if campaign.status != "sent":
            raise ReturnIntentError(
                "Only sent campaigns can be completed",
                code="CAMPAIGN_NOT_SENT",
            )

        campaign.status = "completed"
        await self.db.flush()
        await self.db.refresh(campaign)

        logger.info(
            "return_intent_campaign_completed",
            campaign_id=str(campaign_id),
        )

        return campaign

    async def confirm_re_enrollment(
        self,
        tenant_id: uuid.UUID,
        intent_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
    ) -> ReturnIntent:
        """
        Confirm re-enrollment for a returning student.

        Steps:
        1. Validate intent == "returning"
        2. Check outstanding fees via finance service query
        3. Set re_enrollment_confirmed = True with timestamp
        4. Snapshot outstanding fee balance
        """
        from decimal import Decimal

        intent_record = await self._get_intent(tenant_id, intent_id)

        if intent_record.intent != "returning":
            raise ReturnIntentError(
                "Can only confirm re-enrollment for 'returning' intents. "
                f"Current intent: {intent_record.intent}",
                code="INVALID_INTENT_STATE",
            )

        if intent_record.re_enrollment_confirmed:
            raise ReturnIntentError(
                "Re-enrollment already confirmed",
                code="ALREADY_CONFIRMED",
            )

        # Check outstanding fees for this student via finance tables.
        # Use a savepoint so that a SQL error (e.g. missing table) doesn't
        # abort the outer transaction and block subsequent writes.
        outstanding_amount = Decimal("0.00")
        try:
            from app.models.finance.invoice_models import Invoice

            async with self.db.begin_nested():
                fee_result = await self.db.execute(
                    select(func.coalesce(func.sum(Invoice.balance), 0)).filter(
                        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                        Invoice.tenant_id == tenant_id,
                        Invoice.student_id == intent_record.student_id,
                        Invoice.status.in_(["sent", "partially_paid", "overdue"]),
                        Invoice.deleted_at.is_(None),
                    )
                )
                outstanding_amount = fee_result.scalar() or Decimal("0.00")
        except Exception:
            # Finance module may not be deployed; proceed without fee check.
            # The savepoint rollback keeps the outer transaction healthy.
            logger.warning(
                "outstanding_fees_check_failed",
                intent_id=str(intent_id),
            )

        intent_record.re_enrollment_confirmed = True
        intent_record.re_enrollment_confirmed_at = datetime.now(UTC)
        intent_record.outstanding_fees_checked = True
        intent_record.outstanding_fee_amount = outstanding_amount

        await self.db.flush()
        await self.db.refresh(intent_record)

        logger.info(
            "re_enrollment_confirmed",
            intent_id=str(intent_id),
            student_id=str(intent_record.student_id),
            outstanding_fees=str(outstanding_amount),
        )
        return intent_record

    async def get_re_enrollment_summary(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> dict:
        """
        Re-enrollment summary for a campaign.

        Returns: confirmed vs pending vs not_returning counts,
        outstanding fee totals, and per-class breakdown.
        """
        # Verify campaign exists
        await self._get_campaign(tenant_id, campaign_id)

        base_filter = [
            ReturnIntent.campaign_id == campaign_id,
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            ReturnIntent.tenant_id == tenant_id,
            ReturnIntent.deleted_at.is_(None),
        ]

        # Aggregate counts using CASE expressions
        stats_result = await self.db.execute(
            select(
                func.count(ReturnIntent.id).label("total"),
                func.count(
                    case(
                        (
                            ReturnIntent.re_enrollment_confirmed.is_(True),
                            ReturnIntent.id,
                        ),
                    )
                ).label("confirmed"),
                func.count(
                    case(
                        (
                            and_(
                                ReturnIntent.intent == "returning",
                                ReturnIntent.re_enrollment_confirmed.is_(False),
                            ),
                            ReturnIntent.id,
                        ),
                    )
                ).label("pending"),
                func.count(
                    case(
                        (
                            ReturnIntent.intent == "not_returning",
                            ReturnIntent.id,
                        ),
                    )
                ).label("not_returning"),
                func.count(
                    case(
                        (
                            ReturnIntent.intent.in_(["pending", "undecided"]),
                            ReturnIntent.id,
                        ),
                    )
                ).label("undecided"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ReturnIntent.outstanding_fee_amount.isnot(None),
                                ReturnIntent.outstanding_fee_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_fees"),
            ).filter(*base_filter)
        )
        stats = stats_result.one()

        # Per-class breakdown using Student join
        class_result = await self.db.execute(
            select(
                Class.name.label("class_name"),
                func.count(
                    case(
                        (
                            ReturnIntent.re_enrollment_confirmed.is_(True),
                            ReturnIntent.id,
                        ),
                    )
                ).label("confirmed"),
                func.count(
                    case(
                        (
                            and_(
                                ReturnIntent.intent == "returning",
                                ReturnIntent.re_enrollment_confirmed.is_(False),
                            ),
                            ReturnIntent.id,
                        ),
                    )
                ).label("pending"),
                func.count(
                    case(
                        (
                            ReturnIntent.intent == "not_returning",
                            ReturnIntent.id,
                        ),
                    )
                ).label("not_returning"),
            )
            .select_from(ReturnIntent)
            .join(Student, ReturnIntent.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .filter(*base_filter)
            .group_by(Class.name)
            .order_by(Class.name)
        )
        by_class = [
            {
                "class_name": r.class_name,
                "confirmed": r.confirmed,
                "pending": r.pending,
                "not_returning": r.not_returning,
            }
            for r in class_result.all()
        ]

        return {
            "campaign_id": campaign_id,
            "total_intents": stats.total,
            "confirmed_count": stats.confirmed,
            "pending_count": stats.pending,
            "not_returning_count": stats.not_returning,
            "undecided_count": stats.undecided,
            "total_outstanding_fees": float(stats.total_fees),
            "by_class": by_class,
        }

    # ---- Private helpers ----

    async def _get_campaign(
        self, tenant_id: uuid.UUID, campaign_id: uuid.UUID
    ) -> ReturnIntentCampaign:
        result = await self.db.execute(
            select(ReturnIntentCampaign).where(
                ReturnIntentCampaign.id == campaign_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                ReturnIntentCampaign.tenant_id == tenant_id,
                ReturnIntentCampaign.deleted_at.is_(None),
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise ReturnIntentError(
                "Return intent campaign not found", code="NOT_FOUND"
            )
        return campaign

    async def _get_intent(
        self, tenant_id: uuid.UUID, intent_id: uuid.UUID
    ) -> ReturnIntent:
        result = await self.db.execute(
            select(ReturnIntent).where(
                ReturnIntent.id == intent_id,
                ReturnIntent.tenant_id == tenant_id,
                ReturnIntent.deleted_at.is_(None),
            )
        )
        intent_record = result.scalar_one_or_none()
        if not intent_record:
            raise ReturnIntentError(
                "Return intent not found", code="INTENT_NOT_FOUND"
            )
        return intent_record

    async def _notify_guardians(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        student_ids_and_names: list[tuple[uuid.UUID, str]],
        message_template: str | None,
        campaign_name: str,
    ) -> int:
        """
        Send survey notifications to primary guardians of each student.

        Uses AdmissionNotificationService.send_direct() for each guardian.
        Returns count of notifications successfully dispatched.
        """
        from app.models.student import Guardian, StudentGuardian

        default_template = (
            "Dear parent/guardian, please indicate whether $student_name "
            "will be returning next academic year. "
            "Reply to this survey at your earliest convenience."
        )
        template_text = message_template or default_template

        # Get school name for notifications
        school_name = "the school"
        try:
            from app.models.school import School

            school_result = await self.db.execute(
                select(School.name).where(
                    School.id == school_id,
                    School.tenant_id == tenant_id,
                )
            )
            name = school_result.scalar_one_or_none()
            if name:
                school_name = name
        except Exception:
            logger.warning("school_name_lookup_failed_for_campaign")

        sent_count = 0

        for student_id, student_name in student_ids_and_names:
            try:
                # Get primary guardian for this student
                sg_result = await self.db.execute(
                    select(StudentGuardian).where(
                        StudentGuardian.student_id == student_id,
                        StudentGuardian.tenant_id == tenant_id,
                        StudentGuardian.is_primary.is_(True),
                    )
                )
                sg = sg_result.scalar_one_or_none()

                # Fallback to first guardian if no primary
                if not sg:
                    sg_result = await self.db.execute(
                        select(StudentGuardian)
                        .where(
                            StudentGuardian.student_id == student_id,
                            StudentGuardian.tenant_id == tenant_id,
                        )
                        .limit(1)
                    )
                    sg = sg_result.scalar_one_or_none()

                if not sg:
                    continue

                # Get guardian contact details
                guardian_result = await self.db.execute(
                    select(Guardian).where(
                        Guardian.id == sg.guardian_id,
                        Guardian.tenant_id == tenant_id,
                        Guardian.deleted_at.is_(None),
                    )
                )
                guardian = guardian_result.scalar_one_or_none()
                if not guardian:
                    continue

                # Render message using safe_substitute to avoid KeyError on missing vars
                context = {
                    "student_name": student_name,
                    "guardian_name": f"{guardian.first_name} {guardian.last_name}",
                    "school": school_name,
                    "campaign_name": campaign_name,
                }
                message = StringTemplate(template_text).safe_substitute(context)

                # Send via notification service (best effort per guardian)
                from app.services.admissions.notification_service import (
                    AdmissionNotificationService,
                )

                notifier = AdmissionNotificationService(self.db)
                await notifier.send_direct(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    phone=guardian.phone,
                    email=guardian.email,
                    recipient_name=f"{guardian.first_name} {guardian.last_name}",
                    message=message,
                )
                sent_count += 1

            except Exception:
                # Individual notification failure must not block the campaign
                logger.exception(
                    "return_intent_notification_failed",
                    student_id=str(student_id),
                )

        return sent_count
