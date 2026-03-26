# Multi-Curriculum Gap Closure: Overview

**Date:** 2026-03-23
**Author:** Harry McNinson
**Status:** Ready for Implementation
**Predecessor:** `spec/multi-curriculum/` (Phases 1-3, fully implemented)

---

## Executive Summary

The multi-curriculum infrastructure (9 database tables, 7 services, 50+ endpoints, 6 score strategies, 6 report templates, full frontend) was built across Phases 1-3 and is approximately 85% complete. This gap closure plan addresses the remaining 15% — primarily **integration wiring** between components that were built in isolation.

The single most impactful issue is that `generate_term_reports()` in `report_service.py` never calls `calculate_aggregate()` on the score strategies and never populates the curriculum-specific columns on `TermReport` (GPA, IB total points, French mention, honor roll, credits). All downstream consumers (PDF generation, parent portal, analytics) inherit this gap.

---

## Gap Categories

| Category | Gap Count | Priority | Estimated Effort |
|----------|-----------|----------|-----------------|
| Report Generation Bridge | 4 tasks | Critical | 1.5-2 weeks |
| Score Entry Enhancements | 3 tasks | High | 1 week |
| Parent Portal Adaptation | 3 tasks | High | 1.5 weeks |
| Analytics Curriculum Awareness | 2 tasks | Medium | 0.5 weeks |
| Academic Calendar Validation | 1 task | Medium | 0.5 weeks |
| Montessori Narrative System | 3 tasks | Medium | 2 weeks |
| Dual-Track Reporting | 3 tasks | Medium | 1.5 weeks |
| Mock Exam Integration | 2 tasks | Low-Medium | 1 week |
| Export Format Extensions | 2 tasks | Low | 0.5 weeks |
| Criterion-Referenced Grading | 2 tasks | Low | 1.5 weeks |
| **Total** | **25 tasks** | | **~11-12 weeks raw (~7 calendar weeks with 2 developers)** |

> **Effort revised (2026-03-23):** Original estimate was 9 weeks. After code review
> revealed additional complexity (grade_point population, weighted_gpa extension,
> mandatory pre-computation for subject positions, hybrid parent portal approach),
> revised to 11-12 weeks raw effort. With 2 developers working in parallel on
> independent phases, this compresses to ~7 calendar weeks.

---

## Requirements Traceability

### Fully Implemented (No Action Required) — 23 of 37

| ID | Requirement | Evidence |
|----|-------------|----------|
| MC-001 | School-level curriculum selection | `School.curriculum_profile_id` FK, profile CRUD endpoints |
| MC-002 | Class-level curriculum assignment | `Class.curriculum_profile_id` FK, `_resolve_curriculum_profile()` checks class |
| MC-003 | Student-level curriculum tracking | `Student.curriculum_profile_id` FK + `previous_curriculum_type` column |
| MC-004 | Custom curriculum definition | `CurriculumType.CUSTOM` enum, maps to GESScoreStrategy default |
| MC-006 | Subject mapping across curricula | `SubjectCurriculumMapping` model, full CRUD service + endpoints |
| MC-010 | Multiple grading scales per school | `CurriculumProfile.grading_scale_id` FK, per-profile scale resolution |
| MC-011 | Ghana GES scale | `GESScoreStrategy` with CA/Exam split, WAEC A1-F9 |
| MC-012 | Cambridge/Edexcel scale | `CambridgeScoreStrategy`, A*-G grading, effort grades in model |
| MC-018 | Grade equivalency mapping | `GradeEquivalency` model, `convert_grade()` method, full CRUD |
| MC-020 | Configurable assessment components | `AssessmentStructure` + `AssessmentComponent` with 26 component types |
| MC-021 | GES CA + Exam weighting | Legacy path + GES strategy with `maps_to_ca`/`maps_to_exam` flags |
| MC-022 | Cambridge assessment structure | COURSEWORK, CONTROLLED_ASSESSMENT, EXTERNAL_EXAM component types |
| MC-023 | IB assessment structure | INTERNAL_ASSESSMENT, EXTERNAL_ASSESSMENT, EXTENDED_ESSAY, TOK, CAS |
| MC-024 | American assessment weighting | QUIZ, TEST, PROJECT, PARTICIPATION, FINAL component types |
| MC-025 | Predicted grades tracking | `PredictedGrade` model, full CRUD, frontend page |
| MC-027 | Credit/unit accumulation | `StudentCreditAccumulation` model, GPA calc, transcript generation |
| MC-030 | Curriculum-specific templates | 6 HTML templates, `REPORT_TEMPLATES` mapping, template dispatch |
| MC-031 | GES report card | `term_report.html` with scores, grades, position, rankings |
| MC-037 | Transcript generation | `transcript.html` template, `CreditService.generate_transcript_data()` |
| MC-040 | WAEC registration export | `ExternalExamService.export_waec()` with CSV format |
| MC-041 | Cambridge registration support | `ExternalExamService.export_cambridge()` with component codes |
| MC-044 | External exam results import | `import_results_csv()` with WAEC/Cambridge CSV formats |
| MC-045 | Exam centre/candidate tracking | `candidate_number`, `center_number` columns on registration model |

### Partially Implemented (Gap Closure Required) — 13 of 37

| ID | Requirement | What Exists | What's Missing | Phase |
|----|-------------|-------------|----------------|-------|
| MC-005 | Curriculum-specific calendar | `academic_calendar_type`, `periods_per_year` columns | No validation in term creation | Phase 3 |
| MC-013 | American letter grades | `AmericanScoreStrategy` implemented | Works, but report never shows GPA (bridge gap) | Phase 1 |
| MC-014 | American GPA calculation | Strategy computes GPA, TermReport has columns | `generate_term_reports` never calls `calculate_aggregate()` | Phase 1 |
| MC-015 | IB scale 1-7 | `IBScoreStrategy` computes IB total | `ib_total_points` never set on TermReport | Phase 1 |
| MC-016 | French 0-20 with mentions | `FrenchScoreStrategy` computes mention | `french_mention` never set on TermReport | Phase 1 |
| MC-017 | Montessori narrative assessment | Strategy exists, template exists | No narrative entry workflow, template context all None | Phase 4 |
| MC-032 | Cambridge effort grades | `effort_grade` column on ExamScore, template references it | Score entry form doesn't accept effort_grade | Phase 2 |
| MC-033 | American report with GPA | Template exists, columns exist | PDF context passes `term_gpa=None` always | Phase 1 |
| MC-034 | IB report with ATL/Learner Profile | Template exists, columns exist | PDF context passes all None; no ATL/LP data model | Phase 1 |
| MC-035 | Montessori narrative report | Template exists | Template context all None; no data model for narratives | Phase 4 |
| MC-042 | Edexcel export format | Enum value exists, registration CRUD works | No Edexcel-specific export format | Phase 6 |
| MC-043 | IB export format | Enum value exists, registration CRUD works | No IB-specific export format | Phase 6 |
| MC-046 | Mock exam curriculum integration | `ExamType.MOCK` exists, mocks scored normally | No curriculum component pre-population, no predicted grade link | Phase 5 |

### Not Implemented — 1 of 37

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| MC-026 | Criterion-referenced assessment (IB MYP rubrics) | Could | Phase 7 |
| MC-036 | Dual-track report (GES + international) | Should | Phase 4 |

---

## Phase Overview

| Phase | Title | Tasks | Effort | Dependencies | Priority |
|-------|-------|-------|--------|--------------|----------|
| 1 | Report Generation Bridge | 4 | 1.5-2 weeks | None | Critical |
| 2 | Score Entry Enhancements | 3 | 1 week | None (parallel with Phase 1) |
| 3 | Parent Portal + Analytics | 5 | 1.5 weeks | Phase 1 |
| 4 | Montessori + Dual-Track | 6 | 2.5 weeks | Phase 1 |
| 5 | Mock Exam + Calendar Validation | 3 | 1 week | None |
| 6 | Export Format Extensions | 2 | 0.5 weeks | None |
| 7 | Criterion-Referenced Grading | 2 | 1.5 weeks | Phase 1 |

**Phases 1 and 2 can run in parallel.** Phase 3 depends on Phase 1. Phase 4 depends on Phase 1. Phases 5-7 are independent.

---

## Architecture Context

### Curriculum Resolution Chain (existing, works correctly)

```
Student.curriculum_profile_id  →  if set, use it
         ↓ (NULL)
Class.curriculum_profile_id    →  if set, use it (dual-track)
         ↓ (NULL)
School.curriculum_profile_id   →  if set, use it (school default)
         ↓ (NULL)
None                           →  fall back to legacy GES path
```

Implemented in `report_service.py:_resolve_curriculum_profile()` (lines 59-110).

### Score Strategy Dispatch (existing, works correctly)

```python
# score_strategies.py:get_score_strategy() (line 426-444)
STRATEGY_MAP = {
    "ges": GESScoreStrategy,
    "cambridge": CambridgeScoreStrategy,
    "edexcel": CambridgeScoreStrategy,  # same calculation logic
    "american": AmericanScoreStrategy,
    "ib": IBScoreStrategy,
    "french": FrenchScoreStrategy,
    "montessori": MontessoriScoreStrategy,
    "custom": GESScoreStrategy,  # default fallback
}
```

### The Broken Bridge (the primary gap)

```
┌──────────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  ScoreStrategy       │     │  generate_term_      │     │  TermReport      │
│                      │     │  reports()           │     │  model           │
│  calculate_subject   │────▶│                      │────▶│                  │
│  _score() ✓ CALLED   │     │  total_score ✓       │     │  total_score ✓   │
│                      │     │  average_score ✓     │     │  average_score ✓ │
│  calculate_aggregate │     │                      │     │                  │
│  () ✗ NEVER CALLED   │     │  gpa ✗ NOT SET       │     │  gpa = NULL      │
│                      │     │  ib_total ✗ NOT SET  │     │  ib_total = NULL │
│  Returns: GPA, IB    │     │  honor_roll ✗ NOT SET│     │  honor_roll=NULL │
│  total, mention,     │     │  mention ✗ NOT SET   │     │  mention = NULL  │
│  honor_roll          │     │  credits ✗ NOT SET   │     │  credits = NULL  │
└──────────────────────┘     └─────────────────────┘     └──────────────────┘
                                      │
                                      ▼
                             ┌─────────────────────┐
                             │  pdf.py:generate_    │
                             │  term_report_pdf()   │
                             │                      │
                             │  term_gpa = None ✗   │
                             │  honor_roll = None ✗ │
                             │  ib_total = None ✗   │
                             │  mention = None ✗    │
                             └─────────────────────┘
```

**After gap closure:**

```
ScoreStrategy.calculate_subject_score()  →  per-subject scores  →  TermReport.total_score
ScoreStrategy.calculate_aggregate()      →  GPA/IB/mention      →  TermReport.gpa, .ib_total_points, etc.
                                                                         │
pdf.py reads TermReport fields  ←────────────────────────────────────────┘
```

---

## File Index

| Document | Contents |
|----------|----------|
| `00-overview.md` | This file — summary, traceability, architecture context |
| `01-phase-1-report-bridge.md` | Critical: Wire score strategies into report generation |
| `02-phase-2-score-entry.md` | Effort grades, curriculum-aware score entry |
| `03-phase-3-parent-analytics.md` | Parent portal + analytics curriculum awareness |
| `04-phase-4-montessori-dualtrack.md` | Montessori narrative system + dual-track reports |
| `05-phase-5-mock-calendar.md` | Mock exam integration + calendar validation |
| `06-phase-6-7-extensions.md` | Export formats + criterion-referenced grading |
| `07-testing.md` | Test plan across all phases |
| `08-verification-checklist.md` | Requirement-by-requirement verification checklist |

---

## Review Findings Summary (2026-03-23)

This plan was reviewed by 5 independent agents (code reviewer, security auditor, risk analyst, solution architect, tenancy architect). All critical issues have been fixed inline (marked with `>>REVIEW FIX`). Key corrections applied:

### Critical Fixes (would have caused runtime errors)
| ID | Issue | Fix Applied In |
|----|-------|----------------|
| C1 | `_resolve_curriculum_profile()` called with wrong argument order (student_id passed as class_id) | 01-phase-1, 04-phase-4 |
| C2 | `subject_results` list does not exist in `_calculate_student_term_scores_curriculum()` — must be explicitly created | 01-phase-1, Step 1 |
| C3 | Redundant `_resolve_curriculum_profile()` call would add 50 unnecessary DB queries per class | 01-phase-1, Step 4 (profile now returned in tuple) |
| C4 | `academic_year_id` not passed through call chain — year-specific assessment structures wouldn't resolve | 01-phase-1, Step 3 |
| R1 | `strategy.determine_grade()` never called — `grade_point` always None — GPA always None | 01-phase-1, Step 1 |
| R3 | `weighted_gpa` key doesn't exist in `AmericanScoreStrategy.calculate_aggregate()` return | 01-phase-1, Step 5 + prerequisite |

### High Severity Fixes (security/architecture)
| ID | Issue | Fix Applied In |
|----|-------|----------------|
| H1 | HTML stripping via regex is trivially bypassable — replaced with `nh3.clean()` | 04-phase-4 |
| H2 | Mock→predicted grades silently overwrites manual predictions — added source checking | 05-phase-5 |
| H3 | Missing `check_multi_curriculum_access()` on Montessori and mock→predicted endpoints | 04-phase-4, 05-phase-5 |
| H4 | Dual-track detection used two flags — reduced to single canonical source (`template_key`) | 04-phase-4 |
| H2-parent | Parent portal "read from TermReport" creates timing inconsistency — use hybrid approach | 03-phase-3 |

### Medium Severity Fixes (design/scalability)
| ID | Issue | Fix Applied In |
|----|-------|----------------|
| M1 | Subject position pre-computation changed from optional to mandatory | 01-phase-1, Task A3 |
| M4 | Calendar validation warning check moved from service to endpoint handler | 05-phase-5 |
| M5 | Effort grade regex `^[1-5A-Ea-e]$` too restrictive — relaxed to `max_length=10` | 02-phase-2 |
| L4 | Frontend Montessori used `useQuery` — corrected to Server Action pattern | 04-phase-4 |

### Known Remaining Items (not blocking, documented as future work)
- Defense-in-depth: `Grade.tenant_id` and `Subject.tenant_id` filters missing in curriculum-path queries in report_service.py (pre-existing, not introduced by gap closure — RLS protects at DB level)
- Cumulative GPA uses simple average, not credit-weighted (acceptable for Phase 1)
- No curriculum change audit log (add before production with real schools)
- N+1 query pattern in curriculum scoring path (pre-existing performance debt)
