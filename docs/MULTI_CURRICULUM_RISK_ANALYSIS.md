# Multi-Curriculum Support -- Risk & Feasibility Analysis

**Analyst:** Risk Analyst Agent
**Date:** 2026-03-06
**Spec Reviewed:** `spec/multi-curriculum/` files 00 through 09 + `implementation-plan.md`
**Codebase Files Reviewed:** `exam.py` models, `report_service.py` (1304 lines), `score_service.py`, `subject_models.py`, `test_exams.py`
**Complexity Rating:** 9/10 (as stated in spec -- I agree)

---

## Executive Summary

The multi-curriculum plan is architecturally sound -- the "configuration layer" approach and Strategy Pattern are the right design choices. However, the plan significantly underestimates several areas: the report service refactoring (1304 lines of tightly coupled GES logic), the GES regression testing burden, and the data migration edge cases. The spec's total effort estimate of ~42 developer-days across 3 phases is optimistic by roughly 40-60%. My revised estimate is **60-70 developer-days raw, or 78-91 with buffer**.

The highest-risk item is the Phase 2 refactoring of `TermReportService.get_student_subject_results()` and `calculate_student_term_scores()`. These two methods contain ~500 lines of deeply GES-specific logic including batch query optimization (`_batch_get_all_scores`, `_batch_calculate_subject_positions`) that cannot simply be "renamed to `_legacy`." The strategy pattern must replicate these optimizations or accept a performance regression.

The backward compatibility promise is achievable but only if the GES fallback path is truly a **code-unchanged copy** of the current methods, not a refactored version. The spec says this but the implementation details suggest more surgery than acknowledged.

---

## 1. Backward Compatibility Risk Assessment

### Current State of the Score Pipeline

The existing `report_service.py` is **1304 lines** with the following key methods:

| Method | Lines | Complexity | Notes |
|--------|-------|------------|-------|
| `calculate_student_term_scores()` | ~200 | High | 4-component weighted scoring with CA/midterm/end_term categorization |
| `get_student_subject_results()` | ~220 | Very High | Batch-optimized, builds per-subject CA/Exam breakdown, position calculation |
| `_batch_get_all_scores()` | ~100 | High | Single query fetches CA + exam scores for all subjects at once |
| `_batch_calculate_subject_positions()` | ~80 | High | Cross-student position ranking per subject |
| `generate_term_report()` | ~150 | High | Orchestrates everything, creates TermReport rows |

### Assessment: Is "Zero Impact" Realistic?

**Conditionally yes, but with significant caveats.**

The spec's Decision 6 says: "When the score engine encounters a class without a `curriculum_profile_id`, it falls back to the existing AssessmentWeight-based GES logic." The spec also says: "The existing GES logic is renamed to `_get_student_subject_results_legacy()` but the code is NOT modified."

**Problem 1: The rename is not sufficient.** The current `get_student_subject_results()` is called from multiple places:
- `generate_term_report()` (the main report generation flow)
- `generate_class_reports()` (bulk generation)
- Potentially from the parent portal's grade viewing endpoints

Every call site needs to be updated to go through the new dispatch method. If any call site is missed, it will call the old method name (which no longer exists after rename) and break.

**Problem 2: The GES strategy class in file 04 does NOT match the actual GES logic.** The `GESScoreStrategy.calculate_subject_score()` in the spec (file 04, lines 406-453) takes `component_scores` and `components` as inputs. But the actual `get_student_subject_results()` method fetches scores directly from the database using batch queries. The strategy pattern as designed is a **pure calculation** layer, but the existing GES logic is an **integrated fetch+calculate** layer. This means:
- Either the strategy must also handle data fetching (violating separation of concerns), or
- A new data-fetching layer must be built that normalizes scores from `ContinuousAssessment` + `ExamScore` tables into the `component_scores` dict that strategies expect.

This normalization layer is not described anywhere in the spec and represents 2-3 days of additional work.

**Problem 3: The `_batch_get_all_scores()` optimization.** The current code uses a single batch query to fetch CA scores, CA-exam scores, and end-term scores for all subjects at once. The strategy pattern as designed expects scores to be pre-fetched and passed in. If the new curriculum path does per-subject queries instead of batch queries, performance for non-GES schools will be significantly worse (N+1 pattern for N subjects).

### Highest-Risk Areas for GES Regression

| Area | Risk Level | Why |
|------|-----------|-----|
| `class_score` / `exams_score` split calculation | **Critical** | The existing code uses `ca_total_weight` and `exam_total_weight` from `AssessmentWeight` for the report card display split. The strategy's `maps_to_ca`/`maps_to_exam` flags are a different mechanism. If both paths are active simultaneously, the numbers could diverge. |
| Subject position ranking | **High** | Positions are calculated via `_batch_calculate_subject_positions()` which uses the current weight formula. If the dispatch incorrectly routes a GES class through the strategy path, positions could change. |
| Exam type categorization | **High** | The current code categorizes `ExamType.QUIZ`, `MIDTERM`, `MOCK`, `PRACTICAL`, `PROJECT` as CA-contributing exams. The new `AssessmentComponentType` enum has different categories. The GES fallback MUST continue using `ExamType` categorization, not `AssessmentComponentType`. |
| `ca_total_weight` / `exam_total_weight` fields | **Medium** | The current `AssessmentWeight` model has `ca_total_weight` and `exam_total_weight` (lines 317-326 of subject_models.py). These control the report card display. The new `assessment_components` table uses `maps_to_ca`/`maps_to_exam` flags plus component `weight`. These are conceptually similar but mechanically different. |

---

## 2. Data Migration Risk Assessment

### Algorithm Review (File 01, Section 1.9)

The data migration creates a "GES Default" curriculum profile for each existing tenant.

### Edge Cases Not Handled

| Edge Case | Impact | Likelihood |
|-----------|--------|------------|
| **Tenant with no schools** | Migration creates a profile with `school_id=NULL`. Later queries that filter by `school_id` will not find it. | Medium -- trial tenants that never completed onboarding |
| **Tenant with multiple schools (chain)** | Migration creates ONE profile per tenant, not per school. Chain tenants need per-school profiles. `school_id` is NULL in the created profile. | Low currently (chains are Phase 3, Sprint 19-20), but the migration creates wrong data for future chain tenants |
| **Schools with no assessment_weights** | Handled -- migration creates default 20/10/20/50 structure. Good. | N/A |
| **Assessment weights with non-standard values** | Handled -- migration reads actual weights. Good. But does NOT read `ca_total_weight` and `exam_total_weight` from the existing `AssessmentWeight` row. | Medium -- schools that customized the CA/Exam split will get the wrong report card display weights in the new structure |
| **Multiple assessment_weights per tenant (year-specific overrides)** | Migration creates multiple `assessment_structures` linked to the same profile, each with the correct `academic_year_id`. This is correct, BUT the unique constraint `uq_assessment_structure` uses `COALESCE(academic_year_id, nil_uuid)`, so having a NULL + year-specific structure is fine. Multiple year-specific structures are also fine. **However**: if a tenant has 3 year-specific weights, the migration creates 3 structures + 12 components. That is correct. | Low |
| **Duplicate profile name "GES Default"** | Migration checks for existing "GES Default" profiles (idempotent). Good. But if a school admin manually creates a profile named "GES Default" before migration runs, the idempotency check passes and no profile is created, leaving the tenant without a migrated structure. | Very Low |
| **NULL `academic_year_id` in assessment_weights** | Line 967-968: `"yid": str(year_id) if year_id else None`. When `year_id` is None, `CAST(:yid AS uuid)` receives `None`, which produces `CAST(NULL AS uuid)`. This is correct for PostgreSQL. | N/A -- handled |
| **RLS context during migration** | Migration uses superuser connection (no RLS). It inserts `tenant_id` explicitly. This is correct per project convention. | N/A -- handled |
| **Missing `ca_total_weight`/`exam_total_weight` conversion** | The `AssessmentWeight` model has `ca_total_weight` (default 50) and `exam_total_weight` (default 50) fields that control report card display. The migration does NOT carry these into the new structure's `maps_to_ca`/`maps_to_exam` component flags. Schools that set ca_total_weight=40 and exam_total_weight=60 will get the default 50/50 split in the new system if they ever switch to using the curriculum profile path. | Medium -- only matters if GES schools ever opt into the new profile path |

### Migration Performance

For a production database with ~100 tenants, each with ~3 assessment_weight rows, the migration creates:
- 100 curriculum_profiles
- ~300 assessment_structures
- ~1200 assessment_components
- 0 report_card_configs (migration does not create these -- gap noted below)

This should complete in under 10 seconds. No performance risk.

### Gap: ReportCardConfig Not Created

The data migration creates `curriculum_profiles` and `assessment_structures` + `assessment_components` but does **NOT** create `report_card_configs`. The template instantiation code in file 02 creates these when using `create_from_template()`, but the data migration bypasses templates. This means migrated GES profiles will have no `report_card_config` row, and `CurriculumProfileDetailResponse.report_config` will be `None` for all migrated profiles.

This is not a functional problem (the GES fallback path does not use `report_card_configs`), but it is a UI inconsistency -- the profile detail page will show an empty report config section for migrated profiles.

---

## 3. Score Strategy Complexity Assessment

### Is the Strategy Interface Well-Defined?

The `ScoreStrategy` base class (file 04, lines 344-391) defines:

```python
class ScoreStrategy(ABC):
    def calculate_subject_score(self, component_scores, components, max_scores) -> SubjectScoreResult
    def determine_grade(self, score, grades) -> tuple
    def calculate_aggregate(self, subject_results, profile) -> dict
```

**Assessment: The interface is clean but incomplete.**

### Missing from the Interface

1. **No async support.** The base class methods are synchronous, but the data-fetching layer that feeds them is async. This means the calling code must do all DB work, then call the synchronous strategy. This is fine architecturally but not documented.

2. **No error handling contract.** What should `calculate_subject_score()` return when ALL component scores are `None`? The spec does not specify. The GES strategy (lines 419-453) will return `class_score=0` and `exams_score=0` and `final_score=0`. But should Montessori return `final_score=None`? Should American return a zero GPA or no GPA? Each strategy handles this differently, and there is no contract in the base class.

3. **No `max_score` normalization contract.** The `max_scores` dict maps `component_type -> max_possible_score`. But who provides this? For GES, the max scores come from `ContinuousAssessment.max_score` and `ExamSubject.max_score`. For non-GES curricula, max scores come from `AssessmentComponent.max_score`. The fetching code must know which source to use based on curriculum type -- this is not documented.

4. **Coefficient handling.** The French strategy multiplies `score * coefficient` before averaging. But coefficients live on `SubjectCurriculumMapping.coefficient`, not in the `component_scores` dict. The strategy needs access to per-subject metadata that is not in the current interface.

### Edge Cases Not Covered

| Edge Case | Affected Strategy | Impact |
|-----------|------------------|--------|
| Zero scores across all components | All | Should return `final_score=0` or `None`? Affects GPA (0.0 vs excluded) |
| Student absent for all exams | All | `is_absent=True` on all ExamScores. Should CA still count? |
| Partial data (CA entered, exam not yet) | All | Mid-term reports show partial results. Each strategy handles differently |
| Score exceeds component max_score | All | Validation in `ScoreService` but not in strategies |
| Negative scores after rounding | French | `score * coefficient / sum(coefficients)` can produce floating point artifacts |
| IB bonus points (EE+TOK) | IB | Only applies to DP, not MYP. Strategy must check `config.ib_programme` |
| AP weighted GPA cap at 5.0 | American | `grade_point + 1.0` capped at 5.0, but spec says "max 5.0" for AP -- what about A+ (4.0 + 1.0 = 5.0) vs AP A- (3.7 + 1.0 = 4.7)? Is 5.0 the absolute cap or per-grade cap? |
| Montessori with numeric scores | Montessori | Spec says "NO numeric grades" but `weight` field exists on components. What does `weight=40` mean for a narrative component? |
| Custom curriculum type | Custom | Falls back to GES strategy per factory. But custom may have non-GES components. |

---

## 4. Phase Dependencies Assessment

### Are Dependencies Clearly Documented?

Yes, the cross-phase dependency diagram in file 00 (lines 194-206) is accurate. However, it understates the coupling.

### Detailed Dependency Map

```
Phase 1 Models/Migration
    |
    +-- Phase 1 Services/Endpoints (depends on models)
    |       |
    |       +-- Phase 1 Frontend (depends on endpoints)
    |
    +-- Phase 2 Models (depends on P1 tables existing)
            |
            +-- Phase 2 Score Strategies (depends on P2 models + P1 assessment_components)
            |       |
            |       +-- Phase 2 Report Service Refactor (depends on strategies + P1 _resolve helper)
            |               |
            |               +-- Phase 2 Report Card Templates (depends on refactored data shape)
            |               |
            |               +-- Phase 2 Frontend (depends on all P2 backend)
            |
            +-- Phase 3 External Exams (PARTIALLY INDEPENDENT -- depends on P1 profiles only)
            |
            +-- Phase 3 Credits/GPA (depends on P2 strategies for grade -> grade_point mapping)
            |       |
            |       +-- Phase 3 Transcripts (depends on credits)
            |
            +-- Phase 3 Predicted Grades (depends on P1 profiles + P2 grading scales)
```

### Can Phase 2 Begin Before Phase 1 is Complete?

**Partially.** The score strategy classes (tasks 4.4-4.9) can be developed as pure Python classes with unit tests before Phase 1 models exist in the database. They only need the model classes for type hints, not runtime table access. This saves ~4 days of serial dependency.

However, the report service refactor (task 4.10) absolutely requires Phase 1 to be merged and migrated, because it needs `_resolve_curriculum_profile()` and the `curriculum_profiles` table to exist.

### Are There Circular Dependencies?

**No circular dependencies found.** The dependency chain is strictly forward. One concern: the `GradingScale.curriculum_profile_id` column added in Phase 1 (section 1.7d) is also referenced in the Phase 2 migration (line 87 of file 04). The spec lists it in BOTH phases. The Phase 2 migration should check if the column already exists before adding it (or skip the ADD COLUMN if Phase 1 already added it). As written, the Phase 2 migration would fail with "column already exists."

---

## 5. Effort Estimates Assessment

### Spec Estimates vs. Revised Estimates

#### Phase 1: Foundation

| Task | Spec Est. | Revised | Rationale |
|------|-----------|---------|-----------|
| 1.1-1.6 Enum + Model definitions | 2.75d | 2.5d | Agree -- straightforward model work |
| 1.7 Modify existing models | 1d | 1.5d | Adding FK columns to 4 existing models requires updating schemas, services, and existing tests that create these models via raw SQL (must add new nullable columns to INSERT statements) |
| 1.8 Schema migration | 2d | 3d | `ALTER TYPE ADD VALUE` outside transaction is tricky. Need autocommit handling. 4 tables + RLS + indexes + grants. COALESCE-based unique index on `assessment_structures` is non-trivial |
| 1.9 Data migration | 1d | 2d | Edge cases (see Section 2). Must add `report_card_configs` creation. Must handle `ca_total_weight`/`exam_total_weight` conversion. Idempotency testing |
| 1.10 Test infrastructure | 0.5d | 0.5d | Agree |
| 2.1-2.4 Services | 3.75d | 4d | Templates dict is large (10 templates x 3 sections). Validation logic for JSONB config |
| 2.5-2.9 Schemas + Endpoints | 2.75d | 3d | ~35 schema classes + 17 endpoints. Permission registration. Error handling |
| 2.10-2.12 Modify existing services | 1.25d | 2d | `_resolve_curriculum_profile()` has 3-level resolution chain requiring 3 queries. ClassService changes need audit logging for mid-term curriculum switches |
| 3.1-3.9 Frontend | 5.75d | 7d | CurriculumProfileWizard is a 4-step wizard with React Hook Form + Zod. AssessmentStructureEditor is a complex interactive table with weight validation. These are consistently underestimated |
| **Phase 1 Subtotal** | **~15d** | **~22d** |  |
| Testing (not in spec estimates) | 0d | 5d | 50 test cases for Phase 1 per file 08. This is NOT included in the task estimates |
| **Phase 1 Total** | **~15d** | **~27d** |  |

#### Phase 2: Grading & Score Engine

| Task | Spec Est. | Revised | Rationale |
|------|-----------|---------|-----------|
| 4.1 Migration | 1.5d | 2d | 2 tables + 9 columns on existing tables + RLS. The `grading_scales.curriculum_profile_id` column conflict with Phase 1 |
| 4.2-4.3 Models | 1d | 1d | Agree |
| 4.4 GES Strategy | 1d | 2d | Must exactly reproduce current behavior. Requires extracting logic from 200+ lines of async DB-integrated code into pure calculation. Building the normalization layer between DB and strategy |
| 4.5-4.9 Other strategies | 4d | 5d | 5 strategies at 0.5-1d each. IB criterion grading and French coefficient system are genuinely complex. American GPA with weighted/unweighted adds edge cases |
| 4.10 Report service refactor | 1.5d | 4d | **Most underestimated task.** The `get_student_subject_results()` method is 220 lines of batch-optimized queries. Must create equivalent batch optimization for the curriculum path. Must not break the 4 callers of this method. Must handle the data normalization layer. Must preserve `_batch_get_all_scores()` optimization |
| 4.11-4.15 Equivalency + mapping services | 3d | 3d | Agree -- straightforward CRUD |
| 4.16 Report card templates | 2d | 3d | 5 HTML templates with Jinja2. Each needs curriculum-specific sections. Plus shared macros extraction. WeasyPrint rendering quirks |
| 4.17-4.19 PDF service + schemas + tests | 1.25d | 1.5d | Agree |
| **Phase 2 Subtotal** | **~15.25d** | **~21.5d** |  |
| Testing (GES regression + strategy unit tests) | 0d | 6d | 18 strategy tests + 8 equivalency tests + 8 mapping tests + 8 report tests + 10 GES regression tests = 52 test cases. Critical path -- must be thorough |
| **Phase 2 Total** | **~15.25d** | **~27.5d** |  |

#### Phase 3: External Exams, Credits, Transcripts

| Task | Spec Est. | Revised | Rationale |
|------|-----------|---------|-----------|
| 6.1-6.4 Migration + Models | 2.5d | 3d | 3 tables + new enum + COALESCE unique constraints. JSONB column validation for subjects/results arrays |
| 6.5-6.7 Services | 3.75d | 4d | CSV parser is 1d alone. GPA calculation with AP/Honors bonuses needs careful decimal handling |
| 6.8-6.11 Schemas + Endpoints | 3d | 3d | Agree |
| 6.12-6.16 Export + Import + Transcript | 4.5d | 5d | WAEC/Cambridge export formats are not well-documented in spec. Transcript PDF template is complex (multi-page A4) |
| 6.17 Test infrastructure | 0.25d | 0.25d | Agree |
| 7.1-7.16 Frontend | 10d | 12d | ResultsImportWizard (3-step with dry-run preview) and CreditProgressDashboard (Recharts GPA trend) and TranscriptViewer (print-ready A4) are all complex |
| **Phase 3 Subtotal** | **~24d** | **~27.25d** |  |
| Testing | 0d | 5d | 14 registration tests + 8 CSV import tests + 4 export tests + 11 credit/GPA tests + 7 predicted grade tests + 5 transcript tests = 49 test cases |
| **Phase 3 Total** | **~24d** | **~32.25d** |  |

### Summary

| Phase | Spec Raw | Revised Raw | Revised + 25% Buffer |
|-------|----------|-------------|---------------------|
| Phase 1 | ~15d | ~27d | ~34d |
| Phase 2 | ~15d | ~27.5d | ~34d |
| Phase 3 | ~24d | ~32d | ~40d |
| **Total** | **~54d** | **~86.5d** | **~108d** |

**Note:** The spec's `implementation-plan.md` quotes ~42d total, but the detailed task lists in files 01-07 sum to ~54d. The discrepancy suggests the implementation plan was written separately from the detailed specs. I used the detailed task-level estimates for comparison.

**Confidence Level:** Medium -- I have high confidence in the model/migration/service estimates but lower confidence in the frontend estimates (frontend work depends heavily on developer familiarity with the component library).

---

## 6. Integration Risk with Existing Exam Module

### Risk Level: HIGH

The existing exam module is the most complex part of the codebase. Key concerns:

### 6.1 Report Service Refactoring Surface

The `report_service.py` file is 1304 lines. The refactoring touches:

1. **`calculate_student_term_scores()`** (lines 47-246): This method must be preserved exactly for GES. The new curriculum path needs an equivalent method. The spec does not mention this method at all -- it only discusses `get_student_subject_results()`. But `calculate_student_term_scores()` is used by `generate_term_report()` to populate `TermReport.total_score` and `TermReport.average_score`. If this is not also strategy-dispatched, GES will still work but non-GES curricula will get incorrect `total_score`/`average_score` values on their TermReport rows.

2. **`get_student_subject_results()`** (lines 780-979): The primary refactoring target. This method returns a list of dicts with keys `class_score`, `exams_score`, `total_score`, `grade`, `subject_position`, etc. Non-GES curricula need different keys (e.g., `gpa`, `effort_grade`, `ib_level`). The return shape must be polymorphic.

3. **`generate_term_report()`** (called from exam endpoints): This orchestrates the entire flow. It must branch on curriculum type to populate the new TermReport columns (`gpa`, `weighted_gpa`, `honor_roll`, `ib_total_points`, `french_mention`, `extra_data`).

4. **`_batch_get_all_scores()`** and **`_batch_calculate_subject_positions()`**: These optimization methods are GES-specific (they categorize by `ExamType.END_TERM` vs other types). Non-GES curricula need equivalent batch methods that categorize by `AssessmentComponentType` instead.

### 6.2 Existing Report Card PDF Generation

The current PDF generation uses `templates/reports/term_report.html` (or similar). The template expects a specific data shape with `class_score`, `exams_score`, `total_score`, `position` columns. The 5 new templates must expect different data shapes. The `get_report_template()` function (file 04, lines 630-644) selects the template, but the data passed to the template must also be curriculum-specific. This means the `generate_term_report_pdf()` method needs a strategy-aware data preparation step.

### 6.3 Parent Portal Impact

The parent portal (`services/parent/parent_academic.py`) likely calls into the exam service to show grades. If it calls `get_student_subject_results()`, it will receive the new polymorphic return shape. The parent portal's frontend must handle both GES-style and curriculum-style data.

### 6.4 Exam Analytics Impact

The `analytics_service.py` computes grade distributions, class statistics, etc. These currently assume percentage-based scoring. IB (1-7 levels), Montessori (narrative), and French (0-20) curricula will produce incorrect analytics unless the analytics service is also curriculum-aware. The spec does not mention analytics at all.

---

## 7. Testing Coverage Gaps

### File 08 lists approximately 130 test cases across 15 test files. Gaps identified:

### Critical Gaps

| ID | Missing Test | Why It Matters |
|----|-------------|----------------|
| T1 | **GES regression with `ca_total_weight != 50`** | The GES regression tests (R.1-R.10) test standard 50/50 split. Schools that customized `ca_total_weight=40, exam_total_weight=60` are not tested. If the refactored code accidentally uses the new component weights instead of the legacy `AssessmentWeight.ca_total_weight`, these schools break silently. |
| T2 | **Concurrent report generation for mixed-curriculum classes** | No test for generating reports when the same school has both GES and Cambridge classes. Specifically: does `generate_class_reports()` correctly dispatch per-class, not per-tenant? |
| T3 | **Student transfer between curricula** | A student moves from a GES class to a Cambridge class mid-year. Their `curriculum_profile_id` changes. Old term reports should retain GES formatting. New term reports should use Cambridge. No test covers this. |
| T4 | **Migration rollback + re-run** | The data migration is marked "idempotent" but there is no test verifying that downgrade + upgrade produces correct state. The downgrade deletes all "GES Default" profiles (including any school-admin customizations to those profiles). |
| T5 | **Score strategy with `Decimal` precision** | The GES strategy does `(ca_weighted / ca_max) * ca_weight`. With `Decimal`, this can produce 15+ decimal places. No test verifies rounding behavior matches the existing code's `Decimal("0.01")` quantization. |
| T6 | **Performance regression test for GES path** | No test verifies that the refactored GES path (going through the dispatch + fallback) is not slower than the current direct path. The additional `_resolve_curriculum_profile()` query adds latency. |
| T7 | **Parent portal viewing multi-curriculum reports** | The parent portal shows grades. No test verifies that a parent with children in different curriculum classes sees correct data for each child. |
| T8 | **`get_score_strategy(None)` with non-string input** | Test 6.18 tests `None`, but the actual `curriculum_type` field is an enum. What happens with `get_score_strategy(CurriculumType.GES)` (enum object) vs `get_score_strategy("ges")` (string)? |
| T9 | **Assessment weight sum validation bypass during data migration** | The migration creates components from existing weights. If existing weights sum to 99 or 101 (due to admin error), the migration creates an invalid structure. No validation is run. |
| T10 | **`ExamType` to `AssessmentComponentType` mapping** | The GES path uses `ExamType.MIDTERM` to categorize exams. The new path uses `AssessmentComponentType.MIDTERM`. These are different enums in different modules. No test verifies they are kept in sync. |

### Coverage Assessment

| Area | Spec Coverage | Adequate? |
|------|--------------|-----------|
| Profile CRUD | 15 tests | Yes |
| Assessment structures | 10 tests | Yes |
| Templates | 9 tests | Yes |
| Score strategies | 18 tests | Mostly -- missing edge cases above |
| Grade equivalencies | 6 tests | Yes |
| Subject mappings | 8 tests | Yes |
| Term report multi-curriculum | 8 tests | **No** -- missing concurrent, transfer, performance |
| External exams | 14 tests | Yes |
| CSV import | 8 tests | Yes |
| Credits/GPA | 11 tests | Mostly -- missing precision tests |
| Predicted grades | 7 tests | Yes |
| Transcripts | 5 tests | Yes |
| GES regression | 10 tests | **No** -- missing non-standard weight configs |
| RLS isolation | 18 tests (9 select + 9 insert) | Yes |
| Integration workflows | 9 tests | Adequate |
| Performance | 6 tests | Adequate |

---

## 8. Frontend Complexity Assessment

### Components Ranked by Risk

| Component | Spec Est. | Risk | Assessment |
|-----------|-----------|------|------------|
| **CurriculumProfileWizard** | 1.5d | High | 4-step wizard with conditional branching (template vs custom). React Hook Form with dynamic validation based on curriculum type. Similar complexity to the existing setup wizard. 1.5d is tight -- 2-2.5d more realistic. |
| **AssessmentStructureEditor** | 1d | High | Interactive table with inline editing, dynamic row add/remove, running total calculation, reorder by drag or sequence number. This is essentially a mini-spreadsheet. 1d is underestimated -- 2d more realistic. |
| **GradeEquivalencyMatrix** | 1d | Medium-High | Grid of checkboxes with 2 axis selections. Conceptually simple but the number of cells can be large (9 WAEC grades x 8 Cambridge grades = 72 cells). Bulk save logic. 1d is reasonable if using a simple table, not a custom grid component. |
| **ResultsImportWizard** | 1.5d | High | 3-step wizard with file upload, dry-run preview table with color-coded status rows, confirm+progress. The preview table with matched/unmatched/error row styling is complex. 2d more realistic. |
| **CreditProgressDashboard** | 1d | Medium | Recharts line chart + summary cards + breakdown table. Standard dashboard pattern. 1-1.5d is reasonable. |
| **TranscriptViewer** | 1d | Medium-High | Print-ready A4 layout with `@media print` CSS. Multi-page with page breaks. Signature lines and watermarks. Getting print CSS right is notoriously fiddly. 1.5d more realistic. |
| **ReportCardPreview** | 1d | Medium | Live preview component that renders different report formats. Essentially a mini-version of each report card template in React. 1d is tight for 6 formats -- but can start with just GES + 1 other. |
| **PredictedGradeEntry** | 1d | Medium | Spreadsheet-style grid. Similar to existing score entry form but with inline selects instead of number inputs. Bulk save. 1d is reasonable given existing score entry pattern to copy. |
| **SubjectMappingTable** | 1d | Low-Medium | Bulk mapping table. Standard TanStack Table with editable cells. 1d is reasonable. |
| **Multi-curriculum report card viewer** | 1d | High | Component switch with 6 different report layouts. Each layout is essentially a custom component. 1d covers the switch mechanism but not the 5 new layout components. Add 2d for the layout components. |

### Frontend Total Reassessment

Spec total for all frontend across 3 phases: ~16d
Revised total: ~24d

The pattern I consistently see: the spec estimates each component at its minimum viable time, not accounting for responsive design (the project uses `max-sm:` patterns for mobile), loading states, error states, or accessibility.

---

## 9. Deployment Risk Assessment

### Can Phases Be Deployed Independently?

**Phase 1: Yes, safely.** Phase 1 adds new tables and columns. All new columns are nullable. No existing behavior changes. The data migration creates profiles that are not referenced by any existing code path.

**Phase 2: Yes, but with careful sequencing.** The report service refactor must ship atomically with the score strategies. You cannot deploy the refactored `get_student_subject_results()` without the `GESScoreStrategy` being available. The migration (adding columns to `term_reports` and `exam_scores`) can deploy separately from the code changes, since all new columns are nullable.

**Phase 3: Yes, fully independent of Phase 2.** External exams, predicted grades, and credit tracking are all new features with no existing code dependencies. They can deploy even if Phase 2 is delayed. The only caveat: transcript generation depends on GPA calculation, which depends on Phase 2's credit service integration.

### Blast Radius Analysis

**If Phase 2 has a bug:**

| Scenario | Impact on Phase 1 | Impact on Existing GES |
|----------|-------------------|----------------------|
| Score strategy returns wrong grade | None | None IF the `profile is None` fallback works correctly. If the fallback has a bug (e.g., profile resolution returns a profile when it should not), GES schools are affected. |
| Report template selection fails | None | None -- falls back to default template |
| `_resolve_curriculum_profile()` returns wrong profile | None | **CRITICAL** -- if it returns a non-GES profile for a GES class, the wrong strategy runs |
| TermReport columns (gpa, honor_roll) have wrong values | None | None -- these are new nullable columns, not used by existing UI |

**Key risk:** The `_resolve_curriculum_profile()` resolution chain (Student -> Class -> School -> None) must be bulletproof. If a school admin sets a curriculum profile on the school but some classes should remain GES, the class-level override (or lack thereof) must correctly fall through. The spec says "No profile found -> fall back to GES logic" but the resolution checks `school.curriculum_profile_id`. If the school has a profile, all classes without an explicit override will use it -- including classes that should be GES. This is **by design** but could surprise schools.

### Rollback Safety

The rollback plan (file 09, section 7) is well-documented. Each phase can roll back independently. The critical point: **enum values added via `ALTER TYPE ADD VALUE` cannot be rolled back.** The spec acknowledges this (file 01, line 860-862). The 6 new `gradingscaletype` values and the 3 new enum types will persist even after rollback. This is acceptable.

---

## Risk Register

| ID | Risk Description | Category | Severity | Probability | Impact | Phase | Mitigation |
|----|-----------------|----------|----------|-------------|--------|-------|------------|
| R1 | GES score calculation regression due to refactored dispatch path | Technical | Critical | Medium | Incorrect report cards for all existing GES schools | 2 | (1) Keep existing methods as-is, copy into `_legacy` suffix. (2) Run side-by-side comparison: generate reports using both old and new code paths, diff results for 100 students. (3) Feature flag to disable new dispatch path. |
| R2 | `_resolve_curriculum_profile()` returns non-None for GES classes after school-level profile is set | Technical | High | Medium | GES classes routed through wrong strategy | 2 | Add explicit `curriculum_type == 'ges'` check: if resolved profile is GES type, still use legacy path. This is defense-in-depth for the transition period. |
| R3 | Data migration fails to convert `ca_total_weight`/`exam_total_weight` from AssessmentWeight | Data Migration | Medium | High | Migrated profiles have wrong report card weight split | 1 | Extend migration to read these fields and store them on `ReportCardConfig.custom_columns` or as component weight overrides. |
| R4 | `ALTER TYPE ADD VALUE` runs inside transaction, causing migration failure | Technical | High | Medium | Migration aborts, leaves DB in partial state | 1 | Use separate migration file for enum extensions with `autocommit=True`. Test on staging with PostgreSQL 16 before production. |
| R5 | Phase 2 migration adds `grading_scales.curriculum_profile_id` but Phase 1 already added it | Technical | Medium | High | Migration fails with "column already exists" | 2 | Add `IF NOT EXISTS` check or remove the duplicate column addition from Phase 2 migration. |
| R6 | Score strategy normalization layer not specified -- mismatch between DB data shape and strategy input | Technical | High | High | Strategies receive wrong data format, produce wrong scores | 2 | Design and document the normalization layer before implementing strategies. Create interface test: given known DB state, verify strategy receives expected inputs. |
| R7 | Batch query optimization not replicated for non-GES curriculum path | Performance | Medium | High | Non-GES report generation 5-10x slower than GES (N+1 queries) | 2 | Create equivalent `_batch_get_all_scores_curriculum()` that groups by `AssessmentComponentType` instead of `ExamType`. Add performance test: 200 students x 10 subjects < 5s. |
| R8 | Exam analytics service not updated for multi-curriculum | Technical | Medium | High | Analytics show incorrect grade distributions for non-GES classes | 2 | Add curriculum-aware analytics methods or skip analytics for non-GES curricula in v1. Document as known limitation. |
| R9 | `calculate_student_term_scores()` not strategy-dispatched | Technical | High | High | TermReport.total_score and average_score wrong for non-GES curricula | 2 | Add strategy dispatch to this method as well. The spec only mentions `get_student_subject_results()` but this method also needs it. |
| R10 | Parent portal shows wrong data shape for non-GES students | Technical | Medium | Medium | Parent sees GES-formatted data for Cambridge student | 2 | Audit parent portal service calls to exam module. Add curriculum-type field to parent grade response. |
| R11 | CurriculumProfileWizard frontend underestimated | Timeline | Low | High | Phase 1 frontend delayed by 2-3 days | 1 | Start frontend work immediately after endpoints are ready. Use template selector as MVP, defer custom profile creation to later sprint. |
| R12 | CSV result import parser fails on real WAEC/Cambridge files | Technical | Medium | Medium | Schools cannot import external exam results | 3 | **Action needed before Phase 3:** Obtain real sample files from partner schools. Build parser against real data, not assumed format. |
| R13 | IB criterion-based grading is more complex than estimated | Knowledge | Medium | Medium | IB strategy takes 2d instead of 1d | 2 | Start IB strategy early. Consult IB assessment documentation. Consider deferring IB MYP criterion mode to Phase 3. |
| R14 | French coefficient system has precision issues with Decimal arithmetic | Technical | Low | Medium | Rounding errors in French weighted averages | 2 | Use `Decimal` with explicit `quantize(Decimal("0.01"))` at each calculation step. Add boundary tests with known French baccalaureate results. |
| R15 | Montessori narrative report card requires free-text rich editing | Frontend | Medium | Low | Montessori report card is plain text instead of formatted narrative | 2 | Accept plain text for v1. Rich text editing (Tiptap/ProseMirror) deferred to future sprint. |
| R16 | Feature flag gating by subscription tier not implemented in endpoints | Technical | Medium | Medium | Starter-plan schools can create Cambridge profiles | 1 | Add `check_feature_flag("multi_curriculum")` check in `create_profile()` and `create_from_template()`. Test with all 3 subscription tiers. |
| R17 | 9 new tables expand `TENANT_SCOPED_TABLES` from 55 to 64 -- test suite runtime increases | Quality | Low | High | CI pipeline 15-20% slower | 1-3 | Accepted. The dynamic RLS test scales linearly with table count. |
| R18 | `assessment_components.config` JSONB validation is lightweight (dict-key check) | Technical | Low | Medium | Invalid JSONB config stored, causes runtime errors when strategy reads it | 1 | Add Pydantic model validation for known curriculum types' config schemas. Store validation errors, do not silently accept bad data. |
| R19 | Dual-track classes (same school, different curricula) create UX confusion for teachers | Knowledge | Medium | Low | Teachers enter scores in wrong format for curriculum type | 2 | Clear visual indicators on score entry form showing active curriculum. Color-coded badges per class in class list. |

---

## Multi-Tenancy Risk Assessment

### New Tables Requiring RLS Policies

All 9 new tables require RLS:
1. `curriculum_profiles`
2. `assessment_structures`
3. `assessment_components`
4. `report_card_configs`
5. `grade_equivalencies`
6. `subject_curriculum_mappings`
7. `external_exam_registrations`
8. `student_credit_accumulations`
9. `predicted_grades`

### Cross-Tenant Data Access Vectors

1. **Profile assignment across tenants:** A class references `curriculum_profile_id` via FK. RLS on `curriculum_profiles` prevents reading cross-tenant profiles, but the FK itself only validates existence, not tenant ownership. The service layer must validate `profile.tenant_id == class.tenant_id` before assignment. **This is documented in the spec** (section 2.10, file 02).

2. **Grade equivalency cross-reference:** `grade_equivalencies` references `grading_scales` and `grades` via FK. If a tenant creates an equivalency referencing another tenant's grading scale, RLS would prevent the SELECT but the FK constraint might allow the INSERT (since FK checks use superuser privileges). **Mitigation:** Service-layer validation that both source and target scales belong to the same tenant.

3. **Subject curriculum mapping:** Same pattern as above -- `subject_id` and `curriculum_profile_id` must be validated as same-tenant.

### Cache/Session Tenant Bleed Risks

No new caching introduced by this feature. The curriculum profile resolution (`_resolve_curriculum_profile()`) does 3 queries per student. If caching is added later (e.g., "cache the resolved profile per class"), the cache key MUST include `tenant_id`. **Recommendation:** Add a comment in `_resolve_curriculum_profile()` warning against caching without tenant-scoped keys.

### Background Job Tenant Context

No background jobs introduced in Phase 1-2. Phase 3's CSV import could potentially be moved to Celery for large files. If so, the Celery task must receive `tenant_id` and set tenant context before processing. **This is a future risk, not a current one.**

---

## Recommended Approach

### Parallel Tracks

**Track A (Backend Foundation):** Phase 1 models + migration + services + endpoints
**Track B (Score Strategies, can start after P1 models are defined but before P1 merges):** Pure Python strategy classes with unit tests. No DB required.
**Track C (Frontend, starts after P1 endpoints are ready):** Phase 1 frontend pages and components
**Track D (Report Templates, can start anytime):** HTML/CSS for 5 report card templates (no backend dependency)

### Sequential Dependencies

1. Phase 1 Models + Migration (must be first)
2. Phase 1 Services + Endpoints (depends on #1)
3. Phase 2 Migration + Models (depends on #1)
4. Phase 2 Score Strategies + Normalization Layer (depends on #1 models, #3 models)
5. Phase 2 Report Service Refactor (depends on #2 for `_resolve_curriculum_profile()`, #4 for strategies)
6. Phase 2 Report Card Templates (depends on #5 for data shape)
7. Phase 3 (depends on #1, partially on #5 for transcripts)

### Critical Path

```
P1 Models (3d) -> P1 Migration (3d) -> P1 Services (4d) -> P2 Migration (2d) -> Normalization Layer (3d) -> Report Service Refactor (4d) -> GES Regression Testing (3d)
```

**Minimum Timeline:** 22 days serial (1 developer)
**Realistic Timeline with 2 developers:** 14-16 weeks of calendar time for all 3 phases (accounting for context switching, reviews, and iteration)

### Recommendations

1. **Start Early: Obtain sample WAEC and Cambridge result files.** Phase 3's CSV parser cannot be built against assumed formats. Contact partner schools now (lead time: 2-4 weeks).

2. **Technical Spike: Build the normalization layer prototype first.** Before implementing any strategies, build the layer that converts `ContinuousAssessment` + `ExamScore` + `ExamType` data into the `component_scores` dict that strategies expect. Verify that the GES normalization produces identical numbers to the current code. Budget: 2 days.

3. **Blocker: Fix Phase 2 migration duplicate column.** Remove `grading_scales.curriculum_profile_id` from Phase 2 migration (it is already in Phase 1).

4. **Blocker: Add `ReportCardConfig` creation to data migration.** Without this, migrated profiles will have incomplete data.

5. **Risk Mitigation: Feature flag the dispatch.** Add a tenant-level feature flag `multi_curriculum_engine` that controls whether the new strategy dispatch path is active. Default to `false`. This allows deploying the code without activating it, then enabling per-tenant for testing.

6. **Risk Mitigation: Side-by-side score comparison.** Before activating the new engine for any tenant, run both the legacy and new code paths for the same student/term/class and compare results programmatically. Log any differences. This catches regression before users see it.

7. **Defer Montessori and IB MYP criterion mode to Phase 3.** These are the most different from the GES model and have the fewest potential customers in the Ghana market. Focus Phase 2 on Cambridge, American, and French (which are percentage/score-based and closer to GES).

8. **Add `calculate_student_term_scores()` to the refactoring scope.** The spec only mentions `get_student_subject_results()` but this method also populates TermReport aggregate fields. Without strategy dispatch here, non-GES TermReports will have incorrect `total_score` and `average_score`.

---

## Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| No new infrastructure needed | Multi-curriculum is a code/schema change only | N/A | None |
| Increased test suite runtime | 9 new tables in RLS test, ~130 new test cases | N/A | CI runtime increase ~20% |
| WeasyPrint memory for complex templates | IB and Montessori templates may be larger than GES | N/A | Monitor pod memory usage |
| Sample exam result files | For CSV parser development (WAEC, Cambridge) | 2-4 weeks | None (partner school cooperation) |
