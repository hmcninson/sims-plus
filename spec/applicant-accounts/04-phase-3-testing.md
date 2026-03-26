# Phase 3: Testing

**Module:** Applicant Accounts (extension to Admissions Portal)
**Agent:** Tester
**Depends on:** All backend code (services, endpoints, schemas) must be complete
**Produces:** 54 test cases across 3 new test files + 3 additions to existing file, test fixtures

---

## Task List

| # | Task | File | Tests | Est. |
|---|------|------|-------|------|
| 4.1 | Applicant account tests | `test_applicant_accounts.py` | 17 | 1d |
| 4.2 | Applicant application tests | `test_applicant_applications.py` | 21 | 1.5d |
| 4.3 | IDOR prevention tests | `test_applicant_idor.py` | 13 | 1d |
| 4.4 | Update enrollment conversion tests | `test_enrollment_conversion.py` | +3 | 0.25d |
| 4.5 | Update conftest.py (fixture only) | `tests/conftest.py` | - | 0.1d |

---

## Test Infrastructure Updates

### 4.5 Update `backend/tests/conftest.py`

No new tables to add to `TENANT_SCOPED_TABLES`. This feature adds columns to existing tables (`applications.applicant_user_id`, `admission_periods.require_applicant_account`) and a new value to the `userrole` PostgreSQL enum. The existing 71 entries (55 core + 16 admissions) remain unchanged.

### Add Applicant Test Fixture

Add to `conftest.py` (or `tests/admissions_fixtures.py` if it exists):

```python
@pytest_asyncio.fixture
async def applicant_user_id(admin_session, tenant_a_id, school_a_id):
    """Create a test applicant user for tenant A."""
    user_id = uuid4()
    password_hash = "$argon2id$v=19$m=65536,t=3,p=4$..."  # pre-hashed "Test1234!"
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, school_id, email, password_hash,
                first_name, last_name, phone, role, status,
                email_verified, mfa_enabled, failed_login_attempts,
                timezone, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :email, :password_hash,
                :first_name, :last_name, :phone, :role, :status,
                :email_verified, :mfa_enabled, :failed_login_attempts,
                :timezone, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_id),
            "tid": str(tenant_a_id),
            "sid": str(school_a_id),
            "email": "applicant@test.com",
            "password_hash": password_hash,
            "first_name": "Test",
            "last_name": "Applicant",
            "phone": "+233241234567",
            "role": "applicant",
            "status": "active",
            "email_verified": True,
            "mfa_enabled": False,
            "failed_login_attempts": 0,
            "timezone": "Africa/Accra",
        },
    )
    await admin_session.commit()
    return user_id
```

### Why No `TENANT_SCOPED_TABLES` Update

| Check | Status | Reason |
|-------|--------|--------|
| `TENANT_SCOPED_TABLES` in `conftest.py` | No change | No new tables created -- only new columns on `applications` and `admission_periods` |
| `verify_rls.py` | No change | RLS already covers `applications` and `admission_periods` from the `20260303_0100` migration |
| `models/__init__.py` | No change | No new model classes (only new columns on existing models) |
| `admissions/__init__.py` | May need `ApplicantAccountService` re-export | If `ApplicantAccountService` is added to the admissions service package |

---

## 4.1 Applicant Account Tests

**File:** `backend/tests/test_applicant_accounts.py`

```python
"""
Tests for ApplicantAccountService.

Covers: registration, Turnstile verification, email verification,
login (success, unverified, wrong password, lockout, role rejection),
password reset, profile CRUD. Uses two-engine pattern.
"""

# --- Helpers ---

async def _seed_applicant_prereqs(admin_session, tenant_id):
    """Seed school and return dict with IDs needed for applicant registration.

    Returns dict with: school_id, tenant_id.
    Applicant user creation happens via the service under test.
    """
    school_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School-{uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
        },
    )
    await admin_session.commit()
    return {"school_id": school_id, "tenant_id": tenant_id}


# Test 1: test_register_applicant_success
# - Mock Turnstile → True
# - Mock email sending → success
# - Register with valid data (first_name, last_name, email, phone, password)
# - Assert user created with role='applicant', status='pending', email_verified=False
# - Assert verification email sent (mock called once)
# - Assert returned user has correct fields (id, email, first_name, last_name)

# Test 2: test_register_applicant_turnstile_failure
# - Mock Turnstile → False
# - Register with valid data → error with code CAPTCHA_FAILED
# - Assert no user record created in database

# Test 3: test_register_duplicate_email_within_tenant
# - Register once with email "parent@test.com" → success
# - Register again with same email in same tenant → EMAIL_ALREADY_EXISTS error
# - Assert only 1 user row with that email in the tenant

# Test 4: test_register_same_email_different_tenant
# - Create tenant A and tenant B
# - Register with email "parent@test.com" in tenant A → success
# - Register with same email in tenant B → success (tenant-scoped unique)
# - Assert 2 separate user rows (one per tenant)
# - NOTE: Requires the 20260303_0200 migration which converts users.email
#   from global unique to composite unique (tenant_id, email)

# Test 5: test_register_weak_password
# - Password "12345678" (no uppercase, no special char) → WEAK_PASSWORD error
# - Password "abcdefgh" (no number, no special char) → WEAK_PASSWORD error
# - Password "Abcd123!" → success (meets all requirements)
# - Assert no user created for the weak password attempts

# Test 6: test_login_success
# - Seed a verified applicant user (email_verified=True, status='active')
# - Login with correct email/password
# - Assert response includes access_token, refresh_token, user profile
# - Assert JWT claims contain: role='applicant', tenant_id, user_id
# - Assert failed_login_attempts reset to 0

# Test 7: test_login_unverified_email
# - Seed an applicant user with email_verified=False
# - Login with correct credentials → EMAIL_NOT_VERIFIED error
# - Assert no tokens issued

# Test 8: test_login_wrong_password
# - Seed a verified applicant user
# - Login with wrong password → INVALID_CREDENTIALS error
# - Assert failed_login_attempts incremented by 1
# - Assert no tokens issued

# Test 9: test_login_account_lockout
# - Seed a verified applicant user
# - 5 failed login attempts → each returns INVALID_CREDENTIALS
# - 6th attempt with CORRECT password → ACCOUNT_LOCKED error
# - Assert account locked for 30 minutes (locked_until > now)
# - Assert no tokens issued on the 6th attempt

# Test 10: test_login_rejects_non_applicant_role
# - Seed a user with role='teacher' and same email
# - Login via applicant login endpoint → INVALID_CREDENTIALS
# - This prevents staff from accidentally accessing the applicant portal
# - Assert the service filters by role='applicant' during login

# Test 11: test_verify_email_success
# - Register applicant → mock captures the verification token
# - Call verify-email with the captured token
# - Assert email_verified=True on the user record
# - Assert status changed from 'pending' to 'active'
# - Assert the token is consumed (re-using it fails)

# Test 12: test_forgot_password_sends_email
# - Seed a verified applicant user
# - Call forgot-password with user's email → mock email sent once
# - Assert the email contains a reset token
# - Call forgot-password 3 more times → 4th attempt is rate limited (429)
# - Assert non-existent email does NOT return an error (timing-safe)

# Test 13: test_reset_password_success
# - Trigger forgot-password → capture reset token from mock
# - Call reset-password with token + new password → success
# - Login with new password → success (tokens issued)
# - Login with old password → INVALID_CREDENTIALS
# - Re-use the same reset token → TOKEN_EXPIRED or TOKEN_INVALID error

# Test 14: test_update_profile
# - Seed a verified applicant user, get JWT
# - Update first_name='Kwame', last_name='Mensah', phone='+233201234567'
# - Assert all fields updated correctly in the database
# - Assert email is NOT updatable via profile update endpoint
# - Assert role and status are NOT changed by the update

# Test 15: test_change_password
# - Seed a verified applicant user, get JWT
# - Change password with correct current_password → success
# - Login with new password → success
# - Change password with wrong current_password → INVALID_CURRENT_PASSWORD error
# - Assert failed attempt does NOT lock the account (password change != login)

# Test 16: test_register_resolves_school_id_correctly
# - Register applicant via public endpoint
# - Assert user.school_id is a valid UUID from the schools table (NOT the tenant_id)
# - Assert user.school_id matches the school for this tenant

# Test 17: test_login_adaptive_captcha_after_failures
# - Fail login 3 times
# - 4th attempt WITHOUT turnstile_token → CAPTCHA_REQUIRED error
# - 4th attempt WITH valid turnstile_token → proceeds normally (may still fail if wrong password)
```

---

## 4.2 Applicant Applications Tests

**File:** `backend/tests/test_applicant_applications.py`

```python
"""
Tests for applicant application management.

Covers: my applications list, create/update/submit drafts, claim flow,
multi-child support, guardian pre-fill, print view, IDOR prevention at
the service layer. Uses two-engine pattern.
"""

# --- Helpers ---

async def _seed_app_prereqs(
    admin_session, tenant_id, *,
    with_applicant_user=True,
    period_requires_account=False,
    period_status="open",
):
    """Seed school, year, class, period, and optionally an applicant user.

    Returns dict with: school_id, class_id, period_id, applicant_user_id (or None),
    tenant_id, academic_year_id.
    """
    # ... raw SQL inserts for school, academic_year, class, admission_period ...
    # admission_period includes: require_applicant_account = period_requires_account
    # If with_applicant_user: create a user with role='applicant', email_verified=True
    pass


async def _create_application_for_user(
    admin_session, tenant_id, school_id, period_id, class_id,
    applicant_user_id, *, status="draft",
):
    """Seed an application linked to a specific applicant user.

    Returns dict with: app_id, tracking_code.
    """
    # ... raw SQL insert into applications with applicant_user_id set ...
    pass


# Test 1: test_list_my_applications_empty
# - Create applicant user, no applications
# - Call list_my_applications(tenant_id, user_id)
# - Assert empty list returned, total=0

# Test 2: test_list_my_applications_with_data
# - Create applicant user
# - Create 3 applications linked to this user (different statuses: draft, submitted, offered)
# - Call list_my_applications(tenant_id, user_id)
# - Assert returns all 3 with correct statuses
# - Assert ordered by created_at desc (most recent first)
# - Assert each result includes: id, applicant_first_name, status, tracking_code, target_class

# Test 3: test_list_my_applications_excludes_other_users
# - Create user A and user B (both applicants in same tenant)
# - Create 2 applications for user A, 1 for user B
# - User A: list_my_applications → returns exactly 2
# - User B: list_my_applications → returns exactly 1
# - Assert no cross-contamination of results

# Test 4: test_create_draft_success
# - Create applicant user in a period with require_applicant_account=True
# - Call create_draft(tenant_id, school_id, period_id, user_id, data)
# - data = {applicant_first_name, applicant_last_name, date_of_birth, gender, target_class_id}
# - Assert application created with status='draft', applicant_user_id=user_id
# - Assert tracking_code is generated (64 chars, token_urlsafe(48))
# - Assert submitted_at is NULL

# Test 5: test_update_draft_adds_data
# - Create a draft application
# - Update with guardian info: {guardians: [{first_name, last_name, phone, relationship}]}
# - Update with medical info: {medical_info: "Allergic to peanuts"}
# - Assert all data persisted correctly on the application record
# - Assert guardian records created in application_guardians table

# Test 6: test_update_draft_only_owner
# - Create draft for user A
# - User B tries to update the same draft via service call with user B's user_id
# - Assert raises NOT_FOUND error (service filters by applicant_user_id)
# - Assert the application data is unchanged (user B's update was rejected)

# Test 7: test_update_non_draft_fails
# - Create draft → submit it (status becomes 'submitted')
# - Try to update the submitted application → CANNOT_UPDATE_SUBMITTED error
# - Assert the application data is unchanged

# Test 8: test_submit_draft_success
# - Create complete draft (all required fields + at least 1 guardian)
# - Period has application_fee_required=False
# - Submit → status transitions from 'draft' to 'submitted'
# - Assert submitted_at is set (not NULL)
# - Assert tracking_code was already generated at creation time
# - Assert status_history entry recorded (draft → submitted)

# Test 9: test_submit_incomplete_draft_fails
# - Create draft without any guardians
# - Submit → VALIDATION_ERROR (at least 1 guardian required)
# - Assert status remains 'draft'
# - Assert submitted_at remains NULL

# Test 10: test_submit_draft_period_closed
# - Create draft for an open period
# - Close the period (set status='closed' via admin_session)
# - Submit the draft → PERIOD_NOT_OPEN error
# - Assert status remains 'draft'

# Test 11: test_multi_child_same_period
# - Create applicant user
# - Create draft 1: applicant_first_name='Kofi', target_class_id=class_1
# - Create draft 2: applicant_first_name='Ama', target_class_id=class_1
# - Both succeed (no unique constraint on applicant_user_id + period)
# - list_my_applications → returns 2 applications for this user
# - Assert both have different applicant_first_name values

# Test 12: test_multi_child_different_periods
# - Create 2 admission periods (period A and period B) for different terms
# - Create application in period A, create application in period B
# - Both linked to same applicant user
# - list_my_applications → returns 2 applications
# - Assert each is linked to its respective period

# Test 13: test_claim_application_success
# - Create an anonymous application (applicant_user_id=NULL)
# - Application has guardian with email='applicant@test.com'
# - Create applicant user with email='applicant@test.com'
# - Call claim(tenant_id, user_id, tracking_code)
# - Assert application.applicant_user_id is now set to user_id
# - Assert application appears in list_my_applications for this user
# - Assert claim is idempotent (claiming again returns already_claimed without error)

# Test 14: test_claim_application_email_mismatch
# - Create anonymous application with guardian email='other@test.com'
# - Applicant user has email='applicant@test.com'
# - Claim with the tracking code → EMAIL_MISMATCH error
# - Assert applicant_user_id remains NULL

# Test 15: test_claim_already_claimed
# - Create application with applicant_user_id already set to user A
# - User B tries to claim with the tracking code → ALREADY_CLAIMED error
# - Assert applicant_user_id still points to user A (not changed to user B)

# Test 16: test_claim_invalid_tracking_code
# - Call claim with a random tracking_code that does not exist
# - Assert NOT_FOUND error
# - Assert no database changes

# Test 17: test_get_printable_application
# - Create and submit an application with:
#   - 2 guardians
#   - 1 document (seed in application_documents)
#   - 1 payment (seed in application_payments, status=completed)
#   - 1 decision (seed in admission_decisions, decision_type=accepted)
# - Call get_printable(tenant_id, user_id, application_id)
# - Assert response includes ALL relations: guardians, documents, payments, decision
# - Assert response includes computed fields: applicant full name, period name, class name
# - Assert only the application owner can access the printable view

# Test 18: test_guardian_prefill_data
# - Create and submit application with 2 guardians for child A
# - Call GET /applicant/applications/guardian-prefill
# - Assert returns 2 guardian records matching child A's guardians
# - Create a second draft for child B
# - Guardian pre-fill should match the most recent submitted application's guardians

# Test 19: test_claim_error_messages_are_generic
# - Attempt claim with invalid tracking code → CLAIM_FAILED error
# - Attempt claim with valid code but wrong email → CLAIM_FAILED error (same message!)
# - Attempt claim with valid code already claimed by another user → CLAIM_FAILED error (same message!)
# - Assert all three return identical error message and HTTP status (anti-enumeration)

# Test 20: test_concurrent_claim_race_condition
# - Create anonymous application
# - Two users attempt to claim simultaneously (mock concurrent DB access)
# - Exactly one succeeds, one gets CLAIM_FAILED
# - Assert application.applicant_user_id is set to the winner

# Test 21: test_draft_guardian_hard_delete_on_update
# - Create draft with 2 guardians
# - Update draft with 3 different guardians
# - Assert only 3 guardians exist (old ones hard-deleted, not soft-deleted)
# - Assert no rows with deleted_at IS NOT NULL for this application's guardians
```

---

## 4.3 IDOR Prevention Tests

**File:** `backend/tests/test_applicant_idor.py`

```python
"""
IDOR (Insecure Direct Object Reference) prevention tests for Applicant Accounts.

Ensures applicant A CANNOT access applicant B's data, even within the same
tenant. Also verifies role boundary enforcement (applicant vs. staff).
These are the most critical security tests for this feature.

Uses two-engine pattern. All tests seed data via admin_session (superuser)
and query via app_session (sims_app_user with RLS enforced).
"""

# --- Helpers ---

async def _seed_two_applicants(admin_session, tenant_id):
    """Seed school, period, class, and two applicant users with applications.

    Returns dict with:
        user_a_id, user_b_id, app_a_id, app_b_id,
        tracking_a, tracking_b, school_id, period_id, class_id
    """
    # ... seeds school, academic_year, class, period ...
    # ... creates user A (role=applicant) with 1 application ...
    # ... creates user B (role=applicant) with 1 application ...
    pass


# Test 1: test_cannot_view_other_users_application
# - User A owns application X
# - Service call: get_application(tenant_id, user_B_id, app_X_id)
# - Assert NOT_FOUND (not FORBIDDEN -- avoids enumeration)
# - Service filters by applicant_user_id from JWT, not from request params

# Test 2: test_cannot_update_other_users_draft
# - User A owns draft Y (status=draft)
# - Service call: update_draft(tenant_id, user_B_id, app_Y_id, data)
# - Assert NOT_FOUND error
# - Assert application data unchanged in database

# Test 3: test_cannot_submit_other_users_draft
# - User A owns draft Z (status=draft, complete with guardian)
# - Service call: submit_draft(tenant_id, user_B_id, app_Z_id)
# - Assert NOT_FOUND error
# - Assert application status still 'draft'

# Test 4: test_cannot_upload_to_other_users_application
# - User A owns application X (status=draft)
# - Service call: add_document(tenant_id, user_B_id, app_X_id, document_data)
# - Assert NOT_FOUND error
# - Assert no new document records in application_documents for app X

# Test 5: test_cannot_pay_for_other_users_application
# - User A owns application X (status=draft, fee required)
# - Service call: initiate_payment(tenant_id, user_B_id, app_X_id, callback_url)
# - Assert NOT_FOUND error
# - Assert no payment records created in application_payments for app X

# Test 6: test_cannot_print_other_users_application
# - User A owns submitted application X
# - Service call: get_printable(tenant_id, user_B_id, app_X_id)
# - Assert NOT_FOUND error

# Test 7: test_cannot_claim_other_users_application_by_id
# - The claim endpoint uses tracking_code, not application_id directly
# - But verify: even if user A passes user B's application_id to a service
#   method that accepts application_id, the service still filters by
#   applicant_user_id and rejects
# - This tests defense-in-depth at the service layer

# Test 8: test_list_only_returns_own_applications
# - Seed 5 applications total: 3 for user A, 2 for user B (same tenant)
# - User A: list_my_applications → assert exactly 3 results
# - User B: list_my_applications → assert exactly 2 results
# - Assert UUIDs in each list do not overlap
# - Assert total count matches (no hidden/leaked records)

# Test 9: test_staff_cannot_access_applicant_endpoints
# - Create a user with role='teacher' in the same tenant
# - Call applicant service methods with teacher's user_id
# - list_my_applications → returns empty (no applications linked to a teacher)
# - Assert the endpoint layer rejects non-applicant roles via dependency check
#   (require_permissions('applicant.applications.read') should fail for teacher)

# Test 10: test_applicant_cannot_access_admin_endpoints
# - Create a user with role='applicant'
# - Attempt to call admin admission service methods
#   (e.g., DecisionService.decide, EnrollmentService.enroll)
# - Assert the endpoint dependency check rejects (missing admissions.decide permission)
# - The applicant role has only 'applicant.*' permissions, not 'admissions.*'

# Test 11: test_cross_tenant_idor
# - Tenant A: create applicant user A with application X
# - Tenant B: create applicant user B (different tenant)
# - Set RLS context to tenant B
# - User B calls get_application(tenant_B_id, user_B_id, app_X_id)
# - Assert NOT_FOUND (RLS blocks cross-tenant + IDOR check blocks cross-user)
# - Switch back to tenant A context → user A can still see their own application

# Test 12: test_user_id_from_jwt_not_request
# - The service MUST use user_id from the JWT (passed via dependency injection),
#   NEVER from request body, query params, or headers
# - Seed applicant user A with application X
# - Call service method with: jwt_user_id=user_A_id (correct)
# - Verify: application.applicant_user_id matches jwt_user_id
# - If the service accepted user_id from request body, an attacker could
#   forge user_id=user_A_id in the request while authenticated as user B
# - This test verifies the service signature accepts user_id as a parameter
#   from the dependency chain, and the endpoint passes current_user["user_id"]

# Test 13: test_cookie_isolation_between_portals
# - This is a frontend integration test (may be manual or E2E)
# - Log in as staff at /auth/login → staff cookies set
# - Log in as applicant at /apply/login → applicant cookies set (different names)
# - Verify staff session still active (staff cookies not overwritten)
# - Note: Applicant uses applicant_access_token cookie, staff uses access_token
```

---

## 4.4 Update Existing Tests

### Modify: `backend/tests/test_enrollment_conversion.py`

Add 3 new tests at the end of the file. These test the role promotion feature that was added to `EnrollmentService` as part of the Applicant Accounts feature.

```python
# --- New tests for applicant role promotion ---


async def test_enroll_promotes_applicant_to_parent(app_session, admin_session):
    """Enrolling an applicant's child promotes user role from 'applicant' to 'parent'.

    When an application has an applicant_user_id and that user's role is 'applicant',
    the EnrollmentService should promote the role to 'parent' so the user gains
    access to the parent portal.
    """
    tenant = await create_test_tenant(admin_session)

    # Seed enrollment prerequisites with an applicant user linked to the application
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])

    # Create applicant user
    applicant_user_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Applicant', 'Parent', 'applicant', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(applicant_user_id),
            "tid": str(tenant["id"]),
            "email": f"applicant-{uuid4().hex[:6]}@test.com",
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake",
        },
    )

    # Link application to the applicant user
    await admin_session.execute(
        text("""
            UPDATE applications
            SET applicant_user_id = CAST(:uid AS uuid)
            WHERE id = CAST(:aid AS uuid)
        """),
        {"uid": str(applicant_user_id), "aid": str(prereqs["app_id"])},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )
    assert result["already_enrolled"] is False
    assert result["student_id"] is not None

    # Verify applicant user role was promoted to 'parent'
    r = await app_session.execute(
        text("SELECT role FROM users WHERE id = CAST(:id AS uuid)"),
        {"id": str(applicant_user_id)},
    )
    role = r.scalar()
    assert role == "parent", (
        f"Expected role to be promoted from 'applicant' to 'parent', got '{role}'"
    )


async def test_enroll_does_not_demote_existing_parent(app_session, admin_session):
    """If the applicant user already has role='parent', enrollment must NOT change the role.

    This covers the case where a parent already has one child enrolled (role was
    previously promoted to 'parent') and submits a new application for a second child.
    Enrolling the second child must not demote or re-set the role.
    """
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])

    # Create user with role='parent' (already promoted from a previous enrollment)
    parent_user_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Existing', 'Parent', 'parent', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(parent_user_id),
            "tid": str(tenant["id"]),
            "email": f"parent-{uuid4().hex[:6]}@test.com",
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake",
        },
    )

    # Link application to the parent user
    await admin_session.execute(
        text("""
            UPDATE applications
            SET applicant_user_id = CAST(:uid AS uuid)
            WHERE id = CAST(:aid AS uuid)
        """),
        {"uid": str(parent_user_id), "aid": str(prereqs["app_id"])},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )
    assert result["already_enrolled"] is False

    # Verify role is still 'parent' (not changed to anything else)
    r = await app_session.execute(
        text("SELECT role FROM users WHERE id = CAST(:id AS uuid)"),
        {"id": str(parent_user_id)},
    )
    role = r.scalar()
    assert role == "parent", (
        f"Expected role to remain 'parent', got '{role}'"
    )


# Test 15 (NEW): test_enroll_revokes_applicant_tokens_on_promotion
# - Create applicant user with active JWT
# - Enroll applicant's child → role promoted to parent
# - Assert all existing tokens for this user are revoked (blacklisted)
# - Next API call with old token returns 401
# - Re-login → JWT now contains role=parent with parent.* permissions
```

---

## Test Summary

| File | Tests | Focus Area |
|------|-------|-----------|
| `test_applicant_accounts.py` | 17 | Registration, Turnstile, login, email verify, password reset, profile CRUD, school_id resolution, adaptive CAPTCHA |
| `test_applicant_applications.py` | 21 | My apps list, drafts (create/update/submit), claim flow, multi-child, print, pre-fill, anti-enumeration, race conditions, guardian hard-delete |
| `test_applicant_idor.py` | 13 | IDOR prevention: cross-user, cross-tenant, role boundaries, JWT-only user_id, cookie isolation |
| `test_enrollment_conversion.py` | +3 | Role promotion (applicant->parent) on enrollment, no demotion for existing parent, token revocation on promotion |
| **Total** | **54** | |

---

## Key Test Patterns

1. **Two-engine pattern**: `admin_session` (superuser) for seeding data via raw SQL, `app_session` (`sims_app_user`) for RLS-enforced queries through the service layer
2. **Tenant context**: Always `CAST(:param AS uuid)` for UUID bind params in raw SQL, `set_app_tenant_context(app_session, tenant_id)` before service calls
3. **Mock external services**: Turnstile verification (`unittest.mock.patch`), email sending (SMTP mock), Paystack API (mock)
4. **IDOR prevention**: Always test cross-user AND cross-tenant access -- return NOT_FOUND (not FORBIDDEN) to prevent enumeration
5. **Password validation**: Test strength requirements (uppercase, lowercase, number, special char, 8+ chars)
6. **Account lockout**: Test threshold (5 failed attempts) and cooldown (30 minutes)
7. **Token validation**: Test expired tokens, invalid tokens, reused tokens (one-time verification/reset)
8. **Rate limiting**: Test per-IP limits on public auth endpoints (register, forgot-password, resend-verification)
9. **Role boundary**: Verify applicant role cannot access staff endpoints and vice versa
10. **Defense-in-depth**: All service methods filter by BOTH `tenant_id` (RLS) AND `applicant_user_id` (IDOR)
11. **Anti-enumeration**: Verify claim and forgot-password return identical errors for different failure modes
12. **Cookie isolation**: Verify applicant cookies don't conflict with staff cookies
13. **Token revocation**: Verify tokens are invalidated after role promotion

---

## Running Tests

```bash
# Run all applicant account tests
cd backend
pytest tests/test_applicant_accounts.py tests/test_applicant_applications.py \
       tests/test_applicant_idor.py -v

# Run with the enrollment promotion tests
pytest tests/test_enrollment_conversion.py -v -k "promote_applicant or demote"

# Run all applicant + admissions tests together
pytest tests/test_applicant_accounts.py tests/test_applicant_applications.py \
       tests/test_applicant_idor.py tests/test_enrollment_conversion.py \
       tests/test_admissions_rls.py -v

# Run with coverage for the applicant service
pytest tests/ -v --cov=app/services/admissions/applicant_service --cov-report=term-missing

# Run with coverage for all admissions services (includes enrollment promotion)
pytest tests/ -v --cov=app/services/admissions --cov-report=term-missing

# Verify RLS still covers all tables (no new tables, but good to confirm)
python scripts/verify_rls.py
```
