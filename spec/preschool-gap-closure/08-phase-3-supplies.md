# Phase 3: Supplies Tracking (Could Have)

**Sprint:** 22
**Depends on:** Phase 2 complete (`20260330_0100_preschool_phase2`)
**Priority:** Could Have

---

## Overview

Simple per-student supply inventory for creche/nursery (diapers, wipes, change of clothes, etc.). Parents provide supplies; teachers decrement counts as used. Low-stock alerts notify parents to resupply.

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 8.1 | Create PreschoolSupply model | `backend/app/models/preschool.py` | 0.15d |
| 8.2 | Create migration | `backend/alembic/versions/20260401_0100_preschool_phase3.py` | 0.25d |
| 8.3 | Create schemas | `backend/app/schemas/preschool.py` | 0.15d |
| 8.4 | Create service methods | `backend/app/services/preschool.py` | 0.25d |
| 8.5 | Create endpoints | `backend/app/api/v1/endpoints/preschool.py` | 0.25d |
| 8.6 | Create frontend page + component | Frontend files | 0.5d |
| 8.7 | Tests | `backend/tests/test_preschool_supplies.py` | 0.25d |
| 8.8 | Update test infrastructure | `conftest.py`, `verify_rls.py` | 0.1d |

---

## 8.1 Model

```python
class PreschoolSupply(Base, TenantMixin, SoftDeleteMixin):
    """
    Per-student supply inventory item.

    Tracks parent-provided supplies (diapers, wipes, change of clothes).
    Teachers decrement on use; low-stock alerts notify parents.
    """

    __tablename__ = "preschool_supplies"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Supply item name (e.g., Diapers, Wipes, Spare Clothes)",
    )
    quantity_remaining: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Alert parent when quantity falls to this level",
    )
    last_restocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="e.g., brand preference, size information",
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_remaining <= self.low_stock_threshold

    def __repr__(self) -> str:
        return f"<PreschoolSupply(item='{self.item_name}', qty={self.quantity_remaining})>"
```

---

## 8.2 Migration

**File:** `backend/alembic/versions/20260401_0100_preschool_phase3.py`

```python
"""Preschool Phase 3: Supplies Tracking

Revision ID: 20260401_0100
Revises: 20260330_0100
"""

revision = "20260401_0100"
down_revision = "20260330_0100"

def upgrade() -> None:
    op.create_table(
        "preschool_supplies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("quantity_remaining", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("last_restocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes
    op.create_index("ix_preschool_supplies_tenant", "preschool_supplies", ["tenant_id"])
    op.create_index("ix_preschool_supplies_school", "preschool_supplies", ["school_id"])
    op.create_index("ix_preschool_supplies_student", "preschool_supplies", ["tenant_id", "student_id"])

    # CHECK constraints
    op.execute("""
        ALTER TABLE preschool_supplies
        ADD CONSTRAINT ck_quantity_non_negative CHECK (quantity_remaining >= 0),
        ADD CONSTRAINT ck_threshold_non_negative CHECK (low_stock_threshold >= 0)
    """)

    # RLS (using project-standard rls_helpers)
    from app.db.rls_helpers import enable_rls_for_table
    enable_rls_for_table(op.get_bind(), "preschool_supplies")

def downgrade() -> None:
    from app.db.rls_helpers import disable_rls_for_table
    disable_rls_for_table(op.get_bind(), "preschool_supplies")
    op.drop_table("preschool_supplies")
```

---

## 8.3 Schemas

```python
class PreschoolSupplyCreate(BaseSchema):
    item_name: Annotated[str, Field(min_length=1, max_length=100)]
    quantity_remaining: Annotated[int, Field(ge=0)] = 0
    low_stock_threshold: Annotated[int, Field(ge=0)] = 3
    notes: Annotated[str | None, Field(max_length=500)] = None

class PreschoolSupplyUpdate(BaseSchema):
    item_name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    low_stock_threshold: Annotated[int | None, Field(ge=0)] = None
    notes: Annotated[str | None, Field(max_length=500)] = None

class SupplyUseRequest(BaseSchema):
    quantity: Annotated[int, Field(ge=1)] = 1

class SupplyRestockRequest(BaseSchema):
    quantity: Annotated[int, Field(ge=1)]

class PreschoolSupplyResponse(BaseSchema):
    id: UUID
    tenant_id: UUID
    student_id: UUID
    item_name: str
    quantity_remaining: int
    low_stock_threshold: int
    is_low_stock: bool
    last_restocked_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

---

## 8.4 Service Methods

```python
async def add_supply(self, tenant_id, student_id, data, school_id=None) -> PreschoolSupply:
    """Add a supply item for a student."""

async def list_supplies(self, tenant_id, student_id) -> Sequence[PreschoolSupply]:
    """List all supply items for a student."""

async def update_supply(self, tenant_id, supply_id, data) -> PreschoolSupply:
    """Update supply metadata (name, threshold, notes)."""

async def use_supply(self, tenant_id, supply_id, quantity=1) -> PreschoolSupply:
    """
    Decrement supply quantity.
    If quantity_remaining drops to/below low_stock_threshold:
      - Flag is_low_stock = True (computed property)
      - Trigger parent notification via NotificationDispatcher
        (only if not already notified for this threshold crossing)
    Raises error if quantity_remaining would go below 0.
    """

async def restock_supply(self, tenant_id, supply_id, quantity) -> PreschoolSupply:
    """
    Increment supply quantity and set last_restocked_at = now().
    """
```

---

## 8.5 Endpoints

| Method | Path | Status | Permission |
|--------|------|--------|------------|
| POST | `/preschool/students/{student_id}/supplies` | 201 | `preschool.create` |
| GET | `/preschool/students/{student_id}/supplies` | 200 | `preschool.read` |
| PUT | `/preschool/supplies/{id}` | 200 | `preschool.update` |
| POST | `/preschool/supplies/{id}/use` | 200 | `preschool.update` |
| POST | `/preschool/supplies/{id}/restock` | 200 | `preschool.update` |

---

## 8.6 Frontend

### TypeScript Types

```typescript
interface PreschoolSupply {
  id: string;
  tenant_id: string;
  student_id: string;
  item_name: string;
  quantity_remaining: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
  last_restocked_at?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}
```

### SupplyInventory Component

**File:** `frontend/components/preschool/SupplyInventory.tsx`

**Purpose:** Manage supplies for a student. Shown on student detail page (preschool tab) or as a section in the daily log page.

**UI:**
- Card list per supply item:
  - Item name
  - Quantity badge (color: green if OK, amber if near threshold, red if at/below threshold)
  - "-1" button (quick use), "+1" button (quick restock)
  - Edit button (name, threshold, notes)
  - Restock dialog (quantity input)
- "Add Supply" button → simple dialog (item name, initial quantity, threshold)
- Common presets: "Diapers", "Wipes", "Spare Clothes", "Water Bottle", "Blanket"

### Page Integration

Option A: Add as a section in the student detail page (`/students/[id]`) under a "Supplies" tab (visible only for preschool students).

Option B: Add as a section in the daily log page, visible when logging for creche/nursery students.

**Recommended:** Option A for primary management, with a summary view in Option B.

---

## 8.7 Tests

**File:** `backend/tests/test_preschool_supplies.py`

| Test | Description |
|------|-------------|
| `test_add_supply` | Add supply item with name and quantity |
| `test_list_supplies` | List all supplies for a student |
| `test_use_supply` | Decrement quantity by 1 |
| `test_use_supply_multiple` | Decrement quantity by N |
| `test_use_supply_below_zero_rejected` | Cannot decrement below 0 |
| `test_restock_supply` | Increment quantity, verify last_restocked_at set |
| `test_low_stock_detection` | Verify is_low_stock when at/below threshold |
| `test_supply_rls` | Supplies from tenant A invisible to tenant B |

---

## 8.8 Test Infrastructure

Add to `TENANT_SCOPED_TABLES`:

```python
    # Preschool Phase 3 (Gap Closure)
    "preschool_supplies",
```

---

## Final TENANT_SCOPED_TABLES Count

After all 3 phases:

| Phase | New Tables | Running Total |
|-------|-----------|---------------|
| Before | — | 102 (current) |
| Phase 1 | +3 (incidents, authorized_pickups, pickup_logs) | 105 |
| Phase 2 | +3 (learning_stories, extended_care_sessions, class_caregiver_ratios) | 108 |
| Phase 3 | +1 (preschool_supplies) | 109 |
