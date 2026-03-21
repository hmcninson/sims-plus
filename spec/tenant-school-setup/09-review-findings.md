# Implementation Plan Review Findings

**Date:** 2026-03-21
**Reviewed by:** 5 specialized agents (Code Review, Security, Tenancy, Risk, Architecture)
**Status:** Changes required before implementation

---

## Consolidated Critical Findings

These MUST be fixed in the spec before any developer starts coding.

### C1. Replace SubscriptionMiddleware with a FastAPI Dependency
**Raised by:** Solution Architect, Code Reviewer
**Severity:** Critical (architectural)

The `SubscriptionMiddleware` using `BaseHTTPMiddleware` is wrong for this use case:
- Adds overhead to every request including fully paid tenants
- Requires a fragile exempt-path list that rots over time
- The spec itself showed confusion about Starlette's reversed middleware ordering (two conflicting orderings provided)
- `BaseHTTPMiddleware` creates separate task contexts — anti-pattern for anything needing DB

**Resolution:** Keep the TenantMiddleware enrichment (adding `tenant_status`, `trial_ends_at`, `subscription_end` to `request.state`). Replace the enforcement layer with a FastAPI dependency:
```python
# In api/deps.py
async def enforce_subscription(request: Request, current_user: dict = Depends(get_validated_current_user)):
    # Same enforcement logic, raises HTTPException instead of returning JSONResponse
    # Add to api_router as a global dependency
```
Unauthenticated routes are implicitly exempt since the dependency requires `get_validated_current_user`. No exempt-path list needed.

---

### C2. Trial `PLAN_FEATURES` is All-False (Contradicts Business Requirement)
**Raised by:** Code Reviewer, Solution Architect, Risk Analyst
**Severity:** Critical (business logic)

The `PLAN_FEATURES[TRIAL]` dict has every feature set to `False`, but `docs/SIMS_Plus_Subscription_Tiers.md` says "90-day access to all Starter features." Trial users would be locked out of everything during their trial, defeating the purpose.

**Resolution:** Trial dict must mirror the Starter dict exactly. Add a comment: `# Trial mirrors Starter features for 90 days`.

---

### C3. Missing `timedelta` Import in Middleware/Dependency
**Raised by:** Code Reviewer, Security Auditor, Tenancy Architect, Risk Analyst
**Severity:** Critical (guaranteed crash)

The subscription enforcement code uses `timedelta(days=settings.TRIAL_GRACE_PERIOD_DAYS)` but only imports `datetime, timezone` from `datetime`.

**Resolution:** Add `timedelta` to the import.

---

### C4. `max_students = None` Will Crash on NOT NULL Column
**Raised by:** Code Reviewer, Tenancy Architect, Risk Analyst
**Severity:** Critical (guaranteed crash)

`Tenant.max_students` is `Mapped[int]` (NOT NULL, default=50). The webhook sets it to `None` for Professional/Enterprise (unlimited tiers). This will throw `IntegrityError` on flush.

**Resolution:** Use a large sentinel value (e.g., `999999`) for "unlimited", OR change the model to `Mapped[int | None]` with a migration. The sentinel approach avoids a migration.

---

### C5. Redis Cache Serialization Unspecified
**Raised by:** Tenancy Architect, Solution Architect
**Severity:** Critical (silent enforcement bypass)

The spec adds `trial_ends_at` (datetime) and `subscription_end` (date) to the cached tenant dict but provides no serialization/deserialization code. Without explicit ISO string conversion, the middleware/dependency will get `None` for all subscription fields and **skip all enforcement silently**.

**Resolution:** Provide explicit code for:
- Writing: `"trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None`
- Reading: `datetime.fromisoformat(cached["trial_ends_at"]) if cached.get("trial_ends_at") else None`
- Also flush Redis cache on deployment (old entries lack these fields).

---

### C6. Add-On Purchase Resets Subscription Dates
**Raised by:** Code Reviewer, Solution Architect, Risk Analyst
**Severity:** Critical (guaranteed revenue bug)

The `purchase_addon` endpoint reuses `initiate_upgrade()` with the current tier. The webhook handler then resets `subscription_start` and `subscription_end`. A school on a yearly Professional plan that buys a boarding add-on in month 3 gets their subscription timer reset to a new term/year period — losing months of paid subscription.

**Resolution:** Use a separate `type: "addon_purchase"` in Paystack metadata. Add a separate code path in the webhook handler that only enables add-on features without touching subscription dates.

---

## High Severity Findings

### H1. Webhook Metadata Trust (No Server-Side Validation)
**Raised by:** Security Auditor
**Severity:** High (security)

The subscription webhook trusts `tenant_id` and `target_tier` from Paystack metadata without server-side validation. An attacker who can trigger a webhook could upgrade a different tenant or to a higher tier.

**Resolution:** Store a `subscription_intents` record at initiation time (reference, tenant_id, target_tier, amount, status). In the webhook, validate the metadata against the stored intent. This matches the existing admissions portal pattern.

---

### H2. TOCTOU Race Condition in Limit Checks
**Raised by:** Security Auditor
**Severity:** High (security)

`check_student_limit()` does count-then-check non-atomically. Two concurrent student creation requests can both pass the limit check before either commits.

**Resolution:** Use `pg_advisory_xact_lock` keyed on `(tenant_id, 'student_limit')` before counting. This is already an established pattern in the codebase.

---

### H3. ExpiredGate Blocks Access to Upgrade Page
**Raised by:** Solution Architect
**Severity:** High (UX)

The expired gate is a full-screen overlay inside the dashboard layout, blocking ALL navigation including `/settings/subscription`. Users cannot reach the upgrade page to fix the problem.

**Resolution:** Either: (a) exempt `/settings/subscription` from the gate overlay, (b) embed the upgrade flow directly in the ExpiredGate component, or (c) render the gate outside the dashboard layout so it doesn't block settings navigation.

---

### H4. Add-On Feature Flags Never Expire
**Raised by:** Solution Architect, Risk Analyst
**Severity:** High (revenue leakage)

`tenant.features["boarding"] = True` is set permanently. There is no mechanism to expire add-ons at end of term.

**Resolution:** Store expiry dates in the features JSONB:
```json
{"boarding": {"enabled": true, "expires_at": "2026-07-31"}}
```
Or create a `tenant_addons` table with `addon_name`, `starts_at`, `expires_at`, `payment_reference`. The `check_feature_access` method then checks the expiry date.

---

### H5. Webhook Idempotency Missing
**Raised by:** Solution Architect, Risk Analyst
**Severity:** High (data integrity)

No check for duplicate webhook delivery. Paystack retries webhooks. Could upgrade a tenant multiple times or reset dates.

**Resolution:** Track processed payment references (either a `subscription_payments` table or a Redis set). Check before processing. Existing parent portal payment webhook already does this.

---

### H6. Double Commit in Webhook Endpoint
**Raised by:** Code Reviewer, Tenancy Architect
**Severity:** High (data integrity)

The webhook endpoint calls `db.commit()` explicitly, but `get_unscoped_db` auto-commits via the yield pattern. Cache invalidation happens between the two commits, creating fragile ordering.

**Resolution:** Remove the explicit `await db.commit()`. Let `get_unscoped_db` handle the commit after yield.

---

### H7. Wrong SMS Model Import
**Raised by:** Code Reviewer, Risk Analyst
**Severity:** High (guaranteed crash)

`from app.models.sms_log import SmsLog` — actual model is `SMSLog` in `app.models.sms`.

**Resolution:** Fix import to `from app.models.sms import SMSLog`.

---

### H8. Enum Migration Needs Autocommit
**Raised by:** Risk Analyst
**Severity:** High (migration failure)

`ALTER TYPE ... ADD VALUE` cannot run inside a transaction. Alembic runs migrations transactionally by default. Migration 3 will fail.

**Resolution:** Use `op.execute()` with explicit `COMMIT`/`BEGIN` wrapping or `execution_options={"isolation_level": "AUTOCOMMIT"}`. Follow the existing pattern from `20260303_0200_applicant_accounts.py`.

---

## Medium Severity Findings

| # | Finding | Raised By | Resolution |
|---|---------|-----------|------------|
| M1 | `GET /subscription/status` missing `require_permissions` | Code Review | Add `subscription.read` permission or document exemption |
| M2 | Inline role checks in upgrade endpoints instead of `require_permissions` | Architecture | Use `require_permissions("subscription.manage")` |
| M3 | No rate limiting on `/subscription/upgrade` and `/calculate-cost` | Security, Architecture | Add 5/hour rate limit |
| M4 | No audit logging for subscription changes | Security | Log upgrades/add-ons to finance audit log |
| M5 | `callback_url` only validates `https://` prefix | Security, Code Review | Add domain allowlist (`*.simsplus.io` + `localhost` in dev) |
| M6 | Pricing constants duplicated across 3 files | Architecture, Code Review | Extract to `app/constants/subscription.py` |
| M7 | TrialBanner does client-side fetch | Architecture | Pass `initialStatus` from server-component layout |
| M8 | Warning state tracked in `tenant.features` JSONB (mixing concerns) | Architecture | Use `_internal.` key prefix or separate table |
| M9 | Celery task `_send_trial_warning` is a TODO (pass) | Risk | Spec must outline email template and admin user lookup |
| M10 | `_validate_no_date_overlap` uses `scalar_one_or_none()` — crashes on multiple overlaps | Code Review | Use `scalars().first()` instead |
| M11 | `assert_term_year_editable` variable named `term` but holds UUID | Code Review | Rename to `academic_year_id` |
| M12 | Celery task needs try/except with rollback | Code Review | Add error handling around transaction |
| M13 | Chain tenant billing scope unclear | Tenancy | Explicitly state subscription is tenant-level, not per-school |
| M14 | `SubjectTemplateService(None)` for a method that doesn't use DB | Code Review | Use `@staticmethod` |
| M15 | `SubjectTemplateInitResponse.subjects` typed as `list[dict]` | Code Review | Define a typed Pydantic schema |

---

## Revised Effort Estimate

**Original estimate:** 11-14 developer-days
**Revised estimate:** 16-21 developer-days

| Phase | Original | Revised | Reason |
|-------|----------|---------|--------|
| 1A | 2-3 days | 3-4 days | Cache serialization, dependency (not middleware) |
| 1B | 3-4 days | 5-7 days | Paystack integration complexity, 10+ router modifications, webhook edge cases, subscription_intents table |
| 2A | 2 days | 2 days | Clean, no changes |
| 2B | 2 days | 2 days | Clean, no changes |
| 3A | 1 day | 1 day | Clean, no changes |
| 3B | 1-2 days | 2-3 days | Guard integration across 6+ services (exam, attendance, preschool, timetable, finance) |
| 4 | 0.5-1 day | 1 day | Clean, minor fix |

---

## Business Logic Gaps (Accepted v1 Limitations)

These are documented as known limitations for v1, not blockers:

1. **No reconciliation:** Schools pay based on student count at payment time, then add students freely
2. **No downgrade flow:** What happens to 400 students when downgrading from Professional (unlimited) to Starter (300 limit)?
3. **Term duration hardcoded:** 120 days per "term" regardless of actual term length
4. **No subscription payment audit table:** No local record of charges (only Paystack records)
5. **Student count race at payment time:** Count can change between price display and webhook

---

## Action Items Before Implementation

### Must Do (blocks development)
- [ ] Rewrite Phase 1A: Replace middleware with dependency pattern
- [ ] Fix Trial PLAN_FEATURES to mirror Starter
- [ ] Fix `timedelta` import
- [ ] Fix `max_students` NULL handling (sentinel or model change)
- [ ] Add Redis serialization/deserialization code for datetime fields
- [ ] Separate addon_purchase from subscription_upgrade in webhook
- [ ] Add subscription_intents table for webhook validation
- [ ] Fix SMS model import
- [ ] Fix enum migration autocommit handling

### Should Do (before merge)
- [ ] Add `pg_advisory_xact_lock` for limit checks
- [ ] Fix ExpiredGate to not block subscription page
- [ ] Add add-on expiry tracking
- [ ] Add webhook idempotency check
- [ ] Remove explicit `db.commit()` from webhook endpoint
- [ ] Add rate limiting on payment endpoints
- [ ] Add audit logging for subscription changes

### Nice to Have (can be follow-up)
- [ ] Extract pricing constants to shared module
- [ ] Pass TrialBanner initialStatus from server component
- [ ] Add typed schema for SubjectTemplateInitResponse
- [ ] Add domain allowlist for callback_url
