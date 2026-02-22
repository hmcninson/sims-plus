# School Chain Support -- Design Document

**Author:** Harry McNinson (compiled from specialist analyses)
**Date:** 2026-02-16
**Version:** 1.0
**Status:** DRAFT -- For Review
**Sources:** Solution Architect Design, Tenancy Architect Analysis, Risk Analyst Report

---

## 1. Executive Summary

School Chain Support enables a single SIMS Plus tenant to manage multiple schools under one subdomain (e.g., a chain of 3 primary schools and 2 JHS campuses sharing one `presec.simsplus.io` tenant). The design preserves the existing RLS architecture at the `tenant_id` level and introduces school-level filtering as an application-layer concern, using a new `user_schools` junction table for authorization and an `X-Active-School` HTTP header for school switching. The estimated effort is 53-67 developer-days (7-9 weeks for a two-person team). The recommendation is to implement this in **Sprint 19-20 (Phase 3, Jul 2026)** after Beta Launch stabilizes, with preparatory work seeded into earlier sprints.

---

## 2. Architecture Diagram

### Current State: Single-School Tenant

```
  Browser                  Application                      Database
  ------                   -----------                      --------

  presec.simsplus.io       TenantMiddleware              PostgreSQL + RLS
       |                        |                             |
       |   GET /api/v1/...      |                             |
       |----------------------->|                             |
       |                        |  Extract subdomain          |
       |                        |  Lookup tenant              |
       |                        |  SET app.current_tenant_id  |
       |                        |---------------------------->|
       |                        |                             |
       |                        |  get_school_for_tenant()    |
       |                        |  SELECT * FROM schools      |
       |                        |  WHERE tenant_id = ?        |
       |                        |  LIMIT 1  <-- works because |
       |                        |              only 1 school  |
       |                        |---------------------------->|
       |                        |                             |
       |                        |  Service query (RLS active) |
       |                        |---------------------------->|
       |   <-- Response --------|                             |
```

### Proposed State: School-Chain Tenant

```
  Browser                  Application                      Database
  ------                   -----------                      --------

  presec.simsplus.io       TenantMiddleware              PostgreSQL + RLS
       |                        |                             |
       |   GET /api/v1/...      |                             |
       |   X-Active-School: uuid|                             |
       |----------------------->|                             |
       |                        |  Extract subdomain          |
       |                        |  Lookup tenant              |
       |                        |  SET app.current_tenant_id  |
       |                        |---------------------------->|
       |                        |                             |
       |                        |  SchoolContext dependency   |
       |                        |  1. Read X-Active-School    |
       |                        |  2. Validate against JWT    |
       |                        |     accessible_school_ids   |
       |                        |  3. Resolve school_id       |
       |                        |                             |
       |                        |  Service query (RLS active) |
       |                        |  + .where(school_id == ?)   |
       |                        |---------------------------->|
       |   <-- Response --------|                             |
```

### Key Principle: RLS vs. School Filtering

```
  +---------------------------------------------------------+
  |                    DATABASE LAYER                        |
  |                                                         |
  |   RLS Policy (enforced by PostgreSQL):                  |
  |   tenant_id = get_current_tenant_id()                   |
  |                                                         |
  |   - Cannot be bypassed by application code              |
  |   - Fails CLOSED (zero rows if no tenant set)           |
  |   - Unchanged by chain support                          |
  +---------------------------------------------------------+
                          |
  +---------------------------------------------------------+
  |                 APPLICATION LAYER                        |
  |                                                         |
  |   School Filter (enforced by service code):             |
  |   .where(Model.school_id == school_context.school_id)   |
  |                                                         |
  |   - Opt-in per service method                           |
  |   - Fails OPEN (shows all schools if filter missing)    |
  |   - NEW for chain support                               |
  |   - Within-tenant only (not a cross-tenant risk)        |
  +---------------------------------------------------------+
```

---

## 3. Database Schema Changes

### 3.1 New Tables

**`user_schools`** -- Junction table for multi-school user access.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK tenants.id, NOT NULL |
| `user_id` | UUID | FK users.id, NOT NULL |
| `school_id` | UUID | FK schools.id, NOT NULL |
| `role_at_school` | VARCHAR | Role enum |
| `is_primary` | BOOLEAN | Default false |

Unique constraint: `(tenant_id, user_id, school_id)`. RLS policy required: `tenant_id = get_current_tenant_id()`.

### 3.2 Tables Already Having school_id (10 tables -- no migration needed)

| Table | Nullable | FK ondelete | Source File |
|-------|----------|-------------|-------------|
| `students` | Yes | SET NULL | `models/student.py` |
| `staff` | Yes | SET NULL | `models/staff.py` |
| `users` | Yes | (none) | `models/user.py` |
| `classes` | Yes | SET NULL | `models/academic/class_models.py` |
| `fee_types` | No | CASCADE | `models/finance/fee_models.py` |
| `fee_structures` | No | CASCADE | `models/finance/fee_models.py` |
| `invoices` | No | CASCADE | `models/finance/invoice_models.py` |
| `payments` | No | CASCADE | `models/finance/payment_models.py` |
| `scholarships` | No | CASCADE | `models/finance/scholarship_models.py` |
| `credit_notes` | No | CASCADE | `models/finance/credit_note_models.py` |

### 3.3 Tables Needing school_id Added (32 tables -- migration required)

All columns added as **nullable UUID FK to schools.id**, backfilled from the tenant's single school for existing data.

| Category | Tables |
|----------|--------|
| **Academic** | `academic_years`, `terms`, `class_sections`, `class_subjects`, `subjects`, `grading_scales`, `grades`, `assessment_weights`, `academic_settings`, `school_holidays`, `school_periods`, `class_timetables` |
| **Staff** | `departments`, `staff_class_assignments` |
| **Students** | `guardians`, `student_guardians` |
| **Attendance** | `student_attendance`, `staff_attendance` |
| **Exams** | `exams`, `exam_subjects`, `exam_scores`, `score_change_logs`, `continuous_assessments`, `term_reports` |
| **Preschool** | `learning_areas`, `developmental_skills`, `preschool_rating_scales`, `preschool_ratings`, `student_skill_assessments`, `progress_observations`, `daily_activity_logs`, `preschool_reports` |
| **Finance** | `invoice_items`, `invoice_scholarship_items`, `fee_items`, `student_scholarships`, `scholarship_applications`, `finance_audit_log` |

### 3.4 Unique Constraint Modifications

Only top-level entity constraints need `school_id` added. Child table constraints are already school-scoped via their parent FK.

| Table | Current Constraint | New Constraint |
|-------|-------------------|----------------|
| `academic_years` | `(tenant_id, name)` | `(tenant_id, COALESCE(school_id, '0...0'), name)` |
| `terms` | `(tenant_id, academic_year_id, name)` | `(tenant_id, COALESCE(school_id, '0...0'), academic_year_id, name)` |
| `exams` | `(tenant_id, academic_year_id, term_id, name)` | `(tenant_id, COALESCE(school_id, '0...0'), academic_year_id, term_id, name)` |
| `guardians` | `(email, tenant_id)` | Keep as-is (shared across schools) |
| `student_attendance` | `(tenant_id, student_id, date)` | Keep as-is (student_id is school-scoped) |
| `staff_attendance` | `(tenant_id, staff_id, date)` | Keep as-is (staff_id is school-scoped) |
| `exam_subjects` | `(tenant_id, exam_id, subject_id, ...)` | Keep as-is (exam_id is school-scoped) |
| `exam_scores` | `(tenant_id, exam_subject_id, student_id)` | Keep as-is |
| `term_reports` | `(tenant_id, term_id, student_id)` | Keep as-is |

### 3.5 New Indexes

Composite index `(tenant_id, school_id)` on all 32 tables gaining `school_id`. Estimated storage increase: ~5-10% index overhead.

---

## 4. API Contract Changes

### 4.1 New Headers

| Header | Direction | Required | Description |
|--------|-----------|----------|-------------|
| `X-Active-School` | Request | No (single-school tenants omit) | UUID of the active school for chain tenants |

### 4.2 JWT Claim Additions

Two new claims added to the JWT payload (additive, no existing claims removed):

```json
{
  "tenant_type": "school_chain",
  "accessible_school_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

- `tenant_type`: `"single_school"` or `"school_chain"`
- `accessible_school_ids`: list of school UUIDs the user can access (chain tenants only)
- Capped at 50 UUIDs; chains with 50+ schools use `"all_schools": true` with server-side resolution via Redis cache
- Single-school tenants: these claims are omitted (backward compatible)

### 4.3 New Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/onboarding/register-chain` | Create a chain tenant + chain_admin (no school initially) |
| `POST` | `/api/v1/schools/chain/add` | Add a school to an existing chain tenant |

Existing `POST /api/v1/onboarding/register` remains unchanged (creates `SINGLE_SCHOOL` type).

### 4.4 SchoolContext Dependency

Replaces `get_school_for_tenant()` (located at `backend/app/api/v1/endpoints/finance/_helpers.py:28-40`), which uses `.limit(1)` and breaks for chains.

**Resolution logic:**
1. Read `X-Active-School` from request header
2. Validate against JWT `accessible_school_ids`
3. For single-school tenants without header: auto-resolve to the one school
4. For chain tenants without header: return 400 error
5. Also supports `SchoolContext.from_explicit(school_id)` for non-HTTP contexts (Celery tasks)

### 4.5 Changes to Existing Endpoints

All service methods gain an optional `school_id` parameter for filtering. For single-school tenants, SchoolContext resolves automatically and no client changes are needed. For chain tenants, `X-Active-School` header is required on all API calls.

---

## 5. Frontend Changes

### 5.1 New SchoolProvider Context

Wraps the dashboard layout. Provides `useSchool()` hook with:
- `activeSchoolId`: current school UUID
- `accessibleSchools`: list from JWT
- `switchSchool(id)`: updates cookie + invalidates all caches
- `isChain`: boolean

For single-school tenants, SchoolProvider is inert (no UI changes, no headers, no selector).

### 5.2 School Selector

Dropdown in `AppSidebar`, visible only for chain tenants. Shows school name and logo. Stored in cookie for persistence across page loads.

### 5.3 apiFetch Header

Modify `/frontend/lib/api.ts` to read the active-school cookie and include `X-Active-School` header on all API calls. This is a centralized, one-line change.

### 5.4 New Pages

| Page | Purpose |
|------|---------|
| `/chain/dashboard` | Multi-school overview: student/staff counts, financial summary per school |
| `/settings/chain/schools` | List schools, add school form, school details |

### 5.5 Server Actions

All 10+ action files (`students.action.ts`, `staff.action.ts`, etc.) need school context propagation through API calls.

### 5.6 School Switch UX

- Clear all client data caches on school switch
- Show loading overlay during transition
- Redirect to dashboard after switch
- Set `X-Active-School` cookie before any API call fires

### 5.7 Backward Compatibility

Single-school tenants experience **zero visual changes**: no school selector, no new headers, no SchoolProvider UI. The context auto-resolves silently.

---

## 6. Migration Strategy

### Phase 1: Model Changes + Column Additions (3 days)

Single Alembic migration:
1. Create `user_schools` table with RLS policy
2. Add nullable `school_id` column to all 32 tables
3. Add FK constraints to `schools.id`
4. Create `(tenant_id, school_id)` composite indexes on all 32 tables

### Phase 2: Data Backfill (3 days)

Second Alembic migration (idempotent):
1. For each tenant, find the single school: `SELECT id FROM schools WHERE tenant_id = ?`
2. UPDATE all rows in all 32 tables: `SET school_id = ? WHERE tenant_id = ? AND school_id IS NULL`
3. Pre-migration validation: count rows per table
4. Post-migration validation: verify zero NULL `school_id` rows (for tables where school_id should be populated)
5. Handle edge case: tenants with no school (error state -- log and skip)

### Phase 3: Unique Constraint Updates (2 days)

Third Alembic migration:
1. Drop old unique constraints on `academic_years`, `terms`, `exams`
2. Create new constraints with COALESCE pattern: `(tenant_id, COALESCE(school_id, '0...0'), name)`
3. Constraints on child tables (attendance, exam_scores, etc.) remain unchanged

### Rollback Plan

- Each migration phase has a reverse migration that drops added columns/constraints
- Phase 2 (backfill) rollback: set `school_id = NULL` on all backfilled rows
- Phase 3 rollback: restore original unique constraints
- All migrations wrapped in transactions (Alembic default)

### Testing on Production Clone (Required)

A production DB clone (RDS snapshot) must be used for migration testing before any production run. This validates:
- Migration runs cleanly against real data volumes
- Backfill handles all existing tenant configurations
- Lock duration is acceptable (target: under 5 minutes)
- No data quality issues (orphaned FKs, missing tenants)

Estimated cost: ~$50 for a temporary RDS instance.

---

## 7. Risk Register Summary

Top 10 risks from the Risk Analyst report, ordered by severity:

| ID | Risk | Severity | Probability | Mitigation |
|----|------|----------|-------------|------------|
| R01 | Migration backfill corrupts existing data | CRITICAL | Medium | Single transaction, production clone test, pre/post validation queries, maintenance window with DB snapshot |
| R02 | `get_school_for_tenant()` returns wrong school for chains | CRITICAL | High | Replace with SchoolContext before any chain tenant is created; hard safety net |
| R03 | Service layer school filtering is opt-in, not enforced | CRITICAL | High | SchoolScopedQuery helper, integration tests for every service method, code review checklist |
| R04 | JWT token size exceeds limits with 50 school UUIDs | HIGH | Medium | Lower `all_schools` fallback threshold to 20; Redis cache for resolution; size assertion in tests |
| R05 | X-Active-School header lost in Celery background jobs | HIGH | Medium | SchoolContext.from_explicit(school_id); pass school_id as Celery task argument |
| R06 | Unique constraint conflicts for same-named entities across schools | HIGH | High | Audit all constraints; add school_id to constraint tuples with COALESCE for NULLs |
| R07 | Redis cache keys not school-scoped cause stale data | HIGH | Medium | Convention: `{tenant_id}:{school_id}:{feature}:{key}`; add CacheKeys.school_scoped() helper |
| R08 | Parent Portal coupling with chain support | HIGH | High | Ship Parent Portal first (Sprint 15-16); budget 5-8 days rework later |
| R09 | users.email uniqueness constraint incompatible with chains | HIGH | Medium | Verify DB state; change to composite `UNIQUE(email, tenant_id)` if needed |
| R10 | School switching shows stale frontend data | MEDIUM | High | Invalidate all caches on switch; loading overlay; redirect to dashboard |

---

## 8. Effort Estimate

| Category | Low Estimate | High Estimate |
|----------|-------------|---------------|
| Backend: DB and Models | 16 days | 20 days |
| Backend: Auth and JWT | 5 days | 7 days |
| Backend: Services | 10 days | 12 days |
| Frontend | 10 days | 13 days |
| Testing | 12 days | 15 days |
| **Subtotal** | **53 days** | **67 days** |
| Buffer (25%) | 13 days | 17 days |
| **Realistic Total** | **66 days** | **84 days** |

**Timeline:** 13-17 weeks for 1 developer, 7-9 weeks for 2 developers.

**Complexity Score:** 8/10 -- Touches 30+ tables, 10+ services, 10+ frontend action files, JWT, middleware, and migrations. The largest single feature in the project's history.

---

## 9. Sprint Recommendation

### Why NOT Sprint 15-16 (Parent Portal)

- Delays Parent Portal by 7-9 weeks
- No chain customers exist yet -- zero revenue impact from earlier chain support
- 100% of current users are single-school tenants; risk to all of them for 0% chain benefit
- Sprint scope would balloon uncontrollably

### Why NOT Sprint 17-18 (Beta Launch)

- Adding a 30+ table migration just before beta launch is reckless
- Beta launch should prove single-school stability, not introduce new architecture
- No "soak time" for the migration to settle before real users arrive
- Triple-scope sprint (performance optimization + beta launch + chain support)

### Why Sprint 19-20 (Phase 3, Jul 2026) Is Recommended

- Beta launch has validated the single-school platform with real users
- Real feedback informs chain requirements (the design may change based on what we learn)
- Migration can be tested against production data patterns accumulated during beta
- Phase 3 is explicitly labeled "Enhancement" in the roadmap
- Boarding and Transport (also Phase 3) benefit from chain support existing first
- 2 full sprints of buffer between beta and chain support

### Preparatory Work in Earlier Sprints

| Sprint | Work | Cost | Purpose |
|--------|------|------|---------|
| 15-16 (Parent Portal) | Implement SchoolContext stub (always returns single school) | 1 day | Establishes API pattern and header convention early |
| 17 (Beta prep) | Run unique constraint audit; document all 12+ constraints | 2 days | Zero-risk investigative work; saves critical path time |
| 18 (Post-Beta) | Test migration on production DB clone | 1 day | Identifies data quality issues before Sprint 19 |

---

## 10. Go/No-Go Decision

### GO -- With Conditions

The design is architecturally sound. The three core decisions are correct:

1. **RLS stays at tenant_id** -- Avoids rewriting 48+ RLS policies. Application-layer school filtering within a trusted tenant boundary is appropriate.
2. **X-Active-School header instead of new JWT** -- Avoids token refresh on every school switch. Validated server-side against JWT claims.
3. **user_schools junction table** -- Avoids user duplication. Supports multi-school staff naturally.

### Conditions for Proceeding

1. **Migration must be tested on a production clone** -- not staging, an actual clone of production data
2. **Unique constraint audit must be complete** before migration development begins
3. **Service layer school isolation tests must achieve 100% coverage** of school-scoped service methods
4. **Backward compatibility regression suite must pass** with zero failures (full existing test suite against chain-enabled codebase with single-school tenant)
5. **`get_school_for_tenant()` must be replaced** before any chain tenant can be created in any environment
6. **Feature flag recommended** -- `chain_support_enabled` in tenant features JSONB to gate chain creation until manual verification

### Red Flags That Would Change to NO-GO

- Tables discovered that are shared across tenants (no `tenant_id`) and also need `school_id` -- would require RLS changes
- JWT size exceeds 4KB with existing claims (before adding school UUIDs)
- Production clone migration reveals data inconsistencies (rows with no tenant, invalid FKs)

### Blockers to Resolve Before Implementation

1. Verify `users.email` uniqueness constraint in the actual database (model shows global `unique=True`)
2. Decide whether `academic_years` and `terms` get `school_id` (some chains share academic calendars)
3. Decide whether single-school-to-chain conversion is a supported flow

---

## 11. Appendix: Key File Locations

All paths relative to `/Users/harrymcninson/Documents/projects/sims-plus/`.

| Purpose | File Path |
|---------|-----------|
| Base models (TenantMixin, SoftDeleteMixin) | `backend/app/models/base.py` |
| Tenant model (TenantType enum) | `backend/app/models/tenant.py` |
| User model (school_id, UserRole) | `backend/app/models/user.py` |
| School model | `backend/app/models/school.py` |
| Finance helper (**MUST FIX** -- `get_school_for_tenant`) | `backend/app/api/v1/endpoints/finance/_helpers.py:28-40` |
| JWT creation (`create_access_token`) | `backend/app/core/security.py:55-108` |
| Auth service (authenticate, refresh_tokens) | `backend/app/services/auth.py` |
| Onboarding service (register_school) | `backend/app/services/onboarding.py` |
| Tenant middleware (TenantContext) | `backend/app/middleware/tenant.py` |
| API dependencies (get_db, get_validated_current_user) | `backend/app/api/deps.py` |
| DB session (pool checkout listener) | `backend/app/db/session.py` |
| Cache keys utility | `backend/app/utils/cache_keys.py` |
| RLS migration | `backend/alembic/versions/20260215_0100_hardened_rls_policies.py` |
| Alembic migrations directory | `backend/alembic/versions/` |
| Frontend API client (apiFetch) | `frontend/lib/api.ts` |
| Frontend TenantProvider | `frontend/components/providers/TenantProvider.tsx` |
| Frontend dashboard layout | `frontend/app/(dashboard)/layout.tsx` |

---

*End of Design Document*
