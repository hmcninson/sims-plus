# Phase 3: Teaching Workload & Leave Management

**Duration:** 5-7 days
**Prerequisites:** Phase 1 migrations (for chain dependency)
**Migration Chain:** `20260426_0300` → `20260426_0400`
**New Tables:** 3 (`leave_types`, `leave_balances`, `leave_requests`)
**New Endpoints:** 19 (2 workload + 17 leave)
**Tests:** ~35
**Celery Tasks:** 1 (`update_staff_leave_status`)
**Feature Flag:** `hr_leave` (Professional+ tier)

---

## 1. Overview

Phase 3 adds two features:
1. **Teaching workload tracking** (STF-013) — read-only calculation derived from timetable + assignments
2. **Leave management** (HR-011 through HR-014) — full lifecycle: configure types, track balances, submit/approve requests, calendar view

---

## Part A: Teaching Workload (2 endpoints, 1 page)

### Task 3.1: Workload Service

**File:** `backend/app/services/staff/workload_service.py` (NEW)

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.staff import Staff, StaffClassAssignment
from app.models.academic import ClassSection, Subject
from app.models.timetable import ClassTimetable, TimetablePeriod


class StaffWorkloadService:
    """Calculates teaching workload from timetable and class assignments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_staff_workload(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> dict:
        """
        Get teaching workload for a single staff member.

        Returns:
            {
                "staff_id": UUID,
                "staff_name": str,
                "total_periods_per_week": int,
                "total_sections": int,
                "class_teacher_of": str | None,  # section name
                "subjects_taught": [str],
                "sections": [
                    {
                        "section_id": UUID,
                        "section_name": str,
                        "class_name": str,
                        "subject_name": str | None,
                        "is_class_teacher": bool,
                        "periods_per_week": int,
                    }
                ]
            }
        """
        # 1. Fetch staff with assignments + loaded section/subject names
        staff = await self.db.execute(
            select(Staff)
            .options(
                selectinload(Staff.class_assignments)
                .selectinload(StaffClassAssignment.section)
                .selectinload(ClassSection.class_rel),
                selectinload(Staff.class_assignments)
                .selectinload(StaffClassAssignment.subject),
            )
            .where(
                Staff.id == staff_id,
                Staff.tenant_id == tenant_id,
                Staff.deleted_at.is_(None),
            )
        )
        staff = staff.scalar_one_or_none()
        if not staff:
            raise ValueError("Staff not found")

        # 2. For each assignment, count periods from timetable
        sections = []
        total_periods = 0
        class_teacher_of = None
        subjects_taught = set()

        for assignment in staff.class_assignments:
            # Count periods in timetable for this staff + section
            period_count = await self._count_periods(
                tenant_id, staff_id, assignment.section_id, assignment.subject_id
            )

            section_name = assignment.section.name if assignment.section else "Unknown"
            class_name = (
                assignment.section.class_rel.name
                if assignment.section and assignment.section.class_rel
                else "Unknown"
            )
            subject_name = assignment.subject.name if assignment.subject else None

            if assignment.is_class_teacher:
                class_teacher_of = f"{class_name} {section_name}"

            if subject_name:
                subjects_taught.add(subject_name)

            sections.append({
                "section_id": assignment.section_id,
                "section_name": section_name,
                "class_name": class_name,
                "subject_name": subject_name,
                "is_class_teacher": assignment.is_class_teacher,
                "periods_per_week": period_count,
            })
            total_periods += period_count

        return {
            "staff_id": staff.id,
            "staff_name": f"{staff.first_name} {staff.last_name}",
            "total_periods_per_week": total_periods,
            "total_sections": len(sections),
            "class_teacher_of": class_teacher_of,
            "subjects_taught": sorted(subjects_taught),
            "sections": sections,
        }

    async def get_all_staff_workload(
        self,
        tenant_id: UUID,
        school_id: UUID | None = None,
    ) -> list[dict]:
        """
        Get workload summary for ALL teaching staff.
        Uses a single aggregate query instead of N+1.

        Returns list of:
            {
                "staff_id": UUID,
                "staff_name": str,
                "department": str | None,
                "total_sections": int,
                "total_periods_per_week": int,
                "is_class_teacher": bool,
                "class_teacher_of": str | None,
            }
        """
        # Single query: JOIN staff -> assignments -> timetable_periods
        # GROUP BY staff_id
        # COUNT DISTINCT section_id for total_sections
        # COUNT timetable periods for total_periods_per_week
        # ...

    async def _count_periods(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        section_id: UUID,
        subject_id: UUID | None,
    ) -> int:
        """
        Count timetable periods for a specific staff+section+subject combination.

        Joins class_timetables -> timetable_periods where:
        - timetable belongs to the section
        - period's teacher_id matches staff_id
        - period's subject_id matches (if specified)
        """
        # SELECT COUNT(*) FROM timetable_periods tp
        # JOIN class_timetables ct ON tp.timetable_id = ct.id
        # WHERE ct.section_id = :section_id
        #   AND ct.tenant_id = :tenant_id
        #   AND tp.teacher_id = :staff_id
        #   AND (tp.subject_id = :subject_id OR :subject_id IS NULL)
        #   AND ct.deleted_at IS NULL
        result = await self.db.execute(
            select(func.count())
            .select_from(TimetablePeriod)
            .join(ClassTimetable, TimetablePeriod.timetable_id == ClassTimetable.id)
            .where(
                ClassTimetable.section_id == section_id,
                ClassTimetable.tenant_id == tenant_id,
                TimetablePeriod.teacher_id == staff_id,
                ClassTimetable.deleted_at.is_(None),
                *([TimetablePeriod.subject_id == subject_id] if subject_id else []),
            )
        )
        return result.scalar() or 0
```

### Task 3.2: Workload Endpoints

**File:** `backend/app/api/v1/endpoints/staff/staff.py` (add to existing)

```python
@router.get("/{staff_id}/workload")
async def get_staff_workload(
    staff_id: UUID,
    user: ValidatedUser = Depends(require_permissions("staff.read")),
    db: AsyncSession = Depends(get_db),
):
    """Get teaching workload for a specific staff member."""
    service = StaffWorkloadService(db)
    return await service.get_staff_workload(user.tenant_id, staff_id)


@router.get("/workload/summary")
async def get_all_staff_workload(
    user: ValidatedUser = Depends(require_permissions("staff.read")),
    db: AsyncSession = Depends(get_db),
):
    """Get workload overview for all teaching staff."""
    service = StaffWorkloadService(db)
    return await service.get_all_staff_workload(user.tenant_id, user.school_id)
```

**CRITICAL — Path Conflict Resolution:** The `/workload/summary` route MUST be registered BEFORE `/{staff_id}` routes in the combined staff router. If added via `include_router()`, it must be included BEFORE the main staff CRUD routes. The safest approach is to define these two workload endpoints directly on the main staff router (in `staff.py`) above the `/{staff_id}` GET route, NOT in a separate sub-router. This prevents FastAPI from matching `workload` as a `{staff_id}` parameter.

### Task 3.3: Workload Schemas

**File:** `backend/app/schemas/staff.py` (add)

```python
class StaffWorkloadSection(BaseModel):
    section_id: UUID
    section_name: str
    class_name: str
    subject_name: str | None = None
    is_class_teacher: bool
    periods_per_week: int

class StaffWorkloadResponse(BaseModel):
    staff_id: UUID
    staff_name: str
    total_periods_per_week: int
    total_sections: int
    class_teacher_of: str | None = None
    subjects_taught: list[str]
    sections: list[StaffWorkloadSection]

class StaffWorkloadSummaryItem(BaseModel):
    staff_id: UUID
    staff_name: str
    department: str | None = None
    total_sections: int
    total_periods_per_week: int
    is_class_teacher: bool
    class_teacher_of: str | None = None
```

### Task 3.4: Workload Frontend Page

**File:** `frontend/app/(dashboard)/staff/workload/page.tsx` (NEW)

```
┌─────────────────────────────────────────────────────────┐
│ Teaching Workload Overview                               │
│                                                          │
│ Filter: [Department ▼]                                   │
│                                                          │
│ ┌──── Summary Chart ─────────────────────────────────┐  │
│ │ [Horizontal Bar Chart: periods/week per staff]      │  │
│ │ John Doe       ████████████████ 24                  │  │
│ │ Jane Smith     ████████████ 18                      │  │
│ │ Bob Johnson    ██████████ 15                        │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌──── Detail Table ──────────────────────────────────┐  │
│ │ Staff Name    │ Dept   │ Sections │ Periods │ CT?  │  │
│ │ John Doe      │ Math   │ 4        │ 24      │ Yes  │  │
│ │ Jane Smith    │ English│ 3        │ 18      │ No   │  │
│ │ Bob Johnson   │ Science│ 3        │ 15      │ Yes  │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ Click a row to see detailed section breakdown.          │
└─────────────────────────────────────────────────────────┘
```

**Server action:**
```typescript
// frontend/actions/staff.action.ts (add)
export async function getStaffWorkloadSummary(): Promise<ActionResult<StaffWorkloadSummaryItem[]>> {
  return apiGet("/staff/workload/summary")
}

export async function getStaffWorkload(staffId: string): Promise<ActionResult<StaffWorkloadResponse>> {
  return apiGet(`/staff/${staffId}/workload`)
}
```

---

## Part B: Leave Management (17 endpoints, 7 pages, 3 tables)

### Task 3.5: Migration — Leave Tables

**File:** `backend/alembic/versions/20260426_0400_leave_management.py`
**Revises:** `20260426_0300`

**Operations:**

```python
# 1. Create leave request status enum
op.execute("""
    CREATE TYPE leaverequeststatus AS ENUM (
        'pending', 'approved', 'rejected', 'cancelled'
    )
""")

# 2. Create leave_types table
op.create_table(
    'leave_types',
    sa.Column('id', UUID(), server_default=text('gen_random_uuid()'), primary_key=True),
    sa.Column('tenant_id', UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
    sa.Column('school_id', UUID(), sa.ForeignKey('schools.id', ondelete='SET NULL'), nullable=True),
    sa.Column('name', sa.String(100), nullable=False),
    sa.Column('code', sa.String(20), nullable=False),
    sa.Column('description', sa.Text, nullable=True),
    sa.Column('default_days_per_year', sa.Numeric(5, 1), nullable=False),  # supports 0.5
    sa.Column('max_carryover_days', sa.Numeric(5, 1), nullable=True, server_default='0'),
    sa.Column('is_paid', sa.Boolean, nullable=False, server_default='true'),
    sa.Column('requires_approval', sa.Boolean, nullable=False, server_default='true'),
    sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
    sa.Column('color', sa.String(7), nullable=True),  # hex color for calendar
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
)

# Unique constraint: code per tenant (soft-delete aware)
op.create_index('uq_leave_type_code_tenant', 'leave_types',
    ['tenant_id', 'code', 'deleted_at'], unique=True)

# 3. Create leave_balances table
op.create_table(
    'leave_balances',
    sa.Column('id', UUID(), server_default=text('gen_random_uuid()'), primary_key=True),
    sa.Column('tenant_id', UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
    sa.Column('staff_id', UUID(), sa.ForeignKey('staff.id', ondelete='CASCADE'), nullable=False),
    sa.Column('leave_type_id', UUID(), sa.ForeignKey('leave_types.id', ondelete='CASCADE'), nullable=False),
    sa.Column('academic_year_id', UUID(), sa.ForeignKey('academic_years.id', ondelete='CASCADE'), nullable=False),
    sa.Column('entitled_days', sa.Numeric(5, 1), nullable=False),
    sa.Column('used_days', sa.Numeric(5, 1), nullable=False, server_default='0'),
    sa.Column('pending_days', sa.Numeric(5, 1), nullable=False, server_default='0'),
    sa.Column('carried_over', sa.Numeric(5, 1), nullable=False, server_default='0'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), nullable=False),
)

# Unique: one balance per staff+type+year
op.create_unique_constraint('uq_leave_balance', 'leave_balances',
    ['tenant_id', 'staff_id', 'leave_type_id', 'academic_year_id'])

# Composite index for FOR UPDATE queries during balance checks
op.create_index('ix_leave_balances_staff_type_year', 'leave_balances',
    ['tenant_id', 'staff_id', 'leave_type_id', 'academic_year_id'])

# 4. Create leave_requests table
op.create_table(
    'leave_requests',
    sa.Column('id', UUID(), server_default=text('gen_random_uuid()'), primary_key=True),
    sa.Column('tenant_id', UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
    sa.Column('school_id', UUID(), sa.ForeignKey('schools.id', ondelete='SET NULL'), nullable=True),
    sa.Column('staff_id', UUID(), sa.ForeignKey('staff.id', ondelete='CASCADE'), nullable=False),
    sa.Column('leave_type_id', UUID(), sa.ForeignKey('leave_types.id', ondelete='RESTRICT'), nullable=False),
    sa.Column('academic_year_id', UUID(), sa.ForeignKey('academic_years.id', ondelete='RESTRICT'), nullable=False),
    sa.Column('start_date', sa.Date, nullable=False),
    sa.Column('end_date', sa.Date, nullable=False),
    sa.Column('days_requested', sa.Numeric(5, 1), nullable=False),  # calculated server-side
    sa.Column('reason', sa.Text, nullable=False),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled',
              name='leaverequeststatus', create_type=False), nullable=False, server_default='pending'),
    sa.Column('reviewed_by', UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_notes', sa.Text, nullable=True),
    sa.Column('attachment_key', sa.String(500), nullable=True),  # S3 key for supporting document
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), nullable=False),
)

# Indexes
op.create_index('ix_leave_requests_staff', 'leave_requests', ['tenant_id', 'staff_id'])
op.create_index('ix_leave_requests_status', 'leave_requests', ['tenant_id', 'status'])
op.create_index('ix_leave_requests_dates', 'leave_requests', ['tenant_id', 'start_date', 'end_date'])

# 5. RLS for all 3 tables
for table_name in ['leave_types', 'leave_balances', 'leave_requests']:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON {table_name}
            FOR ALL
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")

# 6. Seed default leave types for existing tenants
op.execute("""
    INSERT INTO leave_types (tenant_id, name, code, default_days_per_year, max_carryover_days, is_paid, requires_approval, color)
    SELECT t.id, lt.name, lt.code, lt.days, lt.carryover, lt.paid, lt.approval, lt.color
    FROM tenants t
    CROSS JOIN (VALUES
        ('Annual Leave',       'ANNUAL',  20.0, 5.0,  true,  true,  '#3B82F6'),
        ('Sick Leave',         'SICK',    15.0, 0.0,  true,  true,  '#EF4444'),
        ('Maternity Leave',    'MATERN',  90.0, 0.0,  true,  true,  '#EC4899'),
        ('Paternity Leave',    'PATERN',   5.0, 0.0,  true,  true,  '#8B5CF6'),
        ('Casual Leave',       'CASUAL',   5.0, 0.0,  true,  true,  '#F59E0B'),
        ('Study Leave',        'STUDY',   30.0, 0.0,  false, true,  '#10B981'),
        ('Compassionate Leave','COMPASS',  5.0, 0.0,  true,  true,  '#6B7280')
    ) AS lt(name, code, days, carryover, paid, approval, color)
    WHERE t.status IN ('active', 'trial')
    ON CONFLICT DO NOTHING
""")
```

### Task 3.6: Leave Models

**File:** `backend/app/models/leave.py` (NEW)

```python
"""Leave management models: types, balances, and requests."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.models.base import Base, TenantMixin, SoftDeleteMixin


class LeaveRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveType(TenantMixin, SoftDeleteMixin, Base):
    __tablename__ = "leave_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_days_per_year: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    max_carryover_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=True, server_default="0")
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    # Relationships
    balances: Mapped[list["LeaveBalance"]] = relationship(back_populates="leave_type", lazy="raise")
    requests: Mapped[list["LeaveRequest"]] = relationship(back_populates="leave_type", lazy="raise")


class LeaveBalance(TenantMixin, Base):
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "staff_id", "leave_type_id", "academic_year_id",
                         name="uq_leave_balance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    entitled_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    used_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, server_default="0")
    pending_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, server_default="0")
    carried_over: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    # Relationships
    leave_type: Mapped["LeaveType"] = relationship(back_populates="balances", lazy="raise")
    staff: Mapped["Staff"] = relationship(lazy="raise")


class LeaveRequest(TenantMixin, Base):
    __tablename__ = "leave_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="RESTRICT"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_requested: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(LeaveRequestStatus, name="leaverequeststatus",
               values_callable=lambda x: [e.value for e in x]),
        nullable=False, server_default="pending"
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    # Relationships
    leave_type: Mapped["LeaveType"] = relationship(back_populates="requests", lazy="raise")
    staff: Mapped["Staff"] = relationship(lazy="raise")
    reviewer: Mapped["User"] = relationship(lazy="raise", foreign_keys=[reviewed_by])
```

### Task 3.7: Leave Schemas

**File:** `backend/app/schemas/leave.py` (NEW)

```python
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# --- Leave Types ---

class LeaveTypeCreate(BaseModel):
    name: str = Field(max_length=100)
    code: str = Field(max_length=20)
    description: str | None = None
    default_days_per_year: Decimal = Field(ge=0, decimal_places=1)
    max_carryover_days: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=1)
    is_paid: bool = True
    requires_approval: bool = True
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

class LeaveTypeUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None
    default_days_per_year: Decimal | None = Field(None, ge=0)
    max_carryover_days: Decimal | None = Field(None, ge=0)
    is_paid: bool | None = None
    requires_approval: bool | None = None
    is_active: bool | None = None
    color: str | None = None

class LeaveTypeResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None = None
    default_days_per_year: Decimal
    max_carryover_days: Decimal
    is_paid: bool
    requires_approval: bool
    is_active: bool
    color: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Leave Balances ---

class LeaveBalanceResponse(BaseModel):
    id: UUID
    staff_id: UUID
    staff_name: str | None = None
    leave_type_id: UUID
    leave_type_name: str | None = None
    academic_year_id: UUID
    entitled_days: Decimal
    used_days: Decimal
    pending_days: Decimal
    carried_over: Decimal
    remaining_days: Decimal  # computed: entitled + carried_over - used - pending
    model_config = ConfigDict(from_attributes=True)

class LeaveBalanceAdjust(BaseModel):
    entitled_days: Decimal | None = None
    carried_over: Decimal | None = None
    reason: str = Field(min_length=3, max_length=500)

class LeaveBalanceInitialize(BaseModel):
    academic_year_id: UUID
    carry_over_from_previous: bool = False


# --- Leave Requests ---

class LeaveRequestCreate(BaseModel):
    leave_type_id: UUID
    start_date: date
    end_date: date
    reason: str = Field(min_length=5, max_length=2000)
    # days_requested is calculated server-side

class LeaveRequestUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(None, min_length=5, max_length=2000)

class LeaveRequestResponse(BaseModel):
    id: UUID
    staff_id: UUID
    staff_name: str | None = None
    leave_type_id: UUID
    leave_type_name: str | None = None
    leave_type_color: str | None = None
    start_date: date
    end_date: date
    days_requested: Decimal
    reason: str
    status: str
    reviewed_by: UUID | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class LeaveApprovalRequest(BaseModel):
    notes: str | None = Field(None, max_length=1000)

class LeaveCalendarEntry(BaseModel):
    staff_id: UUID
    staff_name: str
    leave_type_name: str
    leave_type_color: str | None = None
    start_date: date
    end_date: date
    days: Decimal
    status: str
```

### Task 3.8: Leave Services

**File:** `backend/app/services/leave/type_service.py` (NEW)

```python
class LeaveTypeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id, data, school_id=None) -> LeaveType:
        # Check unique code per tenant
        # Create LeaveType
        # flush() + refresh()

    async def list(self, tenant_id, active_only=True) -> list[LeaveType]:
        # Query with tenant_id filter, optional is_active filter, deleted_at IS NULL

    async def update(self, tenant_id, type_id, data) -> LeaveType:
        # Fetch, validate, apply changes, flush

    async def delete(self, tenant_id, type_id) -> None:
        # Soft delete, check no active balances reference it
```

**File:** `backend/app/services/leave/balance_service.py` (NEW)

```python
class LeaveBalanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_staff_balances(self, tenant_id, staff_id, academic_year_id=None) -> list[LeaveBalance]:
        # Fetch all balances for a staff member, optionally filtered by year
        # Include leave_type name via selectinload

    async def get_all_balances(self, tenant_id, academic_year_id, leave_type_id=None) -> list[LeaveBalance]:
        # All staff balances for a year, with staff name and leave type name

    async def adjust(self, tenant_id, balance_id, data) -> LeaveBalance:
        # Admin override of entitled_days or carried_over
        # Audit log the change with reason

    async def initialize_for_year(self, tenant_id, academic_year_id, carry_over=False) -> int:
        """
        Bulk initialize balances for all active staff for a new academic year.
        If carry_over=True, calculate remaining from previous year (capped by max_carryover_days).
        Returns count of balances created.
        """
        # 1. Fetch all active staff
        # 2. Fetch all active leave types
        # 3. For each staff x leave_type, check if balance exists for this year
        # 4. If carry_over, fetch previous year balance and calculate:
        #    carried = min(remaining, leave_type.max_carryover_days)
        # 5. Bulk INSERT via insert().values([...])
        # 6. Return count
```

**File:** `backend/app/services/leave/request_service.py` (NEW)

```python
class LeaveRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(self, tenant_id, staff_id, data, school_id=None) -> LeaveRequest:
        """
        Submit a new leave request.

        Validations:
        1. Leave type is active for this tenant
        2. end_date >= start_date
        3. start_date not in the past (allow today)
        4. No overlapping approved/pending requests for same staff
        5. Calculate days_requested (exclude weekends + school holidays)
        6. Sufficient balance: remaining_days >= days_requested
        7. Increment pending_days on balance

        If leave_type.requires_approval == False, auto-approve immediately.
        """
        # ... validation logic ...

        # Calculate working days
        days = await self._calculate_working_days(
            tenant_id, data.start_date, data.end_date
        )

        # Check balance
        balance = await self._get_balance(tenant_id, staff_id, data.leave_type_id, academic_year_id)
        remaining = balance.entitled_days + balance.carried_over - balance.used_days - balance.pending_days
        if remaining < days:
            raise self.Error(f"Insufficient leave balance. Available: {remaining} days, Requested: {days} days", "INSUFFICIENT_BALANCE")

        # Create request
        request = LeaveRequest(
            tenant_id=tenant_id,
            staff_id=staff_id,
            leave_type_id=data.leave_type_id,
            academic_year_id=academic_year_id,
            start_date=data.start_date,
            end_date=data.end_date,
            days_requested=days,
            reason=data.reason,
            status="pending",
            school_id=school_id,
        )
        self.db.add(request)

        # Increment pending days on balance
        balance.pending_days += days
        await self.db.flush()
        await self.db.refresh(request)

        # Auto-approve if not requiring approval
        if not leave_type.requires_approval:
            return await self.approve(tenant_id, request.id, reviewer_id=None, notes="Auto-approved")

        return request

    async def approve(self, tenant_id, request_id, reviewer_id, notes=None) -> LeaveRequest:
        """
        Approve a pending leave request.
        - Set status = approved
        - pending_days -= days_requested
        - used_days += days_requested
        - If start_date <= today, set staff.status = 'on_leave'
        """
        request = await self._get_request(tenant_id, request_id)
        if request.status != "pending":
            raise self.Error("Can only approve pending requests", "INVALID_STATUS")

        # Lock balance row to prevent race conditions
        balance = await self._get_balance_for_update(
            tenant_id, request.staff_id, request.leave_type_id, request.academic_year_id
        )

        request.status = "approved"
        request.reviewed_by = reviewer_id
        request.reviewed_at = datetime.utcnow()
        request.review_notes = notes

        balance.pending_days -= request.days_requested
        balance.used_days += request.days_requested

        # If leave starts today or earlier, update staff status
        if request.start_date <= date.today():
            staff = await self.db.get(Staff, request.staff_id)
            if staff:
                staff.status = "on_leave"

        await self.db.flush()
        return request

    async def reject(self, tenant_id, request_id, reviewer_id, notes=None) -> LeaveRequest:
        """Reject a pending request. Reverse pending_days."""
        request = await self._get_request(tenant_id, request_id)
        if request.status != "pending":
            raise self.Error("Can only reject pending requests", "INVALID_STATUS")

        balance = await self._get_balance_for_update(...)
        request.status = "rejected"
        request.reviewed_by = reviewer_id
        request.reviewed_at = datetime.utcnow()
        request.review_notes = notes
        balance.pending_days -= request.days_requested
        await self.db.flush()
        return request

    async def cancel(self, tenant_id, request_id, staff_id) -> LeaveRequest:
        """
        Cancel own request (only if pending or approved-but-not-started).
        If was approved, reverse used_days.
        """
        request = await self._get_request(tenant_id, request_id)
        if request.staff_id != staff_id:
            raise self.Error("Can only cancel own requests", "FORBIDDEN")
        if request.status not in ("pending", "approved"):
            raise self.Error("Cannot cancel this request", "INVALID_STATUS")
        if request.status == "approved" and request.start_date <= date.today():
            raise self.Error("Cannot cancel leave that has already started", "ALREADY_STARTED")

        balance = await self._get_balance_for_update(...)
        if request.status == "pending":
            balance.pending_days -= request.days_requested
        elif request.status == "approved":
            balance.used_days -= request.days_requested

        request.status = "cancelled"
        await self.db.flush()
        return request

    async def list_requests(self, tenant_id, filters) -> list[LeaveRequest]:
        """List leave requests with filters: staff_id, status, date_range, leave_type_id."""

    async def get_calendar(self, tenant_id, start_date, end_date) -> list[LeaveCalendarEntry]:
        """Get all approved/pending leave for calendar view within date range."""

    async def _calculate_working_days(self, tenant_id, start_date, end_date) -> Decimal:
        """
        Calculate working days between two dates, excluding:
        1. Weekends (Saturday, Sunday)
        2. School holidays (from school_holidays table)

        Returns Decimal for half-day support (if end_date == start_date and
        a future half_day flag is added, return 0.5).
        """
        # Iterate through date range
        # For each day: skip if weekend or holiday
        # Count remaining days
        holidays = await self._get_holidays(tenant_id, start_date, end_date)
        holiday_dates = {h.date for h in holidays}

        count = Decimal("0")
        current = start_date
        while current <= end_date:
            if current.weekday() < 5 and current not in holiday_dates:  # Mon-Fri, not holiday
                count += Decimal("1")
            current += timedelta(days=1)
        return count

    async def _get_balance_for_update(self, tenant_id, staff_id, leave_type_id, year_id):
        """Fetch balance with FOR UPDATE lock to prevent race conditions."""
        result = await self.db.execute(
            select(LeaveBalance)
            .where(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.staff_id == staff_id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.academic_year_id == year_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()
```

### Task 3.9: Leave Endpoints

**File:** `backend/app/api/v1/endpoints/leave.py` (NEW)

```python
router = APIRouter(prefix="/leave", tags=["Leave Management"])

# --- Leave Types ---
@router.post("/types", response_model=LeaveTypeResponse, status_code=201)
async def create_leave_type(data: LeaveTypeCreate, user=Depends(require_permissions("hr.leave.manage")), db=Depends(get_db)):

@router.get("/types", response_model=list[LeaveTypeResponse])
async def list_leave_types(active_only: bool = True, user=Depends(require_permissions("hr.leave.read")), db=Depends(get_db)):

@router.put("/types/{type_id}", response_model=LeaveTypeResponse)
async def update_leave_type(type_id: UUID, data: LeaveTypeUpdate, user=Depends(require_permissions("hr.leave.manage")), db=Depends(get_db)):

@router.delete("/types/{type_id}", status_code=204)
async def delete_leave_type(type_id: UUID, user=Depends(require_permissions("hr.leave.manage")), db=Depends(get_db)):


# --- Leave Balances ---
@router.get("/balances", response_model=list[LeaveBalanceResponse])
async def list_leave_balances(academic_year_id: UUID | None = None, leave_type_id: UUID | None = None, user=Depends(require_permissions("hr.leave.read")), db=Depends(get_db)):

@router.get("/balances/{staff_id}", response_model=list[LeaveBalanceResponse])
async def get_staff_balances(staff_id: UUID, academic_year_id: UUID | None = None, user=Depends(require_permissions("hr.leave.read")), db=Depends(get_db)):

@router.put("/balances/{balance_id}", response_model=LeaveBalanceResponse)
async def adjust_leave_balance(balance_id: UUID, data: LeaveBalanceAdjust, user=Depends(require_permissions("hr.leave.manage")), db=Depends(get_db)):

@router.post("/balances/initialize", status_code=201)
async def initialize_balances(data: LeaveBalanceInitialize, user=Depends(require_permissions("hr.leave.manage")), db=Depends(get_db)):
    """Bulk initialize leave balances for all active staff for an academic year."""
    # Returns: {"created": 245, "message": "Initialized 245 leave balances for 35 staff"}


# --- Leave Requests ---
@router.post("/requests", response_model=LeaveRequestResponse, status_code=201)
async def submit_leave_request(data: LeaveRequestCreate, user=Depends(require_permissions("hr.leave.request")), db=Depends(get_db)):
    """Submit a leave request. Staff can only request for themselves."""
    # Get staff_id from user's linked staff profile (user.staff_id)
    # OR allow HR to submit on behalf (if hr.leave.manage permission)

@router.get("/requests", response_model=list[LeaveRequestResponse])
async def list_leave_requests(
    status: str | None = None,
    staff_id: UUID | None = None,
    leave_type_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    user=Depends(require_permissions("hr.leave.read")),
    db=Depends(get_db),
):

@router.get("/requests/{request_id}", response_model=LeaveRequestResponse)
async def get_leave_request(request_id: UUID, user=Depends(require_permissions("hr.leave.read")), db=Depends(get_db)):

@router.put("/requests/{request_id}", response_model=LeaveRequestResponse)
async def update_leave_request(request_id: UUID, data: LeaveRequestUpdate, user=Depends(require_permissions("hr.leave.request")), db=Depends(get_db)):
    """Update a pending leave request (before approval). Staff can only update own."""

@router.post("/requests/{request_id}/approve", response_model=LeaveRequestResponse)
async def approve_leave_request(request_id: UUID, data: LeaveApprovalRequest, user=Depends(require_permissions("hr.leave.approve")), db=Depends(get_db)):

@router.post("/requests/{request_id}/reject", response_model=LeaveRequestResponse)
async def reject_leave_request(request_id: UUID, data: LeaveApprovalRequest, user=Depends(require_permissions("hr.leave.approve")), db=Depends(get_db)):

@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestResponse)
async def cancel_leave_request(request_id: UUID, user=Depends(require_permissions("hr.leave.request")), db=Depends(get_db)):
    """Cancel own leave request."""


# --- Calendar ---
@router.get("/calendar", response_model=list[LeaveCalendarEntry])
async def get_leave_calendar(start_date: date, end_date: date, user=Depends(require_permissions("hr.leave.read")), db=Depends(get_db)):
    """Get leave calendar entries for a date range (approved + pending)."""
```

### Task 3.10: Celery Beat Task — Auto-Update Staff Leave Status

**File:** `backend/app/tasks/leave.py` (NEW)

```python
from app.celery_app import celery_app

@celery_app.task(name="update_staff_leave_status")
def update_staff_leave_status():
    """
    Daily task (runs at 00:05) to:
    1. Set staff.status = 'on_leave' for staff whose approved leave starts today
    2. Set staff.status = 'active' for staff whose approved leave ended yesterday

    Must run per tenant — iterate all active tenants and set tenant context.
    """
    # Use sync session (Celery tasks use sync)
    # For each active tenant:
    #   set_tenant_context(tenant_id)
    #   UPDATE staff SET status = 'on_leave'
    #     WHERE id IN (SELECT staff_id FROM leave_requests WHERE status = 'approved' AND start_date = today)
    #     AND status = 'active'
    #   UPDATE staff SET status = 'active'
    #     WHERE id IN (SELECT staff_id FROM leave_requests WHERE status = 'approved' AND end_date = yesterday)
    #     AND status = 'on_leave'
    #     AND id NOT IN (SELECT staff_id FROM leave_requests WHERE status = 'approved' AND start_date <= today AND end_date >= today)
```

Register in Celery beat schedule:
```python
# In celery_app.py or beat_schedule config:
celery_app.conf.beat_schedule["update-staff-leave-status"] = {
    "task": "update_staff_leave_status",
    "schedule": crontab(hour=0, minute=5),  # Daily at 00:05
}
```

### Task 3.11: Register Routes

**File:** `backend/app/api/v1/router.py`

```python
from app.api.v1.endpoints.leave import router as leave_router
router.include_router(leave_router)
```

### Task 3.12: Update Permissions (CRITICAL — Without this, all leave endpoints will return 403)

**File:** `backend/app/constants/permissions.py`

Add to `PERMISSIONS_CATALOG` list:
```python
{
    "module": "HR & Leave",
    "permissions": [
        {"key": "hr.leave.read", "label": "View leave data", "description": "View leave types, balances, and requests"},
        {"key": "hr.leave.request", "label": "Request leave", "description": "Submit and cancel own leave requests"},
        {"key": "hr.leave.approve", "label": "Approve leave", "description": "Approve or reject leave requests"},
        {"key": "hr.leave.manage", "label": "Manage leave settings", "description": "Configure leave types, adjust balances"},
    ],
},
```

**File:** `backend/app/services/auth.py` (ROLE_PERMISSIONS dict)

Add these permissions to the EXISTING role permission lists:
```python
"school_admin": [..., "hr.leave.read", "hr.leave.request", "hr.leave.approve", "hr.leave.manage"],
"chain_admin": [..., "hr.leave.read", "hr.leave.request", "hr.leave.approve", "hr.leave.manage"],
"hr_officer": [..., "hr.leave.read", "hr.leave.request", "hr.leave.approve", "hr.leave.manage"],
"academic_head": [..., "hr.leave.read", "hr.leave.request"],
"teacher": [..., "hr.leave.read", "hr.leave.request"],  # read scoped to own staff profile only
```

**File:** `backend/app/constants/subscription.py`

Add `hr_leave` to `PLAN_FEATURES` if not already present:
```python
# In _STARTER_FEATURES: "hr_leave": False
# In PROFESSIONAL features: "hr_leave": True
# In ENTERPRISE features: "hr_leave": True
```

### Task 3.13: Feature Flag Check

All leave endpoints must check `hr_leave` feature flag. Add at the router level:

```python
# Option 1: Dependency on router
from app.api.deps import require_feature

@router.post("/types", dependencies=[Depends(require_feature("hr_leave"))])
async def create_leave_type(...):
```

Or create a shared dependency and add to each endpoint.

### Task 3.14-3.20: Frontend Pages

See overview doc for page list. Key implementations:

**Leave Types Config:** TanStack Table with CRUD dialogs, color picker for calendar display.

**Leave Requests List:** Filterable table with status badges, approve/reject action buttons. Teachers see only their own requests.

**Leave Calendar:** Month-view calendar showing colored bars per staff member. Use a grid-based calendar component (similar to school calendar pattern).

**Leave Balances:** Table showing all staff x all leave types for selected academic year. Admin can adjust entitled/carried days.

### Task 3.21: Tests

See overview doc section 9 for full test list. Key test scenarios:

- **Overlap detection:** Two requests for overlapping dates should be rejected
- **Balance enforcement:** Request exceeding available balance should be rejected
- **Auto-approve:** Request for type with `requires_approval=False` should auto-approve
- **Cancel approved:** Should reverse `used_days` back to balance
- **Cancel started:** Should fail if leave has already started
- **Race condition:** Two concurrent approvals on same balance should not double-deduct (FOR UPDATE)

---

## 5. Acceptance Criteria

- [ ] Workload page shows periods/week per staff, derived from timetable
- [ ] Leave types can be created, updated, soft-deleted (seeded with 7 defaults)
- [ ] Leave balances can be bulk-initialized for an academic year with optional carryover
- [ ] Leave requests can be submitted with server-calculated working days
- [ ] Overlapping requests are rejected
- [ ] Insufficient balance is rejected with clear error message
- [ ] Requests can be approved (deducts from balance) and rejected (releases pending)
- [ ] Requests can be cancelled by the staff member (if not started)
- [ ] Leave calendar shows all approved/pending leave in a month view
- [ ] Daily Celery task updates staff status (on_leave / active) based on leave dates
- [ ] All leave endpoints gated by `hr_leave` feature flag
- [ ] All 3 tables have RLS and are in TENANT_SCOPED_TABLES
- [ ] All 35 tests pass
