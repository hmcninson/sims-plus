# Multi-Curriculum Support — Overview & Architecture

**Module:** Multi-Curriculum Support
**Phase:** 4 (MC-Sprint 1, 2, 3)
**Complexity:** 9/10
**Author:** SIMS Plus Team
**Date:** 2026-03-06
**Status:** Implementation Plan
**Migration Chain Head:** `20260303_0200` (applicant_accounts)

---

## 1. Executive Summary

Multi-curriculum support enables SIMS Plus schools to operate under different educational frameworks — Ghana (GES), Cambridge, Edexcel, American, IB, French, and Montessori — with distinct grading systems, assessment structures, and report card formats. Some schools run **dual-track** programmes (e.g., GES + Cambridge IGCSE simultaneously), requiring class-level and even student-level curriculum assignment.

The implementation is a **configuration layer** on top of the existing academic infrastructure. A new `curriculum_profiles` table serves as the central entity that bundles together a grading scale, a flexible assessment structure (N components instead of the current fixed 4), and report card display preferences. A Strategy Pattern dispatches score calculations and report rendering to curriculum-specific logic.

### Key Challenge

The current academic system is hardcoded around Ghana's GES model: 4-component assessment weights (class_work, homework, midterm, end_term), WAEC grading (A1-F9), 3-term calendar, and position-based rankings. Every part of the score calculation pipeline, report card generation, and UI assumes this structure. Multi-curriculum must generalize all of this while maintaining **zero behavioral change** for existing GES schools.

### Scope

| In Scope | Out of Scope (Future) |
|----------|----------------------|
| 8 curriculum types (GES, Cambridge, Edexcel, American, IB, French, Montessori, Custom) | CSSPS/WAEC API direct integration |
| School/class/student level curriculum assignment | Online entrance exam proctoring |
| Flexible N-component assessment structures | Automated curriculum-to-curriculum transfer credit mapping |
| 6 curriculum-specific score calculation strategies | Full IB CAS portfolio management |
| 5 new report card HTML templates | Multi-language report cards |
| External exam registration (WAEC, Cambridge, Edexcel, IB) | Automated external exam results API pull |
| External exam results import (CSV) | Cambridge UCAS integration |
| Credit/unit accumulation (American system) | |
| GPA calculation (weighted + unweighted) | |
| Predicted/target grades (Cambridge, IB) | |
| Grade equivalency mapping between systems | |
| Transcript generation | |
| 10 built-in curriculum templates | |

### Requirements Traceability

| Requirement Group | IDs | Priority | Phase |
|-------------------|-----|----------|-------|
| Curriculum Configuration | MC-001 to MC-006 | Must/Should | 1 |
| Grading Systems | MC-010 to MC-018 | Must/Should/Could | 1, 2 |
| Assessment Structures | MC-020 to MC-027 | Must/Should/Could | 1, 2, 3 |
| Report Cards | MC-030 to MC-037 | Must/Should | 2 |
| External Examinations | MC-040 to MC-046 | Must/Should/Could | 3 |

### Effort Estimate

| Metric | Value |
|--------|-------|
| New database tables | 9 |
| New enum types | 4 (+ 1 extended) |
| New backend files | ~25 |
| New frontend files | ~20 |
| Existing files to modify | ~15 |
| Pydantic schemas | ~35 |
| API endpoints | ~38 |
| Score strategy classes | 6 |
| Report card templates | 5 new |
| Test cases | 100+ |
| Phases | 3 |
| Raw effort estimate | ~94 dev-days (see risk analysis) |
| With 25% buffer | ~118 dev-days |

> **Estimate notes:** Task-level estimates sum to ~54d but exclude testing (~16d), normalization layer (~3d), analytics service update (~5d), parent portal update (~2d), and frontend uplift (~8d). The ~94d figure includes all of these. See `docs/MULTI_CURRICULUM_RISK_ANALYSIS.md` for detailed breakdown.

---

## 2. Architecture Decisions

### Decision 1: Configuration Layer, Not Parallel System

Multi-curriculum is a configuration layer on top of existing academic models. A `curriculum_profiles` table bundles a grading scale, assessment structure, and report card config. The existing `GradingScale`, `Grade`, `ExamScore`, `TermReport`, and `ContinuousAssessment` tables continue to work as-is. No existing tables are removed or restructured.

**Rationale:** Minimizes regression risk. Existing GES schools experience zero change. New curriculum features are opt-in.

### Decision 2: Strategy Pattern for Score Calculation

Score calculation is refactored from a monolithic function into a Strategy Pattern with 6 implementations: `GESScoreStrategy`, `CambridgeScoreStrategy`, `AmericanScoreStrategy`, `IBScoreStrategy`, `FrenchScoreStrategy`, `MontessoriScoreStrategy`. The existing GES logic is extracted verbatim into `GESScoreStrategy` — it is the ELSE branch (default fallback when no curriculum profile exists).

**Rationale:** Each curriculum has fundamentally different calculation rules. A strategy pattern isolates curriculum logic, makes it testable in isolation, and allows new curricula to be added by implementing a single class.

### Decision 3: Flexible N-Component Assessment Structure

The rigid 4-column `AssessmentWeight` model (class_work_weight, homework_weight, midterm_weight, end_term_weight) is supplemented by a new `assessment_structures` + `assessment_components` pair. Each structure contains N components, each with a name, type, weight, and flags indicating whether it maps to the legacy CA/Exam report columns.

**Rationale:** GES has exactly 4 components. Cambridge has 3 (Coursework + Controlled Assessment + External Exam). American has 5+ (Homework, Quizzes, Tests, Projects, Finals). IB has 2-3 (IA + EA + bonus components). A fixed-column model cannot accommodate this variation. The existing `assessment_weights` table is NOT removed — it remains the primary source for GES schools without a curriculum profile.

### Decision 4: JSONB `config` for Curriculum-Specific Settings

Each `curriculum_profiles` row has a JSONB `config` column for curriculum-specific settings (IB programme type, American GPA scale, French mention thresholds, Montessori developmental areas). This avoids creating 8 different rigid table structures or adding dozens of nullable columns.

**Rationale:** Each curriculum has unique concepts that don't overlap (e.g., only IB has "Learner Profile traits", only French has "mention categories", only American has "honor roll threshold"). JSONB keeps the schema clean while allowing per-curriculum customization.

### Decision 5: Built-in Templates as Code Constants

The system ships with 10 pre-built curriculum templates (GES Standard, Cambridge IGCSE, Cambridge A-Level, Edexcel IGCSE, American Standard, American AP, IB MYP, IB DP, French Bac, Montessori). These are Python dictionaries in service code, NOT database rows. When a school selects a template, the system creates a `curriculum_profile` + `assessment_structure` + `assessment_components` + `report_card_config` from the template.

**Rationale:** Templates should be version-controlled, not database state. This makes updates, fixes, and new templates trivially deployable. Schools can customize after instantiation without affecting the template.

### Decision 6: Backward Compatibility via Fallback

When the score engine encounters a class without a `curriculum_profile_id`:
1. It falls back to the existing `AssessmentWeight`-based GES logic
2. It uses the existing report card template
3. It uses the tenant's default grading scale
4. No new code path is executed

This is enforced by an explicit `if profile is None: return await self._get_student_subject_results_ges(...)` check in the refactored `TermReportService`.

### Decision 7: Feature Flag Gating by Subscription Tier

| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| GES curriculum (default) | Yes | Yes | Yes |
| Single non-GES curriculum | No | Yes | Yes |
| Multiple curricula (dual-track) | No | No | Yes |
| External exam management | No | Yes | Yes |
| Transcript generation | No | Yes | Yes |
| Grade equivalencies | No | No | Yes |

Check via `tenant.features` JSONB: `multi_curriculum`, `multi_curriculum_dual`, `external_exams`, `transcripts`.

**IMPORTANT — Enforcement:** Feature flags MUST be checked in the service layer, not just the frontend. Specifically:
- `CurriculumProfileService.create_profile()` and `create_from_template()` must validate that the tenant's subscription plan allows the requested `curriculum_type` (Starter = GES only) and profile count (Professional = 1 non-GES, Enterprise = unlimited).
- Without this, a Starter tenant's school_admin could call `POST /curriculum/profiles` with `curriculum_type: "cambridge"` and bypass the paywall.
- The check should query `tenant.features` and `tenant.subscription_plan` and raise `CurriculumServiceError("Feature not available on your plan", "plan_limit")` if disallowed.

### Decision 8: Single Migration per Phase

Each phase gets one migration file (except Phase 1 which has a separate data migration). This follows the admissions module pattern and ensures atomic rollback per phase.

---

## 3. Integration Architecture

```
                    ┌──────────────────────┐
                    │   curriculum_profiles │  <-- NEW central config
                    │   (per school)        │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              v                v                v
     ┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
     │ GradingScale   │ │ assessment_  │ │ report_card_     │
     │ (EXISTING,     │ │ structures   │ │ configs          │
     │  extended)     │ │ (NEW)        │ │ (NEW)            │
     └────────────────┘ └──────────────┘ └──────────────────┘
              │                │                │
              v                v                v
     ┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
     │ Grade          │ │ assessment_  │ │ TermReport       │
     │ (EXISTING)     │ │ components   │ │ (EXISTING,       │
     │                │ │ (NEW)        │ │  extended)       │
     └────────────────┘ └──────────────┘ └──────────────────┘
              │                │
              v                v
     ┌────────────────────────────────────────────┐
     │  Score Calculation Engine (refactored)      │
     │  - GES strategy (existing logic extracted)  │
     │  - Cambridge/Edexcel strategy               │
     │  - American GPA strategy                    │
     │  - IB criterion strategy                    │
     │  - French mention strategy                  │
     │  - Montessori narrative strategy            │
     └────────────────────────────────────────────┘
```

### Curriculum Resolution Chain

When the system needs to determine which curriculum applies to a student:

```
1. Check student.curriculum_profile_id       → if set, use it
2. Check class.curriculum_profile_id         → if set, use it (dual-track)
3. Check school.curriculum_profile_id        → if set, use it (school default)
4. No profile found                          → fall back to GES logic
```

This 3-level resolution allows:
- **Single-curriculum schools:** Set on school, all classes inherit
- **Dual-track schools:** Override per class (e.g., IGCSE stream vs GES stream)
- **Transfer students:** Override per student if their curriculum differs from class

---

## 4. Phase Overview

| Phase | Title | New Tables | Endpoints | Key Deliverables |
|-------|-------|------------|-----------|------------------|
| **Phase 1** | Foundation — Profiles, Assessment Structures, Class Assignment | 4 | 17 | Curriculum profiles, assessment structures, class assignment, built-in templates, profile wizard UI |
| **Phase 2** | Grading, Score Engine, Report Cards | 2 | 9 | Score strategies (6), report card templates (5), grade equivalencies, subject mappings |
| **Phase 3** | External Exams, Credits, Transcripts | 3 | 16 | WAEC/Cambridge registration, CSV import, GPA/credits, transcripts, predicted grades |

### Cross-Phase Dependencies

```
Phase 1 ──────────> Phase 2 ──────────> Phase 3
  │                   │                   │
  │ curriculum_       │ score strategies  │ external exams (partially
  │ profiles must     │ must exist before │ independent — doesn't
  │ exist before      │ Phase 3 can       │ depend on score strategies)
  │ strategies can    │ generate          │
  │ reference them    │ curriculum-aware  │
  │                   │ transcripts       │
  └───────────────────┴───────────────────┘
```

Phase 3's external exam and predicted grade features are partially independent of Phase 2 (they don't depend on score strategies), but credit accumulation and transcript generation do depend on Phase 2's GPA calculation.

---

## 5. Files Affected — Complete Manifest

### New Files (Backend)

| File | Phase | Purpose |
|------|-------|---------|
| `backend/app/models/curriculum.py` | 1 | All curriculum SQLAlchemy models |
| `backend/app/schemas/curriculum.py` | 1 | All curriculum Pydantic schemas |
| `backend/app/services/curriculum/__init__.py` | 1 | Package init with re-exports |
| `backend/app/services/curriculum/_shared.py` | 1 | CurriculumServiceError class |
| `backend/app/services/curriculum/profile_service.py` | 1 | Profile CRUD, template instantiation |
| `backend/app/services/curriculum/assessment_service.py` | 1 | Assessment structure/component management |
| `backend/app/services/curriculum/equivalency_service.py` | 2 | Grade equivalency mapping |
| `backend/app/services/curriculum/subject_mapping_service.py` | 2 | Subject-to-curriculum mapping |
| `backend/app/services/curriculum/external_exam_service.py` | 3 | External exam registration/results |
| `backend/app/services/curriculum/credit_service.py` | 3 | Credit accumulation and GPA |
| `backend/app/services/curriculum/predicted_grade_service.py` | 3 | Predicted/target grades |
| `backend/app/services/exam/score_strategies.py` | 2 | Strategy pattern classes (6 strategies) |
| `backend/app/api/v1/endpoints/curriculum/__init__.py` | 1 | Combined router |
| `backend/app/api/v1/endpoints/curriculum/profiles.py` | 1 | Profile endpoints |
| `backend/app/api/v1/endpoints/curriculum/assessment.py` | 1 | Assessment structure endpoints |
| `backend/app/api/v1/endpoints/curriculum/equivalencies.py` | 2 | Grade equivalency endpoints |
| `backend/app/api/v1/endpoints/curriculum/subject_mappings.py` | 2 | Subject mapping endpoints |
| `backend/app/api/v1/endpoints/curriculum/external_exams.py` | 3 | External exam endpoints |
| `backend/app/api/v1/endpoints/curriculum/credits.py` | 3 | Credit/GPA endpoints |
| `backend/app/api/v1/endpoints/curriculum/predicted_grades.py` | 3 | Predicted grade endpoints |
| `backend/app/templates/reports/cambridge_report.html` | 2 | Cambridge report card template |
| `backend/app/templates/reports/american_report.html` | 2 | American report card template |
| `backend/app/templates/reports/ib_report.html` | 2 | IB report card template |
| `backend/app/templates/reports/french_report.html` | 2 | French report card template |
| `backend/app/templates/reports/montessori_report.html` | 2 | Montessori report card template |
| `backend/alembic/versions/20260310_0100_curriculum_foundation.py` | 1 | Tables + enums + RLS |
| `backend/alembic/versions/20260310_0200_curriculum_data_migration.py` | 1 | GES default profiles for existing tenants |
| `backend/alembic/versions/20260315_0100_grading_and_equivalencies.py` | 2 | Phase 2 tables + column additions |
| `backend/alembic/versions/20260320_0100_external_exams_and_credits.py` | 3 | Phase 3 tables |
| `backend/tests/test_curriculum_profiles.py` | 1 | Profile CRUD tests |
| `backend/tests/test_assessment_structures.py` | 1 | Assessment structure tests |
| `backend/tests/test_curriculum_rls.py` | 1 | RLS isolation tests |
| `backend/tests/test_score_strategies.py` | 2 | Strategy unit tests + GES regression |
| `backend/tests/test_grade_equivalencies.py` | 2 | Equivalency tests |
| `backend/tests/test_external_exams.py` | 3 | External exam tests |
| `backend/tests/test_credits_gpa.py` | 3 | Credit/GPA calculation tests |

### Modified Files (Backend)

| File | Phase | Change |
|------|-------|--------|
| `backend/app/models/__init__.py` | 1 | Import curriculum models |
| `backend/app/models/academic/subject_models.py` | 1, 2 | Extend `GradingScaleType` enum; add `curriculum_profile_id` to `GradingScale`; add `credit_value`, `coefficient` to `Subject` |
| `backend/app/models/academic/class_models.py` | 1 | Add `curriculum_profile_id` to `Class` |
| `backend/app/models/school.py` | 1 | Add `curriculum_profile_id`, `curriculum_settings` to `School` |
| `backend/app/models/student.py` | 1 | Add `curriculum_profile_id`, `previous_curriculum_type` to `Student` |
| `backend/app/models/exam.py` | 2 | Add `effort_grade` to `ExamScore`; add curriculum fields to `TermReport` |
| `backend/app/services/exam/report_service.py` | 2 | Add strategy dispatch, `_resolve_curriculum_profile()` |
| `backend/app/services/exam/score_service.py` | 2 | Add `effort_grade` handling in score entry |
| `backend/app/api/v1/router.py` | 1 | Include curriculum router |
| `backend/app/schemas/academic.py` | 1 | Add `curriculum_profile_id` to class schemas |
| `backend/app/schemas/exam.py` | 2 | Add curriculum fields to report schemas |
| `backend/tests/conftest.py` | 1, 2, 3 | Add 9 tables to `TENANT_SCOPED_TABLES` |
| `backend/scripts/verify_rls.py` | 1 | Add new tables to RLS verification |

### New Files (Frontend)

| File | Phase | Purpose |
|------|-------|---------|
| `frontend/actions/curriculum.action.ts` | 1 | Profile + assessment structure server actions |
| `frontend/actions/external-exams.action.ts` | 3 | External exam server actions |
| `frontend/actions/credits.action.ts` | 3 | Credit/GPA server actions |
| `frontend/actions/predicted-grades.action.ts` | 3 | Predicted grade server actions |
| `frontend/types/curriculum.type.ts` | 1 | TypeScript type definitions |
| `frontend/app/(dashboard)/settings/curriculum/page.tsx` | 1 | Curriculum settings overview |
| `frontend/app/(dashboard)/settings/curriculum/profiles/page.tsx` | 1 | Profile list |
| `frontend/app/(dashboard)/settings/curriculum/profiles/new/page.tsx` | 1 | Create profile wizard |
| `frontend/app/(dashboard)/settings/curriculum/profiles/[id]/page.tsx` | 1 | Edit profile |
| `frontend/app/(dashboard)/settings/curriculum/profiles/[id]/assessment/page.tsx` | 1 | Assessment structure editor |
| `frontend/app/(dashboard)/settings/curriculum/profiles/[id]/report-config/page.tsx` | 2 | Report card config |
| `frontend/app/(dashboard)/settings/curriculum/grade-equivalencies/page.tsx` | 2 | Grade mapping tool |
| `frontend/app/(dashboard)/settings/curriculum/subject-mappings/page.tsx` | 2 | Subject mapping |
| `frontend/app/(dashboard)/exams/external/page.tsx` | 3 | External exam registrations |
| `frontend/app/(dashboard)/exams/external/register/page.tsx` | 3 | Registration form |
| `frontend/app/(dashboard)/exams/external/results/page.tsx` | 3 | Import results |
| `frontend/app/(dashboard)/exams/external/export/page.tsx` | 3 | Export registration data |
| `frontend/app/(dashboard)/students/[id]/transcript/page.tsx` | 3 | Transcript view |
| `frontend/components/curriculum/CurriculumProfileWizard.tsx` | 1 | Step-by-step profile creation |
| `frontend/components/curriculum/AssessmentStructureEditor.tsx` | 1 | Weight editor |
| `frontend/components/curriculum/CurriculumSelector.tsx` | 1 | Profile dropdown |
| `frontend/components/curriculum/TemplateSelector.tsx` | 1 | Built-in template chooser |
| `frontend/components/curriculum/ReportCardPreview.tsx` | 2 | Live report preview |
| `frontend/components/curriculum/GradeEquivalencyMatrix.tsx` | 2 | Grade mapping grid |
| `frontend/components/curriculum/SubjectMappingTable.tsx` | 2 | Bulk subject mapping |

### Modified Files (Frontend)

| File | Phase | Change |
|------|-------|--------|
| `frontend/app/(dashboard)/settings/page.tsx` | 1 | Add curriculum settings link |
| `frontend/components/dashboard/app-sidebar.tsx` | 1 | Add curriculum menu items |
| `frontend/types/index.ts` | 1 | Add curriculum-related types |
| `frontend/app/(dashboard)/classes/` | 1 | Add curriculum selector to class forms |

---

## 6. TENANT_SCOPED_TABLES Update

After all 3 phases, add to `backend/tests/conftest.py` TENANT_SCOPED_TABLES:

```python
# Multi-Curriculum (Phases 1-3)
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

Current count: **91 tables** (verified from `conftest.py` as of Sprint 20). After multi-curriculum: **100 tables**.

---

## 7. Risk Assessment

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Score calculation regression for GES schools | Critical — incorrect report cards | Exhaustive regression test suite; GES path is the ELSE branch (unchanged code); canary deployment with side-by-side score comparison |
| `calculate_student_term_scores()` not strategy-dispatched | Critical — incorrect non-GES term reports | This 200-line method in report_service.py populates `TermReport.total_score` and `TermReport.average_score` and MUST also be dispatched through the strategy pattern (see Task 4.10) |
| Report service fetch+calculate coupling | High — strategies need a normalization layer | Current code fetches data AND calculates in one method; strategies need pre-fetched, normalized inputs. Add ~3 days for normalization layer in Task 4.10 |
| Batch optimization loss in strategy refactor | High — N+1 regressions for large classes | Current GES code uses batch queries (`_batch_get_all_scores`, `_batch_calculate_subject_positions`). Strategy dispatch must preserve batch-level operations, not dispatch per-student. Design the strategy interface to accept batch inputs. |
| `ALTER TYPE ADD VALUE` is irreversible | Low — cannot roll back enum extension | Acceptable; adding enum values is backward-compatible; no need to remove values |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dual-track class assignment complexity | Medium — teacher/parent confusion | Clear UI labeling; validation that student curriculum matches class curriculum; prevent mismatch at enrollment |
| Report card template proliferation | Medium — maintenance burden | Shared Jinja2 macros for common sections (header, footer, attendance); only curriculum-specific sections differ |
| External exam result import parsing failures | Medium — data quality | Preview mode before commit; validation with clear error messages; row-level error reporting |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Montessori narrative reports require free-text | Low — different UX pattern | Reuse preschool observation module patterns; extend with narrative input |
| IB criterion-based grading is complex | Low — only IB schools | JSONB config holds criterion definitions; UI builds rubric entry dynamically |
| Grade equivalency accuracy | Low — advisory feature | Mark as "approximate" in UI; allow school to customize all mappings |

### Known Downstream Dependencies

These existing services contain GES-specific logic that MUST be updated for multi-curriculum support. They are **not listed in the task tables** but are included in the effort estimate:

| File | Issue | Est. Effort |
|------|-------|-------------|
| `backend/app/services/parent/parent_academic.py` | `get_child_grades()` has independent GES-specific score calculation — does NOT call `report_service.py`. Will show GES-formatted grades for non-GES students. Must use strategy dispatch. | ~2d |
| `backend/app/services/exam/analytics_service.py` (815 lines) | Assumes percentage-based GES scoring throughout. Will produce incorrect analytics for non-GES curricula. Not mentioned in any spec task. | ~5d |
| `backend/app/services/pdf.py:291` | Third caller of `get_student_subject_results()` — spec task 4.10 only accounts for two callers. Must be updated for strategy dispatch. | Included in 4.10 |
| `backend/app/services/exam/report_service.py` | Two redundant position calculation methods: `_batch_calculate_subject_positions` (batch) and `_calculate_subject_positions` (per-subject). Strategy refactor should consolidate. | Included in 4.10 |

---

## 8. Open Questions

1. **Montessori observation integration:** Should Montessori narrative assessments reuse the existing preschool `student_observations` model, or create a separate mechanism? **Recommendation:** Reuse preschool observations for preschool Montessori; use `exam_scores.teacher_remark` with narrative-type curriculum profiles for older students.

2. **IB CAS tracking depth:** Is a lightweight tracker (hours + description) sufficient, or do we need a full CAS portfolio? **Recommendation:** Start with hours + description in `assessment_components.config` JSONB; defer full portfolio to a future sprint.

3. **External exam result format:** Do we have sample WAEC BECE/WASSCE result files and Cambridge Statement of Results for parser development? **Action needed:** Obtain sample files before Phase 3 starts.

4. **French coefficient system:** Should coefficients multiply the score before averaging (true French system) or multiply the weight? **Recommendation:** Store coefficient on `subject_curriculum_mappings.coefficient`; the French strategy multiplies `score * coefficient` before averaging, matching the authentic system.

5. **Transcript format:** Is there a standard transcript format required by Ghana universities or international institutions? **Action needed:** Research requirements before Phase 3.
