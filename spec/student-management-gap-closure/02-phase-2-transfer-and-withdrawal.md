# Phase 2: Transfer & Withdrawal Workflows

**Covers:** SM-030 (Withdrawal), SM-031 (Transfer Certificate), SM-032 (Inter-School Transfer), SM-033 (Fee Check), SM-034 (Academic Record Portability)
**Priority:** Must
**Estimated Effort:** 5–6 days
**New Tables:** 1
**New Endpoints:** 10
**New Tests:** ~30
**PDF Templates:** 2
**Dependencies:** Phase 1 (needs `student_status_changes` and `student_class_history` tables)

---

## 1. Database Schema

### 1.1 New Table: `withdrawal_clearances`

A clearance checklist that must be completed (or bypassed) before a student withdrawal or external transfer is finalized. Created when a withdrawal/transfer is initiated, tracks clearance of each department.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | `uuid4()` | PK | |
| `tenant_id` | UUID | No | | FK `tenants.id` CASCADE | TenantMixin |
| `student_id` | UUID | No | | FK `students.id` CASCADE | |
| `school_id` | UUID | No | | FK `schools.id` CASCADE | |
| `status_change_id` | UUID | Yes | | FK `student_status_changes.id` CASCADE | Set when withdrawal/transfer is completed (status change created at completion, not initiation) |
| `type` | VARCHAR(20) | No | | | `withdrawal` or `transfer` |
| `library_cleared` | BOOLEAN | No | `false` | | Library books returned |
| `finance_cleared` | BOOLEAN | No | `false` | | Fees settled or waived |
| `property_cleared` | BOOLEAN | No | `false` | | School property returned (uniforms, devices) |
| `boarding_cleared` | BOOLEAN | Yes | | | NULL if not a boarder. Dormitory items returned |
| `outstanding_fees` | NUMERIC(12,2) | Yes | | | Snapshot of outstanding amount at initiation |
| `fee_override` | BOOLEAN | No | `false` | | Admin acknowledged and overrode fee warning |
| `notes` | TEXT | Yes | | | Admin notes for clearance |
| `is_complete` | BOOLEAN | No | `false` | | All required items cleared |
| `cleared_by` | UUID | Yes | | FK `users.id` SET NULL | User who completed clearance |
| `cleared_at` | TIMESTAMPTZ | Yes | | | When clearance was completed |
| `created_at` | TIMESTAMPTZ | No | `now()` | | |
| `updated_at` | TIMESTAMPTZ | No | `now()` | | |

**NOT using SoftDeleteMixin** — clearance records are part of the audit trail.

**Indexes:**

```sql
CREATE INDEX ix_wc_student ON withdrawal_clearances(student_id);
CREATE INDEX ix_wc_status_change ON withdrawal_clearances(status_change_id);
CREATE UNIQUE INDEX uq_wc_student_active ON withdrawal_clearances(student_id, tenant_id)
    WHERE is_complete = false;
```

**RLS Policy:**

```sql
ALTER TABLE withdrawal_clearances ENABLE ROW LEVEL SECURITY;
ALTER TABLE withdrawal_clearances FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON withdrawal_clearances
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON withdrawal_clearances TO sims_app_user;
```

---

## 2. Alembic Migration

**File:** `backend/alembic/versions/20260326_0400_withdrawal_transfer.py`

**Revision chain:** Revises `20260326_0300` (Phase 1).

```python
"""Add withdrawal clearances table for transfer/withdrawal workflows.

Revision ID: 20260326_0400
Revises: 20260326_0300
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260326_0400"
down_revision = "20260326_0300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "withdrawal_clearances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status_change_id", UUID(as_uuid=True), sa.ForeignKey("student_status_changes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, comment="withdrawal or transfer"),
        sa.CheckConstraint("type IN ('withdrawal', 'transfer')", name="ck_wc_type"),
        sa.Column("library_cleared", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("finance_cleared", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("property_cleared", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("boarding_cleared", sa.Boolean, nullable=True),
        sa.Column("outstanding_fees", sa.Numeric(12, 2), nullable=True),
        sa.Column("fee_override", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("cleared_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_index("ix_wc_student", "withdrawal_clearances", ["student_id"])
    op.create_index("ix_wc_status_change", "withdrawal_clearances", ["status_change_id"])
    op.execute("""
        CREATE UNIQUE INDEX uq_wc_student_active
        ON withdrawal_clearances(student_id, tenant_id)
        WHERE is_complete = false
    """)

    # RLS
    op.execute("ALTER TABLE withdrawal_clearances ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE withdrawal_clearances FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_withdrawal_clearances ON withdrawal_clearances
        FOR ALL TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON withdrawal_clearances TO sims_app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON withdrawal_clearances")
    op.drop_table("withdrawal_clearances")
```

---

## 3. SQLAlchemy Model

**File:** `backend/app/models/student.py`

Add after the `StudentStatusChange` model (from Phase 1):

```python
class WithdrawalClearance(Base, TenantMixin):
    """Clearance checklist for student withdrawal or external transfer.

    Created when a withdrawal/transfer is initiated. All required items
    must be cleared before the process can be completed.
    """
    __tablename__ = "withdrawal_clearances"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    status_change_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_status_changes.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="withdrawal or transfer",
    )
    library_cleared: Mapped[bool] = mapped_column(Boolean, default=False)
    finance_cleared: Mapped[bool] = mapped_column(Boolean, default=False)
    property_cleared: Mapped[bool] = mapped_column(Boolean, default=False)
    boarding_cleared: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="NULL if student is not a boarder",
    )
    outstanding_fees: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    fee_override: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    cleared_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cleared_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    status_change: Mapped["StudentStatusChange"] = relationship("StudentStatusChange", lazy="raise")
```

**Add import:** `from datetime import datetime` (if not already imported).

---

## 4. Pydantic Schemas

**File:** `backend/app/schemas/student.py`

### 4.1 Fee Check Schemas

```python
class OutstandingInvoiceSummary(BaseModel):
    """Summary of a single outstanding invoice."""
    invoice_id: UUID
    invoice_number: str
    amount: float
    balance: float
    status: str
    due_date: date_type | None = None


class OutstandingFeeCheckResponse(BaseModel):
    """Result of checking a student's outstanding fees."""
    has_outstanding: bool
    total_outstanding: float
    invoice_count: int
    invoices: list[OutstandingInvoiceSummary]
```

### 4.2 Withdrawal Schemas

```python
class WithdrawalInitiateRequest(BaseModel):
    """Request to initiate a student withdrawal."""
    reason: str = Field(..., min_length=5, max_length=1000)
    effective_date: date_type
    fee_override: bool = False  # Admin acknowledges outstanding fees

    @field_validator("effective_date")
    @classmethod
    def effective_date_not_in_past(cls, v: date_type) -> date_type:
        from datetime import date
        if v < date.today():
            raise ValueError("Effective date cannot be in the past")
        return v


class WithdrawalClearanceResponse(BaseModel):
    """Response schema for a withdrawal clearance record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    status_change_id: UUID
    type: str
    library_cleared: bool
    finance_cleared: bool
    property_cleared: bool
    boarding_cleared: bool | None = None
    outstanding_fees: float | None = None
    fee_override: bool
    notes: str | None = None
    is_complete: bool
    cleared_by: UUID | None = None
    cleared_at: str | None = None
    created_at: str


class WithdrawalClearanceUpdateRequest(BaseModel):
    """Request to update clearance items."""
    library_cleared: bool | None = None
    finance_cleared: bool | None = None
    property_cleared: bool | None = None
    boarding_cleared: bool | None = None
    notes: str | None = None


class WithdrawalCompleteResponse(BaseModel):
    """Response after completing a withdrawal."""
    student_id: UUID
    status: str
    clearance_completed: bool
    withdrawal_letter_available: bool
```

### 4.3 Transfer Schemas

```python
class TransferInitiateRequest(BaseModel):
    """Request to initiate an external student transfer."""
    destination_school: str = Field(..., min_length=2, max_length=255)
    reason: str = Field(..., min_length=5, max_length=1000)
    effective_date: date_type
    fee_override: bool = False

    @field_validator("effective_date")
    @classmethod
    def effective_date_not_in_past(cls, v: date_type) -> date_type:
        from datetime import date
        if v < date.today():
            raise ValueError("Effective date cannot be in the past")
        return v


class ChainTransferRequest(BaseModel):
    """Request to transfer a student between schools within the same chain."""
    to_school_id: UUID
    to_class_id: UUID
    to_section_id: UUID | None = None
    reason: str = Field(..., min_length=5, max_length=1000)
    effective_date: date_type
    fee_override: bool = False

    @field_validator("effective_date")
    @classmethod
    def effective_date_not_in_past(cls, v: date_type) -> date_type:
        from datetime import date
        if v < date.today():
            raise ValueError("Effective date cannot be in the past")
        return v


class ChainTransferResponse(BaseModel):
    """Response after completing a chain transfer."""
    student_id: UUID
    from_school_id: UUID
    to_school_id: UUID
    to_class_id: UUID
    status: str  # Should remain "active"
```

---

## 5. Service Layer

**File:** `backend/app/services/student/lifecycle_service.py` (new file)

### 5.1 StudentLifecycleMixin

```python
"""
SIMS Plus - Student Lifecycle Service

Handles withdrawal, transfer, and graduation workflows.
Generates transfer certificates, withdrawal letters, and academic record exports.
"""

from datetime import date, datetime, UTC
from decimal import Decimal
from io import BytesIO
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload, joinedload

from app.models.student import (
    Student, StudentStatus, StudentClassHistory, StudentStatusChange,
    WithdrawalClearance,
)
from app.models.finance.fee_models import Invoice
from app.models.academic import AcademicYear, Class, ClassSection
from app.models.school import School
from app.services.student._shared import StudentServiceError
from app.services.pdf import PDFService


class StudentLifecycleMixin:
    """Mixin for student withdrawal, transfer, and lifecycle management."""

    # ─── Outstanding Fee Check ───────────────────────────────────────

    async def check_outstanding_fees(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> dict:
        """Check if a student has outstanding fees.

        Queries all invoices with status in ('issued', 'sent', 'partially_paid', 'overdue')
        and sums the outstanding balance.

        Returns:
            Dictionary matching OutstandingFeeCheckResponse schema:
            {
                "has_outstanding": bool,
                "total_outstanding": float,
                "invoice_count": int,
                "invoices": [...]
            }
        """
        outstanding_statuses = ["issued", "sent", "partially_paid", "overdue"]

        stmt = (
            select(Invoice)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.student_id == student_id,
                Invoice.status.in_(outstanding_statuses),
            )
            .order_by(Invoice.created_at.asc())
        )
        result = await self.db.execute(stmt)
        invoices = list(result.scalars().all())

        total_outstanding = sum(
            float(inv.balance) for inv in invoices
        )

        return {
            "has_outstanding": total_outstanding > 0,
            "total_outstanding": round(total_outstanding, 2),
            "invoice_count": len(invoices),
            "invoices": [
                {
                    "invoice_id": str(inv.id),
                    "invoice_number": inv.invoice_number,
                    "amount": float(inv.total_amount),
                    "balance": float(inv.balance),
                    "status": inv.status,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                }
                for inv in invoices
            ],
        }

    # ─── Withdrawal ─────────────────────────────────────────────────

    async def initiate_withdrawal(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        reason: str,
        effective_date: date,
        performed_by: UUID,
        fee_override: bool = False,
    ) -> dict:
        """Initiate a student withdrawal.

        Steps:
        1. Lock student row (SELECT FOR UPDATE to prevent concurrent initiation)
        2. Verify student is active
        3. Check for existing pending withdrawal/transfer
        4. Check outstanding fees (warn if present)
        5. Create withdrawal clearance record
        6. Status change record is NOT created here — only at complete_withdrawal()

        Returns:
            Dictionary with clearance_id, fee_warning
        """
        # 1. Lock and verify student (SELECT FOR UPDATE prevents race condition)
        student = await self._get_active_student_for_update(tenant_id, student_id)

        # 2. Check for existing pending clearance
        existing = await self._get_pending_clearance(tenant_id, student_id)
        if existing:
            raise StudentServiceError(
                "Student already has a pending withdrawal or transfer",
                code="pending_clearance_exists",
            )

        # 3. Check fees
        fee_check = await self.check_outstanding_fees(tenant_id, student_id)

        # 4. Create clearance record (NO status change yet — that happens at complete_withdrawal)
        clearance = WithdrawalClearance(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            status_change_id=None,  # Set at complete_withdrawal() when status_change is created
            type="withdrawal",
            boarding_cleared=None if not student.is_boarder else False,
            outstanding_fees=Decimal(str(fee_check["total_outstanding"])),
            fee_override=fee_override,
        )
        self.db.add(clearance)
        await self.db.flush()
        await self.db.refresh(clearance)

        return {
            "clearance_id": str(clearance.id),
            "has_outstanding_fees": fee_check["has_outstanding"],
            "outstanding_amount": fee_check["total_outstanding"],
            "fee_override": fee_override,
        }

    async def get_withdrawal_clearance(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> WithdrawalClearance | None:
        """Get the current (pending) withdrawal clearance for a student.

        Returns None if no pending clearance exists.
        """
        return await self._get_pending_clearance(tenant_id, student_id)

    async def update_clearance(
        self,
        tenant_id: UUID,
        clearance_id: UUID,
        student_id: UUID,
        **fields,
    ) -> WithdrawalClearance:
        """Update clearance checklist items.

        IDOR check: verifies the clearance belongs to the specified student.

        Allowed fields: library_cleared, finance_cleared, property_cleared,
                        boarding_cleared, notes

        Automatically sets is_complete=True when all required items are cleared.
        """
        stmt = (
            select(WithdrawalClearance)
            .where(
                WithdrawalClearance.tenant_id == tenant_id,
                WithdrawalClearance.id == clearance_id,
                WithdrawalClearance.student_id == student_id,
            )
        )
        result = await self.db.execute(stmt)
        clearance = result.scalar_one_or_none()
        if not clearance:
            raise StudentServiceError(
                "Clearance not found",
                code="clearance_not_found",
            )

        allowed_fields = {"library_cleared", "finance_cleared", "property_cleared", "boarding_cleared", "notes"}
        for key, value in fields.items():
            if key in allowed_fields and value is not None:
                setattr(clearance, key, value)

        # Auto-complete check
        required = [clearance.library_cleared, clearance.finance_cleared, clearance.property_cleared]
        if clearance.boarding_cleared is not None:
            required.append(clearance.boarding_cleared)
        clearance.is_complete = all(required)

        await self.db.flush()
        await self.db.refresh(clearance)
        return clearance

    async def complete_withdrawal(
        self,
        tenant_id: UUID,
        student_id: UUID,
        performed_by: UUID,
    ) -> Student:
        """Complete a student withdrawal.

        Validates that all clearance items are done (or fee_override is set),
        then sets the student status to 'withdrawn'.

        Steps:
        1. Get pending clearance
        2. Verify clearance is complete (or allow override)
        3. Update student status to 'withdrawn'
        4. Close current class assignment
        5. Mark clearance as complete with cleared_by and cleared_at

        Returns:
            Updated Student object
        """
        clearance = await self._get_pending_clearance(tenant_id, student_id)
        if not clearance:
            raise StudentServiceError(
                "No pending withdrawal found for this student",
                code="no_pending_withdrawal",
            )

        if not clearance.is_complete and not clearance.fee_override:
            raise StudentServiceError(
                "Clearance is not complete. Clear all items or set fee override.",
                code="clearance_incomplete",
            )

        # Get student
        student = await self._get_active_student(tenant_id, student_id)

        # Update student status
        student.status = StudentStatus.WITHDRAWN
        await self.db.flush()

        # Close class assignment
        if student.class_id:
            # Get active academic year
            ay_stmt = select(AcademicYear.id).where(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.status == "active",
            ).limit(1)
            ay_result = await self.db.execute(ay_stmt)
            academic_year_id = ay_result.scalar_one_or_none()
            if academic_year_id:
                await self.close_class_assignment(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    academic_year_id=academic_year_id,
                    left_date=date.today(),
                    reason="withdrawn",
                )

        # Record the status change NOW (at completion, not initiation)
        status_change = await self.record_status_change(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=student.school_id,
            from_status=clearance_from_status,  # Captured before status update
            to_status="withdrawn",
            reason=clearance.notes or "Withdrawal completed",
            effective_date=date.today(),
            performed_by=performed_by,
            change_metadata={
                "withdrawal_type": "voluntary",
                "fee_override": clearance.fee_override,
                "outstanding_amount": str(clearance.outstanding_fees) if clearance.outstanding_fees else "0.00",
                "clearance_id": str(clearance.id),
            },
        )

        # Mark clearance complete and link to status change
        clearance.is_complete = True
        clearance.status_change_id = status_change.id
        clearance.cleared_by = performed_by
        clearance.cleared_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(student)
        return student

    # ─── External Transfer ──────────────────────────────────────────

    async def initiate_transfer(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        destination_school: str,
        reason: str,
        effective_date: date,
        performed_by: UUID,
        fee_override: bool = False,
    ) -> dict:
        """Initiate an external student transfer (leaving the platform).

        Same workflow as withdrawal but with type='transfer' and
        destination school recorded in metadata.
        """
        student = await self._get_active_student(tenant_id, student_id)

        existing = await self._get_pending_clearance(tenant_id, student_id)
        if existing:
            raise StudentServiceError(
                "Student already has a pending withdrawal or transfer",
                code="pending_clearance_exists",
            )

        fee_check = await self.check_outstanding_fees(tenant_id, student_id)

        status_change = await self.record_status_change(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            from_status=student.status.value if hasattr(student.status, 'value') else str(student.status),
            to_status="transferred",
            reason=reason,
            effective_date=effective_date,
            performed_by=performed_by,
            metadata={
                "transfer_type": "external",
                "destination_school": destination_school,
                "fee_override": fee_override,
                "outstanding_amount": str(fee_check["total_outstanding"]),
                "status": "pending_clearance",
            },
        )

        clearance = WithdrawalClearance(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            status_change_id=status_change.id,
            type="transfer",
            boarding_cleared=None if not student.is_boarder else False,
            outstanding_fees=Decimal(str(fee_check["total_outstanding"])),
            fee_override=fee_override,
        )
        self.db.add(clearance)
        await self.db.flush()
        await self.db.refresh(clearance)

        return {
            "status_change_id": str(status_change.id),
            "clearance_id": str(clearance.id),
            "has_outstanding_fees": fee_check["has_outstanding"],
            "outstanding_amount": fee_check["total_outstanding"],
            "destination_school": destination_school,
        }

    async def complete_transfer(
        self,
        tenant_id: UUID,
        student_id: UUID,
        performed_by: UUID,
    ) -> Student:
        """Complete an external transfer. Same flow as complete_withdrawal but sets status to 'transferred'."""
        clearance = await self._get_pending_clearance(tenant_id, student_id)
        if not clearance:
            raise StudentServiceError("No pending transfer found", code="no_pending_transfer")

        if clearance.type != "transfer":
            raise StudentServiceError("Pending clearance is not a transfer", code="wrong_clearance_type")

        if not clearance.is_complete and not clearance.fee_override:
            raise StudentServiceError("Clearance is not complete", code="clearance_incomplete")

        student = await self._get_active_student(tenant_id, student_id)
        student.status = StudentStatus.TRANSFERRED
        await self.db.flush()

        # Close class assignment
        if student.class_id:
            ay_stmt = select(AcademicYear.id).where(
                AcademicYear.tenant_id == tenant_id, AcademicYear.status == "active"
            ).limit(1)
            ay_result = await self.db.execute(ay_stmt)
            academic_year_id = ay_result.scalar_one_or_none()
            if academic_year_id:
                await self.close_class_assignment(
                    tenant_id=tenant_id, student_id=student_id,
                    academic_year_id=academic_year_id,
                    left_date=date.today(), reason="transferred",
                )

        clearance.is_complete = True
        clearance.cleared_by = performed_by
        clearance.cleared_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(student)
        return student

    # ─── Inter-School Chain Transfer ────────────────────────────────

    async def transfer_within_chain(
        self,
        tenant_id: UUID,
        student_id: UUID,
        from_school_id: UUID,
        to_school_id: UUID,
        to_class_id: UUID,
        to_section_id: UUID | None,
        reason: str,
        effective_date: date,
        performed_by: UUID,
        fee_override: bool = False,
    ) -> Student:
        """Transfer a student between schools within the same chain (tenant).

        Key difference from external transfer:
        - Student status remains ACTIVE (not set to 'transferred')
        - Student record is updated in place (school_id, class_id, section_id)
        - No clearance checklist required (both schools are under same admin)

        Steps:
        1. Verify student exists and is active at from_school
        2. Verify to_school exists and belongs to same tenant
        3. Verify to_class exists at to_school
        4. Check outstanding fees (warn but allow override)
        5. Close class assignment at from_school
        6. Update student's school_id, class_id, section_id
        7. Create new class assignment at to_school
        8. Record status change with intra_chain metadata
        """
        # 1. Verify student
        student = await self._get_active_student(tenant_id, student_id)
        if student.school_id != from_school_id:
            raise StudentServiceError("Student does not belong to the source school", code="wrong_school")

        # 2. Verify destination school
        dest_school = await self.db.execute(
            select(School).where(School.tenant_id == tenant_id, School.id == to_school_id)
        )
        if not dest_school.scalar_one_or_none():
            raise StudentServiceError("Destination school not found in this tenant", code="school_not_found")

        # 3. Verify destination class
        dest_class = await self.db.execute(
            select(Class).where(Class.tenant_id == tenant_id, Class.id == to_class_id)
        )
        if not dest_class.scalar_one_or_none():
            raise StudentServiceError("Destination class not found", code="class_not_found")

        # 4. Fee check
        fee_check = await self.check_outstanding_fees(tenant_id, student_id)
        if fee_check["has_outstanding"] and not fee_override:
            raise StudentServiceError(
                f"Student has outstanding fees of {fee_check['total_outstanding']}. Set fee_override=true to proceed.",
                code="outstanding_fees",
            )

        # 5. Close current class assignment
        ay_stmt = select(AcademicYear.id).where(
            AcademicYear.tenant_id == tenant_id, AcademicYear.status == "active"
        ).limit(1)
        ay_result = await self.db.execute(ay_stmt)
        academic_year_id = ay_result.scalar_one_or_none()

        if academic_year_id and student.class_id:
            await self.close_class_assignment(
                tenant_id=tenant_id, student_id=student_id,
                academic_year_id=academic_year_id,
                left_date=effective_date, reason="transferred",
            )

        # 6. Update student
        student.school_id = to_school_id
        student.class_id = to_class_id
        student.section_id = to_section_id
        # Status remains ACTIVE — this is an intra-chain transfer
        await self.db.flush()

        # 7. Create new class assignment
        if academic_year_id:
            await self.record_class_assignment(
                tenant_id=tenant_id, student_id=student_id,
                school_id=to_school_id, class_id=to_class_id,
                section_id=to_section_id, academic_year_id=academic_year_id,
                enrolled_date=effective_date,
            )

        # 8. Record status change (status doesn't change but we record the event)
        await self.record_status_change(
            tenant_id=tenant_id, student_id=student_id,
            school_id=from_school_id,
            from_status="active", to_status="active",
            reason=reason, effective_date=effective_date,
            performed_by=performed_by,
            metadata={
                "transfer_type": "intra_chain",
                "from_school_id": str(from_school_id),
                "to_school_id": str(to_school_id),
                "to_class_id": str(to_class_id),
                "fee_override": fee_override,
                "outstanding_amount": str(fee_check["total_outstanding"]),
            },
        )

        await self.db.refresh(student)
        return student

    # ─── PDF Generation ─────────────────────────────────────────────

    async def generate_transfer_certificate(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> BytesIO:
        """Generate a transfer certificate PDF for a student.

        The certificate includes:
        - School letterhead (name, logo, address)
        - Student personal details (name, DOB, student ID, photo)
        - Class history (all classes attended with dates)
        - Academic summary (last term's grades if available)
        - Conduct remark
        - Date of transfer
        - Signature block

        Uses the template at backend/app/templates/reports/transfer_certificate.html
        """
        # Load student with relationships
        student = await self._get_student_with_details(tenant_id, student_id)
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")

        # Load class history
        class_history = await self.get_class_history(tenant_id, student_id)

        # Load school
        school_stmt = select(School).where(School.tenant_id == tenant_id, School.id == student.school_id)
        school_result = await self.db.execute(school_stmt)
        school = school_result.scalar_one_or_none()

        # Load last term report (if available) — best effort
        last_report = await self._get_last_term_report(tenant_id, student_id)

        # Get status change for transfer date
        transfer_change = await self._get_last_status_change(tenant_id, student_id, "transferred")

        context = {
            "student": student,
            "school": school,
            "class_history": class_history,
            "last_report": last_report,
            "transfer_date": transfer_change.effective_date if transfer_change else date.today(),
            "transfer_reason": transfer_change.reason if transfer_change else None,
            "destination": (
                transfer_change.metadata.get("destination_school")
                if transfer_change and transfer_change.metadata
                else None
            ),
        }

        pdf_service = PDFService()
        return pdf_service.render_template("reports/transfer_certificate.html", context)

    async def generate_withdrawal_letter(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> BytesIO:
        """Generate a withdrawal letter PDF for a student.

        The letter includes:
        - School letterhead
        - Student name and ID
        - Effective date of withdrawal
        - Reason for withdrawal
        - Clearance status summary
        - Signature block

        Uses the template at backend/app/templates/reports/withdrawal_letter.html
        """
        student = await self._get_student_with_details(tenant_id, student_id)
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")

        school_stmt = select(School).where(School.tenant_id == tenant_id, School.id == student.school_id)
        school_result = await self.db.execute(school_stmt)
        school = school_result.scalar_one_or_none()

        withdrawal_change = await self._get_last_status_change(tenant_id, student_id, "withdrawn")

        # Get clearance
        clearance_stmt = (
            select(WithdrawalClearance)
            .where(
                WithdrawalClearance.tenant_id == tenant_id,
                WithdrawalClearance.student_id == student_id,
            )
            .order_by(WithdrawalClearance.created_at.desc())
            .limit(1)
        )
        clearance_result = await self.db.execute(clearance_stmt)
        clearance = clearance_result.scalar_one_or_none()

        context = {
            "student": student,
            "school": school,
            "effective_date": withdrawal_change.effective_date if withdrawal_change else date.today(),
            "reason": withdrawal_change.reason if withdrawal_change else None,
            "clearance": clearance,
        }

        pdf_service = PDFService()
        return pdf_service.render_template("reports/withdrawal_letter.html", context)

    async def export_student_record(
        self,
        tenant_id: UUID,
        student_id: UUID,
        format: str = "pdf",
    ) -> BytesIO:
        """Export a complete student academic record for portability.

        Includes:
        - Personal details
        - Guardian information
        - Class history
        - Status change timeline
        - Academic records (exam scores, term reports)
        - Attendance summary

        Args:
            format: "pdf" or "json"
        """
        student = await self._get_student_with_details(tenant_id, student_id)
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")

        class_history = await self.get_class_history(tenant_id, student_id)
        status_history = await self.get_status_history(tenant_id, student_id)
        guardians = await self.get_student_guardians(tenant_id, student_id)

        school_stmt = select(School).where(School.tenant_id == tenant_id, School.id == student.school_id)
        school = (await self.db.execute(school_stmt)).scalar_one_or_none()

        # Load term reports
        from app.models.exam import TermReport
        reports_stmt = (
            select(TermReport)
            .where(TermReport.tenant_id == tenant_id, TermReport.student_id == student_id)
            .order_by(TermReport.created_at.desc())
        )
        term_reports = list((await self.db.execute(reports_stmt)).scalars().all())

        if format == "json":
            import json
            data = {
                "student": {
                    "student_id": student.student_id,
                    "name": student.full_name,
                    "date_of_birth": student.date_of_birth.isoformat(),
                    "gender": student.gender.value if hasattr(student.gender, 'value') else str(student.gender),
                    "ghana_card_number": student.ghana_card_number,
                    "nhis_number": student.nhis_number,
                },
                "school": {"name": school.name if school else None},
                "guardians": [
                    {
                        "name": f"{g.guardian.first_name} {g.guardian.last_name}" if g.guardian else None,
                        "relationship": g.relationship,
                        "phone": g.guardian.phone if g.guardian else None,
                        "is_primary": g.is_primary,
                    }
                    for g in guardians
                ],
                "class_history": [
                    {
                        "class": r.class_.name if r.class_ else None,
                        "section": r.section.name if r.section else None,
                        "academic_year": r.academic_year.name if r.academic_year else None,
                        "enrolled_date": r.enrolled_date.isoformat(),
                        "left_date": r.left_date.isoformat() if r.left_date else None,
                        "reason": r.reason,
                    }
                    for r in class_history
                ],
                "status_history": [
                    {
                        "from": r.from_status,
                        "to": r.to_status,
                        "reason": r.reason,
                        "date": r.effective_date.isoformat(),
                    }
                    for r in status_history
                ],
                "exported_at": datetime.now(UTC).isoformat(),
            }
            buffer = BytesIO()
            buffer.write(json.dumps(data, indent=2).encode("utf-8"))
            buffer.seek(0)
            return buffer
        else:
            # PDF export
            context = {
                "student": student,
                "school": school,
                "guardians": guardians,
                "class_history": class_history,
                "status_history": status_history,
                "term_reports": term_reports,
            }
            pdf_service = PDFService()
            return pdf_service.render_template("reports/academic_record_export.html", context)

    # ─── Private Helpers ────────────────────────────────────────────

    async def _get_active_student(self, tenant_id: UUID, student_id: UUID) -> Student:
        """Get a student and verify they are active."""
        stmt = (
            select(Student)
            .where(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        student = result.scalar_one_or_none()
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")
        if student.status != StudentStatus.ACTIVE:
            raise StudentServiceError(
                f"Student is not active (current status: {student.status})",
                code="student_not_active",
            )
        return student

    async def _get_pending_clearance(self, tenant_id: UUID, student_id: UUID) -> WithdrawalClearance | None:
        """Get the pending (incomplete) clearance for a student."""
        stmt = (
            select(WithdrawalClearance)
            .where(
                WithdrawalClearance.tenant_id == tenant_id,
                WithdrawalClearance.student_id == student_id,
                WithdrawalClearance.is_complete == False,
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_student_with_details(self, tenant_id: UUID, student_id: UUID) -> Student | None:
        """Get a student with school, class, and section eagerly loaded."""
        stmt = (
            select(Student)
            .options(
                joinedload(Student.school),
                joinedload(Student.class_),
                joinedload(Student.section),
            )
            .where(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def _get_last_status_change(
        self, tenant_id: UUID, student_id: UUID, to_status: str
    ) -> StudentStatusChange | None:
        """Get the most recent status change to a specific status."""
        stmt = (
            select(StudentStatusChange)
            .where(
                StudentStatusChange.tenant_id == tenant_id,
                StudentStatusChange.student_id == student_id,
                StudentStatusChange.to_status == to_status,
            )
            .order_by(StudentStatusChange.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_last_term_report(self, tenant_id: UUID, student_id: UUID):
        """Get the most recent term report for a student. Best effort."""
        try:
            from app.models.exam import TermReport
            stmt = (
                select(TermReport)
                .where(
                    TermReport.tenant_id == tenant_id,
                    TermReport.student_id == student_id,
                )
                .order_by(TermReport.created_at.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception:
            return None
```

### 5.2 Update `__init__.py`

```python
# backend/app/services/student/__init__.py
from app.services.student.lifecycle_service import StudentLifecycleMixin

class StudentService(
    StudentCoreMixin,
    StudentImportMixin,
    StudentGuardianMixin,
    StudentHistoryMixin,      # Phase 1
    StudentLifecycleMixin,    # Phase 2
):
    def __init__(self, db: AsyncSession):
        self.db = db
```

---

## 6. PDF Templates

### 6.1 Transfer Certificate Template

**File:** `backend/app/templates/reports/transfer_certificate.html`

Uses the existing Jinja2 + WeasyPrint pattern from `backend/app/templates/reports/`.

**Template structure:**

```html
<!-- Extends or includes the base report layout -->
<!-- A4 portrait, school letterhead -->

<div class="certificate">
  <!-- Header: School logo, name, address, contact -->
  <div class="header">
    <img src="{{ school.logo_url }}" />
    <h1>{{ school.name }}</h1>
    <p>{{ school.address }}</p>
  </div>

  <h2>TRANSFER CERTIFICATE</h2>
  <p>Certificate No: TC-{{ student.student_id }}-{{ transfer_date.strftime('%Y%m%d') }}</p>

  <!-- Student Details -->
  <table class="details">
    <tr><td>Student Name:</td><td>{{ student.full_name }}</td></tr>
    <tr><td>Student ID:</td><td>{{ student.student_id }}</td></tr>
    <tr><td>Date of Birth:</td><td>{{ student.date_of_birth.strftime('%d/%m/%Y') }}</td></tr>
    <tr><td>Date of Admission:</td><td>{{ student.admission_date.strftime('%d/%m/%Y') if student.admission_date else 'N/A' }}</td></tr>
    <tr><td>Date of Transfer:</td><td>{{ transfer_date.strftime('%d/%m/%Y') }}</td></tr>
    {% if destination %}
    <tr><td>Transferring To:</td><td>{{ destination }}</td></tr>
    {% endif %}
    <tr><td>Reason:</td><td>{{ transfer_reason or 'Transfer requested' }}</td></tr>
  </table>

  <!-- Class History -->
  <h3>Academic History</h3>
  <table class="history">
    <thead>
      <tr><th>Academic Year</th><th>Class</th><th>Section</th><th>From</th><th>To</th></tr>
    </thead>
    <tbody>
      {% for record in class_history %}
      <tr>
        <td>{{ record.academic_year.name }}</td>
        <td>{{ record.class_.name }}</td>
        <td>{{ record.section.name if record.section else '-' }}</td>
        <td>{{ record.enrolled_date.strftime('%d/%m/%Y') }}</td>
        <td>{{ record.left_date.strftime('%d/%m/%Y') if record.left_date else 'Present' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <!-- Academic Summary (Last Term) -->
  {% if last_report %}
  <h3>Last Term Performance</h3>
  <p>Term Average: {{ last_report.average }}% | Position: {{ last_report.position }}</p>
  {% endif %}

  <!-- Conduct -->
  <h3>Conduct & Character</h3>
  <p>{{ last_report.conduct if last_report and last_report.conduct else 'Good' }}</p>

  <!-- Signature Block -->
  <div class="signatures">
    <div class="signature-block">
      <div class="line"></div>
      <p>Headmaster/Headmistress</p>
      <p>Date: {{ transfer_date.strftime('%d/%m/%Y') }}</p>
    </div>
    <div class="signature-block">
      <div class="line"></div>
      <p>School Stamp</p>
    </div>
  </div>
</div>
```

### 6.2 Withdrawal Letter Template

**File:** `backend/app/templates/reports/withdrawal_letter.html`

```html
<div class="letter">
  <!-- Header: School letterhead -->
  <div class="header">
    <img src="{{ school.logo_url }}" />
    <h1>{{ school.name }}</h1>
    <p>{{ school.address }}</p>
  </div>

  <p class="date">Date: {{ effective_date.strftime('%d/%m/%Y') }}</p>

  <h2>LETTER OF WITHDRAWAL</h2>

  <p>This is to certify that <strong>{{ student.full_name }}</strong>
  (Student ID: {{ student.student_id }}) has been officially withdrawn
  from {{ school.name }} effective {{ effective_date.strftime('%d %B %Y') }}.</p>

  {% if reason %}
  <p><strong>Reason for Withdrawal:</strong> {{ reason }}</p>
  {% endif %}

  <!-- Clearance Summary -->
  {% if clearance %}
  <h3>Clearance Summary</h3>
  <table>
    <tr><td>Library:</td><td>{{ 'Cleared' if clearance.library_cleared else 'Pending' }}</td></tr>
    <tr><td>Finance:</td><td>{{ 'Cleared' if clearance.finance_cleared else 'Pending' }}</td></tr>
    <tr><td>School Property:</td><td>{{ 'Cleared' if clearance.property_cleared else 'Pending' }}</td></tr>
    {% if clearance.boarding_cleared is not none %}
    <tr><td>Boarding:</td><td>{{ 'Cleared' if clearance.boarding_cleared else 'Pending' }}</td></tr>
    {% endif %}
  </table>
  {% endif %}

  <!-- Signature -->
  <div class="signatures">
    <div class="signature-block">
      <div class="line"></div>
      <p>Headmaster/Headmistress</p>
    </div>
    <div class="signature-block">
      <div class="line"></div>
      <p>School Stamp</p>
    </div>
  </div>
</div>
```

---

## 7. API Endpoints

**File:** `backend/app/api/v1/endpoints/students.py`

### 7.1 GET `/students/{student_id}/fees/outstanding`

```python
@router.get("/students/{student_id}/fees/outstanding")
async def check_outstanding_fees(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read", "finance.read")),
):
    """Check if a student has outstanding fees."""
    service = StudentService(db)
    return await service.check_outstanding_fees(user["tenant_id"], student_id)
```

### 7.2 POST `/students/{student_id}/withdraw`

```python
@router.post("/students/{student_id}/withdraw")
async def initiate_withdrawal(
    student_id: UUID,
    request: WithdrawalInitiateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Initiate a student withdrawal.

    Creates a clearance checklist that must be completed before
    the withdrawal is finalized. Returns fee warning if applicable.
    """
    service = StudentService(db)
    try:
        result = await service.initiate_withdrawal(
            tenant_id=user["tenant_id"],
            student_id=student_id,
            school_id=user.get("school_id"),
            reason=request.reason,
            effective_date=request.effective_date,
            performed_by=user["user_id"],
            fee_override=request.fee_override,
        )
        return result
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.3 GET `/students/{student_id}/clearance`

```python
@router.get("/students/{student_id}/clearance")
async def get_clearance(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Get the pending withdrawal/transfer clearance for a student."""
    service = StudentService(db)
    clearance = await service.get_withdrawal_clearance(user["tenant_id"], student_id)
    if not clearance:
        raise HTTPException(status_code=404, detail="No pending clearance found")
    # Return clearance as WithdrawalClearanceResponse
    return { ... }  # Map clearance fields to response
```

### 7.4 PUT `/students/{student_id}/clearance/{clearance_id}`

```python
@router.put("/students/{student_id}/clearance/{clearance_id}")
async def update_clearance(
    student_id: UUID,
    clearance_id: UUID,
    request: WithdrawalClearanceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Update clearance checklist items. Auto-completes when all items are cleared."""
    service = StudentService(db)
    try:
        clearance = await service.update_clearance(
            tenant_id=user["tenant_id"],
            clearance_id=clearance_id,
            student_id=student_id,
            **request.model_dump(exclude_unset=True),
        )
        return { ... }  # Map clearance fields to response
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.5 POST `/students/{student_id}/withdraw/complete`

```python
@router.post("/students/{student_id}/withdraw/complete")
async def complete_withdrawal(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Complete a student withdrawal after clearance is done."""
    service = StudentService(db)
    try:
        student = await service.complete_withdrawal(
            tenant_id=user["tenant_id"],
            student_id=student_id,
            performed_by=user["user_id"],
        )
        return {
            "student_id": str(student.id),
            "status": student.status.value,
            "clearance_completed": True,
            "withdrawal_letter_available": True,
        }
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.6 POST `/students/{student_id}/transfer`

```python
@router.post("/students/{student_id}/transfer")
async def initiate_transfer(
    student_id: UUID,
    request: TransferInitiateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Initiate an external student transfer."""
    service = StudentService(db)
    try:
        result = await service.initiate_transfer(
            tenant_id=user["tenant_id"],
            student_id=student_id,
            school_id=user.get("school_id"),
            destination_school=request.destination_school,
            reason=request.reason,
            effective_date=request.effective_date,
            performed_by=user["user_id"],
            fee_override=request.fee_override,
        )
        return result
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.7 POST `/students/{student_id}/transfer/chain`

```python
@router.post("/students/{student_id}/transfer/chain")
async def chain_transfer(
    student_id: UUID,
    request: ChainTransferRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Transfer a student between schools within the same chain.

    Requires Enterprise plan with multi-school feature.
    """
    # Check enterprise/chain feature
    # ...

    service = StudentService(db)
    try:
        student = await service.transfer_within_chain(
            tenant_id=user["tenant_id"],
            student_id=student_id,
            from_school_id=user.get("school_id"),
            to_school_id=request.to_school_id,
            to_class_id=request.to_class_id,
            to_section_id=request.to_section_id,
            reason=request.reason,
            effective_date=request.effective_date,
            performed_by=user["user_id"],
            fee_override=request.fee_override,
        )
        return {
            "student_id": str(student.id),
            "from_school_id": str(user.get("school_id")),
            "to_school_id": str(request.to_school_id),
            "to_class_id": str(request.to_class_id),
            "status": "active",
        }
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.8 GET `/students/{student_id}/transfer-certificate`

```python
@router.get("/students/{student_id}/transfer-certificate")
async def download_transfer_certificate(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Generate and download a transfer certificate PDF.

    Rate limited to 5 requests per minute.
    """
    service = StudentService(db)
    try:
        pdf_buffer = await service.generate_transfer_certificate(user["tenant_id"], student_id)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=transfer_certificate_{student_id}.pdf"},
        )
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.9 GET `/students/{student_id}/withdrawal-letter`

```python
@router.get("/students/{student_id}/withdrawal-letter")
async def download_withdrawal_letter(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Generate and download a withdrawal letter PDF."""
    service = StudentService(db)
    try:
        pdf_buffer = await service.generate_withdrawal_letter(user["tenant_id"], student_id)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=withdrawal_letter_{student_id}.pdf"},
        )
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.10 GET `/students/{student_id}/academic-record`

```python
@router.get("/students/{student_id}/academic-record")
async def download_academic_record(
    student_id: UUID,
    format: str = Query("pdf", regex="^(pdf|json)$"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Export a complete student academic record.

    Supports PDF and JSON formats.
    Professional and Enterprise plans only.
    """
    service = StudentService(db)
    try:
        buffer = await service.export_student_record(user["tenant_id"], student_id, format=format)
        media_type = "application/pdf" if format == "pdf" else "application/json"
        ext = format
        return StreamingResponse(
            buffer,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=academic_record_{student_id}.{ext}"},
        )
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

---

## 8. Frontend Changes

### 8.1 TypeScript Types

**File:** `frontend/types/index.ts`

```typescript
// Withdrawal & Transfer
export interface OutstandingInvoiceSummary {
  invoice_id: string;
  invoice_number: string;
  amount: number;
  balance: number;
  status: string;
  due_date: string | null;
}

export interface OutstandingFeeCheck {
  has_outstanding: boolean;
  total_outstanding: number;
  invoice_count: number;
  invoices: OutstandingInvoiceSummary[];
}

export interface WithdrawalClearance {
  id: string;
  student_id: string;
  status_change_id: string;
  type: "withdrawal" | "transfer";
  library_cleared: boolean;
  finance_cleared: boolean;
  property_cleared: boolean;
  boarding_cleared: boolean | null;
  outstanding_fees: number | null;
  fee_override: boolean;
  notes: string | null;
  is_complete: boolean;
  cleared_by: string | null;
  cleared_at: string | null;
  created_at: string;
}

export interface WithdrawalInitiateRequest {
  reason: string;
  effective_date: string;
  fee_override?: boolean;
}

export interface TransferInitiateRequest {
  destination_school: string;
  reason: string;
  effective_date: string;
  fee_override?: boolean;
}

export interface ChainTransferRequest {
  to_school_id: string;
  to_class_id: string;
  to_section_id?: string;
  reason: string;
  effective_date: string;
  fee_override?: boolean;
}
```

### 8.2 Server Actions

**File:** `frontend/actions/students.action.ts`

Add these functions:

```typescript
export async function checkOutstandingFees(studentId: string): Promise<ActionResult<OutstandingFeeCheck>> { ... }
export async function initiateWithdrawal(studentId: string, data: WithdrawalInitiateRequest): Promise<ActionResult<any>> { ... }
export async function getClearance(studentId: string): Promise<ActionResult<WithdrawalClearance>> { ... }
export async function updateClearance(studentId: string, clearanceId: string, data: Partial<WithdrawalClearance>): Promise<ActionResult<WithdrawalClearance>> { ... }
export async function completeWithdrawal(studentId: string): Promise<ActionResult<any>> { ... }
export async function initiateTransfer(studentId: string, data: TransferInitiateRequest): Promise<ActionResult<any>> { ... }
export async function chainTransfer(studentId: string, data: ChainTransferRequest): Promise<ActionResult<any>> { ... }
export async function downloadTransferCertificate(studentId: string): Promise<ActionResult<Blob>> { ... }
export async function downloadWithdrawalLetter(studentId: string): Promise<ActionResult<Blob>> { ... }
export async function downloadAcademicRecord(studentId: string, format?: "pdf" | "json"): Promise<ActionResult<Blob>> { ... }
```

### 8.3 Frontend Components

#### Withdrawal Dialog (`students/[id]/withdraw-dialog.tsx`)

A multi-step dialog:

1. **Step 1 — Reason & Date:**
   - Reason textarea (required, min 5 chars)
   - Effective date picker (must be today or future)
   - Fee warning card (shows outstanding amount if any, with acknowledge checkbox)
2. **Step 2 — Clearance Checklist:**
   - Toggle switches for: Library, Finance, Property, Boarding (if applicable)
   - Notes textarea
   - Auto-complete detection
3. **Step 3 — Confirm:**
   - Summary of withdrawal details
   - "Complete Withdrawal" button (disabled if clearance incomplete and no fee override)

#### Transfer Dialog (`students/[id]/transfer-dialog.tsx`)

Two tabs within the dialog:

**External Transfer tab:**
- Destination school name (text input)
- Reason, effective date, fee check (same as withdrawal)

**Chain Transfer tab (Enterprise only):**
- Destination school dropdown (populated from chain schools)
- Target class dropdown (populated from destination school's classes)
- Target section dropdown (optional)
- Reason, effective date, fee check

#### Download Dropdown (`students/[id]/download-menu.tsx`)

A dropdown button on the student detail page with options:
- "Transfer Certificate" (visible when status = transferred)
- "Withdrawal Letter" (visible when status = withdrawn)
- "Academic Record (PDF)" (always visible, Professional+ only)
- "Academic Record (JSON)" (always visible, Professional+ only)

---

## 9. Test Plan

### 9.1 `tests/test_student_withdrawal.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_initiate_withdrawal_success` | Unit | Initiate for active student, creates clearance + status change |
| 2 | `test_initiate_withdrawal_inactive_student` | Unit | Fails for non-active student |
| 3 | `test_initiate_withdrawal_duplicate` | Unit | Fails when pending clearance already exists |
| 4 | `test_initiate_withdrawal_with_fees` | Unit | Returns fee warning, logs fee_override in metadata |
| 5 | `test_update_clearance` | Unit | Update individual clearance items |
| 6 | `test_update_clearance_auto_complete` | Unit | is_complete set to True when all items cleared |
| 7 | `test_update_clearance_idor` | Security | Cannot update clearance for a different student |
| 8 | `test_complete_withdrawal_success` | Integration | Full workflow: initiate → clear items → complete |
| 9 | `test_complete_withdrawal_incomplete` | Unit | Fails when clearance not complete and no fee_override |
| 10 | `test_complete_withdrawal_with_fee_override` | Unit | Succeeds when fee_override is set despite pending items |
| 11 | `test_complete_withdrawal_closes_class_history` | Integration | Class assignment left_date set, reason="withdrawn" |
| 12 | `test_generate_withdrawal_letter` | Unit | PDF generated without errors, returns BytesIO |

### 9.2 `tests/test_student_transfer.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_initiate_transfer_success` | Unit | Creates clearance + status change with destination metadata |
| 2 | `test_complete_transfer` | Integration | Full flow: initiate → clear → complete, status = transferred |
| 3 | `test_chain_transfer_success` | Integration | Updates school_id, class_id, creates history records |
| 4 | `test_chain_transfer_wrong_school` | Unit | Fails when student not in source school |
| 5 | `test_chain_transfer_school_not_found` | Unit | Fails when destination school not in tenant |
| 6 | `test_chain_transfer_with_outstanding_fees` | Unit | Fails without fee_override |
| 7 | `test_chain_transfer_fee_override` | Unit | Succeeds with fee_override, logs override |
| 8 | `test_chain_transfer_status_remains_active` | Unit | Student status stays 'active' after chain transfer |
| 9 | `test_chain_transfer_class_history` | Integration | Old assignment closed, new assignment created |
| 10 | `test_generate_transfer_certificate` | Unit | PDF generated without errors |
| 11 | `test_export_student_record_pdf` | Unit | PDF export works |
| 12 | `test_export_student_record_json` | Unit | JSON export contains expected keys |
| 13 | `test_check_outstanding_fees` | Unit | Returns correct totals and invoice list |
| 14 | `test_check_outstanding_fees_none` | Unit | Returns has_outstanding=False when all paid |

### 9.3 RLS Tests

Add `withdrawal_clearances` to `test_student_mgmt_rls.py` (from Phase 1).

---

## 10. Checklist

- [ ] Create migration `20260326_0400_withdrawal_transfer.py`
- [ ] Run migration
- [ ] Add `WithdrawalClearance` model to `models/student.py`
- [ ] Register model in `db/base.py`
- [ ] Add schemas to `schemas/student.py`
- [ ] Create `services/student/lifecycle_service.py` with `StudentLifecycleMixin`
- [ ] Update `services/student/__init__.py` to include `StudentLifecycleMixin`
- [ ] Create PDF template `templates/reports/transfer_certificate.html`
- [ ] Create PDF template `templates/reports/withdrawal_letter.html`
- [ ] Add 10 endpoints to `api/v1/endpoints/students.py`
- [ ] Add `withdrawal_clearances` to `TENANT_SCOPED_TABLES` in `tests/conftest.py`
- [ ] Add `withdrawal_clearances` to `backend/scripts/verify_rls.py`
- [ ] Add `withdrawal_clearances` to `backend/app/tasks/tenant_cleanup.py`
- [ ] Write `tests/test_student_withdrawal.py` (~12 tests)
- [ ] Write `tests/test_student_transfer.py` (~14 tests)
- [ ] Add RLS tests for `withdrawal_clearances`
- [ ] Add TypeScript types to `frontend/types/index.ts`
- [ ] Add server actions to `frontend/actions/students.action.ts`
- [ ] Create `withdraw-dialog.tsx` component
- [ ] Create `transfer-dialog.tsx` component
- [ ] Create `download-menu.tsx` component
- [ ] Add action buttons to student detail page
- [ ] Test PDF generation manually
- [ ] Test full withdrawal workflow via Swagger UI
- [ ] Test full transfer workflow via Swagger UI
- [ ] Test chain transfer workflow via Swagger UI
