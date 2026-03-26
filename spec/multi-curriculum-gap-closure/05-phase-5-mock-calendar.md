# Phase 5: Mock Exam Integration & Academic Calendar Validation

**Priority:** Medium
**Effort:** 1 week
**Dependencies:** None (independent of other phases)
**Unblocks:** MC-005 (calendar validation), MC-046 (mock exam curriculum integration)

---

## Part A: Academic Calendar Validation (MC-005)

### Problem Statement

`CurriculumProfile` has `academic_calendar_type` (terms/semesters/quarters) and `periods_per_year` (default 3). However, when schools create terms for an academic year, there is no validation that the number of terms matches the curriculum profile's expected period count. A school configured for "semesters" (2 periods) could accidentally create 3 terms.

### Task E1: Validate Term Count Against Curriculum Profile

#### File
`backend/app/services/academic/academic_year_service.py`

#### Current State

**`create_term()` or the term creation method:**
- Accepts name, start_date, end_date, academic_year_id
- Validates date ranges don't overlap
- Does NOT check how many terms already exist for the year
- Does NOT reference curriculum profile

#### Required Changes

Add a warning (not a hard block) when the term count exceeds the curriculum profile's `periods_per_year`:

```python
async def create_term(
    self,
    tenant_id: UUID,
    academic_year_id: UUID,
    name: str,
    start_date: date,
    end_date: date,
    **kwargs,
) -> Term:
    """Create a term for an academic year.

    Validates dates and warns if term count exceeds curriculum profile's
    periods_per_year.
    """
    # ... existing validation ...

    # NEW: Check term count against curriculum profile
    warning = None

    # Count existing terms for this academic year
    term_count_result = await self.db.execute(
        select(func.count(Term.id))
        .where(
            Term.tenant_id == tenant_id,
            Term.academic_year_id == academic_year_id,
            Term.deleted_at.is_(None),
        )
    )
    existing_count = term_count_result.scalar() or 0

    # Resolve school's default curriculum profile
    from app.models.curriculum import CurriculumProfile
    school = await self._get_school(tenant_id)
    if school and school.curriculum_profile_id:
        profile = await self.db.get(CurriculumProfile, school.curriculum_profile_id)
        if profile and (existing_count + 1) > profile.periods_per_year:
            warning = (
                f"This will create {existing_count + 1} terms, but the "
                f"'{profile.name}' curriculum expects {profile.periods_per_year} "
                f"{profile.academic_calendar_type.value} per year."
            )

    # ... create term ...

    # Return term with optional warning
    # (Add warning field to response schema)
    return term, warning
```

#### Design Decision: Warning vs Hard Block

**Recommended: Warning only**, because:
1. Schools transitioning between curricula may need flexibility
2. Chain schools with mixed curricula may have different periods per school
3. Hard-blocking would break existing data entry flows

> **>>REVIEW FIX (M4):** The `(term, warning)` return pattern is novel in this codebase.
> To avoid changing the service method signature, check the term count in the **endpoint
> handler** instead. The service stays clean; the UI concern is localized to the endpoint.

The warning should be:
- Checked in the endpoint handler (not the service layer)
- Returned in the API response as a `warning` field on the response schema
- Displayed as a yellow toast/banner on the frontend
- Logged for audit purposes

#### Schema Change

```python
# schemas/academic.py — TermCreateResponse (extend or create)
class TermCreateResponse(BaseSchema):
    term: TermResponse
    warning: Optional[str] = None
```

#### Endpoint Change (instead of service change)

```python
# In the term creation endpoint handler:
term = await academic_service.create_term(...)

# Check term count vs curriculum profile AFTER creation
warning = None
term_count = await db.scalar(
    select(func.count(Term.id)).where(
        Term.tenant_id == tenant_id,
        Term.academic_year_id == academic_year_id,
        Term.deleted_at.is_(None),
    )
)
if school.curriculum_profile_id:
    profile = await db.get(CurriculumProfile, school.curriculum_profile_id)
    if profile and term_count > profile.periods_per_year:
        warning = f"You now have {term_count} terms, but ..."

return TermCreateResponse(term=term, warning=warning)
```

#### Frontend Change

In the term creation dialog/form, after successful creation:

```tsx
if (result.warning) {
  toast({
    title: "Term Created",
    description: result.warning,
    variant: "warning",  // yellow/amber styling
  });
}
```

---

## Part B: Mock Exam Curriculum Integration (MC-046)

### Problem Statement

Mock exams work via `ExamType.MOCK` in the existing exam workflow. However:
1. Mock exam subjects don't inherit the curriculum's assessment component structure
2. There's no link between mock exam results and predicted grades
3. A Cambridge mock should match the same Paper 1 + Paper 2 + Coursework structure as the real exam

### Task H1: Link Mock Exam Results to Predicted Grades

#### Files
- `backend/app/services/exam/exam_service.py`
- `backend/app/api/v1/endpoints/exams/exams.py`
- `backend/app/services/curriculum/predicted_grade_service.py`

#### Design

After a mock exam's results are published, offer an action to auto-populate predicted grades based on mock results. This is a **suggestion**, not automatic — teachers should review and adjust.

#### New Endpoint

```python
# api/v1/endpoints/exams/exams.py

@router.post(
    "/{exam_id}/generate-predicted-grades",
    response_model=PredictedGradeBulkResponse,
    status_code=200,
)
async def generate_predicted_grades_from_mock(
    exam_id: UUID,
    user: ValidatedUser = Depends(require_permissions("curriculum.create")),
    db: AsyncSession = Depends(get_db),
):
    """Generate predicted grades from mock exam results.

    Only works for mock exams (exam_type='mock') with published results.
    Creates/updates PredictedGrade records for each student-subject.
    """
    # >>REVIEW FIX (H3): Check subscription tier — predicted grades require Professional+
    from app.services.curriculum._shared import check_multi_curriculum_access
    await check_multi_curriculum_access(db, user.tenant_id)

    exam_service = ExamService(db)
    return await exam_service.generate_predicted_grades_from_mock(
        tenant_id=user.tenant_id,
        exam_id=exam_id,
        predicted_by=user.id,
    )
```

#### New Service Method

```python
# services/exam/exam_service.py

async def generate_predicted_grades_from_mock(
    self,
    tenant_id: UUID,
    exam_id: UUID,
    predicted_by: UUID,
) -> dict:
    """Generate predicted grades from mock exam results.

    For each student-subject in the mock exam:
    1. Compute the grade using the curriculum's score strategy
    2. Create/update a PredictedGrade record

    Returns: {"created": int, "updated": int, "skipped": int}
    """
    # 1. Fetch exam and validate it's a mock with published results
    exam = await self._get_exam(tenant_id, exam_id)
    if not exam:
        raise ExamServiceError("Exam not found", "not_found")
    if exam.exam_type != "mock":
        raise ExamServiceError("Only mock exams can generate predicted grades", "invalid_type")
    if exam.status != "results_published":
        raise ExamServiceError("Results must be published first", "invalid_status")

    # 2. Resolve curriculum profile for the exam's class(es)
    # (Mock exams may cover multiple classes — get the first class's profile)
    exam_subjects = await self._get_exam_subjects_with_scores(tenant_id, exam_id)

    class_ids = set()
    for es in exam_subjects:
        # Get class from exam subject enrollment
        class_ids.add(es.class_id)

    # Use first class to resolve profile (assumption: mock exam covers one curriculum)
    profile = None
    if class_ids:
        first_class_id = next(iter(class_ids))
        class_obj = await self.db.get(Class, first_class_id)
        if class_obj and class_obj.curriculum_profile_id:
            profile = await self.db.get(CurriculumProfile, class_obj.curriculum_profile_id)

    if not profile:
        raise ExamServiceError(
            "No curriculum profile found for this class. Predicted grades require a curriculum profile.",
            "no_profile"
        )

    # 3. Get score strategy
    strategy = get_score_strategy(profile.curriculum_type.value)

    # 4. For each student-subject, compute grade and create predicted grade
    from app.models.curriculum import PredictedGrade
    from datetime import datetime, timezone

    created = 0
    updated = 0
    skipped = 0

    for exam_subject in exam_subjects:
        for score in exam_subject.scores:
            if score.is_absent or score.score is None:
                skipped += 1
                continue

            # Compute grade using strategy
            grade_info = strategy.determine_grade(
                score.score,
                grades_list,  # from the profile's grading scale
            )
            predicted_grade_value = grade_info[0] if grade_info else None

            if not predicted_grade_value:
                skipped += 1
                continue

            # Upsert PredictedGrade
            existing = await self.db.execute(
                select(PredictedGrade).where(
                    PredictedGrade.tenant_id == tenant_id,
                    PredictedGrade.student_id == score.student_id,
                    PredictedGrade.subject_id == exam_subject.subject_id,
                    PredictedGrade.academic_year_id == exam.academic_year_id,
                    PredictedGrade.deleted_at.is_(None),
                )
            )
            pg = existing.scalar_one_or_none()

            if pg:
                # >>REVIEW FIX (H2): Do NOT silently overwrite manually-set predictions.
                # Check the source field — only overwrite if previously auto-generated.
                if pg.notes and "Auto-generated from mock exam" not in (pg.notes or ""):
                    # This was manually set by a teacher — skip unless force=True
                    skipped += 1
                    continue
                pg.predicted_grade = predicted_grade_value
                pg.predicted_score = score.score
                pg.predicted_by = predicted_by
                pg.predicted_at = datetime.now(timezone.utc)
                pg.notes = f"Auto-generated from mock exam: {exam.name}"
                updated += 1
            else:
                pg = PredictedGrade(
                    tenant_id=tenant_id,
                    student_id=score.student_id,
                    subject_id=exam_subject.subject_id,
                    academic_year_id=exam.academic_year_id,
                    term_id=exam.term_id,
                    predicted_grade=predicted_grade_value,
                    predicted_score=score.score,
                    predicted_by=predicted_by,
                    predicted_at=datetime.now(timezone.utc),
                    notes=f"Auto-generated from mock exam: {exam.name}",
                )
                self.db.add(pg)
                created += 1

    await self.db.flush()
    return {"created": created, "updated": updated, "skipped": skipped}
```

#### Frontend

Add a "Generate Predicted Grades" button on the mock exam detail page, visible only when:
- `exam.exam_type === "mock"`
- `exam.status === "results_published"`
- The class has a non-GES curriculum profile

```tsx
{exam.exam_type === "mock" && exam.status === "results_published" && (
  <Button
    variant="outline"
    onClick={handleGeneratePredictedGrades}
  >
    Generate Predicted Grades from Mock Results
  </Button>
)}
```

Show a confirmation dialog explaining:
> "This will create predicted grades for all students based on their mock exam scores. Existing predicted grades will be updated. Teachers can review and adjust predicted grades in the Predicted Grades page."

---

## Task H2: Mock Exam Component Structure Pre-Population

#### Files
- `backend/app/services/exam/exam_service.py`
- `backend/app/api/v1/endpoints/exams/exams.py`

#### Design

When creating a mock exam for a non-GES class, optionally pre-populate the exam with subject-component structure matching the class's assessment structure.

This is a convenience feature, not a requirement. The exam creator can choose to use it or create a standard mock.

#### New Endpoint

```python
@router.post(
    "/{exam_id}/apply-curriculum-structure",
    status_code=200,
)
async def apply_curriculum_structure_to_exam(
    exam_id: UUID,
    class_id: UUID = Query(..., description="Class to copy assessment structure from"),
    user: ValidatedUser = Depends(require_permissions("exams.create")),
    db: AsyncSession = Depends(get_db),
):
    """Apply the class's curriculum assessment structure to a mock exam.

    For each subject in the exam, creates sub-scores matching the
    assessment components (e.g., Paper 1, Paper 2, Coursework for Cambridge).
    """
    ...
```

#### Implementation Notes

**Assessment component structure** is defined at the curriculum profile level, not the subject level. For Cambridge IGCSE:
- Component 1: Coursework (25%)
- Component 2: Controlled Assessment (25%)
- Component 3: External Exam (50%)

A "Cambridge mock" should mirror this structure. Since the existing `ExamScore` model stores a single `score` value per student-subject, the component-level scores would need to use the `ExamScore.extra_data` JSONB field (if it exists) or we'd need one `ExamScore` row per component.

**Recommendation:** For this phase, keep it simple:
1. When "Apply Curriculum Structure" is clicked, add a note to the exam description listing the expected component structure
2. The score entry form (Phase 2) already shows the assessment components — teachers enter weighted scores that map to components
3. Do NOT create separate ExamScore rows per component (that would be a larger schema change)

This means Task H2 is primarily a **frontend UX enhancement** — displaying the expected component structure when entering mock exam scores, rather than a deep backend change.

---

## Checklist

### Task E1 (Calendar Validation)
- [ ] Count existing terms for academic year in `create_term()`
- [ ] Resolve school's default curriculum profile
- [ ] Compare (existing_count + 1) against `periods_per_year`
- [ ] Return warning string if exceeded (not a hard block)
- [ ] Add `warning` field to term creation response schema
- [ ] Frontend: show warning toast on term creation
- [ ] Test: creating 3rd term with 2-period curriculum shows warning
- [ ] Test: creating 3rd term with 3-period curriculum shows no warning
- [ ] Test: creating term with no curriculum profile shows no warning

### Task H1 (Mock → Predicted Grades)
- [ ] Create `generate_predicted_grades_from_mock()` service method
- [ ] Validate exam is mock type with published results
- [ ] Resolve curriculum profile from exam's class
- [ ] Compute grade for each student-subject using strategy
- [ ] Upsert PredictedGrade records
- [ ] Set `notes` field indicating auto-generation source
- [ ] Create POST endpoint `/exams/{id}/generate-predicted-grades`
- [ ] Frontend: "Generate Predicted Grades" button on mock exam page
- [ ] Confirmation dialog before generation
- [ ] Show results (created/updated/skipped counts)
- [ ] Test: generate predicted grades from Cambridge mock
- [ ] Test: reject for non-mock exam
- [ ] Test: reject for unpublished results
- [ ] Test: update existing predicted grades

### Task H2 (Mock Component Structure)
- [ ] Display expected component structure in score entry for mock exams
- [ ] Source structure from class's curriculum profile
- [ ] Show component names, weights, and max scores as column headers
- [ ] No backend schema changes needed (use existing assessment components)
- [ ] Test: mock exam for Cambridge class shows Paper 1/2/Coursework headers
- [ ] Test: mock exam for GES class shows standard CA/Exam headers
