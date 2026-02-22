# School Chain Support -- Risk Analysis

**Author:** Risk Analyst (Claude Opus 4.6)
**Date:** 2026-02-16
**Version:** 1.0
**Status:** DRAFT -- For Review

---

## Executive Summary

School Chain Support is a **HIGH complexity** feature that touches nearly every layer of the SIMS Plus stack: 30+ database tables need a new `school_id` column, the JWT token structure changes, a new `user_schools` junction table introduces a new authorization dimension, the middleware/dependency chain must propagate school context, every service needs optional school-scoped filtering, and the frontend needs a SchoolProvider with school switching. The total estimated effort is **52-65 developer-days** (10-13 weeks for a single full-stack developer, or 5-7 weeks for a two-person team).

The design is architecturally sound -- keeping RLS at `tenant_id` and doing school-level filtering at the application layer is the correct decision. However, the risk profile is dominated by three concerns:

1. **Migration blast radius** -- Adding `school_id` to 30+ tables in a single migration with backfill logic is the single largest schema change in the project's history. Any error corrupts data for all existing tenants.
2. **Silent data scoping bugs** -- Unlike RLS (which fails closed with zero rows), application-layer school filtering fails silently if a service method forgets the `school_id` filter. A chain admin might see correct data while a school admin sees cross-school data within their tenant -- not a data *leak* across tenants, but a data *exposure* within the tenant.
3. **Backward compatibility surface** -- The "zero changes for single-school tenants" promise is fragile. Any bug in the SchoolContext fallback path breaks the 100% of current users to serve the 0% of chain users at launch.

**Recommendation:** Proceed with the design, but **NOT** as Sprint 15-16 (before Parent Portal). Schedule this for **Sprint 19-20** (Phase 3, Jul 2026) after Beta Launch stabilizes. Rationale detailed below.

---

## 1. Risk Register

### CRITICAL Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R01 | **Migration backfill corrupts existing data** -- Adding nullable `school_id` to 30+ tables and backfilling from the tenant's single school could fail partway, leaving some tables backfilled and others not, creating an inconsistent state. | Quality | CRITICAL | Medium | All existing tenants have broken data. Reports show NULL school_id for some records. Finance calculations fail on NOT NULL columns. | 1. Wrap entire migration in a single transaction (Alembic default). 2. Run migration on a production clone first. 3. Add pre-migration validation query that counts rows-per-table and post-migration query that verifies all rows have school_id. 4. Create a rollback migration that reverses column additions. 5. Schedule migration during maintenance window with DB snapshot. |
| R02 | **`get_school_for_tenant()` breaks silently for chains** -- The finance helper at `/backend/app/api/v1/endpoints/finance/_helpers.py` line 28-40 uses `.limit(1)` to get "the school." For a chain tenant with 5 schools, it returns whichever school Postgres picks first (undefined order). All invoices, payments, and credit notes for a chain would be associated with the wrong school with no error. | Technical | CRITICAL | High (certain if chain tenant is created before fix) | Finance data integrity -- invoices attributed to wrong school, fee structures applied to wrong students, financial reports inaccurate. | Replace `get_school_for_tenant()` with a `SchoolContext` dependency that reads `X-Active-School` header and validates it against the user's `accessible_school_ids`. This MUST be the first change implemented before any chain tenant can be created. Add a startup check that prevents chain tenant creation if the old function is still in use. |
| R03 | **Service layer school filtering is opt-in, not enforced** -- Unlike RLS (database-enforced), school-level filtering requires every service method to add `.where(Model.school_id == school_id)` when `school_id` is present. If a single service method misses this, a school-level user in a chain sees data from all schools in the tenant. With 10+ service files and 100+ service methods, the probability of at least one miss is near-certain. | Multi-Tenancy | CRITICAL | High | Within-tenant data exposure. A teacher at School A in a chain sees students/scores/attendance from School B. Not a cross-tenant leak but a significant privacy violation. | 1. Create a `SchoolScopedQuery` helper that wraps common query patterns and always applies school_id filter. 2. Write integration tests for EVERY service method with a two-school chain fixture, verifying school A user cannot see school B data. 3. Add a linting rule or code review checklist item for school_id filtering. 4. Consider a `school_id_filter` decorator for service methods. |

### HIGH Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R04 | **JWT token size exceeds limits with `accessible_school_ids`** -- Design caps at 50 schools with fallback to `"all_schools": true`. Each UUID is 36 chars. 50 UUIDs = ~1,800 chars in the JWT payload. With existing claims (permissions list for chain_admin is 11 entries), total JWT could reach 3-4KB. HTTP headers have practical limits (8KB typically, but some proxies enforce 4KB). AWS ALB default header limit is 16KB, but Lambda@Edge and some CDN configs limit to 8KB. | Technical | HIGH | Medium | Chain tenants with 20+ schools experience intermittent auth failures depending on proxy/CDN configuration. Difficult to diagnose because it works in dev (no proxy) but fails in production. | 1. Implement the `"all_schools": true` fallback at a lower threshold (e.g., 20 schools instead of 50). 2. When `all_schools` is true, the backend must query `user_schools` on each request to resolve access -- add Redis caching with `{tenant_id}:{user_id}:schools` key and 5-minute TTL. 3. Measure actual JWT size in tests and add a size assertion. 4. Document the header size constraint for infrastructure team. |
| R05 | **`X-Active-School` header lost in background jobs / Celery tasks** -- Celery tasks do not have HTTP request context. Any background job (future: PDF generation, email sending, bulk operations) that needs school context will not have the `X-Active-School` header. The current codebase has no Celery tasks yet, but Sprint 17-18 (Beta Launch) may add them. | Multi-Tenancy | HIGH | Medium | Background jobs process data without school context, potentially mixing data across schools in a chain. Or jobs fail entirely because SchoolContext dependency cannot resolve. | 1. Design SchoolContext to accept explicit `school_id` parameter (not only from header). 2. For Celery tasks, pass `school_id` as a task argument alongside `tenant_id`. 3. Add a `SchoolContext.from_explicit(school_id)` classmethod for non-HTTP contexts. 4. Document this pattern before any Celery integration. |
| R06 | **Unique constraint conflicts after adding school_id** -- Several tables have unique constraints scoped to `tenant_id` only. For example, `uq_academic_year_name` on `academic_years` is `(tenant_id, name)`. In a chain, two schools might both have an academic year named "2025/2026". The current constraint would reject the second insert. This applies to: `academic_years`, `terms`, `subjects`, `grading_scales`, `exams` (name per term), `fee_types`, `fee_structures`. | Technical | HIGH | High (certain for chains with similar school types) | Chain onboarding fails or requires schools to use unique names for everything, making the product unusable for chains. | 1. Audit ALL unique constraints on tables gaining `school_id`. 2. Alter constraints to include `school_id` in the unique tuple: e.g., `(tenant_id, school_id, name)` for academic_years. 3. Handle NULL school_id in constraints (COALESCE pattern, as used in `exam_subjects`). 4. This must be part of the migration, not a follow-up. The number of affected constraints is at least 12 based on codebase review. |
| R07 | **Redis cache keys not school-scoped** -- The current tenant cache at `/backend/app/middleware/tenant.py` uses `CacheKeys.tenant_by_subdomain()`. If any future caching (e.g., fee structure lookups, academic year resolution) uses tenant-only keys, chain tenants will get stale/wrong data when switching schools. | Multi-Tenancy | HIGH | Medium | Cache returns School A's fee structure when user switches to School B within the same tenant. | 1. Establish cache key convention: `{tenant_id}:{school_id}:{feature}:{key}` from day one. 2. Audit all Redis usage (currently only tenant lookup and rate limiting -- low risk today but high risk as caching grows). 3. Add `CacheKeys.school_scoped(tenant_id, school_id, feature, key)` helper. |
| R08 | **Parent Portal (Sprint 15-16) needs school context for chain parents** -- A parent with children in multiple schools within a chain needs to see the correct school's data when viewing each child. If Parent Portal ships before school chain support, it will hardcode single-school assumptions that must be reworked. If school chain ships first, Parent Portal must handle multi-school parents from day one. | Timeline | HIGH | High | Either Parent Portal ships with single-school assumption (rework later, estimated 5-8 days of rework) or both features are delayed by coupling. | Recommended: Ship Parent Portal first (Sprint 15-16) with single-school only. Add a documented TODO for chain-parent support. Ship school chain support in Sprint 19-20. The rework cost (5-8 days) is lower than the coupling cost of doing both simultaneously (estimated 15+ days of integration complexity). |
| R09 | **`user.email` uniqueness constraint breaks for chain users** -- Current constraint is `UNIQUE(email)` globally on the users table (line 58 in `/backend/app/models/user.py`). For a chain, the same person (e.g., a chain admin) needs ONE user record accessible across schools, but a teacher who works at two schools in the chain also needs one record. However, if the system creates separate user records per school (wrong approach), the unique email constraint blocks it. | Technical | HIGH | Medium | Chain admin or multi-school teacher cannot be created, or the email uniqueness constraint must be relaxed (which has security implications for single-school tenants). | The design correctly uses `user_schools` junction table rather than duplicating users. Verify: 1. A single user record can have multiple `user_schools` entries. 2. The email constraint `UNIQUE(email)` or `UNIQUE(email, tenant_id)` is compatible with this. Based on code review, `users.email` has a global `unique=True` -- this MUST be changed to a composite `UNIQUE(email, tenant_id)` if not already done. Memory notes suggest this was done, but the model file shows `unique=True` on line 58. **Verify actual DB state.** |

### MEDIUM Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R10 | **School switching creates inconsistent UI state** -- When a chain user switches schools via the SchoolProvider, any cached data on the frontend (React state, SWR cache, TanStack Query cache) from the previous school remains visible momentarily. If the user is on a student list page and switches schools, stale data from School A appears until the refetch completes. | Quality | MEDIUM | High | User confusion, potential for actions on stale data (e.g., marking attendance for School A students while viewing School B). | 1. SchoolProvider must invalidate ALL data caches on school switch. 2. Show a loading overlay during school switch. 3. Redirect to dashboard on school switch to avoid stale-context pages. 4. The `X-Active-School` cookie must be set BEFORE any API call fires. |
| R11 | **Frontend `apiFetch` does not send `X-Active-School` header** -- The current `/frontend/lib/api.ts` only sends `X-Subdomain` header. Every `apiGet`, `apiPost`, etc. call will need modification to also send the active school header. With 10+ action files calling these functions, this is a broad change. | Technical | MEDIUM | Low (if centralized in apiFetch) | API calls missing school context, causing SchoolContext to fallback to "first school" for chain tenants. | Modify `apiFetch` to read `X-Active-School` from cookie and include it in all requests. This is a ONE-LINE change in the centralized function, making the risk low IF done correctly. The risk is in forgetting to do it. |
| R12 | **Test infrastructure does not support multi-school fixtures** -- Current conftest.py creates a single tenant + single school. Testing chain support requires fixtures with: 1 tenant, 2+ schools, users with different school associations, and data scoped to each school. The two-engine test pattern needs extension. | Quality | MEDIUM | High | Inadequate test coverage for chain scenarios, leading to bugs in production. | 1. Create a `chain_tenant_fixture` in conftest.py that sets up tenant (type=school_chain), 2 schools, chain_admin, and school-specific users. 2. Create helper functions for populating school-scoped data. 3. Budget 5-8 days for test infrastructure alone. |
| R13 | **`student_id` auto-generation uses school prefix** -- Student IDs are generated as `{prefix}-{year}-{seq}` where prefix comes from `school.student_id_prefix`. In a chain, two schools with prefix "STU" would generate conflicting IDs. The `pg_advisory_xact_lock` is presumably scoped to tenant, not school. | Technical | MEDIUM | Medium | Duplicate student IDs within a chain, or sequence gaps/conflicts. | 1. Scope the advisory lock key to include school_id: `hash(tenant_id + school_id)`. 2. Ensure student_id uniqueness constraint includes school_id or is globally unique within tenant. Current constraint `uq_students_student_id_tenant` is `(student_id, tenant_id)` -- this should be sufficient if prefixes differ per school, but add a chain-specific test. |
| R14 | **Onboarding service hardcodes `TenantType.SINGLE_SCHOOL`** -- `/backend/app/services/onboarding.py` line 123 always creates tenants as `SINGLE_SCHOOL`. The new `register-chain` endpoint needs a separate code path, but the existing `register_school` method creates tenant+school+admin as an atomic unit. Chain registration creates tenant+admin (no school initially, or with first school). | Technical | MEDIUM | Low | New endpoint is straightforward to add, but sharing code between single-school and chain onboarding is tricky without introducing bugs in the existing path. | 1. Create a separate `register_chain()` method rather than adding conditionals to `register_school()`. 2. Share validation logic (subdomain check, email check) but keep creation paths separate. 3. Test that `register_school()` still creates `SINGLE_SCHOOL` type after the change. |
| R15 | **Performance degradation from school_id JOINs and filters** -- Adding `school_id` filter to every query adds overhead. For single-school tenants (the majority at launch), this is a no-op filter on a nullable column. But the query planner may not optimize it well, especially without proper indexing. | Infrastructure | MEDIUM | Medium | p95 API response time increases from ~200ms to ~400ms for common queries. | 1. Add composite indexes: `(tenant_id, school_id)` on all tables gaining school_id. 2. For single-school tenants, SchoolContext should set school_id=NULL (skip filter) rather than school_id=the_one_school. 3. Run EXPLAIN ANALYZE on top 10 queries before and after. |
| R16 | **Preschool module has zero school_id awareness** -- All 7 preschool tables (`learning_areas`, `developmental_skills`, `preschool_rating_scales`, `preschool_ratings`, `student_skill_assessments`, `progress_observations`, `daily_activity_logs`, `preschool_reports`) lack school_id. The preschool service at `/backend/app/services/preschool.py` has no school filtering. | Technical | MEDIUM | High (certain) | Chain with preschool + primary schools: preschool data from one school visible to users of another school in the chain. | Add school_id to all 7 preschool tables in the migration. Add school_id filter to preschool service methods. |

### LOW Risks

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R17 | **Chain dashboard pages are new frontend work** -- `/chain/dashboard` and `/settings/chain/schools` are new pages with no existing patterns to copy. Design and UX decisions needed. | Knowledge | LOW | Low | Slower development, but no data risk. | Use existing dashboard and settings pages as templates. Get UX mockups before implementation. |
| R18 | **Email uniqueness check in onboarding queries globally** -- `_check_email_exists()` at line 203 in onboarding.py queries ALL tenants (no tenant_id filter). This is intentional for cross-tenant uniqueness, but for chain admins managing multiple tenants, this could block legitimate registrations. | Technical | LOW | Low | Edge case -- affects only users who are admins of multiple unrelated tenants. | Document this as a known limitation. Address in Phase 4 if user feedback indicates it is a real issue. |
| R19 | **School deletion/deactivation in a chain has cascading effects** -- If a school in a chain is deactivated, its students, staff, and financial data remain. What happens to user_schools entries? What happens to users whose only school is the deactivated one? | Technical | LOW | Low | Orphaned data, confused users. | Define school lifecycle states (active, inactive, archived) and their effects on associated data. Add soft-delete cascade rules to user_schools. |

---

## 2. Effort Estimate

### Component Breakdown

#### Backend: Database & Models (16-20 days)

| Component | Complexity | Estimate | Notes |
|-----------|------------|----------|-------|
| `user_schools` junction table model | 3 | 2 days | New model with composite unique constraint, role_at_school enum, is_primary flag. Must handle lazy="raise" pattern. |
| Add `school_id` to 30+ tables (model changes) | 5 | 3 days | Nullable FK to schools.id, consistent pattern across all models. Must update `__table_args__` for affected unique constraints. |
| Alembic migration: add columns | 5 | 3 days | Single migration adding school_id to ~30 tables. Must include index creation, FK constraints, and COALESCE-based unique constraint updates. Requires extensive testing on clone DB. |
| Alembic migration: backfill data | 5 | 3 days | For each tenant, find the single school, UPDATE all rows in all 30 tables to set school_id = that school. Must handle tenants with no school (error state). Must be idempotent. |
| Unique constraint audit + migration | 3 | 2 days | Identify all unique constraints that need school_id added. At least 12 constraints. Drop old, create new in migration. |
| `SchoolContext` dependency | 3 | 2 days | New FastAPI dependency: reads X-Active-School header, validates against JWT accessible_school_ids, resolves school for single-school tenants. Replaces `get_school_for_tenant()`. |
| Finance helper refactor | 2 | 1 day | Replace `get_school_for_tenant()` with SchoolContext usage across all finance endpoints. |

#### Backend: Auth & JWT (5-7 days)

| Component | Complexity | Estimate | Notes |
|-----------|------------|----------|-------|
| JWT claims: `tenant_type`, `accessible_school_ids` | 3 | 2 days | Modify `create_access_token()` in security.py and `authenticate()` / `refresh_tokens()` in auth.py. Query user_schools to populate claims. Add `all_schools` fallback for large chains. |
| Token refresh: pick up new schools | 2 | 1 day | `refresh_tokens()` must re-query user_schools to include newly added schools. |
| `get_validated_current_user` changes | 3 | 2 days | Extract and validate `accessible_school_ids` from JWT. Store in request.state. Validate X-Active-School against accessible_school_ids. |
| Chain onboarding endpoint | 3 | 2 days | `POST /onboarding/register-chain`: create tenant (type=school_chain), chain_admin user (school_id=NULL), no school initially. `POST /schools/chain/add`: add school to existing chain tenant. |

#### Backend: Service Layer (10-12 days)

| Component | Complexity | Estimate | Notes |
|-----------|------------|----------|-------|
| School-scoped query helper | 3 | 2 days | Reusable helper that adds `.where(Model.school_id == school_id)` when school_id is not None. Must handle both ORM queries and raw SQL. |
| Student service: school filtering | 2 | 1 day | Add school_id param to list, search, import, enrollment methods. |
| Staff service: school filtering | 2 | 1 day | Add school_id param to list, search methods. |
| Academic service: school filtering | 3 | 2 days | academic_years, terms, classes, subjects, grading -- all need school_id filtering. |
| Attendance service: school filtering | 2 | 1 day | student_attendance, staff_attendance queries. |
| Exam service: school filtering | 3 | 2 days | exams, exam_subjects, scores, CAs, term_reports. Complex due to nested queries. |
| Finance services (6 files): school filtering | 3 | 2 days | Already have school_id on main tables but invoice/payment services need SchoolContext integration. |
| Preschool service: school filtering | 2 | 1 day | All preschool queries need school_id. |
| Timetable service: school filtering | 1 | 0.5 days | class_timetables, school_periods, school_holidays. |

#### Frontend (10-13 days)

| Component | Complexity | Estimate | Notes |
|-----------|------------|----------|-------|
| `SchoolProvider` context | 3 | 2 days | New context: reads JWT for accessible_school_ids, manages active school in cookie, provides useSchool() hook. Must integrate with existing TenantProvider. |
| School selector in sidebar | 2 | 1 day | Dropdown in AppSidebar, visible only for chain tenants. Shows school name + logo. |
| `apiFetch` X-Active-School header | 1 | 0.5 days | Modify `/frontend/lib/api.ts` to read active-school cookie and include X-Active-School header. |
| Server Actions: school context propagation | 3 | 2 days | All 10+ action files need to pass school context through API calls. |
| Chain dashboard page | 3 | 2 days | `/chain/dashboard` with multi-school overview: student counts, staff counts, financial summary per school. |
| Chain settings pages | 3 | 2 days | `/settings/chain/schools`: list schools, add school form, school details. |
| School switch UX: cache invalidation + loading | 2 | 1 day | Clear all client caches on school switch, show loading overlay, redirect to dashboard. |
| UI conditional rendering (chain vs single) | 2 | 1.5 days | Hide/show chain-specific UI elements. Ensure zero visual changes for single-school tenants. |

#### Testing (12-15 days)

| Component | Complexity | Estimate | Notes |
|-----------|------------|----------|-------|
| Test infrastructure: chain fixtures | 3 | 2 days | conftest.py additions: chain tenant, 2 schools, chain_admin, school_admin_A, school_admin_B, teacher_A, teacher_B. |
| Migration tests | 5 | 3 days | Test migration on empty DB, on DB with existing data, verify backfill, verify rollback. |
| Service layer school isolation tests | 5 | 3 days | For EVERY service method, verify school A user cannot see school B data. At least 50 test cases. |
| JWT / auth tests | 3 | 2 days | Test accessible_school_ids in token, school switching validation, all_schools fallback, cross-school rejection. |
| Frontend integration tests | 3 | 2 days | SchoolProvider behavior, school switching, API header propagation. |
| Backward compatibility tests | 3 | 2 days | Full regression suite run with single-school tenant to verify zero behavioral changes. |
| Performance benchmarks | 2 | 1 day | Before/after query performance comparison on top 10 endpoints. |

### Total Effort Summary

| Category | Low Estimate | High Estimate |
|----------|-------------|---------------|
| Backend: DB & Models | 16 days | 20 days |
| Backend: Auth & JWT | 5 days | 7 days |
| Backend: Services | 10 days | 12 days |
| Frontend | 10 days | 13 days |
| Testing | 12 days | 15 days |
| **Total** | **53 days** | **67 days** |

**Confidence Level:** Medium -- The scope is well-defined by the architect designs, but the number of tables (30+) and service methods (100+) means estimation uncertainty is high. Each table has unique constraints, relationships, and service patterns that may surface unexpected complications.

**Recommended Buffer:** 25% -- Justified by the migration complexity (historically, large schema migrations take 1.5x the estimate), the number of unique constraints to audit (12+), and the testing burden of verifying school isolation across all services.

**Realistic Total: 66-84 developer-days (13-17 weeks for 1 developer, 7-9 weeks for 2 developers)**

---

## 3. Dependency Map

### Internal Dependencies

| Component | Depends On | Status |
|-----------|------------|--------|
| `user_schools` model | Base models, User model, School model | Ready |
| Add school_id columns migration | All model files updated | Must be first |
| Backfill migration | Add-columns migration complete | Sequential |
| Unique constraint migration | Add-columns migration complete | Sequential |
| SchoolContext dependency | user_schools model, JWT changes | Blocked until models done |
| JWT claim changes | user_schools table exists, auth service updated | Blocked until migration done |
| Service layer changes | SchoolContext dependency, models with school_id | Blocked until SchoolContext done |
| Finance helper refactor | SchoolContext dependency | Blocked until SchoolContext done |
| Frontend SchoolProvider | JWT claim changes (accessible_school_ids) | Blocked until JWT changes done |
| School selector UI | SchoolProvider | Sequential |
| Chain onboarding | user_schools model, JWT changes | Blocked until models done |
| All integration tests | All implementation complete | Last |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| None identified | -- | -- | -- | This feature is entirely internal. No external API integrations needed. |

### Critical Dependency Chain (Longest Path)

```
Models + Migration (8 days)
    --> SchoolContext dependency (2 days)
        --> JWT/Auth changes (5 days)
            --> Service layer changes (10 days, parallelizable)
            --> Frontend SchoolProvider (2 days)
                --> Frontend UI changes (6 days)
                    --> Integration tests (5 days)
                        --> Backward compat tests (2 days)
```

**Critical Path Length: ~40 days** (with parallelization of service + frontend work)

---

## 4. Sprint Recommendation

### Option A: Sprint 15-16 (Before Parent Portal) -- NOT RECOMMENDED

**Pros:**
- Parent Portal would have school context from day one
- Clean architecture for chain parents

**Cons:**
- Delays Parent Portal by 7-9 weeks (2 sprints = 4 weeks, but chain support is 7-9 weeks of work)
- No chain customers exist yet -- zero revenue impact from having chain support earlier
- Highest risk to existing single-school tenants (100% of current users)
- Sprint 15-16 scope would balloon from Parent Portal to Parent Portal + Chain Support
- Testing burden is enormous -- 30+ table migration + new auth flow + all service changes must be regression-tested

**Verdict:** Hard No. The risk-to-reward ratio is unacceptable. Delaying paying features for speculative chain support is a strategic error.

### Option B: Sprint 17-18 (Before Beta Launch) -- NOT RECOMMENDED

**Pros:**
- Beta launch would support both single-school and chain tenants
- Pilot schools could include a chain

**Cons:**
- Sprint 17-18 is "Performance optimization + Beta Launch" -- adding chain support here creates a triple-scope sprint
- A 30+ table migration just before beta launch is reckless. If the migration has issues, beta launch slips.
- Beta launch should focus on stability, not new architectural features
- No time for the migration to "soak" in production before beta users arrive

**Verdict:** No. Beta launch is about proving single-school stability. Chain support adds uncertainty at the worst possible time.

### Option C: Sprint 19-20 (Phase 3, Jul 2026) -- RECOMMENDED

**Pros:**
- Beta launch (Sprint 17-18) has validated the single-school platform
- Real user feedback informs chain requirements (we may learn things that change the design)
- Migration can be tested against real production data patterns
- 2 full sprints of buffer between Beta and chain support
- Phase 3 is explicitly labeled "Enhancement" in the roadmap
- Boarding and Transport (also Phase 3) may themselves need school_id -- doing chain first means they get it right from the start

**Cons:**
- Parent Portal (Sprint 15-16) ships without chain awareness -- 5-8 days rework later
- Chain customers cannot onboard until Jul 2026

**Mitigation for cons:**
- Parent Portal rework cost (5-8 days) is budgeted into the chain support estimate
- Chain customers are not yet knocking on the door -- enterprise tier with chain support is a future revenue stream, not current demand

**Verdict:** Yes. Sprint 19-20 is the right time. The migration has production data to validate against, the platform is stable, and the team has breathing room.

### Option D: Sprint 21-22 (After Boarding + Transport) -- ACCEPTABLE ALTERNATIVE

If Sprint 19-20 is dedicated to Boarding/Transport, push chain support to 21-22. The key constraint is: chain support must ship before Boarding and Transport are extended to chains. If Boarding/Transport are single-school only at first, this works.

### Final Recommendation

**Sprint 19-20 (Phase 3, Jul 2026)**

With the following preparation in earlier sprints:
- **Sprint 15-16 (Parent Portal):** Add a `SchoolContext` placeholder that always returns the single school. This establishes the pattern without the complexity. Cost: 1 day.
- **Sprint 17-18 (Beta):** Validate single-school architecture under real load. Collect data on table sizes for migration planning.
- **Sprint 19-20:** Full chain support implementation.

---

## 5. Complexity Score

### Score: 8 / 10

**Justification:**

| Factor | Score | Reasoning |
|--------|-------|-----------|
| Scope breadth | 9/10 | 30+ tables, 10+ services, 10+ frontend action files, JWT, middleware, migrations. Touches almost every module. |
| Data migration risk | 8/10 | Largest schema change in project history. Backfill across all tables. Production data at risk. |
| Architectural impact | 7/10 | New authorization dimension (school-level). New request context propagation. New JWT claims. |
| Testing complexity | 8/10 | School isolation must be verified for every service method. Migration testing on production clones. Backward compatibility for all existing features. |
| Backward compatibility | 7/10 | "Zero changes for single-school" is the promise. Every SchoolContext fallback path is a potential regression. |
| Integration points | 6/10 | No external integrations, but internal integration across all modules is extensive. |
| Unknowns | 5/10 | Design is thorough. Main unknowns are unique constraint conflicts and performance impact. |

The score of 8 places this in the "Highly Complex -- Major effort, multiple dependencies, 2+ weeks" category. The actual timeline (7-9 weeks for 2 developers) confirms this assessment.

---

## 6. Go/No-Go Recommendation

### GO -- With Conditions

The design from the Solution Architect and Tenancy Architect is **sound**. The core decisions are correct:

1. **RLS stays at tenant_id** -- Correct. Adding school_id to RLS would require 48+ policy rewrites and a new PostgreSQL function. Application-layer filtering for school scope within a trusted tenant boundary is appropriate.

2. **X-Active-School header instead of new JWT** -- Correct. Avoids token refresh on every school switch. Validated server-side against JWT claims.

3. **user_schools junction table** -- Correct. Avoids user duplication. Supports multi-school staff naturally.

4. **Backward compatibility via SchoolContext auto-resolve** -- Correct pattern, but implementation must be flawless. Single-school tenants should experience literally zero code path changes.

### Conditions for GO

1. **Migration must be tested on a production clone** before any production run. Not a staging environment -- a clone of actual production data.

2. **Unique constraint audit must be complete** before migration development begins. The list of 12+ constraints that need school_id added is a prerequisite, not a discovery during implementation.

3. **Service layer school isolation tests must achieve 100% coverage** of service methods that touch school-scoped data. No method should be untested.

4. **Backward compatibility regression suite must pass** with zero failures before merge. This means running the full existing test suite against the chain-enabled codebase with a single-school tenant.

5. **The `get_school_for_tenant()` function must be replaced** before any chain tenant can be created in any environment (including staging). This is a hard blocker per Risk R02.

6. **Feature flag recommended** -- `chain_support_enabled` in tenant features JSONB. Even after code ships, chain creation should be gated until manual verification.

### Red Flags (Things That Would Change to NO-GO)

- If the team discovers that some tables are shared across tenants (no tenant_id) and also need school_id -- this would require RLS changes, escalating complexity significantly.
- If the JWT size issue (R04) proves worse than estimated (e.g., existing JWTs are already near 4KB).
- If the migration on a production clone reveals data inconsistencies (e.g., rows with no tenant, rows with invalid school_id FKs).

---

## 7. Multi-Tenancy Risk Assessment

### New Tables Requiring RLS Policies

| Table | RLS Needed? | Notes |
|-------|-------------|-------|
| `user_schools` | YES | Must have `tenant_id = get_current_tenant_id()` policy. This is the most sensitive new table -- it controls authorization. |

### Tables Gaining school_id (No New RLS -- Application Layer Only)

All 30+ tables listed in the Tenancy Architect's analysis gain `school_id` as a nullable FK. RLS remains at `tenant_id`. School filtering is application-layer only.

### Cross-Tenant Data Access Vectors: None Introduced

The chain feature does NOT change the RLS architecture. Tenant isolation remains database-enforced. The risk is within-tenant cross-school exposure, not cross-tenant leakage.

### Within-Tenant Cross-School Exposure Vectors

| Vector | Description | Severity | Mitigation |
|--------|-------------|----------|------------|
| Missing service filter | Service method does not add `.where(school_id == ...)` | HIGH | Mandatory integration tests per service method |
| Cache bleed | Redis cache key not school-scoped | MEDIUM | Establish `{tenant}:{school}:{feature}:{key}` convention |
| Background job context loss | Celery task missing school_id | MEDIUM | Pass school_id as explicit task argument |
| Frontend stale data | Client cache not cleared on school switch | LOW | Clear all caches on school switch |

### Cache/Session Tenant Bleed Risks

- **Current state:** Only tenant-level caching (subdomain lookup). Low risk.
- **Post-chain state:** If any school-level caching is added without school-scoped keys, bleed risk is MEDIUM.
- **Session:** No server-side sessions. JWT is stateless. No bleed risk from sessions.
- **Connection pool:** Existing checkout listener clears `app.current_tenant_id`. No change needed for chain support (RLS stays at tenant_id).

### Background Job Tenant Context

- **Current state:** No Celery tasks in codebase. No background jobs.
- **Post-chain state:** When Celery is added (planned for Phase 3-4), every task must carry both `tenant_id` AND `school_id`. The SchoolContext dependency must support explicit initialization, not just HTTP header extraction.

---

## 8. Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| Production DB clone for migration testing | Test backfill migration against real data | 1 day (RDS snapshot + restore) | ~$50 for temporary RDS instance (terminate after testing) |
| Alembic migration maintenance window | Run schema migration with table locks on 30+ tables | 1-2 hours downtime | Zero cost, but requires communication to beta users |
| Additional composite indexes | `(tenant_id, school_id)` on 30+ tables | Part of migration | Slight increase in storage (~5-10% index overhead) and write latency |
| Redis memory increase | School-scoped cache keys increase key count | Minimal | Current ElastiCache plan likely sufficient |
| No new infrastructure required | Chain support is a data model + application logic change | -- | -- |

---

## 9. Recommended Approach

### Parallel Tracks (After Migration Is Complete)

- **Track A (Backend Services):** Refactor all service files to accept optional school_id. Can be done module by module: Student -> Staff -> Academic -> Attendance -> Exams -> Finance -> Preschool -> Timetable.
- **Track B (Frontend):** SchoolProvider, school selector, apiFetch changes, chain pages. Can proceed once JWT changes are deployed.
- **Track C (Testing):** Build chain test fixtures. Write isolation tests. Can start fixture work in parallel with Track A.

### Sequential Dependencies (Must Be Done In Order)

1. **Unique constraint audit** -- Identify all constraints needing school_id (2 days)
2. **Model changes** -- Add school_id to all models + user_schools model (3 days)
3. **Migration: add columns + constraints + indexes** (3 days)
4. **Migration: backfill existing data** (3 days)
5. **SchoolContext dependency** (2 days)
6. **JWT/Auth changes** (5 days)
7. *Tracks A, B, C in parallel* (10-12 days with 2 developers)
8. **Integration testing** (5 days)
9. **Backward compatibility testing** (2 days)
10. **Performance benchmarking** (1 day)

### Critical Path

```
Constraint Audit (2d) --> Models (3d) --> Migration (6d) --> SchoolContext (2d) --> JWT (5d)
    --> [Parallel: Services (12d) | Frontend (10d) | Test Fixtures (3d)]
        --> Integration Tests (5d) --> Compat Tests (2d) --> Perf Bench (1d)
```

**Minimum Timeline:** 40 days (2 developers, maximum parallelization)
**Realistic Timeline:** 50 days (2 developers, with buffer and review cycles)

---

## 10. Recommendations

### Start Early (Before Sprint 19-20)

1. **Sprint 17 (Beta prep):** Run the unique constraint audit. Document every constraint that needs school_id. This is zero-risk investigative work that saves 2 days from the critical path later.
2. **Sprint 15-16 (Parent Portal):** Implement a `SchoolContext` stub that always returns the single school. This establishes the API pattern and header convention without the complexity. When chain support ships, the stub becomes the real implementation.
3. **Sprint 18 (Post-Beta):** Take a production DB snapshot and test the migration on a clone. Identify any data quality issues before the actual sprint begins.

### Risk Mitigation Actions

1. **Create a chain feature flag** in the tenant.features JSONB. Gate chain creation behind it. Allow incremental rollout.
2. **Implement the `SchoolScopedQuery` helper** before touching individual services. This reduces per-service implementation time and ensures consistency.
3. **Write the backward compatibility test suite first** (before any implementation). Run it, confirm it passes, then run it continuously as chain support is developed.
4. **Replace `get_school_for_tenant()`** as the very first code change, even before the migration. Replace it with a version that raises an explicit error for multi-school tenants. This creates a hard safety net.

### Blockers to Resolve

1. **Verify `users.email` uniqueness constraint** in actual database (model shows `unique=True` globally vs. memory suggests composite `(email, tenant_id)`). If it is globally unique, it must be changed before chain support.
2. **Decide: do academic_years and terms get school_id or not?** The architect design says yes, but some chains share academic calendars across schools. If shared, these tables do NOT get school_id, which simplifies the migration but complicates the filtering logic.
3. **Decide: what happens to existing data when a single-school tenant converts to a chain?** Is this even a supported flow? If yes, there is a second migration path (per-tenant, not global) that needs design.

### Technical Spikes (Investigate Before Committing)

1. **JWT size measurement** (0.5 days) -- Generate a JWT with maximum claims (chain_admin, all permissions, 50 school UUIDs) and measure the encoded size. If it exceeds 4KB, the design needs the all_schools fallback at a lower threshold.
2. **Composite index performance impact** (0.5 days) -- Add `(tenant_id, school_id)` indexes to 3 high-volume tables on a clone and benchmark common queries. If performance regresses, we need a different indexing strategy.
3. **Alembic migration timing** (0.5 days) -- Run the column-addition migration on a clone with realistic data volumes (50 tenants, 5000 students, 20000 attendance records) and measure lock duration. If it exceeds 5 minutes, we need an online migration strategy (e.g., `ADD COLUMN ... DEFAULT NULL` is instant in PG 11+, but FK creation takes a lock).

---

## Appendix A: Tables Requiring school_id Addition

Compiled from codebase review on 2026-02-16. Tables marked with * already have school_id.

### Tables WITH school_id (10 tables -- no migration needed)

| Table | Nullable | FK ondelete | Source File |
|-------|----------|-------------|-------------|
| `students`* | Yes | SET NULL | `/backend/app/models/student.py:108` |
| `staff`* | Yes | SET NULL | `/backend/app/models/staff.py:175` |
| `users`* | Yes | (none) | `/backend/app/models/user.py:93` |
| `classes`* | Yes | SET NULL | `/backend/app/models/academic/class_models.py:84` |
| `fee_types`* | No | CASCADE | `/backend/app/models/finance/fee_models.py:59` |
| `fee_structures`* | No | CASCADE | `/backend/app/models/finance/fee_models.py:102` |
| `invoices`* | No | CASCADE | `/backend/app/models/finance/invoice_models.py:104` |
| `payments`* | No | CASCADE | `/backend/app/models/finance/payment_models.py:81` |
| `scholarships`* | No | CASCADE | `/backend/app/models/finance/scholarship_models.py:103` |
| `credit_notes`* | No | CASCADE | `/backend/app/models/finance/credit_note_models.py:74` |

### Tables NEEDING school_id (32 tables -- migration required)

| Table | Recommended Nullable | Source File | Unique Constraints Affected |
|-------|---------------------|-------------|---------------------------|
| `academic_years` | Yes | `academic/year_models.py` | `uq_academic_year_name (tenant_id, name)` |
| `terms` | Yes | `academic/year_models.py` | `uq_term_name (tenant_id, academic_year_id, name)` |
| `class_sections` | Yes | `academic/class_models.py` | None visible |
| `class_subjects` | Yes | `academic/class_models.py` | Unique on (class_id, subject_id) likely |
| `subjects` | Yes | `academic/subject_models.py` | Unique on (tenant_id, code) likely |
| `grading_scales` | Yes | `academic/subject_models.py` | Unique on name likely |
| `grades` | Yes | `academic/subject_models.py` | None visible |
| `assessment_weights` | Yes | `academic/subject_models.py` | None visible |
| `academic_settings` | Yes | `academic/subject_models.py` | Likely singleton per tenant |
| `school_holidays` | Yes | `academic/timetable_models.py` | None visible |
| `school_periods` | Yes | `academic/timetable_models.py` | None visible |
| `class_timetables` | Yes | `academic/timetable_models.py` | None visible |
| `departments` | Yes | `staff.py` | None visible |
| `staff_class_assignments` | Yes | `staff.py` | None visible |
| `guardians` | Yes | `student.py` | `uq_guardians_email_tenant` |
| `student_guardians` | Yes | `student.py` | `uq_student_guardian_tenant` |
| `student_attendance` | Yes | `attendance.py` | `uq_student_attendance_date` |
| `staff_attendance` | Yes | `attendance.py` | `uq_staff_attendance_date` |
| `exams` | Yes | `exam.py` | `uq_exam_name_per_term` |
| `exam_subjects` | Yes | `exam.py` | `uq_exam_subject_class_section` |
| `exam_scores` | Yes | `exam.py` | `uq_exam_score_student` |
| `score_change_logs` | Yes | `exam.py` | None |
| `continuous_assessments` | Yes | `exam.py` | None visible |
| `term_reports` | Yes | `exam.py` | `uq_term_report_student` |
| `learning_areas` | Yes | `preschool.py` | None visible |
| `developmental_skills` | Yes | `preschool.py` | None visible |
| `preschool_rating_scales` | Yes | `preschool.py` | None visible |
| `preschool_ratings` | Yes | `preschool.py` | None visible |
| `student_skill_assessments` | Yes | `preschool.py` | None visible |
| `progress_observations` | Yes | `preschool.py` | None visible |
| `daily_activity_logs` | Yes | `preschool.py` | None visible |
| `preschool_reports` | Yes | `preschool.py` | None visible |
| `invoice_items` | Yes | `finance/invoice_models.py` | None visible |
| `invoice_scholarship_items` | Yes | `finance/invoice_models.py` | None visible |
| `fee_items` | Yes | `finance/fee_models.py` | None visible |
| `student_scholarships` | Yes | `finance/scholarship_models.py` | None visible |
| `scholarship_applications` | Yes | `finance/scholarship_models.py` | None visible |
| `finance_audit_log` | Yes | `finance/audit_models.py` | None (immutable log) |

**Note:** Some child tables (e.g., `invoice_items`, `fee_items`, `exam_scores`) inherit their school context from their parent record (invoice, fee_structure, exam_subject). Adding school_id to these is optional for denormalization/query convenience, but increases migration scope. The architect should decide which child tables truly need their own school_id vs. resolving it via JOIN to parent.

---

## Appendix B: Unique Constraints Requiring Modification

| Table | Current Constraint | New Constraint (with school_id) |
|-------|-------------------|-------------------------------|
| `academic_years` | `(tenant_id, name)` | `(tenant_id, COALESCE(school_id, '0...0'), name)` |
| `terms` | `(tenant_id, academic_year_id, name)` | `(tenant_id, COALESCE(school_id, '0...0'), academic_year_id, name)` |
| `exams` | `(tenant_id, academic_year_id, term_id, name)` | `(tenant_id, COALESCE(school_id, '0...0'), academic_year_id, term_id, name)` |
| `guardians` | `(email, tenant_id)` | Keep as-is (guardians may be shared across schools in a chain) |
| `student_guardians` | `(student_id, guardian_id, tenant_id)` | Keep as-is (student_id is already school-scoped) |
| `student_attendance` | `(tenant_id, student_id, date)` | Keep as-is (student_id is already school-scoped) |
| `staff_attendance` | `(tenant_id, staff_id, date)` | Keep as-is (staff_id is already school-scoped) |
| `exam_subjects` | `(tenant_id, exam_id, subject_id, class_id, COALESCE(section_id))` | Keep as-is (exam_id is school-scoped) |
| `exam_scores` | `(tenant_id, exam_subject_id, student_id)` | Keep as-is (exam_subject_id is school-scoped) |
| `term_reports` | `(tenant_id, term_id, student_id)` | Keep as-is (student_id is school-scoped) |

**Key insight:** Many child table constraints do NOT need modification because their parent FK (student_id, exam_id, etc.) is already school-scoped. Only top-level entity constraints (academic_years, terms, exams) need school_id added.

---

## Appendix C: Key File Locations

All paths are absolute from project root `/Users/harrymcninson/Documents/projects/sims-plus/`.

| Purpose | File Path |
|---------|-----------|
| Base models (TenantMixin, SoftDeleteMixin) | `/backend/app/models/base.py` |
| Tenant model (TenantType enum already exists) | `/backend/app/models/tenant.py` |
| User model (school_id, UserRole with chain_admin) | `/backend/app/models/user.py` |
| School model | `/backend/app/models/school.py` |
| Finance helper (get_school_for_tenant -- MUST FIX) | `/backend/app/api/v1/endpoints/finance/_helpers.py:28-40` |
| JWT creation (create_access_token) | `/backend/app/core/security.py:55-108` |
| Auth service (authenticate, refresh_tokens) | `/backend/app/services/auth.py` |
| Onboarding service (register_school) | `/backend/app/services/onboarding.py` |
| Tenant middleware (TenantContext) | `/backend/app/middleware/tenant.py` |
| API dependencies (get_db, get_validated_current_user) | `/backend/app/api/deps.py` |
| DB session (pool checkout listener) | `/backend/app/db/session.py` |
| Frontend API client (apiFetch) | `/frontend/lib/api.ts` |
| Frontend TenantProvider | `/frontend/components/providers/TenantProvider.tsx` |
| Frontend dashboard layout | `/frontend/app/(dashboard)/layout.tsx` |
| Alembic migrations directory | `/backend/alembic/versions/` (48 files) |

---

*End of Risk Analysis*
