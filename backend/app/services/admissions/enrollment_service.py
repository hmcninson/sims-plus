"""
SIMS Plus - Enrollment Service

Atomic conversion of accepted applicants into student records.
This is the most critical service in the admissions package -- it touches
6+ tables in one transaction: Application, Student, Guardian,
StudentGuardian, Invoice (optional), ApplicationStatusHistory.

Guardian deduplication: matches by email OR phone within the same tenant
to prevent duplicate guardian entries when siblings apply.

Idempotency: if converted_student_id is already set, the enrollment
endpoint returns the existing student rather than creating a duplicate.

Phase 3 additions:
- Enrollment checklist management (create, get, complete items)
- Enrollment deposit recording
- Boarding status assignment
- Enrollment confirmation PDF generation
- Welcome pack dispatch
"""

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from weasyprint import HTML

from app.models.admissions import (
    AdmissionDecision,
    AdmissionPeriod,
    Application,
    ApplicationGuardian,
    ApplicationStatusHistory,
    AdmissionApplicationStatus,
)
from app.models.admissions.enrollment_checklist import (
    EnrollmentChecklist,
    EnrollmentChecklistItem,
)

logger = structlog.get_logger(__name__)

# Fields that must never be set via dynamic attribute assignment
PROTECTED_FIELDS = frozenset({
    "id", "tenant_id", "school_id", "created_at", "updated_at", "deleted_at",
})

# Templates directory for enrollment confirmation letters
_ADMISSIONS_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "admissions"

# Validate hex color to prevent CSS injection in PDF templates (REVIEW FIX H2)
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Safe default school color when the actual color fails validation
_DEFAULT_SCHOOL_COLOR = "#1B4F72"

# Boarding-specific checklist items added when boarding_status == "boarding"
_BOARDING_CHECKLIST_ITEMS = [
    {"item_type": "boarding", "item_name": "Boarding fee paid", "is_required": True},
    {"item_type": "boarding", "item_name": "Dormitory preference submitted", "is_required": False},
    {"item_type": "medical", "item_name": "Boarding medical clearance", "is_required": True},
    {"item_type": "document", "item_name": "Boarding agreement signed", "is_required": True},
]


class EnrollmentError(Exception):
    def __init__(self, message: str, code: str = "ENROLLMENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EnrollmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def enroll(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_id: uuid.UUID,
        enrolled_by: uuid.UUID,
    ) -> dict:
        """
        Convert accepted applicant to student record.

        Steps:
        1. Validate application status=ACCEPTED, converted_student_id=NULL
        2. Determine class (use decision's offered_class if available)
        3. Deduplicate guardians (by email OR phone within tenant)
        4. Create Student record with auto-generated student_id
        5. Create StudentGuardian junction records
        6. Generate first invoice (if fee structure exists for the class)
        7. Update application status=ENROLLED + set converted_student_id
        8. Log status change in history
        9. Send enrollment notification (best effort)
        10. Create parent User accounts for guardians with email (best effort)

        All within single transaction (flush() not commit()).
        Rolls back everything if any step fails.

        Returns: { application_id, student_id, student_number, guardian_count, invoice_id, already_enrolled }
        """
        # 1. Validate application
        app = await self._get_application(tenant_id, application_id)

        # Idempotency guard: if already enrolled, return existing student
        # Check this BEFORE status validation so re-enrollment requests
        # are handled gracefully even though status is now 'enrolled'.
        if app.converted_student_id is not None:
            return {
                "application_id": str(application_id),
                "student_id": str(app.converted_student_id),
                "student_number": None,
                "guardian_count": 0,
                "invoice_id": None,
                "already_enrolled": True,
            }

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                f"Application must be in ACCEPTED status (current: {app.status})",
                code="INVALID_STATUS",
            )

        # --- Phase 3 guards: checklist completion + deposit requirement ---
        # AD-3: Checklist is OPTIONAL -- only enforced when a record exists.
        # If no checklist was created, enrollment proceeds unchanged.
        checklist_result = await self.db.execute(
            select(EnrollmentChecklist)
            .options(selectinload(EnrollmentChecklist.items))
            .where(
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.application_id == application_id,
                EnrollmentChecklist.deleted_at.is_(None),
            )
        )
        checklist = checklist_result.scalar_one_or_none()
        if checklist is not None:
            incomplete = [
                i for i in checklist.items
                if i.is_required and not i.is_completed and i.deleted_at is None
            ]
            if incomplete:
                item_names = [i.item_name for i in incomplete[:5]]
                raise EnrollmentError(
                    f"Enrollment checklist has {len(incomplete)} incomplete required "
                    f"item(s): {', '.join(item_names)}",
                    code="CHECKLIST_INCOMPLETE",
                )

        # Check enrollment deposit requirement from admission period
        period_result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == app.admission_period_id,
                AdmissionPeriod.tenant_id == tenant_id,
            )
        )
        period = period_result.scalar_one_or_none()
        if period and period.enrollment_deposit_required and not app.enrollment_deposit_paid:
            raise EnrollmentError(
                "Enrollment deposit is required but has not been recorded",
                code="DEPOSIT_REQUIRED",
            )

        # 2. Determine which class to enroll the student in
        # Use the decision's offered_class_id if available (may differ from target_class)
        decision_result = await self.db.execute(
            select(AdmissionDecision).where(
                AdmissionDecision.application_id == application_id,
                AdmissionDecision.tenant_id == tenant_id,
            )
        )
        decision = decision_result.scalar_one_or_none()
        class_id = (
            decision.offered_class_id
            if decision and decision.offered_class_id
            else app.target_class_id
        )

        # Get application guardians
        guardian_result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.deleted_at.is_(None),
            )
        )
        app_guardians = list(guardian_result.scalars().all())

        # 3-4. Deduplicate guardians + create student

        from app.models.student import Guardian, Student, StudentGuardian
        from app.models.school import School

        # Get school for student_id_prefix
        school_result = await self.db.execute(
            select(School).where(
                School.id == school_id,
                School.tenant_id == tenant_id,
            )
        )
        school = school_result.scalar_one_or_none()
        if not school:
            raise EnrollmentError("School not found", code="SCHOOL_NOT_FOUND")

        # Deduplicate guardians: match by email OR phone within tenant
        guardian_ids: list[tuple[uuid.UUID, str, bool]] = []
        for ag in app_guardians:
            existing = await self._find_existing_guardian(
                tenant_id, ag.email, ag.phone
            )
            if existing:
                guardian_ids.append(
                    (existing.id, ag.relationship, ag.is_primary)
                )
            else:
                new_guardian = Guardian(
                    tenant_id=tenant_id,
                    first_name=ag.first_name,
                    last_name=ag.last_name,
                    phone=ag.phone,
                    email=ag.email,
                    occupation=ag.occupation,
                    address=ag.address,
                )
                self.db.add(new_guardian)
                await self.db.flush()
                guardian_ids.append(
                    (new_guardian.id, ag.relationship, ag.is_primary)
                )

        # Generate student ID using existing StudentService pattern
        from app.services.student import StudentService

        student_service = StudentService(self.db)
        student_number = await student_service.generate_student_id(
            tenant_id, prefix=school.student_id_prefix or "STU"
        )

        # Create student record
        # Note: Application-only fields (nationality, previous_school, medical_info,
        # other_names) are not copied because the Student model does not have them.
        # applicant_other_names maps to middle_name on Student.
        student = Student(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=student_number,
            first_name=app.applicant_first_name,
            last_name=app.applicant_last_name,
            middle_name=getattr(app, "applicant_other_names", None),
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            class_id=class_id,
            status="active",
        )
        self.db.add(student)
        await self.db.flush()

        # 5. Create StudentGuardian junction records
        for gid, rel_type, is_primary in guardian_ids:
            sg = StudentGuardian(
                tenant_id=tenant_id,
                student_id=student.id,
                guardian_id=gid,
                relation_type=rel_type,
                is_primary=is_primary,
            )
            self.db.add(sg)

        # 6. Generate invoice (if fee structure exists for this class)
        invoice_id = None
        try:
            from app.services.finance.invoice_service import InvoiceService

            invoice_service = InvoiceService(self.db)
            # generate_for_student returns None if no fee structure exists
            if hasattr(invoice_service, "generate_for_student"):
                invoice = await invoice_service.generate_for_student(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    student_id=student.id,
                    class_id=class_id,
                )
                if invoice:
                    invoice_id = str(invoice.id)
            else:
                # Method not yet implemented -- skip invoice generation
                logger.info(
                    "enrollment_invoice_skipped_no_method",
                    application_id=str(application_id),
                )
        except Exception as e:
            # Invoice failure on enrollment is a hard error — the enrollment
            # should NOT proceed without the invoice when a fee structure exists.
            # generate_for_student() returns None (not an error) when no
            # fee structure exists for the target class.
            logger.error(
                "enrollment_invoice_failed",
                application_id=str(application_id),
                error=str(e),
            )
            raise EnrollmentError(
                "Invoice generation failed. Please contact support.",
                code="INVOICE_GENERATION_FAILED",
            )

        # 7. Update application status
        app.status = AdmissionApplicationStatus.ENROLLED.value
        app.converted_student_id = student.id

        # 8. Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application_id,
            from_status=AdmissionApplicationStatus.ACCEPTED.value,
            to_status=AdmissionApplicationStatus.ENROLLED.value,
            changed_by=enrolled_by,
            reason="Applicant enrolled as student",
        )
        self.db.add(history)

        await self.db.flush()

        # --- Phase 3: Post-enrollment automation ---
        # Generate confirmation PDF and send welcome pack (best effort).
        # Failures are logged but never block the enrollment transaction.
        try:
            await self.generate_enrollment_confirmation(
                tenant_id, application_id
            )
        except Exception:
            logger.warning(
                "enrollment_confirmation_generation_failed",
                application_id=str(application_id),
            )

        try:
            await self.send_welcome_pack(tenant_id, application_id)
        except Exception:
            logger.warning(
                "enrollment_welcome_pack_failed",
                application_id=str(application_id),
            )

        # 8b. Role promotion: applicant -> parent
        # If the application was submitted by an authenticated applicant,
        # promote their role from 'applicant' to 'parent' so they gain
        # access to the parent portal. This is a seamless transition --
        # same account, same credentials, expanded permissions.
        skip_parent_onboarding_for_email = None
        if app.applicant_user_id is not None:
            from app.models.user import User, UserRole

            applicant_user_result = await self.db.execute(
                select(User).where(
                    User.id == app.applicant_user_id,
                    # Defense-in-depth: verify tenant matches
                    User.tenant_id == tenant_id,
                    User.deleted_at.is_(None),
                )
            )
            applicant_user = applicant_user_result.scalar_one_or_none()

            if applicant_user and applicant_user.role == UserRole.APPLICANT.value:
                applicant_user.role = UserRole.PARENT.value
                await self.db.flush()

                # Revoke existing tokens to force re-login with new role
                try:
                    from app.services.token_blacklist import get_token_blacklist_service

                    blacklist = await get_token_blacklist_service()
                    await blacklist.blacklist_user_tokens(str(applicant_user.id))
                except Exception:
                    logger.warning("token_revoke_after_promotion_failed", user_id=str(applicant_user.id))

                logger.info(
                    "applicant_promoted_to_parent",
                    user_id=str(applicant_user.id),
                    application_id=str(application_id),
                    tenant_id=str(tenant_id),
                )

            # Skip ParentOnboardingService for this guardian -- user already exists
            if applicant_user:
                skip_parent_onboarding_for_email = applicant_user.email

        # 9. Notification (best effort -- failures logged but not raised)
        try:
            from app.services.admissions.notification_service import (
                AdmissionNotificationService,
            )

            notifier = AdmissionNotificationService(self.db)
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application_id,
                new_status="enrolled",
                extra_context={"student_id": student_number},
            )
        except Exception:
            logger.exception("enrollment_notification_failed")

        # 10. Create parent accounts for guardians with email (best effort)
        # Skip the applicant user's email to prevent duplicate account creation --
        # their account was already promoted from applicant to parent in step 8b.
        for ag in app_guardians:
            if ag.email and (
                skip_parent_onboarding_for_email is None
                or ag.email.lower() != skip_parent_onboarding_for_email.lower()
            ):
                try:
                    from app.services.parent.parent_onboarding import (
                        ParentOnboardingService,
                    )

                    onboarding = ParentOnboardingService(self.db)
                    await onboarding.create_parent_for_student(
                        student_id=student.id,
                        guardian_data={
                            "email": ag.email,
                            "first_name": ag.first_name,
                            "last_name": ag.last_name,
                            "phone": ag.phone,
                        },
                        tenant_id=tenant_id,
                        school_id=school_id,
                        invited_by=enrolled_by,
                    )
                except Exception:
                    # Parent account creation is best effort — don't block enrollment
                    logger.warning(
                        "parent_account_creation_skipped",
                        email=ag.email,
                    )

        logger.info(
            "applicant_enrolled",
            application_id=str(application_id),
            student_id=str(student.id),
            student_number=student_number,
        )

        return {
            "application_id": str(application_id),
            "student_id": str(student.id),
            "student_number": student_number,
            "guardian_count": len(guardian_ids),
            "invoice_id": invoice_id,
            "already_enrolled": False,
        }

    async def bulk_enroll(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_ids: list[uuid.UUID],
        enrolled_by: uuid.UUID,
    ) -> dict:
        """
        Bulk enroll multiple accepted applicants.

        Each enrollment runs in its own savepoint for partial success.
        One failed enrollment does not roll back the others.

        Returns: { succeeded: [...], failed: [...] }
        """
        succeeded: list[dict] = []
        failed: list[dict] = []

        for app_id in application_ids:
            try:
                async with self.db.begin_nested():
                    result = await self.enroll(
                        tenant_id=tenant_id,
                        school_id=school_id,
                        application_id=app_id,
                        enrolled_by=enrolled_by,
                    )
                    succeeded.append(result)
            except Exception as e:
                error_msg = (
                    e.message if isinstance(e, EnrollmentError) else "Enrollment failed"
                )
                failed.append({
                    "application_id": str(app_id),
                    "error": error_msg,
                })

        return {"succeeded": succeeded, "failed": failed}

    # ---- Private helpers ----

    async def _find_existing_guardian(
        self,
        tenant_id: uuid.UUID,
        email: str | None,
        phone: str,
    ):
        """
        Deduplicate: find existing guardian by email OR phone within tenant.

        Email match takes priority since it is a more reliable identifier.
        Falls back to phone match if no email provided or no email match found.
        """
        from app.models.student import Guardian

        if email:
            result = await self.db.execute(
                select(Guardian).where(
                    Guardian.tenant_id == tenant_id,
                    Guardian.email == email,
                    Guardian.deleted_at.is_(None),
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        # Fallback: match by phone
        result = await self.db.execute(
            select(Guardian).where(
                Guardian.tenant_id == tenant_id,
                Guardian.phone == phone,
                Guardian.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

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
            raise EnrollmentError("Application not found", code="NOT_FOUND")
        return app

    # ---- Enrollment Checklist ----

    async def create_enrollment_checklist(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> EnrollmentChecklist:
        """
        Create an enrollment checklist for an accepted application.

        Auto-populates items from the admission period's enrollment_checklist_template.
        If the application has boarding_status == 'boarding', additional boarding-specific
        items are appended and the checklist_type is set to 'boarding'.

        Raises EnrollmentError if:
        - Application not found or not in ACCEPTED status
        - A checklist already exists for this application
        """
        app = await self._get_application(tenant_id, application_id)

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                "Checklist can only be created for applications in ACCEPTED status",
                code="INVALID_STATUS",
            )

        # One active checklist per application -- prevent duplicates
        existing = await self.db.execute(
            select(EnrollmentChecklist).where(
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.application_id == application_id,
                EnrollmentChecklist.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise EnrollmentError(
                "A checklist already exists for this application",
                code="CHECKLIST_EXISTS",
            )

        # Determine checklist type from boarding status
        is_boarding = app.boarding_status == "boarding"
        checklist_type = "boarding" if is_boarding else "standard"

        checklist = EnrollmentChecklist(
            tenant_id=tenant_id,
            school_id=school_id,
            application_id=application_id,
            checklist_type=checklist_type,
        )
        self.db.add(checklist)
        await self.db.flush()

        # Load template from admission period
        period_result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == app.admission_period_id,
                AdmissionPeriod.tenant_id == tenant_id,
            )
        )
        period = period_result.scalar_one_or_none()
        template_items = period.enrollment_checklist_template if period else []

        # Create items from period template
        for item_data in template_items:
            item = EnrollmentChecklistItem(
                tenant_id=tenant_id,
                checklist_id=checklist.id,
                item_type=item_data.get("item_type", "document"),
                item_name=item_data.get("item_name", ""),
                description=item_data.get("description"),
                is_required=item_data.get("is_required", True),
            )
            self.db.add(item)

        # Append boarding-specific items when applicable
        if is_boarding:
            for item_data in _BOARDING_CHECKLIST_ITEMS:
                item = EnrollmentChecklistItem(
                    tenant_id=tenant_id,
                    checklist_id=checklist.id,
                    item_type=item_data["item_type"],
                    item_name=item_data["item_name"],
                    is_required=item_data["is_required"],
                )
                self.db.add(item)

        await self.db.flush()
        await self.db.refresh(checklist)

        logger.info(
            "enrollment_checklist_created",
            checklist_id=str(checklist.id),
            application_id=str(application_id),
            checklist_type=checklist_type,
        )
        return checklist

    async def get_checklist(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> EnrollmentChecklist:
        """
        Get the enrollment checklist for an application, with items eagerly loaded.
        Raises EnrollmentError if no checklist exists.
        """
        result = await self.db.execute(
            select(EnrollmentChecklist)
            .options(selectinload(EnrollmentChecklist.items))
            .where(
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.application_id == application_id,
                EnrollmentChecklist.deleted_at.is_(None),
            )
        )
        checklist = result.scalar_one_or_none()
        if not checklist:
            raise EnrollmentError(
                "No enrollment checklist found for this application",
                code="NOT_FOUND",
            )
        return checklist

    async def complete_checklist_item(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        notes: str | None = None,
        item_metadata: dict | None = None,
    ) -> EnrollmentChecklistItem:
        """
        Mark a checklist item as completed.

        After marking, checks if all required items are now complete.
        If so, auto-completes the parent checklist (sets completed_at/completed_by).
        """
        result = await self.db.execute(
            select(EnrollmentChecklistItem).where(
                EnrollmentChecklistItem.id == item_id,
                EnrollmentChecklistItem.tenant_id == tenant_id,
                EnrollmentChecklistItem.deleted_at.is_(None),
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise EnrollmentError("Checklist item not found", code="NOT_FOUND")

        if item.is_completed:
            raise EnrollmentError("Item already completed", code="ALREADY_COMPLETED")

        item.is_completed = True
        item.completed_at = datetime.now(UTC)
        item.completed_by = user_id
        if notes:
            item.notes = notes
        if item_metadata:
            # Merge metadata -- preserve existing keys, add/overwrite new ones
            existing_meta = item.item_metadata or {}
            existing_meta.update(item_metadata)
            item.item_metadata = existing_meta

        await self.db.flush()
        await self.db.refresh(item)

        # Check if all required items in the checklist are now complete
        await self._auto_complete_checklist(tenant_id, item.checklist_id, user_id)

        logger.info(
            "checklist_item_completed",
            item_id=str(item_id),
            item_name=item.item_name,
        )
        return item

    async def _auto_complete_checklist(
        self,
        tenant_id: uuid.UUID,
        checklist_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Check if all required items are complete. If so, mark the checklist
        as completed. Called after every item completion.
        """
        result = await self.db.execute(
            select(EnrollmentChecklistItem).where(
                EnrollmentChecklistItem.tenant_id == tenant_id,
                EnrollmentChecklistItem.checklist_id == checklist_id,
                EnrollmentChecklistItem.is_required.is_(True),
                EnrollmentChecklistItem.deleted_at.is_(None),
            )
        )
        required_items = list(result.scalars().all())

        if not required_items:
            return

        all_complete = all(item.is_completed for item in required_items)
        if not all_complete:
            return

        # All required items done -- mark checklist as completed
        checklist_result = await self.db.execute(
            select(EnrollmentChecklist).where(
                EnrollmentChecklist.id == checklist_id,
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.deleted_at.is_(None),
            )
        )
        checklist = checklist_result.scalar_one_or_none()
        if checklist and checklist.completed_at is None:
            checklist.completed_at = datetime.now(UTC)
            checklist.completed_by = user_id
            await self.db.flush()

            logger.info(
                "enrollment_checklist_auto_completed",
                checklist_id=str(checklist_id),
            )

    # ---- Enrollment Deposit ----

    async def record_enrollment_deposit(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        amount: Decimal,
        reference: str,
    ) -> Application:
        """
        Record an enrollment deposit payment (manual entry by admin).

        Sets the deposit fields on the application. If a checklist exists
        with a 'payment' type item containing 'deposit' in the name, that
        item is auto-completed.
        """
        app = await self._get_application(tenant_id, application_id)

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                "Deposits can only be recorded for ACCEPTED applications",
                code="INVALID_STATUS",
            )

        if app.enrollment_deposit_paid:
            raise EnrollmentError(
                "Deposit already recorded for this application",
                code="DEPOSIT_ALREADY_PAID",
            )

        app.enrollment_deposit_paid = True
        app.enrollment_deposit_amount = amount
        app.enrollment_deposit_reference = reference
        app.enrollment_deposit_paid_at = datetime.now(UTC)
        await self.db.flush()

        # Auto-complete the deposit checklist item if it exists
        deposit_item_result = await self.db.execute(
            select(EnrollmentChecklistItem)
            .join(
                EnrollmentChecklist,
                EnrollmentChecklistItem.checklist_id == EnrollmentChecklist.id,
            )
            .where(
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.application_id == application_id,
                EnrollmentChecklist.deleted_at.is_(None),
                EnrollmentChecklistItem.item_type == "payment",
                EnrollmentChecklistItem.item_name.ilike("%deposit%"),
                EnrollmentChecklistItem.is_completed.is_(False),
                EnrollmentChecklistItem.deleted_at.is_(None),
            )
        )
        deposit_item = deposit_item_result.scalar_one_or_none()
        if deposit_item:
            deposit_item.is_completed = True
            deposit_item.completed_at = datetime.now(UTC)
            deposit_item.item_metadata = {
                "payment_ref": reference,
                "amount": float(amount),
            }
            await self.db.flush()

            # Re-check checklist completion after auto-completing the deposit item
            await self._auto_complete_checklist(
                tenant_id,
                deposit_item.checklist_id,
                deposit_item.completed_by or uuid.UUID(int=0),
            )

        await self.db.refresh(app)

        logger.info(
            "enrollment_deposit_recorded",
            application_id=str(application_id),
            amount=str(amount),
            reference=reference,
        )
        return app

    # ---- Boarding Status ----

    async def assign_boarding_status(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        boarding_status: str,
    ) -> tuple[Application, int]:
        """
        Assign boarding or day status to an application.

        If status is 'boarding' and a checklist exists that is not already
        a boarding checklist, boarding-specific items are appended and the
        checklist_type is upgraded. Returns (application, boarding_items_added).
        """
        if boarding_status not in ("boarding", "day"):
            raise EnrollmentError(
                f"Invalid boarding status: {boarding_status}. Must be 'boarding' or 'day'",
                code="INVALID_BOARDING_STATUS",
            )

        app = await self._get_application(tenant_id, application_id)

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                "Boarding status can only be assigned to ACCEPTED applications",
                code="INVALID_STATUS",
            )

        app.boarding_status = boarding_status
        await self.db.flush()

        boarding_items_added = 0

        # If boarding and a standard checklist exists, upgrade it
        if boarding_status == "boarding":
            checklist_result = await self.db.execute(
                select(EnrollmentChecklist).where(
                    EnrollmentChecklist.tenant_id == tenant_id,
                    EnrollmentChecklist.application_id == application_id,
                    EnrollmentChecklist.deleted_at.is_(None),
                )
            )
            checklist = checklist_result.scalar_one_or_none()

            if checklist and checklist.checklist_type != "boarding":
                # Upgrade checklist type and add boarding items
                checklist.checklist_type = "boarding"

                for item_data in _BOARDING_CHECKLIST_ITEMS:
                    item = EnrollmentChecklistItem(
                        tenant_id=tenant_id,
                        checklist_id=checklist.id,
                        item_type=item_data["item_type"],
                        item_name=item_data["item_name"],
                        is_required=item_data["is_required"],
                    )
                    self.db.add(item)
                    boarding_items_added += 1

                await self.db.flush()

        await self.db.refresh(app)

        logger.info(
            "boarding_status_assigned",
            application_id=str(application_id),
            boarding_status=boarding_status,
            items_added=boarding_items_added,
        )
        return app, boarding_items_added

    # ---- Enrollment Confirmation PDF ----

    async def generate_enrollment_confirmation(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> str:
        """
        Generate an enrollment confirmation letter as a PDF and upload to S3.

        The PDF includes school branding, student details, assigned class,
        checklist completion summary (if exists), boarding status, and next steps.

        Returns the S3 URL of the generated PDF.
        """
        from app.models.academic import Class
        from app.models.school import School
        from app.services.s3 import get_s3_service

        app = await self._get_application(tenant_id, application_id)

        if app.status not in (
            AdmissionApplicationStatus.ACCEPTED.value,
            AdmissionApplicationStatus.ENROLLED.value,
        ):
            raise EnrollmentError(
                "Confirmation letter can only be generated for ACCEPTED or ENROLLED applications",
                code="INVALID_STATUS",
            )

        # Load school for branding
        school_result = await self.db.execute(
            select(School).where(
                School.id == app.school_id,
                School.tenant_id == tenant_id,
            )
        )
        school = school_result.scalar_one_or_none()
        if not school:
            raise EnrollmentError("School not found", code="SCHOOL_NOT_FOUND")

        # Load target class name
        class_name = "To be assigned"
        if app.target_class_id:
            class_result = await self.db.execute(
                select(Class).where(
                    Class.id == app.target_class_id,
                    Class.tenant_id == tenant_id,
                )
            )
            target_class = class_result.scalar_one_or_none()
            if target_class:
                class_name = target_class.name

        # Load checklist summary if it exists (optional -- AD-3)
        checklist_summary = None
        try:
            checklist = await self.get_checklist(tenant_id, application_id)
            items = [i for i in checklist.items if i.deleted_at is None]
            total = len(items)
            completed = sum(1 for i in items if i.is_completed)
            checklist_summary = {
                "total": total,
                "completed": completed,
                "items": [
                    {
                        "name": i.item_name,
                        "type": i.item_type,
                        "completed": i.is_completed,
                        "required": i.is_required,
                    }
                    for i in items
                ],
            }
        except EnrollmentError:
            # No checklist -- that is fine, it is optional
            pass

        # Validate color and logo URL to prevent CSS/HTML injection (REVIEW FIX H2)
        safe_color = self._safe_color(school.primary_color)
        safe_logo_url = self._safe_logo_url(school.logo_url)

        applicant_name = f"{app.applicant_first_name} {app.applicant_last_name}"
        template_context = {
            "school": school,
            "school_color": safe_color,
            "safe_logo_url": safe_logo_url,
            "applicant_name": applicant_name,
            "applicant_first_name": app.applicant_first_name,
            "applicant_last_name": app.applicant_last_name,
            "date_of_birth": app.date_of_birth,
            "gender": app.gender,
            "class_name": class_name,
            "boarding_status": app.boarding_status,
            "tracking_code": app.tracking_code,
            "deposit_paid": app.enrollment_deposit_paid,
            "deposit_amount": app.enrollment_deposit_amount,
            "checklist": checklist_summary,
            "generated_date": datetime.now(UTC),
        }

        # Render PDF via Jinja2 + WeasyPrint
        pdf_bytes = self._render_pdf("enrollment_confirmation.html", template_context)

        # Upload to S3 -- confirmations are private (served via presigned URLs)
        s3_key = f"admissions/{tenant_id}/{application_id}/enrollment_confirmation.pdf"
        s3 = get_s3_service()
        url = s3.upload_file(pdf_bytes, s3_key, "application/pdf")

        # Save URL on application
        app.enrollment_confirmation_url = url
        await self.db.flush()

        logger.info(
            "enrollment_confirmation_generated",
            application_id=str(application_id),
            url=url,
        )
        return url

    # ---- Welcome Pack ----

    async def send_welcome_pack(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> tuple[Application, list[str]]:
        """
        Send welcome pack / orientation information via email and SMS.

        The welcome pack is dispatched through the AdmissionNotificationService.
        Returns (application, channels_used).
        """
        app = await self._get_application(tenant_id, application_id)

        if app.status not in (
            AdmissionApplicationStatus.ACCEPTED.value,
            AdmissionApplicationStatus.ENROLLED.value,
        ):
            raise EnrollmentError(
                "Welcome pack can only be sent for ACCEPTED or ENROLLED applications",
                code="INVALID_STATUS",
            )

        if app.welcome_pack_sent:
            raise EnrollmentError(
                "Welcome pack already sent for this application",
                code="ALREADY_SENT",
            )

        channels: list[str] = []

        # Load guardians for contact info
        guardian_result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.deleted_at.is_(None),
            )
        )
        guardians = list(guardian_result.scalars().all())
        primary = next(
            (g for g in guardians if g.is_primary),
            guardians[0] if guardians else None,
        )

        if not primary:
            raise EnrollmentError(
                "No guardian found for this application",
                code="NO_GUARDIAN",
            )

        # Send via notification service (best effort -- failures logged but not raised)
        try:
            from app.services.admissions.notification_service import (
                AdmissionNotificationService,
            )

            notifier = AdmissionNotificationService(self.db)
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application_id,
                new_status="welcome_pack",
                extra_context={
                    "boarding_status": app.boarding_status or "day",
                    "confirmation_url": app.enrollment_confirmation_url,
                },
            )
            channels.append("email")
            if primary.phone:
                channels.append("sms")
        except Exception:
            logger.exception("welcome_pack_notification_failed")

        app.welcome_pack_sent = True
        app.welcome_pack_sent_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(app)

        logger.info(
            "welcome_pack_sent",
            application_id=str(application_id),
            channels=channels,
        )
        return app, channels

    # ---- PDF rendering helpers ----

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
        """Render a Jinja2 template to PDF bytes using WeasyPrint."""
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
