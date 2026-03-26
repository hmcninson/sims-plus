# Phase 2: Score Entry Enhancements

**Priority:** High
**Effort:** 1 week
**Dependencies:** None (can run in parallel with Phase 1)
**Unblocks:** MC-032 (Cambridge effort grades)

---

## Problem Statement

The score entry workflow (`score_service.py`, `ScoreEntry` schema, score entry endpoints) was built for GES-style numeric scoring only. It does not support:

1. **Effort grades** (Cambridge/Edexcel) — The `ExamScore.effort_grade` column exists in the database (exam.py line 408) and the Cambridge report template references it (cambridge_report.html lines 323-325, 351), but the score entry form and bulk entry endpoint don't accept or save this field.

2. **Curriculum-aware score form** — The score entry form doesn't tell the frontend which assessment components exist for the class's curriculum, so the frontend cannot render component-specific score inputs.

---

## Task B1: Add Effort Grade to Score Entry

### Files
- `backend/app/schemas/exam.py` — `ScoreEntry` schema
- `backend/app/services/exam/score_service.py` — `bulk_enter_scores()` method
- `backend/app/api/v1/endpoints/exams/scores.py` — Score entry endpoint

### Current State

**ScoreEntry schema (schemas/exam.py lines 204-210):**
```python
class ScoreEntry(BaseSchema):
    student_id: UUID
    score: Optional[Decimal] = Field(None, ge=0)
    is_absent: bool = False
    teacher_remark: Optional[str] = None
```

**bulk_enter_scores() (score_service.py lines 172-373):**
- Accepts `scores: list[dict]` with keys matching ScoreEntry
- Creates/updates `ExamScore` records
- Sets `exam_score.score`, `exam_score.is_absent`, `exam_score.teacher_remark`
- Does NOT set `exam_score.effort_grade`

### Required Changes

#### Step 1: Extend ScoreEntry schema

> **>>REVIEW FIX (M5):** The original regex `^[1-5A-Ea-e]$` is too restrictive — it only
> allows single characters and would break if a future curriculum uses formats like "G+"
> or "Outstanding". Use a relaxed max_length validation instead. The frontend `Select`
> dropdown already constrains to valid values; the backend should validate length only.

```python
# schemas/exam.py — ScoreEntry class
class ScoreEntry(BaseSchema):
    student_id: UUID
    score: Optional[Decimal] = Field(None, ge=0)
    is_absent: bool = False
    teacher_remark: Optional[str] = None
    effort_grade: Optional[str] = Field(
        None,
        max_length=10,
        description="Effort/behavior grade (Cambridge: 1-5, or A-E). "
                    "Valid values depend on the curriculum's effort grade scale."
    )
```

**Validation approach:** Soft backend validation (length limit only). The frontend enforces
curriculum-specific values via a `Select` dropdown (1-5 for Cambridge, A-E for others).
This avoids hard-coding curriculum rules in the schema and allows future flexibility.

#### Step 2: Save effort_grade in bulk_enter_scores()

In `score_service.py`, within the loop that creates/updates ExamScore records:

```python
# CURRENT (approximately):
exam_score.score = score_data.get("score")
exam_score.is_absent = score_data.get("is_absent", False)
exam_score.teacher_remark = score_data.get("teacher_remark")

# AFTER — add:
if "effort_grade" in score_data and score_data["effort_grade"] is not None:
    exam_score.effort_grade = score_data["effort_grade"]
```

**Backward compatibility:** `effort_grade` is Optional with default None. Existing GES score entry payloads that don't include this field will continue to work without change.

#### Step 3: Include effort_grade in score entry form response

In `get_score_entry_form()`, when building the student data for the form, include the existing effort_grade value:

```python
# When building student score data in the form response:
"effort_grade": existing_score.effort_grade if existing_score else None,
```

Also add curriculum context to the form response so the frontend knows whether to show effort grade inputs:

```python
# In the form response dict, add:
"curriculum_type": curriculum_type,  # "ges", "cambridge", etc.
"show_effort_grade": curriculum_type in ("cambridge", "edexcel"),
```

To determine `curriculum_type`, resolve the class's curriculum profile:

```python
# At the top of get_score_entry_form():
from app.models.curriculum import CurriculumProfile

# Get the class for this exam subject
class_obj = ...  # already fetched
curriculum_type = "ges"  # default
if class_obj.curriculum_profile_id:
    profile = await self.db.get(CurriculumProfile, class_obj.curriculum_profile_id)
    if profile:
        curriculum_type = profile.curriculum_type.value
```

### Frontend Impact

The frontend score entry page needs to conditionally render an effort grade column when `show_effort_grade` is true in the form response. This is covered in Phase 2 frontend tasks.

---

## Task B2: Wire Effort Grade into CambridgeScoreStrategy

### File
`backend/app/services/exam/score_strategies.py`

### Current State

**CambridgeScoreStrategy.calculate_subject_score() (lines 153-190):**
- Computes `weighted_total` from component scores
- Calls `determine_grade()` to get letter grade
- Returns `SubjectScoreResult` with `final_score`, `grade`, `grade_point`, `grade_remark`
- Does NOT set `result.effort_grade`

**SubjectScoreResult dataclass (line 35):**
```python
effort_grade: str | None = None  # field exists but never set
```

### Required Changes

The effort grade is NOT computed by the strategy — it's entered by the teacher and stored on `ExamScore.effort_grade`. The strategy just needs to pass it through.

The issue is in `_get_student_subject_results_curriculum()` in `report_service.py`, which builds the subject result dict. Check whether it already reads `effort_grade` from the ExamScore:

**report_service.py line 1335 (approximately):**
```python
"effort_grade": score_result.effort_grade,
```

This line exists but `score_result.effort_grade` is always None because it's never set. The fix is in the score collection phase:

**In `_calculate_student_term_scores_curriculum()` or `_get_student_subject_results_curriculum()`:**

When building `SubjectScoreResult`, read `effort_grade` from the ExamScore record:

```python
# When iterating over exam scores for a student-subject:
# (The exact location depends on how scores are fetched)

# Find the effort_grade from the ExamScore records
effort_grade = None
for score in subject_exam_scores:
    if score.effort_grade:
        effort_grade = score.effort_grade
        break  # Use the first non-null effort grade found

# Set on the result:
result.effort_grade = effort_grade
```

**Where exactly to place this:** The effort_grade lives on `ExamScore`, which is loaded during the score collection phase. Look for where `ExamScore` records are iterated in `_get_student_subject_results_curriculum()` and extract `effort_grade` from there.

### Verification

After this change:
1. Enter scores for a Cambridge class, including effort_grade values (1-5)
2. Generate a term report
3. Generate a PDF report
4. Verify the Cambridge template shows effort grade badges (1=green, 5=red)

---

## Task B3: Frontend — Conditional Effort Grade Column

### Files
- `frontend/app/(dashboard)/exams/` — Score entry page (identify the exact file)
- `frontend/types/index.ts` or `frontend/types/curriculum.type.ts` — ScoreEntry type

### Current State

The score entry form renders a table with columns: Student Name, Score, Absent, Remarks. There is no effort grade column.

### Required Changes

#### Step 1: Update ScoreEntry type

```typescript
// types/index.ts or wherever ScoreEntry is defined
interface ScoreEntry {
  student_id: string;
  score: number | null;
  is_absent: boolean;
  teacher_remark: string | null;
  effort_grade: string | null;  // NEW
}
```

#### Step 2: Update score entry form response type

```typescript
interface ScoreEntryFormResponse {
  students: StudentScoreEntry[];
  // ... existing fields
  curriculum_type: string;      // NEW
  show_effort_grade: boolean;   // NEW
}
```

#### Step 3: Conditionally render effort grade column

In the score entry table component:

```tsx
// In the table header:
{formData.show_effort_grade && (
  <th>Effort</th>
)}

// In the table body row:
{formData.show_effort_grade && (
  <td>
    <Select
      value={student.effort_grade || ""}
      onValueChange={(val) => handleEffortGradeChange(student.student_id, val)}
    >
      <SelectTrigger className="w-20">
        <SelectValue placeholder="-" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="1">1 - Excellent</SelectItem>
        <SelectItem value="2">2 - Good</SelectItem>
        <SelectItem value="3">3 - Satisfactory</SelectItem>
        <SelectItem value="4">4 - Needs Improvement</SelectItem>
        <SelectItem value="5">5 - Unacceptable</SelectItem>
      </SelectContent>
    </Select>
  </td>
)}
```

#### Step 4: Include effort_grade in submit payload

When submitting scores, include effort_grade in the payload:

```typescript
const scores = students.map(s => ({
  student_id: s.student_id,
  score: s.score,
  is_absent: s.is_absent,
  teacher_remark: s.teacher_remark,
  effort_grade: s.effort_grade || null,  // NEW
}));
```

#### Step 5: Update server action

```typescript
// actions/exams.action.ts or wherever score entry is called
export async function enterBulkScores(
  examSubjectId: string,
  scores: ScoreEntry[]
): Promise<ActionResult<BulkScoreResult>> {
  // The payload shape already matches — just ensure effort_grade is included
}
```

### UI/UX Notes

- Effort grade column should only appear for Cambridge and Edexcel curricula
- The column is optional — teachers can leave it blank
- Use a Select dropdown (not a text input) to constrain values
- Show tooltip explaining the effort grade scale on hover
- Mobile: effort grade column should be hidden on `sm:` breakpoints (use `hidden sm:table-cell`)

---

## Implementation Order

1. **B1** (Backend schema + service) — Can be done independently
2. **B2** (Strategy wiring) — Depends on B1 being deployed
3. **B3** (Frontend) — Depends on B1 being deployed

All three can be assigned to different developers if B1 is completed first.

---

## Checklist

### Task B1
- [ ] Add `effort_grade` field to `ScoreEntry` schema with validation
- [ ] Set `exam_score.effort_grade` in `bulk_enter_scores()`
- [ ] Include `effort_grade` in `get_score_entry_form()` response
- [ ] Add `curriculum_type` and `show_effort_grade` to form response
- [ ] Resolve class curriculum profile in `get_score_entry_form()`
- [ ] Test: enter scores with effort_grade for Cambridge class
- [ ] Test: enter scores without effort_grade for GES class (backward compat)

### Task B2
- [ ] In score result building, extract `effort_grade` from ExamScore
- [ ] Set `result.effort_grade` on SubjectScoreResult
- [ ] Verify Cambridge report template renders effort grade badges
- [ ] Test: effort grade appears in subject results API response

### Task B3
- [ ] Update ScoreEntry TypeScript type
- [ ] Update score entry form response type
- [ ] Add conditional effort grade column to score entry table
- [ ] Use Select dropdown with 1-5 options
- [ ] Include effort_grade in submit payload
- [ ] Test on mobile (column hidden on small screens)
- [ ] Test with GES class (column should not appear)
- [ ] Test with Cambridge class (column appears, values saved)
