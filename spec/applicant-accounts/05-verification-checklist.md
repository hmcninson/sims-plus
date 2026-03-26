# Verification Checklist

**Purpose:** End-to-end verification steps, security checks, and deployment checklist for the Applicant Accounts feature. Use this after all implementation is complete.

---

## 1. Pre-Deployment Checks

### 1.1 Database

- [ ] Migration `20260303_0200_applicant_accounts.py` runs cleanly on fresh database
- [ ] Migration downgrade works (note: `'applicant'` enum value removal is not supported in PostgreSQL -- the unused value is harmless)
- [ ] `userrole` enum contains `'applicant'` value (`SELECT unnest(enum_range(NULL::userrole))`)
- [ ] `applications.applicant_user_id` column exists (nullable UUID, FK to `users.id`, ON DELETE SET NULL)
- [ ] Partial index `ix_applications_tenant_applicant_user` exists on `(tenant_id, applicant_user_id)` WHERE `applicant_user_id IS NOT NULL`
- [ ] `admission_periods.require_applicant_account` column exists (boolean, NOT NULL, default `false`)
- [ ] FK constraint `fk_applications_applicant_user_id` exists
- [ ] Existing RLS policies on `applications` and `admission_periods` continue to work (no new policies needed -- column additions are covered by existing table-level policies)
- [ ] Global unique index on `users.email` dropped
- [ ] Composite unique index `uq_users_tenant_email` on `(tenant_id, email) WHERE deleted_at IS NULL` created
- [ ] `applications.date_of_birth` is now nullable
- [ ] `applications.gender` is now nullable
- [ ] `applications.target_class_id` is now nullable
- [ ] Existing anonymous applications (applicant_user_id=NULL) still queryable
- [ ] No changes needed to `TENANT_SCOPED_TABLES` (no new tables created -- only columns added to existing tables)
- [ ] `verify_rls.py` still passes for all 71 tables (55 existing + 16 admissions). Verify exact count against conftest.py (may be 71 or 72 depending on sprint ordering)
- [ ] Migration chain: `20260303_0100 → 20260303_0200` (no branch conflicts)

### 1.2 Backend Code

- [ ] `APPLICANT = "applicant"` added to `UserRole` enum in `backend/app/models/user.py`
- [ ] `applicant_user_id` column + `applicant_user` relationship added to `Application` model in `backend/app/models/admissions/application.py`
- [ ] `require_applicant_account` column added to `AdmissionPeriod` model in `backend/app/models/admissions/period.py`
- [ ] `ApplicantAccountService` created in `backend/app/services/admissions/applicant_service.py` with: `register`, `login`, `verify_email`, `resend_verification`, `forgot_password`, `reset_password`, `get_profile`, `update_profile`, `change_password`, `claim_application`
- [ ] `ApplicationService` updated with: `list_my_applications`, `create_draft`, `update_draft`, `submit_draft`, `get_my_application`, `get_printable_application`
- [ ] `EnrollmentService` updated with role promotion logic (`applicant` -> `parent` on enrollment)
- [ ] `applicant` role added to `ROLE_PERMISSIONS` in `backend/app/services/auth.py`:
  - `applicant.profile.read`, `applicant.profile.update`
  - `applicant.applications.read`, `applicant.applications.create`, `applicant.applications.update`, `applicant.applications.submit`, `applicant.applications.claim`
- [ ] `get_applicant_user()` dependency added to `backend/app/api/deps.py` (validates JWT `role=applicant`)
- [ ] Public paths added to BOTH `middleware/tenant.py` AND `api/deps.py`:
  - `/api/v1/admissions/public/applicant/`
- [ ] Rate limits configured in `middleware/rate_limit.py` for all applicant public endpoints:
  - Register: 3/min/IP
  - Login: 5/min/IP
  - Forgot password: 3/min/IP
  - Reset password: 3/min/IP
  - Verify email: 5/min/IP
  - Resend verification: 2/min/IP
- [ ] All 18 applicant endpoints registered in `backend/app/api/v1/router.py`
- [ ] `ApplicantAccountService` re-exported from `backend/app/services/admissions/__init__.py`
- [ ] All services use `flush()/refresh()` not `commit()`
- [ ] All services have defense-in-depth `.filter(Model.tenant_id == tenant_id)` AND `.filter(Application.applicant_user_id == user_id)` where applicable
- [ ] No `from __future__ import annotations` in endpoint files

### 1.3 Frontend Code

- [ ] Applicant types defined in `frontend/types/applicant.type.ts`
- [ ] `"applicant"` added to `UserRole` type in `frontend/types/index.ts`
- [ ] Server Actions created in `frontend/actions/applicant.action.ts`
- [ ] Register page at `frontend/app/(auth)/apply/register/page.tsx`
- [ ] Login page at `frontend/app/(auth)/apply/login/page.tsx`
- [ ] Verify email page at `frontend/app/(auth)/apply/verify-email/page.tsx`
- [ ] Forgot password page at `frontend/app/(auth)/apply/forgot-password/page.tsx`
- [ ] Reset password page at `frontend/app/(auth)/apply/reset-password/page.tsx`
- [ ] Dashboard page at `frontend/app/(auth)/apply/dashboard/page.tsx`
- [ ] Application detail page at `frontend/app/(auth)/apply/dashboard/[id]/page.tsx`
- [ ] Print view at `frontend/app/(auth)/apply/dashboard/[id]/print/page.tsx`
- [ ] Landing page (`frontend/app/(auth)/apply/page.tsx`) updated with login/register links
- [ ] Form wizard (`frontend/components/admissions/application-form-wizard.tsx`) updated with auto-save for authenticated users (2s debounce on step change)
- [ ] Apply layout (`frontend/app/(auth)/apply/layout.tsx`) updated with auth state handling
- [ ] Dashboard card component at `frontend/components/applicant/applicant-dashboard-card.tsx`
- [ ] Claim dialog component at `frontend/components/applicant/claim-application-dialog.tsx`
- [ ] Applicant cookies use distinct names: `applicant_access_token`, `applicant_refresh_token`
- [ ] Applicant cookies path-scoped to `/apply`
- [ ] Staff login does NOT clear applicant cookies
- [ ] Applicant login does NOT clear staff cookies
- [ ] `NEXT_PUBLIC_TURNSTILE_SITE_KEY` available in frontend environment (already set from admissions portal)

### 1.4 Tests

- [ ] All **54** tests pass: `pytest tests/test_applicant_accounts.py tests/test_applicant_applications.py tests/test_applicant_idor.py -v`
- [ ] IDOR prevention tests cover all authenticated endpoints (view, update, submit, upload, pay, print, list)
- [ ] Role promotion test in enrollment tests passes (`applicant` -> `parent` on enrollment)
- [ ] Claim flow tests pass (valid claim, email mismatch, already claimed, wrong tracking code)
- [ ] Existing admissions tests still pass (no regressions from model changes)
- [ ] No test pollution (each test cleans up after itself)

---

## 2. End-to-End Functional Verification

### 2.1 Registration Flow

- [ ] Visit `presec.simsplus.io/apply/register` -> form loads with school branding (logo, name, colors)
- [ ] Fill valid data (first name, last name, email, phone, password) -> submit -> "Check your email" message
- [ ] Turnstile widget renders and must be completed before submission
- [ ] Verification email sent (check Mailhog in dev at `localhost:8025`)
- [ ] Click verification link -> email verified -> redirect to `/apply/login`
- [ ] Login with new credentials -> redirect to `/apply/dashboard`
- [ ] Duplicate registration with same email -> error: "Email already registered"
- [ ] Registered user has correct `school_id` (NOT tenant_id)
- [ ] Same email can register at two different school subdomains

### 2.2 Login Flow

- [ ] Login with valid credentials -> dashboard loads
- [ ] Login with wrong password -> error message (generic: "Invalid email or password")
- [ ] Login with unverified email -> "Please verify your email" error with resend link
- [ ] 5 failed attempts -> account locked message (30-minute cooldown)
- [ ] Non-applicant role (e.g., teacher email) -> "Invalid credentials" (login endpoint rejects non-applicant roles)
- [ ] JWT contains `role=applicant`, `tenant_id`, and correct `sub` (user_id)
- [ ] Refresh token stored in HttpOnly cookie

### 2.3 Password Reset Flow

- [ ] Forgot password -> enter email -> reset email sent (check Mailhog)
- [ ] Non-existent email -> still shows "If an account exists..." message (no email enumeration)
- [ ] Click reset link -> enter new password -> success message
- [ ] Login with new password -> works
- [ ] Old password -> fails
- [ ] Reset link used twice -> error: "Invalid or expired reset token"

### 2.4 Dashboard

- [ ] Empty state shows "No applications yet" with "Start New Application" CTA
- [ ] Application cards show child name, target class, admission period, status badge
- [ ] Draft cards have "Continue" button
- [ ] Submitted/under review cards have "View Details" button
- [ ] "+ New Application" button opens period selector (only shows open periods)
- [ ] Profile menu: settings, change password, logout
- [ ] Logout clears tokens + redirects to `/apply`
- [ ] "Claim Application" button opens claim dialog

### 2.5 Draft Save & Return

- [ ] Create draft -> save partial data (e.g., Step 1 only) -> close browser
- [ ] Return -> login -> dashboard shows draft with "Continue" button
- [ ] Click "Continue" -> form loads with previously saved data at correct step
- [ ] Auto-save triggers on step change (2s debounce)
- [ ] Submit complete draft -> transitions to submitted status
- [ ] Submitted application can no longer be edited (PUT returns 409)

### 2.6 Multi-Child Applications

- [ ] Apply for Child 1 -> submit -> appears in dashboard
- [ ] Click "New Application" -> select period -> new draft created
- [ ] Guardian info pre-filled from Child 1's most recent application
- [ ] Pre-filled guardian data is editable (not locked)
- [ ] Submit Child 2 -> dashboard shows both children with separate tracking codes
- [ ] Each application has independent status tracking

### 2.7 Claim Flow

- [ ] Previously submitted anonymous application exists (no `applicant_user_id`)
- [ ] Click "Claim Application" -> enter tracking code
- [ ] Guardian email on application matches account email -> application appears in dashboard
- [ ] Wrong email (no guardian email match) -> error: "Could not verify ownership"
- [ ] Already claimed application (has `applicant_user_id`) -> error: "Application already linked to an account"
- [ ] Invalid tracking code -> error: "Application not found"
- [ ] Claimed application now shows in dashboard with full access (view, print)

### 2.8 Print View

- [ ] Click "Print" on submitted/accepted application
- [ ] Print layout loads: school letterhead (logo + name) + all application data
- [ ] Print view includes: child info, guardian details, documents list, payment status, tracking code
- [ ] Browser print dialog opens (or print button triggers `window.print()`)
- [ ] Printable version is clean (no navigation, no sidebar, no action buttons)

### 2.9 Role Promotion

- [ ] Applicant has submitted + accepted application
- [ ] Admin enrolls applicant's child -> student record created
- [ ] Applicant user role changed from `'applicant'` to `'parent'`
- [ ] After enrollment, applicant's existing JWT tokens are revoked
- [ ] Applicant must re-login to access parent portal
- [ ] New JWT contains role=parent with parent.* permissions
- [ ] Applicant can now access `/parent/dashboard` (parent portal)
- [ ] Login credentials unchanged (same email + password)
- [ ] If applicant already has `'parent'` role (from previous child enrollment), no role change occurs

---

## 3. Security Verification

### 3.1 Authentication

- [ ] Unverified email cannot login (returns 403 with verification prompt)
- [ ] Account lockout after 5 failed attempts (30-minute cooldown)
- [ ] Password meets strength requirements (8+ chars, uppercase, lowercase, number, special char)
- [ ] JWT contains `role='applicant'` and correct `tenant_id`
- [ ] Refresh token rotation works (old refresh token blacklisted after rotation)
- [ ] Logout blacklists both access and refresh tokens
- [ ] Registration requires valid Turnstile token
- [ ] Turnstile fails CLOSED on Cloudflare outage (does not silently pass)

### 3.2 IDOR Prevention

- [ ] User A cannot view User B's application (`GET /applicant/applications/{id}`)
- [ ] User A cannot update User B's draft (`PUT /applicant/applications/{id}`)
- [ ] User A cannot submit User B's draft (`POST /applicant/applications/{id}/submit`)
- [ ] User A cannot upload documents to User B's application (`POST /applicant/applications/{id}/documents`)
- [ ] User A cannot initiate payment for User B's application (`POST /applicant/applications/{id}/pay`)
- [ ] User A cannot print User B's application (`GET /applicant/applications/{id}/print`)
- [ ] List endpoint only returns own applications (filtered by `applicant_user_id` from JWT, never from request params)
- [ ] Service layer extracts `user_id` from JWT -- never from request body or URL parameters
- [ ] Profile endpoints only return/modify the authenticated user's own profile
- [ ] Claim errors are generic (same message for NOT_FOUND, EMAIL_MISMATCH, ALREADY_CLAIMED)

### 3.3 Role Isolation

- [ ] Applicant cannot access admin endpoints (`/api/v1/admissions/*` non-public routes)
- [ ] Applicant cannot access teacher endpoints (`/api/v1/exams/*`, `/api/v1/attendance/*`, etc.)
- [ ] Applicant cannot access parent endpoints (`/api/v1/parent/*`) until promoted
- [ ] Applicant cannot access student/staff management endpoints
- [ ] Staff (teacher, school_admin) cannot access applicant endpoints (`/api/v1/admissions/applicant/*`)
- [ ] `get_applicant_user()` dependency rejects non-applicant roles with 403

### 3.4 Cross-Tenant

- [ ] RLS prevents cross-tenant data access on `users` and `applications` tables
- [ ] Tenant A applicant cannot see Tenant B's admission periods
- [ ] Tenant A applicant cannot apply to Tenant B's admission period
- [ ] Tenant A applicant cannot claim Tenant B's application
- [ ] JWT `tenant_id` validated against request tenant (middleware-level + `ValidatedUser` dependency)

### 3.5 Rate Limiting

- [ ] Registration: 3 requests/min/IP
- [ ] Login: 5 requests/min/IP
- [ ] Forgot password: 3 requests/min/IP
- [ ] Reset password: 3 requests/min/IP
- [ ] Resend verification: 2 requests/min/IP
- [ ] Verify email: 5 requests/min/IP
- [ ] Authenticated endpoints: 100 requests/min (standard default rate)
- [ ] Rate limit responses return `429 Too Many Requests` with `Retry-After` header
- [ ] Login: adaptive CAPTCHA after 3 failed attempts
- [ ] Resend verification: requires Turnstile token

### 3.6 Turnstile

- [ ] Registration endpoint requires valid Turnstile token in request body
- [ ] Invalid Turnstile token -> 400 error (not silent pass)
- [ ] Turnstile fails CLOSED on Cloudflare outage (rejects submission)
- [ ] Turnstile validation uses `TURNSTILE_SECRET_KEY` from backend config

---

## 4. Performance Verification

- [ ] Registration completes in <2s (includes Turnstile verification + Argon2id hashing + email send)
- [ ] Login completes in <1s (includes Argon2id verification + JWT issuance)
- [ ] Dashboard loads in <2s (with 10 applications, eager-loaded statuses)
- [ ] Draft save (PUT) completes in <500ms
- [ ] Application list with 50 applications loads in <1s (paginated)
- [ ] Print view loads in <3s (all relations eager-loaded: guardians, documents, payments, status history)
- [ ] Claim flow completes in <1s (tracking code lookup + email match + link)
- [ ] Profile GET/PUT completes in <500ms
- [ ] Partial index `ix_applications_tenant_applicant_user` used for `list_my_applications` queries (verify with `EXPLAIN ANALYZE`)

---

## 5. Deployment Checklist

### 5.1 Environment Variables

```env
# No NEW environment variables required.
# Reuses existing variables from the admissions portal:
# TURNSTILE_SECRET_KEY (already set for admissions portal)
# TURNSTILE_SITE_KEY (already set)
# NEXT_PUBLIC_TURNSTILE_SITE_KEY (already set)
#
# Reuses existing auth infrastructure:
# SECRET_KEY, SMTP_HOST, SMTP_PORT, etc.
```

### 5.2 Dependencies

```bash
# No new Python packages required.
# Reuses existing:
#   - python-jose (JWT)
#   - argon2-cffi (password hashing)
#   - pydantic (validation)
#   All already in requirements.txt
```

### 5.3 Database Migration

```bash
# Run on staging first
alembic upgrade head

# Verify migration applied correctly
python -c "
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://...')
with engine.connect() as conn:
    # 1. Check enum value exists
    result = conn.execute(text(\"SELECT 'applicant' = ANY(enum_range(NULL::userrole)::text[])\"))
    assert result.scalar(), 'applicant role not in userrole enum'

    # 2. Check applicant_user_id column exists
    result = conn.execute(text(
        \"SELECT column_name FROM information_schema.columns \"
        \"WHERE table_name='applications' AND column_name='applicant_user_id'\"
    ))
    assert result.fetchone(), 'applicant_user_id column missing from applications'

    # 3. Check partial index exists
    result = conn.execute(text(
        \"SELECT indexname FROM pg_indexes \"
        \"WHERE tablename='applications' AND indexname='ix_applications_tenant_applicant_user'\"
    ))
    assert result.fetchone(), 'partial index ix_applications_tenant_applicant_user missing'

    # 4. Check require_applicant_account column exists
    result = conn.execute(text(
        \"SELECT column_name FROM information_schema.columns \"
        \"WHERE table_name='admission_periods' AND column_name='require_applicant_account'\"
    ))
    assert result.fetchone(), 'require_applicant_account column missing from admission_periods'

    # 5. Check FK constraint exists
    result = conn.execute(text(
        \"SELECT constraint_name FROM information_schema.table_constraints \"
        \"WHERE constraint_name='fk_applications_applicant_user_id'\"
    ))
    assert result.fetchone(), 'FK constraint fk_applications_applicant_user_id missing'

    # 6. Check RLS still active
    result = conn.execute(text(
        \"SELECT tablename, rowsecurity FROM pg_tables \"
        \"WHERE tablename IN ('applications', 'admission_periods') AND rowsecurity = true\"
    ))
    rows = result.fetchall()
    assert len(rows) == 2, f'RLS not active on both tables (found {len(rows)})'

    print('All verification checks passed!')
"

# Verify RLS coverage
python scripts/verify_rls.py

# Run on production
alembic upgrade head
```

### 5.4 Docker Rebuild

```bash
# No new dependencies -- no Docker image rebuild needed.
# Just restart to pick up code changes:
docker compose restart backend
```

### 5.5 Post-Deployment Smoke Test

1. Visit `presec.simsplus.io/apply/register` -> registration form loads with school branding
2. Register with test email -> verify email via Mailhog -> login -> dashboard loads
3. Create draft application -> save partial data -> logout -> login -> draft visible in dashboard
4. Submit complete application -> appears with tracking code and "submitted" status
5. Claim a previously anonymous application -> appears in dashboard
6. Run `python scripts/verify_rls.py` -> all tables passing (verify exact count against conftest.py -- may be 71 or 72 depending on sprint ordering)

---

## 6. Backward Compatibility

- [ ] Existing anonymous applications (`applicant_user_id=NULL`) continue to work -- all admin management flows unchanged
- [ ] Public submission endpoint (`POST /api/v1/admissions/public/applications`) still works without authentication
- [ ] Admin application management endpoints unchanged (list, review, decision, enrollment)
- [ ] Existing admission periods default to `require_applicant_account=false` (no behavioral change)
- [ ] Existing admissions test suite passes without modification (new columns are nullable/have defaults)
- [ ] No changes to existing `TENANT_SCOPED_TABLES` or RLS policies
- [ ] Migration is additive only -- no existing columns modified, no existing constraints altered (except nullable changes below)
- [ ] `users.email` unique constraint change: existing users with unique emails are unaffected
- [ ] `applications` nullable columns: existing submitted applications have non-null values, unaffected
- [ ] Draft applications with NULL date_of_birth/gender/target_class_id work correctly
- [ ] Anonymous status check endpoint (`GET /api/v1/admissions/public/applications/{tracking_code}/status`) unchanged

---

## 7. Rollback Plan

If issues are found after deployment:

1. **Database rollback:**
   ```bash
   alembic downgrade 20260303_0100  # Roll back to pre-applicant-accounts migration
   ```
   This drops:
   - `applications.applicant_user_id` column (and FK constraint)
   - `ix_applications_tenant_applicant_user` partial index
   - `admission_periods.require_applicant_account` column

   **Note:** The `'applicant'` value CANNOT be removed from the `userrole` PostgreSQL enum. This is a known PostgreSQL limitation (`ALTER TYPE ... DROP VALUE` does not exist). The unused enum value is harmless and has no side effects.

2. **Code rollback:**
   ```bash
   git revert <commit-hash>  # Revert the applicant accounts PR
   ```

3. **Frontend rollback:**
   - `/apply/register`, `/apply/login`, `/apply/dashboard` routes return 404
   - Landing page reverts to anonymous-only flow
   - No impact on admin-facing admissions pages

4. **Impact assessment:**
   - Any users who registered as applicants will remain in the `users` table with `role='applicant'`
   - Their accounts become inaccessible (login endpoint removed), but user records persist
   - Applications previously linked via `applicant_user_id` revert to anonymous (column dropped)
   - No data loss for existing admissions data (applications, guardians, documents, payments all preserved)
   - If any applicant was promoted to `parent` role before rollback, they retain `parent` role (no regression)

5. **Data preservation (optional, before rollback):**
   ```sql
   -- Export applicant user accounts
   COPY (
       SELECT id, email, first_name, last_name, role, created_at
       FROM users
       WHERE role = 'applicant'
   ) TO '/tmp/applicant_users_backup.csv' CSV HEADER;

   -- Export application-to-user links
   COPY (
       SELECT id, tracking_code, applicant_user_id
       FROM applications
       WHERE applicant_user_id IS NOT NULL
   ) TO '/tmp/application_user_links_backup.csv' CSV HEADER;
   ```
