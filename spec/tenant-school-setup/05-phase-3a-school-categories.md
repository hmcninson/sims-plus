# Phase 3A: School Category Fields

**Complexity:** Small
**Requirements:** TS-012
**Dependencies:** None
**Estimated effort:** 1 day

---

## Summary

Add `school_category` (public/private/international/faith-based) and `boarding_type` (day_only/boarding_only/mixed) enum fields to the School model. Update schemas, API, frontend form, and registration flow.

---

## Task 1: Backend Enums and Model

### File: `backend/app/models/school.py`

Add new enums:

```python
class SchoolCategory(str, Enum):
    """Ownership/governance type of the school."""
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNATIONAL = "international"
    FAITH_BASED = "faith_based"


class BoardingType(str, Enum):
    """Residential accommodation type."""
    DAY_ONLY = "day_only"
    BOARDING_ONLY = "boarding_only"
    MIXED = "mixed"  # Both day and boarding students
```

Add columns to the `School` model (after the existing `uses_boarding` field):

```python
# New fields — nullable for backward compatibility
category: Mapped[SchoolCategory | None] = mapped_column(
    SAEnum(SchoolCategory, values_callable=lambda x: [e.value for e in x]),
    nullable=True,
    comment="Ownership: public, private, international, faith_based",
)
boarding_type: Mapped[BoardingType | None] = mapped_column(
    SAEnum(BoardingType, values_callable=lambda x: [e.value for e in x]),
    nullable=True,
    comment="Residential: day_only, boarding_only, mixed",
)
```

**Note:** Keep the existing `uses_boarding: bool` field. Do NOT remove or deprecate it yet — it's referenced in many places. The new `boarding_type` provides richer categorization. Over time, `uses_boarding` can be derived from `boarding_type != day_only`, but that's a future cleanup.

---

## Task 2: Alembic Migration

### File: `backend/alembic/versions/20260322_0200_school_category_fields.py`

```python
"""Add school_category and boarding_type to schools.

Revision ID: 20260322_0200
Revises: 20260322_0100
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa

revision = "20260322_0200"
down_revision = "20260322_0100"  # After trial/subscription migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    schoolcategory = sa.Enum(
        "public", "private", "international", "faith_based",
        name="schoolcategory",
    )
    schoolcategory.create(op.get_bind(), checkfirst=True)

    boardingtype = sa.Enum(
        "day_only", "boarding_only", "mixed",
        name="boardingtype",
    )
    boardingtype.create(op.get_bind(), checkfirst=True)

    # Add columns
    op.add_column(
        "schools",
        sa.Column("category", schoolcategory, nullable=True),
    )
    op.add_column(
        "schools",
        sa.Column("boarding_type", boardingtype, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schools", "boarding_type")
    op.drop_column("schools", "category")

    sa.Enum(name="boardingtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="schoolcategory").drop(op.get_bind(), checkfirst=True)
```

---

## Task 3: Update Schemas

### File: `backend/app/schemas/school.py`

Add to `SchoolProfileUpdate` (the schema used for `PUT /schools/current`):

```python
from app.models.school import SchoolCategory, BoardingType

class SchoolProfileUpdate(BaseModel):
    # ... existing fields ...
    category: SchoolCategory | None = None
    boarding_type: BoardingType | None = None
```

Add to `SchoolResponse` (the response schema):

```python
class SchoolResponse(BaseModel):
    # ... existing fields ...
    category: str | None = None       # "public", "private", etc.
    boarding_type: str | None = None  # "day_only", "boarding_only", "mixed"
```

### File: `backend/app/schemas/onboarding.py`

Add optional fields to the registration schema so schools can set these during onboarding:

```python
class RegisterSchoolRequest(BaseModel):
    # ... existing fields ...
    school_category: str | None = None      # Optional during registration
    boarding_type: str | None = None        # Optional during registration
```

Update the `OnboardingService.register_school()` to accept and store these:

```python
# In register_school(), when creating the School:
school = School(
    tenant_id=tenant.id,
    name=school_name,
    slug=subdomain,
    school_type=SchoolType(school_type),
    category=SchoolCategory(school_category) if school_category else None,
    boarding_type=BoardingType(boarding_type) if boarding_type else None,
    # ... rest of existing fields ...
)
```

---

## Task 4: Frontend Form Updates

### File: `frontend/app/(dashboard)/settings/school/school-profile-form.tsx`

Add two new select fields after the existing school settings:

```tsx
{/* School Category */}
<div>
  <Label>School Category</Label>
  <Select
    value={formData.category || ""}
    onValueChange={(val) => setFormData({ ...formData, category: val || null })}
  >
    <SelectTrigger>
      <SelectValue placeholder="Select category" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="public">Public (Government)</SelectItem>
      <SelectItem value="private">Private</SelectItem>
      <SelectItem value="international">International</SelectItem>
      <SelectItem value="faith_based">Faith-Based</SelectItem>
    </SelectContent>
  </Select>
</div>

{/* Boarding Type */}
<div>
  <Label>Boarding Type</Label>
  <Select
    value={formData.boarding_type || ""}
    onValueChange={(val) => setFormData({ ...formData, boarding_type: val || null })}
  >
    <SelectTrigger>
      <SelectValue placeholder="Select boarding type" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="day_only">Day School Only</SelectItem>
      <SelectItem value="boarding_only">Boarding School Only</SelectItem>
      <SelectItem value="mixed">Mixed (Day & Boarding)</SelectItem>
    </SelectContent>
  </Select>
</div>
```

### File: `frontend/types/index.ts`

Update the `School` interface:

```typescript
interface School {
  // ... existing fields ...
  category: "public" | "private" | "international" | "faith_based" | null;
  boarding_type: "day_only" | "boarding_only" | "mixed" | null;
}
```

### File: `frontend/components/setup-wizard/setup-wizard.tsx`

Add category and boarding_type to the School Profile step:

```tsx
// In the School Profile step, add the two selects after existing fields
// Same pattern as the settings form above
```

### File: `frontend/app/(auth)/register/page.tsx`

Optionally add these fields to the registration form (Step 1: School Info). These are optional during registration, so they can be placed at the bottom with a note "You can set these later."

---

## Testing Checklist

- [ ] Migration runs successfully, creates two new enums and columns
- [ ] Existing schools have NULL for both new fields (no data loss)
- [ ] `PUT /schools/current` accepts and stores category and boarding_type
- [ ] `GET /schools/current` returns new fields in response
- [ ] Registration with category and boarding_type works
- [ ] Registration without these fields works (nullable)
- [ ] School settings form shows the new selects with correct options
- [ ] Setup wizard School Profile step includes new fields
- [ ] Frontend types are updated
