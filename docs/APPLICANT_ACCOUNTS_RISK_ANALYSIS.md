# Risk Analysis: Applicant Accounts Implementation

**Analyst:** Risk Analyst Agent
**Date:** 2026-03-02
**Spec Version:** 1.0 (spec/applicant-accounts/)
**Prerequisite Feature:** Admissions Portal (spec/admissions-portal/)

---

## Executive Summary

The Applicant Accounts feature is a **medium-complexity extension** to the existing Admissions Portal, with a well-structured spec that leverages existing auth infrastructure rather than building from scratch. The estimated 11-15 dev-days is **plausible but tight** -- a realistic range is **14-20 dev-days** when accounting for three specific risks the spec underestimates: (1) the spec references AuthService methods that do not exist in the codebase, requiring either new methods or integration with the separate `EmailVerificationService`; (2) the shared cookie namespace between applicant and staff logins creates a session conflict that is acknowledged but not fully mitigated; and (3) the claim flow's email-matching logic has edge cases around email normalization and the absence of guardian emails on anonymous applications.

**Overall Risk Level: MEDIUM.** No showstoppers, but several issues need resolution before implementation begins.

---

## 1. Implementation Complexity & Effort Assessment

### Component Complexity

| Component | Spec Est. | Revised Est. | Complexity | Notes |
|-----------|-----------|--------------|------------|-------|
| A1-A3: Model changes (enum + 2 columns) | 0.6d | 0.5d | 1 | Straightforward; spec is accurate |
| A4: Alembic migration | 0.5d | 0.75d | 3 | `ALTER TYPE ADD VALUE` transactional behavior needs testing; fallback to AUTOCOMMIT may be needed |
| A5: ApplicantAccountService | 1d | 2d | 5 | **Spec references `AuthService.send_verification_email()` and `verify_email_token()` which do not exist.** Must integrate with `EmailVerificationService` instead. Registration, login, claim, verify, forgot/reset = 8 methods |
| A6: ApplicationService modifications | 0.5d | 0.75d | 3 | `list_my_applications`, `create_draft`, `update_draft`, `submit_draft`, `get_printable` -- all need IDOR-safe `applicant_user_id` filtering + eager loading |
| A7: EnrollmentService role promotion | 0.25d | 0.5d | 3 | Must be added between step 9 (notification) and step 10 (parent accounts). Interaction with existing `ParentOnboardingService.create_parent_for_student()` is unclear -- if guardian email matches applicant email, two paths both try to create/modify the User |
| A8: ROLE_PERMISSIONS update | 0.1d | 0.1d | 1 | Simple dict addition |
| B1: Pydantic schemas | 0.5d | 0.5d | 2 | 18 schemas, mostly standard. Password validator duplication is fine |
| B2: Public endpoints (6) | 1d | 1.25d | 3 | Register, login, verify, resend, forgot, reset. Rate limiting config needed per-endpoint |
| B3: Authenticated endpoints (12) | 1d | 1.5d | 5 | Profile (3) + Applications (7) + Claim (1) + Print (1). Draft guardian upsert logic is the complex part |
| B4: `get_applicant_user()` dependency | 0.25d | 0.25d | 2 | Follows existing `get_validated_current_user()` pattern |
| B5: Middleware updates | 0.25d | 0.5d | 3 | Must update BOTH `middleware/tenant.py` AND `api/deps.py` public path lists. Must add 6 rate limit rules to `RateLimitMiddleware.ENDPOINT_LIMITS` |
| C1-C2: Types + Server Actions | 0.75d | 0.75d | 2 | TypeScript boilerplate |
| C3-C7: Auth pages (register, login, verify, forgot, reset) | 2d | 2.5d | 3 | Turnstile integration, password strength indicator, school branding. Mobile responsiveness needed |
| C8: Applicant dashboard | 1d | 1.5d | 5 | Application cards with status badges, empty state, period selector, claim dialog. Most complex frontend component |
| C9-C10: Detail + Print pages | 1d | 1d | 3 | Reuses patterns from admin application detail view |
| C11-C13: Landing/wizard/layout mods | 1d | 1d | 3 | Auto-save debounce, auth state gating, conditional redirect |
| D1-D3: Tests (47 tests) | 2.75d | 3.5d | 5 | Two-engine pattern, raw SQL fixtures with all NOT NULL columns, mock Turnstile + email sending |
| D4: Existing test updates | 0.25d | 0.25d | 1 | Conftest fixture + 2 enrollment tests |

**Total Estimated Effort:**

| Estimate | Dev-Days |
|----------|----------|
| Spec raw estimate | 11-15 |
| Revised raw estimate | **17-19** |
| With 25% buffer | **21-24** |
| Spec with 25% buffer | 14-19 |

**Confidence Level: Medium** -- The spec is well-detailed but has three specific interface mismatches with the actual codebase (see R1, R3, R7 below) that will add integration time.

**Recommended Buffer: 30%** -- Higher than the standard 25% because this feature introduces the first authenticated public-facing role, and the interaction between applicant auth, staff auth, and role promotion creates novel integration surface area.

### Is the 11-15 Estimate Realistic?

**No, it is approximately 30% too optimistic.** The three main underestimates are:

1. **ApplicantAccountService (A5)**: Spec estimates 1 day, but the service references `AuthService.send_verification_email(user)` and `AuthService.verify_email_token(token)` which do not exist in `backend/app/services/auth.py`. The actual email verification lives in `backend/app/services/email_verification.py` as `EmailVerificationService` with different method signatures (`create_verification_token(user_id, tenant_id, email)` + `send_verification_email(email, token, ...)`). Either the `ApplicantAccountService` must integrate with `EmailVerificationService` directly, or adapter methods must be added to `AuthService`. This adds 0.5-1 day.

2. **Testing (D1-D3)**: The spec estimates 2.75 days for 47 tests. Based on the existing test patterns in the codebase (raw SQL fixtures requiring ALL NOT NULL columns, two-engine setup, mock configurations for Turnstile and email), 47 tests with proper setup/teardown and the claim flow's edge cases will take 3-4 days. The IDOR tests (12 tests) alone require seeding two applicant users with applications in the same tenant, which is fixture-heavy.

3. **Role promotion interaction with ParentOnboardingService (A7)**: The enrollment service already calls `ParentOnboardingService.create_parent_for_student()` at step 10, which creates a User with `role=parent` from guardian email. If the application has `applicant_user_id`, the role promotion at step 9.5 sets the User role to `parent`. Then at step 10, `create_parent_for_student()` tries to create another User with the same email -- it may find the just-promoted user and skip, or it may fail. This interaction is not specified and needs investigation.

### Track Risk Assessment

| Track | Risk Level | Rationale |
|-------|------------|-----------|
| **A: Backend Core** | HIGH | Service method interface mismatches, role promotion interaction |
| **B: Backend Endpoints** | MEDIUM | Follows established patterns, but rate limit config for 6 new endpoints is detail work |
| **C: Frontend** | LOW-MEDIUM | Mostly page creation; auto-save debounce logic is the complex part |
| **D: Testing** | MEDIUM | Fixture complexity, need to mock Turnstile + email, 47 tests is substantial |

### Hidden Dependencies Between Tracks

1. **A5 blocks B2 and B3 entirely.** The `ApplicantAccountService` is the core of both public and authenticated endpoints. Until the `EmailVerificationService` integration question is resolved, no endpoint work can begin.

2. **C12 (auto-save) depends on B3 (PUT draft endpoint).** The auto-save debounce cannot be tested until the draft update endpoint exists.

3. **D1 tests depend on A5's final API.** If the service interface changes during implementation (likely, given the `AuthService` mismatch), tests written early may need rework.

4. **C7 (dashboard) depends on both B3 (list_my_applications endpoint) and C10 (claim dialog).** The dashboard page cannot be fully built until the list and claim endpoints are functional.

### Critical Path

```
A1 (enum) -> A4 (migration) -> A5 (service, 2 days) -> B1 (schemas) -> B2 (public endpoints) -> B3 (auth endpoints) -> D1 (tests)
                                    |
                                    +-> A6 (ApplicationService mods) -> B3 (auth endpoints)
                                    |
                                    +-> A7 (EnrollmentService) -> D4 (enrollment tests)
```

**Minimum timeline:** 10 working days with 2 developers working in parallel (1 backend, 1 frontend starting C1-C6 after A4 completes).

**Realistic timeline:** 14 working days (accounting for integration, review, and the issues identified below).

---

## 2. Risk Register

| ID | Risk | Category | Likelihood (1-5) | Impact (1-5) | Score | Mitigation | Owner |
|----|------|----------|-------------------|---------------|-------|------------|-------|
| **R1** | **Spec references nonexistent AuthService methods.** `AuthService.send_verification_email(user)` and `AuthService.verify_email_token(token)` do not exist. The actual implementation is in `EmailVerificationService` with different signatures. | Technical | **5** | **3** | **15** | Implementer must use `EmailVerificationService.create_verification_token()` + `send_verification_email()` directly, or create wrapper methods. Spec should be updated. | Track A |
| **R2** | **`User.email` model declares `unique=True` (global unique) but database has `uq_users_email_tenant` (composite unique on email+tenant_id).** The model at `backend/app/models/user.py:59` says `unique=True` which generates a global unique constraint. Migration `20260104_0300` dropped the global unique and created `uq_users_email_tenant`. **If Alembic autogenerate is run, it will try to recreate the global unique constraint**, breaking multi-tenant email registration. Additionally, the spec Test 4 (`test_register_same_email_different_tenant`) assumes composite uniqueness but does not address this model-DB mismatch. | Technical / Multi-Tenancy | **4** | **4** | **16** | Fix the model: change `unique=True` to remove it from the column def and add `__table_args__` with `UniqueConstraint('email', 'tenant_id', name='uq_users_email_tenant')`. This is a pre-existing bug, not introduced by this feature, but it will bite applicant registration across tenants. | Track A |
| **R3** | **Role promotion + ParentOnboardingService conflict.** The enrollment service step 10 calls `ParentOnboardingService.create_parent_for_student()` which creates a User with `role=parent` from guardian email. If the applicant's email matches a guardian email, two code paths both try to set `role=parent`: the new role promotion at step 9.5 and the existing step 10. The `create_parent_for_student()` may create a *duplicate* User if it doesn't check for existing users by email, or it may silently succeed if the user already exists. | Technical | **4** | **4** | **16** | Add a check to `create_parent_for_student()`: if a User already exists with the guardian's email and `role=parent` (just promoted from applicant), skip user creation. Alternatively, role promotion should run AFTER step 10 so it serves as a cleanup pass. | Track A |
| **R4** | **Shared cookie namespace causes session conflicts.** The spec (03-phase-2-frontend.md, line 197-200) acknowledges that applicant login uses "the SAME cookie names (access_token, refresh_token) as staff login." If a teacher at a school also has a child applying, they cannot be simultaneously logged in as staff and applicant in the same browser. Logging in as applicant overwrites the staff JWT. | UX / Technical | **3** | **3** | **9** | Accept as a known limitation for v1. Document it in the help center. Long-term: use separate cookie names (`applicant_access_token`, `applicant_refresh_token`) with a separate cookie path (`/apply`). This is a v2 enhancement. | Track C |
| **R5** | **`ALTER TYPE userrole ADD VALUE 'applicant'` cannot be rolled back.** PostgreSQL does not support `DROP VALUE` from enums. The downgrade function in the migration correctly documents this, but it means a rollback leaves an orphaned enum value. If a future migration checks enum values exhaustively, it may be confused. | Technical | **2** | **2** | **4** | Acceptable risk. The orphaned value is harmless. The `IF NOT EXISTS` clause makes re-application idempotent. Document in runbook. | Track A |
| **R6** | **Claim flow email matching fails when guardian used a different email format.** If the anonymous application lists guardian email as `John.Doe@GMAIL.COM` and the applicant registers as `johndoe@gmail.com`, the case-insensitive match succeeds (`.lower()` on both sides), but Gmail's dot-insensitivity is not handled. More critically, if the anonymous applicant used their *phone number* instead of email for a guardian, there is no email to match at all. | Technical / UX | **3** | **3** | **9** | The spec already uses `.lower()` for case normalization. For guardians without email, add an alternative claim path: tracking code + guardian phone number match. This is a v1.1 enhancement -- for v1, document that claiming requires the guardian email to match. | Track A |
| **R7** | **Auto-save debounce failure loses data silently.** The spec says auto-save triggers on step change with 2s debounce. If the PUT request fails (network timeout, 500 error, rate limit), the user sees no indication of save failure. They may close the browser believing their data is saved. | UX | **3** | **3** | **9** | Add a save status indicator to the form wizard: "Saving...", "Saved", "Save failed - click to retry". Show a confirmation dialog on browser close if there are unsaved changes (`beforeunload` event). | Track C |
| **R8** | **Email deliverability for verification (Ghana/Africa ISPs).** Gmail and Yahoo handle verification emails well, but local ISPs (Vodafone Ghana, MTN-branded emails) may delay, spam-filter, or silently drop verification emails. Parents may never receive the verification link. | Operational | **3** | **4** | **12** | Implement resend-verification endpoint (spec includes this). Add SMS-based verification as a fallback (send OTP to phone). Track verification email bounce rates via Sentry or SMTP logs. Consider allowing login without email verification for the first 24 hours (with limited access). | Track A/B |
| **R9** | **Password requirements too strict for non-technical parents.** The spec enforces 8+ chars, uppercase, lowercase, number, special character. Many parents in Ghana are not accustomed to complex passwords. High drop-off risk at registration. | UX | **3** | **3** | **9** | Add a real-time password strength meter (spec C3 mentions this). Consider relaxing to 8+ chars with 3 of 4 categories (instead of all 4). Add "Show password" toggle. Pre-populate a suggested strong password option. | Track C |
| **R10** | **Two parents creating separate accounts for the same child.** Father registers and applies for Kofi. Mother also registers (different email) and applies for Kofi. Two separate applications exist for the same child, leading to duplicate processing. | Data Integrity | **3** | **3** | **9** | This is fundamentally a data problem that cannot be solved purely in code without identity verification. Mitigation: admin deduplication tool in the admissions dashboard that flags applications with matching child name + DOB + target class. For v1, accept as a known limitation. | Track B |
| **R11** | **Draft application with stale period data.** Parent starts a draft while the admission period is open. Admin closes the period. Parent tries to submit the draft. The spec (Test 10) correctly handles this with a `PERIOD_NOT_OPEN` error. However, the UX is poor: the parent filled out the entire form and then cannot submit. | UX | **2** | **3** | **6** | On the dashboard, show a warning badge on drafts for closed/expired periods: "This admission period has closed. Your draft can no longer be submitted." Prevent opening the form wizard for closed-period drafts. | Track C |
| **R12** | **Applicant created in Tenant A tries to access Tenant B.** A parent registers at `presec.simsplus.io` and then visits `achimota.simsplus.io/apply/dashboard`. Their JWT contains `tenant_id` for Presec. | Multi-Tenancy | **2** | **4** | **8** | Already handled: the existing `TenantMiddleware` sets `request.state.tenant_id` from the subdomain, and `ValidatedUser`/`ValidatedTokenTenant` validates the JWT tenant matches the request tenant. The applicant will receive a 403. However, the error message should be user-friendly: "You are logged in at Presec. Please visit presec.simsplus.io/apply/dashboard to access your applications." | Track B |
| **R13** | **School admin accidentally creates user with role=applicant.** The user management endpoint (`POST /api/v1/users`) allows admins to create users with any role. If they select `applicant`, the user exists in the staff management UI but cannot access staff endpoints. | Operational | **2** | **2** | **4** | Add validation to the user creation endpoint: reject `role=applicant` on the admin user management endpoint. Applicant accounts must be created through the self-registration flow only. | Track B |
| **R14** | **Rate limit tuning -- too strict blocks legitimate users behind shared IP (school compound).** Schools in Ghana often share a single public IP via NAT. Multiple parents at a school open day could trigger rate limits when registering from the same IP. 3/min/IP for registration is particularly tight. | Operational | **3** | **3** | **9** | Use a composite rate limit key: `{IP}:{email_prefix}` for registration (so different emails from the same IP get separate buckets). Alternatively, increase registration limit to 10/min/IP since Turnstile already prevents bot abuse. | Track B |
| **R15** | **Monitoring/alerting gaps for new endpoints.** No Prometheus metrics or Sentry alerts are specified for: applicant registration failure rate, claim success rate, email verification completion rate, draft abandonment rate. | Operational | **2** | **3** | **6** | Add structured log events (already in spec) and create Grafana dashboards: "Applicant Registration Funnel" (register -> verify -> login -> draft -> submit). Alert on: verification email send failure rate > 10%, registration error rate > 20%. | Post-launch |
| **R16** | **Orphaned applicant users after rollback.** If the feature is rolled back (migration downgraded), users with `role='applicant'` remain in the `users` table. Their `applicant_user_id` links are lost (column dropped), and the enum value persists. These ghost users could appear in user management lists. | Quality | **2** | **2** | **4** | The rollback plan in the spec (05-verification-checklist.md) correctly identifies this. Add a cleanup SQL to the rollback runbook: `UPDATE users SET status='deactivated' WHERE role='applicant'`. The deactivated users will be filtered out of active user lists. | Track A |
| **R17** | **Social login demand from schools.** The spec explicitly excludes "Social login (Google, Facebook)." Schools targeting middle-class and international parents will demand this within 2-3 months of launch. Google login is especially expected. | Scope Creep | **4** | **2** | **8** | Architect the `ApplicantAccountService.register()` to accept an optional `provider` parameter (defaulting to `email`). Add a `provider` column to `users` (or use the existing `auth_provider` field if it exists). This makes social login a future addition without schema changes. | Track A |
| **R18** | **No notification preferences for applicants.** The spec does not cover how applicants opt out of emails (application status updates, marketing). GDPR and Data Protection Act 2012 (Ghana) require opt-out mechanisms. | Compliance | **3** | **3** | **9** | Add `notification_preferences` JSONB column to users (or a separate `applicant_preferences` table) with `email_updates: boolean`. For v1, default to opted-in with an unsubscribe link in every email. | Post-launch |
| **R19** | **Document management gap.** The spec includes `POST /applications/{id}/documents` for upload but no `GET` for listing or `DELETE` for removing uploaded documents. Applicants cannot view or manage their uploaded files. | Missing Feature | **2** | **2** | **4** | The print view includes `documents: list[PrintableDocumentInfo]`, so documents ARE displayed. Add `DELETE /applications/{id}/documents/{doc_id}` for draft applications only. File viewing can use existing S3 presigned URL patterns. | Track B |
| **R20** | **Missing application status visibility for applicants.** The spec does not explicitly state whether applicants can see admission decisions (accepted/rejected/waitlisted) in their dashboard. The `MyApplicationListItem` includes `status`, but the possible values and their display logic are not specified for the applicant-facing view. | UX | **2** | **3** | **6** | Clarify in the spec: applicants should see all statuses EXCEPT internal ones (e.g., `under_review` should show as "Under Review", `accepted` should show an offer letter prompt). Map `AdmissionApplicationStatus` values to applicant-friendly display strings. | Track C |

### Risk Matrix Summary

```
                    IMPACT
                Low(1-2)  Medium(3)  High(4-5)
LIKELIHOOD
High(4-5)     |  R5,R16  |  R9,R17  | R2,R3    |
              |  R13,R19 |          | R1       |
Medium(3)     |          | R4,R6,R7 | R8       |
              |          | R10,R14  |          |
              |          | R18      |          |
Low(1-2)      |          | R11,R15  | R12      |
              |          | R20      |          |
```

---

## 3. Multi-Tenancy Risk Assessment

### New Tables Requiring RLS Policies
**None.** This feature adds columns to existing tables (`applications`, `admission_periods`) and a new enum value. No new tables are created, so no new RLS policies are needed. The existing `tenant_isolation` policies on both tables automatically cover the new columns.

### Cross-Tenant Data Access Vectors

1. **Applicant registration with same email across tenants (R2):** The `User.email` column has `unique=True` in the model (global unique), but the database has `uq_users_email_tenant` (composite unique on `email + tenant_id`). This mismatch means the ORM may raise a `UniqueViolation` error when a parent tries to register at a second school. **This is the most critical multi-tenancy risk.** Fix: update the model to match the database constraint.

2. **JWT tenant validation:** Already handled by `ValidatedTokenTenant` dependency, which compares JWT `tenant_id` with `request.state.tenant_id`. Cross-tenant JWTs are rejected at the endpoint level.

3. **Claim flow cross-tenant attempt:** The claim service filters by `Application.tenant_id == tenant_id` (from subdomain), so a tracking code from Tenant A cannot be claimed at Tenant B. Defense-in-depth is in place.

4. **Applicant user visible to admin of different tenant:** Impossible due to RLS on the `users` table. Each admin only sees users in their own tenant.

### Cache/Session Tenant Bleed Risks

**LOW.** This feature does not introduce any new caching. All data flows through the existing tenant-scoped database session. If Redis caching is added later (e.g., caching applicant profile), keys must use the `{tenant_id}:{feature}:{key}` prefix pattern.

The shared cookie namespace (R4) is a session bleed risk between *roles* within the same tenant, not between tenants. A parent who is also a teacher at the same school will have their staff session replaced by the applicant session on login.

### Background Job Tenant Context

**NOT APPLICABLE for v1.** The spec does not introduce any Celery tasks. Email sending is synchronous (inline with the request). If email sending is moved to background tasks later, the Celery task must receive `tenant_id` as a parameter and call `set_tenant_context()` before any database operations.

---

## 4. Dependencies

### Internal Dependencies

| Component | Depends On | Status |
|-----------|------------|--------|
| Applicant Accounts migration | Admissions Portal migration (`20260303_0100`) | **Exists (untracked)** -- `backend/alembic/versions/20260303_0100_admissions_tables.py` is in the working directory |
| `ApplicantAccountService` | `EmailVerificationService` (not `AuthService.send_verification_email`) | **EXISTS but interface mismatch** -- spec references wrong service |
| `ApplicantAccountService.login()` | `AuthService.create_access_token()`, `AuthService.create_refresh_token()` | **Must verify these exist** -- spec assumes they do |
| `EnrollmentService` role promotion | `User` model update (APPLICANT enum value) | Ready after A1 + A4 |
| Frontend applicant pages | Backend applicant endpoints | Sequential dependency |
| Auto-save (C12) | Draft update endpoint (B3) | Sequential dependency |
| Claim dialog (C10) | Claim endpoint (B3) | Sequential dependency |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| Cloudflare Turnstile | Cloudflare | LOW | 0 days | Already integrated for admissions portal; reuse `TURNSTILE_SECRET_KEY` |
| SMTP (email verification) | Self-hosted / SendGrid | MEDIUM | 0 days | Already configured; but email deliverability to African ISPs is a concern (R8) |
| Redis (token blacklist, rate limiting) | Self (ElastiCache) | LOW | 0 days | Already provisioned |
| `EmailVerificationService` Redis token storage | Redis | LOW | 0 days | Uses Redis SET with TTL for verification tokens |

---

## 5. Recommended Approach

### Parallel Tracks

- **Track A (Backend Models + Services):** 1 backend developer, days 1-5
  - Day 1: A1-A4 (model changes + migration)
  - Day 2-3: A5 (ApplicantAccountService -- resolve EmailVerificationService integration)
  - Day 4: A6 (ApplicationService mods) + A7 (EnrollmentService role promotion)
  - Day 5: A8 (permissions) + integration testing

- **Track B (Backend Endpoints + Middleware):** Same or 2nd backend developer, days 3-7
  - Day 3: B1 (schemas) -- can start once A5 interface is stable
  - Day 4-5: B2 (public endpoints) + B4 (dependency) + B5 (middleware)
  - Day 6-7: B3 (authenticated endpoints)

- **Track C (Frontend):** 1 frontend developer, days 2-10
  - Day 2-3: C1-C2 (types + actions -- can start once B1 schemas are known)
  - Day 4-6: C3-C7 (auth pages)
  - Day 7-8: C8 (dashboard) + C10 (claim dialog)
  - Day 9: C9 (detail page) + C10 (print view)
  - Day 10: C11-C13 (modifications to existing pages)

- **Track D (Testing):** 1 developer (backend dev), days 8-12
  - Day 8-9: D1 (account tests, 15 tests)
  - Day 10-11: D2 (application tests, 18 tests)
  - Day 11-12: D3 (IDOR tests, 12 tests) + D4 (enrollment test updates)

### Sequential Dependencies

```
1. A1-A4: Model + Migration (MUST be first -- all other work depends on enum + columns)
2. A5: ApplicantAccountService (BLOCKS B2, B3)
3. B1: Schemas (BLOCKS B2, B3, and informs C1)
4. B2 + B5: Public endpoints + Middleware (BLOCKS C3-C7 integration testing)
5. A6 + B3: ApplicationService + Auth endpoints (BLOCKS C8 dashboard)
6. A7: EnrollmentService (BLOCKS D4)
7. D1-D4: All testing (MUST come after services + endpoints are stable)
```

### Critical Path

**A1 -> A4 -> A5 -> B1 -> B2 -> B3 -> D1 -> D2 -> D3**

This path runs through the backend core. The frontend can run in parallel from day 2, but integration testing is blocked until B2/B3 are complete.

**Minimum Timeline:** 10 working days (2 developers in parallel: 1 backend, 1 frontend)
**Realistic Timeline:** 14 working days (with buffer for R1, R2, R3 resolution + integration issues)

---

## 6. Specific Technical Risk Deep-Dives

### 6.1 The `AuthService` Interface Mismatch (R1)

**What the spec says (02-phase-1-services-endpoints.md, lines 558-570):**
```python
auth_service = AuthService(self.db)
await auth_service.send_verification_email(user)
```

**What the codebase actually has:**
- File: `backend/app/services/email_verification.py`
- Class: `EmailVerificationService`
- Methods: `create_verification_token(user_id, tenant_id, email)` and `send_verification_email(email, token, ...)`
- `AuthService.verify_email(user_id)` exists but takes `user_id`, not a `token`
- `AuthService.verify_email_token(token)` does NOT exist

**Resolution options:**
1. (Recommended) Use `EmailVerificationService` directly in `ApplicantAccountService`. Replace the spec's `auth_service.send_verification_email(user)` with:
   ```python
   from app.services.email_verification import EmailVerificationService
   ev_service = EmailVerificationService(self.db, redis_client=request.app.state.redis)
   token = await ev_service.create_verification_token(user.id, tenant_id, user.email)
   await ev_service.send_verification_email(user.email, token, tenant_name=...)
   ```
2. Add wrapper methods to `AuthService` that delegate to `EmailVerificationService`. More indirection, but keeps the spec's interface.

**Impact:** 0.5-1 day additional effort for option 1. The verify_email endpoint also needs adjustment -- it should call `EmailVerificationService.verify_email(token)` instead of the nonexistent `auth_service.verify_email_token()`.

### 6.2 The `User.email unique=True` Model-DB Mismatch (R2)

**Current state:**
- Model (`backend/app/models/user.py:59`): `unique=True` (implies global unique constraint `users_email_key`)
- Database (after migration `20260104_0300`): Composite unique constraint `uq_users_email_tenant` on `(email, tenant_id)`
- The global unique index was dropped by the migration

**Why this matters for applicant accounts:**
- Test 4 in the spec (`test_register_same_email_different_tenant`) expects that `parent@test.com` can register in both Tenant A and Tenant B
- If the `unique=True` on the model triggers a global unique constraint at test DB creation time (via `create_all()`), this test will fail
- In production, the migration has already applied the correct composite constraint, so production works
- But development/test environments using `create_all()` instead of running all migrations will have the wrong constraint

**Resolution:** Fix the model before implementing applicant accounts:
```python
# backend/app/models/user.py
email: Mapped[str] = mapped_column(
    String(255),
    nullable=False,
    index=True,
    # unique is NOT set here -- composite unique constraint in __table_args__
)

__table_args__ = (
    UniqueConstraint('email', 'tenant_id', name='uq_users_email_tenant'),
)
```

### 6.3 Role Promotion vs. ParentOnboardingService (R3)

**Current enrollment flow (no applicant accounts):**
```
Step 10: For each guardian with email:
  ParentOnboardingService.create_parent_for_student(email, ...)
  -> Creates new User(role='parent') if no User exists with that email
  -> Skips if User already exists with that email
```

**New flow with applicant accounts:**
```
Step 9.5 (NEW): If application.applicant_user_id exists AND user.role == 'applicant':
  user.role = 'parent'  (promotion)

Step 10: For each guardian with email:
  ParentOnboardingService.create_parent_for_student(email, ...)
  -> Finds existing User (just promoted to 'parent') -> skips (hopefully)
```

**The problem:** What if `create_parent_for_student()` does not check for existing users by email? Or what if it checks but the email normalization differs? The spec does not address this interaction.

**Resolution:** Before implementing role promotion, read `backend/app/services/parent/parent_onboarding.py` to understand how `create_parent_for_student()` handles existing users. If it does not check, add the check. The role promotion logic should run AFTER step 10 as a cleanup pass, not before.

### 6.4 Cookie Session Conflict (R4)

**Scenario:** Mrs. Ama is a teacher at Presec AND a parent applying for her child's admission.

1. Mrs. Ama logs into the staff dashboard at `presec.simsplus.io` -> cookies: `access_token` (role=teacher), `refresh_token`
2. Mrs. Ama visits `presec.simsplus.io/apply/login` -> logs in as applicant -> cookies OVERWRITTEN: `access_token` (role=applicant), `refresh_token`
3. Mrs. Ama navigates to `presec.simsplus.io/dashboard` -> staff dashboard tries to load with applicant JWT -> 403 Forbidden

**Why this is hard to fix:**
- Using separate cookie names (`applicant_access_token`) requires changing the frontend auth infrastructure
- Using cookie path scoping (`path: /apply`) works for staff cookies not leaking to applicant, but the global `access_token` still gets overwritten
- This is a same-origin problem -- both portals share the same domain

**Recommendation for v1:** Document as a known limitation. Most parents are not also staff. For those who are, they should use separate browsers or an incognito window. This should be logged as a v2 enhancement with separate cookie namespaces.

---

## 7. Comparison with Admissions Portal Spec

### Quality/Detail Level

The Applicant Accounts spec is **comparable in quality** to the Admissions Portal spec. Both follow the same structure (overview, models, services, frontend, testing, verification). Key comparisons:

| Aspect | Admissions Portal | Applicant Accounts |
|--------|------------------|-------------------|
| New tables | 16 | 0 (columns only) |
| Spec files | 12 | 6 |
| Schema detail | Full SQL DDL | Model code snippets |
| Service code | Pseudocode + signatures | Near-complete implementation code |
| Frontend code | Component structure | Near-complete implementation code |
| Test detail | Test descriptions | Test descriptions with assertions |
| Verification checklist | Yes | Yes, more detailed |
| Rollback plan | Brief | Comprehensive with data preservation |

The Applicant Accounts spec is actually MORE detailed in implementation code -- it provides nearly complete Python and TypeScript implementations, not just pseudocode. This is a strength for implementability but creates a risk: implementers may copy-paste without verifying interfaces (which is how R1 would manifest).

### Missing Patterns from Admissions Portal

1. **The admissions portal spec (Decision 10) explicitly addresses the `NotificationDispatcher` limitation** -- that it cannot send to non-users. The applicant accounts spec does not mention notification delivery to applicants (e.g., "Your application status changed"). It implicitly relies on the admissions notification service, but does not specify how status update emails reach applicant accounts.

2. **The admissions portal spec includes JSONB schema validation** (`jsonschema` library for `custom_fields`). The applicant accounts spec's `DraftApplicationCreate` and `DraftApplicationUpdate` accept `custom_fields: dict[str, Any]` but do not specify validation against the period's `form_schema`. This means an applicant could save invalid custom fields in a draft.

3. **The admissions portal spec covers file upload security** (magic byte validation, sanitized error messages, size limits). The applicant accounts spec includes `POST /applications/{id}/documents` but does not specify upload constraints for the applicant-facing endpoint. The existing admin upload endpoints have these protections, but the applicant endpoint must explicitly reuse them.

### Testing Coverage Assessment

- **Admissions Portal:** 80+ tests for 30 endpoints = ~2.7 tests/endpoint
- **Applicant Accounts:** 47 tests for 18 endpoints = ~2.6 tests/endpoint

Coverage is proportionally adequate. However, the applicant accounts spec is missing:

1. **Performance tests** -- no load testing for the registration endpoint (which includes Turnstile verification + Argon2id hashing + email send -- 3 external calls in series)
2. **Concurrent draft save tests** -- what happens if two tabs auto-save the same draft simultaneously?
3. **Cross-tenant claim tests** -- only 1 cross-tenant test (Test 11 in IDOR tests), could use more scenarios

---

## 8. Recommendations

### Top 5 Risks -- Required Actions

1. **R2 (Score: 16) -- Fix `User.email unique=True` model-DB mismatch BEFORE starting implementation.** This is a pre-existing bug that will block multi-tenant applicant registration. Create a separate PR to fix the model and add a test that verifies composite uniqueness. **Owner: Backend lead, Day 0.**

2. **R1 (Score: 15) -- Resolve AuthService interface mismatch immediately.** The implementer of `ApplicantAccountService` needs to know the correct service to call for email verification. Spike: 2 hours to read `EmailVerificationService` and determine the correct integration path. Update the spec before implementation begins. **Owner: Track A lead, Day 1.**

3. **R3 (Score: 16) -- Investigate ParentOnboardingService before implementing role promotion.** Read `backend/app/services/parent/parent_onboarding.py` to understand how `create_parent_for_student()` handles existing users. Write an integration test that covers: applicant user exists -> enrollment -> role promotion -> step 10 does not create duplicate User. **Owner: Track A lead, Day 4.**

4. **R8 (Score: 12) -- Plan email deliverability fallback.** Before beta launch, set up SPF/DKIM/DMARC records for the simsplus.io domain. Add an SMS verification fallback for the `resend-verification` endpoint. Track verification email delivery rates from day 1. **Owner: DevOps + Track A.**

5. **R4 (Score: 9) -- Document cookie conflict as known limitation.** Add a help center article and a tooltip on the applicant login page: "If you are also a staff member, please use a different browser for the applicant portal." Log this as a v2 enhancement. **Owner: Track C.**

### Technical Spikes Needed Before Committing

| Spike | Duration | Question to Answer |
|-------|----------|--------------------|
| EmailVerificationService integration | 2 hours | What is the correct method signature for sending + verifying email tokens? Does it need Redis access? How to get Redis client in the service context? |
| ParentOnboardingService existing-user check | 2 hours | Does `create_parent_for_student()` skip if User already exists? What if the User's role is already `parent`? |
| Cookie namespace separation feasibility | 1 hour | Can we scope applicant cookies to `/apply` path without breaking the auth refresh flow? |
| ALTER TYPE ADD VALUE in Alembic transaction | 1 hour | Does PostgreSQL 16 allow `ADD VALUE` in a transaction when the value is not used in the same migration? Test locally. |

### Start Early

1. **Fix R2 (User.email unique=True)** -- Do this today, before any applicant accounts work begins
2. **Spike R1** -- Determine the correct email verification integration path
3. **Frontend C1-C2** -- Types and Server Actions can be started as soon as schemas (B1) are drafted, even if endpoints are not yet functional

### Blockers to Resolve

| Blocker | Impact | Resolution |
|---------|--------|------------|
| `AuthService.send_verification_email()` does not exist | Blocks A5 | Use `EmailVerificationService` directly |
| `User.email unique=True` in model | Blocks Test 4 (multi-tenant registration) | Fix model to use composite unique |
| Role promotion + ParentOnboardingService interaction unknown | Blocks A7 | Read `parent_onboarding.py`, add integration test |

---

## 9. Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| SPF/DKIM/DMARC DNS records | Email deliverability for verification emails | 1-2 days | None (DNS config only) |
| Increased SMTP throughput | Handle registration spike during admission season | 1 week | Depends on provider; SendGrid free tier: 100 emails/day |
| Redis memory headroom | Verification tokens (1 per registration, TTL 24h) | 0 days | Negligible -- ~200 bytes per token |
| CloudFront cache bypass for `/apply/*` | Dynamic pages must not be cached | 1 day | None |
| Sentry error alerts for applicant endpoints | Monitor registration/login failures | 1 day | None (within existing Sentry plan) |

---

## 10. Scope Creep Watchlist

These items are out of scope but have high demand probability:

| Feature | Demand Timeline | Prep Work |
|---------|----------------|-----------|
| Google/Social login | 2-3 months post-launch | Add `provider` field to User model now |
| Multi-language forms | International schools demand this early | Use i18n keys in form labels now |
| Application fee refunds | When first parent requests one | Design refund flow with Paystack reversal |
| Shared family accounts | Multiple parents for same children | Currently out of scope; complex identity problem |
| Applicant document vault | Parents want to store certificates | Use existing S3 infrastructure |
| SMS verification fallback | Poor email deliverability in rural areas | Design as v1.1 enhancement |
