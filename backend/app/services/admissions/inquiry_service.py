"""
SIMS Plus - Inquiry Service (Enrollment Gap Closure Phase 1)

Lead management service: create, update, search, status transitions,
communication logging, follow-up tasks, duplicate detection, bulk import,
and conversion to formal applications.
"""

import math
import secrets
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admissions import (
    Application,
    ApplicationGuardian,
    AdmissionApplicationStatus,
    AdmissionPeriod,
    AdmissionPeriodStatus,
    Inquiry,
    InquiryCommunication,
    InquiryFollowUp,
    INQUIRY_TERMINAL_STATUSES,
    INQUIRY_VALID_TRANSITIONS,
)
from app.models.user import User
from app.schemas.inquiry import (
    BulkInquiryImportRow,
    CommunicationCreate,
    FollowUpCreate,
    InquiryCreate,
    InquiryUpdate,
)
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger(__name__)


class InquiryServiceError(Exception):
    """Raised when an inquiry operation fails."""

    def __init__(self, message: str, code: str = "INQUIRY_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class InquiryService:
    """Service for managing inquiries (pre-application leads)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Fields that must never be set via setattr loops (REVIEW FIX H1)
    PROTECTED_FIELDS = frozenset({
        "id", "tenant_id", "school_id", "created_at", "updated_at", "deleted_at",
        "converted_application_id", "status",
    })

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        data: InquiryCreate,
    ) -> Inquiry:
        """
        Create a new inquiry/lead.

        Sets initial status to 'new'. Source value is validated by
        Pydantic schema before reaching this method.
        """
        inquiry = Inquiry(
            tenant_id=tenant_id,
            school_id=school_id,
            source=data.source.value,
            status="new",
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            target_class_id=data.target_class_id,
            guardian_name=data.guardian_name,
            guardian_phone=data.guardian_phone,
            guardian_email=data.guardian_email,
            referred_by=data.referred_by,
            notes=data.notes,
        )
        self.db.add(inquiry)
        await self.db.flush()
        await self.db.refresh(inquiry)

        logger.info(
            "inquiry_created",
            inquiry_id=str(inquiry.id),
            tenant_id=str(tenant_id),
            school_id=str(school_id),
            source=data.source.value,
        )
        return inquiry

    async def get(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Inquiry:
        """
        Get a single inquiry by ID with communications and follow-ups loaded.

        Raises InquiryServiceError if not found or soft-deleted.
        """
        result = await self.db.execute(
            select(Inquiry)
            .options(
                selectinload(Inquiry.communications),
                selectinload(Inquiry.follow_ups),
            )
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.id == inquiry_id)
            .where(Inquiry.deleted_at.is_(None))
        )
        inquiry = result.scalar_one_or_none()
        if not inquiry:
            raise InquiryServiceError("Inquiry not found", code="NOT_FOUND")
        return inquiry

    async def list_inquiries(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        status: str | None = None,
        source: str | None = None,
        assigned_to: uuid.UUID | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Inquiry], int]:
        """
        Paginated inquiry list with optional filters.

        Search matches against first_name, last_name, guardian_name,
        and guardian_phone using escaped ILIKE patterns.
        """
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        base_query = (
            select(Inquiry)
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.school_id == school_id)
            .where(Inquiry.deleted_at.is_(None))
        )

        if status:
            base_query = base_query.where(Inquiry.status == status)

        if source:
            base_query = base_query.where(Inquiry.source == source)

        if assigned_to:
            base_query = base_query.where(Inquiry.assigned_to == assigned_to)

        if search:
            safe_search = escape_ilike(search)
            base_query = base_query.where(
                or_(
                    Inquiry.first_name.ilike(f"%{safe_search}%"),
                    Inquiry.last_name.ilike(f"%{safe_search}%"),
                    Inquiry.guardian_name.ilike(f"%{safe_search}%"),
                    Inquiry.guardian_phone.ilike(f"%{safe_search}%"),
                )
            )

        # Count total matching rows
        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        # Paginate
        offset = (page - 1) * page_size
        items_result = await self.db.execute(
            base_query
            .order_by(Inquiry.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(items_result.scalars().all())

        return items, total

    async def update(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: InquiryUpdate,
    ) -> Inquiry:
        """
        Update non-protected fields on an inquiry.

        Uses PROTECTED_FIELDS blocklist to prevent overwriting
        id, tenant_id, school_id, timestamps, or status (REVIEW FIX H1).
        """
        inquiry = await self._get_inquiry(inquiry_id, tenant_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            if field not in self.PROTECTED_FIELDS:
                setattr(inquiry, field, value)

        await self.db.flush()
        await self.db.refresh(inquiry)
        return inquiry

    async def update_status(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
        new_status: str,
    ) -> Inquiry:
        """
        Transition inquiry status with validation against the state machine.

        Raises InquiryServiceError if the transition is not allowed.
        """
        inquiry = await self._get_inquiry(inquiry_id, tenant_id)

        current = inquiry.status
        allowed = INQUIRY_VALID_TRANSITIONS.get(current, [])

        if new_status not in allowed:
            raise InquiryServiceError(
                f"Cannot transition from '{current}' to '{new_status}'. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'none (terminal state)'}",
                code="INVALID_TRANSITION",
            )

        inquiry.status = new_status
        await self.db.flush()
        await self.db.refresh(inquiry)

        logger.info(
            "inquiry_status_changed",
            inquiry_id=str(inquiry_id),
            from_status=current,
            to_status=new_status,
        )
        return inquiry

    async def assign(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
        assigned_to: uuid.UUID,
    ) -> Inquiry:
        """
        Assign inquiry to a staff member.

        Verifies the target user exists within the same tenant
        to prevent cross-tenant staff assignment.
        """
        inquiry = await self._get_inquiry(inquiry_id, tenant_id)

        # Verify the assigned user exists in the same tenant
        user_result = await self.db.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.id == assigned_to)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise InquiryServiceError(
                "Assigned user not found in this school",
                code="USER_NOT_FOUND",
            )

        inquiry.assigned_to = assigned_to
        await self.db.flush()
        await self.db.refresh(inquiry)
        return inquiry

    async def delete(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        """Soft-delete an inquiry."""
        inquiry = await self._get_inquiry(inquiry_id, tenant_id)
        inquiry.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "inquiry_soft_deleted",
            inquiry_id=str(inquiry_id),
            tenant_id=str(tenant_id),
        )

    # ------------------------------------------------------------------
    # Conversion to Application
    # ------------------------------------------------------------------

    async def convert_to_application(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> Application:
        """
        Convert an inquiry into a formal application.

        Steps:
        1. Verify inquiry is not in a terminal state
        2. Verify admission period is open
        3. Create Application record from inquiry data
        4. Create ApplicationGuardian from guardian data
        5. Link inquiry to the new application
        6. Transition inquiry status to 'applied'

        Returns the newly created Application.
        """
        inquiry = await self._get_inquiry(inquiry_id, tenant_id)

        # Cannot convert inquiries that are already applied/enrolled
        if inquiry.status in INQUIRY_TERMINAL_STATUSES or inquiry.status == "applied":
            raise InquiryServiceError(
                f"Cannot convert inquiry with status '{inquiry.status}'",
                code="INVALID_STATUS",
            )

        if inquiry.converted_application_id is not None:
            raise InquiryServiceError(
                "Inquiry has already been converted to an application",
                code="ALREADY_CONVERTED",
            )

        # Verify admission period exists and is open
        period_result = await self.db.execute(
            select(AdmissionPeriod)
            .where(AdmissionPeriod.tenant_id == tenant_id)
            .where(AdmissionPeriod.id == period_id)
            .where(AdmissionPeriod.deleted_at.is_(None))
        )
        period = period_result.scalar_one_or_none()
        if not period:
            raise InquiryServiceError(
                "Admission period not found",
                code="PERIOD_NOT_FOUND",
            )
        if period.status != AdmissionPeriodStatus.OPEN.value:
            raise InquiryServiceError(
                "Admission period is not open for applications",
                code="PERIOD_NOT_OPEN",
            )

        # Generate a tracking code for the new application
        tracking_code = secrets.token_urlsafe(48)

        # Create application from inquiry data
        application = Application(
            tenant_id=tenant_id,
            school_id=school_id,
            admission_period_id=period_id,
            inquiry_id=inquiry_id,
            tracking_code=tracking_code,
            applicant_first_name=inquiry.first_name,
            applicant_last_name=inquiry.last_name,
            date_of_birth=inquiry.date_of_birth,
            gender=inquiry.gender,
            target_class_id=inquiry.target_class_id,
            status=AdmissionApplicationStatus.SUBMITTED.value,
            custom_fields={},
        )
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)

        # Create guardian record if guardian info is present
        if inquiry.guardian_name and inquiry.guardian_phone:
            # Split guardian name into first/last (best effort)
            name_parts = inquiry.guardian_name.strip().split(maxsplit=1)
            guardian_first = name_parts[0]
            guardian_last = name_parts[1] if len(name_parts) > 1 else ""

            guardian = ApplicationGuardian(
                tenant_id=tenant_id,
                application_id=application.id,
                first_name=guardian_first,
                last_name=guardian_last,
                phone=inquiry.guardian_phone,
                email=inquiry.guardian_email,
                relationship="guardian",
                is_primary=True,
            )
            self.db.add(guardian)
            await self.db.flush()

        # Link inquiry to the application and transition status
        inquiry.converted_application_id = application.id
        inquiry.status = "applied"
        await self.db.flush()
        await self.db.refresh(inquiry)

        logger.info(
            "inquiry_converted_to_application",
            inquiry_id=str(inquiry_id),
            application_id=str(application.id),
            tenant_id=str(tenant_id),
        )
        return application

    # ------------------------------------------------------------------
    # Communications
    # ------------------------------------------------------------------

    async def add_communication(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: CommunicationCreate,
    ) -> InquiryCommunication:
        """
        Append a communication log entry to an inquiry.

        If this is an outbound communication and the inquiry is still 'new',
        auto-transition to 'contacted' to reflect first contact.
        """
        inquiry = await self._get_inquiry(inquiry_id, tenant_id)

        comm = InquiryCommunication(
            tenant_id=tenant_id,
            inquiry_id=inquiry_id,
            channel=data.channel.value,
            direction=data.direction.value,
            content=data.content,
            sent_by=user_id,
            sent_at=datetime.now(UTC),
        )
        self.db.add(comm)
        await self.db.flush()
        await self.db.refresh(comm)

        # Auto-transition: outbound contact on a new lead marks it as contacted
        if data.direction.value == "outbound" and inquiry.status == "new":
            inquiry.status = "contacted"
            await self.db.flush()

        return comm

    async def list_communications(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[InquiryCommunication]:
        """List all communication log entries for an inquiry, newest first."""
        # Verify inquiry exists and belongs to tenant
        await self._get_inquiry(inquiry_id, tenant_id)

        result = await self.db.execute(
            select(InquiryCommunication)
            .where(InquiryCommunication.tenant_id == tenant_id)
            .where(InquiryCommunication.inquiry_id == inquiry_id)
            .order_by(InquiryCommunication.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Follow-Ups
    # ------------------------------------------------------------------

    async def create_follow_up(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: FollowUpCreate,
    ) -> InquiryFollowUp:
        """Create a follow-up task assigned to a staff member."""
        # Verify inquiry exists and belongs to tenant
        await self._get_inquiry(inquiry_id, tenant_id)

        # Verify assigned user exists in tenant
        user_result = await self.db.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.id == data.assigned_to)
        )
        if not user_result.scalar_one_or_none():
            raise InquiryServiceError(
                "Assigned user not found in this school",
                code="USER_NOT_FOUND",
            )

        follow_up = InquiryFollowUp(
            tenant_id=tenant_id,
            inquiry_id=inquiry_id,
            assigned_to=data.assigned_to,
            due_date=data.due_date,
            priority=data.priority.value,
            notes=data.notes,
        )
        self.db.add(follow_up)
        await self.db.flush()
        await self.db.refresh(follow_up)
        return follow_up

    async def complete_follow_up(
        self,
        follow_up_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> InquiryFollowUp:
        """Mark a follow-up task as completed."""
        result = await self.db.execute(
            select(InquiryFollowUp)
            .where(InquiryFollowUp.tenant_id == tenant_id)
            .where(InquiryFollowUp.id == follow_up_id)
            .where(InquiryFollowUp.deleted_at.is_(None))
        )
        follow_up = result.scalar_one_or_none()
        if not follow_up:
            raise InquiryServiceError(
                "Follow-up not found", code="NOT_FOUND"
            )

        if follow_up.completed_at is not None:
            raise InquiryServiceError(
                "Follow-up is already completed", code="ALREADY_COMPLETED"
            )

        follow_up.completed_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(follow_up)
        return follow_up

    async def list_pending_follow_ups(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> list[InquiryFollowUp]:
        """
        List pending (incomplete) follow-ups.

        Optionally filter by assigned_to for 'my follow-ups' views.
        """
        query = (
            select(InquiryFollowUp)
            .where(InquiryFollowUp.tenant_id == tenant_id)
            .where(InquiryFollowUp.completed_at.is_(None))
            .where(InquiryFollowUp.deleted_at.is_(None))
        )

        if user_id:
            query = query.where(InquiryFollowUp.assigned_to == user_id)

        query = query.order_by(InquiryFollowUp.due_date.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Duplicate Check
    # ------------------------------------------------------------------

    async def check_duplicate(
        self,
        tenant_id: uuid.UUID,
        phone: str | None = None,
        email: str | None = None,
    ) -> list[Inquiry]:
        """
        Find existing inquiries matching phone or email within the tenant.

        Advisory only -- returns matches for the user to review, does not
        block creation.
        """
        if not phone and not email:
            return []

        conditions = []
        if phone:
            conditions.append(Inquiry.guardian_phone == phone)
        if email:
            conditions.append(Inquiry.guardian_email == email)

        result = await self.db.execute(
            select(Inquiry)
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.deleted_at.is_(None))
            .where(or_(*conditions))
            .order_by(Inquiry.created_at.desc())
            .limit(10)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Bulk Import
    # ------------------------------------------------------------------

    async def bulk_import(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        rows: list[BulkInquiryImportRow],
    ) -> dict:
        """
        Bulk import inquiries from a list of rows.

        - Maximum 200 rows per call (validated at schema level)
        - Deduplicates by guardian_phone within the tenant
        - Returns imported/skipped/errors counts
        """
        imported = 0
        skipped = 0
        errors: list[dict] = []

        # Pre-fetch existing guardian phones for dedup
        existing_result = await self.db.execute(
            select(Inquiry.guardian_phone)
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.deleted_at.is_(None))
        )
        existing_phones = {row[0] for row in existing_result.all()}

        # Track phones seen in this batch to avoid intra-batch duplicates
        seen_phones: set[str] = set()

        for idx, row in enumerate(rows):
            try:
                phone = row.guardian_phone.strip()

                # Skip duplicates (existing in DB or already in this batch)
                if phone in existing_phones or phone in seen_phones:
                    skipped += 1
                    continue

                seen_phones.add(phone)

                inquiry = Inquiry(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    source=row.source.value if row.source else "other",
                    status="new",
                    first_name=row.first_name,
                    last_name=row.last_name,
                    guardian_name=row.guardian_name,
                    guardian_phone=phone,
                    guardian_email=row.guardian_email,
                    notes=row.notes,
                )
                self.db.add(inquiry)
                imported += 1

            except Exception:
                errors.append({
                    "row": idx + 1,
                    "error": "Failed to import this row",
                })

        if imported > 0:
            await self.db.flush()

        logger.info(
            "inquiry_bulk_import",
            tenant_id=str(tenant_id),
            imported=imported,
            skipped=skipped,
            errors=len(errors),
        )

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_stats(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> dict:
        """
        Get inquiry pipeline statistics for the school.

        Returns total count, breakdown by status and source, and
        conversion rate (inquiries that became applications).
        """
        base = (
            select(Inquiry)
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.school_id == school_id)
            .where(Inquiry.deleted_at.is_(None))
        )

        # Total count
        total_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = total_result.scalar_one()

        # By status
        status_result = await self.db.execute(
            select(Inquiry.status, func.count())
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.school_id == school_id)
            .where(Inquiry.deleted_at.is_(None))
            .group_by(Inquiry.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        # By source
        source_result = await self.db.execute(
            select(Inquiry.source, func.count())
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.school_id == school_id)
            .where(Inquiry.deleted_at.is_(None))
            .group_by(Inquiry.source)
        )
        by_source = {row[0]: row[1] for row in source_result.all()}

        # Conversion rate: inquiries that have a linked application
        converted_result = await self.db.execute(
            select(func.count())
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.school_id == school_id)
            .where(Inquiry.deleted_at.is_(None))
            .where(Inquiry.converted_application_id.isnot(None))
        )
        converted = converted_result.scalar_one()
        conversion_rate = (converted / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "by_source": by_source,
            "conversion_rate": round(conversion_rate, 2),
        }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    async def _get_inquiry(
        self,
        inquiry_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Inquiry:
        """
        Fetch a single inquiry without eager loading relationships.

        Used by mutation methods that don't need communications/follow-ups.
        """
        result = await self.db.execute(
            select(Inquiry)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(Inquiry.tenant_id == tenant_id)
            .where(Inquiry.id == inquiry_id)
            .where(Inquiry.deleted_at.is_(None))
        )
        inquiry = result.scalar_one_or_none()
        if not inquiry:
            raise InquiryServiceError("Inquiry not found", code="NOT_FOUND")
        return inquiry
