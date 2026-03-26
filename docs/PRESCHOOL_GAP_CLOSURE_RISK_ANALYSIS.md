# Risk Analysis: Preschool Gap Closure (Sprints 20.5-22)

**Analyst:** Risk Analyst Agent
**Date:** 2026-03-23
**Spec Version:** 00-overview.md through 09-verification-checklist.md
**Status:** Complete

---

## Executive Summary

The Preschool Gap Closure is a **moderately complex** feature set (6/10, I agree with the spec) that extends an already well-built preschool module with safety features, portfolio capabilities, and fee integration. The spec is among the better-written ones I have reviewed for this project -- architecture decisions are sound, the "DO NOT re-implement" list prevents wasted effort, and the file-append strategy avoids the fragmentation risk of creating new packages. However, the effort estimates are **underestimated by approximately 35-40%**, primarily because the spec underweights testing, the sibling discount integration with invoice generation is more complex than described, and the SVG radar chart in WeasyPrint PDF is unproven in this codebase. The child safety features (pickup validation, incident notification) carry **operational risk** beyond the technical -- a bug in pickup authorization could have real-world consequences for child safety.

**Overall Risk Level:** MEDIUM. No architectural red flags, but three areas need early attention: (1) the preschool_reports unique constraint change with existing data, (2) NotificationDispatcher integration for incidents, and (3) the TENANT_SCOPED_TABLES count is wrong in the spec (says 55, actual is 102).

---

## Component Complexity

| Component | Complexity | Spec Est. | Revised Est. | Notes |
|-----------|------------|-----------|-------------|-------|
| **Phase 1: Incident Reporting** | 3 | 2d | 3d | Status machine + notification integration + attachments |
| **Phase 1: Pickup Authorization** | 3 | 2d | 3d | Guardian validation logic, authorization chain, immutable logs |
| **Phase 1: Allergy/Dietary Alerts** | 2 | 1d | 1.5d | JSONB schema + GIN index + class-wide alerts |
| **Phase 1: Session Enrollment** | 1 | 0.5d | 0.5d | Simple column addition |
| **Phase 1: Session-Based Fees** | 2 | 0.5d | 1d | Must verify fee structure matching in invoice generation |
| **Phase 1: Migration + Tests** | 2 | 1d | 2d | 40 tests is correct count but writing them takes longer than 1d |
| **Phase 1: Frontend** | 3 | (in 7d) | 3d | 2 pages + 6 components + sidebar updates |
| **Phase 2: Learning Stories** | 2 | 2d | 2.5d | Standard CRUD; JSONB arrays for cross-references |
| **Phase 2: Extended Care** | 3 | 2d | 3d | Check-in/out state machine + billing calc + preschool_settings dependency |
| **Phase 2: Caregiver Ratios** | 1 | 0.5d | 0.5d | Simple CRUD with computed property |
| **Phase 2: Progress Timeline** | 3 | 1d | 1.5d | 4-table aggregation, merge-sort in Python |
| **Phase 2: Report Enhancements** | 5 | 1d | 2.5d | SVG radar chart + unique constraint change + WeasyPrint testing |
| **Phase 2: Daily Report Sending** | 3 | 1d | 1.5d | NotificationDispatcher integration + bulk rate limiting |
| **Phase 2: Sibling Discount** | 3 | 1d | 2d | Touches invoice generation code path + new ScholarshipType enum value |
| **Phase 2: Migration + Tests** | 2 | 1d | 2d | 33 tests across 6 files |
| **Phase 2: Frontend** | 3 | (in 9.5d) | 3.5d | 3 pages + 7 components |
| **Phase 3: Supplies** | 2 | 2d | 2d | Simple CRUD + low-stock notification |

**Total Estimated Effort:**

| | Spec Estimate | Revised Estimate |
|---|---|---|
| Phase 1 | 7d | 10d |
| Phase 2 | 9.5d | 14.5d |
| Phase 3 | 2d | 2d |
| **Raw Total** | **18.5d** | **26.5d** |
| **With 25% Buffer** | **23d** | **33d** |

**Confidence Level:** Medium -- the spec is well-structured and builds on existing patterns, but the file-append strategy for 1300-line service + 1100-line endpoint files introduces merge risk and cognitive load. Testing effort is consistently underestimated across all phases.

**Recommended Buffer:** 25% -- rationale: this feature extends existing code rather than creating new subsystems, which reduces unknowns, but the SVG chart and sibling discount integration are first-time patterns.

**Spec underestimation:** ~43% at raw level. Consistent with the pattern observed across previous specs (45-60%).

---

## Risk Register

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R1 | **TENANT_SCOPED_TABLES count wrong**: Spec says "Before: 55, After: 62". Actual current count is **102**. Phase 3 verification checklist uses wrong totals. | Quality | Low | High | conftest.py already has the right entries; wrong count in spec is cosmetic but could cause confusion during verification | Correct the spec's count references. Actual final count will be 102 + 7 = 109. |
| R2 | **Unique constraint change on preschool_reports may fail**: Phase 2 migration drops `uq_preschool_report` and creates `uq_preschool_report_v2` including `report_type`. If existing data has NULL `report_type` values before the `server_default` takes effect, the constraint creation may fail. | Technical | High | Medium | The migration adds the column with `server_default="term"` BEFORE creating the new constraint, so existing rows get 'term'. However, the ADD COLUMN and constraint operations happen in the same transaction -- verify that `server_default` backfills existing rows within the same statement. Test with populated data. |
| R3 | **Pickup authorization bug allows unauthorized pickup**: If the `record_pickup` service method has a logic error in the guardian `can_pickup` check or the authorized person `is_active` check, an unauthorized person could pick up a child. | Multi-Tenancy / Safety | Critical | Low | A child could be released to an unauthorized person. | Write explicit negative test cases for EVERY rejection path: (1) guardian with `can_pickup=False`, (2) guardian not linked to student, (3) deactivated authorized person, (4) soft-deleted authorized person, (5) authorized person from different student, (6) cross-tenant authorized person. Make the pickup validation a separate method that can be unit-tested independently. |
| R4 | **Incident notification fails silently**: The spec says "Serious incidents auto-trigger parent notification" via NotificationDispatcher. If the dispatcher is called in a fire-and-forget pattern and the SMS/email fails, the parent is never notified of a serious incident. | Safety | Critical | Medium | Parent not informed of serious child safety incident. | Wrap NotificationDispatcher call in try/except. On failure: (1) log the error with structlog at ERROR level, (2) set `parent_notified_at = None` to indicate failure, (3) return a response field `notification_failed: true` so the UI can show a warning banner "Parent notification failed -- please call directly". Add a fallback: cron job that checks for incidents with severity='serious' AND status != 'parent_notified' older than 15 minutes. |
| R5 | **Allergy data staleness**: `dietary_requirements` JSONB is set once and not validated against any external source. If a parent updates allergy info after the start of term, teachers may work with stale data. | Safety | Medium | Medium | Teacher relies on outdated allergy information when preparing meals or activities. | Display `updated_at` prominently in the AllergyAlert component. Add a "Verify allergies" prompt at start of each term. Consider adding `last_verified_at` timestamp that teachers must acknowledge. |
| R6 | **SVG radar chart not tested with WeasyPrint**: The spec correctly identifies that WeasyPrint cannot execute JavaScript, and proposes inline SVG. However, this codebase has never generated SVG charts in WeasyPrint PDFs. Complex SVG features (text rotation, polygon fills with opacity) may render incorrectly or not at all. | Technical | Medium | Medium | Radar chart appears blank or garbled in PDF reports. Parents receive reports without the visual progress overview. | Create a standalone test that generates a PDF with the SVG radar chart BEFORE implementing the full feature. Test with WeasyPrint locally. Known WeasyPrint SVG limitations: no `transform-origin` on text, no CSS animations, limited filter support. Stick to basic SVG primitives: `<polygon>`, `<line>`, `<text>`, `<circle>`. |
| R7 | **Preschool service file grows to ~2000+ lines**: The existing `preschool.py` service is 1321 lines. Phase 1 adds ~400 lines (incidents, pickups, allergies). Phase 2 adds ~500 lines (stories, extended care, timeline, reports, daily send). Total: ~2200 lines in a single file. | Knowledge | Medium | High | Increased cognitive load, merge conflicts, harder to navigate and test. Single-developer bottleneck. | Consider splitting the service into a package (`services/preschool/`) with submodules: `incident_service.py`, `pickup_service.py`, `allergy_service.py`, `portfolio_service.py`, `extended_care_service.py` -- following the existing `finance/` package pattern. The spec explicitly says "append to existing file" but the existing `finance/` and `exam/` services were split for the same reason. |
| R8 | **Sibling discount integration touches invoice generation**: The spec says "the developer should read invoice_service.py and follow the existing scholarship auto-application pattern." The invoice_service.py is 1230 lines. There is NO existing scholarship auto-application code in invoice_service.py (confirmed by grep). The spec's assumption that this code path exists is **incorrect**. | Technical | High | High | Sibling discount auto-application requires building a new integration point in invoice generation, not extending an existing one. Effort is 2d, not 1d. | Audit `invoice_service.py` for how scholarships are currently applied. If scholarships are applied manually (not auto-detected), the sibling auto-detection must be a separate step -- either a pre-invoice-generation hook or a manual "Apply Sibling Discounts" action. Do NOT modify the invoice generation critical path without thorough regression testing. |
| R9 | **ScholarshipType enum needs new value**: Adding `SIBLING_DISCOUNT` to `ScholarshipType` requires a PostgreSQL `ALTER TYPE ... ADD VALUE` statement. This cannot be run inside a transaction in PostgreSQL < 12. SIMS Plus uses PostgreSQL 16, so `ADD VALUE` works in transactions, but the migration must still use `op.execute()` not `sa.Enum.create()`. | Technical | Medium | Medium | Migration fails if enum addition is done incorrectly. | Use `op.execute("ALTER TYPE scholarshiptype ADD VALUE IF NOT EXISTS 'sibling_discount'")` in the Phase 2 migration. Add `IF NOT EXISTS` to make it idempotent. |
| R10 | **Extended care billing depends on preschool_settings**: The billing summary reads `extended_care_rate_per_hour` and `extended_care_flat_rate` from `schools.preschool_settings` JSONB. If the school hasn't configured these settings, the billing endpoint must gracefully handle NULL/missing keys. | Technical | Low | High | Billing summary returns $0 or throws KeyError for schools that haven't configured rates. | Default to rate=0 with a clear message: "Extended care rates not configured. Go to Preschool Settings to set rates." Add a `is_configured` boolean to the billing summary response. |
| R11 | **NotificationDispatcher requires User objects**: From my memory: "NotificationDispatcher assumes User objects -- Cannot send to raw phone/email without wrapper service." The dispatcher's `dispatch()` method takes a `user_id` parameter. Guardians who are not registered users cannot receive notifications through this path. | Technical | Medium | Medium | Guardians without user accounts don't receive incident notifications or daily reports. | The spec's daily report sending loads guardians via `selectinload`. Check if guardians have linked User accounts (via email match). For guardians WITHOUT user accounts, fall back to direct SMS/email using the SMS service and email service directly, bypassing NotificationDispatcher. Add a `send_to_guardian()` helper that checks for User account first, then falls back. |
| R12 | **PickupLog has no SoftDeleteMixin but pickup_logs gets `created_at` and `updated_at` without `deleted_at`**: This is intentional and correct (immutable audit records). However, the conftest.py cleanup in `_cleanup_tables` does hard DELETE. If the table has FK references or is referenced by other tables, cleanup order matters. | Quality | Low | Low | Test cleanup fails if table order is wrong. | Verify `pickup_logs` is cleaned up BEFORE `authorized_pickups` and `students` in the test teardown, since it has FK references to both. |
| R13 | **Phase 1 and Phase 2 migrations depend on specific `down_revision`**: Phase 1 depends on `20260327_0100_user_sessions`. Phase 2 depends on Phase 1. If any intervening migration is added by another developer between now and sprint 20.5, the migration chain breaks. | Timeline | Medium | Medium | Alembic reports multiple heads; migration cannot run. | Use `alembic merge` if heads diverge. Better: run Phase 1 migration immediately after the user_sessions migration lands, locking the chain. |
| R14 | **Bulk daily report sending (30+ students) is synchronous**: The spec caps at 50 students per call and suggests Celery for larger classes. Even 30 students x 2 guardians = 60 notifications synchronously. At ~200ms per SMS API call, this is 12 seconds of blocking time. | Performance | Medium | High | API request timeout (30s default) or degraded response time during bulk send. | Add a background task pattern even for < 50 students. Use Celery if available, or at minimum return a 202 Accepted with a job ID and poll for completion. Alternatively, send notifications in batches of 10 with asyncio.gather() to parallelize. |
| R15 | **Timeline query performance**: The timeline aggregates across 4 tables (student_skill_assessments, progress_observations, preschool_incidents, learning_stories). Each query runs separately, then Python merges. For a student with many entries (unlikely for preschool but possible over multiple terms), this could be slow. | Performance | Low | Low | Acceptable for preschool volumes (1 student, typically < 100 entries total). | The spec correctly identifies this is fine for preschool. No mitigation needed. Monitor if timeline is expanded to non-preschool students later. |
| R16 | **Class allergy alerts query JSONB column**: The spec adds a GIN index on `students.dietary_requirements`. The query must filter by class enrollment AND non-null dietary_requirements. Without the right query pattern, the GIN index may not be used. | Performance | Low | Medium | Full table scan on students for allergy alerts. Acceptable for preschool class sizes (< 30 students). | Ensure the query uses `dietary_requirements IS NOT NULL` in the WHERE clause to leverage the partial GIN index. For class sizes < 30, this is a non-issue regardless. |
| R17 | **Frontend estimate does not account for testing**: The spec lists 5 pages and 15 components but the frontend estimate is embedded in the phase totals. No E2E or component tests are planned for the frontend. | Testing | Low | High | Frontend bugs caught only in manual testing. | Add at minimum smoke tests for each page (renders without error). For the PickupLogForm, add a client-side test verifying the guardian/authorized person validation logic. |
| R18 | **40 tests for Phase 1 is adequate but tight**: 13 incident + 12 pickup + 6 allergy + 4 session fee + 5 RLS = 40 tests. This covers happy paths and key error paths. Missing: (1) concurrent pickup logs for same student, (2) incident with all JSONB fields populated, (3) dietary requirements with maximum array sizes. | Testing | Low | Medium | Edge cases not covered may surface in production. | Add 5 additional edge case tests: concurrent access, JSONB size limits, empty arrays vs null, Unicode in allergen names, phone number format validation on authorized pickups. |
| R19 | **`from __future__ import annotations` risk**: The spec correctly warns against this in verification checklist. However, the models file (preschool.py) already uses `from typing import TYPE_CHECKING` correctly. The risk is that a developer might add the future import for type hint convenience when appending 7 new models. | Quality | High | Low | 204 responses break silently (return empty body instead of no body). | Add this check to the CI linter. grep for `from __future__ import annotations` in all endpoint files as a pre-commit hook. |
| R20 | **Photo URLs in reports reference S3 presigned URLs**: Presigned URLs expire (typically 1 hour). If report PDFs are generated with presigned URLs and the PDF is opened later, the images will show as broken. | Technical | Medium | Medium | Report card PDFs have broken images when opened after presigned URL expiry. | When generating the PDF, download the image from S3 and embed it as base64 data URI in the HTML template. This makes the PDF self-contained. WeasyPrint supports data URIs in `<img src>`. |

---

## Multi-Tenancy Risk Assessment

### New Tables Requiring RLS Policies: 7
1. `preschool_incidents` (Phase 1)
2. `authorized_pickups` (Phase 1)
3. `pickup_logs` (Phase 1)
4. `learning_stories` (Phase 2)
5. `extended_care_sessions` (Phase 2)
6. `class_caregiver_ratios` (Phase 2)
7. `preschool_supplies` (Phase 3)

All tables correctly use `TenantMixin` and the migration creates proper RLS policies with `USING` + `WITH CHECK` + `FORCE ROW LEVEL SECURITY`. This follows the established pattern exactly. **No issues identified.**

### Cross-Tenant Data Access Vectors
- **Authorized pickups**: The unique constraint on `(tenant_id, student_id, phone)` correctly scopes to tenant. No cross-tenant risk.
- **Learning story `observation_ids` JSONB**: Contains UUIDs of progress_observations. If a client sends observation IDs from another tenant, the service MUST validate they belong to the same tenant. The spec does not explicitly mention this validation. **Flag: validate observation_ids belong to tenant before saving.**
- **Sibling discount detection**: Queries `student_guardians` join which is already tenant-scoped via RLS. Safe.

### Cache/Session Tenant Bleed Risks
- No Redis caching introduced for preschool features. No cache bleed risk.
- `preschool_settings` on the `schools` table is per-tenant via existing RLS. Safe.

### Background Job Tenant Context
- Daily report bulk sending is synchronous (not Celery). If moved to Celery later, tenant context must be passed explicitly via task arguments, not relied upon from the request context. The existing NotificationDispatcher takes `tenant_id` as a parameter, which is correct.

---

## Dependencies

### Internal Dependencies

| Component | Depends On | Status |
|-----------|------------|--------|
| Phase 1 migration | `20260327_0100_user_sessions` migration | Ready (committed) |
| Phase 2 migration | Phase 1 migration | Sequential |
| Phase 3 migration | Phase 2 migration | Sequential |
| Incident notification | `NotificationDispatcher` service | Ready (511 lines, functional) |
| Daily report sending | `NotificationDispatcher` service | Ready |
| Sibling discount | `ScholarshipType` enum + `invoice_service.py` | Requires audit -- no auto-apply exists |
| Extended care billing | `schools.preschool_settings` JSONB | Ready (column exists) |
| Pickup validation | `StudentGuardian.can_pickup` boolean | Ready (exists) |
| Allergy alerts | `Student.allergies` text field (coexistence) | Ready |
| Session-based fees | `FeeStructure` model | Ready |
| SVG radar chart | WeasyPrint PDF engine | Ready but **untested with SVG** |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| SMS delivery (Arkesel) | Arkesel API | Low | None | Already integrated; used by incident notifications |
| Email delivery (SMTP) | Internal | Low | None | Already integrated |
| S3 for photo storage | AWS | Low | None | Already integrated for media uploads |
| WeasyPrint SVG support | Open source | Medium | N/A | Must test radar chart rendering; no control over bugs |

---

## Guaranteed Bugs in Spec

These are issues that will cause failures if implemented exactly as written:

### Bug 1: TENANT_SCOPED_TABLES Count
**Location:** `08-phase-3-supplies.md`, line 310-313
**Issue:** Spec says "Before: 55 (current)" and "After: 62". Actual current count is **102**. The count after all 3 phases will be **109**, not 62.
**Impact:** Cosmetic -- the actual `conftest.py` entries are correct in the spec. Only the summary counts are wrong.
**Fix:** Correct the counts in the spec and verification checklist.

### Bug 2: Missing ScholarshipType Enum Migration
**Location:** `06-phase-2-services-endpoints.md`, section 6.7
**Issue:** Spec says "Add `SIBLING_DISCOUNT` to the `ScholarshipType` enum" but does NOT include this in the Phase 2 migration (`05-phase-2-models-migration.md`). The migration creates tables and adds columns but never runs `ALTER TYPE scholarshiptype ADD VALUE 'sibling_discount'`.
**Impact:** Sibling discount feature will fail with a database error when trying to insert a scholarship with type 'sibling_discount'.
**Fix:** Add `op.execute("ALTER TYPE scholarshiptype ADD VALUE IF NOT EXISTS 'sibling_discount'")` to the Phase 2 migration.

### Bug 3: No Auto-Apply Scholarship Pattern Exists
**Location:** `06-phase-2-services-endpoints.md`, section 6.7
**Issue:** Spec says "the developer should read invoice_service.py and follow the existing scholarship auto-application pattern." Grep confirms there is NO auto-application pattern in `invoice_service.py`. Scholarships are applied manually, not auto-detected during invoice generation.
**Impact:** Developer will need to build the auto-detection and auto-application logic from scratch, not follow an existing pattern. This is 2d of work, not 1d.
**Fix:** Rewrite the sibling discount spec to include explicit implementation steps for: (1) sibling detection query, (2) scholarship creation/update, (3) invoice generation hook.

### Bug 4: Missing Guardian Import in TYPE_CHECKING
**Location:** `01-phase-1-models-migration.md`, section "Import Updates"
**Issue:** Spec correctly identifies that `Guardian` needs to be added to the `TYPE_CHECKING` block. However, the current code imports `from app.models.student import Student` -- `Guardian` is also in `app.models.student`, so the import should be `from app.models.student import Guardian, Student`.
**Impact:** Minor -- will cause a NameError in type checking mode if Guardian is referenced in type hints.
**Fix:** Already correctly specified in the spec (line 761). This is a non-issue.

---

## Recommended Approach

### Parallel Tracks

- **Track A (Backend):** Models, migration, service methods, endpoints, tests
- **Track B (Frontend):** TypeScript types, server actions, components, pages

Track B can start as soon as Track A's endpoints are defined (schemas finalized), even before the backend is fully tested.

### Sequential Dependencies

1. Phase 1 Models + Migration (must be first)
2. Phase 1 Schemas + Service Methods (depends on models)
3. Phase 1 Endpoints + Tests (depends on services)
4. Phase 1 Frontend (depends on endpoints)
5. Phase 2 Models + Migration (depends on Phase 1 complete)
6. Phase 2 Services + Endpoints + Tests
7. Phase 2 Frontend
8. Phase 3 (depends on Phase 2 complete)

### Critical Path

**Phase 1 Critical Path:** Migration (1d) --> Incident Service (1.5d) --> Pickup Service (1.5d) --> Allergy Service (0.5d) --> Endpoints (1.5d) --> Tests (2d) --> Frontend (3d)

**Minimum Timeline:** 11 working days for Phase 1 (1 developer)
**Minimum Timeline:** 15 working days for Phase 2 (1 developer)
**Minimum Timeline:** 2 working days for Phase 3 (1 developer)

**Total Minimum:** 28 working days (1 developer) = ~6 weeks
**With 2 developers (backend + frontend parallel):** ~4 weeks
**Realistic Timeline:** 5 weeks with buffer

---

## Recommendations

### 1. Start Early: SVG Radar Chart Spike (0.5d)
Before committing to the radar chart in Phase 2, write a standalone test that generates a PDF with an SVG radar chart using WeasyPrint. Verify: polygon rendering, text placement, opacity fills, label positioning. This eliminates R6 and avoids discovering rendering issues late.

### 2. Start Early: Audit Invoice Service for Scholarship Pattern (0.5d)
The spec assumes an auto-application pattern that does not exist. Before Phase 2 starts, audit `invoice_service.py` to understand how scholarships are currently applied, and design the sibling discount integration point. This eliminates R8.

### 3. Risk Mitigation: Child Safety Features
- Make pickup validation a separate, independently testable method (not inline in `record_pickup`)
- Add explicit negative test for EVERY rejection path
- Log all pickup events to the audit service (not just the pickup_logs table)
- Add a "verification mode" where teachers must type the pickup person's phone number to confirm identity

### 4. Risk Mitigation: Notification Reliability
- Never fire-and-forget incident notifications for "serious" severity
- Add retry logic (3 attempts with exponential backoff) for serious incident notifications
- Add a dashboard widget showing "Unnotified Serious Incidents" count
- Consider adding `notification_status` field to `preschool_incidents` (pending, sent, failed)

### 5. Technical Spike: Service File Splitting
The preschool.py service will grow to ~2200 lines. Before Phase 1 implementation, consider splitting into a `services/preschool/` package. This is a mechanical refactor (no logic changes) that takes ~2 hours and pays dividends in maintainability. Follow the `services/finance/` pattern.

### 6. Blockers to Resolve
- **ScholarshipType enum migration**: Must be added to Phase 2 migration
- **TENANT_SCOPED_TABLES count**: Must be corrected in spec (102 current, not 55)
- **Learning story observation_ids validation**: Must add tenant-scope validation for cross-referenced UUIDs

---

## Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| No new infrastructure | All features use existing DB, S3, Redis, SMS, Email | None | None |
| WeasyPrint SVG testing | Verify radar chart rendering | 0.5d developer time | None |
| S3 presigned URL policy review | Pickup person photos must be private | 0.5d review | None |

---

## Child Safety Risk Deep-Dive

This section addresses questions 4 specifically, given the critical nature of child safety in preschool operations.

### What happens if pickup validation has a bug?

**Scenario:** A bug in the `record_pickup` method allows a guardian with `can_pickup=False` to be logged as the pickup person.

**Current mitigations in the spec:**
1. Service-layer validation checks `can_pickup` flag
2. Service validates guardian is linked to the specific student
3. Service validates authorized persons are active (not deactivated or soft-deleted)
4. `pickup_date` is set server-side (cannot be forged by client)

**Gaps:**
1. No secondary verification (e.g., teacher must confirm identity)
2. No alert when an unauthorized pickup is attempted (the system just returns an error)
3. If the API returns a generic 403, the teacher may not understand why
4. The pickup log is created AFTER validation, but there is no "attempted pickup" log for rejected attempts

**Recommendations:**
- Log rejected pickup attempts to the audit service (who tried, when, why rejected)
- Show specific error messages: "Guardian X does not have pickup permission for Student Y. Contact the parent to update permissions."
- Consider a "pickup override" flow: teacher can override with a reason and their user_id, creating an audit trail

### What happens if incident notification fails silently?

**Scenario:** A "serious" incident occurs. The teacher clicks "Notify Parent." The NotificationDispatcher is called, but SMS delivery fails (Arkesel API timeout). The incident status transitions to `parent_notified` but the parent never receives the message.

**Analysis of the spec:**
1. The `notify_parent_incident` service method sets `status = parent_notified` and `parent_notified_at = now()`
2. It then calls NotificationDispatcher
3. If the dispatcher fails AFTER the status update, the database shows "parent notified" but the parent was never actually notified

**This is a critical ordering bug in the spec.** The status should only transition AFTER confirmed delivery, or the system should track notification status separately.

**Recommendation:**
1. Call NotificationDispatcher FIRST
2. Only update `status` to `parent_notified` if dispatch succeeds
3. If dispatch fails, keep status at `reviewed` (or `reported`) and set a `notification_failed_at` timestamp
4. Add a retry button in the UI that attempts notification again
5. Add a monitoring query: incidents with severity='serious' AND status NOT IN ('parent_notified', 'resolved') AND created_at > 15 minutes ago

### What happens if allergy data is stale or incorrect?

**Scenario:** A parent informs the school about a new peanut allergy at the start of Term 2. The admin updates `dietary_requirements` for the student. However, the teacher loaded the daily log page before the update and sees the old (no allergies) data.

**Analysis:**
1. The AllergyAlert component fetches class allergy data when a class is selected
2. If the teacher selected the class before the update, they work with stale data
3. There is no real-time push mechanism to update the alert

**Mitigations:**
- The allergy alert is fetched per-session (page load), so a page refresh gets current data
- This is acceptable for a web app -- real-time allergy updates are Phase 4+ (push notifications)
- Add `last_updated` display in the AllergyAlert component so teachers can see how fresh the data is
- Consider adding a "Refresh Allergies" button that teachers can click before meal times

---

## Comparison to Previous Risk Analyses

| Metric | This Spec | Multi-Curriculum | Admissions | User Mgmt |
|--------|-----------|-----------------|------------|-----------|
| Spec Quality | Good | Good | Good | Medium |
| Estimate Accuracy | 57% (raw) | 58% | 79% | 48% |
| Guaranteed Bugs | 3 | 4 | 3 | 5 |
| New Tables | 7 | 9 | 10 | 1 |
| Service File Growth Risk | HIGH (2200 lines) | HIGH (refactor needed) | LOW (new package) | LOW |
| Safety-Critical | YES (child safety) | No | No | No (auth is safety but different) |

This spec is notable for being the first safety-critical feature in the codebase. Previous modules handle data correctness (grades, finances) but not physical child safety. This raises the bar for testing thoroughness and error handling.
