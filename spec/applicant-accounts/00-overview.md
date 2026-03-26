# Applicant Accounts — Overview & Architecture

**Module:** Applicant Accounts (extension to Admissions Portal)
**Phase:** 3 (Sprints 19-24)
**Complexity:** 5/10
**Author:** SIMS Plus Team
**Date:** 2026-03-02
**Status:** Implementation Plan
**Prerequisite:** Admissions Portal (see `spec/admissions-portal/`)

---

## 1. Executive Summary

The Admissions Portal currently operates as an **anonymous submission model** — prospective parents visit `{school}.simsplus.io/apply`, fill out a form, and receive a tracking code. There is no user account, no login, no way to save progress and return, and no dashboard to manage multiple children's applications.

**Applicant Accounts** adds authenticated access for prospective parents:

```
Register → Verify Email → Login → Dashboard → Apply for Child(ren) → Save Drafts → Track Status → Print History
```

### Key Capabilities

| Capability | Description |
|-----------|-------------|
| **Register/Login** | Applicants create accounts (email + password), verify email, then log in |
| **Multi-Child Dashboard** | View all applications (drafts, submitted, decisions) across multiple children |
| **Save & Return** | Auto-save draft on each wizard step, return anytime to continue |
| **Print/Export** | Server-rendered printable view of any application |
| **Claim Existing** | Link previously anonymous applications to new account via tracking code + guardian email match |
| **Role Promotion** | Seamless transition from `applicant` → `parent` role when child is enrolled |

### Scope

| In Scope | Out of Scope |
|----------|-------------|
| Applicant registration with email verification | Social login (Google, Facebook) |
| Applicant login (separate from staff login) | Two-factor authentication for applicants |
| Applicant dashboard (my applications) | Applicant-to-applicant messaging |
| Save draft and resume later | Offline draft support |
| Print application history | PDF generation of applications (Phase 4) |
| Claim anonymous applications | Bulk claim (multiple tracking codes) |
| Guardian info pre-fill for 2nd+ child | Custom applicant profile fields |
| Role promotion on enrollment | Applicant document vault |
| Per-period account requirement toggle | Shared family accounts (multiple parents) |

### Effort Estimate

| Metric | Value |
|--------|-------|
| New database columns | 2 (on existing tables) |
| New enum values | 1 (`applicant` in `userrole`) |
| New backend files | ~9 |
| New frontend files | ~12 |
| Existing files to modify | ~13 |
| Pydantic schemas | ~18 |
| API endpoints | ~18 |
| Test cases | 54+ |
| Estimated dev-days (raw) | 17-19 |
| Estimated dev-days (with 30% buffer) | 21-24 |

---

## 2. Architecture Decisions

### Decision 1: Reuse Existing `UserRole` Enum — Add `APPLICANT` Value

Rather than creating a separate applicant identity system, we add `'applicant'` as a new value to the existing `userrole` PostgreSQL enum. This reuses the entire auth infrastructure: JWT issuance, refresh token rotation, Argon2id password hashing, account lockout, token blacklisting, email verification, and password reset — all without duplicating code.

**Trade-off:** Applicants share the `users` table with staff/admins, but RLS and permission checks ensure complete isolation. The `applicant` role has its own minimal permission set.

### Decision 2: Nullable `applicant_user_id` FK on `applications`

A new nullable `applicant_user_id` column on the existing `applications` table links applications to user accounts. Nullable because:
- Existing anonymous applications (submitted before this feature) have no user account
- Schools can toggle whether accounts are required per admission period
- The anonymous flow remains functional for schools that prefer it

**No unique constraint** on `(tenant_id, applicant_user_id)` — one parent can own many applications (multi-child support).

### Decision 3: Per-Period Account Requirement Toggle

A new `require_applicant_account` boolean on `admission_periods` gives schools per-period flexibility:
- `false` (default): Anonymous submissions allowed (backward compatible)
- `true`: Account required — the public form redirects to register/login before allowing submission

This avoids a global setting that forces all schools to adopt accounts simultaneously.

### Decision 4: Separate Login Path (`/apply/login`)

Applicants log in at `/apply/login`, not the staff `/auth/login` page. The login endpoint rejects non-applicant roles, preventing staff from accidentally accessing the applicant portal and vice versa. The UX is tailored: school branding, "Create Account" link, "Check Application Status" link.

### Decision 5: Server-Side Draft Persistence (Not localStorage)

Draft applications are saved server-side via PUT requests. The `Application` model already supports `DRAFT` status. This means:
- Drafts survive across devices and browser changes
- No data loss on browser cache clear
- The existing `ApplicationService` handles persistence
- Auto-save triggers on each wizard step (debounced 2s)

### Decision 6: Claim Flow via Tracking Code + Guardian Email Match

When a parent who previously submitted anonymously creates an account, they can "claim" their applications by providing:
1. The tracking code (proves they received the confirmation)
2. Their email must match a guardian email on the application (proves they're the applicant)

This prevents unauthorized claiming while being simple enough for real users.

### Decision 7: Role Promotion `applicant` → `parent` on Enrollment

When an applicant's child is enrolled (application → student conversion), the `EnrollmentService` promotes the user's role from `applicant` to `parent`. The user retains the same account, login credentials, and login history — they seamlessly gain access to the parent portal. If the user already has a `parent` role (from a previous child's enrollment), no change is needed.

### Decision 8: Guardian Info Pre-Fill for Multi-Child

When an authenticated applicant starts a new application (2nd, 3rd child), the guardian section is pre-populated from their most recent application. This is a frontend convenience — the data is fetched from the API and used as default form values. The parent can modify the pre-filled data for each application.

### Decision 9: Separate Cookie Namespace for Applicant Sessions

Applicant sessions use distinct cookie names (`applicant_access_token`, `applicant_refresh_token`) path-scoped to `/apply`. This prevents session conflicts when a user has both a staff account and an applicant account in the same browser. Staff cookies (`access_token`, `refresh_token`) remain on path `/` and are unaffected by applicant login/logout.

---

## 3. Data Model Changes

### 3.1 Enum Changes

| Change | Details |
|--------|---------|
| Add `'applicant'` to `userrole` PostgreSQL enum | `ALTER TYPE userrole ADD VALUE 'applicant'` |

**Python enum update:**
```python
# backend/app/models/user.py — UserRole class
class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    CHAIN_ADMIN = "chain_admin"
    SCHOOL_ADMIN = "school_admin"
    ACADEMIC_HEAD = "academic_head"
    FINANCE_OFFICER = "finance_officer"
    TEACHER = "teacher"
    HOUSE_PARENT = "house_parent"
    PARENT = "parent"
    STUDENT = "student"
    APPLICANT = "applicant"  # NEW
```

### 3.2 Table Modifications

#### `applications` — Add `applicant_user_id` Column

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| applicant_user_id | UUID | FK→users.id, NULLABLE, ON DELETE SET NULL | Account owner (null for anonymous) |

**Index:** `ix_applications_tenant_applicant_user` — partial index on `(tenant_id, applicant_user_id)` WHERE `applicant_user_id IS NOT NULL`

**No unique constraint** — one user can own many applications (multi-child).

#### `admission_periods` — Add `require_applicant_account` Column

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| require_applicant_account | BOOLEAN | NOT NULL, DEFAULT false | Whether account is required to apply |

### 3.3 Additional Migration Items

| Change | Details |
|--------|---------|
| Drop global unique on `users.email` | Replace with composite unique `(tenant_id, email) WHERE deleted_at IS NULL` — allows same email across tenants |
| ALTER `applications.date_of_birth` to nullable | Required for draft save (partial data allowed before submission) |
| ALTER `applications.gender` to nullable | Required for draft save |
| ALTER `applications.target_class_id` to nullable | Required for draft save |

### 3.4 Entity Relationship Update

```
users (role=applicant) ──┐
                         │  applicant_user_id (nullable, many-to-one)
                         ▼
                    applications ──→ (existing relations unchanged)
                         │
admission_periods ───────┘
  require_applicant_account: bool
```

---

## 4. API Overview

### 4.1 Public Endpoints (6 endpoints, unauthenticated)

Base: `/api/v1/admissions/public/applicant`

| Method | Path | Purpose | Rate Limit |
|--------|------|---------|------------|
| POST | `/register` | Create applicant account | 3/min/IP |
| POST | `/login` | Applicant login (returns JWT) | 5/min/IP |
| POST | `/verify-email` | Verify email with token | 5/min/IP |
| POST | `/forgot-password` | Request password reset email | 3/min/IP |
| POST | `/reset-password` | Reset password with token | 3/min/IP |
| POST | `/resend-verification` | Resend email verification | 2/min/IP |

### 4.2 Authenticated Endpoints (12 endpoints, JWT with role=applicant)

Base: `/api/v1/admissions/applicant`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/profile` | Get applicant profile |
| PUT | `/profile` | Update applicant profile (name, phone) |
| PUT | `/profile/password` | Change password |
| GET | `/applications` | List my applications (paginated, filterable) |
| GET | `/applications/{id}` | Get application detail (IDOR-safe: must be owner) |
| POST | `/applications` | Create new draft application |
| PUT | `/applications/{id}` | Update draft application (save progress) |
| POST | `/applications/{id}/submit` | Submit draft application |
| POST | `/applications/{id}/documents` | Upload document to draft |
| POST | `/applications/{id}/pay` | Initiate payment for application |
| GET | `/applications/{id}/print` | Get printable application view |
| POST | `/applications/claim` | Claim anonymous application by tracking code |

### 4.3 Permissions

| Role | Permissions |
|------|------------|
| `applicant` | `applicant.profile.read`, `applicant.profile.update`, `applicant.applications.read`, `applicant.applications.create`, `applicant.applications.update`, `applicant.applications.submit`, `applicant.applications.claim` |

### 4.4 Modified Existing Endpoints

| Endpoint | Change |
|----------|--------|
| `POST /api/v1/admissions/public/applications` | Accept optional `applicant_user_id` from JWT when authenticated |
| `GET /api/v1/admissions/public/periods` | Include `require_applicant_account` field |
| `POST /api/v1/admissions/enrollment/{id}` | Promote applicant user role to `parent` on enrollment |

---

## 5. Security Model

### 5.1 Authentication

| Concern | Mitigation |
|---------|-----------|
| Applicant registration spam | Cloudflare Turnstile on register form + rate limit (3/min/IP) |
| Credential stuffing | Account lockout after 5 failed attempts (30-min cooldown) — reuses existing `AuthService` logic |
| Email verification bypass | JWT not issued until email verified; unverified accounts cannot log in |
| Password strength | Same policy as staff accounts (8+ chars, uppercase, lowercase, number, special char) |
| Token security | 15-min access token, 7-day refresh in HttpOnly cookie — same as staff |

### 5.2 Authorization (IDOR Prevention)

| Concern | Mitigation |
|---------|-----------|
| Applicant accessing another applicant's data | All "my applications" queries filter by `applicant_user_id` from JWT — never from request body/params |
| Applicant accessing staff endpoints | Role check rejects `applicant` role on all non-applicant endpoints |
| Staff accessing applicant endpoints | Applicant endpoints require `role=applicant` — staff roles rejected |
| Cross-tenant access | RLS on `users` and `applications` tables enforces tenant isolation |
| Stale JWT after role promotion | Token revocation forces re-login; new JWT contains updated role |

### 5.3 Claim Flow Security

| Concern | Mitigation |
|---------|-----------|
| Unauthorized claiming | Requires BOTH tracking code AND matching guardian email on the application |
| Brute-force tracking codes | 384 bits entropy (token_urlsafe(48)) — computationally infeasible |
| Claiming already-owned apps | Reject if `applicant_user_id` is already set (already claimed or was created with account) |
| Rate limit on claim endpoint | 5/min/IP — prevents enumeration |
| Information leakage via error messages | All claim failures return identical generic error (anti-enumeration) |

### 5.4 Data Isolation

| Layer | Protection |
|-------|-----------|
| Database | RLS on `users` and `applications` — tenant_id enforced |
| Service | Defense-in-depth: all queries include `.filter(Application.tenant_id == tenant_id)` AND `.filter(Application.applicant_user_id == user_id)` |
| Endpoint | `ValidatedUser` dependency validates JWT tenant matches request tenant |
| Frontend | Server Actions pass JWT automatically — no client-side tenant manipulation |

---

## 6. User Flows

### 6.1 New Applicant (Account Required)

```
1. Parent visits presec.simsplus.io/apply
2. Sees admission periods — one has "Account Required" badge
3. Clicks "Apply Now" → redirected to /apply/register
4. Fills: first name, last name, email, phone, password
5. Clicks "Create Account" → email sent with verification link
6. Clicks verification link → email verified → redirected to /apply/login
7. Logs in → redirected to /apply/dashboard (empty)
8. Clicks "New Application" → form wizard loads
9. Fills Step 1 (child info) → auto-saves draft
10. Takes a break → closes browser
11. Returns next day → /apply/login → dashboard shows draft
12. Clicks "Continue" → resumes at Step 2
13. Completes all steps → submits → pays (if required)
14. Dashboard now shows: "Kofi Mensah — Class 1 — Submitted"
15. Clicks "New Application" for 2nd child
16. Guardian info pre-filled from Kofi's application
17. Submits 2nd application → dashboard shows both children
```

### 6.2 Claim Anonymous Application

```
1. Parent previously submitted anonymously → has tracking code
2. Parent creates account (or already has one)
3. On dashboard, clicks "Claim Application"
4. Enters tracking code
5. System checks: guardian email on application matches account email
6. Match → application linked to account → appears in dashboard
```

### 6.3 Role Promotion on Enrollment

```
1. Admin enrolls applicant's child → student record created
2. EnrollmentService checks: application.applicant_user_id exists?
3. Yes → look up the User record
4. User role is 'applicant' → promote to 'parent'
5. User's existing JWT tokens are revoked (blacklisted)
6. User must re-login to get new JWT with role=parent and parent.* permissions
7. User can now access parent portal (/parent/dashboard)
8. Login credentials unchanged
```

---

## 7. File Organization

### Backend (~9 new files, ~9 modified files)

```
backend/
├── app/
│   ├── models/
│   │   ├── user.py                      # MODIFY: Add APPLICANT to UserRole
│   │   └── admissions/
│   │       ├── application.py           # MODIFY: Add applicant_user_id column + relationship
│   │       └── period.py               # MODIFY: Add require_applicant_account column
│   ├── schemas/
│   │   └── applicant.py               # NEW: ~18 schemas
│   ├── services/
│   │   ├── auth.py                    # MODIFY: Add applicant permissions + role-specific login
│   │   └── admissions/
│   │       ├── applicant_service.py   # NEW: registration, profile, claim flow
│   │       ├── application_service.py # MODIFY: accept applicant_user_id, list_my_applications
│   │       ├── enrollment_service.py  # MODIFY: role promotion logic
│   │       └── __init__.py            # MODIFY: re-export ApplicantAccountService
│   ├── api/v1/endpoints/admissions/
│   │   ├── applicant_public.py        # NEW: register, login, verify, forgot/reset password
│   │   ├── applicant.py              # NEW: profile, my applications, drafts, claim
│   │   └── __init__.py               # MODIFY: register new routers
│   ├── api/
│   │   ├── deps.py                   # MODIFY: add get_applicant_user dependency + public paths
│   │   └── v1/router.py             # MODIFY: register applicant routers
│   └── middleware/
│       ├── tenant.py                 # MODIFY: add public path prefixes
│       └── rate_limit.py            # MODIFY: add rate limits for applicant endpoints
├── alembic/versions/
│   └── 20260303_0200_applicant_accounts.py  # NEW: migration
└── tests/
    ├── test_applicant_accounts.py    # NEW: registration, login, profile tests
    ├── test_applicant_applications.py # NEW: my apps, drafts, claim tests
    └── test_applicant_idor.py        # NEW: IDOR prevention tests
```

### Frontend (~12 new files, ~4 modified files)

```
frontend/
├── app/(auth)/apply/
│   ├── register/page.tsx             # NEW: registration form
│   ├── login/page.tsx                # NEW: applicant login
│   ├── verify-email/page.tsx         # NEW: email verification
│   ├── forgot-password/page.tsx      # NEW: forgot password form
│   ├── reset-password/page.tsx       # NEW: reset password form
│   ├── dashboard/page.tsx            # NEW: my applications dashboard
│   ├── dashboard/[id]/page.tsx       # NEW: application detail view
│   ├── dashboard/[id]/print/page.tsx # NEW: printable application view
│   ├── layout.tsx                    # MODIFY: add auth state handling
│   └── page.tsx                      # MODIFY: add login/register links
├── actions/
│   └── applicant.action.ts           # NEW: all applicant Server Actions
├── types/
│   └── applicant.type.ts             # NEW: TypeScript types
├── components/admissions/
│   └── application-form-wizard.tsx    # MODIFY: add auto-save for authenticated users
└── components/applicant/
    ├── applicant-dashboard-card.tsx   # NEW: application card for dashboard
    └── claim-application-dialog.tsx   # NEW: claim dialog
```

### Existing Files to Modify (12)

| File | Change |
|------|--------|
| `backend/app/models/user.py` | Add `APPLICANT` to `UserRole` |
| `backend/app/models/admissions/application.py` | Add `applicant_user_id` column + relationship |
| `backend/app/models/admissions/period.py` | Add `require_applicant_account` column |
| `backend/app/services/auth.py` | Add applicant permissions to `ROLE_PERMISSIONS` |
| `backend/app/services/admissions/application_service.py` | Add `applicant_user_id` param + `list_my_applications()` |
| `backend/app/services/admissions/enrollment_service.py` | Add role promotion logic |
| `backend/app/services/admissions/__init__.py` | Re-export `ApplicantAccountService` |
| `backend/app/api/deps.py` | Add `get_applicant_user()` dependency + public paths |
| `backend/app/api/v1/router.py` | Register applicant routers |
| `backend/app/api/v1/endpoints/admissions/__init__.py` | Include applicant routers |
| `backend/app/middleware/tenant.py` | Add public path prefixes |
| `backend/app/middleware/rate_limit.py` | Add rate limits |

---

## 8. Implementation Tracks

### Track A: Backend Core (3-4 days)

| Step | Task | Files | Est. |
|------|------|-------|------|
| A1 | Add `APPLICANT` to UserRole enum | `models/user.py` | 0.25d |
| A2 | Add `applicant_user_id` to Application model | `models/admissions/application.py` | 0.25d |
| A3 | Add `require_applicant_account` to AdmissionPeriod | `models/admissions/period.py` | 0.1d |
| A4 | Create Alembic migration | `alembic/versions/20260303_0200_...py` | 0.5d |
| A5 | Create `ApplicantAccountService` | `services/admissions/applicant_service.py` | 1d |
| A6 | Modify `ApplicationService` (accept user_id, list_my_apps) | `services/admissions/application_service.py` | 0.5d |
| A7 | Modify `EnrollmentService` (role promotion) | `services/admissions/enrollment_service.py` | 0.25d |
| A8 | Update `ROLE_PERMISSIONS` in auth service | `services/auth.py` | 0.1d |

### Track B: Backend Endpoints (2-3 days)

| Step | Task | Files | Est. |
|------|------|-------|------|
| B1 | Create Pydantic schemas | `schemas/applicant.py` | 0.5d |
| B2 | Create public endpoints (register, login, verify, etc.) | `api/v1/endpoints/admissions/applicant_public.py` | 1d |
| B3 | Create authenticated endpoints (profile, my apps, etc.) | `api/v1/endpoints/admissions/applicant.py` | 1d |
| B4 | Add `get_applicant_user()` dependency | `api/deps.py` | 0.25d |
| B5 | Update middleware (public paths, rate limits) | `middleware/tenant.py`, `middleware/rate_limit.py` | 0.25d |

### Track C: Frontend (4-5 days)

| Step | Task | Files | Est. |
|------|------|-------|------|
| C1 | Create TypeScript types | `types/applicant.type.ts` | 0.25d |
| C2 | Create Server Actions | `actions/applicant.action.ts` | 0.5d |
| C3 | Create register page | `app/(auth)/apply/register/page.tsx` | 0.5d |
| C4 | Create login page | `app/(auth)/apply/login/page.tsx` | 0.5d |
| C5 | Create verify-email page | `app/(auth)/apply/verify-email/page.tsx` | 0.25d |
| C6 | Create forgot/reset password pages | `app/(auth)/apply/forgot-password/`, `reset-password/` | 0.5d |
| C7 | Create applicant dashboard | `app/(auth)/apply/dashboard/page.tsx` | 1d |
| C8 | Create application detail page | `app/(auth)/apply/dashboard/[id]/page.tsx` | 0.5d |
| C9 | Create print view page | `app/(auth)/apply/dashboard/[id]/print/page.tsx` | 0.5d |
| C10 | Create dashboard card + claim dialog components | `components/applicant/` | 0.5d |
| C11 | Modify landing page (add login/register links) | `app/(auth)/apply/page.tsx` | 0.25d |
| C12 | Modify form wizard (add auto-save for auth users) | `components/admissions/application-form-wizard.tsx` | 0.5d |
| C13 | Modify apply layout (auth state handling) | `app/(auth)/apply/layout.tsx` | 0.25d |

### Track D: Testing (2-3 days)

| Step | Task | Files | Est. |
|------|------|-------|------|
| D1 | Applicant account tests (register, login, verify, reset) | `tests/test_applicant_accounts.py` | 1d |
| D2 | My applications tests (CRUD, submit, list, claim) | `tests/test_applicant_applications.py` | 1d |
| D3 | IDOR prevention tests | `tests/test_applicant_idor.py` | 0.5d |
| D4 | Update existing tests (conftest, verify_rls) | `tests/conftest.py`, `scripts/verify_rls.py` | 0.25d |

### Dependency Graph

```
Track A (Core) ──────────────────────→ Track B (Endpoints) ──→ Track D (Testing)
    │                                       │
    │  C1 (types) can start early           │
    ▼                                       ▼
Track C (Frontend) ────────────────────────────────────────→ Track D (Testing)
```

**Critical path:** A1 → A4 → A5 → A6 → B1 → B2 → B3 → D1

**Total: 17-19 developer days (21-24 with 30% buffer)**
