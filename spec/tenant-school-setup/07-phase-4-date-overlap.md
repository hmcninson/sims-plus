# Phase 4: Academic Year Date Overlap Validation

**Complexity:** Small
**Requirements:** TS-024
**Dependencies:** Phase 3B (uses 'archived' status in exclusion filter)
**Estimated effort:** 0.5-1 day

---

## Summary

Add date range overlap validation when creating or updating academic years. Prevent two non-archived academic years from having overlapping date ranges within the same tenant/school.

---

## Task 1: Backend Overlap Validation

### File: `backend/app/services/academic/academic_year_service.py`

Add a private validation method to `AcademicYearMixin`:

```python
async def _validate_no_date_overlap(
    self,
    tenant_id: UUID,
    start_date: date,
    end_date: date,
    school_id: UUID | None = None,
    exclude_id: UUID | None = None,
) -> None:
    """
    Ensure no other non-archived academic year has overlapping dates.

    Two date ranges [A_start, A_end] and [B_start, B_end] overlap if:
        A_start <= B_end AND A_end >= B_start

    Args:
        tenant_id: Tenant UUID
        start_date: Proposed start date
        end_date: Proposed end date
        school_id: Optional school UUID (for chain tenants)
        exclude_id: Academic year ID to exclude (for updates)

    Raises:
        AcademicServiceError: If overlap detected
    """
    from app.models.academic.year_models import AcademicYear, AcademicYearStatus

    query = select(AcademicYear).where(
        and_(
            AcademicYear.tenant_id == tenant_id,
            AcademicYear.deleted_at.is_(None),
            # Exclude archived years — they don't conflict
            AcademicYear.status != AcademicYearStatus.ARCHIVED,
            # Overlap condition
            AcademicYear.start_date <= end_date,
            AcademicYear.end_date >= start_date,
        )
    )

    # For chain tenants, scope to school
    if school_id:
        query = query.where(AcademicYear.school_id == school_id)

    # Exclude the year being updated (for update operations)
    if exclude_id:
        query = query.where(AcademicYear.id != exclude_id)

    result = await self.db.execute(query)
    overlapping = result.scalar_one_or_none()

    if overlapping:
        raise AcademicServiceError(
            f"Date range ({start_date} to {end_date}) overlaps with "
            f"'{overlapping.name}' ({overlapping.start_date} to {overlapping.end_date}). "
            f"Academic years cannot have overlapping date ranges.",
            "DATE_OVERLAP",
        )
```

### Integrate into `create_academic_year()`:

```python
async def create_academic_year(
    self, tenant_id, name, start_date, end_date,
    description=None, is_current=False, school_id=None,
):
    # Basic date validation
    if start_date >= end_date:
        raise AcademicServiceError(
            "Start date must be before end date.",
            "INVALID_DATES",
        )

    # NEW: Check for date overlaps
    await self._validate_no_date_overlap(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        school_id=school_id,
    )

    # ... existing creation logic ...
```

### Integrate into `update_academic_year()`:

```python
async def update_academic_year(
    self, tenant_id, academic_year_id, **kwargs
):
    year = await self._get_academic_year(tenant_id, academic_year_id)

    # If dates are being changed, validate overlap
    new_start = kwargs.get("start_date", year.start_date)
    new_end = kwargs.get("end_date", year.end_date)

    if new_start != year.start_date or new_end != year.end_date:
        if new_start >= new_end:
            raise AcademicServiceError(
                "Start date must be before end date.",
                "INVALID_DATES",
            )

        # NEW: Check for date overlaps (excluding self)
        await self._validate_no_date_overlap(
            tenant_id=tenant_id,
            start_date=new_start,
            end_date=new_end,
            school_id=year.school_id,
            exclude_id=academic_year_id,
        )

    # ... existing update logic ...
```

---

## Task 2: Error Response

The `AcademicServiceError` is already handled by existing error handlers. The error code `DATE_OVERLAP` and message will be returned to the client.

If `AcademicServiceError` currently returns 400, that's fine. Alternatively, if you want to be more specific, map `DATE_OVERLAP` to 409 Conflict:

```python
# In the existing exception handler for AcademicServiceError:
if exc.code == "DATE_OVERLAP":
    return JSONResponse(status_code=409, content={"detail": exc.message, "code": exc.code})
```

---

## Task 3: Frontend Error Display

### File: `frontend/components/academic/AcademicYears.tsx`

The existing form error handling should already display server errors in a toast or inline message. Ensure that:

1. When creating an academic year and getting a `DATE_OVERLAP` error, the error message is displayed clearly:

```tsx
const handleCreate = async (data: AcademicYearFormData) => {
  const result = await createAcademicYear(data);
  if (!result.success) {
    // The error message from the server already explains the overlap
    toast.error(result.error);
    return;
  }
  // ... success handling ...
};
```

2. **Optional enhancement:** Add a visual timeline showing existing academic years to make overlaps obvious before the user submits:

```tsx
// In the academic year creation/edit dialog, show existing years:
<div className="mb-4">
  <p className="text-xs text-muted-foreground mb-1">Existing academic years:</p>
  <div className="space-y-1">
    {existingYears
      .filter((y) => y.status !== "archived")
      .map((y) => (
        <div key={y.id} className="flex items-center gap-2 text-xs">
          <Badge variant="outline" className="text-xs">
            {y.status}
          </Badge>
          <span>{y.name}</span>
          <span className="text-muted-foreground">
            ({y.start_date} - {y.end_date})
          </span>
        </div>
      ))}
  </div>
</div>
```

This gives the user visual context to avoid creating overlapping years.

---

## No Migration Needed

This is pure application-layer validation. No database changes required.

---

## Testing Checklist

- [ ] Create year 2025-2026 (Sep 1 - Jul 31) → success
- [ ] Create year 2026-2027 (Sep 1 - Jul 31) → success (no overlap)
- [ ] Create year 2025-2027 (Sep 1 - Jul 31) → error (overlaps both)
- [ ] Create year fully within existing range → error
- [ ] Create year partially overlapping at start → error
- [ ] Create year partially overlapping at end → error
- [ ] Create year adjacent but not overlapping (Jul 31 end, Aug 1 start) → success
- [ ] Update year to overlap with another → error
- [ ] Update year's own dates (no overlap with others) → success
- [ ] Archived year does NOT block new year in same date range → success
- [ ] Chain tenant: overlap check scoped to school_id → years in different schools can overlap
- [ ] Frontend displays overlap error message clearly
- [ ] Optional: timeline shows existing years in create dialog
