"""
SIMS Plus - Student Lifecycle Service

Withdrawal, transfer, and lifecycle management for students.
Handles clearance workflows, chain transfers, and document generation.
"""

import json
from datetime import date as date_type, datetime, UTC
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import UUID

import nh3
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from weasyprint import HTML

from app.models.academic import AcademicYear, Class, ClassSection
from app.models.finance.invoice_models import Invoice, InvoiceStatus
from app.models.school import School
from app.models.student import (
    Student,
    StudentClassHistory,
    StudentStatus,
    StudentStatusChange,
    WithdrawalClearance,
)

from app.services.student._shared import StudentServiceError


# Statuses that indicate outstanding fees
_OUTSTANDING_STATUSES = (
    InvoiceStatus.ISSUED,
    InvoiceStatus.PARTIAL,
    InvoiceStatus.OVERDUE,
)


class StudentLifecycleMixin:
    """Mixin for withdrawal, transfer, and lifecycle management.

    Composes into StudentService alongside other mixins. Uses self.db
    (AsyncSession) and raises StudentServiceError for business rule violations.
    """

    # Type hint for self.db -- set by StudentService.__init__
    db: AsyncSession

    # ===========================
    # Private Helpers
    # ===========================

    async def _get_active_student_for_update(
        self, tenant_id: UUID, student_id: UUID
    ) -> Student:
        """Lock and return an active student row.

        F-16: SELECT FOR UPDATE prevents concurrent withdrawal/transfer races
        on the same student.
        """
        result = await self.db.execute(
            select(Student)
            .with_for_update()
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Student.school),
                selectinload(Student.class_),
                selectinload(Student.section),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")
        if student.status != StudentStatus.ACTIVE:
            raise StudentServiceError(
                f"Student status is '{student.status.value}', expected 'active'",
                code="student_not_active",
            )
        return student

    async def _get_active_student(
        self, tenant_id: UUID, student_id: UUID
    ) -> Student:
        """Get an active student without locking."""
        result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Student.school),
                selectinload(Student.class_),
                selectinload(Student.section),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")
        if student.status != StudentStatus.ACTIVE:
            raise StudentServiceError(
                f"Student status is '{student.status.value}', expected 'active'",
                code="student_not_active",
            )
        return student

    async def _get_pending_clearance(
        self, tenant_id: UUID, student_id: UUID
    ) -> WithdrawalClearance | None:
        """Get the pending (not yet finalized) clearance for a student, if any.

        A clearance is pending until it has been linked to a status change
        (status_change_id is set at complete_withdrawal/complete_transfer).
        Using status_change_id IS NULL instead of is_complete=False so that
        clearances that have been auto-completed can still be finalized.
        """
        result = await self.db.execute(
            select(WithdrawalClearance).where(
                and_(
                    WithdrawalClearance.tenant_id == tenant_id,
                    WithdrawalClearance.student_id == student_id,
                    WithdrawalClearance.status_change_id.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    # ===========================
    # Fee Checks
    # ===========================

    async def check_outstanding_fees(
        self, tenant_id: UUID, student_id: UUID
    ) -> dict:
        """Query outstanding invoices for a student.

        AD-4: Fee check is advisory, not blocking -- callers can choose
        to proceed with fee_override=True.

        Returns dict matching OutstandingFeeCheckResponse schema.
        """
        result = await self.db.execute(
            select(Invoice).where(
                and_(
                    # Defense-in-depth: filter by tenant_id
                    Invoice.tenant_id == tenant_id,
                    Invoice.student_id == student_id,
                    Invoice.deleted_at.is_(None),
                    Invoice.status.in_(_OUTSTANDING_STATUSES),
                )
            )
        )
        invoices = result.scalars().all()

        invoice_summaries = []
        total_outstanding = Decimal("0.00")

        for inv in invoices:
            balance = inv.total_amount - inv.amount_paid
            total_outstanding += balance
            invoice_summaries.append({
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": float(inv.total_amount),
                "balance": float(balance),
                "status": inv.status.value,
                "due_date": inv.due_date,
            })

        return {
            "has_outstanding": len(invoice_summaries) > 0,
            "total_outstanding": float(total_outstanding),
            "invoice_count": len(invoice_summaries),
            "invoices": invoice_summaries,
        }

    # ===========================
    # Withdrawal Flow
    # ===========================

    async def initiate_withdrawal(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        reason: str,
        effective_date: date_type,
        performed_by: UUID,
        fee_override: bool = False,
    ) -> dict:
        """Start the withdrawal process by creating a clearance checklist.

        F-16: Locks student row to prevent concurrent withdrawal/transfer races.
        F-17: Status change is NOT created here -- only at complete_withdrawal().
        """
        # Lock student to prevent race conditions
        student = await self._get_active_student_for_update(tenant_id, student_id)

        # Check for an existing pending clearance
        existing = await self._get_pending_clearance(tenant_id, student_id)
        if existing:
            raise StudentServiceError(
                "A pending withdrawal/transfer clearance already exists for this student",
                code="clearance_already_exists",
            )

        # Check outstanding fees (advisory)
        fee_info = await self.check_outstanding_fees(tenant_id, student_id)

        # Create clearance checklist
        clearance = WithdrawalClearance(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            status_change_id=None,  # F-17: linked at completion
            type="withdrawal",
            outstanding_fees=Decimal(str(fee_info["total_outstanding"])),
            fee_override=fee_override,
            # Boarding cleared is only relevant for boarders
            boarding_cleared=None if not student.is_boarder else False,
            notes=reason,
        )
        self.db.add(clearance)
        await self.db.flush()
        await self.db.refresh(clearance)

        return {
            "clearance_id": clearance.id,
            "type": "withdrawal",
            "fee_warning": fee_info["has_outstanding"] and not fee_override,
            "outstanding_fees": fee_info["total_outstanding"],
            "invoice_count": fee_info["invoice_count"],
        }

    async def get_withdrawal_clearance(
        self, tenant_id: UUID, student_id: UUID
    ) -> WithdrawalClearance | None:
        """Get the pending clearance for a student."""
        return await self._get_pending_clearance(tenant_id, student_id)

    async def update_clearance(
        self,
        tenant_id: UUID,
        clearance_id: UUID,
        student_id: UUID,
        **fields,
    ) -> WithdrawalClearance:
        """Update clearance checklist items.

        IDOR check: verifies clearance belongs to the specified student.
        Auto-completes when all required items are cleared.
        """
        result = await self.db.execute(
            select(WithdrawalClearance).where(
                and_(
                    # Defense-in-depth: filter by tenant_id
                    WithdrawalClearance.tenant_id == tenant_id,
                    WithdrawalClearance.id == clearance_id,
                    # IDOR prevention: ensure clearance belongs to this student
                    WithdrawalClearance.student_id == student_id,
                )
            )
        )
        clearance = result.scalar_one_or_none()
        if not clearance:
            raise StudentServiceError(
                "Clearance not found or does not belong to this student",
                code="clearance_not_found",
            )

        if clearance.is_complete:
            raise StudentServiceError(
                "Clearance has already been completed",
                code="clearance_already_complete",
            )

        # Apply provided fields
        allowed_fields = {
            "library_cleared", "finance_cleared", "property_cleared",
            "boarding_cleared", "notes",
        }
        for key, value in fields.items():
            if key in allowed_fields and value is not None:
                setattr(clearance, key, value)

        # Auto-complete: set is_complete when all required items are cleared
        required_cleared = (
            clearance.library_cleared
            and clearance.finance_cleared
            and clearance.property_cleared
        )
        # Boarding is only required if the student is a boarder (non-NULL value)
        if clearance.boarding_cleared is not None:
            required_cleared = required_cleared and clearance.boarding_cleared

        if required_cleared:
            clearance.is_complete = True

        await self.db.flush()
        await self.db.refresh(clearance)
        return clearance

    async def complete_withdrawal(
        self,
        tenant_id: UUID,
        student_id: UUID,
        performed_by: UUID,
    ) -> Student:
        """Finalize the withdrawal after clearance is complete.

        F-17: Creates the status change record HERE, not at initiation.
        Closes the class assignment and updates student status.
        """
        # Lock student for the status update
        student = await self._get_active_student_for_update(tenant_id, student_id)

        # Get and verify clearance
        clearance = await self._get_pending_clearance(tenant_id, student_id)
        if not clearance:
            raise StudentServiceError(
                "No pending clearance found. Initiate withdrawal first.",
                code="no_pending_clearance",
            )

        # Must be complete OR have fee_override
        if not clearance.is_complete and not clearance.fee_override:
            raise StudentServiceError(
                "Clearance is not complete. Clear all required items or use fee override.",
                code="clearance_incomplete",
            )

        effective_date = date_type.today()

        # Close class assignment if student has an active academic year enrollment
        await self._try_close_class_assignment(
            tenant_id, student_id, effective_date, "withdrawn"
        )

        # Create status change record (F-17: at completion, not initiation)
        status_change = await self.record_status_change(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=student.school_id,
            from_status=student.status.value,
            to_status=StudentStatus.WITHDRAWN.value,
            reason=clearance.notes,
            effective_date=effective_date,
            performed_by=performed_by,
            change_metadata={"type": "withdrawal", "clearance_id": str(clearance.id)},
        )

        # Update student status
        student.status = StudentStatus.WITHDRAWN
        student.updated_at = datetime.now(UTC)

        # Link clearance to status change and mark as cleared
        clearance.status_change_id = status_change.id
        clearance.cleared_by = performed_by
        clearance.cleared_at = datetime.now(UTC)
        clearance.is_complete = True

        await self.db.flush()
        await self.db.refresh(student)
        return student

    # ===========================
    # Transfer Flow (External)
    # ===========================

    async def initiate_transfer(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        destination_school: str,
        reason: str,
        effective_date: date_type,
        performed_by: UUID,
        fee_override: bool = False,
    ) -> dict:
        """Start an external transfer process.

        Same clearance flow as withdrawal but type='transfer' and
        destination school recorded in notes/metadata.
        """
        # Lock student to prevent race conditions
        student = await self._get_active_student_for_update(tenant_id, student_id)

        existing = await self._get_pending_clearance(tenant_id, student_id)
        if existing:
            raise StudentServiceError(
                "A pending withdrawal/transfer clearance already exists for this student",
                code="clearance_already_exists",
            )

        fee_info = await self.check_outstanding_fees(tenant_id, student_id)

        clearance = WithdrawalClearance(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            status_change_id=None,
            type="transfer",
            outstanding_fees=Decimal(str(fee_info["total_outstanding"])),
            fee_override=fee_override,
            boarding_cleared=None if not student.is_boarder else False,
            notes=f"Transfer to: {destination_school}. Reason: {reason}",
        )
        self.db.add(clearance)
        await self.db.flush()
        await self.db.refresh(clearance)

        return {
            "clearance_id": clearance.id,
            "type": "transfer",
            "destination_school": destination_school,
            "fee_warning": fee_info["has_outstanding"] and not fee_override,
            "outstanding_fees": fee_info["total_outstanding"],
            "invoice_count": fee_info["invoice_count"],
        }

    async def complete_transfer(
        self,
        tenant_id: UUID,
        student_id: UUID,
        performed_by: UUID,
    ) -> Student:
        """Finalize an external transfer.

        Same as complete_withdrawal but sets status to 'transferred'.
        """
        student = await self._get_active_student_for_update(tenant_id, student_id)

        clearance = await self._get_pending_clearance(tenant_id, student_id)
        if not clearance:
            raise StudentServiceError(
                "No pending clearance found. Initiate transfer first.",
                code="no_pending_clearance",
            )
        if clearance.type != "transfer":
            raise StudentServiceError(
                "Pending clearance is not a transfer",
                code="wrong_clearance_type",
            )
        if not clearance.is_complete and not clearance.fee_override:
            raise StudentServiceError(
                "Clearance is not complete. Clear all required items or use fee override.",
                code="clearance_incomplete",
            )

        effective_date = date_type.today()

        await self._try_close_class_assignment(
            tenant_id, student_id, effective_date, "transferred"
        )

        status_change = await self.record_status_change(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=student.school_id,
            from_status=student.status.value,
            to_status=StudentStatus.TRANSFERRED.value,
            reason=clearance.notes,
            effective_date=effective_date,
            performed_by=performed_by,
            change_metadata={"type": "transfer", "clearance_id": str(clearance.id)},
        )

        student.status = StudentStatus.TRANSFERRED
        student.updated_at = datetime.now(UTC)

        clearance.status_change_id = status_change.id
        clearance.cleared_by = performed_by
        clearance.cleared_at = datetime.now(UTC)
        clearance.is_complete = True

        await self.db.flush()
        await self.db.refresh(student)
        return student

    # ===========================
    # Chain Transfer (Intra-tenant)
    # ===========================

    async def transfer_within_chain(
        self,
        tenant_id: UUID,
        student_id: UUID,
        from_school_id: UUID,
        to_school_id: UUID,
        to_class_id: UUID,
        to_section_id: UUID | None,
        reason: str,
        effective_date: date_type,
        performed_by: UUID,
        fee_override: bool = False,
    ) -> Student:
        """Transfer a student between schools in the same chain.

        AD-5: Student remains ACTIVE -- only school/class/section change.
        F-12: Verify destination school belongs to the same tenant.
        """
        # Lock student
        student = await self._get_active_student_for_update(tenant_id, student_id)

        # Verify student is at the from_school
        if student.school_id != from_school_id:
            raise StudentServiceError(
                "Student is not enrolled at the specified source school",
                code="wrong_source_school",
            )

        # F-12: Verify destination school belongs to the same tenant
        dest_school_result = await self.db.execute(
            select(School).where(
                and_(
                    School.tenant_id == tenant_id,
                    School.id == to_school_id,
                    School.deleted_at.is_(None),
                )
            )
        )
        dest_school = dest_school_result.scalar_one_or_none()
        if not dest_school:
            raise StudentServiceError(
                "Destination school not found or does not belong to this tenant",
                code="invalid_destination_school",
            )

        # Verify destination class belongs to tenant
        dest_class_result = await self.db.execute(
            select(Class).where(
                and_(
                    Class.tenant_id == tenant_id,
                    Class.id == to_class_id,
                    Class.deleted_at.is_(None),
                )
            )
        )
        dest_class = dest_class_result.scalar_one_or_none()
        if not dest_class:
            raise StudentServiceError(
                "Destination class not found",
                code="invalid_destination_class",
            )

        # Verify destination section if provided
        if to_section_id:
            dest_section_result = await self.db.execute(
                select(ClassSection).where(
                    and_(
                        ClassSection.tenant_id == tenant_id,
                        ClassSection.id == to_section_id,
                        # IDOR check: section must belong to the destination class
                        ClassSection.class_id == to_class_id,
                    )
                )
            )
            dest_section = dest_section_result.scalar_one_or_none()
            if not dest_section:
                raise StudentServiceError(
                    "Destination section not found or does not belong to the destination class",
                    code="invalid_destination_section",
                )

        # Check outstanding fees (advisory)
        if not fee_override:
            fee_info = await self.check_outstanding_fees(tenant_id, student_id)
            if fee_info["has_outstanding"]:
                raise StudentServiceError(
                    f"Student has outstanding fees of {fee_info['total_outstanding']}. "
                    "Use fee_override=True to proceed.",
                    code="outstanding_fees",
                )

        # Close the class assignment at the source school
        await self._try_close_class_assignment(
            tenant_id, student_id, effective_date, "chain_transfer"
        )

        # Update student to new school/class/section (AD-5: stays active)
        student.school_id = to_school_id
        student.class_id = to_class_id
        student.section_id = to_section_id
        student.updated_at = datetime.now(UTC)

        # Create new class assignment at destination
        active_year = await self._get_active_academic_year(tenant_id)
        if active_year:
            await self.record_class_assignment(
                tenant_id=tenant_id,
                student_id=student_id,
                school_id=to_school_id,
                class_id=to_class_id,
                section_id=to_section_id,
                academic_year_id=active_year.id,
                enrolled_date=effective_date,
            )

        # Record the intra-chain transfer as a status change for audit trail
        await self.record_status_change(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=from_school_id,
            from_status=StudentStatus.ACTIVE.value,
            to_status=StudentStatus.ACTIVE.value,
            reason=reason,
            effective_date=effective_date,
            performed_by=performed_by,
            change_metadata={
                "type": "chain_transfer",
                "from_school_id": str(from_school_id),
                "to_school_id": str(to_school_id),
                "to_class_id": str(to_class_id),
                "to_section_id": str(to_section_id) if to_section_id else None,
            },
        )

        await self.db.flush()
        await self.db.refresh(student)
        return student

    # ===========================
    # Document Generation
    # ===========================

    async def generate_transfer_certificate(
        self, tenant_id: UUID, student_id: UUID
    ) -> bytes:
        """Generate a PDF transfer certificate.

        F-14: Uses Jinja2 autoescape and nh3.clean() to sanitize
        user-controlled content injected into the PDF template.
        """
        student = await self._load_student_for_document(tenant_id, student_id)
        school = await self._get_school(tenant_id, student.school_id)
        class_history = await self.get_class_history(tenant_id, student_id)
        latest_report = await self._get_latest_term_report(tenant_id, student_id)

        # Sanitize user-controlled content (F-14)
        context = {
            "student": student,
            "student_name": nh3.clean(student.full_name),
            "school": school,
            "school_name": nh3.clean(school.name) if school else "",
            "class_history": class_history,
            "latest_report": latest_report,
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "student_id": student.student_id,
            "date_of_birth": student.date_of_birth,
            "admission_date": student.admission_date,
            "class_name": nh3.clean(student.class_.name) if student.class_ else "",
        }

        return self._render_pdf("transfer_certificate.html", context)

    async def generate_withdrawal_letter(
        self, tenant_id: UUID, student_id: UUID
    ) -> bytes:
        """Generate a PDF withdrawal confirmation letter.

        F-14: Same HTML sanitization as transfer certificate.
        """
        student = await self._load_student_for_document(tenant_id, student_id)
        school = await self._get_school(tenant_id, student.school_id)

        # Get the most recent status change for withdrawal details
        status_history = await self.get_status_history(tenant_id, student_id)
        withdrawal_record = next(
            (r for r in status_history if r["to_status"] == "withdrawn"),
            None,
        )

        context = {
            "student": student,
            "student_name": nh3.clean(student.full_name),
            "school": school,
            "school_name": nh3.clean(school.name) if school else "",
            "withdrawal": withdrawal_record,
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "student_id": student.student_id,
            "class_name": nh3.clean(student.class_.name) if student.class_ else "",
        }

        return self._render_pdf("withdrawal_letter.html", context)

    async def export_student_record(
        self, tenant_id: UUID, student_id: UUID, format: str = "json"
    ) -> bytes:
        """Export a comprehensive student record.

        Includes personal info, class history, status history, and academic summary.
        Supports 'json' and 'pdf' formats.
        """
        student = await self._load_student_for_document(tenant_id, student_id)
        class_history = await self.get_class_history(tenant_id, student_id)
        status_history = await self.get_status_history(tenant_id, student_id)
        latest_report = await self._get_latest_term_report(tenant_id, student_id)
        fee_info = await self.check_outstanding_fees(tenant_id, student_id)

        record = {
            "student": {
                "id": str(student.id),
                "student_id": student.student_id,
                "first_name": student.first_name,
                "middle_name": student.middle_name,
                "last_name": student.last_name,
                "date_of_birth": str(student.date_of_birth),
                "gender": student.gender.value,
                "status": student.status.value,
                "email": student.email,
                "phone": student.phone,
                "address": student.address,
                "city": student.city,
                "region": student.region,
                "admission_date": str(student.admission_date) if student.admission_date else None,
                "school_name": student.school.name if student.school else None,
                "class_name": student.class_.name if student.class_ else None,
                "section_name": student.section.name if student.section else None,
            },
            "class_history": class_history,
            "status_history": status_history,
            "academic_summary": latest_report,
            "finance_summary": fee_info,
            "exported_at": datetime.now(UTC).isoformat(),
        }

        if format == "pdf":
            school = await self._get_school(tenant_id, student.school_id)
            context = {
                "student": student,
                "student_name": nh3.clean(student.full_name),
                "school": school,
                "school_name": nh3.clean(school.name) if school else "",
                "record": record,
                "class_history": class_history,
                "status_history": status_history,
                "latest_report": latest_report,
                "fee_info": fee_info,
                "current_date": datetime.now().strftime("%d/%m/%Y"),
            }
            return self._render_pdf("transfer_certificate.html", context)

        # JSON format
        return json.dumps(record, indent=2, default=str).encode("utf-8")

    # ===========================
    # Internal Helpers
    # ===========================

    async def _try_close_class_assignment(
        self,
        tenant_id: UUID,
        student_id: UUID,
        left_date: date_type,
        reason: str,
    ) -> None:
        """Close any active class assignment, silently skipping if none exists.

        Unlike close_class_assignment() which requires an academic_year_id and
        raises on missing assignments, this helper finds the active assignment
        (where left_date IS NULL) and closes it directly.
        """
        result = await self.db.execute(
            select(StudentClassHistory).where(
                and_(
                    StudentClassHistory.tenant_id == tenant_id,
                    StudentClassHistory.student_id == student_id,
                    StudentClassHistory.left_date.is_(None),
                )
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.left_date = left_date
            record.reason = reason
            await self.db.flush()

    async def _get_active_academic_year(
        self, tenant_id: UUID
    ) -> AcademicYear | None:
        """Get the current active academic year for the tenant."""
        result = await self.db.execute(
            select(AcademicYear).where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.status == "active",
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def _load_student_for_document(
        self, tenant_id: UUID, student_id: UUID
    ) -> Student:
        """Load a student with related data needed for document generation."""
        result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Student.school),
                selectinload(Student.class_),
                selectinload(Student.section),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")
        return student

    async def _get_school(
        self, tenant_id: UUID, school_id: UUID | None
    ) -> School | None:
        """Get a school by ID scoped to tenant."""
        if not school_id:
            return None
        result = await self.db.execute(
            select(School).where(
                and_(
                    School.tenant_id == tenant_id,
                    School.id == school_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_latest_term_report(
        self, tenant_id: UUID, student_id: UUID
    ) -> dict | None:
        """Get the most recent term report for academic summary."""
        from app.models.exam import TermReport

        result = await self.db.execute(
            select(TermReport)
            .where(
                and_(
                    TermReport.tenant_id == tenant_id,
                    TermReport.student_id == student_id,
                )
            )
            .order_by(TermReport.created_at.desc())
            .limit(1)
        )
        report = result.scalar_one_or_none()
        if not report:
            return None

        return {
            "term_id": str(report.term_id),
            "academic_year_id": str(report.academic_year_id),
            "total_score": float(report.total_score) if report.total_score else None,
            "average_score": float(report.average_score) if report.average_score else None,
            "class_position": report.class_position,
            "conduct": report.conduct,
            "interest": report.interest,
            "teacher_remarks": report.teacher_remarks,
            "head_teacher_remarks": report.head_teacher_remarks,
        }

    @staticmethod
    def _render_pdf(template_name: str, context: dict) -> bytes:
        """Render a Jinja2 template to PDF bytes.

        Uses autoescape=True for XSS prevention in generated HTML.
        """
        templates_dir = Path(__file__).parent.parent.parent / "templates" / "reports"
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )
        template = env.get_template(template_name)
        html_content = template.render(**context)

        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        return pdf_buffer.getvalue()
