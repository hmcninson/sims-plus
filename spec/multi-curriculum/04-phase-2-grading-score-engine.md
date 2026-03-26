# Phase 2: Grading, Score Engine & Report Cards

**Phase:** MC-Sprint 2
**Depends on:** Phase 1 complete (curriculum profiles must exist)
**Parallel with:** Phase 2 Frontend (after endpoints are ready)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 4.1 | Create Phase 2 migration | `backend/alembic/versions/20260315_0100_grading_and_equivalencies.py` | 1.5d |
| 4.2 | Create GradeEquivalency + SubjectCurriculumMapping models | `backend/app/models/curriculum.py` | 0.5d |
| 4.3 | Add columns to TermReport + ExamScore + Subject models | Multiple model files | 0.5d |
| 4.4 | Create ScoreStrategy base class + GES strategy | `backend/app/services/exam/score_strategies.py` | 1d |
| 4.5 | Create Cambridge/Edexcel score strategy | `backend/app/services/exam/score_strategies.py` | 1d |
| 4.6 | Create American score strategy (GPA) | `backend/app/services/exam/score_strategies.py` | 1d |
| 4.7 | Create IB score strategy (criterion) | `backend/app/services/exam/score_strategies.py` | 1d |
| 4.8 | Create French score strategy (mention) | `backend/app/services/exam/score_strategies.py` | 0.5d |
| 4.9 | Create Montessori score strategy (narrative) | `backend/app/services/exam/score_strategies.py` | 0.5d |
| 4.10 | Refactor TermReportService for strategy dispatch (includes `calculate_student_term_scores()`, normalization layer, batch optimization) | `backend/app/services/exam/report_service.py` | 4.5d |
| 4.11 | Create GradeEquivalencyService | `backend/app/services/curriculum/equivalency_service.py` | 0.75d |
| 4.12 | Create SubjectMappingService | `backend/app/services/curriculum/subject_mapping_service.py` | 0.75d |
| 4.13 | Create equivalency + subject mapping schemas | `backend/app/schemas/curriculum.py` | 0.5d |
| 4.14 | Create equivalency endpoints | `backend/app/api/v1/endpoints/curriculum/equivalencies.py` | 0.5d |
| 4.15 | Create subject mapping endpoints | `backend/app/api/v1/endpoints/curriculum/subject_mappings.py` | 0.5d |
| 4.16 | Create 5 report card HTML templates | `backend/app/templates/reports/` | 2d |
| 4.17 | Update PDF service for template selection | `backend/app/services/pdf.py` | 0.5d |
| 4.18 | Update exam schemas for curriculum fields | `backend/app/schemas/exam.py` | 0.5d |
| 4.19 | Update conftest.py for Phase 2 tables | `backend/tests/conftest.py` | 0.25d |

---

## 4.1 Phase 2 Migration

**File:** `backend/alembic/versions/20260315_0100_grading_and_equivalencies.py`

**Revision chain:** `20260310_0200` -> `20260315_0100`

### New Tables

**`grade_equivalencies`:**

```sql
CREATE TABLE grade_equivalencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
    source_grading_scale_id UUID NOT NULL REFERENCES grading_scales(id) ON DELETE CASCADE,
    target_grading_scale_id UUID NOT NULL REFERENCES grading_scales(id) ON DELETE CASCADE,
    source_grade_id UUID NOT NULL REFERENCES grades(id) ON DELETE CASCADE,
    target_grade_id UUID NOT NULL REFERENCES grades(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_grade_equivalency UNIQUE (tenant_id, source_grade_id, target_grading_scale_id)
);
```

**`subject_curriculum_mappings`:**

```sql
CREATE TABLE subject_curriculum_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    curriculum_profile_id UUID NOT NULL REFERENCES curriculum_profiles(id) ON DELETE CASCADE,
    external_code VARCHAR(20),
    external_name VARCHAR(200),
    level VARCHAR(50),
    credits NUMERIC(4,1),
    coefficient NUMERIC(4,1),
    is_hl BOOLEAN DEFAULT false,
    grading_scale_id UUID REFERENCES grading_scales(id) ON DELETE SET NULL,
    config JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_subject_curriculum_mapping UNIQUE (tenant_id, subject_id, curriculum_profile_id)
);
```

### Column Additions

```sql
-- NOTE: grading_scales.curriculum_profile_id was already added in Phase 1 (file 01, section 1.7d).
-- Do NOT add it again here — the migration will fail with "column already exists".

-- exam_scores
ALTER TABLE exam_scores ADD COLUMN effort_grade VARCHAR(5);

-- term_reports
ALTER TABLE term_reports ADD COLUMN curriculum_profile_id UUID REFERENCES curriculum_profiles(id) ON DELETE SET NULL;
ALTER TABLE term_reports ADD COLUMN gpa NUMERIC(4,2);
ALTER TABLE term_reports ADD COLUMN weighted_gpa NUMERIC(4,2);
ALTER TABLE term_reports ADD COLUMN cumulative_gpa NUMERIC(4,2);
ALTER TABLE term_reports ADD COLUMN total_credits_earned NUMERIC(5,1);
ALTER TABLE term_reports ADD COLUMN cumulative_credits NUMERIC(5,1);
ALTER TABLE term_reports ADD COLUMN honor_roll BOOLEAN;
ALTER TABLE term_reports ADD COLUMN ib_total_points INTEGER;
ALTER TABLE term_reports ADD COLUMN french_mention VARCHAR(20);
ALTER TABLE term_reports ADD COLUMN extra_data JSONB;

-- subjects
ALTER TABLE subjects ADD COLUMN credit_value NUMERIC(4,1);
ALTER TABLE subjects ADD COLUMN coefficient NUMERIC(4,1);
```

### RLS + Indexes

Use `rls_helpers.enable_rls_for_table()` for both new tables (same as Phase 1 — do NOT write inline RLS DDL):

```python
from app.db.rls_helpers import enable_rls_for_table

for table_name in ["grade_equivalencies", "subject_curriculum_mappings"]:
    enable_rls_for_table(op.get_bind(), table_name)
```

Add indexes:

```sql
-- Standard single-column indexes
CREATE INDEX ix_grade_equivalencies_tenant_id ON grade_equivalencies(tenant_id);
CREATE INDEX ix_grade_equivalencies_source_scale ON grade_equivalencies(source_grading_scale_id);
CREATE INDEX ix_grade_equivalencies_target_scale ON grade_equivalencies(target_grading_scale_id);
CREATE INDEX ix_subject_curriculum_mappings_tenant_id ON subject_curriculum_mappings(tenant_id);
CREATE INDEX ix_subject_curriculum_mappings_subject ON subject_curriculum_mappings(subject_id);
CREATE INDEX ix_subject_curriculum_mappings_profile ON subject_curriculum_mappings(curriculum_profile_id);

-- Composite indexes for common query patterns
CREATE INDEX ix_grade_equivalencies_tenant_source_target
    ON grade_equivalencies (tenant_id, source_grading_scale_id, target_grading_scale_id);
CREATE INDEX ix_subject_curriculum_mappings_tenant_profile
    ON subject_curriculum_mappings (tenant_id, curriculum_profile_id);

-- Index on new FK columns added to existing tables
CREATE INDEX ix_term_reports_curriculum_profile_id ON term_reports(curriculum_profile_id);
CREATE INDEX ix_exam_scores_curriculum_profile_id ON exam_scores(curriculum_profile_id) WHERE curriculum_profile_id IS NOT NULL;
```

### Downgrade

```python
def downgrade():
    # Disable RLS before dropping
    from app.db.rls_helpers import disable_rls_for_table
    for table in ["grade_equivalencies", "subject_curriculum_mappings"]:
        disable_rls_for_table(op.get_bind(), table)

    # Drop new tables (reverse order of creation)
    op.drop_table("subject_curriculum_mappings")
    op.drop_table("grade_equivalencies")

    # Remove columns added to subjects
    op.drop_column("subjects", "coefficient")
    op.drop_column("subjects", "credit_value")

    # Remove columns added to term_reports
    op.drop_column("term_reports", "extra_data")
    op.drop_column("term_reports", "french_mention")
    op.drop_column("term_reports", "ib_total_points")
    op.drop_column("term_reports", "honor_roll")
    op.drop_column("term_reports", "cumulative_credits")
    op.drop_column("term_reports", "total_credits_earned")
    op.drop_column("term_reports", "cumulative_gpa")
    op.drop_column("term_reports", "weighted_gpa")
    op.drop_column("term_reports", "gpa")
    op.drop_column("term_reports", "curriculum_profile_id")

    # Remove columns added to exam_scores
    op.drop_column("exam_scores", "effort_grade")
```

---

## 4.2 GradeEquivalency + SubjectCurriculumMapping Models

**File:** `backend/app/models/curriculum.py` (append to existing file)

### GradeEquivalency

```python
class GradeEquivalency(Base, TenantMixin):
    """
    Cross-curriculum grade mapping.

    Maps a grade from one scale to an equivalent grade in another scale.
    e.g., WAEC A1 -> Cambridge A*, IB 7 -> American A+
    """

    __tablename__ = "grade_equivalencies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_grade_id", "target_grading_scale_id",
            name="uq_grade_equivalency",
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    source_grading_scale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grading_scales.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_grading_scale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grading_scales.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### SubjectCurriculumMapping

```python
class SubjectCurriculumMapping(Base, TenantMixin):
    """
    Maps an internal subject to its curriculum-specific code, name, and metadata.

    e.g., Subject "Mathematics" -> Cambridge code "0580", level "Extended",
    credits 1.0 for American system.
    """

    __tablename__ = "subject_curriculum_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "subject_id", "curriculum_profile_id",
            name="uq_subject_curriculum_mapping",
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="External subject code, e.g., '0580' for IGCSE Mathematics",
    )
    external_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="Official curriculum subject name",
    )
    level: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="e.g., 'Higher', 'Standard', 'Extended', 'Core', 'AP', 'Honors'",
    )
    credits: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True,
        comment="Credit value (American system)",
    )
    coefficient: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True,
        comment="Coefficient (French system)",
    )
    is_hl: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="IB Higher Level flag",
    )
    grading_scale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grading_scales.id", ondelete="SET NULL"),
        nullable=True,
        comment="Subject-specific grading scale override",
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Subject-specific curriculum config",
    )
```

---

## 4.3 Model Column Additions

### TermReport Model (`backend/app/models/exam.py`)

Add after `headmaster_remark`:

```python
# Curriculum-specific fields (Phase 2)
curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
    nullable=True,
    comment="Curriculum profile used to generate this report",
)
gpa: Mapped[Decimal | None] = mapped_column(
    Numeric(4, 2), nullable=True, comment="Term GPA (American, IB)",
)
weighted_gpa: Mapped[Decimal | None] = mapped_column(
    Numeric(4, 2), nullable=True, comment="Weighted GPA",
)
cumulative_gpa: Mapped[Decimal | None] = mapped_column(
    Numeric(4, 2), nullable=True, comment="Cumulative GPA across terms",
)
total_credits_earned: Mapped[Decimal | None] = mapped_column(
    Numeric(5, 1), nullable=True, comment="Credits earned this term",
)
cumulative_credits: Mapped[Decimal | None] = mapped_column(
    Numeric(5, 1), nullable=True, comment="Total credits to date",
)
honor_roll: Mapped[bool | None] = mapped_column(
    Boolean, nullable=True, comment="Honor roll status",
)
ib_total_points: Mapped[int | None] = mapped_column(
    Integer, nullable=True, comment="IB total points (out of 45)",
)
french_mention: Mapped[str | None] = mapped_column(
    String(20), nullable=True, comment="French mention category",
)
extra_data: Mapped[dict | None] = mapped_column(
    JSONB, nullable=True, comment="Curriculum-specific report data",
)
```

### ExamScore Model (`backend/app/models/exam.py`)

Add after `grade_remark`:

```python
effort_grade: Mapped[str | None] = mapped_column(
    String(5), nullable=True,
    comment="Effort grade (Cambridge: 1-5 or A-E)",
)
```

### Subject Model (`backend/app/models/academic/subject_models.py`)

Add after `is_active`:

```python
credit_value: Mapped[Decimal | None] = mapped_column(
    Numeric(4, 1), nullable=True,
    comment="Default credit value for American system",
)
coefficient: Mapped[Decimal | None] = mapped_column(
    Numeric(4, 1), nullable=True,
    comment="Default coefficient for French system",
)
```

---

## 4.4 Score Strategy Pattern — Base Class + GES

**File:** `backend/app/services/exam/score_strategies.py`

```python
"""
Curriculum-specific score calculation strategies.

Each strategy implements the scoring rules for a specific curriculum:
- How subject scores are calculated from assessment components
- How grades are determined from scores
- How aggregate scores (GPA, total points) are computed
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.models.curriculum import (
    AssessmentComponent,
    CurriculumProfile,
    CurriculumType,
)
from app.models.academic import Grade


class SubjectScoreResult:
    """Result of scoring a single subject for a student."""

    def __init__(self):
        self.component_scores: dict[str, Decimal | None] = {}  # component_type -> score
        self.raw_total: Decimal | None = None
        self.weighted_total: Decimal | None = None
        self.class_score: Decimal | None = None  # CA column (legacy GES)
        self.exams_score: Decimal | None = None  # Exam column (legacy GES)
        self.final_score: Decimal | None = None
        self.grade: str | None = None
        self.grade_point: Decimal | None = None
        self.grade_remark: str | None = None
        self.narrative: str | None = None  # Montessori
        self.effort_grade: str | None = None  # Cambridge


class ScoreStrategy(ABC):
    """Base class for curriculum-specific score calculation."""

    @abstractmethod
    def calculate_subject_score(
        self,
        component_scores: dict[str, Decimal | None],
        components: list[AssessmentComponent],
        max_scores: dict[str, Decimal],
    ) -> SubjectScoreResult:
        """
        Calculate the final subject score from component scores.

        Args:
            component_scores: Dict of component_type -> raw score achieved
            components: Assessment component definitions with weights
            max_scores: Dict of component_type -> max possible score

        Returns:
            SubjectScoreResult with all calculated values
        """
        ...

    @abstractmethod
    def determine_grade(
        self, score: Decimal | None, grades: list[Grade]
    ) -> tuple[str | None, Decimal | None, str | None]:
        """
        Determine grade from score using grading scale.

        Returns:
            (grade_symbol, grade_point, grade_remark)
        """
        ...

    def calculate_aggregate(
        self,
        subject_results: list[SubjectScoreResult],
        profile: CurriculumProfile,
    ) -> dict[str, Any]:
        """
        Calculate aggregate metrics (GPA, total points, etc.).
        Override in subclasses that need aggregate calculations.

        Returns dict with keys like 'gpa', 'weighted_gpa', 'total_points', etc.
        """
        return {}


class GESScoreStrategy(ScoreStrategy):
    """
    Ghana Education Service score calculation.

    This is the EXISTING logic extracted verbatim from the current
    TermReportService. It MUST produce identical results.

    Assessment: Class Work + Homework + Midterm + End Term
    Report Card: Class Score (CA%) + Exams Score (Exam%) = Total (100)
    Grading: WAEC A1-F9 based on percentage
    Rankings: Class position based on total score
    """

    def calculate_subject_score(
        self,
        component_scores: dict[str, Decimal | None],
        components: list[AssessmentComponent],
        max_scores: dict[str, Decimal],
    ) -> SubjectScoreResult:
        result = SubjectScoreResult()
        result.component_scores = component_scores

        # Calculate CA total (components with maps_to_ca=True)
        ca_components = [c for c in components if c.maps_to_ca]
        exam_components = [c for c in components if c.maps_to_exam]

        ca_weighted = Decimal("0")
        ca_max = Decimal("0")
        for comp in ca_components:
            score = component_scores.get(comp.component_type.value)
            max_s = max_scores.get(comp.component_type.value, Decimal("10"))
            if score is not None:
                ca_weighted += score
                ca_max += max_s

        exam_weighted = Decimal("0")
        exam_max = Decimal("0")
        for comp in exam_components:
            score = component_scores.get(comp.component_type.value)
            max_s = max_scores.get(comp.component_type.value, Decimal("100"))
            if score is not None:
                exam_weighted += score
                exam_max += max_s

        # Normalize to CA% and Exam% of total 100
        # Default: 50/50 split (configurable via assessment weight)
        ca_weight = sum(c.weight for c in ca_components)
        exam_weight = sum(c.weight for c in exam_components)

        if ca_max > 0:
            result.class_score = (ca_weighted / ca_max) * ca_weight
        else:
            result.class_score = Decimal("0")

        if exam_max > 0:
            result.exams_score = (exam_weighted / exam_max) * exam_weight
        else:
            result.exams_score = Decimal("0")

        result.final_score = result.class_score + result.exams_score
        return result

    def determine_grade(
        self, score: Decimal | None, grades: list[Grade]
    ) -> tuple[str | None, Decimal | None, str | None]:
        if score is None:
            return (None, None, None)

        # Grades are ordered by min_score DESC
        for grade in sorted(grades, key=lambda g: g.min_score, reverse=True):
            if score >= grade.min_score:
                return (grade.grade, grade.grade_point, grade.remark)

        return (None, None, None)
```

---

## 4.5 - 4.9 Additional Score Strategies

Each strategy class follows the same interface. Key differences:

### CambridgeScoreStrategy
- Component-based scoring (coursework + controlled assessment + external exam)
- NO CA/Exam split (all `maps_to_ca=False`, `maps_to_exam=False`)
- Grades: A*-G (IGCSE) or A*-E (A-Level) — determined by grading scale
- Supports effort grades (separate from achievement grade)
- `calculate_subject_score`: weighted average of components, normalized to percentage

> **Template weight reference:** The Cambridge IGCSE template defines 3 components: Coursework 25%, Controlled Assessment 25%, External Exam 50% (see Phase 1, section 1.7). Test expectations in `08-testing.md` test 3.3 currently reference "Coursework 30%, Exam 70%" (2 components) — that is incorrect and should be updated to match the 3-component 25/25/50 definition.

### AmericanScoreStrategy
- Component-based (homework, quizzes, tests, projects, finals)
- GPA calculation: maps letter grade to grade points (A=4.0, B=3.0, etc.)
- Weighted GPA: AP courses add +1.0, Honors add +0.5 to grade points
- `calculate_aggregate`: computes term GPA, cumulative GPA, honor roll status
- Credits earned: if grade >= D (1.0), credits earned = subject's credit_value

### IBScoreStrategy
- Internal Assessment + External Assessment
- Grades: 1-7 achievement levels
- IB DP total: sum of subject grades (max 42) + bonus points from EE+TOK (max 3) = 45
- `calculate_aggregate`: computes total IB points, checks passing threshold (24)
- Criterion-referenced mode: score per criterion, then aggregate to level

### FrenchScoreStrategy
- Controle Continu + Epreuve
- Scores on 0-20 scale
- Coefficient system: each subject has a coefficient, final = sum(score * coefficient) / sum(coefficient)
- Mention: Tres Bien (16+), Bien (14+), Assez Bien (12+), Passable (10+)
- `calculate_aggregate`: computes weighted average, determines mention

### MontessoriScoreStrategy
- Observation + Portfolio + Narrative
- NO numeric grades — uses progress levels (emerging, developing, proficient, mastery)
- `calculate_subject_score`: returns `SubjectScoreResult` with `narrative` field populated
- `determine_grade`: returns progress level string from JSONB config
- `final_score` is None (no numeric total)

---

## 4.10 Refactor TermReportService

**File:** `backend/app/services/exam/report_service.py`

### Key Change

Modify `get_student_subject_results()` to dispatch to the strategy pattern:

```python
async def get_student_subject_results(self, tenant_id, student_id, term_id, class_id, ...):
    # Resolve curriculum profile (uses helper from Phase 1)
    profile = await self._resolve_curriculum_profile(tenant_id, class_id, student_id)

    if profile is None:
        # NO CURRICULUM PROFILE — use existing GES logic UNCHANGED
        return await self._get_student_subject_results_legacy(
            tenant_id, student_id, term_id, class_id, ...
        )

    # Has curriculum profile — use strategy pattern
    strategy = get_score_strategy(profile.curriculum_type)
    structure = await self._get_assessment_structure(profile, academic_year_id)

    if structure is None:
        # Profile exists but no assessment structure — fall back to legacy
        return await self._get_student_subject_results_legacy(
            tenant_id, student_id, term_id, class_id, ...
        )

    return await self._get_student_subject_results_curriculum(
        strategy, structure, profile, tenant_id, student_id, term_id, class_id, ...
    )
```

**CRITICAL:** The existing GES logic is renamed to `_get_student_subject_results_legacy()` but the code is NOT modified. It is the exact same code path that runs today. This ensures zero regression for existing schools.

### Also Refactor: `calculate_student_term_scores()`

**THIS IS CRITICAL AND EASY TO MISS.** The `calculate_student_term_scores()` method (~200 lines) in `report_service.py` populates `TermReport.total_score` and `TermReport.average_score`. It MUST also be dispatched through the strategy pattern, or non-GES curricula will produce incorrect term reports. Apply the same `if profile is None: use legacy` pattern.

### Normalization Layer (New Task — ~3 days)

The current report service code is tightly coupled: it fetches data from the database AND calculates scores in the same methods. The strategy pattern expects pre-fetched, normalized inputs (`component_scores`, `components`, `max_scores`). A normalization layer is needed:

1. **Fetch layer:** Queries `exam_scores`, `continuous_assessments`, and `assessment_components` for all students in a class.
2. **Normalize:** Transforms raw DB rows into the `dict[str, Decimal]` format the strategy's `calculate_subject_score()` expects.
3. **Strategy dispatch:** Passes normalized data to the strategy.

This decoupling is essential for testability and prevents each strategy from needing its own database queries.

### Batch Optimization Preservation

The current GES code uses batch queries (`_batch_get_all_scores`, `_batch_calculate_subject_positions`) that process entire classes at once. The strategy refactor MUST preserve these batch-level operations:

- Fetch scores for ALL students in the class in one query.
- Loop over students, calling the strategy per student with pre-fetched data.
- Do NOT dispatch per-student database queries inside the strategy.
- Position calculation (GES-only) stays at the batch level.

### Strategy Factory

```python
def get_score_strategy(curriculum_type: str) -> ScoreStrategy:
    """Factory function for score strategies."""
    strategies = {
        "ges": GESScoreStrategy,
        "cambridge": CambridgeScoreStrategy,
        "edexcel": CambridgeScoreStrategy,  # shares logic with Cambridge
        "american": AmericanScoreStrategy,
        "ib": IBScoreStrategy,
        "french": FrenchScoreStrategy,
        "montessori": MontessoriScoreStrategy,
        "custom": GESScoreStrategy,  # custom defaults to GES-style
    }
    strategy_class = strategies.get(curriculum_type, GESScoreStrategy)
    return strategy_class()
```

### 4.10.1 Curriculum Switch Confirmation Flow

When a class's curriculum profile is changed mid-year, existing scores and reports may become invalid. The `TermReportService` must expose a dedicated method for this:

```python
async def switch_curriculum(
    self,
    class_id: UUID,
    new_profile_id: UUID,
    tenant_id: UUID,
    confirm: bool = False,
) -> SwitchImpactSummary:
    """
    Switch a class's curriculum profile. Requires confirmation if scores exist.

    Flow:
    1. Count affected students and existing scores for the current term.
    2. If scores exist and confirm=False, return an impact summary WITHOUT
       switching. The caller (endpoint) returns this summary to the user
       for review before they confirm.
    3. If confirm=True (or no scores exist), update class.curriculum_profile_id.
    4. Log a structured audit event with:
       - old_profile_id, new_profile_id
       - affected_student_count, affected_score_count
    5. Flag existing term reports for the current term as needs_recalculation
       by setting term_reports.extra_data['needs_recalculation'] = True.
    """
```

**SwitchImpactSummary** (returned when `confirm=False` and scores exist):

```python
class SwitchImpactSummary:
    class_id: UUID
    current_profile_id: UUID | None
    new_profile_id: UUID
    affected_student_count: int
    affected_score_count: int
    affected_report_count: int
    requires_confirmation: bool  # True when scores/reports exist
    warnings: list[str]          # e.g., ["12 term reports will need recalculation"]
```

The endpoint should be:

| Method | Path | Handler | Permission |
|--------|------|---------|------------|
| POST | /curriculum/classes/{class_id}/switch-profile | switch_class_curriculum | curriculum.update |

Request body: `{ "new_profile_id": UUID, "confirm": bool }`.

---

## 4.11 GradeEquivalencyService

**File:** `backend/app/services/curriculum/equivalency_service.py`

```python
class GradeEquivalencyService:
    """
    Manages cross-curriculum grade mappings.

    Maps grades between different grading scales (e.g., WAEC A1 -> Cambridge A*).
    Used when transferring students between curricula or generating
    comparative reports.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def create_equivalency(
        self, data: GradeEquivalencyCreate, tenant_id: UUID
    ) -> GradeEquivalency:
        """
        Create a grade equivalency mapping.

        Validations:
        - source_grading_scale_id belongs to tenant (defense-in-depth)
        - target_grading_scale_id belongs to tenant
        - source_grading_scale_id != target_grading_scale_id (no self-mapping)
        - Each source_grade_id in mappings belongs to the source scale
        - Each target_grade_id in mappings belongs to the target scale
        - No duplicate (tenant_id, source_grade_id, target_grading_scale_id) rows
        """
        # Validate source scale belongs to tenant
        source_scale = await self._get_scale_or_raise(
            data.source_grading_scale_id, tenant_id
        )
        # Validate target scale belongs to tenant
        target_scale = await self._get_scale_or_raise(
            data.target_grading_scale_id, tenant_id
        )

        # Prevent self-mapping
        if data.source_grading_scale_id == data.target_grading_scale_id:
            raise self.Error(
                "Cannot create equivalency between a scale and itself", 422
            )

        # Create one GradeEquivalency row per mapping entry
        equivalencies = []
        for mapping in data.mappings:
            equivalency = GradeEquivalency(
                tenant_id=tenant_id,
                source_grading_scale_id=data.source_grading_scale_id,
                target_grading_scale_id=data.target_grading_scale_id,
                source_grade_id=mapping.source_grade_id,
                target_grade_id=mapping.target_grade_id,
                notes=mapping.notes,
            )
            self.db.add(equivalency)
            equivalencies.append(equivalency)

        await self.db.flush()
        for eq in equivalencies:
            await self.db.refresh(eq)
        return equivalencies

    async def get_equivalencies(
        self,
        tenant_id: UUID,
        source_scale_id: UUID | None = None,
        target_scale_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GradeEquivalency], int]:
        """
        List equivalencies with optional filtering by source/target scale.
        Returns (items, total_count) for pagination.
        """
        query = (
            select(GradeEquivalency)
            .where(GradeEquivalency.tenant_id == tenant_id)
        )

        if source_scale_id:
            query = query.where(
                GradeEquivalency.source_grading_scale_id == source_scale_id
            )
        if target_scale_id:
            query = query.where(
                GradeEquivalency.target_grading_scale_id == target_scale_id
            )

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_equivalency(
        self, id: UUID, tenant_id: UUID
    ) -> GradeEquivalency:
        """Get a single equivalency by ID."""
        result = await self.db.execute(
            select(GradeEquivalency)
            .where(GradeEquivalency.tenant_id == tenant_id)
            .where(GradeEquivalency.id == id)
        )
        equivalency = result.scalar_one_or_none()
        if not equivalency:
            raise self.Error("Grade equivalency not found", 404)
        return equivalency

    async def update_equivalency(
        self, id: UUID, data: GradeEquivalencyUpdate, tenant_id: UUID
    ) -> GradeEquivalency:
        """Update an existing equivalency."""
        equivalency = await self.get_equivalency(id, tenant_id)

        if data.notes is not None:
            equivalency.notes = data.notes

        await self.db.flush()
        await self.db.refresh(equivalency)
        return equivalency

    async def delete_equivalency(self, id: UUID, tenant_id: UUID) -> None:
        """
        Hard delete an equivalency (not soft delete).

        Grade equivalencies are reference/configuration data,
        not transactional records, so hard delete is appropriate.
        """
        equivalency = await self.get_equivalency(id, tenant_id)
        await self.db.delete(equivalency)
        await self.db.flush()

    async def convert_grade(
        self,
        source_grade_id: UUID,
        source_scale_id: UUID,
        target_scale_id: UUID,
        tenant_id: UUID,
    ) -> GradeEquivalency | None:
        """
        Look up the equivalent grade in the target scale for a given source grade.

        Returns the GradeEquivalency row if a mapping exists, None otherwise.
        The caller can then access .target_grade_id to resolve the target grade.
        """
        result = await self.db.execute(
            select(GradeEquivalency)
            .where(GradeEquivalency.tenant_id == tenant_id)
            .where(GradeEquivalency.source_grade_id == source_grade_id)
            .where(GradeEquivalency.source_grading_scale_id == source_scale_id)
            .where(GradeEquivalency.target_grading_scale_id == target_scale_id)
        )
        return result.scalar_one_or_none()

    async def _get_scale_or_raise(
        self, scale_id: UUID, tenant_id: UUID
    ) -> Any:
        """Validate that a grading scale belongs to the tenant."""
        result = await self.db.execute(
            select(GradingScale)
            .where(GradingScale.tenant_id == tenant_id)
            .where(GradingScale.id == scale_id)
        )
        scale = result.scalar_one_or_none()
        if not scale:
            raise self.Error(
                f"Grading scale {scale_id} not found or does not belong to tenant",
                404,
            )
        return scale
```

---

## 4.12 SubjectMappingService

**File:** `backend/app/services/curriculum/subject_mapping_service.py`

```python
class SubjectMappingService:
    """
    Manages mappings between internal subjects and curriculum-specific metadata.

    Each mapping links a Subject to a CurriculumProfile with external codes,
    names, credit values, and curriculum-specific configuration.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def create_mapping(
        self, data: SubjectCurriculumMappingCreate, tenant_id: UUID
    ) -> SubjectCurriculumMapping:
        """
        Create a subject-curriculum mapping.

        Validations:
        - subject_id belongs to tenant (defense-in-depth)
        - curriculum_profile_id belongs to tenant
        - No duplicate (tenant_id, subject_id, curriculum_profile_id)
        """
        # Validate subject belongs to tenant
        await self._validate_subject(data.subject_id, tenant_id)
        # Validate curriculum profile belongs to tenant
        await self._validate_profile(data.curriculum_profile_id, tenant_id)

        mapping = SubjectCurriculumMapping(
            tenant_id=tenant_id,
            subject_id=data.subject_id,
            curriculum_profile_id=data.curriculum_profile_id,
            external_code=data.external_subject_code,
            external_name=data.external_subject_name,
            credits=data.credit_value,
            config=None,
        )
        self.db.add(mapping)
        await self.db.flush()
        await self.db.refresh(mapping)
        return mapping

    async def get_mappings(
        self,
        tenant_id: UUID,
        curriculum_profile_id: UUID | None = None,
        subject_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[SubjectCurriculumMapping], int]:
        """
        List mappings with optional filtering.
        Returns (items, total_count) for pagination.
        """
        query = (
            select(SubjectCurriculumMapping)
            .where(SubjectCurriculumMapping.tenant_id == tenant_id)
        )

        if curriculum_profile_id:
            query = query.where(
                SubjectCurriculumMapping.curriculum_profile_id == curriculum_profile_id
            )
        if subject_id:
            query = query.where(
                SubjectCurriculumMapping.subject_id == subject_id
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_mapping(
        self, id: UUID, tenant_id: UUID
    ) -> SubjectCurriculumMapping:
        """Get a single mapping by ID."""
        result = await self.db.execute(
            select(SubjectCurriculumMapping)
            .where(SubjectCurriculumMapping.tenant_id == tenant_id)
            .where(SubjectCurriculumMapping.id == id)
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            raise self.Error("Subject curriculum mapping not found", 404)
        return mapping

    async def update_mapping(
        self, id: UUID, data: SubjectCurriculumMappingUpdate, tenant_id: UUID
    ) -> SubjectCurriculumMapping:
        """Update an existing mapping."""
        mapping = await self.get_mapping(id, tenant_id)

        if data.external_subject_code is not None:
            mapping.external_code = data.external_subject_code
        if data.external_subject_name is not None:
            mapping.external_name = data.external_subject_name
        if data.is_core is not None:
            mapping.config = mapping.config or {}
            mapping.config["is_core"] = data.is_core
        if data.credit_value is not None:
            mapping.credits = data.credit_value
        if data.notes is not None:
            mapping.config = mapping.config or {}
            mapping.config["notes"] = data.notes

        await self.db.flush()
        await self.db.refresh(mapping)
        return mapping

    async def delete_mapping(self, id: UUID, tenant_id: UUID) -> None:
        """
        Hard delete a mapping (not soft delete).

        Subject-curriculum mappings are configuration data,
        not transactional records.
        """
        mapping = await self.get_mapping(id, tenant_id)
        await self.db.delete(mapping)
        await self.db.flush()

    async def get_mappings_for_profile(
        self, profile_id: UUID, tenant_id: UUID
    ) -> list[SubjectCurriculumMapping]:
        """Get all subject mappings for a specific curriculum profile."""
        # Validate profile belongs to tenant
        await self._validate_profile(profile_id, tenant_id)

        result = await self.db.execute(
            select(SubjectCurriculumMapping)
            .where(SubjectCurriculumMapping.tenant_id == tenant_id)
            .where(SubjectCurriculumMapping.curriculum_profile_id == profile_id)
        )
        return result.scalars().all()

    async def _validate_subject(self, subject_id: UUID, tenant_id: UUID) -> None:
        """Validate that a subject belongs to the tenant."""
        result = await self.db.execute(
            select(Subject)
            .where(Subject.tenant_id == tenant_id)
            .where(Subject.id == subject_id)
            .where(Subject.deleted_at.is_(None))
        )
        if not result.scalar_one_or_none():
            raise self.Error(
                f"Subject {subject_id} not found or does not belong to tenant",
                404,
            )

    async def _validate_profile(
        self, profile_id: UUID, tenant_id: UUID
    ) -> None:
        """Validate that a curriculum profile belongs to the tenant."""
        result = await self.db.execute(
            select(CurriculumProfile)
            .where(CurriculumProfile.tenant_id == tenant_id)
            .where(CurriculumProfile.id == profile_id)
            .where(CurriculumProfile.deleted_at.is_(None))
        )
        if not result.scalar_one_or_none():
            raise self.Error(
                f"Curriculum profile {profile_id} not found or does not belong to tenant",
                404,
            )
```

---

## 4.13 Equivalency + Subject Mapping Pydantic Schemas

**File:** `backend/app/schemas/curriculum.py` (append to existing file)

### Grade Equivalency Schemas

```python
class GradeMapping(BaseSchema):
    """A single grade-to-grade mapping within an equivalency."""
    model_config = ConfigDict(from_attributes=True)

    source_grade_id: UUID
    target_grade_id: UUID
    notes: str | None = None


class GradeEquivalencyCreate(BaseSchema):
    """Create a set of grade equivalency mappings between two scales."""
    model_config = ConfigDict(from_attributes=True)

    source_grading_scale_id: UUID
    target_grading_scale_id: UUID
    mappings: list[GradeMapping] = Field(
        ..., min_length=1,
        description="At least one grade mapping is required",
    )


class GradeEquivalencyUpdate(BaseSchema):
    """Update an existing grade equivalency."""
    model_config = ConfigDict(from_attributes=True)

    mappings: list[GradeMapping] | None = None
    notes: str | None = None


class GradeEquivalencyResponse(BaseSchema):
    """Response for a single grade equivalency row."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_grading_scale_id: UUID
    target_grading_scale_id: UUID
    source_grade_id: UUID
    target_grade_id: UUID
    notes: str | None
    created_at: datetime
    updated_at: datetime


class GradeEquivalencyListResponse(BaseSchema):
    """Paginated list of grade equivalencies."""
    model_config = ConfigDict(from_attributes=True)

    items: list[GradeEquivalencyResponse]
    total: int
    page: int
    page_size: int
    pages: int


class GradeConvertRequest(BaseSchema):
    """Request to convert a grade from one scale to another."""
    model_config = ConfigDict(from_attributes=True)

    source_grade_id: UUID
    source_scale_id: UUID
    target_scale_id: UUID
```

### Subject Curriculum Mapping Schemas

```python
class SubjectCurriculumMappingCreate(BaseSchema):
    """Create a subject-to-curriculum mapping."""
    model_config = ConfigDict(from_attributes=True)

    subject_id: UUID
    curriculum_profile_id: UUID
    external_subject_code: str | None = Field(
        default=None, max_length=20,
        description="External subject code, e.g., '0580' for IGCSE Mathematics",
    )
    external_subject_name: str | None = Field(
        default=None, max_length=200,
        description="Official curriculum subject name",
    )
    is_core: bool = False
    credit_value: Decimal | None = Field(
        default=None, ge=0, le=99.9,
        description="Credit value (American system)",
    )
    notes: str | None = None


class SubjectCurriculumMappingUpdate(BaseSchema):
    """Update a subject-to-curriculum mapping."""
    model_config = ConfigDict(from_attributes=True)

    external_subject_code: str | None = Field(
        default=None, max_length=20,
    )
    external_subject_name: str | None = Field(
        default=None, max_length=200,
    )
    is_core: bool | None = None
    credit_value: Decimal | None = Field(
        default=None, ge=0, le=99.9,
    )
    notes: str | None = None


class SubjectCurriculumMappingResponse(BaseSchema):
    """Response for a single subject-curriculum mapping."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_id: UUID
    curriculum_profile_id: UUID
    external_subject_code: str | None
    external_subject_name: str | None
    is_core: bool
    credit_value: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SubjectCurriculumMappingListResponse(BaseSchema):
    """Paginated list of subject-curriculum mappings."""
    model_config = ConfigDict(from_attributes=True)

    items: list[SubjectCurriculumMappingResponse]
    total: int
    page: int
    page_size: int
    pages: int
```

---

## 4.14 Equivalency Endpoints

**File:** `backend/app/api/v1/endpoints/curriculum/equivalencies.py`

### Endpoint Table

| Method | Path | Handler | Permission | Rate Limit |
|--------|------|---------|------------|------------|
| POST | `/curriculum/grade-equivalencies` | `create_equivalency` | `curriculum.create` | 100/min |
| GET | `/curriculum/grade-equivalencies` | `list_equivalencies` | `curriculum.read` | 100/min |
| GET | `/curriculum/grade-equivalencies/{id}` | `get_equivalency` | `curriculum.read` | 100/min |
| PUT | `/curriculum/grade-equivalencies/{id}` | `update_equivalency` | `curriculum.update` | 100/min |
| DELETE | `/curriculum/grade-equivalencies/{id}` | `delete_equivalency` | `curriculum.delete` | 100/min |
| POST | `/curriculum/grade-equivalencies/convert` | `convert_grade` | `curriculum.read` | 100/min |

### Endpoint Signatures

```python
router = APIRouter(prefix="/curriculum/grade-equivalencies", tags=["Curriculum"])


@router.post(
    "",
    response_model=list[GradeEquivalencyResponse],
    status_code=201,
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_equivalency(
    data: GradeEquivalencyCreate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = GradeEquivalencyService(db)
    try:
        equivalencies = await service.create_equivalency(
            data, school_ctx.tenant_id
        )
        return equivalencies
    except GradeEquivalencyService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "",
    response_model=GradeEquivalencyListResponse,
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_equivalencies(
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    source_scale_id: UUID | None = None,
    target_scale_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    service = GradeEquivalencyService(db)
    items, total = await service.get_equivalencies(
        tenant_id=school_ctx.tenant_id,
        source_scale_id=source_scale_id,
        target_scale_id=target_scale_id,
        page=page,
        page_size=page_size,
    )
    return GradeEquivalencyListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/{id}",
    response_model=GradeEquivalencyResponse,
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_equivalency(
    id: UUID,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = GradeEquivalencyService(db)
    try:
        return await service.get_equivalency(id, school_ctx.tenant_id)
    except GradeEquivalencyService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/{id}",
    response_model=GradeEquivalencyResponse,
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_equivalency(
    id: UUID,
    data: GradeEquivalencyUpdate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = GradeEquivalencyService(db)
    try:
        return await service.update_equivalency(id, data, school_ctx.tenant_id)
    except GradeEquivalencyService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/{id}",
    status_code=204,
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_equivalency(
    id: UUID,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = GradeEquivalencyService(db)
    try:
        await service.delete_equivalency(id, school_ctx.tenant_id)
    except GradeEquivalencyService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/convert",
    response_model=GradeEquivalencyResponse | None,
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def convert_grade(
    data: GradeConvertRequest,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = GradeEquivalencyService(db)
    result = await service.convert_grade(
        source_grade_id=data.source_grade_id,
        source_scale_id=data.source_scale_id,
        target_scale_id=data.target_scale_id,
        tenant_id=school_ctx.tenant_id,
    )
    return result
```

---

## 4.15 Subject Mapping Endpoints

**File:** `backend/app/api/v1/endpoints/curriculum/subject_mappings.py`

### Endpoint Table

| Method | Path | Handler | Permission | Rate Limit |
|--------|------|---------|------------|------------|
| POST | `/curriculum/subject-mappings` | `create_mapping` | `curriculum.create` | 100/min |
| GET | `/curriculum/subject-mappings` | `list_mappings` | `curriculum.read` | 100/min |
| GET | `/curriculum/subject-mappings/{id}` | `get_mapping` | `curriculum.read` | 100/min |
| PUT | `/curriculum/subject-mappings/{id}` | `update_mapping` | `curriculum.update` | 100/min |
| DELETE | `/curriculum/subject-mappings/{id}` | `delete_mapping` | `curriculum.delete` | 100/min |

### Endpoint Signatures

```python
router = APIRouter(prefix="/curriculum/subject-mappings", tags=["Curriculum"])


@router.post(
    "",
    response_model=SubjectCurriculumMappingResponse,
    status_code=201,
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_mapping(
    data: SubjectCurriculumMappingCreate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = SubjectMappingService(db)
    try:
        mapping = await service.create_mapping(data, school_ctx.tenant_id)
        return mapping
    except SubjectMappingService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "",
    response_model=SubjectCurriculumMappingListResponse,
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_mappings(
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    curriculum_profile_id: UUID | None = None,
    subject_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    service = SubjectMappingService(db)
    items, total = await service.get_mappings(
        tenant_id=school_ctx.tenant_id,
        curriculum_profile_id=curriculum_profile_id,
        subject_id=subject_id,
        page=page,
        page_size=page_size,
    )
    return SubjectCurriculumMappingListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/{id}",
    response_model=SubjectCurriculumMappingResponse,
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_mapping(
    id: UUID,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = SubjectMappingService(db)
    try:
        return await service.get_mapping(id, school_ctx.tenant_id)
    except SubjectMappingService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/{id}",
    response_model=SubjectCurriculumMappingResponse,
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_mapping(
    id: UUID,
    data: SubjectCurriculumMappingUpdate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = SubjectMappingService(db)
    try:
        return await service.update_mapping(id, data, school_ctx.tenant_id)
    except SubjectMappingService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/{id}",
    status_code=204,
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_mapping(
    id: UUID,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
):
    service = SubjectMappingService(db)
    try:
        await service.delete_mapping(id, school_ctx.tenant_id)
    except SubjectMappingService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)
```

---

## 4.16 Report Card HTML Templates

Create 5 new Jinja2 HTML templates in `backend/app/templates/reports/`.

**SECURITY: All templates MUST use `autoescape=True`** in the Jinja2 environment. The `header_text` and `footer_text` fields from `ReportCardConfig` are user-supplied free text rendered in these templates. While the Pydantic schema strips HTML tags (defense-in-depth), autoescape prevents any residual XSS in the HTML web preview mode.

### Shared Macros (`_report_macros.html`)
Extract common sections from the existing `term_report.html` into macros:
- `report_header(school, student, term)` — school logo, name, student info
- `attendance_section(attendance)` — days present/absent/percentage
- `remarks_section(remarks)` — class teacher + headmaster remarks
- `report_footer(school)` — school contact info, signature lines

### Template: `cambridge_report.html`
- Component columns: one per assessment component (Coursework, Controlled Assessment, External Exam)
- Effort grade column
- Predicted grade column (if enabled)
- Teacher comment column
- NO position/ranking columns
- Class average row at bottom

### Template: `american_report.html`
- Component columns: one per component
- Letter grade column
- Grade points column
- Credits attempted / earned columns
- Term GPA and Cumulative GPA summary
- Honor Roll banner (if applicable)
- NO position/ranking

### Template: `ib_report.html`
- Achievement Level column (1-7)
- Criterion scores (if criterion-based)
- IB Total Points summary (out of 45)
- Learner Profile traits assessment grid (if enabled)
- ATL Skills assessment grid (if enabled)
- NO position/ranking

### Template: `french_report.html`
- Score column (0-20 scale)
- Coefficient column
- Weighted score column (score * coefficient)
- Class average column
- Mention banner (Tres Bien, Bien, Assez Bien, Passable)
- Position column (French system uses rankings)

### Template: `montessori_report.html`
- Developmental area sections (not traditional subject rows)
- Progress level indicators (emerging → mastery)
- Narrative text blocks per area
- Work samples section (placeholder)
- Goals section
- NO numeric scores, NO grades, NO rankings

---

## 4.17 PDF Service Template Selection

**File:** `backend/app/services/pdf.py`

Add template selection logic:

```python
REPORT_TEMPLATES = {
    "ges": "reports/term_report.html",          # existing
    "cambridge": "reports/cambridge_report.html",
    "american": "reports/american_report.html",
    "ib": "reports/ib_report.html",
    "french": "reports/french_report.html",
    "montessori": "reports/montessori_report.html",
    "default": "reports/term_report.html",      # fallback
}

def get_report_template(profile: CurriculumProfile | None) -> str:
    if profile is None:
        return REPORT_TEMPLATES["default"]
    template_key = profile.curriculum_type.value if hasattr(profile.curriculum_type, 'value') else profile.curriculum_type
    return REPORT_TEMPLATES.get(template_key, REPORT_TEMPLATES["default"])
```

---

## 4.18 Exam Schema Updates

**File:** `backend/app/schemas/exam.py`

Add to `TermReportResponse` / `TermReportWithDetailsResponse`:

```python
curriculum_profile_id: UUID | None = None
gpa: Decimal | None = None
weighted_gpa: Decimal | None = None
cumulative_gpa: Decimal | None = None
total_credits_earned: Decimal | None = None
cumulative_credits: Decimal | None = None
honor_roll: bool | None = None
ib_total_points: int | None = None
french_mention: str | None = None
extra_data: dict | None = None
```

Add to `ExamScoreResponse`:

```python
effort_grade: str | None = None
```

Add `effort_grade` to `ScoreEntry` schema for score input:

```python
effort_grade: str | None = Field(
    default=None, max_length=5,
    description="Effort grade (Cambridge: 1-5 or A-E)",
)
```

---

## 4.19 Test Infrastructure

Add to `TENANT_SCOPED_TABLES` in `conftest.py`:

```python
"grade_equivalencies",
"subject_curriculum_mappings",
```

### Key Test Cases

**GES Regression Test (CRITICAL):**
- Set up a tenant with NO curriculum profile
- Create assessment weights, exams, CA, scores (same as existing test data)
- Generate a term report
- Assert: total_score, average_score, class_position, grade — ALL identical to values produced by the pre-refactor code
- This test MUST pass before the refactor is merged

**Strategy Unit Tests:**
- Each strategy tested with known inputs and expected outputs
- Test edge cases: all components missing, partial scores, absent students
- Test grade determination at boundaries (e.g., score of exactly 80.00)

**Multi-Curriculum Test:**
- Tenant with two classes: one GES, one Cambridge
- Generate reports for both
- Assert: GES class uses legacy template; Cambridge class uses Cambridge template
- Assert: GES class has positions; Cambridge class does not
