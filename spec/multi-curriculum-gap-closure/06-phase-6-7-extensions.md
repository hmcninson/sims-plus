# Phase 6 & 7: Export Format Extensions & Criterion-Referenced Grading

**Priority:** Low
**Effort:** 2 weeks total
**Dependencies:** Phase 6 = None, Phase 7 = Phase 1
**Unblocks:** MC-042 (Edexcel export), MC-043 (IB export), MC-026 (IB MYP rubrics)

---

## Phase 6: Export Format Extensions

### Problem Statement

The external exam export endpoint (`/api/v1/curriculum/external-exams/export`) currently only supports WAEC and Cambridge International formats. Edexcel and IB registration exports return HTTP 400. While these are "Could" priority, they are straightforward additions.

### Task I1: Edexcel-Specific Export Format

#### File
`backend/app/services/curriculum/external_exam_service.py`

#### Current State

**`export_registrations()` method:**
```python
if exam_board == "waec":
    return await self.export_waec(tenant_id, exam_session)
elif exam_board == "cambridge_international":
    return await self.export_cambridge(tenant_id, exam_session)
else:
    raise CurriculumServiceError("Export not supported for this exam board", "unsupported_board")
```

#### Required Changes

Add an `export_edexcel()` method:

```python
async def export_edexcel(
    self,
    tenant_id: UUID,
    exam_session: str,
) -> list[dict]:
    """Export Edexcel registration data.

    Edexcel registration format:
    - CentreNumber (5 digits)
    - CandidateNumber (4 digits)
    - CandidateName (Surname, FirstName)
    - QualificationCode (e.g., "4MA1" for IGCSE Maths)
    - OptionCode (paper variant)
    - EntryLevel (Foundation/Higher for tiered papers)
    """
    registrations = await self._get_registrations(
        tenant_id, "edexcel", exam_session
    )

    export_rows = []
    for reg in registrations:
        student = reg.student
        for subject in reg.subjects:
            export_rows.append({
                "CentreNumber": reg.center_number or "",
                "CandidateNumber": reg.candidate_number or "",
                "Surname": student.last_name,
                "FirstName": student.first_name,
                "DateOfBirth": student.date_of_birth.strftime("%d/%m/%Y") if student.date_of_birth else "",
                "Gender": student.gender or "",
                "QualificationCode": subject.get("subject_code", ""),
                "SubjectTitle": subject.get("subject_name", ""),
                "OptionCode": subject.get("option_code", ""),
                "EntryLevel": subject.get("level", ""),
            })

    return export_rows
```

> **>>REVIEW FIX (Security):** All export methods must use the existing
> `_sanitize_csv_cell()` method on all string fields to prevent CSV formula injection,
> consistent with the WAEC/Cambridge export pattern.

Update the dispatcher:

```python
elif exam_board == "edexcel":
    return await self.export_edexcel(tenant_id, exam_session)
```

### Task I2: IB-Specific Export Format

#### Same File

```python
async def export_ib(
    self,
    tenant_id: UUID,
    exam_session: str,
) -> list[dict]:
    """Export IB candidate registration data.

    IB registration format:
    - SchoolCode (IB World School number)
    - CandidateNumber (session-specific)
    - CandidateName
    - Programme (DP, MYP, PYP)
    - SubjectGroup (1-6 for DP)
    - SubjectCode
    - SubjectName
    - Level (HL/SL for DP)
    """
    registrations = await self._get_registrations(
        tenant_id, "ibo", exam_session
    )

    export_rows = []
    for reg in registrations:
        student = reg.student
        for subject in reg.subjects:
            export_rows.append({
                "SchoolCode": reg.center_number or "",  # IB World School code
                "CandidateNumber": reg.candidate_number or "",
                "Surname": student.last_name,
                "FirstName": student.first_name,
                "DateOfBirth": student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "",
                "Programme": subject.get("programme", "DP"),
                "SubjectGroup": subject.get("subject_group", ""),
                "SubjectCode": subject.get("subject_code", ""),
                "SubjectName": subject.get("subject_name", ""),
                "Level": subject.get("level", ""),  # HL or SL
                "PaperNumbers": ",".join(subject.get("paper_numbers", [])),
            })

    return export_rows
```

Update the dispatcher:

```python
elif exam_board == "ibo":
    return await self.export_ib(tenant_id, exam_session)
```

### CSV Export Endpoint

Both export methods return `list[dict]`. The endpoint should convert to CSV:

```python
# The existing export endpoint likely already handles this:
@router.get("/external-exams/export")
async def export_external_exam_registrations(
    exam_board: str = Query(...),
    exam_session: str = Query(...),
    format: str = Query("csv", pattern="^(csv|json)$"),
    ...
):
    data = await service.export_registrations(tenant_id, exam_board, exam_session)

    if format == "csv":
        # Convert list[dict] to CSV StreamingResponse
        ...
    return data
```

---

## Phase 7: Criterion-Referenced Grading (MC-026)

### Problem Statement

IB MYP (Middle Years Programme) uses criterion-referenced assessment. Each subject has 4 criteria (A, B, C, D), each scored on a level 1-8. The final grade (1-7) is derived from the sum of criterion scores, not from a single numeric score.

The current system stores one score per student-subject-exam. Criterion-referenced grading requires storing 4+ scores per student-subject (one per criterion).

This is a "Could" priority and represents the most significant schema change in the gap closure plan.

### Design Decision

**Option A (Recommended for now): JSONB criterion scores on ExamScore**

Add a `criterion_scores` JSONB column to the existing `ExamScore` model:

```json
{
  "criteria": [
    {"criterion": "A", "name": "Knowing and understanding", "level": 6, "max_level": 8},
    {"criterion": "B", "name": "Investigating", "level": 5, "max_level": 8},
    {"criterion": "C", "name": "Communicating", "level": 7, "max_level": 8},
    {"criterion": "D", "name": "Thinking critically", "level": 6, "max_level": 8}
  ],
  "criterion_total": 24,
  "criterion_max": 32
}
```

**Rationale:** Avoids a new table and migration. The criterion structure varies by subject group (Sciences have different criteria than Humanities). JSONB accommodates this flexibility. The `score` column can still hold the derived final score (1-7).

**Option B: New `assessment_criteria` + `criterion_scores` tables**

More normalized, better for querying ("find all students at level 7+ in criterion A across all subjects"). Consider this only if criterion-level analytics are a requirement.

### Task J1: Criterion Score Support on ExamScore

#### Migration

```python
# New migration: 20260XXX_0100_criterion_scores.py

def upgrade():
    op.add_column(
        "exam_scores",
        sa.Column("criterion_scores", sa.JSON(), nullable=True),
    )

    # Index for querying criterion scores (optional, for analytics)
    # PostgreSQL GIN index on JSONB
    op.create_index(
        "ix_exam_scores_criterion_scores",
        "exam_scores",
        ["criterion_scores"],
        postgresql_using="gin",
    )
```

#### Model Change

```python
# models/exam.py — ExamScore class
class ExamScore(TenantMixin, Base):
    # ... existing fields ...
    criterion_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

#### Schema Change

```python
# schemas/exam.py

class CriterionScore(BaseSchema):
    criterion: str = Field(..., max_length=5, description="Criterion label (A, B, C, D)")
    name: str = Field(..., max_length=200, description="Criterion name")
    level: int = Field(..., ge=0, le=8, description="Achievement level 0-8")
    max_level: int = Field(default=8, ge=1, le=10)

class CriterionScoreEntry(BaseSchema):
    criteria: list[CriterionScore] = Field(..., min_length=1, max_length=10)

# Extend ScoreEntry:
class ScoreEntry(BaseSchema):
    student_id: UUID
    score: Optional[Decimal] = Field(None, ge=0)
    is_absent: bool = False
    teacher_remark: Optional[str] = None
    effort_grade: Optional[str] = None
    criterion_scores: Optional[CriterionScoreEntry] = None  # NEW
```

#### Service Change

In `bulk_enter_scores()`:

```python
if score_data.get("criterion_scores"):
    exam_score.criterion_scores = score_data["criterion_scores"].model_dump()

    # Also compute the final score (1-7) from criterion total
    criterion_data = score_data["criterion_scores"]
    total = sum(c.level for c in criterion_data.criteria)
    max_total = sum(c.max_level for c in criterion_data.criteria)

    # IB MYP grade boundaries (sum of 4 criteria, max 32):
    # 28-32 = 7, 24-27 = 6, 19-23 = 5, 15-18 = 4, 10-14 = 3, 6-9 = 2, 1-5 = 1
    exam_score.score = self._criterion_total_to_grade(total, max_total)
```

#### IB MYP Grade Boundary Conversion

```python
def _criterion_total_to_grade(self, total: int, max_total: int) -> Decimal:
    """Convert criterion total to IB MYP 1-7 grade.

    Standard MYP boundaries for 4 criteria (max 32):
    28-32 = 7, 24-27 = 6, 19-23 = 5, 15-18 = 4,
    10-14 = 3, 6-9 = 2, 1-5 = 1, 0 = 0
    """
    if max_total == 32:  # Standard 4 criteria
        if total >= 28: return Decimal("7")
        elif total >= 24: return Decimal("6")
        elif total >= 19: return Decimal("5")
        elif total >= 15: return Decimal("4")
        elif total >= 10: return Decimal("3")
        elif total >= 6: return Decimal("2")
        elif total >= 1: return Decimal("1")
        else: return Decimal("0")
    else:
        # Proportional for non-standard criteria counts
        percentage = total / max_total if max_total > 0 else 0
        return Decimal(str(min(7, max(0, round(percentage * 7)))))
```

### Task J2: Criterion-Level Score Entry UI

#### Frontend

When the class uses `use_criterion_grading = true` (IB MYP), the score entry form should show 4 criterion columns instead of a single score column:

```tsx
function CriterionScoreEntry({ criteria, onChange }: Props) {
  return (
    <div className="flex gap-2">
      {criteria.map((criterion) => (
        <div key={criterion.criterion} className="flex flex-col items-center">
          <label className="text-xs font-medium text-muted-foreground">
            {criterion.criterion}
          </label>
          <Input
            type="number"
            min={0}
            max={criterion.max_level}
            value={criterion.level}
            onChange={(e) => onChange(criterion.criterion, parseInt(e.target.value))}
            className="w-14 text-center"
          />
          <span className="text-xs text-muted-foreground">/{criterion.max_level}</span>
        </div>
      ))}
      <div className="flex flex-col items-center">
        <label className="text-xs font-medium">Total</label>
        <span className="h-10 flex items-center font-semibold">
          {criteria.reduce((sum, c) => sum + c.level, 0)}
        </span>
        <span className="text-xs text-muted-foreground">
          /{criteria.reduce((sum, c) => sum + c.max_level, 0)}
        </span>
      </div>
    </div>
  );
}
```

#### Default IB MYP Criteria by Subject Group

```typescript
const IB_MYP_CRITERIA: Record<string, CriterionDefinition[]> = {
  "language_acquisition": [
    { criterion: "A", name: "Comprehending spoken and visual text", max_level: 8 },
    { criterion: "B", name: "Comprehending written and visual text", max_level: 8 },
    { criterion: "C", name: "Communicating", max_level: 8 },
    { criterion: "D", name: "Using language", max_level: 8 },
  ],
  "sciences": [
    { criterion: "A", name: "Knowing and understanding", max_level: 8 },
    { criterion: "B", name: "Inquiring and designing", max_level: 8 },
    { criterion: "C", name: "Processing and evaluating", max_level: 8 },
    { criterion: "D", name: "Reflecting on the impacts of science", max_level: 8 },
  ],
  "mathematics": [
    { criterion: "A", name: "Knowing and understanding", max_level: 8 },
    { criterion: "B", name: "Investigating patterns", max_level: 8 },
    { criterion: "C", name: "Communicating", max_level: 8 },
    { criterion: "D", name: "Applying mathematics in real-life contexts", max_level: 8 },
  ],
  // ... other subject groups
  "default": [
    { criterion: "A", name: "Criterion A", max_level: 8 },
    { criterion: "B", name: "Criterion B", max_level: 8 },
    { criterion: "C", name: "Criterion C", max_level: 8 },
    { criterion: "D", name: "Criterion D", max_level: 8 },
  ],
};
```

---

## Checklist

### Task I1 (Edexcel Export)
- [ ] Implement `export_edexcel()` method
- [ ] Output fields: CentreNumber, CandidateNumber, Surname, FirstName, DOB, Gender, QualificationCode, SubjectTitle, OptionCode, EntryLevel
- [ ] Add "edexcel" to export dispatcher
- [ ] Test: export Edexcel registrations as CSV
- [ ] Test: empty session returns empty list

### Task I2 (IB Export)
- [ ] Implement `export_ib()` method
- [ ] Output fields: SchoolCode, CandidateNumber, Surname, FirstName, DOB, Programme, SubjectGroup, SubjectCode, SubjectName, Level, PaperNumbers
- [ ] Add "ibo" to export dispatcher
- [ ] Test: export IB registrations as CSV
- [ ] Test: empty session returns empty list

### Task J1 (Criterion Score Model)
- [ ] Add `criterion_scores` JSONB column to ExamScore model
- [ ] Create Alembic migration
- [ ] Add GIN index on criterion_scores
- [ ] Create `CriterionScore` and `CriterionScoreEntry` schemas
- [ ] Extend `ScoreEntry` schema with optional `criterion_scores`
- [ ] Save criterion_scores in `bulk_enter_scores()`
- [ ] Auto-compute final grade (1-7) from criterion total
- [ ] Implement `_criterion_total_to_grade()` with IB MYP boundaries
- [ ] Test: enter criterion scores and verify final grade
- [ ] Test: criterion scores stored in JSONB
- [ ] Test: backward compat — entry without criterion_scores still works

### Task J2 (Criterion Score UI)
- [ ] Create `CriterionScoreEntry` component
- [ ] Detect `use_criterion_grading` on class curriculum profile
- [ ] Show 4 criterion columns instead of single score for IB MYP classes
- [ ] Auto-calculate total and display derived grade
- [ ] Default criteria by subject group (Language, Sciences, Maths, etc.)
- [ ] Include criterion_scores in submit payload
- [ ] Mobile: stack criteria vertically on small screens
- [ ] Test: enter criterion scores, verify saved correctly
- [ ] Test: GES class still shows single score column
