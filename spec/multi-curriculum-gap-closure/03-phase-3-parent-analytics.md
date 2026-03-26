# Phase 3: Parent Portal & Analytics Curriculum Awareness

**Priority:** High
**Effort:** 1.5 weeks
**Dependencies:** Phase 1 (report generation must populate curriculum fields first)
**Unblocks:** Correct grade display for non-GES parents, meaningful analytics for all curricula

---

## Problem Statement

### Parent Portal
`ParentAcademicService.get_child_grades()` (parent_academic.py lines 46-282) hardcodes the GES scoring format: it computes `total = ca_score + exam_score` and shows a simple percentage average. For a parent whose child is in a Cambridge, American, or IB class, this produces misleading data:
- No GPA shown for American curriculum students
- No IB total points shown for IB students
- No component-level score breakdown (only CA+Exam)
- No French mention for French curriculum students
- Grade trend shows raw percentage average, not GPA trend

### Analytics
The analytics service uses hardcoded pass mark of 50% and operates on raw percentage scores. For IB (1-7 scale), French (0-20 scale), or narrative-based Montessori, these statistics are meaningless.

---

## Task C1: Make `get_child_grades()` Curriculum-Aware

### File
`backend/app/services/parent/parent_academic.py`

### Current State

**`get_child_grades()` (lines 46-282):**
```python
# Line 113-134: Fetches ExamScores with status == "results_published"
# Line 221-227: Computes total = ca_score + exam_score (GES-only)
# Line 255-256: average = total_marks / subjects_with_scores
# NO curriculum profile resolution
# NO GPA, IB points, or mention data
```

**`_get_class_averages_for_term()` (lines 284-322):**
```python
# Uses func.avg(ExamScore.score) directly — raw average, GES-only
```

### Required Changes

#### Step 1: Resolve curriculum profile for the child's class

At the top of `get_child_grades()`, after fetching the student's current class:

```python
from app.models.curriculum import CurriculumProfile
from app.services.exam.score_strategies import get_score_strategy

# Resolve curriculum profile (student → class → school → None)
curriculum_profile = None
curriculum_type = "ges"

if student.curriculum_profile_id:
    curriculum_profile = await self.db.get(CurriculumProfile, student.curriculum_profile_id)
elif student_class and student_class.curriculum_profile_id:
    curriculum_profile = await self.db.get(CurriculumProfile, student_class.curriculum_profile_id)
elif school and school.curriculum_profile_id:
    curriculum_profile = await self.db.get(CurriculumProfile, school.curriculum_profile_id)

if curriculum_profile:
    curriculum_type = curriculum_profile.curriculum_type.value
```

#### Step 2: Branch logic based on curriculum type

```python
if curriculum_type == "ges" or curriculum_profile is None:
    # Existing GES logic (lines 113-260) — no change
    subjects_data = await self._get_child_grades_ges(...)
else:
    # New curriculum-aware path
    subjects_data = await self._get_child_grades_curriculum(
        student_id, term_id, curriculum_profile, ...
    )
```

#### Step 3: Implement `_get_child_grades_curriculum()`

```python
async def _get_child_grades_curriculum(
    self,
    student_id: UUID,
    term_id: UUID,
    profile: CurriculumProfile,
    academic_year_id: UUID,
    class_id: UUID,
) -> dict:
    """Get grades for a student using curriculum-aware scoring."""
    strategy = get_score_strategy(profile.curriculum_type.value)

    # 1. Fetch the assessment structure for this profile
    from app.models.curriculum import AssessmentStructure, AssessmentComponent
    structure = await self.db.execute(
        select(AssessmentStructure)
        .options(selectinload(AssessmentStructure.components))
        .where(
            AssessmentStructure.tenant_id == self.tenant_id,
            AssessmentStructure.curriculum_profile_id == profile.id,
            AssessmentStructure.is_active == True,
            AssessmentStructure.deleted_at.is_(None),
        )
        .order_by(
            # Prefer year-specific, fall back to default
            AssessmentStructure.academic_year_id.desc().nullslast()
        )
        .limit(1)
    )
    structure = structure.scalar_one_or_none()

    # 2. Fetch exam scores for the student in this term
    # (Same query as existing, but include effort_grade)
    scores_result = await self.db.execute(
        select(ExamScore, Subject.name, Subject.code)
        .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
        .join(Subject, ExamSubject.subject_id == Subject.id)
        .join(Exam, ExamSubject.exam_id == Exam.id)
        .where(
            ExamScore.tenant_id == self.tenant_id,
            ExamScore.student_id == student_id,
            Exam.term_id == term_id,
            Exam.status == "results_published",
        )
    )
    scores = scores_result.all()

    # 3. Group scores by subject, compute using strategy
    subject_scores = {}
    for score, subject_name, subject_code in scores:
        if score.subject_id not in subject_scores:
            subject_scores[score.subject_id] = {
                "name": subject_name,
                "code": subject_code,
                "scores": {},
            }
        # Map score to component type
        # (This requires knowing which component each score belongs to)
        ...

    # 4. For each subject, call strategy.calculate_subject_score()
    results = []
    for subject_id, data in subject_scores.items():
        result = strategy.calculate_subject_score(
            data["scores"], components, max_scores
        )
        results.append({
            "subject_name": data["name"],
            "subject_code": data["code"],
            "final_score": result.final_score,
            "grade": result.grade,
            "grade_point": result.grade_point,
            "effort_grade": result.effort_grade,
            "component_scores": result.component_scores,
        })

    # 5. Read aggregate data from TermReport (populated by Phase 1)
    term_report = await self.db.execute(
        select(TermReport)
        .where(
            TermReport.tenant_id == self.tenant_id,
            TermReport.student_id == student_id,
            TermReport.term_id == term_id,
            TermReport.deleted_at.is_(None),
        )
    )
    report = term_report.scalar_one_or_none()

    # 6. Build response with curriculum-specific fields
    return {
        "curriculum_type": profile.curriculum_type.value,
        "score_display_mode": profile.score_display_mode.value,
        "subjects": results,
        "total_score": report.total_score if report else None,
        "average_score": report.average_score if report else None,
        "class_position": report.class_position if report else None,
        # American
        "gpa": report.gpa if report else None,
        "weighted_gpa": report.weighted_gpa if report else None,
        "cumulative_gpa": report.cumulative_gpa if report else None,
        "honor_roll": report.honor_roll if report else None,
        "total_credits_earned": report.total_credits_earned if report else None,
        # IB
        "ib_total_points": report.ib_total_points if report else None,
        # French
        "french_mention": report.french_mention if report else None,
    }
```

**Alternative simpler approach:** Instead of re-computing scores in the parent service, just read the TermReport and its associated subject results that were already computed during report generation. This avoids duplicating the strategy dispatch logic:

```python
async def _get_child_grades_curriculum(self, student_id, term_id, profile, ...):
    """Read pre-computed curriculum grades from TermReport."""
    # Fetch TermReport with subject results
    report = await self._get_term_report(student_id, term_id)
    if not report:
        return {"curriculum_type": profile.curriculum_type.value, "subjects": []}

    # Fetch subject results from report_service
    subject_results = await self.report_service.get_student_subject_results(
        tenant_id=self.tenant_id,
        term_report_id=report.id,
    )

    return {
        "curriculum_type": profile.curriculum_type.value,
        "score_display_mode": profile.score_display_mode.value,
        "subjects": subject_results,
        "gpa": report.gpa,
        "weighted_gpa": report.weighted_gpa,
        "cumulative_gpa": report.cumulative_gpa,
        "honor_roll": report.honor_roll,
        "total_credits_earned": report.total_credits_earned,
        "ib_total_points": report.ib_total_points,
        "french_mention": report.french_mention,
        "class_position": report.class_position,
    }
```

> **>>REVIEW FIX (H2):** The "read from TermReport" approach creates a timing
> inconsistency: GES parents see live scores (from ExamScore queries), but non-GES
> parents would see nothing until `generate_term_reports()` runs. Use a **hybrid approach**:
> - Per-subject scores: Use the existing ExamScore query path (live data)
> - Aggregate metrics (GPA, IB total, French mention): Read from TermReport
>
> This gives parents immediate access to raw scores while aggregate metrics appear
> after report generation. The `ParentAcademicService` has `self.db` but not
> `self.tenant_id` — tenant_id is passed as a parameter to each method.

**Decision for developers:** Use the **hybrid approach**. For per-subject scores, query ExamScore directly (same as GES path) but display using the curriculum's score_display_mode. For aggregate metrics (GPA, IB total points, French mention, honor roll), read from TermReport. Show a "Reports not yet generated" notice if the TermReport doesn't exist yet.

#### Step 4: Update the response schema

Add curriculum fields to the parent grades response:

```python
# schemas/parent.py — ChildGradesResponse (create or extend)
class ChildGradesResponse(BaseSchema):
    curriculum_type: str = "ges"
    score_display_mode: str = "grade_and_score"
    subjects: list[SubjectGradeResponse]
    total_score: Optional[Decimal] = None
    average_score: Optional[Decimal] = None
    class_position: Optional[int] = None
    # Curriculum-specific
    gpa: Optional[Decimal] = None
    weighted_gpa: Optional[Decimal] = None
    cumulative_gpa: Optional[Decimal] = None
    honor_roll: Optional[bool] = None
    total_credits_earned: Optional[Decimal] = None
    ib_total_points: Optional[int] = None
    french_mention: Optional[str] = None
```

---

## Task C2: Curriculum-Appropriate Grade Trend

### File
`backend/app/services/parent/parent_academic.py`

### Current State

**`get_child_grade_trend()` (lines 348-404):**
- Reads `average_score` and `class_position` from TermReport
- Returns a list of `{term_name, average_score, class_position}` objects

### Required Changes

For non-GES curricula, the trend should show the curriculum-appropriate metric:

```python
async def get_child_grade_trend(self, student_id: UUID) -> list[dict]:
    # Existing query to fetch TermReports across terms
    reports = ...

    # Resolve curriculum profile for the student
    profile = await self._resolve_profile(student_id)
    curriculum_type = profile.curriculum_type.value if profile else "ges"

    trend = []
    for report in reports:
        entry = {
            "term_name": report.term.name,
            "class_position": report.class_position,
        }

        if curriculum_type == "american":
            entry["metric"] = "gpa"
            entry["value"] = float(report.gpa) if report.gpa else None
            entry["label"] = f"GPA: {report.gpa}" if report.gpa else "N/A"
        elif curriculum_type == "ib":
            entry["metric"] = "ib_total_points"
            entry["value"] = report.ib_total_points
            entry["label"] = f"{report.ib_total_points}/45" if report.ib_total_points else "N/A"
        elif curriculum_type == "french":
            entry["metric"] = "average"
            entry["value"] = float(report.average_score) if report.average_score else None
            entry["label"] = report.french_mention or "N/A"
        else:
            # GES, Cambridge, Edexcel, Montessori, Custom
            entry["metric"] = "average_score"
            entry["value"] = float(report.average_score) if report.average_score else None
            entry["label"] = f"{report.average_score}%" if report.average_score else "N/A"

        trend.append(entry)

    return trend
```

**Response schema update:**

```python
class GradeTrendEntry(BaseSchema):
    term_name: str
    class_position: Optional[int] = None
    metric: str  # "gpa", "ib_total_points", "average_score", "average"
    value: Optional[float] = None
    label: str
```

---

## Task C3: Frontend — Parent Portal Grade View Adaptation

### Files
- `frontend/app/(parent)/parent/` — Grades/academic pages
- `frontend/types/parent.type.ts` — Parent portal types

### Required Changes

#### Step 1: Update TypeScript types

```typescript
interface ChildGrades {
  curriculum_type: string;
  score_display_mode: string;
  subjects: SubjectGrade[];
  total_score: number | null;
  average_score: number | null;
  class_position: number | null;
  // Curriculum-specific
  gpa: number | null;
  weighted_gpa: number | null;
  cumulative_gpa: number | null;
  honor_roll: boolean | null;
  total_credits_earned: number | null;
  ib_total_points: number | null;
  french_mention: string | null;
}
```

#### Step 2: Curriculum-specific summary card

Replace the static "Average Score" card with a curriculum-aware one:

```tsx
function GradeSummaryCard({ grades }: { grades: ChildGrades }) {
  switch (grades.curriculum_type) {
    case "american":
      return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Term GPA" value={grades.gpa?.toFixed(2) ?? "N/A"} />
          <StatCard label="Cumulative GPA" value={grades.cumulative_gpa?.toFixed(2) ?? "N/A"} />
          <StatCard label="Credits Earned" value={grades.total_credits_earned ?? "N/A"} />
          <StatCard label="Honor Roll" value={grades.honor_roll ? "Yes" : "No"}
                    variant={grades.honor_roll ? "success" : "default"} />
        </div>
      );

    case "ib":
      return (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatCard label="IB Total Points" value={`${grades.ib_total_points ?? "N/A"}/45`} />
          <StatCard label="Class Position" value={grades.class_position ?? "N/A"} />
          <StatCard label="Average Score" value={grades.average_score ?? "N/A"} />
        </div>
      );

    case "french":
      return (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatCard label="Average" value={`${grades.average_score}/20`} />
          <StatCard label="Mention" value={grades.french_mention ?? "N/A"} />
          <StatCard label="Class Position" value={grades.class_position ?? "N/A"} />
        </div>
      );

    default: // GES, Cambridge, Edexcel, Montessori
      return (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatCard label="Total Score" value={grades.total_score ?? "N/A"} />
          <StatCard label="Average" value={grades.average_score ?? "N/A"} />
          <StatCard label="Class Position" value={grades.class_position ?? "N/A"} />
        </div>
      );
  }
}
```

#### Step 3: Curriculum-aware grade trend chart

```tsx
function GradeTrendChart({ trend, curriculumType }: Props) {
  const yAxisLabel = curriculumType === "american" ? "GPA"
    : curriculumType === "ib" ? "IB Points"
    : curriculumType === "french" ? "Average (0-20)"
    : "Average Score (%)";

  const yAxisDomain = curriculumType === "american" ? [0, 4.0]
    : curriculumType === "ib" ? [0, 45]
    : curriculumType === "french" ? [0, 20]
    : [0, 100];

  return (
    <ResponsiveContainer>
      <LineChart data={trend}>
        <YAxis domain={yAxisDomain} label={yAxisLabel} />
        <XAxis dataKey="term_name" />
        <Line dataKey="value" />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

---

## Task D1: Make Analytics Service Curriculum-Aware

### File
`backend/app/services/exam/analytics_service.py`

### Current State

The analytics service computes:
- Grade distribution (percentage of students in each grade band)
- Class statistics (mean, median, standard deviation)
- Pass/fail rates (hardcoded 50% pass mark)
- Subject comparison charts

All use raw `ExamScore.score` values assumed to be percentages.

### Required Changes

#### Step 1: Resolve curriculum profile for the class

```python
async def get_grade_distribution(self, tenant_id, exam_id, class_id, ...):
    # NEW: Resolve curriculum profile
    profile = await self._resolve_class_curriculum(tenant_id, class_id)
    pass_mark = self._get_pass_mark(profile)
    ...
```

#### Step 2: Implement curriculum-aware pass mark

```python
def _get_pass_mark(self, profile: CurriculumProfile | None) -> Decimal:
    """Return the minimum passing score for this curriculum."""
    if profile is None:
        return Decimal("50")  # GES default

    curriculum_type = profile.curriculum_type.value
    if curriculum_type in ("ges", "cambridge", "edexcel"):
        return Decimal("50")      # 50% pass
    elif curriculum_type == "american":
        return Decimal("60")      # D- = 60%
    elif curriculum_type == "ib":
        return Decimal("28.57")   # Level 2 out of 7 ≈ 28.57%
    elif curriculum_type == "french":
        return Decimal("50")      # 10/20 = 50%
    elif curriculum_type == "montessori":
        return None               # No pass/fail for Montessori
    else:
        return Decimal("50")
```

#### Step 3: Add curriculum context to analytics response

```python
# In the analytics response, add:
{
    "curriculum_type": profile.curriculum_type.value if profile else "ges",
    "score_display_mode": profile.score_display_mode.value if profile else "percentage",
    "pass_mark": float(pass_mark) if pass_mark else None,
    # ... existing analytics data
}
```

#### Step 4: Skip pass/fail for Montessori

```python
if pass_mark is None:
    # Montessori — no pass/fail statistics
    analytics["pass_rate"] = None
    analytics["fail_rate"] = None
else:
    analytics["pass_rate"] = passed / total * 100
    analytics["fail_rate"] = failed / total * 100
```

---

## Task D2: Add Curriculum Context to Analytics API Response

### Files
- `backend/app/schemas/exam.py` — Analytics response schemas
- `backend/app/api/v1/endpoints/exams/analytics.py` — Analytics endpoints

### Required Changes

Add curriculum context fields to the analytics response schema:

```python
class AnalyticsResponse(BaseSchema):
    # ... existing fields
    curriculum_type: str = "ges"
    score_display_mode: str = "percentage"
    pass_mark: Optional[float] = None
```

The frontend analytics dashboard should use `score_display_mode` to format score labels:
- `"percentage"` → "85%"
- `"grade_only"` → "A"
- `"gpa"` → "3.5"
- `"level"` → "Level 6"
- `"narrative"` → (no numeric display)
- `"mention"` → "Bien"

---

## Checklist

### Task C1
- [ ] Resolve curriculum profile in `get_child_grades()`
- [ ] Branch to `_get_child_grades_curriculum()` for non-GES
- [ ] Read TermReport curriculum fields (GPA, IB total, French mention)
- [ ] Include curriculum_type and score_display_mode in response
- [ ] Update ChildGradesResponse schema
- [ ] Test: American parent sees GPA and honor roll
- [ ] Test: IB parent sees IB total points
- [ ] Test: GES parent sees unchanged data (backward compat)

### Task C2
- [ ] Update `get_child_grade_trend()` to return curriculum-appropriate metric
- [ ] Return `metric` field ("gpa", "ib_total_points", "average_score")
- [ ] Update GradeTrendEntry schema
- [ ] Test: American parent sees GPA trend over terms

### Task C3
- [ ] Update ChildGrades TypeScript type
- [ ] Create `GradeSummaryCard` with curriculum switch
- [ ] Create curriculum-aware grade trend chart with correct Y-axis
- [ ] Test: renders correctly for each curriculum type
- [ ] Test: mobile responsiveness

### Task D1
- [ ] Resolve curriculum profile in analytics methods
- [ ] Implement `_get_pass_mark()` per curriculum
- [ ] Skip pass/fail for Montessori
- [ ] Add curriculum_type to analytics response
- [ ] Test: Cambridge class uses 50% pass mark
- [ ] Test: American class uses 60% pass mark
- [ ] Test: Montessori class has null pass/fail rates

### Task D2
- [ ] Add curriculum fields to AnalyticsResponse schema
- [ ] Pass curriculum context from service to endpoint
- [ ] Frontend: use score_display_mode for label formatting
