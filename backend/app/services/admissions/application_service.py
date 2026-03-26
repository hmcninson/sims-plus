"""
SIMS Plus - Application Service

Handles application submission, status transitions, search, waivers,
and notes for the admissions module.

This is the largest service in the admissions package — it handles the
core application lifecycle from public submission through admin review.
"""

import secrets
import uuid
from datetime import UTC, date, datetime

import structlog
from jsonschema import ValidationError, validate
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.admissions import (
    AdmissionFormConfig,
    AdmissionPeriod,
    AdmissionPeriodStatus,
    Application,
    ApplicationDocument,
    ApplicationGuardian,
    ApplicationNote,
    ApplicationPayment,
    ApplicationStatusHistory,
    AdmissionApplicationStatus,
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
)
from app.utils.turnstile import verify_turnstile

logger = structlog.get_logger(__name__)


class ApplicationServiceError(Exception):
    def __init__(self, message: str, code: str = "APPLICATION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        turnstile_token: str,
        admission_period_id: uuid.UUID,
        applicant_first_name: str,
        applicant_last_name: str,
        applicant_other_names: str | None,
        date_of_birth: date,
        gender: str,
        nationality: str | None,
        target_class_id: uuid.UUID,
        custom_fields: dict,
        previous_school: str | None,
        medical_info: str | None,
        guardians: list[dict],
        applicant_user_id: uuid.UUID | None = None,
        remote_ip: str | None = None,
    ) -> Application:
        """
        Submit a new application (public endpoint).

        Steps:
        1. Verify Turnstile token (fail closed)
        2. Check per-tenant daily submission cap
        3. Validate period is open and has capacity
        4. Validate target_class_id is in period's target_classes
        5. Validate custom_fields against form_schema (if configured)
        6. Generate tracking_code (384-bit entropy)
        7. Create Application + ApplicationGuardian records
        8. Create initial status history entry
        9. If fee not required, auto-transition to SUBMITTED

        Raises ApplicationServiceError on failure.
        """
        # 1. Turnstile verification (fail closed)
        if not await verify_turnstile(turnstile_token, remote_ip=remote_ip):
            raise ApplicationServiceError(
                "CAPTCHA verification failed. Please try again.",
                code="CAPTCHA_FAILED",
            )

        # 2. Per-tenant daily submission cap (defense against distributed attacks)
        daily_count = await self._get_daily_submission_count(tenant_id)
        if daily_count >= settings.ADMISSIONS_DAILY_CAP_PER_TENANT:
            raise ApplicationServiceError(
                "This school has reached the maximum number of applications for today. "
                "Please try again tomorrow.",
                code="DAILY_CAP_EXCEEDED",
            )

        # 3. Period validation
        period = await self._get_open_period(tenant_id, admission_period_id)

        # Enforce require_applicant_account — anonymous users cannot submit
        # when the period mandates an authenticated applicant account
        if period.require_applicant_account and applicant_user_id is None:
            raise ApplicationServiceError(
                "This admission period requires an applicant account. "
                "Please create an account or sign in before applying.",
                code="ACCOUNT_REQUIRED",
            )

        if period.max_applications:
            count = await self._count_applications(tenant_id, admission_period_id)
            if count >= period.max_applications:
                raise ApplicationServiceError(
                    "This admission period has reached its application limit.",
                    code="PERIOD_FULL",
                )

        # 4. Validate target class is accepted by this period
        target_class_str = str(target_class_id)
        if period.target_classes and target_class_str not in period.target_classes:
            raise ApplicationServiceError(
                "The selected class is not accepting applications in this period.",
                code="CLASS_NOT_IN_PERIOD",
            )

        # 5. Validate custom fields against form schema
        await self._validate_custom_fields(tenant_id, admission_period_id, custom_fields)

        # 6. Guardian validation
        if not guardians:
            raise ApplicationServiceError(
                "At least one guardian is required.",
                code="NO_GUARDIANS",
            )

        # 7. Generate tracking code (384-bit entropy, not guessable)
        tracking_code = secrets.token_urlsafe(48)

        # 8. Determine initial status based on fee requirement
        initial_status = AdmissionApplicationStatus.DRAFT.value
        submitted_at = None

        if not period.application_fee_required:
            # No fee required — go straight to SUBMITTED
            initial_status = AdmissionApplicationStatus.SUBMITTED.value
            submitted_at = datetime.now(UTC)

        # 9. Create application
        application = Application(
            tenant_id=tenant_id,
            school_id=school_id,
            admission_period_id=admission_period_id,
            tracking_code=tracking_code,
            applicant_first_name=applicant_first_name.strip(),
            applicant_last_name=applicant_last_name.strip(),
            applicant_other_names=(
                applicant_other_names.strip() if applicant_other_names else None
            ),
            date_of_birth=date_of_birth,
            gender=gender.lower(),
            nationality=nationality,
            target_class_id=target_class_id,
            status=initial_status,
            custom_fields=custom_fields,
            previous_school=previous_school,
            medical_info=medical_info,
            submitted_at=submitted_at,
            # Link to applicant account if authenticated
            applicant_user_id=applicant_user_id,
        )
        self.db.add(application)
        await self.db.flush()

        # 10. Create guardian records
        for g_data in guardians:
            guardian = ApplicationGuardian(
                tenant_id=tenant_id,
                application_id=application.id,
                first_name=g_data["first_name"].strip(),
                last_name=g_data["last_name"].strip(),
                phone=g_data["phone"].strip(),
                email=g_data.get("email", "").strip() or None,
                relationship=g_data["relationship"],
                is_primary=g_data.get("is_primary", False),
                occupation=g_data.get("occupation"),
                address=g_data.get("address"),
            )
            self.db.add(guardian)

        # 11. Status history (append-only audit log)
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application.id,
            from_status=None,
            to_status=initial_status,
            changed_by=None,  # Public action — no user account
            reason="Application submitted via public form",
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "application_submitted",
            application_id=str(application.id),
            tracking_code=tracking_code,
            tenant_id=str(tenant_id),
            period_id=str(admission_period_id),
        )

        return application

    async def transition_status(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: str,
        changed_by: uuid.UUID,
        reason: str | None = None,
    ) -> Application:
        """
        Transition application to a new status.

        Validates against VALID_TRANSITIONS dict and enforces gate checks
        (fee payment, exam completion) for certain transitions.
        Creates status history record.
        """
        application = await self._get_application(tenant_id, application_id)
        current = AdmissionApplicationStatus(application.status)
        target = AdmissionApplicationStatus(new_status)

        allowed = VALID_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise ApplicationServiceError(
                f"Cannot transition from {current.value} to {target.value}",
                code="INVALID_TRANSITION",
            )

        # Fee gate: DRAFT -> SUBMITTED requires payment or waiver
        if target == AdmissionApplicationStatus.SUBMITTED:
            if not application.fee_waived:
                has_payment = await self._has_completed_payment(
                    tenant_id, application_id
                )
                if not has_payment:
                    raise ApplicationServiceError(
                        "Application fee must be paid before submission",
                        code="FEE_REQUIRED",
                    )

        # Exam gate: SHORTLISTED -> OFFERED requires exam result or waiver
        if (
            target == AdmissionApplicationStatus.OFFERED
            and current == AdmissionApplicationStatus.SHORTLISTED
        ):
            if not application.exam_waived:
                raise ApplicationServiceError(
                    "Entrance exam not waived. Schedule exam first.",
                    code="EXAM_REQUIRED",
                )

        old_status = application.status
        application.status = target.value

        if target == AdmissionApplicationStatus.SUBMITTED and not application.submitted_at:
            application.submitted_at = datetime.now(UTC)

        # Append-only status history record
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application_id,
            from_status=old_status,
            to_status=target.value,
            changed_by=changed_by,
            reason=reason,
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)
        return application

    async def get_by_tracking_code(
        self,
        tenant_id: uuid.UUID,
        tracking_code: str,
    ) -> dict:
        """
        Public status lookup. Returns MINIMAL data only to prevent PII leakage.

        Only exposes: status, first name, submitted_at, last_updated_at.
        """
        result = await self.db.execute(
            select(Application).where(
                Application.tenant_id == tenant_id,
                Application.tracking_code == tracking_code,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise ApplicationServiceError("Application not found", code="NOT_FOUND")

        return {
            "status": app.status,
            "applicant_first_name": app.applicant_first_name,
            "submitted_at": app.submitted_at,
            "last_updated_at": app.updated_at,
        }

    async def get_application(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """Admin: get application detail by ID."""
        return await self._get_application(tenant_id, application_id)

    async def list_applications(
        self,
        tenant_id: uuid.UUID,
        *,
        school_id: uuid.UUID | None = None,
        status: str | None = None,
        admission_period_id: uuid.UUID | None = None,
        target_class_id: uuid.UUID | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Application], int]:
        """
        Admin: list applications with filters and pagination.
        Returns (applications, total_count).
        """
        query = select(Application).where(
            Application.tenant_id == tenant_id,
            Application.deleted_at.is_(None),
        )

        if school_id:
            query = query.where(Application.school_id == school_id)
        if status:
            query = query.where(Application.status == status)
        if admission_period_id:
            query = query.where(
                Application.admission_period_id == admission_period_id
            )
        if target_class_id:
            query = query.where(Application.target_class_id == target_class_id)
        if search:
            from app.utils.sanitize import escape_ilike

            escaped = escape_ilike(search)
            search_term = f"%{escaped}%"
            query = query.where(
                or_(
                    Application.applicant_first_name.ilike(search_term),
                    Application.applicant_last_name.ilike(search_term),
                    Application.tracking_code.ilike(search_term),
                )
            )

        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Paginate
        query = (
            query.order_by(Application.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def add_note(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        author_id: uuid.UUID,
        content: str,
        is_internal: bool = True,
    ) -> ApplicationNote:
        """Admin: add an internal review note to an application."""
        # Verify application exists and belongs to tenant
        await self._get_application(tenant_id, application_id)

        note = ApplicationNote(
            tenant_id=tenant_id,
            application_id=application_id,
            author_id=author_id,
            content=content.strip(),
            is_internal=is_internal,
        )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note)
        return note

    async def waive_fee(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """Admin: waive application fee."""
        app = await self._get_application(tenant_id, application_id)
        app.fee_waived = True

        # If app is in DRAFT and fee was the only blocker, transition to SUBMITTED
        if app.status == AdmissionApplicationStatus.DRAFT.value:
            app.status = AdmissionApplicationStatus.SUBMITTED.value
            app.submitted_at = datetime.now(UTC)
            history = ApplicationStatusHistory(
                tenant_id=tenant_id,
                application_id=application_id,
                from_status=AdmissionApplicationStatus.DRAFT.value,
                to_status=AdmissionApplicationStatus.SUBMITTED.value,
                changed_by=None,
                reason="Fee waived -- auto-submitted",
            )
            self.db.add(history)

        await self.db.flush()
        await self.db.refresh(app)
        return app

    async def waive_exam(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """Admin: waive entrance exam requirement."""
        app = await self._get_application(tenant_id, application_id)
        app.exam_waived = True
        await self.db.flush()
        await self.db.refresh(app)
        return app

    async def get_school_info(
        self,
        tenant_id: uuid.UUID,
    ) -> dict:
        """
        Get school branding info for the public application form.

        Returns minimal school data (name, logo, colors, contact info).
        Queries the first active school for the tenant -- public forms
        resolve tenant from subdomain, which maps to one school.
        """
        from app.models.school import School

        result = await self.db.execute(
            select(School).where(
                School.tenant_id == tenant_id,
                School.is_active.is_(True),
            ).limit(1)
        )
        school = result.scalar_one_or_none()
        if not school:
            raise ApplicationServiceError(
                "School not found", code="NOT_FOUND"
            )

        return {
            "school_name": school.name,
            "logo_url": school.logo_url if hasattr(school, "logo_url") else None,
            "primary_color": school.primary_color if hasattr(school, "primary_color") else None,
            "secondary_color": school.secondary_color if hasattr(school, "secondary_color") else None,
            "motto": school.motto if hasattr(school, "motto") else None,
            "address": school.address if hasattr(school, "address") else None,
            "phone": school.phone if hasattr(school, "phone") else None,
            "email": school.email if hasattr(school, "email") else None,
        }

    async def upload_document(
        self,
        tenant_id: uuid.UUID,
        tracking_code: str,
        document_type: str,
        file_name: str,
        mime_type: str,
        file_size: int,
    ) -> dict:
        """
        Create an ApplicationDocument record and return a presigned S3 PUT URL.

        Validates:
        - Application exists and is in DRAFT or SUBMITTED status
        - Max 5 documents per application (prevent storage abuse)
        - MIME type is allowed (validated by schema, defense-in-depth here)

        The frontend uploads directly to S3 using the presigned URL.
        """
        # Look up application by tracking code
        result = await self.db.execute(
            select(Application).where(
                Application.tenant_id == tenant_id,
                Application.tracking_code == tracking_code,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise ApplicationServiceError(
                "Application not found", code="NOT_FOUND"
            )

        # Only allow document upload in DRAFT or SUBMITTED status
        allowed_statuses = {
            AdmissionApplicationStatus.DRAFT.value,
            AdmissionApplicationStatus.SUBMITTED.value,
        }
        if app.status not in allowed_statuses:
            raise ApplicationServiceError(
                "Documents can only be uploaded for draft or submitted applications",
                code="INVALID_STATUS",
            )

        # Check document count limit (max 5 per application)
        doc_count_result = await self.db.execute(
            select(func.count(ApplicationDocument.id)).where(
                ApplicationDocument.application_id == app.id,
                ApplicationDocument.tenant_id == tenant_id,
                ApplicationDocument.deleted_at.is_(None),
            )
        )
        doc_count = doc_count_result.scalar() or 0
        if doc_count >= 5:
            raise ApplicationServiceError(
                "Maximum of 5 documents per application",
                code="MAX_DOCUMENTS",
            )

        # Defense-in-depth: validate mime type
        allowed_mimes = {"application/pdf", "image/jpeg", "image/png"}
        if mime_type not in allowed_mimes:
            raise ApplicationServiceError(
                "Unsupported file type", code="VALIDATION_ERROR"
            )

        # Generate S3 key with unique UUID to prevent overwrites
        ext = mime_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        doc_uuid = uuid.uuid4()
        s3_key = f"admissions/{tenant_id}/{app.id}/{doc_uuid}.{ext}"

        # Create document record
        document = ApplicationDocument(
            tenant_id=tenant_id,
            application_id=app.id,
            document_type=document_type,
            file_name=file_name,
            s3_key=s3_key,
            file_size=file_size,
            mime_type=mime_type,
        )
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)

        # Generate presigned PUT URL for direct upload from frontend
        from app.services.s3 import get_s3_service

        s3 = get_s3_service()
        upload_url = s3.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": s3.bucket,
                "Key": s3_key,
                "ContentType": mime_type,
            },
            ExpiresIn=3600,
        )

        return {
            "document_id": document.id,
            "upload_url": upload_url,
            "s3_key": s3_key,
            "expires_in": 3600,
        }

    async def get_dashboard_stats(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        admission_period_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Aggregate pipeline statistics for the admissions dashboard.

        Returns counts by status, by class, by period, conversion rate,
        pending decisions/enrollment counts, and recent applications.
        """
        base_filters = [
            Application.tenant_id == tenant_id,
            Application.school_id == school_id,
            Application.deleted_at.is_(None),
        ]
        if admission_period_id:
            base_filters.append(
                Application.admission_period_id == admission_period_id
            )

        # Total count
        total_result = await self.db.execute(
            select(func.count(Application.id)).where(*base_filters)
        )
        total = total_result.scalar() or 0

        # By status
        status_result = await self.db.execute(
            select(Application.status, func.count(Application.id))
            .where(*base_filters)
            .group_by(Application.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        # By target class
        from app.models.academic import Class

        class_result = await self.db.execute(
            select(Class.name, func.count(Application.id))
            .join(Class, Application.target_class_id == Class.id)
            .where(*base_filters)
            .group_by(Class.name)
            .order_by(func.count(Application.id).desc())
        )
        by_class = [
            {"class_name": row[0], "count": row[1]}
            for row in class_result.all()
        ]

        # By admission period
        by_period_result = await self.db.execute(
            select(AdmissionPeriod.name, func.count(Application.id))
            .join(
                AdmissionPeriod,
                Application.admission_period_id == AdmissionPeriod.id,
            )
            .where(*base_filters)
            .group_by(AdmissionPeriod.name)
            .order_by(func.count(Application.id).desc())
        )
        by_period = [
            {"period_name": row[0], "count": row[1]}
            for row in by_period_result.all()
        ]

        # Conversion rate: enrolled / total
        enrolled_count = by_status.get(
            AdmissionApplicationStatus.ENROLLED.value, 0
        )
        conversion_rate = (
            round(enrolled_count / total, 4) if total > 0 else None
        )

        # Pending decisions: applications in reviewable states without a decision
        reviewable = {
            AdmissionApplicationStatus.UNDER_REVIEW.value,
            AdmissionApplicationStatus.EXAM_COMPLETED.value,
            AdmissionApplicationStatus.SHORTLISTED.value,
        }
        pending_decisions = sum(
            by_status.get(s, 0) for s in reviewable
        )

        # Pending enrollment: accepted but not yet enrolled
        pending_enrollment = by_status.get(
            AdmissionApplicationStatus.ACCEPTED.value, 0
        )

        # Recent applications (last 10)
        recent_result = await self.db.execute(
            select(Application)
            .where(*base_filters)
            .order_by(Application.created_at.desc())
            .limit(10)
        )
        recent = list(recent_result.scalars().all())

        # Convert recent applications to list items
        recent_items = []
        for app in recent:
            recent_items.append({
                "id": app.id,
                "tracking_code": app.tracking_code,
                "applicant_first_name": app.applicant_first_name,
                "applicant_last_name": app.applicant_last_name,
                "date_of_birth": app.date_of_birth,
                "gender": app.gender,
                "target_class_name": None,
                "status": app.status,
                "fee_waived": app.fee_waived,
                "exam_waived": app.exam_waived,
                "submitted_at": app.submitted_at,
                "created_at": app.created_at,
            })

        return {
            "total_applications": total,
            "by_status": by_status,
            "by_class": by_class,
            "by_period": by_period,
            "conversion_rate": conversion_rate,
            "pending_decisions": pending_decisions,
            "pending_enrollment": pending_enrollment,
            "recent_applications": recent_items,
        }

    async def get_demographics(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        admission_period_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Aggregate demographic data for applicants.

        Returns breakdowns by gender, nationality, previous school,
        and age distribution.
        """
        base_filters = [
            Application.tenant_id == tenant_id,
            Application.school_id == school_id,
            Application.deleted_at.is_(None),
        ]
        if admission_period_id:
            base_filters.append(
                Application.admission_period_id == admission_period_id
            )

        # By gender
        gender_result = await self.db.execute(
            select(Application.gender, func.count(Application.id))
            .where(*base_filters)
            .group_by(Application.gender)
        )
        by_gender = {row[0]: row[1] for row in gender_result.all()}

        # By nationality
        nationality_result = await self.db.execute(
            select(Application.nationality, func.count(Application.id))
            .where(
                *base_filters,
                Application.nationality.isnot(None),
            )
            .group_by(Application.nationality)
            .order_by(func.count(Application.id).desc())
            .limit(20)
        )
        by_nationality = [
            {"nationality": row[0], "count": row[1]}
            for row in nationality_result.all()
        ]

        # By previous school
        prev_school_result = await self.db.execute(
            select(Application.previous_school, func.count(Application.id))
            .where(
                *base_filters,
                Application.previous_school.isnot(None),
            )
            .group_by(Application.previous_school)
            .order_by(func.count(Application.id).desc())
            .limit(20)
        )
        by_previous_school = [
            {"school": row[0], "count": row[1]}
            for row in prev_school_result.all()
        ]

        # Age distribution (calculate age from date_of_birth)
        today = date.today()
        # Use SQL to compute age brackets
        age_result = await self.db.execute(
            select(
                func.extract("year", func.age(Application.date_of_birth)),
                func.count(Application.id),
            )
            .where(*base_filters)
            .group_by(
                func.extract("year", func.age(Application.date_of_birth))
            )
            .order_by(
                func.extract("year", func.age(Application.date_of_birth))
            )
        )

        # Group into age ranges
        age_buckets: dict[str, int] = {}
        for row in age_result.all():
            age = int(row[0]) if row[0] is not None else 0
            if age < 3:
                bucket = "Under 3"
            elif age <= 5:
                bucket = "3-5"
            elif age <= 8:
                bucket = "6-8"
            elif age <= 11:
                bucket = "9-11"
            elif age <= 14:
                bucket = "12-14"
            elif age <= 17:
                bucket = "15-17"
            else:
                bucket = "18+"
            age_buckets[bucket] = age_buckets.get(bucket, 0) + row[1]

        age_distribution = [
            {"age_range": k, "count": v} for k, v in age_buckets.items()
        ]

        return {
            "by_gender": by_gender,
            "by_nationality": by_nationality,
            "by_previous_school": by_previous_school,
            "age_distribution": age_distribution,
        }

    # ---- Applicant account methods ----

    async def list_my_applications(
        self,
        tenant_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Application], int]:
        """
        List applications belonging to a specific applicant user.

        IDOR protection: filters by BOTH tenant_id AND applicant_user_id.
        The user_id comes from the JWT (never from request body/params).
        """
        query = (
            select(Application)
            .options(
                selectinload(Application.target_class),
                selectinload(Application.admission_period),
            )
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Application.tenant_id == tenant_id,
                # IDOR prevention: only this user's applications
                Application.applicant_user_id == applicant_user_id,
                Application.deleted_at.is_(None),
            )
        )

        if status:
            query = query.where(Application.status == status)

        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Paginate, most recent first
        query = (
            query
            .order_by(Application.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_draft(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
        *,
        admission_period_id: uuid.UUID,
        applicant_first_name: str,
        applicant_last_name: str,
        applicant_other_names: str | None = None,
        date_of_birth: date | None = None,
        gender: str | None = None,
        nationality: str | None = None,
        target_class_id: uuid.UUID | None = None,
        previous_school: str | None = None,
        medical_info: str | None = None,
        custom_fields: dict | None = None,
        guardians: list[dict] | None = None,
    ) -> Application:
        """
        Create a new draft application linked to an applicant account.

        Minimal validation: period must exist and be open.
        No Turnstile required (user is authenticated).
        No custom_fields schema validation (will be validated on submit).
        Guardians are optional at draft stage.

        Per-tenant daily cap still applies to prevent abuse.

        Raises:
            ApplicationServiceError: If period not found, not open, or daily cap hit.
        """
        # Validate period exists and is open
        period = await self._get_open_period(tenant_id, admission_period_id)

        # Per-tenant daily cap (defense against authenticated abuse)
        daily_count = await self._get_daily_submission_count(tenant_id)
        if daily_count >= settings.ADMISSIONS_DAILY_CAP_PER_TENANT:
            raise ApplicationServiceError(
                "This school has reached the maximum number of applications for today.",
                code="DAILY_CAP_EXCEEDED",
            )

        # Generate tracking code
        tracking_code = secrets.token_urlsafe(48)

        # Create application in DRAFT status (always starts as draft)
        application = Application(
            tenant_id=tenant_id,
            school_id=school_id,
            admission_period_id=admission_period_id,
            tracking_code=tracking_code,
            applicant_first_name=applicant_first_name.strip(),
            applicant_last_name=applicant_last_name.strip(),
            applicant_other_names=(
                applicant_other_names.strip() if applicant_other_names else None
            ),
            date_of_birth=date_of_birth,
            gender=gender.lower() if gender else None,
            nationality=nationality,
            target_class_id=target_class_id,
            status=AdmissionApplicationStatus.DRAFT.value,
            custom_fields=custom_fields or {},
            previous_school=previous_school,
            medical_info=medical_info,
            # Link to applicant account
            applicant_user_id=applicant_user_id,
        )
        self.db.add(application)
        await self.db.flush()

        # Create guardian records if provided
        if guardians:
            for g_data in guardians:
                guardian = ApplicationGuardian(
                    tenant_id=tenant_id,
                    application_id=application.id,
                    first_name=g_data.get("first_name", "").strip(),
                    last_name=g_data.get("last_name", "").strip(),
                    phone=g_data.get("phone", "").strip(),
                    email=(g_data.get("email", "") or "").strip() or None,
                    relationship=g_data.get("relationship", "guardian"),
                    is_primary=g_data.get("is_primary", False),
                    occupation=g_data.get("occupation"),
                    address=g_data.get("address"),
                )
                self.db.add(guardian)

        # Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application.id,
            from_status=None,
            to_status=AdmissionApplicationStatus.DRAFT.value,
            changed_by=applicant_user_id,
            reason="Draft created via applicant dashboard",
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "draft_application_created",
            application_id=str(application.id),
            user_id=str(applicant_user_id),
            tenant_id=str(tenant_id),
        )

        return application

    async def update_draft(
        self,
        tenant_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        applicant_first_name: str | None = None,
        applicant_last_name: str | None = None,
        applicant_other_names: str | None = None,
        date_of_birth: date | None = None,
        gender: str | None = None,
        nationality: str | None = None,
        target_class_id: uuid.UUID | None = None,
        previous_school: str | None = None,
        medical_info: str | None = None,
        custom_fields: dict | None = None,
        guardians: list[dict] | None = None,
    ) -> Application:
        """
        Update a draft application.

        IDOR protection: verifies application.applicant_user_id == user_id.
        Only applications in DRAFT status can be updated.

        When guardians are provided, the existing guardian records are
        replaced (delete + recreate). This simplifies partial updates
        from the multi-step wizard.

        Raises:
            ApplicationServiceError: If not found, not owner, or not in DRAFT status.
        """
        application = await self._get_my_application(
            tenant_id, applicant_user_id, application_id
        )

        if application.status != AdmissionApplicationStatus.DRAFT.value:
            raise ApplicationServiceError(
                "Only draft applications can be updated.",
                code="NOT_DRAFT",
            )

        # Update scalar fields (only if provided)
        if applicant_first_name is not None:
            application.applicant_first_name = applicant_first_name.strip()
        if applicant_last_name is not None:
            application.applicant_last_name = applicant_last_name.strip()
        if applicant_other_names is not None:
            application.applicant_other_names = (
                applicant_other_names.strip() if applicant_other_names else None
            )
        if date_of_birth is not None:
            application.date_of_birth = date_of_birth
        if gender is not None:
            application.gender = gender.lower()
        if nationality is not None:
            application.nationality = nationality
        if target_class_id is not None:
            application.target_class_id = target_class_id
        if previous_school is not None:
            application.previous_school = previous_school
        if medical_info is not None:
            application.medical_info = medical_info
        if custom_fields is not None:
            application.custom_fields = custom_fields

        # Replace guardians if provided
        if guardians is not None:
            # Hard-delete existing guardians (draft data, not finalized)
            # Draft guardian records are not finalized data -- hard delete prevents
            # accumulating orphan records during repeated saves.
            await self.db.execute(
                delete(ApplicationGuardian).where(
                    ApplicationGuardian.application_id == application.id,
                    ApplicationGuardian.tenant_id == tenant_id,
                )
            )
            await self.db.flush()

            # Create new guardian records
            for g_data in guardians:
                guardian = ApplicationGuardian(
                    tenant_id=tenant_id,
                    application_id=application_id,
                    first_name=g_data.get("first_name", "").strip(),
                    last_name=g_data.get("last_name", "").strip(),
                    phone=g_data.get("phone", "").strip(),
                    email=(g_data.get("email", "") or "").strip() or None,
                    relationship=g_data.get("relationship", "guardian"),
                    is_primary=g_data.get("is_primary", False),
                    occupation=g_data.get("occupation"),
                    address=g_data.get("address"),
                )
                self.db.add(guardian)

        await self.db.flush()
        await self.db.refresh(application)

        return application

    async def submit_draft(
        self,
        tenant_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """
        Submit a draft application.

        IDOR protection: verifies application.applicant_user_id == user_id.
        Only applications in DRAFT status can be submitted.

        Full validation (same as public submit):
        - At least one guardian required (with non-empty required fields)
        - target_class_id must be set
        - date_of_birth must be set
        - gender must be set
        - custom_fields validated against form_schema (if configured)

        If fee is required and not waived, status stays DRAFT until payment.
        If fee is not required (or waived), status transitions to SUBMITTED.

        Raises:
            ApplicationServiceError: If validation fails, not owner, or not DRAFT.
        """
        application = await self._get_my_application(
            tenant_id, applicant_user_id, application_id
        )

        if application.status != AdmissionApplicationStatus.DRAFT.value:
            raise ApplicationServiceError(
                "Only draft applications can be submitted.",
                code="NOT_DRAFT",
            )

        # --- Full validation ---

        # Required fields
        if not application.target_class_id:
            raise ApplicationServiceError(
                "Target class is required before submission.",
                code="MISSING_TARGET_CLASS",
            )
        if not application.date_of_birth:
            raise ApplicationServiceError(
                "Date of birth is required before submission.",
                code="MISSING_DOB",
            )
        if not application.gender:
            raise ApplicationServiceError(
                "Gender is required before submission.",
                code="MISSING_GENDER",
            )

        # Guardians validation
        guardian_result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.deleted_at.is_(None),
            )
        )
        active_guardians = guardian_result.scalars().all()

        if not active_guardians:
            raise ApplicationServiceError(
                "At least one guardian is required before submission.",
                code="NO_GUARDIANS",
            )

        # Validate guardian required fields
        for g in active_guardians:
            if not g.first_name or not g.last_name or not g.phone:
                raise ApplicationServiceError(
                    "All guardians must have first name, last name, and phone number.",
                    code="INCOMPLETE_GUARDIAN",
                )

        # Custom fields validation against form schema
        await self._validate_custom_fields(
            tenant_id, application.admission_period_id, application.custom_fields
        )

        # --- Determine submission status ---
        period = await self._get_open_period(tenant_id, application.admission_period_id)

        if not period.application_fee_required or application.fee_waived:
            # No fee required -- transition to SUBMITTED
            application.status = AdmissionApplicationStatus.SUBMITTED.value
            application.submitted_at = datetime.now(UTC)
        else:
            # Fee required -- check if already paid
            has_payment = await self._has_completed_payment(tenant_id, application_id)
            if has_payment:
                application.status = AdmissionApplicationStatus.SUBMITTED.value
                application.submitted_at = datetime.now(UTC)
            # else: stays in DRAFT until payment confirmed (via webhook)

        # Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application_id,
            from_status=AdmissionApplicationStatus.DRAFT.value,
            to_status=application.status,
            changed_by=applicant_user_id,
            reason="Submitted via applicant dashboard",
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "draft_submitted",
            application_id=str(application_id),
            user_id=str(applicant_user_id),
            new_status=application.status,
        )

        return application

    async def get_my_application(
        self,
        tenant_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """
        Get a single application owned by the applicant.

        IDOR protection: verifies application.applicant_user_id == user_id.
        Loads basic relations (guardians, documents, payments, status_history, decision).
        """
        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.guardians),
                selectinload(Application.documents),
                selectinload(Application.payments),
                selectinload(Application.status_history),
                selectinload(Application.decision),
                selectinload(Application.target_class),
                selectinload(Application.admission_period),
            )
            .where(
                Application.id == application_id,
                # Defense-in-depth: filter by tenant_id
                Application.tenant_id == tenant_id,
                # IDOR prevention: must be owner
                Application.applicant_user_id == applicant_user_id,
                Application.deleted_at.is_(None),
            )
        )
        application = result.scalar_one_or_none()

        if not application:
            raise ApplicationServiceError(
                "Application not found.",
                code="NOT_FOUND",
            )

        return application

    async def get_printable_application(
        self,
        tenant_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """
        Get full application data for print view.

        Same IDOR protection as get_my_application but eager-loads ALL
        relations needed for the printable view:
        - guardians, documents, payments, decision
        - admission_period (for period name)
        - target_class (for class name)
        - school (for school name, logo)

        Does NOT include: notes, status_history (admin-only data).
        """
        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.guardians),
                selectinload(Application.documents),
                selectinload(Application.payments),
                selectinload(Application.decision),
                selectinload(Application.admission_period),
                selectinload(Application.target_class),
                selectinload(Application.school),
            )
            .where(
                Application.id == application_id,
                Application.tenant_id == tenant_id,
                Application.applicant_user_id == applicant_user_id,
                Application.deleted_at.is_(None),
            )
        )
        application = result.scalar_one_or_none()

        if not application:
            raise ApplicationServiceError(
                "Application not found.",
                code="NOT_FOUND",
            )

        return application

    async def get_latest_guardian_info(
        self,
        tenant_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
    ) -> list[dict]:
        """
        Get guardian info from the most recent submitted application.
        Used for pre-filling guardian section when creating a new application.
        Returns empty list if no previous applications exist.
        """
        result = await self.db.execute(
            select(Application)
            .where(
                Application.tenant_id == tenant_id,
                Application.applicant_user_id == applicant_user_id,
                Application.status != AdmissionApplicationStatus.DRAFT.value,
                Application.deleted_at.is_(None),
            )
            .options(selectinload(Application.guardians))
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        latest_app = result.scalar_one_or_none()
        if not latest_app:
            return []

        return [
            {
                "first_name": g.first_name,
                "last_name": g.last_name,
                "phone": g.phone,
                "email": g.email,
                "relationship": g.relationship,
                "is_primary": g.is_primary,
                "occupation": g.occupation,
                "address": g.address,
            }
            for g in latest_app.guardians
            if g.deleted_at is None
        ]

    async def _get_my_application(
        self,
        tenant_id: uuid.UUID,
        applicant_user_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """
        Internal helper: fetch application with IDOR check.

        Does NOT eagerly load relations -- used by update/submit methods
        that don't need nested data.
        """
        result = await self.db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id,
                Application.applicant_user_id == applicant_user_id,
                Application.deleted_at.is_(None),
            )
        )
        application = result.scalar_one_or_none()

        if not application:
            raise ApplicationServiceError(
                "Application not found.",
                code="NOT_FOUND",
            )

        return application

    # ---- Private helpers ----

    async def _get_open_period(
        self, tenant_id: uuid.UUID, period_id: uuid.UUID
    ) -> AdmissionPeriod:
        result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == period_id,
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.status == AdmissionPeriodStatus.OPEN.value,
                AdmissionPeriod.deleted_at.is_(None),
            )
        )
        period = result.scalar_one_or_none()
        if not period:
            raise ApplicationServiceError(
                "Admission period not found or not open",
                code="PERIOD_NOT_OPEN",
            )

        today = date.today()
        if today < period.start_date or today > period.end_date:
            raise ApplicationServiceError(
                "Admission period is not currently accepting applications",
                code="PERIOD_NOT_ACTIVE",
            )
        return period

    async def _validate_custom_fields(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
        custom_fields: dict,
    ) -> None:
        result = await self.db.execute(
            select(AdmissionFormConfig).where(
                AdmissionFormConfig.tenant_id == tenant_id,
                AdmissionFormConfig.admission_period_id == period_id,
            )
        )
        config = result.scalar_one_or_none()
        if config and config.form_schema:
            try:
                validate(instance=custom_fields, schema=config.form_schema)
            except ValidationError as e:
                raise ApplicationServiceError(
                    f"Invalid custom fields: {e.message}",
                    code="VALIDATION_ERROR",
                )

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
            raise ApplicationServiceError("Application not found", code="NOT_FOUND")
        return app

    async def _count_applications(
        self, tenant_id: uuid.UUID, period_id: uuid.UUID
    ) -> int:
        result = await self.db.execute(
            select(func.count(Application.id)).where(
                Application.tenant_id == tenant_id,
                Application.admission_period_id == period_id,
                Application.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def _get_daily_submission_count(self, tenant_id: uuid.UUID) -> int:
        """Count today's submissions for this tenant."""
        today = datetime.now(UTC).date()
        result = await self.db.execute(
            select(func.count(Application.id)).where(
                Application.tenant_id == tenant_id,
                func.date(Application.created_at) == today,
                Application.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    async def _has_completed_payment(
        self, tenant_id: uuid.UUID, app_id: uuid.UUID
    ) -> bool:
        result = await self.db.execute(
            select(func.count(ApplicationPayment.id)).where(
                ApplicationPayment.tenant_id == tenant_id,
                ApplicationPayment.application_id == app_id,
                ApplicationPayment.status == "completed",
            )
        )
        return (result.scalar() or 0) > 0
