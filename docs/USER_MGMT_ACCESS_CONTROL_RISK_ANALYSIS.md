# Risk Analysis: User Management & Access Control

**Date:** 2026-03-21
**Analyst:** Risk Analyst Agent (Claude Opus 4.6)
**Spec:** `/spec/user-management-access-control/` (files 00-09)
**Spec Estimate:** 11 working days (~2.5 weeks)

---

## Executive Summary

The User Management & Access Control plan is well-structured and largely grounded in existing codebase patterns, making it lower-risk than prior multi-curriculum or admissions analyses. However, the **11-day timeline is optimistic by approximately 30-40%**, primarily due to underestimated frontend complexity in MFA and Custom Roles, the auth.py modification collision between Phases 3 and 4, and the Arkesel SMS migration carrying hidden blast radius across 6+ files and the DB enum type. The most dangerous single risk is the **SMSProvider enum type change** (Phase 0), which is destructive and irreversible in a way that the spec acknowledges but underestimates. The MFA login flow modification to `auth.py` is the second-highest-risk change, as it alters the critical path that every user in the system traverses on every login.

---

## Component Complexity

| Component | Spec Est. | Revised Complexity | Revised Estimate | Notes |
|-----------|-----------|-------------------|-----------------|-------|
| Phase 0: Arkesel SMS Migration | 1 day | 3 | 1.5 days | Enum type change is destructive; 6+ files to update; test mock updates |
| Phase 1A: HR Officer Role | 0.5 days | 1 | 0.5 days | Purely additive; lowest risk item |
| Phase 1B: OTP + Phone Verify + SMS Reset | 2-3 days | 5 | 3.5 days | New service + 4 endpoints + frontend UI + Redis integration |
| Phase 1C: Bulk User Import | 1.5-2 days | 3 | 2 days | Follows staff import pattern; CSV edge cases underestimated |
| Phase 2: Session Timeout | 2 days | 3 | 2.5 days | Frontend hook is complex (timer management, multi-tab); server component is simple |
| Phase 3: MFA (TOTP) | 3-4 days | 5 | 5 days | Crypto operations, login flow modification, 3-step wizard, backup codes |
| Phase 4: Custom Roles | 3-4 days | 5 | 4.5 days | New table + RLS + permission resolution change + permission picker UI |
| Migration | (included) | 2 | 0.5 days | Combined migration is sound but needs careful testing |
| Testing | (included) | -- | 3 days | 9 test files specified; integration tests needed |

**Total Estimated Effort:** 23 developer-days (raw)
**Spec Estimate:** 11 developer-days (assuming 3 parallel devs for Phase 1)
**Confidence Level:** Medium -- the individual components are well-specified, but the auth.py collision zone and the enum migration are non-trivial risks
**Recommended Buffer:** 25% -- yielding ~29 developer-days / ~15 calendar days with 2 developers

### Timeline Realism: Serial vs. Parallel

The spec assumes 3 developers working Phase 1 items in parallel. Adjusting:

- **With 3 developers:** Phase 0 (1.5d) + Phase 1 (3.5d parallel) + Phase 2 (2.5d) + Phase 3 (5d) + Phase 4 (4.5d) + Testing (3d) = ~20 calendar days minimum. Phases 3 and 4 are serial (auth.py collision), so the critical path is Phase 0 -> Phase 1B -> Phase 3 -> Phase 4 = 14.5 days minimum even with perfect parallelism elsewhere.

- **With 1 developer:** 23 raw days + 6 buffer = ~29 days (~6 weeks).

- **The spec's 11-day estimate is achievable only with 3 developers AND no testing buffer AND no buffer for integration issues.** This is unrealistic. Realistic estimate for 2 developers: ~3.5 weeks.

---

## Risk Register

| ID | Risk | Category | Severity | Probability | Impact | Mitigation | Spec File(s) to Update |
|----|------|----------|----------|-------------|--------|------------|----------------------|
| R1 | **SMSProvider enum type change is destructive** -- `ALTER TYPE smsprovider RENAME TO smsprovider_old; CREATE TYPE smsprovider AS ENUM ('arkesel'); ALTER TABLE sms_log ALTER COLUMN provider TYPE smsprovider USING 'arkesel'::smsprovider; DROP TYPE smsprovider_old;` will fail if ANY other table or view references `smsprovider`. The `check_constraint` on the column created by `create_constraint=True` in the model will also conflict. | Technical | High | High | Data loss or failed deployment. Migration cannot be rolled back once old type is dropped. | 1. Verify no other tables reference `smsprovider` type. 2. Drop the check constraint before type swap. 3. Test on a DB snapshot first. 4. Consider keeping HUBTEL and TWILIO values in enum (benign; avoids destructive DDL entirely). | `09-arkesel-sms-migration.md` (Task 7), `07-migration-plan.md` |
| R2 | **auth.py is modified by both Phase 3 (MFA login flow) and Phase 4 (permission resolution)** -- concurrent development will cause merge conflicts on the most critical file in the system | Integration | High | High | Login regression affecting all users if merge is botched | Serialize Phases 3 and 4 strictly. Phase 3 developer completes and merges before Phase 4 begins. Do NOT attempt parallel development on auth.py. | `00-overview.md` (timeline section) |
| R3 | **MFA login flow changes authenticate() return type** -- currently returns `Tuple[User, str, str]`, Phase 3 changes it to sometimes return a `dict`. This breaks the type contract and all callers. | Technical | High | High | Runtime errors in login flow, typing violations | Refactor authenticate() to always return a typed response object (e.g., `AuthResult` dataclass with `mfa_required` field) instead of mixing tuple and dict returns. This is cleaner and type-safe. | `05-phase-3-mfa.md` (Task 7) |
| R4 | **Password field name mismatch** -- Spec references `user.hashed_password` in multiple places (Phase 1B reset-password-sms line 631, Phase 3 MFA disable). Actual User model has `password_hash` (line 73 of user.py). | Technical | High | High | NameError at runtime on password reset and MFA disable/verify | Fix all spec references from `hashed_password` to `password_hash`. Also fix `get_password_hash` to match actual function name (verify in `core/security.py`). | `02-phase-1b-otp-phone-verification.md` (Task 4, endpoint 4), `05-phase-3-mfa.md` (Task 5) |
| R5 | **mfa_pending token type not handled in get_current_user_id** -- Phase 3 Task 9 says to reject `mfa_pending` tokens in deps.py, but the current code (line 222) already rejects anything where `type != "access"`. So the `mfa_pending` token with `type: "mfa_pending"` would ALREADY be rejected. This means the `/auth/mfa/verify` endpoint cannot use `get_current_user_id` -- it must parse the token independently. | Technical | Medium | High | MFA login verification endpoint always returns 401 | Spec already implies manual token parsing in Task 8, but Task 9 is misleading -- the check already exists. Remove Task 9 or note it as already-handled. Ensure `/auth/mfa/verify` does NOT use `CurrentUserId` dependency. | `05-phase-3-mfa.md` (Task 9) |
| R6 | **OTP service instantiates ArkeselClient() per call** (line 168-169 of spec) -- creates a new httpx client per OTP send. Should use the module-level singleton pattern like sms.py does. | Technical | Low | High | Unnecessary connection overhead; potential connection pool exhaustion under load | Use module-level `_sms_client = ArkeselClient()` singleton, or accept `ArkeselClient` as a constructor parameter of `OTPService`. | `02-phase-1b-otp-phone-verification.md` (Task 1) |
| R7 | **`get_school_for_tenant().limit(1)` antipattern repeated** -- Phase 1B endpoints (lines 414-418, 544-548) use `select(School).where(School.tenant_id == user.tenant_id).limit(1)` for school name lookup. This is the known antipattern for chain tenants (multiple schools per tenant). | Technical | Medium | Medium | Wrong school name in OTP messages for chain tenants | Use `user.school_id` to look up the specific school, falling back to tenant name if no school_id. | `02-phase-1b-otp-phone-verification.md` (Tasks 4, endpoints 1 and 3) |
| R8 | **Bulk import returns plaintext temp passwords in HTTP response** -- credentials array with `temporary_password` in the response body. If response is logged by any middleware, proxy, or client-side error tracker, passwords are exposed. | Operational | Medium | Medium | Password exposure in logs or error tracking | 1. Ensure no response logging middleware captures this endpoint's body. 2. Add `X-Sensitive-Response: true` header and exclude from Sentry breadcrumbs. 3. Consider encrypting the credentials CSV with a one-time key. | `03-phase-1c-bulk-user-import.md` (Task 2) |
| R9 | **Bulk import per-row DB query for email uniqueness** -- for 200 rows, this is 200 sequential SELECT queries. Will be slow. | Technical | Medium | High | Slow import preview (10+ seconds for 200 rows) | Batch the email uniqueness check: collect all emails, do a single `SELECT email FROM users WHERE email IN (...) AND tenant_id = :tid`, then check results against the set. | `03-phase-1c-bulk-user-import.md` (Task 1) |
| R10 | **Session timeout hook has stale closure over `showWarning`** -- the `onActivity` callback captures `showWarning` in its closure, but `useCallback` dependency array includes `showWarning`. This causes the event listeners to be re-registered every time `showWarning` changes, which is a common React bug that can cause duplicate listeners or missed events. | Technical | Medium | Medium | Session timeout warning may not appear, or may appear multiple times | Use a ref for `showWarning` state instead of depending on it in the callback closure. The event listeners should be registered once and use refs for mutable state. | `04-phase-2-session-timeout.md` (Task 6) |
| R11 | **MFA backup code hashing with Argon2id is slow by design** -- hashing 10 backup codes during setup will take ~2-3 seconds (Argon2id is intentionally slow at ~200-300ms per hash). During login verification, verifying a backup code checks up to 10 hashes sequentially = potential 2-3 second response time. | Technical | Medium | High | Slow MFA setup response (2-3s) and slow backup code verification (worst case 2-3s) | 1. For setup: accept the latency as it's one-time. 2. For verification: try TOTP first (fast), only fall back to backup code scan. 3. Consider bcrypt (faster) instead of Argon2id for backup codes since they're already high-entropy random strings. | `05-phase-3-mfa.md` (Task 5) |
| R12 | **MFA secret encryption key rotation not addressed** -- if `MFA_SECRET_ENCRYPTION_KEY` is compromised, there's no mechanism to re-encrypt all secrets. Also, if the key is lost, all MFA setups become unrecoverable. | Operational | Medium | Low | All MFA users locked out if key is lost | 1. Document key backup procedure. 2. Add key versioning (`mfa_key_version` column) for future rotation. 3. Include key recovery in incident response plan. | `05-phase-3-mfa.md` (Task 2) |
| R13 | **Custom roles permission catalog is incomplete** -- the catalog in Task 2 is missing several permissions that exist in ROLE_PERMISSIONS: `exams.scores.submit`, `exams.ca.enter`, `exams.ca.read`, `boarding.exeat.approve`, all `teacher.*` permissions (14 of them), all `applicant.*` permissions, `parent.*` permissions, `self.read`, `self.update`, `finance.invoices.read`, `children.read`. | Technical | High | High | Custom roles cannot grant permissions that exist in the base role, causing silent permission gaps. Admin creates "Senior Teacher" role with base_role=teacher but cannot select `exams.scores.submit` because it's not in the catalog. | Audit ROLE_PERMISSIONS dict and ensure every non-wildcard permission appears in PERMISSIONS_CATALOG. Add missing modules for teacher portal, parent portal, applicant, and self-service permissions. | `06-phase-4-custom-roles.md` (Task 2) |
| R14 | **Custom role wildcard expansion is incomplete** -- `_get_base_role_permissions()` expands `staff.*` to all `staff.X` permissions in the catalog. But `staff.*` in ROLE_PERMISSIONS means "ALL staff operations" including ones not in the catalog (e.g., future `staff.payroll`). If a new permission is added to the catalog later, existing custom roles won't automatically gain it even if their base_role has `staff.*`. | Technical | Medium | Medium | Permission drift: custom roles fall behind as new features are added | Document this as a known limitation. When new permissions are added to the catalog, admins must manually update custom roles. Consider a "sync with base role" button in the UI. | `06-phase-4-custom-roles.md` (Task 3) |
| R15 | **Arkesel SMS delivery reliability is unknown** -- the spec migrates from Hubtel (which has known reliability data in Ghana) to Arkesel. No fallback provider is configured. If Arkesel is down, ALL OTP, password reset, and notification SMS fails. | Operational | Medium | Medium | Complete SMS outage during Arkesel downtime; users cannot verify phones or reset passwords via SMS | 1. Keep TWILIO in SMSProvider enum as a fallback for international numbers. 2. Monitor Arkesel delivery rates for 2 weeks post-migration before relying on it for critical flows (OTP/password reset). 3. SMS password reset is already a secondary path (email is primary). | `09-arkesel-sms-migration.md` |
| R16 | **TENANT_SCOPED_TABLES count is wrong in migration plan** -- Spec says to update from 55 to 56 tables. Memory records show the actual count is 91 (corrected 2026-03-06). The migration plan references an outdated number. | Technical | Low | High | Test infrastructure assertions fail; conftest.py RLS check breaks | Update the migration plan to reference the actual current TENANT_SCOPED_TABLES count (91 + 1 = 92 after adding custom_roles). | `07-migration-plan.md` |
| R17 | **Combined migration has ALTER TYPE ADD VALUE inside transaction** -- The spec notes PostgreSQL 16 allows this, which is correct. However, Alembic's default behavior with `op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'hr_officer'")` requires the migration to NOT be wrapped in a transaction block (Alembic's `autocommit` or `non_transactional_ddl` context). If not configured correctly, this will fail silently or error. | Technical | Medium | Medium | Migration fails with "ALTER TYPE ... ADD VALUE cannot be executed from within a transaction" | Wrap the ALTER TYPE statement in a non-transactional block, or split it into a separate migration file that uses `autocommit=True`. This is a well-known Alembic footgun. | `07-migration-plan.md` |
| R18 | **Phone number normalization not implemented** -- OTP service spec says "Phone numbers should be normalized before storage/lookup" (line 39) but provides no normalization logic. Users might enter `0241234567` or `+233241234567` or `233241234567`. If the stored format differs from the lookup format, OTP verification will fail. | Technical | Medium | High | OTP sent to `+233241234567` but verification attempted with `0241234567` -- Redis key mismatch, verification fails | Add phone normalization using the existing `phonenumbers` library (already in requirements.txt). Normalize to E.164 format at both generation and verification time. | `02-phase-1b-otp-phone-verification.md` (Task 1) |
| R19 | **apiPostForm does not exist in frontend** -- Spec (Phase 1C, Task 5 note) acknowledges this may not exist. The bulk import requires multipart/form-data upload, but all existing `apiPost` calls use JSON. This is a net-new pattern. | Technical | Low | High | Import endpoint unreachable from frontend until apiPostForm is created | Create `apiPostForm` in `lib/api.ts` following the existing `apiPost` pattern but omitting Content-Type header (let browser set multipart boundary). Budget 0.5 day for this. | `03-phase-1c-bulk-user-import.md` (Task 5) |
| R20 | **Fernet encryption key not in requirements.txt** -- MFA uses `cryptography.fernet.Fernet` but `cryptography` is not listed in requirements.txt. It's likely installed as a transitive dependency of `python-jose[cryptography]`, but this is fragile. | Technical | Low | High | Import error on `from cryptography.fernet import Fernet` if transitive dependency changes | Add `cryptography>=42.0.0` explicitly to requirements.txt. | `05-phase-3-mfa.md` (Task 1) |
| R21 | **Dashboard layout may be a Server Component** -- Phase 2 spec (Task 8) acknowledges this and provides a workaround, but the `useSessionTimeout` hook requires client-side state. If the layout is already a Server Component with many server-side data fetches, wrapping it in a Client Component boundary may cause a cascade of "use client" propagation. | Technical | Medium | Medium | Significant frontend refactoring to accommodate client-side session timeout | Check if dashboard layout already has a client component wrapper. If not, create a thin `SessionTimeoutProvider` that wraps only the timeout logic without forcing the entire layout to be client-rendered. | `04-phase-2-session-timeout.md` (Task 8) |
| R22 | **No test for Arkesel client itself** -- The testing plan (08) lists tests for existing SMS messaging tests updated with new mocks, but no dedicated `test_arkesel_client.py` for the new ArkeselClient class (response parsing, error handling, balance check, bulk send). | Timeline | Medium | Medium | ArkeselClient bugs not caught until integration; regressions on error handling paths | Add `test_arkesel_client.py` with mocked httpx responses for: success, 402 (insufficient balance), 403 (auth failure), 422 (validation), timeout, and sandbox mode. | `08-testing-plan.md` |
| R23 | **Custom role assignment during bulk import not addressed** -- Phase 1C allows importing users with predefined roles only. When Phase 4 adds custom roles, the import CSV format has no `custom_role_id` column. This is fine now but creates a UX gap later. | Timeline | Low | Low | Admins cannot bulk-assign custom roles; must update users one by one after import | Document as a known limitation. Add custom_role column to CSV import in a future sprint. | `03-phase-1c-bulk-user-import.md` |

---

## Multi-Tenancy Risk Assessment

### New tables requiring RLS policies
- `custom_roles` -- Phase 4. RLS policy specified correctly in migration plan.

### Cross-tenant data access vectors
1. **OTP Redis keys are tenant-scoped** -- correctly uses `otp:{purpose}:{tenant_id}:{phone}:{suffix}` format. Cross-tenant OTP reuse is prevented.
2. **Custom roles** -- RLS policy on `custom_roles` table prevents cross-tenant access. The `created_by` FK to `users` is not tenant-scoped (users table has its own RLS), but since `custom_roles` itself is tenant-scoped, this is safe.
3. **MFA secrets** -- stored on the `users` table which already has RLS. No new cross-tenant vector.
4. **Bulk import** -- creates users within the authenticated admin's tenant. No cross-tenant risk.

### Cache/session tenant bleed risks
- **OTP Redis keys** -- correctly tenant-scoped. No bleed risk identified.
- **Session timeout** -- `last_activity_at` is per-user on the `users` table (RLS-protected). No bleed risk.
- **MFA pending tokens** -- contain `tenant_id` in claims. Token validation at `/auth/mfa/verify` should verify tenant_id matches request context.

### Background job tenant context
- **Welcome emails for bulk import** -- spec mentions queuing emails but doesn't specify how tenant context propagates to the email worker. If using Celery, the task must include `tenant_id` in its arguments. The existing email service pattern should be followed.

---

## Dependencies

### Internal Dependencies

| Component | Depends On | Status |
|-----------|------------|--------|
| Phase 1B (OTP) | Phase 0 (Arkesel client) | Phase 0 must complete first |
| Phase 3 (MFA) | Phase 1 completion (auth.py must be stable) | Sequential |
| Phase 4 (Custom Roles) | Phase 3 completion (auth.py must be stable) | Sequential |
| Phase 1C (Bulk Import) | User model + UserService | Ready (existing) |
| Phase 2 (Session Timeout) | Auth endpoints (heartbeat) | Can start after Phase 0 |
| Combined Migration | All model changes | Must be written after all models finalized |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| Arkesel API key | DevOps/Harry | Low | 1 day | Account creation at developers.arkesel.com |
| Arkesel sender ID approval | Arkesel | Medium | 3-7 days | Custom sender IDs (e.g., "SIMSPlus") require approval in Ghana. May be blocked if not pre-registered. |
| pyotp 2.9.0 | PyPI | Low | Immediate | Stable, well-maintained, 2.1M downloads/month |
| qrcode[pil] 7.4.2 | PyPI | Low | Immediate | Stable, requires Pillow (already in requirements) |
| MFA_SECRET_ENCRYPTION_KEY generation | DevOps | Low | Immediate | One-time key generation, must be in env vars before MFA phase |

---

## Recommended Approach

### Parallel Tracks (with 2+ developers)

- **Track A (Developer 1):** Phase 0 (Arkesel) -> Phase 1B (OTP) -> Phase 3 (MFA) -> Phase 4 (Custom Roles)
  - This is the critical path because of the auth.py serialization requirement.

- **Track B (Developer 2):** Phase 1A (HR Officer) -> Phase 1C (Bulk Import) -> Phase 2 (Session Timeout) -> Testing
  - These are independent and can run in parallel with Track A.

### Sequential Dependencies (Strict Order)

1. Phase 0: Arkesel SMS Migration (blocks Phase 1B)
2. Phase 1B: OTP Service (blocks nothing directly, but tests SMS infrastructure)
3. Phase 3: MFA (modifies auth.py -- must complete before Phase 4)
4. Phase 4: Custom Roles (modifies auth.py permission resolution)
5. Combined Migration (must be finalized after all model changes are confirmed)

---

## Critical Path

The sequence of tasks that determines the minimum timeline:

**Phase 0 (1.5d) -> Phase 1B (3.5d) -> Phase 3 (5d) -> Phase 4 (4.5d) = 14.5 developer-days on the critical path**

**Minimum Timeline:** 15 days with 2 developers (critical path + Track B in parallel)
**Realistic Timeline:** 19 days (~4 weeks) with 25% buffer

---

## Guaranteed Bugs in Spec

These items will cause immediate failures if implemented as-written:

1. **`user.hashed_password` does not exist** -- actual field is `password_hash`. Appears in Phase 1B (reset-password-sms endpoint, line 631) and Phase 3 (MFA disable, MFA regenerate backup codes). Fix: `user.hashed_password` -> `user.password_hash` everywhere.

2. **`ALTER TYPE smsprovider RENAME TO smsprovider_old`** -- will fail if `create_constraint=True` in the model created a CHECK constraint referencing the type. Must drop the constraint first. Additionally, the migration plan (`07-migration-plan.md`) does NOT include this enum type change at all -- it's only in `09-arkesel-sms-migration.md` which says "no migration needed" for Phase 0, contradicting the SQL in Task 7.

3. **TENANT_SCOPED_TABLES count is 91, not 55** -- conftest.py reference in migration plan is outdated.

4. **`ALTER TYPE userrole ADD VALUE` requires non-transactional context** -- Alembic's default migration runner wraps everything in a transaction. The `IF NOT EXISTS` clause helps but the statement still needs special handling.

5. **Permissions catalog is missing 20+ permissions** that exist in `ROLE_PERMISSIONS` -- teacher portal permissions (`teacher.dashboard.read`, etc.), parent permissions, applicant permissions, fine-grained exam permissions (`exams.scores.submit`, `exams.ca.enter`, `exams.ca.read`), boarding exeat approval. Custom roles based on teacher/parent/applicant will have a truncated permission ceiling.

---

## Recommendations

### 1. Start Early (Long-Lead Items)
- **Arkesel sender ID approval** -- register the sender ID with Arkesel immediately. In Ghana, custom sender IDs can take 3-7 business days for approval. Start this before any development.
- **MFA_SECRET_ENCRYPTION_KEY** -- generate and provision to all environments (dev, staging) on day 1. Do not wait until Phase 3.
- **`cryptography` package** -- add to requirements.txt immediately to verify compatibility.

### 2. Risk Mitigation Actions
- **Do not change SMSProvider enum type destructively.** Instead: keep `hubtel` and `twilio` values in the DB enum, change only the application code to use Arkesel. This eliminates the most dangerous migration risk (R1) entirely. Dead enum values in PostgreSQL are harmless.
- **Refactor auth.py authenticate() return type** before starting Phase 3. Create an `AuthResult` dataclass that can represent both normal login and MFA-pending states. This makes the Phase 3 changes cleaner and prevents the tuple-to-dict type violation (R3).
- **Batch the email uniqueness check** in bulk import. Change from N queries to 1 query. This is a simple optimization that avoids a guaranteed performance complaint.

### 3. Blockers to Resolve
- **Confirm Arkesel API key and sandbox access** before Phase 0 begins.
- **Confirm dashboard layout component type** (Server vs Client) before Phase 2 frontend work begins.
- **Audit and complete the permissions catalog** before Phase 4 begins. This is a prerequisite, not something to discover during implementation.

### 4. Technical Spikes (Investigate Before Committing)
- **Arkesel sandbox mode** -- verify that `sandbox: true` actually works and returns realistic response shapes. Some SMS providers' sandbox modes are poorly documented or broken.
- **Fernet key length/format** -- verify that `Fernet.generate_key()` produces a key that works with Pydantic Settings string loading (base64 encoding can have padding issues).
- **Phone number format in existing user data** -- query the database to understand what formats are currently stored in `users.phone`. If formats are inconsistent, the OTP service will need normalization at query time, not just at send time.

---

## Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| Arkesel API account | SMS gateway for OTP and notifications | 1-2 days | Pay-per-SMS (~GHS 0.04/SMS) |
| Arkesel sender ID registration | Custom "SIMSPlus" sender ID | 3-7 days | Included in Arkesel account |
| MFA_SECRET_ENCRYPTION_KEY in all envs | Fernet key for TOTP secret encryption | Immediate | None |
| Redis (existing) | OTP storage, rate limiting, session tracking | Already provisioned | No change |

---

## Testing Gaps Identified

The test plan (08) is reasonably comprehensive but has these gaps:

1. **No Arkesel client unit tests** -- the new `ArkeselClient` class has zero dedicated tests. Only existing SMS tests are updated with new mocks.
2. **No phone normalization tests** -- if normalization is added (recommended), it needs tests for Ghanaian number formats (0XX, +233XX, 233XX).
3. **No MFA + session timeout interaction test** -- what happens when a user's MFA pending token expires AND the session timeout fires simultaneously?
4. **No multi-tab session timeout test** -- the spec mentions multi-tab behavior but no test verifies it.
5. **No custom role + MFA interaction test** -- user with custom role that loses `self.update` permission cannot manage their own MFA. Is this intended?
6. **No load test for bulk import** -- 200 rows with email uniqueness checks, password hashing, and email queuing. What's the expected response time?
7. **No test for Arkesel insufficient balance (402)** -- this is a critical production scenario that should be tested and handled gracefully in the UI.
8. **No test for concurrent OTP requests** -- two requests hitting the rate limit check at the same millisecond could both pass. Redis WATCH/MULTI or Lua script needed for atomicity.
