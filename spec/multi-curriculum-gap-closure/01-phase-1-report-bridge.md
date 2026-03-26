# Phase 1: Report Generation Bridge

**Priority:** Critical
**Effort:** 1.5-2 weeks (revised from 1 week after code review)
**Dependencies:** None
**Unblocks:** MC-014, MC-015, MC-016, MC-033, MC-034 (5 requirements)

> **Review Notes (2026-03-23):** This document was revised after cross-referencing
> against actual source code by 5 independent reviewers (code correctness, security,
> risk analysis, architecture, multi-tenancy). All critical bugs in the original
> pseudocode have been corrected. See `>>REVIEW FIX` markers for changes.

---

## Problem Statement

The score strategies (`GESScoreStrategy`, `AmericanScoreStrategy`, `IBScoreStrategy`, `FrenchScoreStrategy`) implement a `calculate_aggregate()` method that computes curriculum-specific aggregate data (GPA, IB total points, French mention, honor roll). However, `generate_term_reports()` in `report_service.py` never calls this method. Additionally, `generate_term_report_pdf()` in `pdf.py` hardcodes all curriculum-specific template context variables to `None`.

This means:
- American report cards have no GPA, no honor roll status, no credits
- IB report cards have no total points (out of 45)
- French report cards have no mention (Tres Bien, Bien, etc.)
- Cambridge report cards have no predicted grades passed through
- All TermReport curriculum columns (`gpa`, `weighted_gpa`, `cumulative_gpa`, `total_credits_earned`, `cumulative_credits`, `honor_roll`, `ib_total_points`, `french_mention`, `extra_data`) are permanently NULL

---

## Task A1: Populate Curriculum Aggregate Fields in `generate_term_reports()`

### File
`backend/app/services/exam/report_service.py`

### Current State

**`_calculate_student_term_scores_curriculum()` (lines 219-360):**
- Line 235: Calls `get_score_strategy(profile.curriculum_type.value)` to get the strategy instance
- Lines 270-350: Iterates over subjects, calling `strategy.calculate_subject_score()` per subject
- Lines 352-360: Sums `final_score` values to compute `total_score` and `average_score`
- Returns `(total_score, average_score, subjects_with_scores)` — a 3-tuple

**`generate_term_reports()` (lines 1558-1658):**
- Line 1608-1613: Calls `calculate_student_term_scores()` and receives `(total_score, average_score, subjects_count)`
- Lines 1615-1630: Sets `report.total_score`, `report.average_score`, `report.subjects_count`
- Does NOT set any curriculum-specific fields

### Required Changes

#### Step 1: Modify `_calculate_student_term_scores_curriculum()` return value

Change the method to also return the aggregate data from the strategy AND the resolved profile.

> **>>REVIEW FIX (C2):** The `subject_results` list does NOT exist in the current code.
> The loop at lines 284-354 only extracts `result.final_score` for summation and discards
> the `SubjectScoreResult`. You MUST create the list explicitly.
>
> **>>REVIEW FIX (R1):** After calling `strategy.calculate_subject_score()`, you must ALSO
> call `strategy.determine_grade()` to populate `result.grade_point`. Without this,
> `calculate_aggregate()` will see `grade_point=None` for every subject, and GPA will
> always compute as None/0. The current code calls `determine_grade()` only in
> `_get_student_subject_results_curriculum()` (a different method), not here.
>
> **>>REVIEW FIX (C3):** Return the resolved `profile` as part of the return tuple so
> `generate_term_reports()` does NOT redundantly call `_resolve_curriculum_profile()` again
> (which would add 50 unnecessary DB queries for a class of 50 students).

```python
# CURRENT (line 284-360, simplified):
# profile is resolved at the top of this method (~line 235)
# strategy = get_score_strategy(profile.curriculum_type.value)
total_score = Decimal("0")
subjects_with_scores = 0

for subject_id, score_data in student_scores.items():
    components = ...
    result = strategy.calculate_subject_score(score_data, components, max_scores)
    if result.final_score is not None:
        total_score += result.final_score
        subjects_with_scores += 1

average_score = total_score / subjects_with_scores if subjects_with_scores > 0 else Decimal("0")
return total_score, average_score, subjects_with_scores

# AFTER:
total_score = Decimal("0")
subjects_with_scores = 0
subject_results = []  # NEW: collect SubjectScoreResult objects for aggregate

# Load grading scale grades for determine_grade() calls
grades_list = []
if profile.grading_scale_id:
    grades_result = await self.db.execute(
        select(Grade)
        .where(
            Grade.tenant_id == tenant_id,
            Grade.grading_scale_id == profile.grading_scale_id,
        )
        .order_by(Grade.min_score.desc())
    )
    grades_list = grades_result.scalars().all()

for subject_id, score_data in student_scores.items():
    components = ...
    result = strategy.calculate_subject_score(score_data, components, max_scores)
    if result.final_score is not None:
        total_score += result.final_score
        subjects_with_scores += 1

        # NEW: Also determine the grade so grade_point is populated
        if grades_list:
            grade, grade_point, remark = strategy.determine_grade(
                result.final_score, grades_list
            )
            result.grade = grade
            result.grade_point = grade_point
            result.grade_remark = remark

        subject_results.append(result)

average_score = total_score / subjects_with_scores if subjects_with_scores > 0 else Decimal("0")

# NEW: Compute curriculum-specific aggregates (GPA, IB total, French mention)
aggregate_data = strategy.calculate_aggregate(subject_results, profile)

# Return 5-tuple: include resolved profile to avoid redundant resolution
return total_score, average_score, subjects_with_scores, aggregate_data, profile
```

**Critical implementation notes:**
1. The `subject_results` list MUST be explicitly created — it does not exist in the current code.
2. `strategy.determine_grade()` MUST be called to populate `result.grade_point` before `calculate_aggregate()`. Without this, GPA calculation will always return None/0.
3. `grades_list` must be loaded from the profile's grading scale. Filter by `Grade.tenant_id == tenant_id` for defense-in-depth.
4. The resolved `profile` is returned as the 5th element to eliminate redundant DB queries in the caller.

#### Step 2: Update `_calculate_student_term_scores_legacy()` to match signature

The legacy GES path should also return a 5-tuple for signature consistency:

```python
# At the end of _calculate_student_term_scores_legacy() (line ~561):
return total_score, average_score, subjects_with_scores, {}, None  # empty aggregate, no profile
```

#### Step 3: Update `calculate_student_term_scores()` dispatcher

The dispatcher method that chooses between legacy and curriculum paths must pass through the 5-tuple return value:

> **>>REVIEW FIX (C4):** Ensure `academic_year_id` is passed through to
> `_calculate_student_term_scores_curriculum()`. Currently `generate_term_reports()` does
> not pass it, which means year-specific assessment structures may not resolve correctly.

```python
# CURRENT:
if profile:
    return await self._calculate_student_term_scores_curriculum(...)
else:
    return await self._calculate_student_term_scores_legacy(...)

# AFTER: Both paths return 5-tuples. Also ensure academic_year_id is forwarded:
# calculate_student_term_scores(tenant_id, term_id, student_id, class_id, academic_year_id=None)
#   → _calculate_student_term_scores_curriculum(..., academic_year_id=academic_year_id)
```

#### Step 4: Populate TermReport fields in `generate_term_reports()`

After the `calculate_student_term_scores()` call, set the curriculum fields on the TermReport:

> **>>REVIEW FIX (C1):** The original pseudocode called `_resolve_curriculum_profile(tenant_id,
> student.id, class_id, school_id)` — this is WRONG. The actual method signature is
> `_resolve_curriculum_profile(self, tenant_id, class_id, student_id=None)`. It takes
> `class_id` as the 2nd positional arg and does NOT accept `school_id`.
>
> **>>REVIEW FIX (C3):** The profile is now returned as the 5th element of the tuple from
> `calculate_student_term_scores()`, eliminating the redundant resolution call entirely.

```python
# CURRENT (lines 1608-1630):
total_score, average_score, subjects_count = await self.calculate_student_term_scores(...)
report.total_score = total_score
report.average_score = average_score
report.subjects_count = subjects_count

# AFTER:
total_score, average_score, subjects_count, aggregate_data, profile = (
    await self.calculate_student_term_scores(
        tenant_id, term_id, student.id, class_id,
        academic_year_id=academic_year_id,  # REVIEW FIX: pass through
    )
)
report.total_score = total_score
report.average_score = average_score
report.subjects_count = subjects_count

# NEW: Populate curriculum-specific fields from aggregate_data
# The profile is returned from the score calculation — NO redundant DB call
if aggregate_data and profile:
    report.curriculum_profile_id = profile.id

    # American fields
    if "gpa" in aggregate_data:
        report.gpa = aggregate_data["gpa"]
    if "honor_roll" in aggregate_data:
        report.honor_roll = aggregate_data["honor_roll"]
    if "total_credits_earned" in aggregate_data:
        report.total_credits_earned = aggregate_data["total_credits_earned"]

    # IB fields
    if "ib_total_points" in aggregate_data:
        report.ib_total_points = aggregate_data["ib_total_points"]

    # French fields
    if "french_mention" in aggregate_data:
        report.french_mention = aggregate_data["french_mention"]

    # Generic extra data (for future curricula)
    remaining = {k: v for k, v in aggregate_data.items()
                 if k not in ("gpa", "honor_roll", "total_credits_earned",
                              "ib_total_points", "french_mention")}
    if remaining:
        report.extra_data = remaining
```

#### Step 5: Compute cumulative GPA and credits

For American curricula, cumulative GPA should factor in prior terms:

> **>>REVIEW FIX (R3):** `AmericanScoreStrategy.calculate_aggregate()` does NOT currently
> return a `weighted_gpa` key. It only returns `{"gpa", "total_credits_earned", "honor_roll"}`.
> To populate `report.weighted_gpa`, you must EITHER:
> (a) Extend `AmericanScoreStrategy.calculate_aggregate()` to also compute and return
>     `weighted_gpa` (recommended — add AP/Honors bonus calculation), OR
> (b) Compute it separately here from the subject_results and credit records.
>
> For Phase 1, option (a) is cleaner. Add `weighted_gpa` to the strategy return dict.
>
> **>>REVIEW NOTE (L2):** This uses a simple average of term GPAs for cumulative_gpa.
> Many American schools use credit-weighted cumulative GPA: `sum(gpa * credits) / sum(credits)`.
> The simple average is acceptable for Phase 1. Add a TODO for credit-weighted cumulative GPA.

```python
# After setting report.gpa, if the profile uses GPA:
if profile and profile.use_gpa and report.gpa is not None:
    # Query prior TermReports for this student in the same academic year
    prior_reports = await self.db.execute(
        select(TermReport)
        .where(
            TermReport.tenant_id == tenant_id,
            TermReport.student_id == student.id,
            TermReport.academic_year_id == academic_year_id,
            TermReport.term_id != term_id,
            TermReport.gpa.isnot(None),
            TermReport.deleted_at.is_(None),
        )
    )
    prior = prior_reports.scalars().all()

    if prior:
        all_gpas = [p.gpa for p in prior] + [report.gpa]
        report.cumulative_gpa = sum(all_gpas) / len(all_gpas)
        # TODO: Future iteration should use credit-weighted cumulative GPA
    else:
        report.cumulative_gpa = report.gpa

# Weighted GPA (requires extending AmericanScoreStrategy — see prerequisite below):
if profile and profile.use_gpa and "weighted_gpa" in aggregate_data:
    report.weighted_gpa = aggregate_data["weighted_gpa"]
```

#### Prerequisite: Extend `AmericanScoreStrategy.calculate_aggregate()`

The current `calculate_aggregate()` only returns `{"gpa", "total_credits_earned", "honor_roll"}`. Add `weighted_gpa` to the return dict:

```python
# In score_strategies.py, AmericanScoreStrategy.calculate_aggregate():
# After computing standard GPA, also compute weighted GPA with AP/Honors bonuses.
# AP courses get +1.0 bonus (capped at 5.0), Honors get +0.5 (capped at 4.5).
# The weighted calculation already exists in CreditService — port it here.
return {
    "gpa": gpa,
    "weighted_gpa": weighted_gpa,  # NEW
    "total_credits_earned": total_credits,
    "honor_roll": gpa >= Decimal("3.5"),
}
```

#### Step 6: Compute cumulative credits

```python
if profile and profile.use_credits and report.total_credits_earned is not None:
    # Query StudentCreditAccumulation for running total
    from app.models.curriculum import StudentCreditAccumulation
    credits_result = await self.db.execute(
        select(func.sum(StudentCreditAccumulation.credits_earned))
        .where(
            StudentCreditAccumulation.tenant_id == tenant_id,
            StudentCreditAccumulation.student_id == student.id,
            StudentCreditAccumulation.curriculum_profile_id == profile.id,
        )
    )
    report.cumulative_credits = credits_result.scalar() or report.total_credits_earned
```

### Strategy Aggregate Return Values (for reference)

These are the current return values from each strategy's `calculate_aggregate()`:

**AmericanScoreStrategy** (score_strategies.py lines 236-257):
```python
# CURRENT return value (before gap closure):
{
    "gpa": Decimal,           # 0.00 - 4.00
    "total_credits_earned": Decimal,
    "honor_roll": bool,       # True if GPA >= 3.5
}
# AFTER gap closure (add weighted_gpa — see prerequisite in Step 5):
{
    "gpa": Decimal,           # 0.00 - 4.00
    "weighted_gpa": Decimal,  # 0.00 - 5.00 (with AP/Honors bonuses) — NEW
    "total_credits_earned": Decimal,
    "honor_roll": bool,       # True if GPA >= 3.5
}
```

**IBScoreStrategy** (score_strategies.py lines 302-312):
```python
{
    "ib_total_points": int,   # 0 - 45 (sum of subject grade points)
}
```

**FrenchScoreStrategy** (score_strategies.py lines 366-388):
```python
{
    "french_mention": str,    # "Tres Bien" | "Bien" | "Assez Bien" | "Passable" | None
    "weighted_average": Decimal,  # 0.00 - 20.00
}
```

**GESScoreStrategy, CambridgeScoreStrategy, MontessoriScoreStrategy:**
```python
{}  # empty dict (no aggregates)
```

---

## Task A2: Wire Curriculum Data into PDF Template Context

### File
`backend/app/services/pdf.py`

### Current State

**`generate_term_report_pdf()` (lines 407-430):**
```python
# Curriculum-specific context - ALL hardcoded to None
"term_gpa": None,
"cumulative_gpa": None,
"total_credits_attempted": None,
"total_credits_earned": None,
"honor_roll": None,
"ib_total_points": None,
"ib_bonus_points": None,
"learner_profile_traits": None,
"atl_skills": None,
"mention": None,
"weighted_average": None,
"total_coefficients": None,
"total_weighted_score": None,
```

### Required Changes

Replace the hardcoded None values with actual data from the TermReport model. The `report` variable (the TermReport instance) is available in the method scope.

```python
# AFTER — read from the TermReport model:
"term_gpa": report.gpa,
"weighted_gpa": report.weighted_gpa,
"cumulative_gpa": report.cumulative_gpa,
"total_credits_attempted": None,  # Keep None; not stored on TermReport yet
"total_credits_earned": report.total_credits_earned,
"cumulative_credits": report.cumulative_credits,
"honor_roll": report.honor_roll,
"ib_total_points": report.ib_total_points,
"ib_bonus_points": (report.extra_data or {}).get("ib_bonus_points"),
"learner_profile_traits": (report.extra_data or {}).get("learner_profile_traits"),
"atl_skills": (report.extra_data or {}).get("atl_skills"),
"mention": report.french_mention,
"weighted_average": (report.extra_data or {}).get("weighted_average"),
"total_coefficients": (report.extra_data or {}).get("total_coefficients"),
"total_weighted_score": (report.extra_data or {}).get("total_weighted_score"),
```

### Template Variable Reference

Each template expects these context variables:

**american_report.html:**
- `term_gpa` — Decimal (e.g., 3.75)
- `weighted_gpa` — Decimal (e.g., 4.12)
- `cumulative_gpa` — Decimal (e.g., 3.80)
- `total_credits_earned` — Decimal (e.g., 18.0)
- `cumulative_credits` — Decimal (e.g., 54.0)
- `honor_roll` — bool

**ib_report.html:**
- `ib_total_points` — int (e.g., 38)
- `ib_bonus_points` — int (e.g., 2, from EE+TOK)
- `learner_profile_traits` — list of dicts `[{"trait": "Inquirers", "level": "Exceeding"}]`
- `atl_skills` — list of dicts `[{"skill": "Thinking", "level": "Proficient"}]`

**french_report.html:**
- `mention` — str (e.g., "Bien")
- `weighted_average` — Decimal (e.g., 14.5)
- `total_coefficients` — Decimal (sum of subject coefficients)
- `total_weighted_score` — Decimal (coefficient-weighted sum)

**cambridge_report.html:**
- Uses `subject_results[].effort_grade` (per-subject, not report-level)
- Uses `subject_results[].predicted_grade` (per-subject)

---

## Task A3: Calculate Subject Positions in Curriculum Path

### File
`backend/app/services/exam/report_service.py`

### Current State

**`_get_student_subject_results_curriculum()` (line 1337):**
```python
"subject_position": None,  # will be added in Phase 3
```

The legacy GES path (`_get_student_subject_results_legacy()`) correctly calculates subject positions using DENSE_RANK. The curriculum path skips this.

### Required Changes

Port the position calculation logic from the legacy path into the curriculum path. The logic is:

1. For each subject in the exam, fetch all students' final scores for that subject in the same class/section
2. Rank by score descending using DENSE_RANK
3. Assign the student's position

```python
# In _get_student_subject_results_curriculum(), after computing subject scores:

# Build a mapping of subject_id -> list of (student_id, final_score)
# for all students in the same class/section and term
if report_config and report_config.show_subject_position:
    subject_positions = await self._calculate_subject_positions_curriculum(
        tenant_id=tenant_id,
        exam_id=exam_id,
        class_id=class_id,
        section_id=section_id,
        student_id=student_id,
        profile=profile,
        strategy=strategy,
    )
    # subject_positions is a dict: subject_id -> position (int)
```

**New method `_calculate_subject_positions_curriculum()`:**

```python
async def _calculate_subject_positions_curriculum(
    self,
    tenant_id: UUID,
    exam_id: UUID,
    class_id: UUID,
    section_id: UUID | None,
    student_id: UUID,
    profile: CurriculumProfile,
    strategy: ScoreStrategy,
) -> dict[UUID, int]:
    """Calculate subject positions for a student using curriculum-aware scoring.

    Fetches all students' scores for the same exam/class, computes final_score
    using the curriculum strategy, then ranks by DENSE_RANK descending.
    """
    # 1. Get all students in this class/section
    # 2. For each subject, compute final_score using strategy.calculate_subject_score()
    # 3. Sort descending, assign DENSE_RANK
    # 4. Return {subject_id: position}
    ...
```

> **>>REVIEW FIX (M1):** Pre-computation is MANDATORY, not optional. Without it, bulk
> report generation for a class of 50 students with 10 subjects would trigger 25,000+
> strategy invocations (O(N^2 * S)), exceeding the 5-second p95 target.

**Performance requirement — pre-compute rankings before per-student loop:**

In `generate_term_reports()`, BEFORE the per-student loop, compute all subject positions once for the entire class:

```python
# BEFORE the per-student loop in generate_term_reports():
class_rankings = await self._precompute_class_rankings_curriculum(
    tenant_id, exam_id, class_id, section_id, profile, strategy
)
# class_rankings: dict[UUID, dict[UUID, int]]
#   → subject_id -> {student_id: position}

# Pass class_rankings to _get_student_subject_results_curriculum() as a parameter
# so it can look up positions in O(1) instead of recomputing
```

This reduces complexity from O(N^2 * S) to O(N * S) — compute all students' scores once, rank once, then look up per student.

**Implementation note:** The legacy path uses raw SQL with `DENSE_RANK() OVER (ORDER BY score DESC)`. The curriculum path cannot use this approach because the final_score is computed in Python (by the strategy), not stored directly in the database. Instead, use an in-memory sort and rank.

---

## Task A4: Tests for Curriculum-Aware Report Generation

### File
`backend/tests/test_curriculum_reports.py` (new file)

### Test Cases

#### A4.1: American GPA Population

```python
async def test_generate_term_reports_american_gpa(
    self, db, tenant_a_id, school_a_id
):
    """Verify that generate_term_reports populates GPA fields for American curriculum."""
    # Setup:
    # 1. Create an American curriculum profile (use_gpa=True, use_credits=True)
    # 2. Create a grading scale with A-F grades and grade_points
    # 3. Create an assessment structure (homework 20%, quiz 20%, test 30%, final 30%)
    # 4. Create academic year, term, class (with curriculum_profile_id)
    # 5. Enroll 3 students
    # 6. Create exam, exam_subjects, exam_scores for all students
    # 7. Call generate_term_reports()

    # Assertions:
    # - report.curriculum_profile_id == profile.id
    # - report.gpa is not None
    # - report.gpa is within valid range (0.0 - 4.0)
    # - report.honor_roll is True/False based on GPA >= 3.5
    # - report.cumulative_gpa is set (for first term, equals term GPA)
    # - report.total_credits_earned is not None
```

#### A4.2: IB Total Points Population

```python
async def test_generate_term_reports_ib_total_points(
    self, db, tenant_a_id, school_a_id
):
    """Verify ib_total_points populated for IB curriculum."""
    # Setup: IB DP profile, 6 subjects, scores entered
    # Assert: report.ib_total_points == sum of subject grade points (max 42 for 6 subjects)
```

#### A4.3: French Mention Population

```python
async def test_generate_term_reports_french_mention(
    self, db, tenant_a_id, school_a_id
):
    """Verify french_mention populated for French curriculum."""
    # Setup: French profile, scores averaging 15/20
    # Assert: report.french_mention == "Bien" (14 <= avg < 16)
```

#### A4.4: GES Backward Compatibility

```python
async def test_generate_term_reports_ges_no_regression(
    self, db, tenant_a_id, school_a_id
):
    """Verify existing GES schools are unaffected by aggregate changes."""
    # Setup: GES profile (or no profile), standard exam scores
    # Assert: report.gpa is None, report.ib_total_points is None, etc.
    # Assert: report.total_score and report.average_score still correct
```

#### A4.5: PDF Template Selection

```python
async def test_pdf_uses_correct_template_for_curriculum(
    self, db, tenant_a_id, school_a_id
):
    """Verify PDF generation selects the right template per curriculum."""
    # For each curriculum type, generate PDF and check template used
```

#### A4.6: PDF Context Contains Aggregate Data

```python
async def test_pdf_context_contains_gpa_for_american(
    self, db, tenant_a_id, school_a_id
):
    """Verify the PDF template context includes actual GPA data, not None."""
    # Setup: American profile, generate report, then generate PDF
    # Mock WeasyPrint to capture template context
    # Assert: context["term_gpa"] == report.gpa (not None)
```

#### A4.7: Cumulative GPA Across Terms

```python
async def test_cumulative_gpa_across_terms(
    self, db, tenant_a_id, school_a_id
):
    """Verify cumulative GPA averages across multiple terms."""
    # Setup: American profile, generate reports for Term 1 (GPA 3.5), then Term 2 (GPA 3.0)
    # Assert: Term 2 report.cumulative_gpa == 3.25
```

#### A4.8: Subject Position Calculation

```python
async def test_subject_position_in_curriculum_path(
    self, db, tenant_a_id, school_a_id
):
    """Verify subject positions are calculated for non-GES curricula."""
    # Setup: Cambridge profile, 3 students with different scores
    # Assert: Student with highest score has subject_position == 1
```

### Test Infrastructure Notes

- Use the existing `tenant_a_id`, `school_a_id` fixtures from `conftest.py`
- Create curriculum profile using raw SQL (not through the service, to avoid plan-limit checks in tests)
- Use `CurriculumProfileService.create_from_template("american_standard")` if plan limits are bypassed in test fixtures
- Set tenant subscription to "professional" or "enterprise" to bypass feature gates
- Use `pytest.mark.asyncio` for all async tests
- Include `@pytest.mark.curriculum` marker for selective test running

---

## Task A1 Implementation Checklist

- [ ] Add `subject_results = []` list variable in `_calculate_student_term_scores_curriculum()` (it does NOT exist — CRITICAL)
- [ ] Append each `SubjectScoreResult` to `subject_results` in the scoring loop
- [ ] Load `grades_list` from the profile's grading scale (with `Grade.tenant_id == tenant_id` filter)
- [ ] Call `strategy.determine_grade(result.final_score, grades_list)` per subject to populate `grade_point` (CRITICAL — without this, GPA is always None)
- [ ] Call `strategy.calculate_aggregate(subject_results, profile)` at end of method
- [ ] Extend `AmericanScoreStrategy.calculate_aggregate()` to return `weighted_gpa` key
- [ ] Return 5-tuple: `(total_score, average_score, subjects_with_scores, aggregate_data, profile)`
- [ ] Update `_calculate_student_term_scores_legacy()` to return 5-tuple with empty dict and None
- [ ] Pass `academic_year_id` through `calculate_student_term_scores()` dispatcher to curriculum path
- [ ] In `generate_term_reports()`, unpack 5th return value (profile) — do NOT call `_resolve_curriculum_profile()` again
- [ ] Set `report.curriculum_profile_id` from the returned profile
- [ ] Set `report.gpa` from `aggregate_data.get("gpa")`
- [ ] Set `report.weighted_gpa` from `aggregate_data.get("weighted_gpa")`
- [ ] Set `report.honor_roll` from `aggregate_data.get("honor_roll")`
- [ ] Set `report.total_credits_earned` from `aggregate_data.get("total_credits_earned")`
- [ ] Set `report.ib_total_points` from `aggregate_data.get("ib_total_points")`
- [ ] Set `report.french_mention` from `aggregate_data.get("french_mention")`
- [ ] Set `report.extra_data` for any remaining aggregate keys
- [ ] Compute `report.cumulative_gpa` from prior term reports (simple average for now; credit-weighted is future work)
- [ ] Compute `report.cumulative_credits` from StudentCreditAccumulation
- [ ] Add defense-in-depth `tenant_id` filter to Grade query and cumulative GPA query

## Task A2 Implementation Checklist

- [ ] Replace all hardcoded `None` values in pdf.py template context (lines 407-430)
- [ ] Read `report.gpa`, `report.weighted_gpa`, `report.cumulative_gpa` for American
- [ ] Read `report.total_credits_earned`, `report.cumulative_credits` for American
- [ ] Read `report.honor_roll` for American
- [ ] Read `report.ib_total_points` for IB
- [ ] Read `(report.extra_data or {}).get(...)` for IB bonus, ATL, learner profile
- [ ] Read `report.french_mention` for French
- [ ] Read `(report.extra_data or {}).get(...)` for French weighted average, coefficients
- [ ] Verify each template renders correctly with non-None values (manual test with sample data)

## Task A3 Implementation Checklist

- [ ] Create `_calculate_subject_positions_curriculum()` method in report_service.py
- [ ] Fetch all students in class/section for the exam
- [ ] Compute final_score for each student-subject using strategy
- [ ] Sort descending, assign DENSE_RANK positions
- [ ] Wire into `_get_student_subject_results_curriculum()` at line 1337
- [ ] Replace `"subject_position": None` with actual position
- [ ] Respect `report_config.show_subject_position` flag
- [ ] Pre-compute class rankings BEFORE per-student loop (MANDATORY for performance — see review fix M1)
- [ ] Pass pre-computed `class_rankings` dict to `_get_student_subject_results_curriculum()`
