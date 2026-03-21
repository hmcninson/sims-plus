# Phase 3B: Academic Year Archiving with Read-Only Enforcement

**Complexity:** Small
**Requirements:** TS-023
**Dependencies:** None
**Estimated effort:** 1-2 days

---

## Summary

Add an `archived` status to the `AcademicYearStatus` enum. Implement read-only enforcement so that archived (and completed) academic years cannot be modified. Create an archive endpoint and update the frontend to reflect archived state.

---

## Task 1: Add Archived Status to Enum

### File: `backend/app/models/academic/year_models.py`

Update the enum:

```python
class AcademicYearStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"  # NEW: Read-only, hidden by default
```

### Migration: `backend/alembic/versions/20260322_0300_academic_year_archiving.py`

```python
"""Add 'archived' value to academicyearstatus enum.

Revision ID: 20260322_0300
Revises: 20260322_0200
Create Date: 2026-03-22

Note: ALTER TYPE ... ADD VALUE cannot be run inside a transaction in PostgreSQL.
Alembic auto-commits this if needed, but we explicitly handle it.
"""

from alembic import op

revision = "20260322_0300"
down_revision = "20260322_0200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE to an existing enum
    # This is NOT reversible in PostgreSQL (cannot remove enum values)
    # Run outside transaction block
    op.execute("ALTER TYPE academicyearstatus ADD VALUE IF NOT EXISTS 'archived'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL
    # Downgrade would require recreating the enum type
    # This is intentionally left as no-op
    pass
```

**Important:** `ALTER TYPE ... ADD VALUE` cannot run inside a transaction. Alembic typically handles this, but if issues arise, use `op.execute()` with `execution_options={"isolation_level": "AUTOCOMMIT"}`.

---

## Task 2: Archive Endpoint

### File: `backend/app/api/v1/endpoints/academic/academic_years.py`

Add a new endpoint:

```python
@router.post(
    "/academic-years/{academic_year_id}/archive",
    response_model=AcademicYearResponse,
    dependencies=[Depends(require_permissions("academic.*"))],
)
async def archive_academic_year(
    academic_year_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_validated_current_user),
):
    """
    Archive an academic year.

    Requirements:
    - Academic year must be in 'completed' status
    - All terms within the year must be in 'completed' status
    - Cannot archive the current academic year (is_current=True)

    Once archived, the academic year and all associated data become read-only.
    """
    service = AcademicService(db)
    result = await service.archive_academic_year(
        tenant_id=UUID(current_user["tenant_id"]),
        academic_year_id=academic_year_id,
    )
    return result
```

### File: `backend/app/services/academic/academic_year_service.py`

Add to `AcademicYearMixin`:

```python
async def archive_academic_year(
    self, tenant_id: UUID, academic_year_id: UUID
) -> AcademicYear:
    """
    Transition an academic year from 'completed' to 'archived'.

    Validates:
    - Year exists and belongs to tenant
    - Status is 'completed'
    - is_current is False
    - All terms are 'completed'
    """
    year = await self.db.scalar(
        select(AcademicYear).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.id == academic_year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
    )

    if not year:
        raise AcademicServiceError("Academic year not found", "NOT_FOUND")

    if year.status != AcademicYearStatus.COMPLETED:
        raise AcademicServiceError(
            "Only completed academic years can be archived. "
            f"Current status: {year.status.value}",
            "INVALID_STATUS",
        )

    if year.is_current:
        raise AcademicServiceError(
            "Cannot archive the current academic year. "
            "Set another year as current first.",
            "IS_CURRENT",
        )

    # Check all terms are completed
    terms = await self.db.scalars(
        select(Term).where(
            and_(
                Term.tenant_id == tenant_id,
                Term.academic_year_id == academic_year_id,
                Term.deleted_at.is_(None),
            )
        )
    )
    incomplete_terms = [
        t for t in terms.all()
        if t.status != TermStatus.COMPLETED
    ]
    if incomplete_terms:
        names = ", ".join(t.name for t in incomplete_terms)
        raise AcademicServiceError(
            f"All terms must be completed before archiving. "
            f"Incomplete: {names}",
            "INCOMPLETE_TERMS",
        )

    year.status = AcademicYearStatus.ARCHIVED
    await self.db.flush()
    await self.db.refresh(year)

    logger.info(
        "academic_year_archived",
        tenant_id=str(tenant_id),
        academic_year_id=str(academic_year_id),
        year_name=year.name,
    )

    return year
```

---

## Task 3: Read-Only Enforcement in Services

Add validation guards to prevent modifications to archived/completed academic years.

### Helper Method (add to `AcademicYearMixin` or a shared utility):

```python
async def _assert_year_editable(self, tenant_id: UUID, academic_year_id: UUID) -> None:
    """
    Raise an error if the academic year is completed or archived.
    Call this before any write operation that references an academic year.
    """
    year = await self.db.scalar(
        select(AcademicYear.status).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.id == academic_year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
    )

    if year in (AcademicYearStatus.COMPLETED, AcademicYearStatus.ARCHIVED):
        raise AcademicServiceError(
            f"Cannot modify data in a {year.value} academic year. "
            "Academic years that are completed or archived are read-only.",
            "READ_ONLY_YEAR",
        )
```

### Apply Guards to These Service Methods:

**1. Academic Year Updates** — `backend/app/services/academic/academic_year_service.py`

In `update_academic_year()`:
```python
async def update_academic_year(self, tenant_id, academic_year_id, **kwargs):
    year = await self._get_academic_year(tenant_id, academic_year_id)

    # Guard: cannot modify completed/archived years
    if year.status in (AcademicYearStatus.COMPLETED, AcademicYearStatus.ARCHIVED):
        raise AcademicServiceError(
            f"Cannot modify a {year.status.value} academic year.",
            "READ_ONLY_YEAR",
        )

    # ... existing update logic ...
```

**Exception:** Allow changing status FROM completed TO archived (handled by archive endpoint). Also allow changing status FROM completed TO active (re-opening a year) if business rules permit. The guard should block field edits (name, dates) but not status transitions done through proper endpoints.

Refined guard:
```python
# Block updates to name, dates, etc. on completed/archived years
# Status changes are handled by dedicated endpoints (archive, complete)
non_status_changes = {k: v for k, v in kwargs.items() if k != "status"}
if non_status_changes and year.status in (AcademicYearStatus.COMPLETED, AcademicYearStatus.ARCHIVED):
    raise AcademicServiceError(
        f"Cannot modify a {year.status.value} academic year.",
        "READ_ONLY_YEAR",
    )
```

**2. Term Updates** — `backend/app/services/academic/academic_year_service.py`

In `create_term()`, `update_term()`, `delete_term()`:
```python
# Before creating/updating/deleting a term, check the parent year
await self._assert_year_editable(tenant_id, academic_year_id)
```

**3. Exam Creation** — `backend/app/services/exam/exam_service.py`

In `create_exam()`:
```python
# Look up the term's academic year and check editability
term = await self.db.get(Term, term_id)
if term:
    await self._assert_year_editable(tenant_id, term.academic_year_id)
```

Note: The exam service may not have `_assert_year_editable`. Options:
- Import and use `AcademicService` to call the check
- Or duplicate the check as a standalone function in a shared module

Recommended: Create a standalone utility:

### New File: `backend/app/services/academic/guards.py`

```python
"""
Academic year guard checks.

Shared utility to enforce read-only status on archived/completed years.
"""

from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic.year_models import AcademicYear, AcademicYearStatus


class ReadOnlyYearError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def assert_year_editable(
    db: AsyncSession,
    tenant_id: UUID,
    academic_year_id: UUID,
) -> None:
    """
    Raise ReadOnlyYearError if the academic year is completed or archived.

    Use this before any write operation that modifies data within an
    academic year (terms, exams, scores, attendance, etc.)
    """
    status = await db.scalar(
        select(AcademicYear.status).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.id == academic_year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
    )

    if status in (AcademicYearStatus.COMPLETED, AcademicYearStatus.ARCHIVED):
        raise ReadOnlyYearError(
            f"Cannot modify data in a {status.value} academic year. "
            "Completed and archived years are read-only."
        )


async def assert_term_year_editable(
    db: AsyncSession,
    tenant_id: UUID,
    term_id: UUID,
) -> None:
    """
    Look up a term's academic year and check if it's editable.

    Convenience wrapper: pass a term_id and it resolves the year.
    """
    from app.models.academic.year_models import Term

    term = await db.scalar(
        select(Term.academic_year_id).where(
            and_(
                Term.tenant_id == tenant_id,
                Term.id == term_id,
                Term.deleted_at.is_(None),
            )
        )
    )

    if term:
        await assert_year_editable(db, tenant_id, term)
```

### Register Exception Handler

In `backend/app/main.py`:

```python
from app.services.academic.guards import ReadOnlyYearError

@app.exception_handler(ReadOnlyYearError)
async def read_only_year_handler(request, exc: ReadOnlyYearError):
    return JSONResponse(
        status_code=409,  # Conflict — resource state prevents modification
        content={"detail": exc.message, "code": "READ_ONLY_YEAR"},
    )
```

### Services to Guard:

| Service | Method | Guard |
|---------|--------|-------|
| `academic_year_service.py` | `update_academic_year()` | `assert_year_editable(db, tenant_id, year_id)` |
| `academic_year_service.py` | `delete_academic_year()` | `assert_year_editable(db, tenant_id, year_id)` |
| `academic_year_service.py` | `create_term()` | `assert_year_editable(db, tenant_id, academic_year_id)` |
| `academic_year_service.py` | `update_term()` | `assert_year_editable(db, tenant_id, academic_year_id)` |
| `academic_year_service.py` | `delete_term()` | `assert_year_editable(db, tenant_id, academic_year_id)` |
| `exam_service.py` | `create_exam()` | `assert_term_year_editable(db, tenant_id, term_id)` |
| `exam_service.py` | `update_exam_scores()` | `assert_term_year_editable(db, tenant_id, exam.term_id)` |
| `attendance_service.py` | `mark_attendance()` | Check if term's year is archived (via date → term lookup) |

---

## Task 4: Frontend Updates

### File: `frontend/components/academic/AcademicYears.tsx`

**1. Add Archive button on completed years:**
```tsx
{year.status === "completed" && !year.is_current && (
  <Button
    variant="outline"
    size="sm"
    onClick={() => handleArchive(year.id)}
  >
    Archive
  </Button>
)}
```

**2. Disable edit/delete on archived years:**
```tsx
{year.status === "archived" ? (
  <Badge variant="secondary">Archived</Badge>
) : (
  // existing edit/delete buttons
)}
```

**3. Filter archived years by default:**
```tsx
const [showArchived, setShowArchived] = useState(false);

const filteredYears = years.filter((y) =>
  showArchived ? true : y.status !== "archived"
);

// Toggle:
<label className="flex items-center gap-2 text-sm">
  <Checkbox
    checked={showArchived}
    onCheckedChange={(v) => setShowArchived(!!v)}
  />
  Show archived years
</label>
```

**4. Read-only banner when viewing archived year's data:**
```tsx
{selectedYear?.status === "archived" && (
  <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
    This academic year is archived. All records are read-only.
  </div>
)}
```

### Server Action

### File: `frontend/actions/academic.action.ts`

Add:

```typescript
export async function archiveAcademicYear(
  yearId: string,
): Promise<ActionResult<AcademicYear>> {
  try {
    const response = await apiPost<AcademicYear>(
      `/academic/academic-years/${yearId}/archive`,
      {},
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to archive academic year",
    };
  }
}
```

### File: `frontend/types/index.ts`

Update AcademicYear status type:

```typescript
interface AcademicYear {
  // ... existing fields ...
  status: "planning" | "active" | "completed" | "archived";  // Add "archived"
}
```

---

## Testing Checklist

- [ ] Migration adds 'archived' to enum without issues
- [ ] `POST /academic-years/{id}/archive` on completed year → success (200)
- [ ] Archive on active year → error (must be completed first)
- [ ] Archive on current year → error (must unset is_current first)
- [ ] Archive with incomplete terms → error (lists incomplete terms)
- [ ] Update archived year's name → 409 READ_ONLY_YEAR
- [ ] Create term in archived year → 409 READ_ONLY_YEAR
- [ ] Create exam in archived year's term → 409 READ_ONLY_YEAR
- [ ] Enter scores in archived year's exam → 409 READ_ONLY_YEAR
- [ ] Frontend: Archive button appears on completed years
- [ ] Frontend: Archived years are grayed out, no edit/delete
- [ ] Frontend: Archived years hidden by default, shown with toggle
- [ ] Frontend: Read-only banner displayed when viewing archived year data
