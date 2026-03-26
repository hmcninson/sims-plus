# Risk Analysis: Tenant & School Setup Gap Closure

**Date:** 2026-03-21
**Analyst:** Risk Analyst Agent
**Spec Location:** `spec/tenant-school-setup/` (files 00-08)
**Status:** REVIEW ONLY -- no files modified

---

## Executive Summary

This plan addresses 7 identified gaps across 4 phases with an estimated 11-14 developer-days (spec estimate). The overall risk level is **Medium**, with the highest concentration of risk in Phase 1B (subscription enforcement + Paystack checkout). The plan is well-structured with clear dependencies, but contains several code-level issues that will cause bugs if not caught before implementation: a middleware ordering confusion that the spec itself catches but resolves ambiguously, a missing `timedelta` import in the subscription middleware, an SMS limit check referencing a model with the wrong class name, and a webhook handler that lacks proper transaction isolation. The per-student pricing model introduces non-trivial edge cases around 0-student tenants, mid-term student count changes, and downgrade scenarios that the spec does not address.

**Overall Risk Rating:** Medium (manageable with pre-implementation fixes)
**Recommendation:** Address the 6 "resolve before implementation" items, then proceed phase-by-phase.

---

## Component Complexity

| Component | Spec Est. | Revised Est. | Complexity | Notes |
|-----------|-----------|-------------|------------|-------|
| Phase 1A: Trial 90d + Middleware | 2-3d | 3-4d | 3 | Middleware needs tenant lookup expansion + Redis cache schema change |
| Phase 1B: Subscription Enforcement | 3-4d | 5-7d | 5 | Paystack integration, pricing calculation, webhook handler, feature gating across many routers |
| Phase 2A: GES Subject Templates | 2d | 2d | 2 | Straightforward data + endpoint, low risk |
| Phase 2B: Setup Wizard Improvements | 2d | 2-3d | 3 | State management between steps, setup-check criteria expansion |
| Phase 3A: School Category Fields | 1d | 1d | 1 | Simple nullable columns + enums |
| Phase 3B: Academic Year Archiving | 1-2d | 2-3d | 3 | Guard integration across 6+ services, exception handler registration |
| Phase 4: Date Overlap Validation | 0.5-1d | 1d | 2 | Clean overlap logic, but chain-tenant school_id scoping needs care |

**Total Estimated Effort:** 16-21 developer-days (spec says 11-14)
**Confidence Level:** Medium -- the spec underestimates Phase 1B significantly due to Paystack integration complexity and the number of services requiring limit check injection
**Recommended Buffer:** 25% -- primarily for webhook edge cases and feature gating integration testing

---

## Risk Register

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R1 | **Missing `timedelta` import in subscription middleware** -- Line 146 of the spec's `SubscriptionMiddleware` uses `timedelta` but the import block only imports `datetime` and `timezone` from `datetime`. Will crash at runtime on first trial-expired request. | Technical | High | High | Middleware crash on every request for expired trial tenants, blocking all API access | Add `from datetime import datetime, timedelta, timezone` at the top of `middleware/subscription.py`. This is a guaranteed bug. |
| R2 | **Tenant cache schema change breaks existing cached entries** -- The spec adds `status`, `trial_ends_at`, `subscription_end` to the tenant lookup dict, but existing Redis cache entries only contain `{id, subdomain, name, is_active}`. After deployment, cached entries from before the change will be missing these keys, causing `SubscriptionMiddleware` to read `None` for all subscription fields and incorrectly skip enforcement. | Technical | High | High | Silent bypass of subscription enforcement for all tenants with unexpired cache entries (up to 10 minutes TTL) | 1. Flush all tenant cache keys on deployment (`FLUSHDB` or iterate `tenant:subdomain:*`). 2. Add defensive `.get()` with sensible defaults in the middleware -- treat missing `status` as `None` and fall through to `call_next` (fail-open for cache miss, fail-closed for explicit expiry). 3. Better: version the cache schema (add a `cache_version` key; invalidate on mismatch). |
| R3 | **Webhook handler lacks transaction isolation** -- The subscription webhook endpoint at line 1129 uses `get_unscoped_db` and calls `service.handle_webhook()` which does `flush()`, then the endpoint itself does `db.commit()`. But between `flush()` and `commit()`, the endpoint also calls `invalidate_tenant_cache()`. If the cache invalidation succeeds but the `commit()` fails, the cache is invalidated (good) but the tenant is NOT upgraded (bad). On next request, the stale DB data is re-cached. More critically: if the server crashes between `flush()` and `commit()`, Paystack considers the payment successful (they got a 200), but the tenant is never upgraded. | Data Integrity | High | Medium | Paying customer stuck on trial/lower tier with no automatic recovery. Manual intervention required. | 1. Move `db.commit()` BEFORE `invalidate_tenant_cache()`. 2. Add an idempotent `verify_and_apply_payment(reference)` endpoint that re-checks Paystack transaction status via their Verify Transaction API and re-applies the upgrade. 3. Add a Celery periodic task that checks for "initiated but not confirmed" upgrades (store the Paystack reference in a `subscription_transactions` table). |
| R4 | **Per-student pricing with 0 students calculates incorrectly** -- `calculate_upgrade_cost()` uses `max(student_count, 1)` to enforce a minimum of 1 billable student. But a brand-new trial tenant doing immediate upgrade has 0 students. The spec charges them for 1 student (GHS 5-15). This is arguably correct as a minimum charge, but is undocumented and will confuse customers. More importantly: the cost shown at checkout is based on current student count, but students can be added AFTER checkout. A school could pay for 5 students (GHS 50/term Starter), then import 295 more, paying GHS 50 for 300 students worth of service. | Business Logic | High | High | Revenue leakage. Schools pay once based on a snapshot of student count, then add students freely until the next billing cycle. No reconciliation mechanism exists. | 1. Document the "pay for current count" model explicitly, with a plan for mid-term reconciliation (even if manual initially). 2. Consider a minimum student threshold per tier (e.g., Starter minimum 50 students = GHS 250/term). 3. For v1: accept this as a known limitation and add a TODO for usage-based billing reconciliation in Phase 2. 4. At minimum, store the `student_count` at time of payment in a `subscription_payments` audit table for future reconciliation. |
| R5 | **SMS limit check references `SmsLog` but actual model is `SMSLog`** -- Phase 1B Task 1 imports `from app.models.sms_log import SmsLog`, but the actual model file is `backend/app/models/sms.py` and the class is `SMSLog` (verified via grep). This will cause an ImportError at runtime. | Technical | High | High | SMS limit enforcement completely broken; either crashes (ImportError) or is never called | Fix import to `from app.models.sms import SMSLog` and use `SMSLog` throughout the SMS limit check method. |
| R6 | **Middleware ordering confusion in spec** -- The spec acknowledges the Starlette middleware ordering issue (last added = outermost = first executed) and provides TWO different orderings (lines 230-237 and 248-256). The second ordering is correct, but a developer reading the spec linearly may implement the first (incorrect) one. If SubscriptionMiddleware runs before TenantMiddleware, `request.state.tenant_id` will always be `None`, and the middleware will skip all subscription checks (fail-open). | Technical | Medium | Medium | All subscription enforcement silently bypassed | 1. Remove the first (incorrect) ordering from the spec entirely. 2. Add a startup assertion that verifies middleware order by checking that TenantMiddleware runs before SubscriptionMiddleware (e.g., a test that registers a school, expires its trial, and verifies 403 is returned). |
| R7 | **No downgrade flow specified** -- The spec covers upgrades (Trial->Starter->Professional->Enterprise) but says nothing about downgrades. What happens when a Professional tenant with 400 students downgrades to Starter (max 300)? What about a tenant with active boarding add-on who downgrades to Starter? | Business Logic | Medium | Medium | Customer service burden. Manual intervention needed for downgrades. Features may break mid-use if the tenant's plan is manually changed in DB. | 1. For v1: downgrades only via manual admin process (contact support). 2. Add a `can_downgrade_to(target_tier)` check that validates current usage against target tier limits before allowing a downgrade. 3. Document this explicitly as a v1 limitation. |
| R8 | **Grace period `days_left` can show 0 incorrectly** -- In the middleware, `days_left = (grace_end - now).days` uses integer division. If the grace period ends in 23 hours, `days_left` is 0, and the message says "You have 0 days of read-only access remaining." This is confusing (0 days but still accessible). | Technical | Low | High | Confusing UX -- user sees "0 days remaining" but can still access the system | Use `max(1, (grace_end - now).days)` when `grace_end > now`, or switch to hours for the final day: "less than 24 hours remaining." |
| R9 | **`tenant.max_students` set to `None` for Professional/Enterprise breaks existing code** -- The webhook handler sets `tenant.max_students = MAX_STUDENTS_BY_TIER.get(target_tier)` which is `None` for Professional/Enterprise. But `max_students` is defined as `Mapped[int]` with `default=100` in the tenant model (line 110-113). Setting it to `None` when the column is `Integer` may work (nullable), but any code doing arithmetic on `max_students` (e.g., `if current_count > tenant.max_students`) will crash with `TypeError: '>' not supported between instances of 'int' and 'NoneType'`. | Technical | Medium | Medium | Runtime crashes in any code path that compares against `max_students` without null-checking | 1. Use a sentinel value like `999999` for unlimited instead of `None`. 2. Or ensure ALL comparisons against `max_students` handle `None` (grep the codebase for `max_students` usage). The `check_student_limit()` method correctly handles `None`, but the `SubscriptionStatusResponse` returns it directly -- frontend must handle null. |
| R10 | **Subscription middleware adds latency to every request** -- The middleware reads `request.state.tenant_*` fields which are set by TenantMiddleware. This is zero-cost (in-memory dict lookup). However, the middleware runs on EVERY request including static asset paths that aren't in the exempt list. The exempt prefix check (`any(path.startswith(prefix) for ...)`) is O(n) for n=7 prefixes, which is negligible. **No actual performance concern here.** | Performance | Low | Low | Negligible -- sub-microsecond overhead | No action needed. The middleware design is efficient. |
| R11 | **Feature gating requires touching 10+ router files** -- Phase 1B Task 4 lists 9 routers that need `require_feature()` dependencies added. Each is a separate code change with its own test. If even one is missed, a feature remains ungated. | Quality | Medium | Medium | Ungated feature accessible on lower tiers, allowing free access to paid features | 1. Create a comprehensive test matrix: for each feature key, verify that a Starter-tier tenant gets 403 on the gated endpoint. 2. Add a `test_feature_gating_matrix.py` integration test. 3. Consider a reverse approach: instead of gating at the router level, add a global middleware that maps URL prefixes to features. This is more maintainable but less flexible. |
| R12 | **Trial Celery task has `asyncio.run()` antipattern** -- The spec's `check_trial_expirations` Celery task wraps the async implementation with `asyncio.run()`. This creates a new event loop per invocation. If Celery is configured with an async pool (e.g., gevent), this will raise `RuntimeError: This event loop is already running`. | Technical | Medium | Medium | Trial expiration warnings never sent if Celery uses async pool. Silent failure. | 1. Use `asgiref.sync.async_to_sync` instead of `asyncio.run()`. 2. Or configure Celery to use prefork pool (default) where `asyncio.run()` is safe. 3. Test the task locally before deploying. |
| R13 | **`_send_trial_warning` is a TODO stub** -- The spec leaves `_send_trial_warning()` as `pass` with a TODO comment. If implemented as-is, the trial warning system will silently succeed without actually sending any emails. | Technical | Low | High | No trial expiration warnings ever sent. Schools expire without notice. | Implement the function before deploying Phase 1A. It should query the tenant's admin user(s) and call the existing `email_service.send_email()`. |
| R14 | **Migration 1 uses `sa.inspect()` inside migration which may fail with async engine** -- The migration calls `sa.inspect(op.get_bind())` to check existing columns. This works with synchronous engines but may fail if Alembic is configured to use the async engine. | Technical | Low | Low | Migration fails on first run; easily caught in development | Verify Alembic migration runner uses synchronous engine (check `alembic/env.py`). If async, use raw SQL `SELECT column_name FROM information_schema.columns WHERE table_name = 'tenants'` instead. |
| R15 | **Migration 3 (enum ADD VALUE) cannot run inside a transaction** -- The spec correctly notes this but provides no concrete solution. Alembic by default runs migrations inside a transaction. `ALTER TYPE ... ADD VALUE` will fail with: `ERROR: ALTER TYPE ... ADD VALUE cannot be executed from a function or multi-command string`. | Technical | Medium | High | Migration 3 fails on every attempt, blocking Phase 3B deployment | Add `from alembic import context; context.get_context().autocommit_block()` or set `transaction_per_migration = False` in `env.py`. Alternatively, use the `op.execute()` with `execution_options={"autocommit": True}` or run outside Alembic's transaction wrapper. Test this migration specifically in a fresh DB before proceeding. |
| R16 | **Academic archiving guards miss several write paths** -- Phase 3B lists 8 services to guard, but misses: score_service.py (CA score entry), preschool_service.py (observations, assessments), timetable_service.py (period modifications), finance services (invoice generation for archived terms). Any of these can modify data within an archived academic year. | Quality | Medium | Medium | Data integrity: scores, assessments, or invoices created against archived years, breaking the read-only guarantee | Audit all services that accept a `term_id` or `academic_year_id` parameter and add the `assert_year_editable` or `assert_term_year_editable` guard. Create an integration test that attempts writes through every service against an archived year. |
| R17 | **Setup wizard `needsSetup` change triggers wizard for existing schools** -- Phase 2B changes the setup-check to also require `terms.length > 0 && subjects.length > 0`. Any existing school that registered before this change but hasn't created terms/subjects via the wizard will see the wizard pop up again on their next login. | Timeline | Medium | High | Every existing school gets the wizard overlay on login, causing confusion and support tickets | 1. The spec says "clean slate -- delete all" existing tenants. If this is truly enforced, this risk is zero. BUT: if any tenants survive (e.g., demo accounts, staging), they'll hit this. 2. Add a "dismiss wizard permanently" option that stores a flag (`setup_wizard_completed`) in school settings or local storage. |
| R18 | **Feature matrix contradicts CLAUDE.md pricing** -- CLAUDE.md says Professional costs $150/month (flat rate) and max_students is 1,000. The spec says Professional is GHS 10/student/term (per-student) with unlimited students. These are fundamentally different pricing models. CLAUDE.md also lists Trial as 14 days, Starter at $50/month. | Compliance | Medium | Low | Developer confusion if they reference CLAUDE.md for pricing logic instead of the spec. Could implement wrong pricing. | Update CLAUDE.md to reflect the new pricing model from `docs/SIMS_Plus_Subscription_Tiers.md`. The spec is authoritative -- CLAUDE.md is stale. |
| R19 | **Paystack webhook can be replayed** -- The webhook handler verifies the HMAC signature but does not check for replay attacks. The same webhook payload can be sent multiple times (Paystack retries on non-200). The handler is partially idempotent (setting the same tier twice is harmless), but `subscription_start` and `subscription_end` will be reset on each replay, potentially extending the subscription period. | Security | Medium | Medium | Subscription period extended via webhook replay. Minor revenue impact. | 1. Store Paystack `reference` in a `subscription_payments` table with a unique constraint. Check for duplicate reference before processing. 2. Use Paystack's Verify Transaction API as a secondary check: after receiving the webhook, call `GET /transaction/verify/{reference}` to confirm. |
| R20 | **No subscription_payments audit table** -- The spec stores no record of what was paid, when, for how many students, at what price. The only record is Paystack's side. If there's a dispute, there's no local evidence of what was charged. | Data Integrity | Medium | High | Cannot reconcile payments, audit billing, or prove what a customer paid for. No refund path. | Create a `subscription_payments` table with columns: `id`, `tenant_id`, `paystack_reference`, `amount_pesewas`, `tier`, `billing_period`, `student_count_at_time`, `addons`, `status` (pending/completed/failed), `metadata_json`, `created_at`. Populate on webhook receipt. |
| R21 | **`purchase_addon` endpoint has a logic flaw** -- It calls `service.initiate_upgrade()` with the current tier (not upgrading), which means the webhook handler will "upgrade" to the same tier, resetting `subscription_start` and `subscription_end`. For an add-on purchase, we only want to enable the add-on feature, not reset the subscription dates. | Business Logic | High | High | Every add-on purchase resets the subscription period. A school that paid for a year, then buys a boarding add-on in month 3, gets their year counter reset. | Differentiate between "upgrade" and "add-on purchase" in the webhook handler. Add a `type` field to metadata: `subscription_upgrade` vs `addon_purchase`. For addon purchases, only update `tenant.features` -- do NOT touch `subscription_tier`, `subscription_start`, or `subscription_end`. |
| R22 | **`SchoolContext` dependency used in subject template endpoint but may not exist for all tenants** -- The spec's subject template endpoint uses `Depends(get_school_context)` to get `school_id`. For single-school tenants this works, but the dependency's behavior for chain tenants needs verification -- does it require `X-Active-School` header? If so, the wizard (which runs during onboarding of a single school) may not send this header. | Technical | Low | Medium | Subject template initialization fails for certain tenant configurations during onboarding | Verify `get_school_context` behavior. If it requires a header for chain tenants, make `school_id` optional in the template service and derive it from the tenant's single school when `tenant_type == single_school`. |

---

## Multi-Tenancy Risk Assessment

**New tables requiring RLS policies:** None. This plan adds columns to existing tables (`tenants`, `schools`) and an enum value. No new tenant-scoped tables.

**Cross-tenant data access vectors:**
- The subscription webhook uses `get_unscoped_db` and manually looks up tenants by ID from Paystack metadata. This is correct because webhook calls are not tenant-scoped. However, if an attacker crafts a webhook payload with a different `tenant_id`, the HMAC signature check prevents this (they'd need the Paystack webhook secret).
- The `SubscriptionService` queries are scoped by `tenant_id` parameter. Since these are called from authenticated endpoints that extract `tenant_id` from the JWT, cross-tenant access is not possible.

**Cache/session tenant bleed risks:**
- R2 (above): The tenant cache schema change is the primary bleed risk. Old cache entries missing subscription fields could cause the middleware to make incorrect decisions.
- Feature flags stored in `tenant.features` JSONB are per-tenant. No cache-level bleed risk here because features are read fresh from DB in `check_feature_access()`.

**Background job tenant context:**
- The Celery task `check_trial_expirations` queries ALL tenants (no tenant scoping needed since it reads the `tenants` table which has no RLS). The `async_session_factory()` used is unscoped. This is correct.
- However, if `_send_trial_warning()` needs to query tenant-scoped data (e.g., finding admin users), it would need to set tenant context via `set_db_tenant_context()`. The stub implementation doesn't show this.

---

## Dependencies

### Internal Dependencies

| Component | Depends On | Status |
|-----------|------------|--------|
| Phase 1A: Subscription Middleware | TenantMiddleware request.state fields | Requires modification to TenantMiddleware (expand cached/queried fields) |
| Phase 1B: Limit Checks | Student, User, SMSLog models | Ready (models exist, but import path in spec is wrong for SMSLog) |
| Phase 1B: Feature Gating | All feature-specific routers | Ready (routers exist but each needs modification) |
| Phase 1B: Paystack Integration | Paystack webhook pattern from parent portal | Ready (pattern exists in `services/payment/online_payment.py`) |
| Phase 2A: Subject Templates | Subject model, SubjectCategory enum | Ready |
| Phase 2B: Setup Wizard | Phase 2A SubjectTemplateSelector component, createTerm action | Phase 2A must be complete; createTerm action needs verification |
| Phase 3B: Academic Archiving | AcademicYearStatus enum, all services that write to year-scoped data | Ready but guard coverage is incomplete (R16) |
| Phase 4: Date Overlap | Phase 3B archived status (for exclusion filter) | Phase 3B must be complete |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| Paystack API | Paystack | Medium | 0 days (already integrated) | API is well-documented. Existing integration in parent portal. Main risk: test mode API keys needed. |
| Paystack Webhook Secret | Paystack Dashboard | Low | Minutes | Must configure webhook URL for subscription callbacks in Paystack dashboard. |
| Redis | Infrastructure | Low | 0 days (already deployed) | Required for tenant cache, trial warning dedup. Graceful degradation exists. |
| Celery + Celery Beat | Infrastructure | Medium | 0-1 day | Required for trial expiration warnings. Celery exists but Beat scheduler may not be configured. Verify Celery Beat is running in production. |
| SMTP / Email Service | Infrastructure | Low | 0 days | Trial warning emails use existing email_service. |

---

## Recommended Approach

### Parallel Tracks

- **Track A (Backend):** Phase 1A (middleware + status endpoint) -> Phase 1B (subscription service + Paystack + feature gating)
- **Track B (Backend):** Phase 3A (school categories -- fully independent) + Phase 3B (academic archiving -- independent)
- **Track C (Frontend):** Phase 2A + 2B (GES templates + wizard -- depends on 2A backend being done)
- **Track D (Frontend):** Phase 1A frontend (trial banner) can start immediately; Phase 1B frontend (subscription settings page) after backend is done

### Sequential Dependencies

1. Phase 1A backend (middleware, cache expansion, status endpoint)
2. Phase 1B backend (subscription service, limit checks, Paystack, webhook)
3. Phase 1B frontend (subscription settings page, upgrade flow)
4. Phase 2A backend (subject templates endpoint)
5. Phase 2B frontend (wizard improvements, uses 2A endpoint)
6. Phase 3B backend (archiving)
7. Phase 4 backend (date overlap, uses 3B archived status)

---

## Critical Path

```
Phase 1A backend (3d) -> Phase 1B backend (5d) -> Phase 1B frontend (2d) = 10 days
```

The critical path is the subscription enforcement chain. Phases 2A/2B, 3A, 3B, and 4 can all run in parallel on a second developer track.

**Minimum Timeline:** 10 days (2 developers, critical path)
**Realistic Timeline:** 14 days (with buffer for webhook edge cases and integration testing)
**With single developer:** 18-21 days

---

## Business Logic Edge Cases Not Addressed

1. **Mid-term student count increase:** School pays for 50 students, imports 200 more. No reconciliation.
2. **Mid-term student count decrease:** School pays for 200 students, 150 withdraw. No refund mechanism.
3. **Upgrade mid-subscription:** School on Starter (paid for term) upgrades to Professional mid-term. Does the Starter payment get prorated as credit? The spec charges full Professional price with no proration.
4. **Term duration ambiguity:** Subscription is billed "per term" but `duration_days = 120` is hardcoded. Ghanaian terms vary (some are 13 weeks, some 10). This disconnect means the subscription could expire before or after the actual term ends.
5. **Annual billing student count:** If a school pays annually for 50 students, then grows to 200 by term 2, they've effectively paid for 50 students for 3 terms while using 200 by term 3. No true-up mechanism.
6. **Add-on duration:** Add-on purchases use the same `billing_period` but have no tracking of when they expire. If a school buys boarding for one term, `tenant.features.boarding = True` persists forever.
7. **School chain pricing:** The spec doesn't address how chain pricing works. Is it per-student across all schools? Per-school? The tiers doc mentions "School chain discounts available for 2+ schools (10%-25%)" but the code has no discount logic.

---

## Recommendations

### Resolve Before Implementation (Priority 1)

1. **Fix R1:** Add `timedelta` import to subscription middleware spec.
2. **Fix R5:** Correct `SmsLog` -> `SMSLog` import path and class name.
3. **Fix R6:** Remove the first (incorrect) middleware ordering from the spec. Keep only the corrected version.
4. **Fix R21:** Separate webhook handling for upgrades vs. addon purchases. Addon purchases must NOT reset subscription dates.
5. **Fix R15:** Add explicit autocommit handling for the enum migration.
6. **Fix R2:** Plan the cache flush on deployment, or add cache versioning.

### Address During Implementation (Priority 2)

7. **R3:** Add a `subscription_payments` table (R20) and use the Paystack reference as an idempotency key (R19).
8. **R13:** Implement `_send_trial_warning()` -- do not ship Phase 1A without it.
9. **R16:** Audit all services for missing academic year guards.
10. **R11:** Create a feature gating test matrix.

### Accept as v1 Limitations (Priority 3)

11. **R4:** Per-student pricing with no mid-term reconciliation. Document and plan for v2.
12. **R7:** No self-service downgrade. Manual process via support.
13. **R18:** Update CLAUDE.md to match new pricing model (cleanup, not blocking).

### Technical Spikes Needed

1. **Celery Beat verification:** Confirm Celery Beat is configured and running. If not, trial expiration warnings will never fire.
2. **Alembic async engine check:** Verify migration runner uses sync engine (for `sa.inspect()` usage in migration 1).
3. **Paystack test mode:** Ensure test API keys are configured in development/staging for the upgrade flow.

---

## Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| Celery Beat scheduler | Trial expiration warning cron | 0-1 day (if not already configured) | Negligible (runs on existing worker) |
| Paystack webhook URL config | Subscription payment callbacks | Minutes (dashboard config) | None |
| Redis cache flush on deploy | Clear stale tenant cache entries after middleware changes | Include in deployment script | None |

---

## Scope Creep Assessment

The plan is well-scoped with clear phase boundaries. However, Phase 1B is the largest single phase and contains both limit enforcement AND Paystack checkout AND feature gating AND a full frontend subscription settings page. This is 3-4 distinct features packaged as one phase.

**Recommendation:** Split Phase 1B into:
- **1B-1:** Subscription service + limit enforcement (backend only, 2d)
- **1B-2:** Feature gating on routers (backend, 1d)
- **1B-3:** Paystack checkout + webhook (backend, 2d)
- **1B-4:** Frontend subscription settings page (frontend, 2d)

This allows shipping limit enforcement independently of the payment flow, reducing blast radius if Paystack integration has issues.

**Items that could be deferred to a later sprint:**
- SMS limit enforcement (depends on SMSLog model naming fix and is less urgent than student/user limits)
- Storage limit enforcement (no storage tracking mechanism exists yet -- `storage_used_bytes` needs an implementation)
- Add-on purchase flow (Professional tier add-ons are a niche case for initial launch)
- School chain pricing discounts (no chain tenants expected at beta)

---

## Phase Ordering Risks

The spec's phase dependency diagram is correct. The key ordering constraints are:

1. Phase 1A MUST complete before Phase 1B (1B uses the subscription status endpoint and middleware from 1A)
2. Phase 2A MUST complete before Phase 2B (2B uses the SubjectTemplateSelector component from 2A)
3. Phase 3B MUST complete before Phase 4 (Phase 4's overlap check excludes archived years from 3B)
4. Phase 3A is fully independent and can be done at any time

A developer COULD start Phase 2B frontend before Phase 2A backend is done by mocking the API, but this introduces integration risk. Better to wait for 2A.

A developer CANNOT start Phase 1B before Phase 1A because:
- Phase 1B's subscription service uses the subscription status endpoint from Phase 1A
- Phase 1B's feature gating depends on the middleware from Phase 1A being in place
- The migration chain is sequential (0100 -> 0200 -> 0300)

---

## Revenue Risk Assessment

| Scenario | Risk | Impact | Likelihood |
|----------|------|--------|------------|
| Trial enforcement bypassed (R6 middleware ordering) | Schools use system indefinitely without paying | High | Medium (caught in spec but ambiguous) |
| Feature gating missed on a router (R11) | Paid feature available for free | Medium | Medium (10+ routers to modify) |
| Webhook payment not applied (R3) | Customer pays but doesn't get upgrade | High | Low-Medium |
| Per-student pricing gamed (R4) | Schools pay for fewer students than enrolled | Medium | High (no enforcement mechanism) |
| Add-on purchase resets subscription (R21) | Subscription period extended for free | Medium | High (guaranteed bug) |
| Downgrade without usage check (R7) | N/A for revenue (downgrades reduce revenue anyway) | Low | N/A |

**Net revenue risk:** The combination of R4 (per-student gaming), R21 (addon reset bug), and R6 (middleware bypass) represents the most significant revenue risk. R21 is a guaranteed bug that should be fixed before any code is written.
