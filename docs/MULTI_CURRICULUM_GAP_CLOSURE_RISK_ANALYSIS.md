# Multi-Curriculum Gap Closure -- Risk Analysis

**Analyst:** Risk Analyst Agent
**Date:** 2026-03-23
**Spec Reviewed:** `spec/multi-curriculum-gap-closure/` documents 00 through 08
**Previous Analysis:** `docs/MULTI_CURRICULUM_RISK_ANALYSIS.md` (2026-03-06, original multi-curriculum)
**Codebase Files Reviewed:** `report_service.py` (1866 lines), `score_strategies.py` (444 lines), `pdf.py` (551 lines), `analytics_service.py` (815 lines), `parent_academic.py` (528 lines), `exam.py` models, `exam.py` schemas
**Complexity Rating:** 6/10 (gap closure, not greenfield -- but critical-path code is involved)

---

## Executive Summary

This gap closure plan is well-structured and identifies the right problems: the "broken bridge" between score strategies and report generation is real, effort grades are unsaved, and parent/analytics are GES-hardcoded. However, the plan contains **3 bugs that will produce runtime failures** (grade_point never populated for aggregate calculation, weighted_gpa referenced but not produced, subject_results list not collected), has **optimistic estimates for Phase 1 and Phase 4**, and underestimates the **performance impact of Task A3** (subject positions in curriculum path). The total 9-week estimate is achievable with 2 developers working in parallel on independent tracks, but not with 1 developer working serially.

**Realistic total:** 12-14 developer-weeks (not 9), or ~7-8 calendar weeks with 2 developers.

---

## 1. Effort Estimate Assessment

### Phase 1: Report Generation Bridge (Spec: 1 week)

| Task | Spec Est | Revised | Rationale |
|------|----------|---------|-----------|
| A1: Populate aggregate fields | 2d | 3d | Must fix grade_point bug (see R1), collect subject_results list, add cumulative GPA query, handle edge cases (no prior reports, deleted reports) |
| A2: Wire PDF template context | 0.5d | 0.5d | Agree -- straightforward replacement of None values |
| A3: Subject position calculation | 1.5d | 3d | Requires computing ALL students' scores per subject per class. The spec acknowledges this but underestimates. Must build in-memory ranking, handle tied scores, handle absent students. For bulk report generation, this is O(students * subjects) strategy calls per class, not per student |
| A4: Tests | 1d | 2d | 8 test cases with complex setup fixtures (curriculum profile + grading scale + assessment structure + components + students + exam + scores). Each test needs ~30 lines of setup |
| **Total** | **5d** | **8.5d** |  |

**Verdict:** Phase 1 will take 1.5-2 weeks, not 1 week. Task A1 has a critical bug that will cause debugging time, and Task A3 is a performance-sensitive method that needs careful implementation and caching for bulk generation.

### Phase 2: Score Entry Enhancements (Spec: 1 week)

| Task | Spec Est | Revised | Rationale |
|------|----------|---------|-----------|
| B1: Add effort_grade to ScoreEntry | 1d | 1d | Agree -- schema + service change is small |
| B2: Wire effort_grade into strategy | 0.5d | 1d | Must trace where ExamScore records are loaded in the curriculum result-building path and extract effort_grade. Currently effort_grade is never read from DB in the curriculum path |
| B3: Frontend conditional column | 1.5d | 2d | Select dropdown, conditional rendering, mobile responsiveness, server action update |
| Tests | 0.5d | 1d | 6 test cases |
| **Total** | **3.5d** | **5d** |  |

**Verdict:** Phase 2 is roughly 1 week. Reasonable estimate. Can truly run in parallel with Phase 1.

### Phase 3: Parent Portal + Analytics (Spec: 1.5 weeks)

| Task | Spec Est | Revised | Rationale |
|------|----------|---------|-----------|
| C1: get_child_grades curriculum-aware | 2d | 2.5d | The simpler approach (read from TermReport) is correct but depends on Phase 1 being complete and reports being generated. Need fallback for when reports don't exist yet |
| C2: Grade trend | 0.5d | 0.5d | Agree -- branching on curriculum_type is straightforward |
| C3: Frontend parent portal | 2d | 2.5d | GradeSummaryCard switch + grade trend chart with dynamic Y-axis |
| D1: Analytics curriculum-aware | 1d | 1.5d | Two hardcoded 50% pass marks to replace, plus Montessori null handling |
| D2: Analytics API response | 0.5d | 0.5d | Schema additions |
| Tests | 0.5d | 1.5d | 14 test cases across 2 files |
| **Total** | **7d** | **9d** |  |

**Verdict:** Phase 3 is roughly 2 weeks, not 1.5. The dependency on Phase 1 is real -- if Phase 1 slips, Phase 3 slips.

### Phase 4: Montessori + Dual-Track (Spec: 2 weeks)

| Task | Spec Est | Revised | Rationale |
|------|----------|---------|-----------|
| F1: Montessori narrative endpoint | 2d | 2d | JSONB approach avoids new tables -- good decision |
| F2: Montessori PDF wiring | 0.5d | 1d | Must verify montessori_report.html template actually renders with the data shape. WeasyPrint rendering of rich text/narrative is untested in this codebase |
| F3: Montessori frontend | 3d | 4d | Complex form: accordion with dynamic skill lists, multiple textareas, work samples dynamic list, goals list, auto-save. React Hook Form with nested field arrays is consistently 30% underestimated |
| G1: Dual-track template | 1d | 1.5d | Two result tables + combined summary. Print-friendly A4 layout with two tables is tricky |
| G2: Dual-track generation logic | 1.5d | 2.5d | Calling BOTH legacy and curriculum paths for same student doubles the DB queries. Must handle case where GES exam data and international exam data are for DIFFERENT exams. Edge case: same subject in both tracks |
| G3: Template mapping + config | 0.5d | 0.5d | Simple |
| Tests | 1d | 2d | 16 test cases across 2 files |
| **Total** | **10d** | **13.5d** |  |

**Verdict:** Phase 4 is 2.5-3 weeks, not 2. The Montessori frontend is the bottleneck.

### Phases 5-7 (Spec: 3 weeks total)

| Phase | Spec Est | Revised | Notes |
|-------|----------|---------|-------|
| Phase 5: Mock + Calendar | 5d | 6d | Mock-to-predicted-grades is well-specified |
| Phase 6: Export extensions | 2.5d | 3d | Two new export methods, low risk |
| Phase 7: Criterion grading | 7.5d | 9d | New migration + JSONB schema + criterion UI is medium complexity |
| **Total** | **15d** | **18d** |  |

### Overall Estimate Summary

| Phase | Spec | Revised Raw | With 25% Buffer |
|-------|------|-------------|-----------------|
| 1: Report Bridge | 5d | 8.5d | 10.5d |
| 2: Score Entry | 3.5d | 5d | 6d |
| 3: Parent + Analytics | 7d | 9d | 11d |
| 4: Montessori + Dual-Track | 10d | 13.5d | 17d |
| 5: Mock + Calendar | 5d | 6d | 7.5d |
| 6: Export Extensions | 2.5d | 3d | 4d |
| 7: Criterion Grading | 7.5d | 9d | 11d |
| **Total** | **40.5d** | **54d** | **67d** |

**Spec says 9 weeks. Revised: ~11 weeks raw, ~13.5 weeks with buffer.**

**Confidence Level:** Medium-High. The gap closure plan is better-scoped than the original multi-curriculum spec because most of the infrastructure is already built. The main uncertainty is in Phase 1 (critical path) and Phase 4 (frontend complexity).

---

## 2. Risk Register

### Critical Bugs in Spec

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Document to Update |
|----|------|----------|----------|-------------|--------|------------|--------------------|
| R1 | **grade_point never set in _calculate_student_term_scores_curriculum().** The spec says to collect `subject_results` from strategy calls and pass to `calculate_aggregate()`. But `calculate_subject_score()` does NOT call `determine_grade()` or set `result.grade_point`. The `calculate_aggregate()` method checks `result.grade_point` (line 242 of score_strategies.py). Every `grade_point` will be `None`, so GPA will always be `None`, honor_roll always `False`, and credits_earned always `0`. | Technical | **Critical** | **Certain** | GPA never computed; American reports permanently broken | **Must add** `determine_grade()` call per subject INSIDE `_calculate_student_term_scores_curriculum()` after `calculate_subject_score()`, and set `result.grade_point` before appending to list. Requires grades list to be loaded in that method (currently only loaded in `_get_student_subject_results_curriculum`). | `01-phase-1-report-bridge.md` Task A1 Step 1 |
| R2 | **subject_results list not collected.** The spec says to call `strategy.calculate_aggregate(subject_results, profile)` but the current `_calculate_student_term_scores_curriculum()` does not accumulate `SubjectScoreResult` objects into a list. Only `result.final_score` is extracted (line 352-354). A new list variable must be created and results appended. | Technical | **High** | **Certain** | Code will crash with NameError if not fixed | Add `subject_results_list = []` before the loop, append `result` after `calculate_subject_score()` call, pass to `calculate_aggregate()`. | `01-phase-1-report-bridge.md` Task A1 Step 1 |
| R3 | **weighted_gpa referenced but not produced.** The spec (Task A1 Step 5) says `report.weighted_gpa = aggregate_data["weighted_gpa"]`. But `AmericanScoreStrategy.calculate_aggregate()` does NOT return `weighted_gpa` (only returns `gpa`, `total_credits_earned`, `honor_roll`). | Technical | **Medium** | **Certain** | `weighted_gpa` column stays NULL on TermReport. Not a crash (dict.get returns None), but the American report template will show no weighted GPA. | Either add `weighted_gpa` computation to `AmericanScoreStrategy.calculate_aggregate()` (requires AP/Honors course metadata not currently available per-subject), or remove references to `weighted_gpa` from the spec and template. | `01-phase-1-report-bridge.md` Task A1 Steps 5-6, `score_strategies.py` |

### Return Signature Change Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Document to Update |
|----|------|----------|----------|-------------|--------|------------|--------------------|
| R4 | **3-tuple to 4-tuple return change in calculate_student_term_scores().** The dispatcher returns `(total_score, average_score, subjects_count)`. Task A1 changes this to a 4-tuple. The ONLY caller is `generate_term_reports()` line 1608 which unpacks as `total_score, average_score, subjects_count = await self.calculate_student_term_scores(...)`. This unpacking will crash with `ValueError: too many values to unpack` if either the curriculum or legacy path returns 4 but the caller expects 3. | Technical | **High** | **Medium** | Server crash on report generation for ALL curricula (GES included) if legacy path is updated but caller is not, or vice versa | Change MUST be atomic: update both paths AND the caller in the same commit. Add a type annotation on the method signature. Consider returning a dataclass instead of a tuple to make this less fragile for future changes. | `01-phase-1-report-bridge.md` Task A1 Steps 1-4 |
| R5 | **effort_grade added to ScoreEntry schema may break strict API clients.** The frontend sends `ScoreEntry` objects. Adding `effort_grade: Optional[str]` is backward-compatible for deserialization (existing payloads without the field still validate). But if any API client does strict response matching (e.g., TypeScript type checking on the response), the new field could cause compile-time errors. | Quality | **Low** | **Low** | Frontend types need updating (covered by Task B3). No external API clients in production. | `02-phase-2-score-entry.md` |

### Performance Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Document to Update |
|----|------|----------|----------|-------------|--------|------------|--------------------|
| R6 | **Task A3 subject position calculation in bulk report generation.** For a class of 50 students with 10 subjects, computing positions requires running `calculate_subject_score()` for ALL 50 students x 10 subjects = 500 strategy invocations PLUS DB queries per student-subject. For bulk generation of the entire class, this is 500 x 50 = 25,000 strategy calls (each student's positions require all students' scores). Without caching, this will exceed the 5-second p95 target for bulk report generation. | Performance | **High** | **High** | Bulk report generation becomes unusably slow for classes > 30 students | Implement position caching: compute positions ONCE per class+subject (not per student), store in a local dict, reuse across all students in the class. The spec mentions this as "optional but recommended" -- it should be **mandatory**. | `01-phase-1-report-bridge.md` Task A3 |
| R7 | **Cumulative GPA query adds N DB queries in generate_term_reports().** Task A1 Step 5 adds a `select(TermReport)` query per student to fetch prior terms for cumulative GPA. For a class of 50 students, this adds 50 additional DB queries inside the report generation loop. | Performance | **Medium** | **High** | Report generation slows by ~200-500ms for classes with 50+ students | Batch-fetch all prior TermReports for the class in a single query BEFORE the per-student loop. Filter by `student_id.in_(student_ids)` and `academic_year_id == academic_year_id` and `gpa.isnot(None)`. Build a dict of `student_id -> [prior_gpas]`. | `01-phase-1-report-bridge.md` Task A1 Step 5 |
| R8 | **Dual-track doubles DB queries per student.** Task G2 calls BOTH `_get_student_subject_results_legacy()` AND `_get_student_subject_results_curriculum()` for the same student. Each method runs ~5-10 queries internally. For a class of 50 students, dual-track PDF generation means ~500-1000 DB queries instead of 250-500. | Performance | **Medium** | **Medium** | Dual-track report generation takes 2x as long. Acceptable for single reports; potentially slow for bulk class generation. | Document the performance impact. Consider generating dual-track reports asynchronously (Celery) for bulk generation. | `04-phase-4-montessori-dualtrack.md` Task G2 |

### Regression Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Document to Update |
|----|------|----------|----------|-------------|--------|------------|--------------------|
| R9 | **GES report generation regression from 4-tuple change.** If the legacy path is updated to return `(total_score, average_score, subjects_with_scores, {})` but the returned empty dict breaks any downstream code that doesn't expect it, GES schools break. More subtly: if `aggregate_data` is `{}` (falsy in Python), the `if aggregate_data:` guard in Step 4 of Task A1 will skip all curriculum field setting -- which is correct for GES, but if someone later adds default values to the empty dict, it could start setting fields incorrectly. | Quality | **High** | **Low** | GES report cards show incorrect data | Test explicitly: GES path returns 4-tuple with empty dict, and `if aggregate_data:` evaluates to False for empty dict. Add a dedicated regression test (Task A4.4 covers this). | `01-phase-1-report-bridge.md` |
| R10 | **pdf.py template context change could break existing GES reports.** Replacing `"term_gpa": None` with `"term_gpa": report.gpa` is safe ONLY if `report.gpa` is `None` for GES reports. Since GES `calculate_aggregate` returns `{}` and the code only sets `report.gpa` when `"gpa" in aggregate_data`, GES reports will have `report.gpa = None`. **But**: if there's any residual data in the `gpa` column from previous manual testing or migration artifacts, it could leak into GES PDFs. | Quality | **Medium** | **Low** | GES report cards incorrectly show a GPA section | Add a guard: only pass non-None curriculum fields to the template if a curriculum profile is active. Or: verify all existing TermReport rows have NULL curriculum columns before deploying. | `01-phase-1-report-bridge.md` Task A2 |
| R11 | **_resolve_curriculum_profile called redundantly in generate_term_reports().** The dispatcher `calculate_student_term_scores()` already calls `_resolve_curriculum_profile()` (line 190). Then Task A1 Step 4 calls it AGAIN to get the profile for setting `report.curriculum_profile_id`. This means 2 x N profile resolution queries per class (N students). | Performance | **Low** | **High** | Unnecessary DB queries, ~50ms overhead per student | Return the resolved profile from `calculate_student_term_scores()` (or make it a 5th tuple element), or cache the resolution result per student in a local dict. The spec acknowledges this concern (checklist item: "Verify _resolve_curriculum_profile is not called redundantly") but does not provide a solution. | `01-phase-1-report-bridge.md` Task A1 Step 4 |

### Dependency Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Document to Update |
|----|------|----------|----------|-------------|--------|------------|--------------------|
| R12 | **Phase 3 hard-depends on Phase 1 AND on reports being generated.** The simpler approach for C1 (reading from TermReport) means parents see no grades until `generate_term_reports()` is run. If a school generates reports after 2 weeks, parents have no data for 2 weeks. This is a UX regression from the current GES parent path which computes grades on-the-fly. | Timeline | **Medium** | **High** | Parents of non-GES students see "No grades available" for potentially weeks | Document the dependency clearly. Add a fallback in the parent service: if no TermReport exists, show a message like "Report generation pending. Contact your school." Do NOT implement on-the-fly calculation in the parent service (that duplicates logic). | `03-phase-3-parent-analytics.md` Task C1 |
| R13 | **Phases 1 and 2 file overlap.** Spec says they can run in parallel. Phase 1 modifies `report_service.py` (A1, A3) and `pdf.py` (A2). Phase 2 modifies `score_strategies.py` (B2), `score_service.py` (B1), and `schemas/exam.py` (B1). **No file overlap** -- parallel is safe. However, Phase 2 Task B2 modifies `_get_student_subject_results_curriculum()` in `report_service.py` to extract effort_grade. If Phase 1 Task A3 also modifies this method (for positions), there will be a merge conflict. | Dependencies | **Medium** | **Medium** | Git merge conflict requiring manual resolution | Assign Phase 1 and Phase 2 to different developers. Merge Phase 1 first. Phase 2 developer rebases after Phase 1 merge. Total delay: ~0.5 days. | `00-overview.md` |

### Missing Risk Coverage

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Document to Update |
|----|------|----------|----------|-------------|--------|------------|--------------------|
| R14 | **School changes curriculum mid-year.** A school switches from GES to Cambridge in Term 2. Term 1 reports have GES data; Term 2 should use Cambridge. The curriculum resolution chain checks current profile, not term-specific profile. Cumulative GPA calculation (Task A1 Step 5) queries prior TermReports by `academic_year_id` -- if Term 1 has no GPA (was GES), cumulative GPA = Term 2 GPA, which is correct. **But**: if the school switches BACK, the cumulative logic will average a NULL with a number, potentially producing incorrect results. | Technical | **Medium** | **Low** | Incorrect cumulative GPA for schools that change curriculum mid-year | Filter prior reports by `curriculum_profile_id` as well as `academic_year_id` when computing cumulative GPA. Only average GPAs from the same curriculum type. | `01-phase-1-report-bridge.md` Task A1 Step 5 |
| R15 | **Student transfers between curricula within same term.** Student moves from Cambridge class to American class mid-term. Term reports may exist for both classes. `generate_term_reports()` uses the student's current class, so the old Cambridge report will be orphaned (or overwritten?). The `TermReport` has a `class_id` FK, and the upsert in `generate_term_reports()` checks `student_id + academic_year_id + term_id` (line 1583-1594). If the old report had a different class_id, a NEW report is created for the new class, but the OLD report remains. Parent sees two reports? | Quality | **Medium** | **Low** | Duplicate or conflicting TermReports for transferred students | Check the TermReport upsert query. If it filters by class_id, this is handled. If not, add `class_id` to the upsert filter. Add a test case for this scenario. | `07-testing.md` |
| R16 | **Grading scale linked to profile is deleted.** The `GradingScale.curriculum_profile_id` FK links a scale to a profile. If the scale is soft-deleted, `determine_grade()` receives an empty grades list and returns `(None, None, None)` for all scores. This cascades: GPA is None, honor roll is False, all grades show as "-" on reports. | Technical | **Medium** | **Low** | Reports show no grades (silent failure, no error) | Add a check in report generation: if grades list is empty and curriculum profile is active, log a warning and raise a user-facing error. | Not in spec -- add to `01-phase-1-report-bridge.md` |
| R17 | **No Redis cache invalidation for curriculum fields.** The existing tenant cache stores `{id, subdomain, name, is_active}`. Adding curriculum-specific data to reports does not affect the tenant cache. **However**: if `_resolve_curriculum_profile()` is called frequently (2x per student per report), its results could benefit from a per-request cache. The spec does not mention caching curriculum resolution. | Performance | **Low** | **Medium** | Redundant DB queries for profile resolution (~50ms per call) | Use a `@functools.lru_cache` or a simple dict cache within the `TermReportService` instance scope. Since the service is instantiated per-request, the cache is naturally scoped. | `01-phase-1-report-bridge.md` |
| R18 | **Existing TermReport records have NULL curriculum columns -- is this handled?** Yes. Phase 1 does not add new migrations (no new columns). The columns `gpa`, `ib_total_points`, etc. already exist on TermReport and are all nullable. Existing reports with NULL values will display as "-" in templates. New reports generated after Phase 1 will have populated values. **No data migration needed.** | Quality | **N/A** | **N/A** | No risk | Already handled by nullable columns and template graceful degradation. | N/A |
| R19 | **Phase 7 adds criterion_scores column to ExamScore -- migration risk.** Adding a JSONB column with a GIN index to a large table (ExamScore) requires an `ALTER TABLE ... ADD COLUMN` which is fast for nullable columns in PostgreSQL (metadata-only). The GIN index creation will lock the table briefly. For production with <100 tenants and <100K exam scores, this is safe. | Infrastructure | **Low** | **Low** | Brief table lock during migration | Use `CONCURRENTLY` for index creation if the table has >100K rows. | `06-phase-6-7-extensions.md` Task J1 |
| R20 | **N+1 query pattern in _calculate_student_term_scores_curriculum().** Lines 294-345 show that for EACH subject, there is a separate CA query (lines 294-314) and a separate exam score query (lines 321-345). For 10 subjects, this is 20 queries per student. The legacy GES path has `_batch_get_all_scores()` which fetches all scores in 1-2 queries. The curriculum path has no equivalent batch optimization. This was flagged in the original risk analysis (R1 in `MULTI_CURRICULUM_RISK_ANALYSIS.md`) and is STILL not addressed in the gap closure spec. | Performance | **High** | **High** | 10-20x slower score calculation for non-GES curricula vs GES | Implement a batch score fetch for the curriculum path: one query for all CA scores by student+term+class, one query for all exam scores. Group in Python by subject_id. This is ~2 days of additional work not in the spec. | `01-phase-1-report-bridge.md` (add new task) |

### Team Readiness Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Document to Update |
|----|------|----------|----------|-------------|--------|------------|--------------------|
| R21 | **Task A1 has ambiguous implementation instructions.** The spec says "check if subject_results already exists as a local variable" (Step 1). A developer unfamiliar with the codebase will not know that it does NOT exist in `_calculate_student_term_scores_curriculum()` but DOES exist in `_get_student_subject_results_curriculum()`. The two methods have similar names and similar code but different purposes. Confusion is likely. | Knowledge | **Medium** | **High** | Developer implements the change in the wrong method, or implements it incorrectly and debugging takes 1+ days | Add explicit line numbers. State clearly: "In `_calculate_student_term_scores_curriculum()` (starting line 219), the `result` variable from `strategy.calculate_subject_score()` is NOT collected into a list. You must: (1) add `subject_results_list = []` before the for loop, (2) call `determine_grade()` to get `grade_point`, (3) set `result.grade_point = grade_point`, (4) append `result` to the list." | `01-phase-1-report-bridge.md` Task A1 |
| R22 | **Phase 4 Montessori frontend has no wireframe or design mock.** The spec provides component code snippets but no visual design. A developer will have to make UI/UX decisions (accordion layout, skill progress indicators, work sample cards) without guidance. Different developers will produce very different UIs. | Knowledge | **Medium** | **High** | Inconsistent UI requiring redesign, or multiple review cycles adding 1-2 days | Create a Figma mock or annotated screenshot before starting Phase 4 frontend work. At minimum, list the UI components to use (Shadcn Accordion, Badge for progress levels, Card for sections). | `04-phase-4-montessori-dualtrack.md` Task F3 |
| R23 | **Dual-track template context variables not fully specified.** Task G2 returns a dict with keys like `ges_results`, `international_results`, `international_components`. But the template in Task G1 also references `ges_ca_weight`, `ges_exam_weight`, `ges_average`, `ges_position`, `international_average`, `show_effort_grade`, `gpa`, `ib_total_points`. These additional context variables are NOT produced by `_get_dual_track_results()`. | Technical | **Medium** | **High** | Jinja2 template renders with missing variables (shows empty/None or errors) | Add the missing context variables to the `_get_dual_track_results()` return dict. Compute `ges_average` and `international_average` from the respective result sets. Pass `ges_ca_weight`/`ges_exam_weight` from AssessmentWeight. Pass `show_effort_grade` based on international curriculum type. | `04-phase-4-montessori-dualtrack.md` Tasks G1-G2 |
| R24 | **Test fixtures are not DRY.** Each test file creates its own curriculum profile, grading scale, assessment structure, components, students, exams, and scores. With 9 new test files, this is ~270 lines of duplicated setup. Future changes to the model (e.g., adding a NOT NULL column) require updating ALL test files. | Quality | **Low** | **High** | Maintenance burden increases with each model change | Create shared fixtures in `conftest.py` or a `tests/fixtures/curriculum.py` file: `american_profile`, `cambridge_profile`, `ib_profile`, `montessori_profile`, `french_profile`. Each creates profile + scale + structure + components. Reference these in all test files. | `07-testing.md` |

---

## 3. Dependency Analysis

### Can Phases 1 and 2 Truly Run in Parallel?

**Yes, with one caveat.**

File overlap analysis:

| File | Phase 1 | Phase 2 | Conflict? |
|------|---------|---------|-----------|
| `report_service.py` | A1 (lines 172-360, 1608-1630), A3 (line 1337, new method) | B2 (line 1334-1335, read effort_grade) | **Yes -- line 1337 area** |
| `pdf.py` | A2 (lines 407-430) | -- | No |
| `score_strategies.py` | -- | B2 (read-only reference) | No |
| `score_service.py` | -- | B1 (bulk_enter_scores) | No |
| `schemas/exam.py` | -- | B1 (ScoreEntry), B3 (types) | No |

The conflict is limited to the `_get_student_subject_results_curriculum()` method area (~line 1317-1340). Phase 1 Task A3 inserts position calculation code near line 1337. Phase 2 Task B2 reads `effort_grade` at line 1335. These are adjacent but not overlapping changes. A clean merge is possible if Phase 1 merges first.

**Recommendation:** Start both in parallel. Merge Phase 1 first. Phase 2 developer rebases. Expected merge conflict resolution: <30 minutes.

### Critical Path

```
Phase 1 (8.5d) --> Phase 3 (9d) --> [Done with parent portal + analytics]
                \-> Phase 4 (13.5d) --> [Done with Montessori + dual-track]

Phase 2 (5d) --> [independent, merge after Phase 1]

Phase 5 (6d) --> [independent]
Phase 6 (3d) --> [independent]
Phase 7 (9d) --> [depends on Phase 1 for strategy pattern]
```

**Critical path: Phase 1 (8.5d) + Phase 4 (13.5d) = 22 days = ~4.5 weeks**

With 2 developers:
- Dev A: Phase 1 (8.5d) -> Phase 3 (9d) -> Phase 7 (9d) = 26.5d
- Dev B: Phase 2 (5d) -> Phase 4 (13.5d) -> Phase 5 (6d) -> Phase 6 (3d) = 27.5d
- Calendar time: ~28d = ~5.5 weeks + 25% buffer = ~7 weeks

**With 1 developer: 54d raw = ~11 weeks + 25% buffer = ~14 weeks.**

---

## 4. Multi-Tenancy Risk Assessment

**New tables requiring RLS policies:** None in Phases 1-6. Phase 7 adds a column (`criterion_scores`) to `exam_scores` which already has RLS. No new RLS policies needed.

**Cross-tenant data access vectors:** The cumulative GPA query (Task A1 Step 5) filters by `tenant_id`. The `StudentCreditAccumulation` query (Task A1 Step 6) also filters by `tenant_id`. Both are safe because they are within the RLS-enforced session.

**Cache/session tenant bleed risks:** None. No new Redis caching introduced. Curriculum profile resolution uses the RLS-scoped DB session.

**Background job tenant context:** Not applicable. No new background jobs introduced. Report generation is synchronous within the request.

**Verdict:** Multi-tenancy risk is LOW for this gap closure plan. All changes operate within existing RLS-scoped sessions on existing tables.

---

## 5. What The Spec Gets Right

1. **The "broken bridge" diagnosis is accurate and well-illustrated.** The ASCII diagram clearly shows the gap between strategy `calculate_aggregate()` and TermReport field population.

2. **The simpler approach for parent portal (read from TermReport) is the correct choice.** Duplicating strategy logic in the parent service would create a maintenance nightmare (risk pattern #14 from MEMORY.md).

3. **Storing Montessori data in TermReport.extra_data JSONB is the right call.** Avoids new tables and migration for a niche feature.

4. **Phase separation is correct.** The independent phases (5, 6, 7) can be done in any order and by any developer.

5. **The verification checklist (document 08) is thorough.** Every requirement has a concrete verification step.

6. **No new database migrations in Phases 1-3.** This reduces deployment risk significantly.

---

## 6. Recommendations

### Must-Fix Before Implementation

1. **Fix R1 (grade_point bug) in spec.** Add explicit steps to `01-phase-1-report-bridge.md` Task A1: load grading scale, call `determine_grade()` per subject, set `result.grade_point` before appending to subject_results_list. Without this, GPA will never be computed.

2. **Fix R2 (subject_results collection) in spec.** Add `subject_results_list = []` and `subject_results_list.append(result)` to the code in Task A1 Step 1.

3. **Fix R3 (weighted_gpa) in spec.** Either implement `weighted_gpa` in `AmericanScoreStrategy.calculate_aggregate()` or remove all references to it. Since AP/Honors course metadata is not available per-subject in the current model, the pragmatic choice is to remove it and add it as a future enhancement.

### Should-Fix Before Implementation

4. **Address R20 (N+1 queries) in the curriculum score calculation path.** Add a batch-fetch optimization task to Phase 1. This is ~2 additional days but prevents a 10-20x performance regression for non-GES schools.

5. **Address R6 (position caching) for bulk generation.** Change Task A3 from "optional caching" to "mandatory caching." Without it, bulk report generation will time out for classes >30 students.

6. **Address R7 (cumulative GPA batch query).** Move the prior-terms query outside the per-student loop. This is a ~0.5 day change that prevents 50+ additional queries per class.

7. **Address R23 (missing dual-track context variables).** List all template variables and their sources in the spec.

### Should-Fix During Implementation

8. **Create shared test fixtures (R24).** Before writing the first test file, create reusable curriculum fixtures in conftest.py.

9. **Add curriculum mid-year switch test (R14).** Verify cumulative GPA handles curriculum changes correctly.

10. **Add student transfer test (R15).** Verify TermReport upsert handles class changes.

### Start Early

11. **Phase 1 Task A1 is the critical path and has 3 bugs.** Start here with your strongest developer. Allow 3 days, not 2.

12. **Montessori frontend wireframe (R22).** Create before Phase 4 coding starts. Even a hand-drawn sketch saves rework.

### Technical Spikes

13. **WeasyPrint rendering of Montessori narrative content.** Spend 2 hours verifying that the `montessori_report.html` template renders correctly with actual narrative data (multi-paragraph text, Unicode characters, long skill lists). The template exists but has never been rendered with non-None data.

14. **Dual-track template A4 layout.** Spend 1 hour verifying that two full result tables fit on a single A4 page. If they don't, the template needs a page-break strategy.

---

## 7. Comparison With Original Risk Analysis

The original `MULTI_CURRICULUM_RISK_ANALYSIS.md` (2026-03-06) covered the full multi-curriculum infrastructure build. This gap closure plan addresses the wiring issues identified in that analysis. Key comparisons:

| Original Risk | Status | Gap Closure Coverage |
|---------------|--------|---------------------|
| R1: N+1 queries in curriculum path | **STILL OPEN** | Not addressed in gap closure spec. See R20 above. |
| R5: Duplicate column additions across migration phases | **RESOLVED** | Gap closure has no new migrations in Phases 1-3 |
| R9: calculate_student_term_scores not strategy-dispatched | **RESOLVED** | Already dispatched (line 194-217 of report_service.py) |
| R11: parent_academic.py independent GES calculation | **ADDRESSED** | Task C1 in Phase 3 |
| Analytics service not mentioned | **ADDRESSED** | Tasks D1-D2 in Phase 3 |
| pdf.py third caller of get_student_subject_results | **ADDRESSED** | Task A2 in Phase 1 |

**Pattern confirmed: specs consistently underestimate by ~35%.** Original spec was 54d task-level, revised to 87d. Gap closure spec is 40.5d, revised to 54d. The underestimation ratio is 33% for gap closure (better than 60% for greenfield), likely because the infrastructure is already built and the scope is more constrained.
