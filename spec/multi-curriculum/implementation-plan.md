# Multi-Curriculum Support - Implementation Plan

**Author:** Solution Architect
**Date:** 2026-03-06
**Status:** Draft
**Estimated Sprints:** 3 (MC-Sprint 1, 2, 3)
**Migration Chain Head:** `20260303_0200` (applicant_accounts)

---

## 1. Architecture Overview

### 1.1 Design Philosophy

Multi-curriculum support is implemented as a **configuration layer** on top of the existing academic infrastructure rather than a parallel system. The core insight is that every curriculum ultimately produces the same artifacts -- subjects, grades, scores, and report cards -- but differs in:

1. **How assessment components are structured** (4-component GES vs N-component flexible)
2. **How grades are expressed** (A1-F9 vs A*-G vs 1-7 vs narrative)
3. **How final scores are calculated** (weighted sums vs criterion-referenced vs qualitative)
4. **How reports are formatted** (positions vs GPA vs achievement levels)

The design introduces a `curriculum_profiles` table as the central configuration entity. A curriculum profile bundles together a grading scale, an assessment structure, and report card preferences. Schools select one or more profiles, classes are assigned to profiles, and the report/score engines dispatch to the correct calculation strategy based on the active profile.

### 1.2 Integration Strategy

```
                    ┌──────────────────────┐
                    │   curriculum_profiles │  <-- NEW central config
                    │   (per school)        │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
     │ GradingScale   │ │ assessment_  │ │ report_card_     │
     │ (EXISTING,     │ │ structures   │ │ configs          │
     │  extended)     │ │ (NEW)        │ │ (NEW)            │
     └────────────────┘ └──────────────┘ └──────────────────┘
              │                │                │
              ▼                ▼                ▼
     ┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
     │ Grade          │ │ assessment_  │ │ TermReport       │
     │ (EXISTING)     │ │ components   │ │ (EXISTING,       │
     │                │ │ (NEW)        │ │  extended)       │
     └────────────────┘ └──────────────┘ └──────────────────┘
              │                │
              ▼                ▼
     ┌────────────────────────────────────────────┐
     │  Score Calculation Engine (refactored)      │
     │  - GES strategy (existing logic)            │
     │  - Cambridge/Edexcel strategy               │
     │  - American GPA strategy                    │
     │  - IB criterion strategy                    │
     │  - French mention strategy                  │
     │  - Montessori narrative strategy            │
     └────────────────────────────────────────────┘
```

### 1.3 Backward Compatibility Guarantee

Existing GES schools experience **zero behavioral change**:

- Schools without a `curriculum_profile_id` on their classes default to a system-generated "GES Default" profile
- The existing `AssessmentWeight` table continues to work; a migration creates a matching `assessment_structure` + `assessment_components` for each existing weight config
- The existing `GradingScale` / `Grade` tables are unchanged; the profile simply references them
- Report card generation detects the absence of a profile and falls back to the current GES calculation path
- No existing API contracts change; new endpoints are additive

---

## 2. New Enums

### 2.1 CurriculumType (new DB enum: `curriculumtype`)

```python
class CurriculumType(str, Enum):
    GES = "ges"                  # Ghana Education Service
    CAMBRIDGE = "cambridge"      # Cambridge International (IGCSE, A-Level)
    EDEXCEL = "edexcel"          # Pearson Edexcel (IGCSE, A-Level)
    AMERICAN = "american"        # US Common Core / AP
    IB = "ib"                    # International Baccalaureate (MYP, DP)
    FRENCH = "french"            # French Baccalaureate
    MONTESSORI = "montessori"    # Montessori (narrative-based)
    CUSTOM = "custom"            # School-defined custom curriculum
```

### 2.2 GradingScaleType (EXTEND existing DB enum: `gradingscaletype`)

Add new values to the existing enum:

```sql
ALTER TYPE gradingscaletype ADD VALUE 'cambridge';
ALTER TYPE gradingscaletype ADD VALUE 'edexcel';
ALTER TYPE gradingscaletype ADD VALUE 'ib';
ALTER TYPE gradingscaletype ADD VALUE 'french';
ALTER TYPE gradingscaletype ADD VALUE 'narrative';
ALTER TYPE gradingscaletype ADD VALUE 'american';
```

Updated Python enum:

```python
class GradingScaleType(str, Enum):
    WAEC = "waec"              # existing
    GPA = "gpa"                # existing
    PERCENTAGE = "percentage"  # existing
    CUSTOM = "custom"          # existing
    CAMBRIDGE = "cambridge"    # new
    EDEXCEL = "edexcel"        # new
    IB = "ib"                  # new
    FRENCH = "french"          # new
    NARRATIVE = "narrative"    # new (Montessori qualitative)
    AMERICAN = "american"      # new (A-F with +/-)
```

### 2.3 AssessmentComponentType (new DB enum: `assessmentcomponenttype`)

```python
class AssessmentComponentType(str, Enum):
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
    TOK = "tok"  # Theory of Knowledge
    CAS = "cas"  # Creativity, Activity, Service
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

### 2.4 ScoreDisplayMode (new DB enum: `scoredisplaymode`)

```python
class ScoreDisplayMode(str, Enum):
    PERCENTAGE = "percentage"       # 85%
    GRADE_ONLY = "grade_only"       # A*
    GRADE_AND_SCORE = "grade_and_score"  # A* (92%)
    LEVEL = "level"                 # Level 7 (IB)
    GPA = "gpa"                     # 3.85
    NARRATIVE = "narrative"         # Qualitative description only
    MENTION = "mention"             # Tres Bien (French)
```

### 2.5 ExternalExamBoard (new DB enum: `externalexamboard`)

```python
class ExternalExamBoard(str, Enum):
    WAEC = "waec"
    CAMBRIDGE_INTERNATIONAL = "cambridge_international"
    EDEXCEL = "edexcel"
    COLLEGE_BOARD = "college_board"  # SAT/AP
    IBO = "ibo"                      # IB Organization
    NONE = "none"
```

---

## 3. New Tables

### 3.1 `curriculum_profiles` -- Central Curriculum Configuration

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | For chain support |
| name | VARCHAR(100) | NOT NULL | e.g., "Cambridge IGCSE", "GES Standard" |
| curriculum_type | curriculumtype enum | NOT NULL | One of the 8 types |
| description | TEXT | nullable | |
| grading_scale_id | UUID | FK grading_scales.id, nullable | Default grading scale for this profile |
| academic_calendar_type | VARCHAR(20) | NOT NULL, default 'terms' | 'terms' (3), 'semesters' (2), 'quarters' (4) |
| periods_per_year | INTEGER | NOT NULL, default 3 | Number of terms/semesters |
| score_display_mode | scoredisplaymode enum | NOT NULL, default 'grade_and_score' | How scores appear on reports |
| show_position | BOOLEAN | NOT NULL, default true | Some curricula forbid rankings |
| show_class_average | BOOLEAN | NOT NULL, default true | |
| use_gpa | BOOLEAN | NOT NULL, default false | Calculate and display GPA |
| use_credits | BOOLEAN | NOT NULL, default false | Track credit/unit accumulation |
| use_criterion_grading | BOOLEAN | NOT NULL, default false | IB MYP criterion-referenced |
| config | JSONB | nullable | Curriculum-specific config (see below) |
| is_default | BOOLEAN | NOT NULL, default false | Default profile for this school |
| is_active | BOOLEAN | NOT NULL, default true | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |
| deleted_at | TIMESTAMPTZ | nullable | SoftDeleteMixin |

**JSONB `config` field** (curriculum-specific overrides):

```jsonc
// IB example
{
  "ib_programme": "dp",           // "myp" | "dp" | "pyp"
  "learner_profile_traits": ["inquirers", "knowledgeable", ...],
  "atl_skills": ["thinking", "communication", ...],
  "max_total_points": 45,
  "bonus_points_max": 3,          // EE + TOK bonus
  "passing_total": 24
}

// American example
{
  "gpa_scale": 4.0,
  "weighted_gpa": true,
  "honor_roll_threshold": 3.5,
  "ap_weight_bonus": 1.0,
  "honors_weight_bonus": 0.5,
  "graduation_credits_required": 24
}

// French example
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

// Montessori example
{
  "developmental_areas": ["practical_life", "sensorial", "language", "mathematics", "cultural"],
  "progress_levels": ["emerging", "developing", "proficient", "mastery"],
  "narrative_required": true
}
```

**Unique constraint:** `(tenant_id, name)` -- `uq_curriculum_profile_name`

**RLS:** Required (tenant-scoped)

### 3.2 `assessment_structures` -- Flexible Assessment Weight System

Replaces the rigid 4-column `AssessmentWeight` model with an N-component system.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| curriculum_profile_id | UUID | FK curriculum_profiles.id, NOT NULL | |
| academic_year_id | UUID | FK academic_years.id, nullable | Year-specific override; NULL = default |
| name | VARCHAR(100) | NOT NULL | e.g., "IGCSE Assessment Structure" |
| description | TEXT | nullable | |
| is_active | BOOLEAN | NOT NULL, default true | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique constraint:** `(tenant_id, curriculum_profile_id, academic_year_id)` with COALESCE for NULL academic_year_id -- `uq_assessment_structure`

**RLS:** Required

### 3.3 `assessment_components` -- Individual Weight Components

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| assessment_structure_id | UUID | FK assessment_structures.id, CASCADE | |
| component_type | assessmentcomponenttype enum | NOT NULL | |
| name | VARCHAR(100) | NOT NULL | Display name, e.g., "Coursework" |
| weight | NUMERIC(5,2) | NOT NULL | Percentage weight (must sum to 100 within structure) |
| max_score | NUMERIC(5,2) | nullable | Optional fixed max score |
| is_external | BOOLEAN | NOT NULL, default false | Externally assessed (Cambridge papers) |
| sequence | INTEGER | NOT NULL, default 1 | Display order |
| maps_to_ca | BOOLEAN | NOT NULL, default false | Maps to CA score column on report |
| maps_to_exam | BOOLEAN | NOT NULL, default false | Maps to Exam score column on report |
| config | JSONB | nullable | Component-specific config |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**RLS:** Required

**Note:** The `maps_to_ca` and `maps_to_exam` flags allow backward compatibility with the existing report card template which shows "Class Score" and "Exams Score" columns. For curricula that don't map cleanly to this split, all components can set `maps_to_ca = false, maps_to_exam = false` and the report card template renders individual component columns instead.

### 3.4 `report_card_configs` -- Curriculum-Specific Report Settings

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| curriculum_profile_id | UUID | FK curriculum_profiles.id, NOT NULL | |
| template_key | VARCHAR(50) | NOT NULL, default 'default' | Template identifier |
| show_position | BOOLEAN | NOT NULL, default true | |
| show_class_average | BOOLEAN | NOT NULL, default true | |
| show_subject_position | BOOLEAN | NOT NULL, default true | |
| show_effort_grade | BOOLEAN | NOT NULL, default false | Cambridge-style effort grades |
| show_predicted_grades | BOOLEAN | NOT NULL, default false | Cambridge/IB predicted grades |
| show_gpa | BOOLEAN | NOT NULL, default false | |
| show_credits | BOOLEAN | NOT NULL, default false | |
| show_honor_roll | BOOLEAN | NOT NULL, default false | |
| show_learner_profile | BOOLEAN | NOT NULL, default false | IB Learner Profile traits |
| show_atl_skills | BOOLEAN | NOT NULL, default false | IB ATL skills |
| custom_columns | JSONB | nullable | Additional columns for report |
| header_text | TEXT | nullable | Custom header text |
| footer_text | TEXT | nullable | Custom footer text |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique constraint:** `(tenant_id, curriculum_profile_id, template_key)` -- `uq_report_card_config`

**RLS:** Required

### 3.5 `grade_equivalencies` -- Cross-Curriculum Grade Mapping

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| source_grading_scale_id | UUID | FK grading_scales.id, NOT NULL | |
| target_grading_scale_id | UUID | FK grading_scales.id, NOT NULL | |
| source_grade_id | UUID | FK grades.id, NOT NULL | |
| target_grade_id | UUID | FK grades.id, NOT NULL | |
| notes | TEXT | nullable | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique constraint:** `(tenant_id, source_grade_id, target_grading_scale_id)` -- `uq_grade_equivalency`

**RLS:** Required

### 3.6 `subject_curriculum_mappings` -- Subject-to-Curriculum Links

Maps internal subjects to their curriculum-specific codes and names.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| subject_id | UUID | FK subjects.id, CASCADE | |
| curriculum_profile_id | UUID | FK curriculum_profiles.id, CASCADE | |
| external_code | VARCHAR(20) | nullable | e.g., "0580" for IGCSE Mathematics |
| external_name | VARCHAR(200) | nullable | Official curriculum subject name |
| level | VARCHAR(50) | nullable | e.g., "Higher", "Standard", "AP", "Honors" |
| credits | NUMERIC(4,1) | nullable | Credit value (American system) |
| coefficient | NUMERIC(4,1) | nullable | Coefficient (French system) |
| is_hl | BOOLEAN | default false | IB Higher Level flag |
| grading_scale_id | UUID | FK grading_scales.id, nullable | Subject-specific grading override |
| config | JSONB | nullable | Subject-specific curriculum config |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique constraint:** `(tenant_id, subject_id, curriculum_profile_id)` -- `uq_subject_curriculum_mapping`

**RLS:** Required

### 3.7 `external_exam_registrations` -- External Exam Tracking

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| student_id | UUID | FK students.id, CASCADE | |
| exam_board | externalexamboard enum | NOT NULL | |
| exam_session | VARCHAR(20) | NOT NULL | e.g., "May 2026", "Nov 2026" |
| candidate_number | VARCHAR(50) | nullable | Board-assigned candidate number |
| center_number | VARCHAR(20) | nullable | Exam center number |
| registration_status | VARCHAR(20) | NOT NULL, default 'pending' | pending, registered, confirmed |
| subjects | JSONB | NOT NULL | Array of {subject_code, subject_name, level, paper_numbers} |
| results | JSONB | nullable | Array of {subject_code, grade, score, date_received} |
| registration_date | DATE | nullable | |
| results_date | DATE | nullable | |
| notes | TEXT | nullable | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |
| deleted_at | TIMESTAMPTZ | nullable | SoftDeleteMixin |

**Unique constraint:** `(tenant_id, student_id, exam_board, exam_session)` -- `uq_external_exam_registration`

**RLS:** Required

### 3.8 `student_credit_accumulations` -- Credit/Unit Tracking (American/IB)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| student_id | UUID | FK students.id, CASCADE | |
| curriculum_profile_id | UUID | FK curriculum_profiles.id | |
| academic_year_id | UUID | FK academic_years.id | |
| term_id | UUID | FK terms.id, nullable | |
| subject_id | UUID | FK subjects.id | |
| credits_attempted | NUMERIC(4,1) | NOT NULL | |
| credits_earned | NUMERIC(4,1) | NOT NULL | |
| grade_points | NUMERIC(5,2) | nullable | For GPA calculation |
| weighted_grade_points | NUMERIC(5,2) | nullable | For weighted GPA |
| is_ap | BOOLEAN | default false | AP course flag |
| is_honors | BOOLEAN | default false | Honors course flag |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique constraint:** `(tenant_id, student_id, subject_id, academic_year_id, term_id)` with COALESCE for NULL term_id -- `uq_student_credit`

**RLS:** Required

### 3.9 `predicted_grades` -- Predicted/Target Grade Tracking

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK tenants.id, NOT NULL, RLS | |
| school_id | UUID | FK schools.id, nullable | |
| student_id | UUID | FK students.id, CASCADE | |
| subject_id | UUID | FK subjects.id | |
| academic_year_id | UUID | FK academic_years.id | |
| term_id | UUID | FK terms.id, nullable | |
| predicted_grade | VARCHAR(10) | nullable | Teacher-predicted grade |
| target_grade | VARCHAR(10) | nullable | Target/aspirational grade |
| predicted_score | NUMERIC(5,2) | nullable | |
| predicted_by | UUID | FK users.id, nullable | |
| predicted_at | TIMESTAMPTZ | nullable | |
| notes | TEXT | nullable | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Unique constraint:** `(tenant_id, student_id, subject_id, academic_year_id, term_id)` -- `uq_predicted_grade`

**RLS:** Required

**Summary: 9 new tables, all tenant-scoped with RLS.**

---

## 4. Modified Tables

### 4.1 `schools` -- Add curriculum_profile_id

| Column | Change | Details |
|--------|--------|---------|
| curriculum_profile_id | ADD | `UUID FK curriculum_profiles.id, nullable` -- school's default curriculum |
| curriculum_settings | ADD | `JSONB, nullable` -- school-level curriculum overrides |

### 4.2 `classes` -- Add curriculum_profile_id

| Column | Change | Details |
|--------|--------|---------|
| curriculum_profile_id | ADD | `UUID FK curriculum_profiles.id, nullable` -- class-level override (for dual-track schools) |

This enables dual-track schools: SHS 2 Science Stream could use Cambridge IGCSE while SHS 2 Arts Stream uses GES.

### 4.3 `students` -- Add curriculum tracking

| Column | Change | Details |
|--------|--------|---------|
| curriculum_profile_id | ADD | `UUID FK curriculum_profiles.id, nullable` -- student's current curriculum (inherited from class if NULL) |
| previous_curriculum_type | ADD | `VARCHAR(20), nullable` -- for transfer students, records origin curriculum |

### 4.4 `grading_scales` -- Add curriculum_profile_id

| Column | Change | Details |
|--------|--------|---------|
| curriculum_profile_id | ADD | `UUID FK curriculum_profiles.id, nullable` -- links scale to a curriculum (existing unlinked scales remain usable by all) |

### 4.5 `term_reports` -- Add curriculum fields

| Column | Change | Details |
|--------|--------|---------|
| curriculum_profile_id | ADD | `UUID FK curriculum_profiles.id, nullable` -- which curriculum was used to generate this report |
| gpa | ADD | `NUMERIC(4,2), nullable` -- term GPA (American, IB) |
| weighted_gpa | ADD | `NUMERIC(4,2), nullable` -- weighted GPA |
| cumulative_gpa | ADD | `NUMERIC(4,2), nullable` -- cumulative across terms |
| total_credits_earned | ADD | `NUMERIC(5,1), nullable` -- credits earned this term |
| cumulative_credits | ADD | `NUMERIC(5,1), nullable` -- total credits to date |
| honor_roll | ADD | `BOOLEAN, nullable` -- honor roll status |
| ib_total_points | ADD | `INTEGER, nullable` -- IB total points (out of 45) |
| french_mention | ADD | `VARCHAR(20), nullable` -- French mention category |
| extra_data | ADD | `JSONB, nullable` -- curriculum-specific report data |

### 4.6 `exam_scores` -- Add predicted grade

| Column | Change | Details |
|--------|--------|---------|
| effort_grade | ADD | `VARCHAR(5), nullable` -- Cambridge effort grade (1-5 or A-E) |

### 4.7 `subjects` -- Add curriculum awareness

| Column | Change | Details |
|--------|--------|---------|
| credit_value | ADD | `NUMERIC(4,1), nullable` -- default credits for American system |
| coefficient | ADD | `NUMERIC(4,1), nullable` -- default coefficient for French system |

### 4.8 `assessment_weights` -- No structural change

The existing `assessment_weights` table is NOT removed. It continues to work as-is for GES schools. The new `assessment_structures` + `assessment_components` system is used when a curriculum profile is active. The score calculation engine checks for a curriculum profile first; if none, it falls back to `assessment_weights`.

---

## 5. RLS Policies

All 9 new tables use the canonical `rls_helpers.enable_rls_for_table()` helper — do NOT write inline RLS DDL.

```python
from app.db.rls_helpers import enable_rls_for_table

for table_name in [
    "curriculum_profiles",
    "assessment_structures",
    "assessment_components",
    "report_card_configs",
    "grade_equivalencies",
    "subject_curriculum_mappings",
    "external_exam_registrations",
    "student_credit_accumulations",
    "predicted_grades",
]:
    enable_rls_for_table(op.get_bind(), table_name)
```

This handles: ENABLE/FORCE RLS, creates `tenant_isolation_{table}` policy targeting `sims_app_user` (not PUBLIC), with `USING` and `WITH CHECK` on `get_current_tenant_id()`, and grants `SELECT, INSERT, UPDATE, DELETE` to `sims_app_user`.

---

## 6. API Endpoints

### 6.1 Curriculum Profile Management

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| POST | `/api/v1/curriculum/profiles` | Create curriculum profile | school_admin | 100/min |
| GET | `/api/v1/curriculum/profiles` | List profiles (with filters) | authenticated | 100/min |
| GET | `/api/v1/curriculum/profiles/{id}` | Get profile with details | authenticated | 100/min |
| PUT | `/api/v1/curriculum/profiles/{id}` | Update profile | school_admin | 100/min |
| DELETE | `/api/v1/curriculum/profiles/{id}` | Soft delete profile | school_admin | 100/min |
| POST | `/api/v1/curriculum/profiles/{id}/set-default` | Set as school default | school_admin | 100/min |
| GET | `/api/v1/curriculum/profiles/templates` | Get built-in templates | authenticated | 100/min |
| POST | `/api/v1/curriculum/profiles/from-template` | Create from built-in template | school_admin | 100/min |

### 6.2 Assessment Structure Management

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| POST | `/api/v1/curriculum/profiles/{id}/assessment-structure` | Create assessment structure | school_admin | 100/min |
| GET | `/api/v1/curriculum/profiles/{id}/assessment-structure` | Get structure with components | authenticated | 100/min |
| PUT | `/api/v1/curriculum/assessment-structures/{id}` | Update structure | school_admin | 100/min |
| POST | `/api/v1/curriculum/assessment-structures/{id}/components` | Add component | school_admin | 100/min |
| PUT | `/api/v1/curriculum/assessment-components/{id}` | Update component | school_admin | 100/min |
| DELETE | `/api/v1/curriculum/assessment-components/{id}` | Remove component | school_admin | 100/min |
| POST | `/api/v1/curriculum/assessment-structures/{id}/validate` | Validate weights sum to 100 | school_admin | 100/min |

### 6.3 Report Card Configuration

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| GET | `/api/v1/curriculum/profiles/{id}/report-config` | Get report config | authenticated | 100/min |
| PUT | `/api/v1/curriculum/profiles/{id}/report-config` | Update report config | school_admin | 100/min |

### 6.4 Grade Equivalencies

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| POST | `/api/v1/curriculum/grade-equivalencies` | Create mapping | school_admin | 100/min |
| GET | `/api/v1/curriculum/grade-equivalencies` | List mappings | authenticated | 100/min |
| GET | `/api/v1/curriculum/grade-equivalencies/convert` | Convert a grade between scales | authenticated | 100/min |
| DELETE | `/api/v1/curriculum/grade-equivalencies/{id}` | Remove mapping | school_admin | 100/min |

### 6.5 Subject Curriculum Mappings

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| POST | `/api/v1/curriculum/subject-mappings` | Map subject to curriculum | school_admin | 100/min |
| GET | `/api/v1/curriculum/subject-mappings` | List mappings (filter by profile) | authenticated | 100/min |
| PUT | `/api/v1/curriculum/subject-mappings/{id}` | Update mapping | school_admin | 100/min |
| DELETE | `/api/v1/curriculum/subject-mappings/{id}` | Remove mapping | school_admin | 100/min |
| POST | `/api/v1/curriculum/subject-mappings/bulk` | Bulk create/update mappings | school_admin | 10/min |

### 6.6 External Examinations

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| POST | `/api/v1/curriculum/external-exams/registrations` | Register students for external exam | school_admin | 100/min |
| GET | `/api/v1/curriculum/external-exams/registrations` | List registrations (filter by board, session) | authenticated | 100/min |
| GET | `/api/v1/curriculum/external-exams/registrations/{id}` | Get registration detail | authenticated | 100/min |
| PUT | `/api/v1/curriculum/external-exams/registrations/{id}` | Update registration | school_admin | 100/min |
| POST | `/api/v1/curriculum/external-exams/registrations/bulk` | Bulk register students | school_admin | 10/min |
| POST | `/api/v1/curriculum/external-exams/results/import` | Import external results (CSV/JSON) | school_admin | 10/min |
| GET | `/api/v1/curriculum/external-exams/export/waec` | Export WAEC registration data | school_admin | 5/min |
| GET | `/api/v1/curriculum/external-exams/export/cambridge` | Export Cambridge registration data | school_admin | 5/min |

### 6.7 Credits and GPA

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| GET | `/api/v1/curriculum/credits/student/{student_id}` | Get student credit summary | authenticated | 100/min |
| GET | `/api/v1/curriculum/credits/student/{student_id}/transcript` | Generate transcript data | authenticated | 100/min |
| GET | `/api/v1/curriculum/gpa/student/{student_id}` | Get student GPA (term + cumulative) | authenticated | 100/min |
| POST | `/api/v1/curriculum/credits/recalculate/{student_id}` | Recalculate credits for student | school_admin | 10/min |

### 6.8 Predicted Grades

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| POST | `/api/v1/curriculum/predicted-grades` | Set predicted grade | teacher | 100/min |
| GET | `/api/v1/curriculum/predicted-grades` | List predicted grades (filter by student/class/subject) | authenticated | 100/min |
| PUT | `/api/v1/curriculum/predicted-grades/{id}` | Update predicted grade | teacher | 100/min |
| POST | `/api/v1/curriculum/predicted-grades/bulk` | Bulk set predicted grades | teacher | 10/min |

**Total: ~38 new endpoints across 8 groups.**

---

## 7. Key Request/Response Schemas

### 7.1 CurriculumProfileCreate

```python
class CurriculumProfileCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    curriculum_type: str = Field(..., pattern="^(ges|cambridge|edexcel|american|ib|french|montessori|custom)$")
    description: Optional[str] = None
    grading_scale_id: Optional[UUID] = None
    academic_calendar_type: str = Field(default="terms", pattern="^(terms|semesters|quarters)$")
    periods_per_year: int = Field(default=3, ge=1, le=6)
    score_display_mode: str = Field(default="grade_and_score")
    show_position: bool = True
    show_class_average: bool = True
    use_gpa: bool = False
    use_credits: bool = False
    use_criterion_grading: bool = False
    config: Optional[dict] = None
    is_default: bool = False
```

### 7.2 CurriculumProfileResponse

```python
class CurriculumProfileResponse(BaseSchema):
    id: UUID
    name: str
    curriculum_type: str
    description: Optional[str] = None
    grading_scale_id: Optional[UUID] = None
    grading_scale_name: Optional[str] = None
    academic_calendar_type: str
    periods_per_year: int
    score_display_mode: str
    show_position: bool
    show_class_average: bool
    use_gpa: bool
    use_credits: bool
    use_criterion_grading: bool
    config: Optional[dict] = None
    is_default: bool
    is_active: bool
    assessment_structure: Optional["AssessmentStructureResponse"] = None
    report_config: Optional["ReportCardConfigResponse"] = None
    created_at: datetime
    updated_at: datetime
```

### 7.3 AssessmentStructureWithComponents

```python
class AssessmentComponentCreate(BaseSchema):
    component_type: str
    name: str = Field(..., min_length=1, max_length=100)
    weight: Decimal = Field(..., ge=0, le=100)
    max_score: Optional[Decimal] = None
    is_external: bool = False
    sequence: int = Field(default=1, ge=1)
    maps_to_ca: bool = False
    maps_to_exam: bool = False

class AssessmentStructureCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    academic_year_id: Optional[UUID] = None
    components: list[AssessmentComponentCreate] = []

    @field_validator("components")
    @classmethod
    def validate_weights_sum(cls, v):
        if v:
            total = sum(c.weight for c in v)
            if total != Decimal("100"):
                raise ValueError(f"Component weights must sum to 100, got {total}")
        return v
```

---

## 8. Score Calculation Engine Refactor

### 8.1 Strategy Pattern

The existing monolithic score calculation in `TermReportService.calculate_student_term_scores` and `get_student_subject_results` is refactored into a strategy dispatcher:

```python
# services/exam/score_strategies.py

class ScoreStrategy(ABC):
    """Base class for curriculum-specific score calculation."""

    @abstractmethod
    async def calculate_subject_score(
        self, scores: dict, components: list[AssessmentComponent]
    ) -> dict:
        """Calculate final subject score from component scores."""
        ...

    @abstractmethod
    def calculate_grade(self, score: Decimal, grades: list[Grade]) -> dict:
        """Determine grade from score."""
        ...


class GESScoreStrategy(ScoreStrategy):
    """GES: CA + Exam weighted calculation (existing logic, extracted)."""
    ...

class CambridgeScoreStrategy(ScoreStrategy):
    """Cambridge: Component-based with external exam integration."""
    ...

class AmericanScoreStrategy(ScoreStrategy):
    """American: Points-based with GPA calculation."""
    ...

class IBScoreStrategy(ScoreStrategy):
    """IB: 1-7 levels with criterion bands."""
    ...

class FrenchScoreStrategy(ScoreStrategy):
    """French: 0-20 with coefficients and mention calculation."""
    ...

class MontessoriScoreStrategy(ScoreStrategy):
    """Montessori: Narrative/qualitative assessment."""
    ...


def get_score_strategy(curriculum_type: CurriculumType) -> ScoreStrategy:
    """Factory function for score strategies."""
    strategies = {
        CurriculumType.GES: GESScoreStrategy,
        CurriculumType.CAMBRIDGE: CambridgeScoreStrategy,
        CurriculumType.EDEXCEL: CambridgeScoreStrategy,  # shares logic
        CurriculumType.AMERICAN: AmericanScoreStrategy,
        CurriculumType.IB: IBScoreStrategy,
        CurriculumType.FRENCH: FrenchScoreStrategy,
        CurriculumType.MONTESSORI: MontessoriScoreStrategy,
        CurriculumType.CUSTOM: GESScoreStrategy,  # custom defaults to GES
    }
    return strategies.get(curriculum_type, GESScoreStrategy)()
```

### 8.2 Backward Compatibility in Report Service

```python
async def get_student_subject_results(self, ...):
    # Resolve curriculum profile
    profile = await self._resolve_curriculum_profile(tenant_id, class_id)

    if profile is None:
        # NO CURRICULUM PROFILE -- use existing GES logic unchanged
        return await self._get_student_subject_results_ges(...)

    # Has curriculum profile -- use strategy pattern
    strategy = get_score_strategy(profile.curriculum_type)
    structure = await self._get_assessment_structure(profile.id, academic_year_id)
    return await self._get_student_subject_results_curriculum(
        strategy, structure, profile, ...
    )
```

---

## 9. Report Card Template Architecture

### 9.1 Template Selection

```python
# services/exam/report_service.py

REPORT_TEMPLATES = {
    "ges": "reports/term_report.html",              # existing
    "cambridge": "reports/cambridge_report.html",    # new
    "american": "reports/american_report.html",      # new
    "ib": "reports/ib_report.html",                  # new
    "french": "reports/french_report.html",          # new
    "montessori": "reports/montessori_report.html",  # new
    "default": "reports/term_report.html",           # fallback
}
```

### 9.2 Template Data Model

Each template receives a `ReportContext` dataclass with curriculum-aware fields:

```python
@dataclass
class ReportContext:
    # Universal fields (all templates)
    student: StudentData
    school: SchoolData
    term: TermData
    subjects: list[SubjectResult]
    attendance: AttendanceData
    remarks: RemarksData

    # Curriculum-specific (None if not applicable)
    gpa: Optional[GPAData] = None
    credits: Optional[CreditsData] = None
    ib_data: Optional[IBData] = None
    french_data: Optional[FrenchData] = None
    montessori_data: Optional[MontessoriData] = None
    predicted_grades: Optional[dict] = None
    effort_grades: Optional[dict] = None
```

---

## 10. Built-in Curriculum Templates

The system ships with pre-built templates that schools can instantiate. These are NOT stored in the database -- they are code constants that create `curriculum_profiles` + `assessment_structures` + `assessment_components` + `report_card_configs` when selected.

### 10.1 Templates

| Template | Grading Scale | Components | Calendar |
|----------|--------------|------------|----------|
| GES Standard | WAEC (A1-F9) | Class Work 20%, Homework 10%, Midterm 20%, End Term 50% | 3 terms |
| Cambridge IGCSE | Cambridge (A*-G) | Coursework 25%, Controlled Assessment 25%, External Exam 50% | 3 terms |
| Cambridge A-Level | Cambridge (A*-E) | Coursework 20%, External Exam 80% | 3 terms |
| Edexcel IGCSE | Edexcel (9-1) | Coursework 25%, External Exam 75% | 3 terms |
| American Standard | American (A-F) | Homework 15%, Quizzes 15%, Tests 25%, Projects 15%, Final 30% | 2 semesters |
| American AP | American (1-5) | Participation 10%, Homework 15%, Tests 25%, Projects 20%, Final 30% | 2 semesters |
| IB MYP | IB (1-7) | Internal Assessment 100% (criterion-based) | 2 semesters |
| IB DP | IB (1-7) | Internal Assessment 20-30%, External Assessment 70-80% | 2 semesters |
| French Bac | French (0-20) | Controle Continu 40%, Epreuve 60% | 3 terms |
| Montessori | Narrative | Observation 40%, Portfolio 30%, Narrative 30% | 3 terms |

---

## 11. Frontend Architecture

### 11.1 New Pages

```
app/(dashboard)/settings/curriculum/
    page.tsx                          # Curriculum settings overview
    profiles/
        page.tsx                      # List curriculum profiles
        new/page.tsx                  # Create profile (wizard)
        [id]/page.tsx                 # Edit profile details
        [id]/assessment/page.tsx      # Assessment structure editor
        [id]/report-config/page.tsx   # Report card configuration
    grade-equivalencies/page.tsx      # Grade mapping tool
    subject-mappings/page.tsx         # Subject-to-curriculum mapping

app/(dashboard)/exams/
    external/
        page.tsx                      # External exam registrations
        register/page.tsx             # New registration form
        results/page.tsx              # Import external results
        export/page.tsx               # Export registration data (WAEC, Cambridge)

app/(dashboard)/students/
    [id]/transcript/page.tsx          # Student transcript view
    [id]/credits/page.tsx             # Credit accumulation view
```

### 11.2 New Server Actions

```
actions/curriculum.action.ts         # Curriculum profile CRUD
actions/assessment-structure.action.ts  # Assessment structure management
actions/external-exams.action.ts      # External exam management
actions/credits.action.ts            # Credit/GPA queries
actions/predicted-grades.action.ts   # Predicted grades
```

### 11.3 Key Components

```
components/curriculum/
    CurriculumProfileWizard.tsx      # Step-by-step profile creation
    AssessmentStructureEditor.tsx     # Drag-and-drop weight editor
    ReportCardPreview.tsx            # Live preview of report card
    GradeEquivalencyMatrix.tsx       # Visual grade mapping grid
    SubjectMappingTable.tsx          # Bulk subject mapping
    CurriculumSelector.tsx           # Dropdown for selecting profile
    TemplateSelector.tsx             # Built-in template chooser
```

---

## 12. Sprint Breakdown

### MC-Sprint 1: Foundation (Curriculum Profiles + Assessment Structures)

**Goal:** Schools can create and configure curriculum profiles with flexible assessment structures. Classes can be assigned to profiles. Existing GES behavior unchanged.

**Database:**
- Migration: Create `curriculum_profiles`, `assessment_structures`, `assessment_components`, `report_card_configs` tables with RLS
- Migration: Add `curriculum_profile_id` to `schools`, `classes`, `students`
- Migration: Extend `gradingscaletype` enum with new values
- Migration: Create `curriculumtype`, `assessmentcomponenttype`, `scoredisplaymode` enums
- Migration: Seed built-in curriculum templates as code constants (NOT database rows)
- Migration: For each existing `assessment_weights` row, create a corresponding `assessment_structure` + `assessment_components` linked to an auto-generated "GES Default" curriculum profile per tenant (data migration)

**Backend:**
- Models: `CurriculumProfile`, `AssessmentStructure`, `AssessmentComponent`, `ReportCardConfig`
- Enums: `CurriculumType`, `AssessmentComponentType`, `ScoreDisplayMode`
- Schemas: ~20 Pydantic schemas for profile/structure/component CRUD
- Service: `CurriculumService` class with profile CRUD, template instantiation, assessment structure management
- Endpoints: Profile CRUD (8), Assessment Structure CRUD (7), Report Config (2) = 17 endpoints
- Modify `ClassService` to accept `curriculum_profile_id` on class create/update
- Add `_resolve_curriculum_profile(tenant_id, class_id)` helper to `TermReportService`

**Frontend:**
- Curriculum settings page with profile list
- Profile creation wizard (template selection -> customize -> review)
- Assessment structure editor (add/remove/reorder components, validate weights)
- Class curriculum assignment in class edit form
- CurriculumSelector component for class forms

**Tests:**
- Profile CRUD + RLS isolation
- Assessment structure weight validation (must sum to 100)
- Template instantiation creates correct components
- Backward compatibility: existing GES schools work without profiles
- Class curriculum_profile_id assignment

**Deliverables:** 4 new tables, 17 endpoints, profile wizard UI, class assignment

---

### MC-Sprint 2: Grading, Score Engine, and Report Cards

**Goal:** Score calculation engine supports all curriculum types. Report cards render curriculum-specific templates. Grade equivalencies work.

**Database:**
- Migration: Create `grade_equivalencies`, `subject_curriculum_mappings` tables with RLS
- Migration: Add `curriculum_profile_id` to `grading_scales`
- Migration: Add `effort_grade` to `exam_scores`
- Migration: Add curriculum fields to `term_reports` (gpa, weighted_gpa, cumulative_gpa, total_credits_earned, cumulative_credits, honor_roll, ib_total_points, french_mention, extra_data)
- Migration: Add `credit_value`, `coefficient` to `subjects`
- Migration: Create built-in grading scales for Cambridge (A*-G, A*-E), American (A-F with +/-), IB (1-7), French (0-20), Narrative per tenant (data migration, conditional: only for tenants that have a non-GES profile)

**Backend:**
- Score strategies: `GESScoreStrategy`, `CambridgeScoreStrategy`, `AmericanScoreStrategy`, `IBScoreStrategy`, `FrenchScoreStrategy`, `MontessoriScoreStrategy`
- Strategy factory: `get_score_strategy()`
- Refactor `TermReportService.get_student_subject_results` to dispatch to strategy
- Refactor `TermReportService.calculate_student_term_scores` to use strategy
- Add GPA calculation methods to `AmericanScoreStrategy`
- Grade equivalency service and endpoints (4)
- Subject curriculum mapping service and endpoints (5)
- New report card HTML templates: cambridge, american, ib, french, montessori
- Template selection logic in PDF service

**Frontend:**
- Grade equivalency matrix editor
- Subject mapping bulk editor
- Report card preview with curriculum-specific rendering
- Effort grade column in score entry (when Cambridge profile active)
- Updated report card viewer to handle all template types

**Tests:**
- Each score strategy produces correct calculations
- GES strategy matches existing behavior exactly (regression test)
- Grade equivalency conversion accuracy
- Report card PDF renders correctly for each curriculum
- Subject mapping uniqueness constraints
- Multi-curriculum school: different classes produce different report formats

**Deliverables:** 2 new tables, 9 endpoints, 5 report templates, score engine refactor

---

### MC-Sprint 3: External Exams, Credits, Transcripts, and Predicted Grades

**Goal:** External exam registration and results tracking. Credit accumulation and transcript generation. Predicted grades for Cambridge/IB schools.

**Database:**
- Migration: Create `external_exam_registrations`, `student_credit_accumulations`, `predicted_grades` tables with RLS
- Migration: Create `externalexamboard` enum

**Backend:**
- Models: `ExternalExamRegistration`, `StudentCreditAccumulation`, `PredictedGrade`
- External exam service: registration CRUD, bulk registration, results import (CSV parser), WAEC export, Cambridge export
- Credit service: accumulation tracking, GPA calculation, transcript data generation
- Predicted grade service: CRUD, bulk set
- Endpoints: External Exams (8), Credits/GPA (4), Predicted Grades (4) = 16 endpoints
- CSV import parser for external results (WAEC format, Cambridge format)
- Transcript PDF template

**Frontend:**
- External exam registration page (single + bulk)
- External results import wizard (upload CSV, preview, confirm)
- WAEC/Cambridge export download buttons
- Student transcript page with cumulative GPA and credit summary
- Predicted grades entry (integrated into teacher score entry view)
- Student credit progress dashboard

**Tests:**
- External exam registration CRUD + RLS
- Bulk registration with validation
- CSV results import parsing and error handling
- Credit accumulation calculation accuracy
- GPA calculation (weighted and unweighted)
- Transcript data generation
- Predicted grade CRUD + teacher permission checks

**Deliverables:** 3 new tables, 16 endpoints, transcript template, external exam workflows

---

## 13. Migration Strategy

### 13.1 Migration Sequence

```
20260310_0100_curriculum_foundation.py
    - Create enums: curriculumtype, assessmentcomponenttype, scoredisplaymode
    - Extend gradingscaletype enum (ADD VALUE for cambridge, edexcel, ib, french, narrative, american)
    - Create tables: curriculum_profiles, assessment_structures, assessment_components, report_card_configs
    - Add columns: schools.curriculum_profile_id, classes.curriculum_profile_id, students.curriculum_profile_id, students.previous_curriculum_type
    - RLS policies on all 4 new tables
    - Indexes on tenant_id, school_id, curriculum_profile_id columns

20260310_0200_curriculum_data_migration.py
    - For each tenant: create a "GES Default" curriculum_profile (curriculum_type=ges)
    - For each existing assessment_weights row: create matching assessment_structure + assessment_components
    - Link the default grading_scale to the GES profile
    - Set schools.curriculum_profile_id to the GES profile (optional, can remain NULL)

20260315_0100_grading_and_equivalencies.py
    - Create tables: grade_equivalencies, subject_curriculum_mappings
    - Add columns: grading_scales.curriculum_profile_id, exam_scores.effort_grade
    - Add columns to term_reports: gpa, weighted_gpa, cumulative_gpa, total_credits_earned, cumulative_credits, honor_roll, ib_total_points, french_mention, extra_data
    - Add columns to subjects: credit_value, coefficient
    - RLS policies on 2 new tables

20260320_0100_external_exams_and_credits.py
    - Create enum: externalexamboard
    - Create tables: external_exam_registrations, student_credit_accumulations, predicted_grades
    - RLS policies on 3 new tables
```

### 13.2 Data Migration Details

The data migration in `20260310_0200` is critical. It must:

1. Query all tenants (using unscoped connection, since tenants table has no RLS)
2. For each tenant, set the tenant context via `set_config('app.current_tenant_id', ...)`
3. Create a `curriculum_profiles` row with `curriculum_type = 'ges'`, `name = 'GES Default'`, `is_default = true`
4. Query `assessment_weights` for this tenant
5. For each weight row, create an `assessment_structure` linked to the profile and year
6. Create 4 `assessment_components`: class_work, homework, midterm, end_term with matching weights
7. Set the `maps_to_ca` flag on class_work and homework components, `maps_to_exam` on end_term

This migration is **idempotent** -- it checks for existing "GES Default" profiles before creating.

### 13.3 Rollback Strategy

- All new tables can be dropped without affecting existing data
- New columns on existing tables are all nullable with no defaults that affect behavior
- The `ALTER TYPE ADD VALUE` for enum extension is NOT transactional in PostgreSQL and CANNOT be rolled back. This is acceptable because adding values to an enum is backward-compatible (existing code never encounters the new values unless new profiles are created).

---

## 14. Multi-Tenancy Considerations

### 14.1 Tenant Isolation

- All 9 new tables include `tenant_id` with RLS policies
- Defense-in-depth: all service queries filter `.filter(Model.tenant_id == tenant_id)`
- Curriculum profiles are tenant-scoped; no cross-tenant sharing of profiles
- Built-in templates are code constants instantiated per-tenant

### 14.2 Cache Key Scoping

```python
# Cache patterns for curriculum data
CacheKeys.curriculum_profile(tenant_id, profile_id) -> f"curriculum:profile:{tenant_id}:{profile_id}"
CacheKeys.curriculum_profiles_list(tenant_id) -> f"curriculum:profiles:{tenant_id}"
CacheKeys.assessment_structure(tenant_id, structure_id) -> f"curriculum:structure:{tenant_id}:{structure_id}"
```

TTL: 600s (10 minutes), same as tenant lookup cache.

### 14.3 Feature Flag Gating

Multi-curriculum is gated by subscription tier:

| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| GES curriculum (default) | Yes | Yes | Yes |
| Single non-GES curriculum | No | Yes | Yes |
| Multiple curricula (dual-track) | No | No | Yes |
| External exam management | No | Yes | Yes |
| Transcript generation | No | Yes | Yes |
| Grade equivalencies | No | No | Yes |

Check in the `tenant.features` JSONB:

```python
# Features JSONB additions
{
    "multi_curriculum": false,       # Starter
    "multi_curriculum": true,        # Professional (1 non-GES profile)
    "multi_curriculum_dual": true,   # Enterprise (multiple profiles)
    "external_exams": true,          # Professional+
    "transcripts": true,             # Professional+
}
```

### 14.4 School Chain Considerations

- Each school in a chain can have its own curriculum profile
- Chain admin can see all profiles across schools
- The `school_id` column on curriculum tables enables per-school configuration
- A chain could have School A using GES and School B using Cambridge

---

## 15. Security Considerations

### 15.1 Authorization

- Curriculum profile CRUD: `school_admin`, `chain_admin`, `platform_admin`
- Assessment structure: `school_admin`+
- Score entry with effort grades: `teacher` (same as existing score entry)
- Predicted grades: `teacher` (for their assigned subjects only)
- External exam registration: `school_admin`+
- Grade viewing: role-based (same as existing report card access)
- Transcript generation: `school_admin` + `academic_head`

### 15.2 Input Validation

- Assessment component weights MUST sum to exactly 100.00 (server-side validation)
- Curriculum profile `config` JSONB validated against curriculum-type-specific JSON schemas
- External exam `subjects` JSONB validated for required fields
- Grade equivalency: source and target scales must belong to same tenant
- IDOR: verify curriculum_profile belongs to tenant before any operation

### 15.3 Audit Logging

- Curriculum profile create/update/delete logged via existing `AuditService`
- Assessment structure changes logged
- External exam results import logged (who imported, how many records, timestamp)
- Grade equivalency changes logged
- Score strategy changes (if a class switches curriculum) logged

### 15.4 Data Integrity

- Changing a class's curriculum_profile_id after scores exist: WARN but allow (scores remain, recalculation needed)
- Deleting a curriculum profile: soft delete only; block if any classes currently reference it
- Removing an assessment component: block if scores exist for that component type in the current term

---

## 16. Performance Considerations

### 16.1 Query Patterns

- `_resolve_curriculum_profile()`: Called on every report generation. Uses 2 queries max (class -> school fallback). Cache result for the request lifecycle.
- Assessment structure + components: Loaded together with `selectinload(AssessmentStructure.components)`. Cached per tenant+profile+year.
- Score calculation: The strategy pattern adds one extra query (load profile) but the actual score queries remain the same count.

### 16.2 Bulk Operations

- Template instantiation: creates 1 profile + 1 structure + N components in a single flush
- Subject mapping bulk endpoint: batch insert/upsert up to 200 mappings
- External exam bulk registration: up to 200 students per request
- External results import: CSV parser processes up to 1000 rows; larger files use Celery task

### 16.3 Report Card Generation

- Profile resolution is cached per class for the batch generation run
- Strategy objects are stateless singletons (no per-request instantiation cost)
- Template selection is a dict lookup (O(1))

---

## 17. Risk Assessment

### 17.1 High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Score calculation regression for GES schools | Critical -- incorrect report cards | Exhaustive regression test suite; GES path is the ELSE branch (unchanged code path); canary deployment with side-by-side score comparison |
| `ALTER TYPE ADD VALUE` is irreversible | Low -- cannot roll back enum extension | Acceptable; adding values is backward-compatible; only creates risk if we need to REMOVE a value later (which we won't) |
| Assessment weight migration creates incorrect components | Medium -- wrong score calculations for GES schools using new path | Migration is optional for GES; existing `assessment_weights` remains the primary source; new path only activates when profile is explicitly assigned |

### 17.2 Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dual-track class assignment complexity | Medium -- teacher/parent confusion | Clear UI labeling; validation that a student's curriculum matches their class's curriculum; prevent mismatch at enrollment |
| Report card template proliferation | Medium -- maintenance burden | Shared Jinja2 macros for common sections (header, footer, attendance); only curriculum-specific sections differ |
| External exam result import parsing failures | Medium -- data quality | Preview mode before commit; validation with clear error messages; row-level error reporting |

### 17.3 Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Montessori narrative reports require free-text | Low -- different UX pattern | Observation module already exists (preschool); extend with narrative input fields |
| IB criterion-based grading is complex | Low -- only for IB schools | JSONB `config` on profile holds criterion definitions; UI builds rubric entry from config |
| Grade equivalency accuracy | Low -- advisory feature | Mark as "approximate" in UI; allow school to customize all mappings |

---

## 18. Testing Strategy

### 18.1 Unit Tests

- Each `ScoreStrategy` class tested independently with known inputs/outputs
- GES strategy regression: compare output against current `calculate_student_term_scores` for identical inputs
- Assessment component weight validation (sum to 100, no negatives, no > 100 individual)
- Template instantiation creates correct number of components with correct weights
- GPA calculation: 4.0 scale, weighted, cumulative

### 18.2 Integration Tests

- Full report generation flow for each curriculum type
- Class with curriculum profile -> score entry -> report generation -> PDF output
- Dual-track school: two classes with different profiles, verify correct template selection
- External exam registration -> result import -> display on student profile
- Credit accumulation across terms -> transcript generation

### 18.3 Multi-Tenant Tests

- RLS verification for all 9 new tables (same pattern as existing `test_admissions_rls.py`)
- Cross-tenant profile access blocked
- Curriculum profile created in tenant A not visible in tenant B

### 18.4 Backward Compatibility Tests

- Tenant with no curriculum profiles: all existing behavior unchanged
- Tenant with GES profile: identical scores as without profile
- Existing `assessment_weights` endpoint continues to work
- Existing report card generation produces identical PDF
- Existing grading scale CRUD unaffected

---

## 19. Open Questions

1. **Montessori observation integration:** Should Montessori narrative assessments reuse the existing preschool `student_observations` model, or create a separate `narrative_assessments` table? The preschool module is already scoped to developmental domains; Montessori for older students may need different categories. **Recommendation:** Reuse preschool observations for preschool Montessori; create curriculum-specific JSONB entries in `exam_scores.teacher_remark` for older students.

2. **IB CAS tracking depth:** The IB Creativity-Activity-Service component requires hours logging and reflection. Is a lightweight tracker (hours + description) sufficient, or do we need a full CAS portfolio module? **Recommendation:** Start with hours + description in `assessment_components.config` JSONB; defer full portfolio to a future sprint.

3. **External exam result format:** WAEC and Cambridge publish results in specific formats. Do we have sample files to build parsers against? **Action needed:** Obtain sample WAEC BECE/WASSCE result files and Cambridge Statement of Results for parser development.

4. **French coefficient system:** Should coefficients multiply the score before averaging (true French system) or multiply the weight in our component system? **Recommendation:** Store coefficient on `subject_curriculum_mappings.coefficient`; the French strategy multiplies `score * coefficient` before averaging, matching the authentic system.

5. **Transcript format:** Is there a standard transcript format required by Ghana universities or international institutions? **Action needed:** Research Ghana tertiary admission requirements and Cambridge UCAS format.

---

## 20. Implementation Order and Dependencies

```
MC-Sprint 1 (Week 1-2)
  ├── Day 1-2:  Enums + curriculum_profiles table + migration
  ├── Day 3-4:  assessment_structures + assessment_components tables + migration
  ├── Day 5:    report_card_configs table + migration
  ├── Day 6:    Data migration (GES default profiles for existing tenants)
  ├── Day 7-8:  CurriculumService + Profile endpoints (8)
  ├── Day 9:    Assessment structure endpoints (7) + Report config endpoints (2)
  └── Day 10:   Frontend: Profile wizard + class assignment UI

MC-Sprint 2 (Week 3-4)
  ├── Day 1-2:  grade_equivalencies + subject_curriculum_mappings tables
  ├── Day 3:    term_reports + exam_scores + subjects column additions
  ├── Day 4-6:  Score strategy classes (6 strategies)
  ├── Day 7:    TermReportService refactor (strategy dispatch)
  ├── Day 8:    Report card HTML templates (5 new)
  ├── Day 9:    Grade equivalency + subject mapping endpoints (9)
  └── Day 10:   Frontend: Report preview + grade equivalency matrix

MC-Sprint 3 (Week 5-6)
  ├── Day 1-2:  external_exam_registrations + student_credit_accumulations + predicted_grades tables
  ├── Day 3-4:  External exam service + endpoints (8)
  ├── Day 5-6:  Credit service + GPA calculation + endpoints (4)
  ├── Day 7:    Predicted grades service + endpoints (4)
  ├── Day 8:    Transcript PDF template
  ├── Day 9:    CSV import parsers (WAEC, Cambridge)
  └── Day 10:   Frontend: External exams + transcript + credits pages
```

**Cross-sprint dependencies:**
- Sprint 2 depends on Sprint 1 (curriculum_profiles must exist before strategies can look them up)
- Sprint 3 depends on Sprint 1 (external_exam_registrations references curriculum concepts)
- Sprint 3 is partially independent of Sprint 2 (external exams and predicted grades don't depend on score strategies)

---

## 21. TENANT_SCOPED_TABLES Update

After all 3 sprints, add to `conftest.py` TENANT_SCOPED_TABLES:

```python
# Multi-Curriculum (MC Sprint 1-3)
"curriculum_profiles",
"assessment_structures",
"assessment_components",
"report_card_configs",
"grade_equivalencies",
"subject_curriculum_mappings",
"external_exam_registrations",
"student_credit_accumulations",
"predicted_grades",
```

Total tenant-scoped tables after MC: 55 + 9 = 64.

---

## 22. Files Affected Summary

### New Files (Backend)
- `backend/app/models/curriculum.py` -- All curriculum models
- `backend/app/schemas/curriculum.py` -- All curriculum schemas
- `backend/app/services/curriculum/` -- Package with:
  - `__init__.py`
  - `_shared.py` -- CurriculumServiceError
  - `profile_service.py` -- Profile CRUD, template instantiation
  - `assessment_service.py` -- Assessment structure management
  - `equivalency_service.py` -- Grade equivalencies
  - `subject_mapping_service.py` -- Subject-curriculum mappings
  - `external_exam_service.py` -- External exam registration/results
  - `credit_service.py` -- Credit accumulation and GPA
  - `predicted_grade_service.py` -- Predicted grades
- `backend/app/services/exam/score_strategies.py` -- Strategy pattern classes
- `backend/app/api/v1/endpoints/curriculum/` -- Package with:
  - `__init__.py` -- Combined router
  - `profiles.py`
  - `assessment.py`
  - `equivalencies.py`
  - `subject_mappings.py`
  - `external_exams.py`
  - `credits.py`
  - `predicted_grades.py`
- `backend/app/templates/reports/cambridge_report.html`
- `backend/app/templates/reports/american_report.html`
- `backend/app/templates/reports/ib_report.html`
- `backend/app/templates/reports/french_report.html`
- `backend/app/templates/reports/montessori_report.html`
- `backend/alembic/versions/20260310_0100_curriculum_foundation.py`
- `backend/alembic/versions/20260310_0200_curriculum_data_migration.py`
- `backend/alembic/versions/20260315_0100_grading_and_equivalencies.py`
- `backend/alembic/versions/20260320_0100_external_exams_and_credits.py`

### Modified Files (Backend)
- `backend/app/models/__init__.py` -- Import curriculum models
- `backend/app/models/academic/subject_models.py` -- Extend GradingScaleType enum, add curriculum_profile_id to GradingScale, add credit_value/coefficient to Subject
- `backend/app/models/academic/class_models.py` -- Add curriculum_profile_id to Class
- `backend/app/models/school.py` -- Add curriculum_profile_id, curriculum_settings to School
- `backend/app/models/student.py` -- Add curriculum_profile_id, previous_curriculum_type to Student
- `backend/app/models/exam.py` -- Add effort_grade to ExamScore; add curriculum fields to TermReport
- `backend/app/services/exam/report_service.py` -- Add strategy dispatch, _resolve_curriculum_profile
- `backend/app/services/exam/score_service.py` -- Add effort_grade handling
- `backend/app/api/v1/router.py` -- Include curriculum router
- `backend/app/schemas/academic.py` -- Add curriculum_profile_id to class schemas
- `backend/app/schemas/exam.py` -- Add curriculum fields to report schemas
- `backend/tests/conftest.py` -- Add 9 tables to TENANT_SCOPED_TABLES

### New Files (Frontend)
- `frontend/actions/curriculum.action.ts`
- `frontend/actions/external-exams.action.ts`
- `frontend/actions/credits.action.ts`
- `frontend/actions/predicted-grades.action.ts`
- `frontend/types/curriculum.type.ts`
- `frontend/app/(dashboard)/settings/curriculum/` -- 6 pages
- `frontend/app/(dashboard)/exams/external/` -- 4 pages
- `frontend/app/(dashboard)/students/[id]/transcript/page.tsx`
- `frontend/components/curriculum/` -- 7 components

### Modified Files (Frontend)
- `frontend/app/(dashboard)/settings/page.tsx` -- Add curriculum settings link
- `frontend/app/(dashboard)/classes/` -- Add curriculum selector to class forms
- `frontend/components/dashboard/app-sidebar.tsx` -- Add curriculum menu items
- `frontend/types/index.ts` -- Add curriculum types
