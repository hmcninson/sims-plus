# Phase 1: Models & Migration

**Phase:** MC-Sprint 1 (Foundation)
**Depends on:** Nothing (can start immediately)
**Parallel with:** Phase 1 Frontend (after models are merged)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 1.1 | Create enum definitions | `backend/app/models/curriculum.py` | 0.5d |
| 1.2 | Create CurriculumProfile model | `backend/app/models/curriculum.py` | 0.5d |
| 1.3 | Create AssessmentStructure model | `backend/app/models/curriculum.py` | 0.5d |
| 1.4 | Create AssessmentComponent model | `backend/app/models/curriculum.py` | 0.5d |
| 1.5 | Create ReportCardConfig model | `backend/app/models/curriculum.py` | 0.5d |
| 1.6 | Register models in `__init__.py` | `backend/app/models/__init__.py` | 0.25d |
| 1.7 | Modify existing models (School, Class, Student, GradingScale) | Multiple model files | 1d |
| 1.8 | Create Alembic migration (schema) | `backend/alembic/versions/20260310_0100_curriculum_foundation.py` | 2d |
| 1.9 | Create Alembic migration (data) | `backend/alembic/versions/20260310_0200_curriculum_data_migration.py` | 1d |
| 1.10 | Update test infrastructure | `backend/tests/conftest.py`, `backend/scripts/verify_rls.py` | 0.5d |

---

## 1.1 Enum Definitions

**File:** `backend/app/models/curriculum.py` (top of file)

All enums follow the project convention:
- Python class: `class Name(str, Enum)` with UPPERCASE members
- Database: lowercase `.value` strings
- PostgreSQL type: lowercase name with no underscores
- `values_callable=lambda x: [e.value for e in x]` on all SQLEnum columns

### CurriculumType (new DB enum: `curriculumtype`)

```python
class CurriculumType(str, Enum):
    """Supported curriculum frameworks."""

    GES = "ges"                  # Ghana Education Service
    CAMBRIDGE = "cambridge"      # Cambridge International (IGCSE, A-Level)
    EDEXCEL = "edexcel"          # Pearson Edexcel (IGCSE, A-Level)
    AMERICAN = "american"        # US Common Core / AP
    IB = "ib"                    # International Baccalaureate (MYP, DP)
    FRENCH = "french"            # French Baccalaureate
    MONTESSORI = "montessori"    # Montessori (narrative-based)
    CUSTOM = "custom"            # School-defined custom curriculum
```

### AssessmentComponentType (new DB enum: `assessmentcomponenttype`)

```python
class AssessmentComponentType(str, Enum):
    """Types of assessment components across all curricula."""

    # Universal
    CONTINUOUS_ASSESSMENT = "continuous_assessment"
    EXAM = "exam"
    # GES-specific
    CLASS_WORK = "class_work"
    HOMEWORK = "homework"
    MIDTERM = "midterm"
    END_TERM = "end_term"
    # Cambridge/Edexcel
    COURSEWORK = "coursework"
    CONTROLLED_ASSESSMENT = "controlled_assessment"
    EXTERNAL_EXAM = "external_exam"
    PRACTICAL = "practical"
    ORAL = "oral"
    # IB
    INTERNAL_ASSESSMENT = "internal_assessment"
    EXTERNAL_ASSESSMENT = "external_assessment"
    EXTENDED_ESSAY = "extended_essay"
    TOK = "tok"                          # Theory of Knowledge
    CAS = "cas"                          # Creativity, Activity, Service
    # American
    QUIZ = "quiz"
    TEST = "test"
    PROJECT = "project"
    PARTICIPATION = "participation"
    FINAL = "final"
    # French
    CONTROLE_CONTINU = "controle_continu"
    EPREUVE = "epreuve"
    # Montessori
    OBSERVATION = "observation"
    NARRATIVE = "narrative"
    PORTFOLIO = "portfolio"
```

### ScoreDisplayMode (new DB enum: `scoredisplaymode`)

```python
class ScoreDisplayMode(str, Enum):
    """How scores are displayed on reports."""

    PERCENTAGE = "percentage"              # 85%
    GRADE_ONLY = "grade_only"              # A*
    GRADE_AND_SCORE = "grade_and_score"    # A* (92%)
    LEVEL = "level"                        # Level 7 (IB)
    GPA = "gpa"                            # 3.85
    NARRATIVE = "narrative"                # Qualitative description only
    MENTION = "mention"                    # Tres Bien (French)
```

### GradingScaleType (EXTEND existing DB enum: `gradingscaletype`)

Add 6 new values to the existing enum in `backend/app/models/academic/subject_models.py`:

```python
class GradingScaleType(str, Enum):
    """Type of grading scale."""

    # Existing values (DO NOT CHANGE)
    WAEC = "waec"
    GPA = "gpa"
    PERCENTAGE = "percentage"
    CUSTOM = "custom"

    # New values (Phase 1)
    CAMBRIDGE = "cambridge"    # A*-G (IGCSE), A*-E (A-Level)
    EDEXCEL = "edexcel"        # 9-1 (IGCSE), A*-E (A-Level)
    IB = "ib"                  # 1-7 achievement levels
    FRENCH = "french"          # 0-20 scale
    NARRATIVE = "narrative"    # Qualitative (Montessori)
    AMERICAN = "american"      # A-F with +/- modifiers
```

**Important:** The migration must use `ALTER TYPE gradingscaletype ADD VALUE` for each new value. This is NOT transactional in PostgreSQL and cannot be rolled back, but is backward-compatible.

---

## 1.2 CurriculumProfile Model

**File:** `backend/app/models/curriculum.py`

```python
class CurriculumProfile(Base, TenantMixin, SoftDeleteMixin):
    """
    Central curriculum configuration entity.

    Bundles a grading scale, assessment structure, and report card
    preferences for a specific curriculum framework.
    """

    __tablename__ = "curriculum_profiles"
    __table_args__ = (
        # Partial unique index — allows re-creating a profile with the same name
        # after the original is soft-deleted (deleted_at IS NOT NULL).
        Index(
            "uq_curriculum_profile_name",
            "tenant_id", "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Profile name, e.g., 'Cambridge IGCSE', 'GES Standard'",
    )
    curriculum_type: Mapped[CurriculumType] = mapped_column(
        SQLEnum(
            CurriculumType,
            name="curriculumtype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Linked Grading Scale
    grading_scale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grading_scales.id", ondelete="SET NULL"),
        nullable=True,
        comment="Default grading scale for this curriculum",
    )

    # Calendar Configuration
    academic_calendar_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="terms",
        comment="'terms' (3), 'semesters' (2), 'quarters' (4)",
    )
    periods_per_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Number of terms/semesters per academic year",
    )

    # Display Configuration
    score_display_mode: Mapped[ScoreDisplayMode] = mapped_column(
        SQLEnum(
            ScoreDisplayMode,
            name="scoredisplaymode",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ScoreDisplayMode.GRADE_AND_SCORE,
    )
    show_position: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Show class position/ranking on reports",
    )
    show_class_average: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Feature Flags
    use_gpa: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Calculate and display GPA (American, IB)",
    )
    use_credits: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Track credit/unit accumulation (American)",
    )
    use_criterion_grading: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Use criterion-referenced grading (IB MYP)",
    )

    # Curriculum-Specific Configuration (JSONB)
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Curriculum-specific settings (see docs for schema per type)",
    )

    # Status
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Default profile for this school",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    grading_scale: Mapped["GradingScale"] = relationship(
        "GradingScale",
        lazy="raise",
    )
    assessment_structures: Mapped[list["AssessmentStructure"]] = relationship(
        "AssessmentStructure",
        back_populates="curriculum_profile",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    report_card_configs: Mapped[list["ReportCardConfig"]] = relationship(
        "ReportCardConfig",
        back_populates="curriculum_profile",
        cascade="all, delete-orphan",
        lazy="raise",
    )
```

### JSONB `config` Field Schemas

Each curriculum type has a different config schema. The service layer validates config against the curriculum type on create/update.

**IB:**
```json
{
  "ib_programme": "dp",
  "learner_profile_traits": ["inquirers", "knowledgeable", "thinkers", "communicators", "principled", "open-minded", "caring", "risk-takers", "balanced", "reflective"],
  "atl_skills": ["thinking", "communication", "social", "self-management", "research"],
  "max_total_points": 45,
  "bonus_points_max": 3,
  "passing_total": 24
}
```

**American:**
```json
{
  "gpa_scale": 4.0,
  "weighted_gpa": true,
  "honor_roll_threshold": 3.5,
  "ap_weight_bonus": 1.0,
  "honors_weight_bonus": 0.5,
  "graduation_credits_required": 24
}
```

**French:**
```json
{
  "mention_thresholds": {
    "tres_bien": 16,
    "bien": 14,
    "assez_bien": 12,
    "passable": 10
  },
  "max_score": 20,
  "coefficient_system": true
}
```

**Montessori:**
```json
{
  "developmental_areas": ["practical_life", "sensorial", "language", "mathematics", "cultural"],
  "progress_levels": ["emerging", "developing", "proficient", "mastery"],
  "narrative_required": true
}
```

**GES:** `null` (no extra config needed — all GES settings come from existing `AssessmentWeight` and `AcademicSettings` tables).

**Cambridge/Edexcel:** `null` or `{"programme": "igcse"}` / `{"programme": "a_level"}`.

---

## 1.3 AssessmentStructure Model

**File:** `backend/app/models/curriculum.py`

```python
class AssessmentStructure(Base, TenantMixin, SoftDeleteMixin):
    """
    Flexible assessment weight system for a curriculum profile.

    Replaces the rigid 4-column AssessmentWeight model with an
    N-component system. Each structure contains multiple components
    whose weights must sum to 100.

    NOTE: Soft-deleting a CurriculumProfile should cascade soft-deletes
    to its AssessmentStructures in the service layer (set deleted_at on
    all child structures). SQLAlchemy cascade="all, delete-orphan" only
    handles hard deletes; soft-delete cascading must be explicit.
    """

    __tablename__ = "assessment_structures"
    __table_args__ = (
        Index(
            "uq_assessment_structure",
            "tenant_id", "curriculum_profile_id",
            # Sentinel UUID for NULL academic_year_id — collision probability
            # negligible with gen_random_uuid()
            text("COALESCE(academic_year_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
        ),
    )

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
        comment="Year-specific override; NULL = default structure",
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g., 'IGCSE Assessment Structure'",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    curriculum_profile: Mapped["CurriculumProfile"] = relationship(
        "CurriculumProfile",
        back_populates="assessment_structures",
        lazy="raise",
    )
    components: Mapped[list["AssessmentComponent"]] = relationship(
        "AssessmentComponent",
        back_populates="assessment_structure",
        cascade="all, delete-orphan",
        order_by="AssessmentComponent.sequence",
        lazy="raise",
    )
```

---

## 1.4 AssessmentComponent Model

**File:** `backend/app/models/curriculum.py`

```python
class AssessmentComponent(Base, TenantMixin):
    """
    Individual assessment weight component within a structure.

    Each component has a type, weight (percentage), and flags
    indicating whether it maps to the legacy CA/Exam report columns.
    """

    __tablename__ = "assessment_components"

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links
    assessment_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_structures.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Component Definition
    component_type: Mapped[AssessmentComponentType] = mapped_column(
        SQLEnum(
            AssessmentComponentType,
            name="assessmentcomponenttype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name, e.g., 'Coursework'",
    )
    weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Percentage weight (all components in structure must sum to 100)",
    )
    max_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Optional fixed max score for this component",
    )

    # Flags
    is_external: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Externally assessed (Cambridge papers, WAEC exam)",
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Display order within structure",
    )
    maps_to_ca: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Maps to 'Class Score' column on legacy GES report cards",
    )
    maps_to_exam: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Maps to 'Exams Score' column on legacy GES report cards",
    )

    # Curriculum-Specific Config
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Component-specific config (e.g., IB criterion definitions)",
    )

    # Relationships
    assessment_structure: Mapped["AssessmentStructure"] = relationship(
        "AssessmentStructure",
        back_populates="components",
        lazy="raise",
    )
```

### maps_to_ca / maps_to_exam Explanation

These flags enable backward compatibility with the existing GES report card template which shows "Class Score" and "Exams Score" columns:

| Curriculum | Component | maps_to_ca | maps_to_exam |
|------------|-----------|------------|--------------|
| GES | Class Work (20%) | True | False |
| GES | Homework (10%) | True | False |
| GES | Midterm (20%) | True | False |
| GES | End Term (50%) | False | True |
| Cambridge | Coursework (25%) | False | False |
| Cambridge | Controlled Assessment (25%) | False | False |
| Cambridge | External Exam (50%) | False | False |

When all components have `maps_to_ca = false` AND `maps_to_exam = false`, the report card template renders individual component columns instead of the CA/Exam split.

---

## 1.5 ReportCardConfig Model

**File:** `backend/app/models/curriculum.py`

```python
class ReportCardConfig(Base, TenantMixin, SoftDeleteMixin):
    """
    Curriculum-specific report card display configuration.

    Controls which sections and columns appear on the report card
    for a given curriculum profile.

    NOTE: Soft-deleting a CurriculumProfile should cascade soft-deletes
    to its ReportCardConfigs in the service layer.
    """

    __tablename__ = "report_card_configs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "curriculum_profile_id", "template_key",
            name="uq_report_card_config",
        ),
    )

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Template
    template_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="default",
        comment="Template identifier for HTML template selection",
    )

    # Visibility Flags
    # **Precedence rule:** ReportCardConfig settings override CurriculumProfile
    # display settings. The profile-level show_position and show_class_average
    # serve as defaults when no ReportCardConfig exists.
    show_position: Mapped[bool] = mapped_column(Boolean, default=True)
    show_class_average: Mapped[bool] = mapped_column(Boolean, default=True)
    show_subject_position: Mapped[bool] = mapped_column(Boolean, default=True)
    show_effort_grade: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Cambridge-style effort grades (1-5 or A-E)",
    )
    show_predicted_grades: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Show predicted grades (Cambridge/IB for university apps)",
    )
    show_gpa: Mapped[bool] = mapped_column(Boolean, default=False)
    show_credits: Mapped[bool] = mapped_column(Boolean, default=False)
    show_honor_roll: Mapped[bool] = mapped_column(Boolean, default=False)
    show_learner_profile: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="IB Learner Profile traits assessment",
    )
    show_atl_skills: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="IB Approaches to Learning skills",
    )

    # Custom Content
    custom_columns: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional custom columns for the report card",
    )
    header_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Custom header text for the report",
    )
    footer_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Custom footer text for the report",
    )

    # Relationships
    curriculum_profile: Mapped["CurriculumProfile"] = relationship(
        "CurriculumProfile",
        back_populates="report_card_configs",
        lazy="raise",
    )
```

**Audit columns note:** All models inherit `created_at`/`updated_at` from `Base`. The `created_by`/`updated_by` fields should be added via service-layer audit logging (AuditService), not as model columns, consistent with existing SIMS Plus patterns.

---

## 1.6 Register Models

**File:** `backend/app/models/__init__.py`

Add the following import alongside existing model imports:

```python
from app.models.curriculum import (  # noqa: F401
    CurriculumProfile,
    AssessmentStructure,
    AssessmentComponent,
    ReportCardConfig,
)
```

---

## 1.7 Modify Existing Models

### 1.7a School Model — Add curriculum_profile_id

**File:** `backend/app/models/school.py`

Add two new columns after `communication_settings`:

```python
# Curriculum
curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
    nullable=True,
    comment="School's default curriculum profile",
)
curriculum_settings: Mapped[dict | None] = mapped_column(
    JSONB,
    nullable=True,
    default=None,
    comment="School-level curriculum overrides",
)
```

Add import for `UUID` from `sqlalchemy.dialects.postgresql` if not already present.

### 1.7b Class Model — Add curriculum_profile_id

**File:** `backend/app/models/academic/class_models.py`

Add one new column after `is_active`:

```python
# Curriculum (overrides school default for dual-track)
curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
    nullable=True,
    comment="Class-level curriculum override (for dual-track schools)",
)
```

### 1.7c Student Model — Add curriculum tracking

**File:** `backend/app/models/student.py`

Add two new columns:

```python
# Curriculum tracking
curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
    nullable=True,
    comment="Student's current curriculum (inherited from class if NULL)",
)
previous_curriculum_type: Mapped[str | None] = mapped_column(
    String(20),
    nullable=True,
    comment="For transfer students — records origin curriculum type",
)
```

### 1.7d GradingScale Model — Add curriculum_profile_id

**File:** `backend/app/models/academic/subject_models.py`

Add one new column to `GradingScale` after `is_active`:

```python
# Curriculum link
curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
    nullable=True,
    comment="Links scale to a curriculum (NULL = usable by all)",
)
```

Also update the `GradingScaleType` enum with the 6 new values (see section 1.1).

---

## 1.8 Schema Migration (DDL)

**File:** `backend/alembic/versions/20260310_0100_curriculum_foundation.py`

**Revision chain:** `20260303_0200` -> `20260310_0100`

This migration must:

### Step 1: Create New Enums

```python
# Create new enum types
op.execute("CREATE TYPE curriculumtype AS ENUM ('ges', 'cambridge', 'edexcel', 'american', 'ib', 'french', 'montessori', 'custom')")

op.execute("CREATE TYPE assessmentcomponenttype AS ENUM ('continuous_assessment', 'exam', 'class_work', 'homework', 'midterm', 'end_term', 'coursework', 'controlled_assessment', 'external_exam', 'practical', 'oral', 'internal_assessment', 'external_assessment', 'extended_essay', 'tok', 'cas', 'quiz', 'test', 'project', 'participation', 'final', 'controle_continu', 'epreuve', 'observation', 'narrative', 'portfolio')")

op.execute("CREATE TYPE scoredisplaymode AS ENUM ('percentage', 'grade_only', 'grade_and_score', 'level', 'gpa', 'narrative', 'mention')")
```

### Step 2: Extend Existing Enum

```python
# ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
# Must temporarily switch to AUTOCOMMIT isolation level.
connection = op.get_bind()
connection.execution_options(isolation_level="AUTOCOMMIT")
connection.execute(text("ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'cambridge'"))
connection.execute(text("ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'edexcel'"))
connection.execute(text("ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'ib'"))
connection.execute(text("ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'french'"))
connection.execute(text("ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'narrative'"))
connection.execute(text("ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'american'"))
connection.execution_options(isolation_level="READ COMMITTED")  # restore for remaining DDL
```

**CRITICAL:** `ALTER TYPE ADD VALUE` requires PostgreSQL 9.1+ and `IF NOT EXISTS` requires PostgreSQL 12+. We use PostgreSQL 16, so this is fine. However, this statement **cannot run inside a transaction block**. The pattern above temporarily switches the connection to `AUTOCOMMIT` for the enum extension, then restores `READ COMMITTED` for the transactional table creation that follows.

### Step 3: Create Tables

Create all 4 tables in this order (respecting FK dependencies):

1. `curriculum_profiles` (no FK to other new tables)
2. `assessment_structures` (FK to `curriculum_profiles`)
3. `assessment_components` (FK to `assessment_structures`)
4. `report_card_configs` (FK to `curriculum_profiles`)

Each table must include:
- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`
- `school_id UUID REFERENCES schools(id) ON DELETE SET NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `deleted_at TIMESTAMPTZ` (for tables with `SoftDeleteMixin`: `curriculum_profiles`, `assessment_structures`, `report_card_configs`)
- Appropriate unique constraints and indexes

**Note on `curriculum_profiles` uniqueness:** Use a partial unique index instead of a table-level UNIQUE constraint to accommodate soft deletes:
```sql
CREATE UNIQUE INDEX uq_curriculum_profile_name
    ON curriculum_profiles (tenant_id, name)
    WHERE deleted_at IS NULL;
```
Do NOT use `UNIQUE (tenant_id, name)` as a table constraint — it would prevent re-creating a profile with the same name after the original is soft-deleted.

### Step 4: Add Columns to Existing Tables

```sql
-- schools
ALTER TABLE schools ADD COLUMN curriculum_profile_id UUID REFERENCES curriculum_profiles(id) ON DELETE SET NULL;
ALTER TABLE schools ADD COLUMN curriculum_settings JSONB;

-- classes
ALTER TABLE classes ADD COLUMN curriculum_profile_id UUID REFERENCES curriculum_profiles(id) ON DELETE SET NULL;

-- students
ALTER TABLE students ADD COLUMN curriculum_profile_id UUID REFERENCES curriculum_profiles(id) ON DELETE SET NULL;
ALTER TABLE students ADD COLUMN previous_curriculum_type VARCHAR(20);

-- grading_scales
ALTER TABLE grading_scales ADD COLUMN curriculum_profile_id UUID REFERENCES curriculum_profiles(id) ON DELETE SET NULL;
```

### Step 5: RLS Policies

**IMPORTANT:** Use the `rls_helpers` module — do NOT write RLS DDL inline. This ensures correct policy naming, `FORCE ROW LEVEL SECURITY`, targeting `sims_app_user` (not PUBLIC), and `GRANT` to `sims_app_user` (not `sims_admin`).

```python
from app.db.rls_helpers import enable_rls_for_table

# Apply to all 4 new tables
for table_name in [
    "curriculum_profiles",
    "assessment_structures",
    "assessment_components",
    "report_card_configs",
]:
    enable_rls_for_table(op.get_bind(), table_name)
```

This calls `enable_rls_for_table()` which:
1. Drops any existing policies
2. `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`
3. `ALTER TABLE ... FORCE ROW LEVEL SECURITY`
4. Creates `tenant_isolation_{table}` policy targeting `sims_app_user` with `USING (tenant_id = get_current_tenant_id())` and `WITH CHECK (tenant_id = get_current_tenant_id())`
5. `GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO sims_app_user`

### Step 6: Indexes

```sql
-- curriculum_profiles
CREATE INDEX ix_curriculum_profiles_tenant_id ON curriculum_profiles(tenant_id);
CREATE INDEX ix_curriculum_profiles_school_id ON curriculum_profiles(school_id);
-- Partial unique index (allows re-use of name after soft delete)
CREATE UNIQUE INDEX uq_curriculum_profile_name ON curriculum_profiles(tenant_id, name) WHERE deleted_at IS NULL;

-- assessment_structures
CREATE INDEX ix_assessment_structures_tenant_id ON assessment_structures(tenant_id);
CREATE INDEX ix_assessment_structures_profile_id ON assessment_structures(curriculum_profile_id);

-- assessment_components
CREATE INDEX ix_assessment_components_tenant_id ON assessment_components(tenant_id);
CREATE INDEX ix_assessment_components_structure_id ON assessment_components(assessment_structure_id);

-- report_card_configs
CREATE INDEX ix_report_card_configs_tenant_id ON report_card_configs(tenant_id);
CREATE INDEX ix_report_card_configs_profile_id ON report_card_configs(curriculum_profile_id);

-- New FK columns on existing tables
CREATE INDEX ix_schools_curriculum_profile_id ON schools(curriculum_profile_id);
CREATE INDEX ix_classes_curriculum_profile_id ON classes(curriculum_profile_id);
CREATE INDEX ix_students_curriculum_profile_id ON students(curriculum_profile_id);
CREATE INDEX ix_grading_scales_curriculum_profile_id ON grading_scales(curriculum_profile_id);

-- Composite indexes for common multi-tenant query patterns
CREATE INDEX ix_curriculum_profiles_tenant_school_active
    ON curriculum_profiles (tenant_id, school_id, is_active)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_curriculum_profiles_default
    ON curriculum_profiles (tenant_id, school_id)
    WHERE is_default = true AND deleted_at IS NULL;
CREATE INDEX ix_assessment_structures_tenant_profile_year
    ON assessment_structures (tenant_id, curriculum_profile_id, academic_year_id);
```

### Step 7: Grants

**NOTE:** Grants are already handled by `enable_rls_for_table()` in Step 5. No additional grant statements are needed. The helper grants `SELECT, INSERT, UPDATE, DELETE` to `sims_app_user` (the application role). Do NOT grant to `sims_admin` — that is the superuser and does not need explicit grants.

### Downgrade

```python
def downgrade():
    # Drop new columns from existing tables
    op.drop_column("grading_scales", "curriculum_profile_id")
    op.drop_column("students", "previous_curriculum_type")
    op.drop_column("students", "curriculum_profile_id")
    op.drop_column("classes", "curriculum_profile_id")
    op.drop_column("schools", "curriculum_settings")
    op.drop_column("schools", "curriculum_profile_id")

    # Drop new tables (reverse order of creation)
    op.drop_table("report_card_configs")
    op.drop_table("assessment_components")
    op.drop_table("assessment_structures")
    op.drop_table("curriculum_profiles")

    # Drop new enum types
    op.execute("DROP TYPE IF EXISTS scoredisplaymode")
    op.execute("DROP TYPE IF EXISTS assessmentcomponenttype")
    op.execute("DROP TYPE IF EXISTS curriculumtype")

    # NOTE: Cannot remove values from gradingscaletype enum.
    # The 6 new values (cambridge, edexcel, ib, french, narrative, american)
    # will remain. This is acceptable and backward-compatible.
```

---

## 1.9 Data Migration

**File:** `backend/alembic/versions/20260310_0200_curriculum_data_migration.py`

**Revision chain:** `20260310_0100` -> `20260310_0200`

This migration creates a "GES Default" curriculum profile for each existing tenant, with a matching assessment structure and components mirroring their existing `assessment_weights` configuration.

### Algorithm

```python
def upgrade():
    conn = op.get_bind()

    # Verify running as superuser (not sims_app_user which would be blocked by FORCE RLS)
    result = conn.execute(text("SELECT current_user")).scalar()
    assert result in ('postgres', 'sims_admin'), f"Migration must run as superuser, not {result}"

    # 1. Get all tenants (tenants table has no RLS)
    tenants = conn.execute(text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:
        # 2. Check if a GES Default profile already exists (idempotent)
        existing = conn.execute(
            text("""
                SELECT id FROM curriculum_profiles
                WHERE tenant_id = CAST(:tid AS uuid)
                AND name = 'GES Default'
            """),
            {"tid": str(tenant_id)},
        ).fetchone()

        if existing:
            continue

        # 3. Create GES Default curriculum profile
        profile_id = uuid.uuid4()
        conn.execute(
            text("""
                INSERT INTO curriculum_profiles
                (id, tenant_id, school_id, name, curriculum_type, academic_calendar_type,
                 periods_per_year, score_display_mode, show_position,
                 show_class_average, use_gpa, use_credits,
                 use_criterion_grading, is_default, is_active, created_at, updated_at)
                VALUES
                (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                 'GES Default', 'ges', 'terms',
                 3, 'grade_and_score', true,
                 true, false, false,
                 false, true, true, NOW(), NOW())
            """),
            {
                "id": str(profile_id),
                "tid": str(tenant_id),
                "sid": str(fallback_school_id) if fallback_school_id else None,
            },
        )

        # 4. Find the tenant's default grading scale
        default_scale = conn.execute(
            text("""
                SELECT id FROM grading_scales
                WHERE tenant_id = CAST(:tid AS uuid)
                AND is_default = true AND deleted_at IS NULL
                LIMIT 1
            """),
            {"tid": str(tenant_id)},
        ).fetchone()

        if default_scale:
            conn.execute(
                text("""
                    UPDATE curriculum_profiles
                    SET grading_scale_id = CAST(:sid AS uuid)
                    WHERE id = CAST(:pid AS uuid)
                """),
                {"sid": str(default_scale[0]), "pid": str(profile_id)},
            )

        # 5. Get existing assessment weights (include school_id for new tables)
        weights = conn.execute(
            text("""
                SELECT id, academic_year_id, class_work_weight, homework_weight,
                       midterm_weight, end_term_weight, school_id
                FROM assessment_weights
                WHERE tenant_id = CAST(:tid AS uuid)
            """),
            {"tid": str(tenant_id)},
        ).fetchall()

        # Look up a default school_id for this tenant (used when assessment_weights
        # has no school_id, or when the tenant has no assessment_weights at all).
        # For chain tenants with multiple schools, the first active school is used
        # as a fallback — the admin can reassign profiles to specific schools later.
        fallback_school = conn.execute(
            text("""
                SELECT id FROM schools
                WHERE tenant_id = CAST(:tid AS uuid)
                AND deleted_at IS NULL
                ORDER BY created_at ASC
                LIMIT 1
            """),
            {"tid": str(tenant_id)},
        ).fetchone()
        fallback_school_id = fallback_school[0] if fallback_school else None

        # 6. For each weight config, create assessment structure + components
        for weight_row in weights:
            (w_id, year_id, cw_w, hw_w, mid_w, end_w, w_school_id) = weight_row
            # Use school_id from assessment_weights if available, else fallback
            row_school_id = w_school_id or fallback_school_id
            structure_id = uuid.uuid4()

            conn.execute(
                text("""
                    INSERT INTO assessment_structures
                    (id, tenant_id, school_id, curriculum_profile_id, academic_year_id,
                     name, is_active, created_at, updated_at)
                    VALUES
                    (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                     CAST(:pid AS uuid), CAST(:yid AS uuid),
                     'GES Assessment Structure', true, NOW(), NOW())
                """),
                {
                    "id": str(structure_id),
                    "tid": str(tenant_id),
                    "sid": str(row_school_id) if row_school_id else None,
                    "pid": str(profile_id),
                    "yid": str(year_id) if year_id else None,
                },
            )

            # Create 4 components matching existing weights
            components = [
                (AssessmentComponentType.CLASS_WORK.value, "Class Work", cw_w, 1, True, False),
                (AssessmentComponentType.HOMEWORK.value, "Homework", hw_w, 2, True, False),
                (AssessmentComponentType.MIDTERM.value, "Midterm", mid_w, 3, True, False),
                (AssessmentComponentType.END_TERM.value, "End of Term", end_w, 4, False, True),
            ]

            for (ctype, cname, cweight, seq, to_ca, to_exam) in components:
                comp_id = uuid.uuid4()
                conn.execute(
                    text("""
                        INSERT INTO assessment_components
                        (id, tenant_id, school_id, assessment_structure_id, component_type,
                         name, weight, is_external, sequence,
                         maps_to_ca, maps_to_exam, created_at, updated_at)
                        VALUES
                        (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid2 AS uuid),
                         CAST(:sid AS uuid),
                         :ctype, :cname, :cweight, false, :seq,
                         :to_ca, :to_exam, NOW(), NOW())
                    """),
                    {
                        "id": str(comp_id),
                        "tid": str(tenant_id),
                        "sid2": str(row_school_id) if row_school_id else None,
                        "sid": str(structure_id),
                        "ctype": ctype,
                        "cname": cname,
                        "cweight": float(cweight),
                        "seq": seq,
                        "to_ca": to_ca,
                        "to_exam": to_exam,
                    },
                )

        # 6b. Normalize component weights using ca_total_weight/exam_total_weight.
        #     The existing AssessmentWeight has ca_total_weight (e.g., 50) and
        #     exam_total_weight (e.g., 50). The raw sub-weights (class_work=20,
        #     homework=10, midterm=20, end_term=50) are relative to each other,
        #     but the report card displays CA as ca_total_weight% and Exam as
        #     exam_total_weight%. When a school has customized these (e.g., 60/40),
        #     the migrated component weights must reflect the actual split.
        for weight_row in weights:
            (w_id, year_id, cw_w, hw_w, mid_w, end_w, w_school_id) = weight_row
            # Fetch ca_total_weight and exam_total_weight for this assessment_weights row
            totals = conn.execute(
                text("""
                    SELECT ca_total_weight, exam_total_weight
                    FROM assessment_weights
                    WHERE id = CAST(:wid AS uuid)
                """),
                {"wid": str(w_id)},
            ).fetchone()
            ca_total = float(totals[0]) if totals and totals[0] else 50.0
            exam_total = float(totals[1]) if totals and totals[1] else 50.0

            # Normalize: CA sub-weights should sum to ca_total, exam to exam_total
            ca_raw = float(cw_w or 0) + float(hw_w or 0) + float(mid_w or 0)
            if ca_raw > 0:
                # Update each CA component: weight = (sub_weight / ca_raw_sum) * ca_total_weight
                for (ctype, sub_w) in [("class_work", cw_w), ("homework", hw_w), ("midterm", mid_w)]:
                    normalized = round((float(sub_w or 0) / ca_raw) * ca_total, 2)
                    conn.execute(
                        text("""
                            UPDATE assessment_components
                            SET weight = :w
                            WHERE assessment_structure_id = (
                                SELECT id FROM assessment_structures
                                WHERE tenant_id = CAST(:tid AS uuid)
                                AND curriculum_profile_id = CAST(:pid AS uuid)
                                AND COALESCE(academic_year_id, '00000000-0000-0000-0000-000000000000')
                                    = COALESCE(CAST(:yid AS uuid), '00000000-0000-0000-0000-000000000000')
                            )
                            AND component_type = :ct
                        """),
                        {"w": normalized, "tid": str(tenant_id), "pid": str(profile_id),
                         "yid": str(year_id) if year_id else None, "ct": ctype},
                    )
            # Update exam component weight to exam_total_weight
            conn.execute(
                text("""
                    UPDATE assessment_components
                    SET weight = :w
                    WHERE assessment_structure_id = (
                        SELECT id FROM assessment_structures
                        WHERE tenant_id = CAST(:tid AS uuid)
                        AND curriculum_profile_id = CAST(:pid AS uuid)
                        AND COALESCE(academic_year_id, '00000000-0000-0000-0000-000000000000')
                            = COALESCE(CAST(:yid AS uuid), '00000000-0000-0000-0000-000000000000')
                    )
                    AND component_type = 'end_term'
                """),
                {"w": exam_total, "tid": str(tenant_id), "pid": str(profile_id),
                 "yid": str(year_id) if year_id else None},
            )

        # 6c. Create ReportCardConfig for each GES profile
        conn.execute(
            text("""
                INSERT INTO report_card_configs
                (id, tenant_id, school_id, curriculum_profile_id, template_key,
                 show_position, show_class_average, show_subject_position,
                 show_effort_grade, show_predicted_grades, show_gpa,
                 show_credits, show_honor_roll, show_learner_profile,
                 show_atl_skills, created_at, updated_at)
                VALUES
                (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                 CAST(:pid AS uuid), 'ges',
                 true, true, true,
                 false, false, false,
                 false, false, false,
                 false, NOW(), NOW())
            """),
            {
                "id": str(uuid.uuid4()),
                "tid": str(tenant_id),
                "sid": str(fallback_school_id) if fallback_school_id else None,
                "pid": str(profile_id),
            },
        )

        # 7. If tenant has no assessment_weights, create default structure
        if not weights:
            structure_id = uuid.uuid4()
            conn.execute(
                text("""
                    INSERT INTO assessment_structures
                    (id, tenant_id, school_id, curriculum_profile_id, name,
                     is_active, created_at, updated_at)
                    VALUES
                    (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                     CAST(:pid AS uuid),
                     'GES Assessment Structure', true, NOW(), NOW())
                """),
                {
                    "id": str(structure_id),
                    "tid": str(tenant_id),
                    "sid": str(fallback_school_id) if fallback_school_id else None,
                    "pid": str(profile_id),
                },
            )

            defaults = [
                ("class_work", "Class Work", 20, 1, True, False),
                ("homework", "Homework", 10, 2, True, False),
                ("midterm", "Midterm", 20, 3, True, False),
                ("end_term", "End of Term", 50, 4, False, True),
            ]
            for (ctype, cname, cweight, seq, to_ca, to_exam) in defaults:
                conn.execute(
                    text("""
                        INSERT INTO assessment_components
                        (id, tenant_id, school_id, assessment_structure_id, component_type,
                         name, weight, is_external, sequence,
                         maps_to_ca, maps_to_exam, created_at, updated_at)
                        VALUES
                        (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid2 AS uuid),
                         CAST(:sid AS uuid),
                         :ct, :cn, :cw, false, :seq, :tca, :tex, NOW(), NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()), "tid": str(tenant_id),
                        "sid2": str(fallback_school_id) if fallback_school_id else None,
                        "sid": str(structure_id), "ct": ctype, "cn": cname,
                        "cw": cweight, "seq": seq, "tca": to_ca, "tex": to_exam,
                    },
                )
```

**Important notes:**
- This migration uses raw SQL with `CAST(:param AS uuid)` for UUID parameters (project convention)
- It does NOT use `set_config('app.current_tenant_id', ...)` because it operates directly on tables with explicit tenant_id filters. RLS applies to the app user at runtime, not to migrations run by the superuser.
- It is idempotent — checks for existing "GES Default" profiles before creating.

### Downgrade

```python
def downgrade():
    conn = op.get_bind()
    # Delete all auto-created GES Default profiles and cascaded children.
    # Match by curriculum_type + is_default rather than name to avoid
    # accidentally deleting user-renamed profiles.
    conn.execute(text("""
        DELETE FROM curriculum_profiles
        WHERE curriculum_type = 'ges' AND is_default = true
    """))
```

---

## 1.10 Update Test Infrastructure

### conftest.py

Add 4 new tables to `TENANT_SCOPED_TABLES` list:

```python
# Multi-Curriculum (Phase 1)
"curriculum_profiles",
"assessment_structures",
"assessment_components",
"report_card_configs",
```

### verify_rls.py

Add the same 4 tables to the RLS verification script's table list.

### init-db.sql (if applicable)

If the test database initialization script creates RLS functions, ensure the new tables are included.
