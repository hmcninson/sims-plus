# Enrollment Management Gap Closure -- Risk Analysis

**Analyst:** Risk Analyst Agent
**Date:** 2026-03-24
**Spec Version:** enrollment-gap-closure/00-overview.md (dated 2026-03-24)
**Status:** Review Complete

---

## Executive Summary

The enrollment gap closure plan is **well-structured and architecturally sound** compared to prior specs in this codebase. It benefits from a mature admissions module (16 tables, 11 services already in place), clear architecture decisions (AD-1 through AD-8), and explicit backward compatibility guards (AD-3, AD-4). However, the **8-week / 2-developer estimate is approximately 30-40% under** what realistic delivery requires. The primary underestimation sources are: frontend effort (35+ components essentially unmeasured), Celery infrastructure bootstrap (no working Celery in production), CSSPS import edge cases, and the testing overhead for 10 new RLS-enabled tables.

**Overall Risk Level:** MEDIUM-HIGH
**Spec Quality:** Above average for this codebase (better than multi-curriculum, similar to preschool gap closure)
**Key Concern:** Phase 2 (Celery + PDF + offer acceptance) and Phase 3 (CSSPS + enrollment flow modification) carry the highest risk concentration.

---

## Risk Register

### Critical Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Phase |
|----|------|----------|----------|-------------|--------|------------|-------|
| R-001 | **Celery infrastructure does not exist in production.** `backend/app/tasks/__init__.py` line 13 says "TODO: Wire to Celery once celery worker + beat are configured in docker-compose." The offer_expiry and reminder tasks are the first Celery Beat tasks in admissions. There is no `celery_app` instance, no `celery_config.py`, no worker process in docker-compose. | Technical | Critical | High | Tasks silently never run. Offers never expire. Reminders never send. Schools lose trust in automation. | **Must bootstrap Celery infrastructure BEFORE Phase 2.** Add to Phase 1 as a prerequisite: (1) Create `celery_app.py` with Redis broker config, (2) Add celery worker + celery beat services to docker-compose.yml, (3) Create one smoke-test task to validate the pipeline end-to-end. Estimate: 2-3 additional dev-days. | 2 |
| R-002 | **Modifying `EnrollmentService.enroll()` breaks existing enrollment flow.** The spec adds checklist and deposit enforcement to the existing enroll() method. Schools that are mid-enrollment-cycle with applications already in ACCEPTED status will suddenly face new requirements (checklist, deposit) if the migration runs while they have pending enrollments. | Integration | Critical | Medium | Active schools unable to complete enrollments after deploy. Support tickets. Possible data inconsistency if partial mitigation applied. | AD-3 partially mitigates this (checklist only enforced when record exists). **But the deposit check is NOT guarded.** Verify that `enrollment_deposit_required` defaults to `false` on existing admission_periods (it does -- `server_default="false"`). Add explicit integration test: "test_enrollment_proceeds_for_pre_existing_accepted_applications_without_deposit_config". | 3 |
| R-003 | **CSSPS file import with 5000+ rows causes transaction timeout or OOM.** The spec creates one Application + ApplicationGuardian per row in a single transaction. 5000 rows = 10,000+ inserts + 5000 dedup checks (each a SELECT). The current enrollment endpoint has no batch/chunk mechanism. | Data | Critical | Medium | Import hangs. Transaction times out at default 30s. Large CSSPS files (some SHS schools receive 2000-5000 placements) fail silently or corrupt data. | **Implement chunked processing:** Process in batches of 100 rows per flush(). Add progress tracking. Consider 202 Accepted + background task pattern for files > 500 rows. Add a configurable MAX_ROWS limit (default 5000) with clear error message. Estimate: +2 dev-days over spec. | 3 |

### High Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Phase |
|----|------|----------|----------|-------------|--------|------------|-------|
| R-004 | **PDF letter generation timeout on bulk operations.** WeasyPrint is synchronous and CPU-bound. Generating 50+ admission letters sequentially will exceed API timeout (30s default). The spec acknowledges this in Section 7 ("Generate async; return 202 Accepted") but the service code is synchronous `_render_pdf()`. | Technical | High | High | Bulk decision + letter generation fails for popular schools. Admin retries, creating duplicates. | The spec's own mitigation is correct but not implemented. **Generate letters on-demand per decision, not in bulk.** The `generate_admission_letter` endpoint is already per-decision. Add rate limiting (5/min) and implement async generation only if schools request bulk. | 2 |
| R-005 | **Offer expiry Celery task tenant context leak.** The spec correctly identifies this risk. The task must iterate all tenants using `run_for_all_tenants()` from `app/tasks/utils.py` (which exists and properly sets RLS context per tenant). However, the task spec code is not shown -- only referenced. If implemented incorrectly (e.g., single unscoped session), expired offers from tenant A could be processed under tenant B's context. | Multi-Tenancy | High | Low | Cross-tenant data modification. Compliance violation. | **Use the existing `run_for_all_tenants()` helper verbatim.** Add RLS isolation test: create expired offers in two tenants, run task, verify each tenant's offers are processed independently. Add to TENANT_SCOPED_TABLES verification. | 2 |
| R-006 | **CSSPS deduplication by `custom_fields.index_number` is fragile.** The spec uses `custom_fields.index_number` for dedup, but `custom_fields` is a JSONB column. Querying `custom_fields->>'index_number'` across thousands of applications without an index will be slow. More critically, if any prior import used a different key structure, dedup fails silently and creates duplicate students. | Data | High | Medium | Duplicate student records from re-imports. Data cleanup cost. | **Add a GIN index** on `applications.custom_fields` or a partial B-tree index on `(tenant_id, (custom_fields->>'index_number'))` for CSSPS imports. Add a unique constraint check in the service layer before insertion. Add explicit test for re-import dedup. | 3 |
| R-007 | **Analytics queries in Phase 4 are O(all_applications) with no materialized views.** The enrollment funnel, trend, and lead source effectiveness queries all scan the full applications + inquiries tables. Schools with 3+ years of data (10,000+ applications) will see dashboard timeouts (>500ms p95 target). | Technical | High | Medium | Analytics dashboard is unusable for established schools. Complaints during peak enrollment season. | **Add indexed covering queries** (the spec already uses SQL aggregation, which is good). Add query timeout at 10 seconds. If p95 exceeds 500ms with test data >5000 rows, implement materialized view refreshed hourly. Defer this optimization -- monitor first. | 4 |
| R-008 | **Frontend effort is completely unmeasured in the 2-week-per-phase estimate.** The spec lists 35+ new components, 7+ new pages, 4+ new action files, 5+ new type files. Phase 1 alone has: inquiry form, inquiry table, status badge, communication log, follow-up list, bulk import dialog, duplicate warning, inquiry detail page, inquiry list page, interview schedule form, interview list, screening checklist. That is ~12 components + 2 pages in Phase 1. At 0.5-1 day each, that is 6-12 dev-days of frontend work PER PHASE -- equal to the entire backend estimate. | Schedule | High | High | Phase deadlines missed by 40-60%. Either frontend is cut (bad UX) or backend work is rushed (bugs). | **Split frontend and backend tracks.** Backend developer handles models/services/endpoints/tests. Frontend developer handles pages/components/actions. If only 2 developers: allocate 60% backend, 40% frontend per phase. Realistic per-phase estimate becomes 3 weeks, not 2. | ALL |
| R-009 | **Presigned URL expiry in generated PDFs.** The admission/rejection letter templates use `school.logo_url` which, if it is a presigned S3 URL, will expire. The confirmation letter has the same issue. When PDFs are stored in S3 and later downloaded, the embedded logo URLs are dead. | Technical | High | Medium | PDFs generated with broken images when opened days later. Schools print blank logos on official letters. | **Embed logo as base64 data URI** before passing to WeasyPrint template. This is a known pattern (see memory: risk pattern #27). The `_render_pdf` method should fetch and inline the logo before rendering. | 2, 3 |
| R-010 | **JSONB scoring_criteria on interviews has no server-side validation.** The spec says school-configurable JSONB, but the `InterviewFeedback` schema accepts `dict[str, Any]`. A malicious or buggy client could store arbitrary large JSON (megabytes), non-numeric scores, or deeply nested structures. | Security | High | Low | DoS via large JSONB payloads. Corrupted data that breaks score calculation. | **Add Pydantic validator** on `scoring_criteria` that: (1) limits total keys to 20, (2) validates each value has numeric `score` and `max` fields, (3) limits total serialized size to 10KB. Add test for oversized payload rejection. | 1 |

### Medium Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Phase |
|----|------|----------|----------|-------------|--------|------------|-------|
| R-011 | **Inquiry-to-application conversion loses data.** The `convert_to_application` method splits `guardian_name` on space to get first/last name: `inquiry.guardian_name.split(" ", 1)[0]`. Ghanaian names with more than two parts (e.g., "Nana Kwame Mensah") will misparse. Single-name guardians will have first_name == last_name. | Data | Medium | High | Guardian names mangled in applications converted from inquiries. Manual correction needed. | **Accept the split heuristic** but add a note in the conversion UI: "Please verify guardian name after conversion." Better: store full guardian name and let admin correct during application review. | 1 |
| R-012 | **Waitlist rank hash collision in `pg_advisory_xact_lock`.** The lock key is `hash(f"{tenant_id}_waitlist_rank") & 0x7FFFFFFFFFFFFFFF`. Two different tenant UUIDs could hash to the same key, causing cross-tenant lock contention (not data leak, just performance). | Technical | Medium | Low | Rare slowdowns during concurrent waitlist operations across tenants. | Accept the risk. Hash collisions cause contention, not correctness issues. The probability with UUID inputs is negligible. No action needed. | 2 |
| R-013 | **Return intent confirmation modifies existing `return_intents` table.** Adding 4 columns to an existing table that schools are actively using for return intent surveys. If the migration runs mid-campaign, existing intents get `re_enrollment_confirmed=false` which is correct but may confuse reports that now show a "Confirmed: 0" column. | Integration | Medium | Medium | UI shows misleading "0 confirmed" for campaigns that pre-date this feature. Admins confused. | **Add migration note:** The `re_enrollment_confirmed` column defaults to `false`. For existing campaigns, the "Confirmed" count starts at 0 until the admin explicitly uses the new confirmation flow. Document this in release notes. | 4 |
| R-014 | **Event registration `registered_count` can drift.** The spec uses Python-side `event.registered_count += 1` with `with_for_update()`. This is correct for single-process, but if a transaction fails AFTER the increment but BEFORE commit, the count could temporarily be wrong (it rolls back with the transaction, so this is fine). However, hard-deleting registrations while decrementing count is fragile if the delete succeeds but decrement fails mid-transaction. | Technical | Medium | Low | Registered count shows wrong number. Event appears full when it is not, or allows over-registration. | The `with_for_update()` pattern is correct and transactional. The risk is minimal. As a safety net, add a periodic reconciliation query: `UPDATE school_events SET registered_count = (SELECT COUNT(*) FROM event_registrations WHERE event_id = ...) WHERE ...`. Run monthly or on-demand. | 4 |
| R-015 | **No feature flag enforcement for inquiry module.** The overview mentions "Feature Gate: Professional+" in the original spec (EM-001 context) but `grep` for "Feature Gate" in the spec returns zero matches. The inquiry endpoints use standard `admissions.*` permissions but no subscription tier check. A Starter-tier school gets the full inquiry module. | Schedule | Medium | Medium | Starter schools get features meant for Professional+. Revenue leakage if inquiry module is a paid differentiator. | **Clarify product decision:** Is inquiry module available to all tiers? If not, add `enforce_subscription(["professional", "enterprise"])` dependency to inquiry endpoints. If yes, document the decision. | 1 |
| R-016 | **CSSPS column mapping accepts arbitrary column names.** The `CSSPSColumnMapping` schema has string fields with no validation on the mapped column names. An admin could map `index_number` to a non-existent column header, causing silent data loss (all index_numbers become None) and bypassing deduplication. | Data | Medium | Medium | Failed imports with cryptic errors. Duplicate records if index_number mapping is wrong. | **Validate column names against actual file headers** during the preview step. The preview response includes `detected_columns` -- cross-reference the mapping against this list. Reject the import if any required mapped column does not exist in the file. | 3 |
| R-017 | **Admission letter stores S3 key, not presigned URL.** `decision.decision_letter_url = s3_key` stores the raw S3 key (e.g., `admissions/{tenant_id}/letters/{id}_admission.pdf`). The method returns a presigned URL to the caller, but subsequent reads of `decision_letter_url` from the database return the raw key, not a valid URL. The offer details endpoint correctly re-generates a presigned URL, but any code path that returns `decision_letter_url` directly will show a broken link. | Technical | Medium | Medium | Letter download links broken in some UI paths (e.g., decision list table). | Ensure ALL endpoints that return `decision_letter_url` or `rejection_letter_url` pass the value through `s3.generate_presigned_url()` before sending to the client. Add a schema property or response builder that auto-generates presigned URLs for S3 key fields. | 2 |
| R-018 | **`ApplicationGuardian.first_name` from CSSPS split.** Similar to R-011, the CSSPS import splits `parent_name` into first/last. Ghanaian naming conventions (patronymics, compound names, honorifics like "Nana", "Maame") make this unreliable. | Data | Medium | High | Guardian names mangled for CSSPS imports. Data quality degrades. | Accept for MVP. Add a "Review imported records" step in the CSSPS workflow UI where admins can correct names before finalizing. | 3 |

### Low Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Phase |
|----|------|----------|----------|-------------|--------|------------|-------|
| R-019 | Interview time overlap check may miss edge cases with NULL scheduled_time. | Technical | Low | Low | Possible double-booking if time is not provided. | The `_check_interviewer_overlap` only runs when `scheduled_time` is provided. Interviews without times can overlap. Acceptable for MVP -- schools schedule manually. | 1 |
| R-020 | Inquiry soft-delete does not cascade to follow-ups and communications. | Technical | Low | Low | Orphaned follow-up tasks for deleted inquiries. | Follow-ups have FK CASCADE on `inquiry_id`. Communications also CASCADE. Soft-delete on inquiry does not trigger CASCADE, but follow-ups are filtered by `deleted_at IS NULL` on the inquiry join. Minor data hygiene issue. | 1 |
| R-021 | Analytics service counts are eventually consistent during enrollment peaks. | Technical | Low | Medium | Dashboard numbers lag by one request cycle. | Acceptable. No materialized views yet. Real-time accuracy is not critical for analytics. | 4 |
| R-022 | Tour/event registration is admin-only (AD-8). Public registration deferred. | Schedule | Low | Low | Schools wanting self-service event registration must wait. | Documented as deferred. No risk to current scope. | 4 |
| R-023 | Enrollment confirmation PDF uses `PDFService` (existing) while admission letters use direct `WeasyPrint + Jinja2`. Two different PDF generation patterns in the same module. | Technical | Low | Medium | Maintenance confusion. Inconsistent error handling. | Standardize in a future refactor. Both work. The admission letter pattern is more self-contained. | 2, 3 |

---

## Revised Effort Estimates

### Spec Estimate vs. Revised Estimate

| Phase | Spec Estimate | Backend (Revised) | Frontend (Revised) | Total (Revised) | Delta |
|-------|--------------|-------------------|-------------------|----------------|-------|
| Phase 1: Inquiry + Interview | 2 weeks (10d) | 12 dev-days | 8 dev-days | 20 dev-days | +100% |
| Phase 2: Letters + Offers + Waitlist | 2 weeks (10d) | 10 dev-days | 5 dev-days | 15 dev-days | +50% |
| Phase 3: Enrollment Confirmation + CSSPS | 2 weeks (10d) | 12 dev-days | 6 dev-days | 18 dev-days | +80% |
| Phase 4: Capacity + Re-enrollment + Tours + Analytics | 2 weeks (10d) | 14 dev-days | 10 dev-days | 24 dev-days | +140% |
| **Celery Bootstrap** (prerequisite) | 0 | 3 dev-days | 0 | 3 dev-days | NEW |
| **Total** | **40 dev-days** | **51 dev-days** | **29 dev-days** | **80 dev-days** | **+100%** |

### With 25% Buffer: ~100 dev-days

### Realistic Calendar Time

| Scenario | Calendar Weeks | Notes |
|----------|---------------|-------|
| 2 developers, no parallel frontend | 10 weeks | Sequential phases, one dev on backend + one on frontend per phase |
| 2 developers, parallel frontend | 8 weeks | Frontend developer works on Phase N while backend developer works on Phase N+1 |
| 3 developers (2 backend + 1 frontend) | 7 weeks | Frontend parallelized fully; backend phases sequential |
| 2 developers, spec estimate | 4 weeks | Unrealistic. Would require cutting frontend, reducing tests, and skipping Celery |

**Confidence Level:** Medium -- the admissions module is well-established and the spec is high-quality, but frontend effort is genuinely unknown (no mockups referenced) and Celery bootstrap is an infrastructure task with unknown deployment blockers.

### Phase-by-Phase Breakdown

**Phase 1 (Inquiry + Interview) -- 20 dev-days:**
- Models + Enums + Migration: 1.5d
- Schemas (inquiry.py + interview.py): 1d
- InquiryService (11 methods): 3d (bulk import + conversion are complex)
- InterviewService (8 methods): 2d
- Endpoints (25 endpoints): 2d
- Tests (~46 tests, 5 files): 3d (new table setup + RLS tests)
- Frontend (12 components + 2 pages + 2 action files + 2 type files): 8d
- Delta from spec: +10d (frontend unmeasured, testing underestimated)

**Phase 2 (Letters + Offers + Waitlist) -- 15 dev-days:**
- Column additions + Migration: 0.5d
- PDF templates (2 templates): 2d (WeasyPrint CSS is finicky)
- DecisionService additions (5 methods): 2d
- ApplicantService additions (2 methods): 1d
- Celery tasks (2 tasks): 2d (includes Celery bootstrap integration)
- Endpoints (8 endpoints): 1d
- Tests (~40 tests, 4 files): 2.5d
- Frontend (offer acceptance UI, waitlist management, letter download): 5d
- Delta from spec: +5d (Celery integration, frontend)

**Phase 3 (Enrollment Confirmation + CSSPS) -- 18 dev-days:**
- Models (2 tables) + Migration: 1d
- EnrollmentService modifications (7 methods): 3d (most complex -- modifies existing critical path)
- CSSPSImportService: 3d (file parsing, column mapping, chunked import, dedup)
- Enrollment confirmation PDF template: 1d
- Endpoints (9 endpoints): 1.5d
- Tests (~42 tests, 5 files): 3d
- Frontend (checklist UI, CSSPS import wizard with preview + mapping): 6d
- Delta from spec: +8d (CSSPS complexity underestimated, frontend)

**Phase 4 (Capacity + Re-enrollment + Tours + Analytics) -- 24 dev-days:**
- Models (3 tables) + Migration: 1d
- CapacityService: 2d
- EventService: 2d
- ReturnIntentService modifications: 1.5d
- AnalyticsService (6 analytics methods with SQL aggregation): 4d (complex queries)
- Endpoints (19 endpoints): 2.5d
- Tests (~44 tests, 4 files): 3d
- Frontend (capacity dashboard with charts, events CRUD, analytics funnel visualization, re-enrollment UI): 10d
- Delta from spec: +14d (analytics complexity, frontend dashboard with charts)

---

## Dependency Analysis

### Phase Dependencies (Corrected)

The spec's dependency diagram is:
```
Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

**Assessment: The sequential chain Phase 1 -> Phase 2 -> Phase 3 is correct.** Phase 4's dependency on Phase 1 (for analytics funnel) is also correct.

However, there are **hidden dependencies** the spec does not call out:

1. **Celery Bootstrap -> Phase 2.** The offer_expiry and reminder tasks REQUIRE a working Celery infrastructure. This is a hard blocker. Phase 2 cannot be started until Celery is operational. This should be a Phase 0 or added to Phase 1.

2. **S3 presigned URL pattern -> Phase 2, Phase 3.** Letter generation stores S3 keys and returns presigned URLs. The applicant portal's offer detail endpoint re-generates presigned URLs. Both paths need the S3 service to be configured. This is already done (existing admissions use S3 for document uploads), so this is a soft dependency, already met.

3. **Finance module -> Phase 4 (Re-enrollment).** The `confirm_re_enrollment()` method checks outstanding fees via the finance service. If the finance service interface changes between now and Phase 4 implementation, this breaks. Low risk given finance module is stable.

4. **CSSPS -> Class model.** The CSSPS import needs `Class.capacity` (for advisory warnings) and programme-to-class mapping. If the school has not set up classes for SHS programmes before import, the mapping step fails. This is a user workflow issue, not a code dependency.

### Internal Dependencies

| Component | Depends On | Status |
|-----------|------------|--------|
| InquiryService.convert_to_application() | Application model, ApplicationGuardian model | Ready |
| DecisionService.generate_admission_letter() | WeasyPrint, S3Service, School model | Ready |
| DecisionService.promote_from_waitlist() | VALID_TRANSITIONS dict, AdmissionNotificationService | Ready |
| EnrollmentService.enroll() (modified) | EnrollmentChecklist model (new) | Phase 3 prerequisite |
| CSSPSImportService | Application model, ApplicationGuardian model, admission_periods | Ready |
| CapacityService.get_dashboard() | Student model, Class model, EnrollmentTarget (new) | Phase 4 prerequisite |
| AnalyticsService.get_full_funnel() | Inquiry model (Phase 1) | Must complete Phase 1 first |
| ReturnIntentService.confirm_re_enrollment() | Finance service (existing) | Ready |
| Celery offer_expiry task | run_for_all_tenants(), DecisionService | Celery infra must exist |
| Celery admission_reminders task | run_for_all_tenants(), AdmissionNotificationService | Celery infra must exist |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| Celery + Redis | Infrastructure | High | 2-3 days | Docker-compose config + worker process |
| WeasyPrint (already installed) | PyPI | Low | 0 | Already in requirements.txt |
| S3 (already configured) | AWS | Low | 0 | Already used for document uploads |
| CSSPS file format | GES/WAEC | Medium | N/A | We define our own format; schools map columns |
| openpyxl (for CSSPS Excel parsing) | PyPI | Low | 0 | Already in requirements.txt |

---

## Parallel Work Tracks

### Recommended Approach (2 Developers)

```
Week 1-3:   Dev A: Phase 1 Backend (models, services, endpoints, migration)
            Dev B: Celery Bootstrap + Phase 1 Frontend (inquiry form, table, detail page)

Week 3-5:   Dev A: Phase 2 Backend (letters, waitlist, Celery tasks, offer acceptance)
            Dev B: Phase 1 Frontend (remaining) + Phase 2 Frontend (offer acceptance UI)

Week 5-7:   Dev A: Phase 3 Backend (checklist, CSSPS, enrollment modifications)
            Dev B: Phase 2 Frontend (waitlist UI, letter download) + Phase 3 Frontend (checklist, CSSPS wizard)

Week 7-10:  Dev A: Phase 4 Backend (capacity, events, analytics, re-enrollment)
            Dev B: Phase 3 Frontend (remaining) + Phase 4 Frontend (dashboard, charts, events)
```

### Within Each Phase (Parallel Sub-tracks)

**Phase 1:**
- Track A: Inquiry module (5 tables, InquiryService, inquiry endpoints)
- Track B: Interview module (1 table, InterviewService, interview endpoints)
- Sequential: Inquiry-to-application conversion (depends on both)

**Phase 2:**
- Track A: Letters (PDF templates, generate endpoints)
- Track B: Waitlist management (rank, reorder, promote)
- Sequential: Offer acceptance (depends on letters for offer detail page)

**Phase 3:**
- Track A: Enrollment checklist (models, service, endpoints)
- Track B: CSSPS import (service, parsing, endpoints)
- Sequential: Enrollment flow modification (depends on checklist)

**Phase 4:**
- Track A: Capacity planning (model, service, dashboard)
- Track B: Events/tours (model, service, CRUD)
- Track C: Analytics (6 query methods, dashboard)
- Track D: Re-enrollment confirmation (modification to existing service)
- All four sub-modules are genuinely independent within Phase 4.

---

## Critical Path

The critical path (longest sequential dependency chain) is:

```
Celery Bootstrap (3d)
  --> Phase 1 Backend (12d)
    --> Phase 2 Backend (10d)
      --> Phase 3 Backend (12d)
        --> Phase 4 Backend (14d)
```

**Total sequential backend: 51 dev-days = ~10.2 calendar weeks (1 developer)**

With 2 developers (backend + frontend parallel):
**Minimum: ~7 calendar weeks**
**Realistic with buffer: ~10 calendar weeks**

The bottleneck is **Phase 4** due to 4 independent sub-modules that each need testing + frontend work. This is where a third developer would have the most impact.

---

## Priority-Ordered List: Things Most Likely to Go Wrong

1. **Celery not operational by Phase 2 start.** This is a near-certainty if not explicitly scheduled. The infrastructure TODO has been in the codebase since Sprint 11-12. Without a forcing function, it will continue to be deferred.

2. **Frontend takes 2x longer than anyone expects.** The spec has zero frontend effort estimation. 35 components + 7 pages with forms, tables, badges, modals, and a CSSPS import wizard (with file upload, preview table, column mapping dropdowns, programme mapping) is a substantial frontend effort.

3. **CSSPS import fails on real-world files.** The defined format is clean, but actual CSSPS files from GES have: inconsistent headers across years, merged cells in Excel, BOM characters in CSV, Windows-1252 encoding, missing required fields, phone numbers with leading zeros stripped. The first real import WILL fail and require 2-3 rounds of debugging.

4. **WeasyPrint PDF rendering differences across environments.** Fonts, CSS rendering, and page breaks behave differently in Docker (Alpine/Debian) vs local dev (macOS). Letter formatting that looks correct locally may break in production. Requires testing in the actual Docker image.

5. **Enrollment checklist auto-complete races.** Two admins completing different checklist items simultaneously could both trigger `_auto_complete_checklist()`. The second call finds all required items complete and sets `completed_at` twice. This is harmless (idempotent set) but could cause duplicate log entries.

6. **TENANT_SCOPED_TABLES count in conftest.py.** The spec correctly identifies +10 tables across 4 phases. Current count is 102 (from preschool gap closure). After all 4 phases: 112. But `inquiry_communications` and `event_registrations` have NO SoftDeleteMixin -- verify the dynamic RLS test handles tables without `deleted_at` correctly.

7. **Analytics queries are slow without test data.** The analytics service will appear to work perfectly with 10 test records but degrade at 5000+. Performance testing with realistic data volumes is rarely done during sprint testing.

---

## Testing Sufficiency Analysis

### Spec's Test Plan: ~172 tests across 18 files

| Phase | Test Files | Tests | Assessment |
|-------|-----------|-------|------------|
| 1 | 5 files | ~46 | Adequate for CRUD. **Missing:** bulk import edge cases (empty file, duplicate phone formats, >200 rows), inquiry conversion with existing application, concurrent follow-up completion |
| 2 | 4 files | ~40 | Good coverage. **Missing:** PDF rendering test (currently mocked), presigned URL expiry behavior, Celery task isolation test (cross-tenant), offer expiry for already-responded offers |
| 3 | 5 files | ~42 | Good. **Missing:** CSSPS import with >500 rows, column mapping with non-existent column, Excel file with merged cells, enrollment with both checklist AND deposit requirement simultaneously |
| 4 | 4 files | ~44 | **Weakest phase.** Missing: capacity dashboard with 0 classes, analytics with 0 data, concurrent event registration (race condition), re-enrollment with no finance module configured |

### Specific Test Gaps

1. **No RLS isolation test file** for the 10 new tables. The spec mentions adding to `TENANT_SCOPED_TABLES` but does not list a dedicated RLS test file (like `test_admissions_rls.py` which exists for the original tables). Estimate: +8 tests.

2. **No concurrent operation tests.** Waitlist reorder, event registration, and checklist completion all have race condition vectors. Need at least 3 tests using `asyncio.gather()` to test concurrent execution.

3. **No negative-path tests for CSSPS.** What happens when: file is empty, file has only headers, file is 10MB, file is a PDF (not CSV/Excel), column mapping points to wrong columns, programme maps to non-existent class UUID?

4. **No end-to-end test** for the complete inquiry -> application -> decision -> letter -> offer acceptance -> checklist -> enrollment flow. This is the most critical user journey and should have at least 1 E2E test.

### Revised Test Estimate: ~200 tests (vs 172 in spec)

---

## Backward Compatibility Assessment

### Safe Changes (No Breaking Risk)

- New tables (10 tables) -- additive only
- New endpoints (61 endpoints) -- no existing endpoint signatures change
- New schemas -- additive only
- Column additions with defaults -- existing rows get safe defaults

### Potentially Breaking Changes

| Change | Risk | Mitigation |
|--------|------|------------|
| `EnrollmentService.enroll()` adds checklist check | Medium | AD-3 makes it optional (only when checklist exists). Safe for existing applications. |
| `EnrollmentService.enroll()` adds deposit check | Low | `enrollment_deposit_required` defaults to `false`. Existing periods unaffected. |
| `admission_decisions` gets new columns | None | All new columns are nullable with no default. Existing decisions unaffected. |
| `applications` gets new columns | None | All new columns are nullable or have safe defaults (`false`, `null`). |
| `return_intents` gets `re_enrollment_confirmed` | Low | Defaults to `false`. Existing intents show as "not confirmed" -- accurate for pre-feature data. |
| `admission_periods` gets `reminder_enabled` | None | Defaults to `false`. Reminders off by default. |

**Verdict:** Backward compatibility is well-handled. The AD-3 decision (optional checklist) is the most important guard and it is correctly implemented.

---

## "DONE" Items That May Have Gaps

Reviewing the requirement matrix for items marked "DONE":

| ID | Requirement | Marked As | Potential Gap |
|----|-------------|-----------|---------------|
| EM-058 | Waitlist-to-offer conversion | DONE | The state machine transition exists, but the new `promote_from_waitlist()` method in Phase 2 adds notification and rank clearing. This is an enhancement, not a bug -- the "DONE" status is accurate for the basic transition. |
| EM-053 | Offer letter with acceptance deadline | DONE | `response_deadline` field exists. But there is no enforcement of the deadline -- expired offers can still be accepted. Phase 2 adds `is_expired` check in the applicant portal, which should arguably have been part of the original implementation. |
| EM-076 | Automatic student record creation | DONE | Correct. `EnrollmentService.enroll()` is fully implemented. Phase 3 adds guards but does not change the core logic. |
| EM-027 | Application status tracking | DONE | 14-state machine is complete. No gaps found. |

**No critical gaps found in "DONE" items.** EM-053 is a minor gap (deadline enforcement) but Phase 2 addresses it.

---

## Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| Celery worker process | Background task execution (offer expiry, reminders) | 2-3 days | Minimal -- runs in existing EKS cluster. Add 1 worker pod. |
| Celery Beat scheduler | Periodic task scheduling | Included above | Same pod as worker or separate cron pod. |
| Redis (already exists) | Celery broker | 0 | Already provisioned for caching/rate limiting. |
| WeasyPrint system deps in Docker | PDF generation (fonts, libpango, etc.) | Verify in Dockerfile | Already installed per existing PDF generation. Verify admission letter fonts render correctly. |
| S3 bucket path | `admissions/{tenant_id}/letters/` prefix | 0 | Already using S3 for document uploads. No new bucket needed. |

---

## Recommendations

### Start Early (This Week)

1. **Bootstrap Celery.** Create `celery_app.py`, add worker to docker-compose, write smoke test. This is the longest-lead infrastructure item and blocks Phase 2.
2. **Validate WeasyPrint in Docker.** Render the admission letter template in the production Docker image and verify fonts/layout. CSS rendering differences between macOS and Linux are the #1 source of PDF bugs.
3. **Get a sample CSSPS file.** Contact a pilot SHS school and ask for a redacted CSSPS placement file. Real-world format knowledge is essential before implementing the parser.

### Risk Mitigation Actions

1. **Add CSSPS row limit and chunking** -- 100 rows per flush, 5000 max per import, 202 Accepted for >500 rows.
2. **Embed logos as base64** in all PDF templates to avoid presigned URL expiry.
3. **Add JSONB size validation** on `scoring_criteria` (interviews) and `metadata` (checklist items).
4. **Add RLS test file** for all 10 new tables before merging Phase 1.
5. **Create one E2E test** for the full inquiry-to-enrollment journey.

### Blockers to Resolve Before Starting

1. **Celery: Production-ready or stub?** The spec uses `run_for_all_tenants()` which exists but is designed for "TODO: Wire to Celery." Decide: implement real Celery now, or keep as async functions called from a management command?
2. **Inquiry module tier gating:** Is this Professional+ or available to all tiers? Product decision needed before Phase 1 starts.
3. **CSSPS format confirmation:** Does the proposed standard format (Section 5) align with what pilot SHS schools actually receive from GES?

### Technical Spikes Needed

1. **WeasyPrint performance benchmark:** Generate 50 letters in sequence. Measure wall time. If >30s, implement async generation pattern.
2. **CSSPS file format survey:** Collect 2-3 real CSSPS files from different years/regions. Verify the column mapping approach handles actual variations.
3. **Analytics query performance:** Load 10,000 applications into a test database. Run all 6 analytics queries. Verify p95 < 500ms.
