# Risk Analysis: Platform Admin Login Implementation

**Date:** 2026-03-22
**Analyst:** Risk Analyst Agent
**Spec Version:** 00-overview through 04-phase-4-testing
**Overall Risk Level:** HIGH -- first cross-tenant write path using superuser credentials

---

## Executive Summary

The Platform Admin Login spec introduces the single most security-sensitive feature in SIMS Plus: a superuser database connection that bypasses all Row-Level Security. The architecture is sound in principle -- using `sims_admin` role rather than modifying RLS policies is the correct approach. However, the implementation has several concrete bugs, a SQL injection vulnerability, and underestimates the effort by approximately 40-50%. The 12-day estimate should be 17-20 days for 1-2 developers.

The three highest-priority risks are: (1) SQL injection in `_get_tenant_counts` via string interpolation of UUIDs, (2) the `authenticate()` method can never issue full tokens because `mfa_enabled=False` falls through to the setup-required branch before reaching `_issue_tokens()`, and (3) removal of "admin" from `RESERVED_SUBDOMAINS` requires a corresponding database migration to remove it from the `reserved_subdomains` table, which the spec omits entirely.

---

## 1. Blast Radius Assessment

### Worst Case: Superuser Engine Leak

If the `sims_admin` connection pool is accidentally exposed to normal request handlers (e.g., registered as a FastAPI dependency, imported by a non-platform service), **every tenant's data becomes readable and writable without RLS filtering**. This is a full-platform data breach affecting all schools simultaneously.

**Blast radius:** ALL tenants, ALL data (students, staff, grades, financial records).

**Probability:** LOW with the current design (module-level variable, lazy init, not a dependency). But one careless import in a future sprint could expose it.

**Mitigation (already in spec):** Engine is module-scoped in `session.py`, never registered as a dependency. Pool is small (5 max connections).

**Additional mitigation needed:**
1. Add a CI check (grep) that verifies `get_platform_admin_session_maker` is only imported in `services/platform.py` and `tests/`.
2. Add a startup assertion that verifies the admin engine's pool size is <= 5.
3. Consider moving the admin engine to `services/platform.py` itself rather than `session.py` -- reduces import surface.

### Worst Case: Impersonation Token Abuse

A compromised or forged impersonation token grants `["*"]` permissions scoped to a single tenant for 30 minutes. The impersonation token uses the same JWT signing key as all other tokens.

**Blast radius:** Single tenant's full data (not platform-wide).

**Mitigation (already in spec):** 30-min non-refreshable expiry, audit logging, `is_impersonation=True` claim.

**Additional concern:** The spec does not prevent a platform admin from impersonating the `_platform` tenant itself. While `get_tenant()` excludes `_platform`, a direct impersonation call with the platform tenant UUID would fail at the tenant lookup. This is correct behavior but should have an explicit test.

### Worst Case: Platform Admin Account Compromise

A compromised platform admin account can: suspend/activate any tenant, read all tenant metadata, impersonate any tenant with full read-write access. Combined with impersonation, this is equivalent to compromising every school simultaneously.

**Blast radius:** ALL tenants (via sequential impersonation).

**Mitigation (already in spec):** MFA mandatory, CLI-only creation, separate cookies, audit logging.

**Additional mitigation needed:** Rate limit impersonation harder (5/min is too high -- an attacker could impersonate 150 tenants in 30 minutes). Recommend 2/min or 10/hour.

---

## 2. Operational Risks

### R-OP1: Platform Tenant Seed Row Deletion

If the `_platform` tenant row is deleted (accidentally or via a rogue migration), all platform admin users become invisible to RLS (their `tenant_id` FK points to a deleted row). Platform admin login fails silently -- the user query returns zero rows.

**Severity:** HIGH | **Probability:** LOW

**Current mitigation:** `ON CONFLICT (subdomain) DO NOTHING` in migration makes seeding idempotent.

**Missing mitigation:** No runtime check that the platform tenant exists. The login endpoint will just return "Invalid email or password" with no clue that the underlying tenant is missing. Add a startup health check that verifies `SELECT 1 FROM tenants WHERE id = PLATFORM_TENANT_ID`.

### R-OP2: ALEMBIC_DATABASE_URL Misconfiguration

The spec reuses `ALEMBIC_DATABASE_URL` for the superuser engine. This env var is documented as optional (`str | None = None` in config.py) and is currently only used by `alembic/env.py`. The spec changes it from "needed only for migrations" to "needed at runtime for platform admin features."

**Severity:** MEDIUM | **Probability:** MEDIUM

**Concrete issues:**
1. `ALEMBIC_DATABASE_URL` uses sync driver (`postgresql://`) in `.env.example` but the async engine requires `postgresql+asyncpg://`. The spec's `create_async_engine(str(admin_url))` will fail if the URL has the sync driver prefix.
2. In `docker-compose.yml` (line 96), `ALEMBIC_DATABASE_URL` uses the sync prefix. The platform admin engine will crash at runtime.
3. If `ALEMBIC_DATABASE_URL` is not set, `get_platform_admin_session_maker()` raises `RuntimeError`. This only happens on the first platform admin API call -- not at startup. A startup check would catch this earlier.

**Mitigation:** Add a `PLATFORM_ADMIN_DATABASE_URL` setting separate from `ALEMBIC_DATABASE_URL`. Auto-derive from `ALEMBIC_DATABASE_URL` by replacing the driver prefix. Validate at startup, not lazily.

### R-OP3: Superuser Connection Pool Exhaustion

With `pool_size=2, max_overflow=3`, the admin engine supports 5 concurrent connections. If analytics queries or tenant list queries are slow (see Scale Risks below), requests will queue. The `list_tenants` endpoint creates a new admin session per call, and each request holds the connection for the duration of 3 COUNT queries.

**Severity:** MEDIUM | **Probability:** LOW (few platform admins)

**Mitigation:** The pool size is intentionally small. At most 2-3 platform admins would use this concurrently. If the pool does exhaust, only platform admin features degrade -- school operations are unaffected.

### R-OP4: Platform Admin Account Compromise

**Severity:** CRITICAL | **Probability:** LOW

**Missing from spec:**
1. No IP allowlisting for platform admin endpoints.
2. No alert/notification when a platform admin logs in from a new IP.
3. No session revocation mechanism beyond token blacklisting (which requires knowing the JTI).
4. The CLI creates platform admin users with `status=ACTIVE` and `email_verified=True` -- no email verification step. If the wrong email is used, the actual email holder could potentially trigger a password reset.

**Mitigation:** Add IP allowlisting as a configuration option. Log all login attempts to an external alerting system (not just the audit log). Document that password reset for platform admins should be CLI-only, not self-service.

---

## 3. Complexity Risks

### R-CX1: Is the Superuser Engine Over-Engineered?

**Short answer: No.** Given the hardened RLS with `FORCE ROW LEVEL SECURITY`, `sims_app_user` genuinely cannot read cross-tenant data even without setting tenant context (returns zero rows). The superuser engine is the minimum viable solution.

**Simpler alternatives considered:**
1. **Add RLS bypass for platform_admin role** -- This would weaken RLS for all tables globally. Rejected correctly.
2. **Query the tenants table only (no cross-tenant counts)** -- This would work for basic tenant management but not for analytics or impersonation validation. The spec needs cross-tenant reads.
3. **Use `sims_app_user` and loop through tenants setting context each time** -- This would work functionally but requires N database round-trips (one per tenant) for analytics. Impractical at scale.

The superuser engine is the right approach. The complexity is inherent, not over-engineered.

### R-CX2: Impersonation Flow Maintainability

The impersonation flow is actually elegant and simple: create a JWT with `tenant_id=target`, pass it to the school subdomain, and all existing endpoints work unchanged because `ValidatedTokenTenant` validates `token.tenant_id == request.tenant_id`. No special cases needed in any existing endpoint.

**Risk:** Future developers might not understand why `is_impersonation` is in the JWT. They might try to add special-case handling for impersonation in individual endpoints. This should be documented.

### R-CX3: Platform Tenant Concept

The `_platform` tenant is a pragmatic solution to SQLAlchemy's `TenantMixin` NOT NULL constraint. It is invisible to normal flows because:
1. `_platform` fails `SUBDOMAIN_PATTERN` validation (starts with underscore)
2. The middleware would reject it even if accessed directly
3. Platform admin endpoints filter `WHERE subdomain != '_platform'`

**Risk:** The `_platform` tenant shows up in `SELECT * FROM tenants` queries. Any code that iterates all tenants (reports, billing, data exports) will include it unless explicitly filtered.

**Mitigation:** Add a check to common tenant iteration patterns. The `list_tenants` endpoint already excludes it. Add a comment on the Tenant model itself warning about the platform tenant.

---

## 4. Backward Compatibility Risks

### R-BC1: Removing "admin" from RESERVED_SUBDOMAINS

**Three places where "admin" is reserved:**
1. `backend/app/middleware/tenant.py:94` -- the in-memory set
2. `frontend/proxy.ts:17` -- the frontend set
3. **`reserved_subdomains` database table** -- seeded via migration `20260215_0200`

The spec addresses #1 and #2 but **completely misses #3**. The onboarding service checks the `reserved_subdomains` table when registering new schools:

```python
# backend/app/services/onboarding.py:20
from app.models.reserved_subdomain import ReservedSubdomain
```

If "admin" is removed from the in-memory sets but remains in the database table, onboarding will still reject "admin" as a subdomain -- which is actually correct behavior (we want to prevent schools from registering "admin"). But there is a more subtle issue:

**Could any existing school have "admin" as their subdomain?** No. The 4-character minimum length check passes ("admin" = 5 chars), but the `reserved_subdomains` table has had "admin" since the first migration. No school could have registered it. Confirmed safe.

**Recommendation:** Do NOT remove "admin" from the `reserved_subdomains` DB table. It should remain reserved to prevent future schools from registering it. Only remove from the in-memory sets in middleware and proxy.ts so the admin domain is not rejected at the routing level. The spec's approach of removing from the in-memory set is correct; the DB table is a separate concern (registration validation, not request routing).

### R-BC2: Adding Platform Paths to PUBLIC_PATH_PREFIXES

The spec adds `/api/v1/platform/login` and `/api/v1/platform/refresh` to `_PUBLIC_PATH_PREFIXES` in `deps.py`, and `/api/v1/platform/` to `PUBLIC_PATH_PREFIXES` in `tenant.py`.

**Risk:** The prefix `/api/v1/platform/` is broad. Any future endpoint added under `/api/v1/platform/` will automatically skip tenant resolution. This is correct for platform admin endpoints, but if someone accidentally creates a school-facing endpoint under this prefix, it would bypass tenant checks.

**Mitigation:** This is acceptable because the entire `/platform/` router uses `PlatformAdmin` dependency. Non-platform-admin tokens are rejected regardless. Add a comment in the router file: "ALL endpoints in this router require PlatformAdmin -- do not add school-facing endpoints here."

### R-BC3: Modifying proxy.ts

The spec adds admin domain detection BEFORE subdomain extraction. This is the correct ordering -- it means admin.simsplus.io is handled as a special case and never reaches the subdomain extraction logic.

**Risk:** The spec shows the admin detection code but says "rest of existing middleware unchanged." However, the current proxy.ts exports a `default function proxy()` (line 141), while the spec shows a `middleware()` function. This mismatch needs resolution -- the spec must use `export default function proxy()` to match the actual file.

**Additional risk:** In development mode, `?subdomain=admin` currently returns null (rejected by RESERVED_SUBDOMAINS). After removing "admin" from the reserved set, `?subdomain=admin` would resolve as a valid school subdomain and try to look up tenant "admin" in the database. The spec handles this by detecting `?subdomain=admin` in the admin domain check, but only for `localhost` -- not for cookie-based subdomain persistence. If a developer visits `?subdomain=admin`, the `x-subdomain` cookie gets set to "admin", and subsequent requests (without the query param) would try to route to tenant "admin".

**Mitigation:** Keep "admin" in the `RESERVED_SUBDOMAINS` set in proxy.ts. Instead, add the admin domain detection BEFORE the reserved subdomain check. This way, `admin.simsplus.io` hits the special case, but `?subdomain=admin` on localhost is still rejected by the reserved check. The spec should NOT remove "admin" from the frontend reserved set.

### R-BC4: Existing Tests That Assert "admin" is Reserved

The test file `backend/tests/test_tenant_middleware.py:40` asserts:
```python
assert extract_subdomain_from_host("admin.simsplus.io") is None
```

And `backend/tests/test_onboarding.py:115` tests that "admin" is rejected as a reserved subdomain.

Removing "admin" from the backend `RESERVED_SUBDOMAINS` set will break `test_tenant_middleware.py:40`. The onboarding test should continue to pass if "admin" remains in the DB table.

**Mitigation:** Update `test_tenant_middleware.py` to reflect the new behavior. Add a new test that verifies "admin" subdomain is handled as the platform portal, not as a school.

---

## 5. Dependency Risks

### R-DEP1: ALEMBIC_DATABASE_URL Runtime Availability

**Is it documented?** Partially. `.env.example` has it, but `config.py` marks it as `str | None = None` (optional). The spec elevates it from optional migration tool to required runtime dependency.

**Is it set in all environments?**
- `docker-compose.yml`: Yes (line 96), but uses sync driver prefix
- `.env.example`: Yes, but uses sync driver prefix
- Staging/Production: Unknown -- typically only set where Alembic runs, which may be a separate CI job, not the application server

**Risk:** The application server in production may not have `ALEMBIC_DATABASE_URL` set because migrations run in a separate CI pipeline. This would cause `RuntimeError` on the first platform admin API call.

**Mitigation:** Add `PLATFORM_ADMIN_DATABASE_URL` as a separate setting with clear documentation that it must be set on application servers, not just migration runners. Add a startup validation in the app lifespan that warns if this is not set.

### R-DEP2: Well-Known UUID Hardcoded in Multiple Places

The UUID `00000000-0000-0000-0000-000000000001` appears in:
1. Migration `20260326_0100` (seed)
2. `config.py` (PLATFORM_TENANT_ID setting)
3. CLI command (references settings)
4. `PlatformAdminUser` dependency (references settings)
5. PlatformService (references settings)
6. Tests (will reference settings or hardcode)

**Risk:** If this UUID needs to change (e.g., conflict with a test fixture, collision with a restored backup), every reference must be updated. The migration seed is immutable (already run), so the UUID is effectively permanent.

**Mitigation:** This is acceptable. The UUID is deliberately well-known (similar to the null UUID `00000000-...0000` pattern). All code references `settings.PLATFORM_TENANT_ID`, which centralizes the value. The migration hardcodes it, but that is by design. The only risk is if someone creates a test that uses this same UUID for a test tenant -- add a note in the test infrastructure.

---

## 6. Timeline Risks

### Is the 12-Day Estimate Realistic?

**No.** Based on the spec's own task breakdown and historical estimation patterns for this codebase:

| Phase | Spec Estimate | Revised Estimate | Gap Reason |
|-------|---------------|------------------|------------|
| Phase 1: Infrastructure | 2 days | 2 days | Accurate -- straightforward migration + CLI |
| Phase 2: Backend | 3-4 days | 5-7 days | Superuser engine testing alone is 1-2 days; MFA integration has unknowns |
| Phase 3: Frontend | 3-4 days | 4-5 days | Platform portal is 6+ pages; proxy.ts changes need careful testing |
| Phase 4: Testing | 2 days | 4-5 days | 6 test files * 6-12 tests each; security review is not a quick checklist |
| **Total** | **~12 days** | **17-20 days** | **~50% underestimate** |

**Critical path:** Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 (strictly sequential, no parallelization).

**Biggest unknowns:**
1. MFA setup enforcement on first login -- the existing MFA infrastructure needs verification. Does the MFA setup endpoint exist? Is it tenant-scoped?
2. Superuser engine testing -- the two-engine test pattern needs a third engine (or the admin engine reused for tests).
3. proxy.ts changes -- Next.js 16 proxy behavior with multiple subdomain patterns needs integration testing.

### What Could Block Progress?

1. **MFA infrastructure gaps:** If the existing MFA setup/verify endpoints are tenant-scoped (require subdomain), platform admin MFA will not work without modifications.
2. **ALEMBIC_DATABASE_URL driver mismatch:** The sync/async driver prefix issue will block Phase 2 until resolved.
3. **Test infrastructure:** The `conftest.py` creates test tenants with specific UUIDs. The platform tenant seed may conflict if tests run before the migration or if the migration has already run in the test database.

---

## 7. Testing Risks

### R-TEST1: Cross-Tenant Queries in CI

**Problem:** CI may have only one test tenant. The `_get_tenant_counts` method needs to query across multiple tenants to be meaningful.

**Mitigation:** Tests should create 2-3 test tenants with students/staff, then verify that analytics returns correct aggregated counts. The existing two-engine test pattern (admin + app_user) provides the admin engine needed for cross-tenant setup.

### R-TEST2: Superuser Engine Testing Without Exposing Credentials

**Problem:** The superuser engine uses `ALEMBIC_DATABASE_URL`. In tests, `conftest.py` already has an admin engine (line ~30-40) that connects as postgres superuser for DDL operations. The platform admin tests need to verify that the `get_platform_admin_session_maker()` function works, which requires `ALEMBIC_DATABASE_URL` to be set in the test environment.

**Mitigation:** This is already handled -- `ALEMBIC_DATABASE_URL` is set in the test environment (Docker Compose provides it). The test admin engine and the platform admin engine will use the same credentials. No credential exposure beyond what already exists.

### R-TEST3: proxy.ts Admin Subdomain Testing

**Problem:** proxy.ts runs in the Next.js runtime. Testing it requires either unit tests (mocking NextRequest/NextResponse) or integration tests (running the dev server).

**Mitigation:** The spec does not include frontend tests for proxy.ts. This is a gap. Add at minimum:
1. Manual testing checklist for admin.localhost:3000
2. Unit test that verifies `extractSubdomain` returns null for "admin" subdomain
3. Integration test that verifies the platform login page loads on admin subdomain

---

## 8. Scale Risks

### R-SCALE1: _get_tenant_counts Performance

**Problem:** The method runs 3 separate `COUNT(*) ... GROUP BY tenant_id` queries on `students`, `staff`, and `schools` tables. Each query scans all non-deleted rows in the table.

At 1000 tenants with average 200 students each:
- `students` table: 200,000 rows scanned per query
- `staff` table: ~20,000 rows scanned
- `schools` table: ~1,500 rows scanned

With the current B-tree index on `tenant_id`, these are index-only scans (`GROUP BY tenant_id` with `COUNT(*)` and `WHERE deleted_at IS NULL`). Performance should be acceptable up to ~500K students.

**But:** The method is called for every page of the tenant list. With 100 tenants per page, it creates an `IN` clause with 100 UUIDs. This is fine.

**Real concern:** At 10,000+ tenants with 2M+ students, these COUNT queries will take 1-5 seconds. The platform admin dashboard will feel slow.

**Mitigation:** Add a materialized view or periodic background job that pre-computes tenant counts. This is not needed for MVP but should be planned for Phase 4.

### R-SCALE2: Analytics Full Table Scans

**Problem:** `get_analytics()` runs `SELECT COUNT(*) FROM students WHERE deleted_at IS NULL` (no tenant filter). This is a full sequential scan on the students table.

At 1M students, this takes 2-10 seconds depending on I/O.

**Mitigation:** Same as R-SCALE1 -- materialized view for MVP+. For the MVP with <10 schools, this is not an issue.

### R-SCALE3: SQL Injection in _get_tenant_counts

**CRITICAL BUG:** The `_get_tenant_counts` method builds the `IN` clause via string interpolation:

```python
ids_str = ",".join(f"'{str(tid)}'" for tid in tenant_ids)
# ...
result = await admin_session.execute(text(f"""
    SELECT tenant_id::TEXT, COUNT(*)
    FROM {table_name}
    WHERE tenant_id IN ({ids_str})
    AND deleted_at IS NULL
    GROUP BY tenant_id
"""))
```

While `tenant_ids` come from `Tenant.id` (database UUIDs, not user input), this pattern is categorically unsafe:
1. The `table_name` variable comes from a hardcoded list, so that is safe.
2. The `ids_str` interpolates UUIDs that were read from the database, so SQL injection from external input is not directly possible.
3. **However**, this pattern violates defense-in-depth. If a future developer passes user-supplied IDs to this method, it becomes exploitable.

**Mitigation:** Use parameterized queries with `ANY(:ids)` and cast to UUID array:
```python
result = await admin_session.execute(
    text(f"""
        SELECT tenant_id::TEXT, COUNT(*)
        FROM {table_name}
        WHERE tenant_id = ANY(CAST(:ids AS uuid[]))
        AND deleted_at IS NULL
        GROUP BY tenant_id
    """),
    {"ids": [str(tid) for tid in tenant_ids]},
)
```

---

## 9. Concrete Bugs in the Spec

### BUG-1: authenticate() Never Issues Full Tokens

In `PlatformService.authenticate()`, the logic is:

```python
if user.mfa_enabled:
    return {"mfa_required": True, ...}

if not user.mfa_enabled:
    return {"mfa_setup_required": True, ...}

# Full login (only reached after MFA verify or if MFA exempt)
return await self._issue_tokens(user)
```

The `if user.mfa_enabled` and `if not user.mfa_enabled` branches cover all cases -- the code after them is unreachable. `_issue_tokens()` is never called from `authenticate()`.

**Fix:** The full token issuance should happen after MFA verification, not in `authenticate()`. The spec needs a separate `verify_mfa()` method that calls `_issue_tokens()`. Or, add a `skip_mfa_check` parameter (but this is less secure).

The intended flow should be:
1. `authenticate()` always returns `mfa_required` or `mfa_setup_required`
2. After MFA verification, a separate endpoint calls `_issue_tokens()`
3. A `/platform/mfa/verify` endpoint is needed (not in the spec)

### BUG-2: Missing `settings` Import in platform.py Endpoint

The `platform_login` endpoint references `settings.ACCESS_TOKEN_EXPIRE_MINUTES` (line 1129) but `settings` is not imported in the endpoint file. The imports show `from app.api.deps import PlatformAdmin, UnscopedDatabaseSession` but no `from app.config import settings`.

### BUG-3: MFA Pending Token Audit Log References Missing user_id

In the endpoint `platform_login`, the MFA pending branch tries to log an audit entry:

```python
await service.log_action(
    actor_user_id=UUID(result.get("user_id", "00000000-...")),
    ...
)
```

But the `authenticate()` method returns `{"mfa_required": True, "mfa_pending_token": ...}` -- there is no `user_id` key. The fallback UUID is misleading (it collides with `PLATFORM_TENANT_ID`).

### BUG-4: ALEMBIC_DATABASE_URL Driver Prefix Mismatch

`ALEMBIC_DATABASE_URL` in `.env.example` and `docker-compose.yml` uses `postgresql://` (sync driver). `create_async_engine()` requires `postgresql+asyncpg://`. The spec does not perform the driver conversion that `alembic/env.py` does.

### BUG-5: Missing /platform/mfa/* Endpoints

The spec enforces MFA on first login but provides no endpoints for:
- `POST /platform/mfa/setup` -- Generate TOTP secret and QR code
- `POST /platform/mfa/verify` -- Verify TOTP code and issue full tokens
- `POST /platform/mfa/verify-login` -- Verify TOTP during login (when MFA already enabled)

Without these, platform admins cannot complete login.

### BUG-6: Missing reserved_subdomains DB Table Update

The spec removes "admin" from the in-memory `RESERVED_SUBDOMAINS` set but does not mention removing it from the `reserved_subdomains` database table. The onboarding service checks both. However, as noted in R-BC1, "admin" should remain in the DB table to prevent schools from registering it. But the spec should explicitly state this decision.

---

## Risk Register

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R1 | SQL injection pattern in `_get_tenant_counts` (string-interpolated UUIDs) | Technical/Security | HIGH | LOW | Cross-tenant data exposure via superuser engine | Replace with parameterized `ANY(CAST(:ids AS uuid[]))` query |
| R2 | `authenticate()` unreachable `_issue_tokens()` -- platform admins can never fully log in | Technical | CRITICAL | CERTAIN | Feature completely non-functional | Add `/platform/mfa/verify` and `/platform/mfa/setup` endpoints; restructure auth flow |
| R3 | `ALEMBIC_DATABASE_URL` sync driver prefix crashes `create_async_engine` | Technical | HIGH | HIGH | Platform admin features completely non-functional | Add driver prefix conversion or separate `PLATFORM_ADMIN_DATABASE_URL` with asyncpg prefix |
| R4 | Missing MFA endpoints (`/platform/mfa/setup`, `/platform/mfa/verify`) | Technical | CRITICAL | CERTAIN | Platform admin login flow incomplete | Add Phase 2.5 for MFA endpoints (1-2 days additional effort) |
| R5 | Superuser engine pool leak to non-platform code paths | Multi-Tenancy | CRITICAL | LOW | Full data breach for all tenants | CI grep check; startup assertion on pool size; consider moving engine to `services/platform.py` |
| R6 | Platform tenant seed row deletion breaks all platform admin auth | Operational | HIGH | LOW | Platform admin login fails silently | Startup health check; add `ON DELETE RESTRICT` or protect via trigger |
| R7 | `ALEMBIC_DATABASE_URL` not set on production app servers (only in CI/migration runner) | Infrastructure | HIGH | MEDIUM | Platform admin RuntimeError on first use | Separate `PLATFORM_ADMIN_DATABASE_URL` config; startup validation |
| R8 | Removing "admin" from proxy.ts RESERVED_SUBDOMAINS allows `?subdomain=admin` cookie persistence | Backward Compatibility | MEDIUM | MEDIUM | Dev mode routing confusion; potential cookie-based tenant resolution to nonexistent "admin" tenant | Keep "admin" in proxy.ts reserved set; detect admin domain before reserved check |
| R9 | `test_tenant_middleware.py:40` and `test_onboarding.py:115` will break | Quality | MEDIUM | CERTAIN | Test suite regressions | Update tests as part of Phase 4 |
| R10 | Missing `settings` import in `platform.py` endpoint file | Technical | LOW | CERTAIN | NameError at runtime | Add `from app.config import settings` to imports |
| R11 | MFA pending audit log uses nonexistent `result["user_id"]` key | Technical | LOW | CERTAIN | Falls back to misleading UUID that collides with PLATFORM_TENANT_ID | Extract user_id from JWT payload in the mfa_pending_token, or return user_id from authenticate() |
| R12 | Impersonation rate limit too permissive (5/min = 150 tenants in 30 min) | Security | MEDIUM | LOW | Compromised account can sequentially access many tenants | Reduce to 2/min or 10/hour |
| R13 | 12-day estimate is ~50% under actual effort | Timeline | MEDIUM | HIGH | Sprint overrun, scope cuts | Budget 17-20 days; identify Phase 2.5 for MFA as mandatory addition |
| R14 | proxy.ts spec uses `middleware()` function name but actual file exports `proxy()` | Technical | LOW | CERTAIN | Copy-paste from spec produces broken code | Spec should use `export default function proxy()` |
| R15 | Analytics `COUNT(*)` full table scans at scale | Infrastructure | LOW | LOW (pre-MVP) | Slow dashboard (2-10s) at 1M+ students | Accept for MVP; plan materialized views for Phase 4 |
| R16 | `_platform` tenant appears in unfiltered tenant queries (billing, reports, exports) | Multi-Tenancy | MEDIUM | MEDIUM | Platform tenant counted in billing reports, included in data exports | Add `WHERE subdomain != '_platform'` to common tenant iteration patterns; add model-level warning comment |
| R17 | Platform admin password reset via self-service email flow | Security | MEDIUM | LOW | Attacker with email access can reset platform admin password without MFA | Disable self-service password reset for platform admins; CLI-only password changes |
| R18 | No `/platform/refresh` endpoint implementation in spec | Technical | MEDIUM | CERTAIN | Platform admin tokens expire after 15 min with no way to refresh | Add refresh endpoint to Phase 2 |

---

## Recommended Priority Order

### P0 -- Must Fix Before Implementation

1. **R2/R4:** Fix the authenticate() flow and add MFA endpoints. Without this, the feature literally does not work.
2. **R3:** Fix the async driver prefix conversion for ALEMBIC_DATABASE_URL.
3. **R1:** Replace SQL string interpolation with parameterized queries.
4. **R10/R11:** Fix the import and audit log bugs.
5. **R14:** Correct the proxy.ts function name in the spec.

### P1 -- Should Fix During Implementation

6. **R5:** Add CI grep check for superuser engine imports.
7. **R7:** Add separate PLATFORM_ADMIN_DATABASE_URL or auto-derive with driver conversion.
8. **R8:** Keep "admin" in proxy.ts RESERVED_SUBDOMAINS; detect admin domain before reserved check.
9. **R9:** Update breaking tests.
10. **R18:** Add refresh endpoint.
11. **R12:** Tighten impersonation rate limit.

### P2 -- Should Fix Before Production

12. **R6:** Startup health check for platform tenant existence.
13. **R16:** Audit common tenant queries for platform tenant filtering.
14. **R17:** Disable self-service password reset for platform admins.

### P3 -- Plan for Future

15. **R15:** Materialized views for tenant counts at scale.

---

## Revised Timeline Estimate

| Phase | Effort | Notes |
|-------|--------|-------|
| Phase 1: Infrastructure | 2 days | Migration + CLI + model. No changes. |
| Phase 2: Backend Core | 4-5 days | Auth + endpoints + deps + middleware |
| Phase 2.5: MFA Flow | 2 days | MFA setup, verify, verify-login endpoints for platform admin |
| Phase 3: Frontend | 4-5 days | Portal pages + proxy.ts + impersonation banner |
| Phase 4: Testing | 3-4 days | 6 test files + security review + regression fixes |
| **Total** | **17-20 days** | 1-2 developers |

**Confidence Level:** Medium -- the architecture is well-understood from the prior analysis, but the MFA integration adds uncertainty.

**Recommended Buffer:** 25% -- bringing the realistic total to 21-25 days.

---

## Changes to Implementation Plan

The following changes should be made to the spec files:

### 01-phase-1-infrastructure.md
- Add startup health check task for platform tenant existence
- Add note about NOT removing "admin" from reserved_subdomains DB table

### 02-phase-2-backend.md
- Fix `_get_tenant_counts` SQL injection (parameterized queries)
- Fix `authenticate()` unreachable code (always returns MFA response)
- Add driver prefix conversion for ALEMBIC_DATABASE_URL
- Add MFA endpoints (setup, verify, verify-login)
- Add `settings` import to platform.py endpoint file
- Fix MFA pending audit log user_id extraction
- Add `/platform/refresh` endpoint
- Add rate limit note for impersonation (reduce to 2/min)
- Add note about keeping `reserved_subdomains` DB row for "admin"

### 03-phase-3-frontend.md
- Fix proxy.ts function name (proxy, not middleware)
- Keep "admin" in proxy.ts RESERVED_SUBDOMAINS set
- Add admin domain detection before reserved check, not after removal

### 04-phase-4-testing.md
- Add test for platform tenant existence on startup
- Add test for driver prefix conversion
- Add test for `?subdomain=admin` not routing to school
- Update test_tenant_middleware.py expectations
- Add proxy.ts testing notes
