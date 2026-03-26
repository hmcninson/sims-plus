# Testing Plan: User Management & Access Control

---

## Test File Organization

| Test File | Phase | Coverage |
|-----------|-------|----------|
| `backend/tests/test_hr_officer_role.py` | 1A | HR Officer permissions and access |
| `backend/tests/test_otp_service.py` | 1B | OTP generation, verification, rate limiting |
| `backend/tests/test_phone_verification.py` | 1B | Phone verification endpoints |
| `backend/tests/test_sms_password_reset.py` | 1B | SMS-based password reset flow |
| `backend/tests/test_bulk_user_import.py` | 1C | CSV import validation and creation |
| `backend/tests/test_session_timeout.py` | 2 | Heartbeat and inactivity enforcement |
| `backend/tests/test_mfa.py` | 3 | MFA setup, login, backup codes |
| `backend/tests/test_custom_roles.py` | 4 | Custom role CRUD and permission resolution |
| `backend/tests/test_custom_roles_rls.py` | 4 | Cross-tenant isolation for custom_roles |

---

## Phase 1A: HR Officer Role

### test_hr_officer_role.py

```python
"""Tests for HR Officer role."""

class TestHROfficerPermissions:
    """Verify HR Officer has correct access."""

    async def test_hr_officer_can_list_staff(self):
        """HR Officer should have staff.* permissions."""
        # Create HR Officer user, login, GET /staff → 200

    async def test_hr_officer_can_create_staff(self):
        """HR Officer should be able to create staff."""
        # POST /staff → 201

    async def test_hr_officer_can_read_students(self):
        """HR Officer has students.read (not write)."""
        # GET /students → 200

    async def test_hr_officer_cannot_create_students(self):
        """HR Officer should NOT be able to create students."""
        # POST /students → 403

    async def test_hr_officer_cannot_access_finance(self):
        """HR Officer should NOT have finance permissions."""
        # GET /finance/invoices → 403

    async def test_hr_officer_cannot_access_exams(self):
        """HR Officer should NOT have exam permissions."""
        # GET /exams → 403

    async def test_hr_officer_can_read_attendance(self):
        """HR Officer has attendance.read."""
        # GET /attendance → 200

    async def test_hr_officer_cannot_mark_attendance(self):
        """HR Officer should NOT be able to mark attendance."""
        # POST /attendance → 403

    async def test_hr_officer_jwt_permissions(self):
        """JWT for HR Officer should contain correct permissions."""
        # Login as HR Officer, decode JWT, verify permissions list
```

---

## Phase 1B: OTP Service

### test_otp_service.py

```python
"""Tests for the shared OTP service."""

class TestOTPGeneration:
    async def test_generate_otp_returns_true(self):
        """OTP generation should succeed with valid phone and tenant."""

    async def test_otp_stored_hashed_in_redis(self):
        """OTP should be hashed (SHA-256) before Redis storage, not plaintext."""
        # Generate OTP, read raw Redis key, verify it's a hash not digits

    async def test_otp_redis_keys_tenant_scoped(self):
        """Redis keys should include tenant_id."""
        # Verify key format: otp:{purpose}:{tenant_id}:{phone}:{suffix}

    async def test_otp_is_6_digits(self):
        """Generated OTP should be exactly 6 digits."""

    async def test_otp_expires_after_10_minutes(self):
        """Redis TTL should be 600 seconds."""
        # Generate OTP, check TTL on Redis key

class TestOTPRateLimit:
    async def test_rate_limit_1_per_minute(self):
        """Second OTP request within 60 seconds should raise rate_limited."""

    async def test_rate_limit_resets_after_60_seconds(self):
        """OTP request should succeed after 60 seconds."""

class TestOTPVerification:
    async def test_verify_correct_code(self):
        """Correct OTP should verify successfully."""

    async def test_verify_incorrect_code(self):
        """Incorrect OTP should raise invalid error."""

    async def test_verify_increments_attempts(self):
        """Each failed verification should increment attempt counter."""

    async def test_max_5_attempts(self):
        """After 5 failed attempts, should raise max_attempts and delete OTP."""

    async def test_verify_expired_otp(self):
        """Expired OTP should raise expired error."""
        # Generate OTP, delete Redis keys to simulate expiry, verify

    async def test_verify_deletes_keys_on_success(self):
        """Successful verification should delete all Redis keys for this OTP."""

    async def test_cross_tenant_isolation(self):
        """OTP from tenant A should not verify in tenant B."""
        # Generate OTP with tenant_A, try verify with tenant_B → expired

class TestOTPPhoneNormalization:
    async def test_normalize_local_ghana_format(self):
        """Phone '0241234567' should be normalized to '+233241234567'."""

    async def test_normalize_strips_spaces_and_dashes(self):
        """Phone '+233 24-123-4567' should be normalized to '+233241234567'."""

    async def test_otp_matches_after_normalization(self):
        """OTP sent to '0241234567' should verify with '+233241234567' (same phone after normalization)."""

class TestOTPSendFailure:
    async def test_sms_failure_cleans_up_redis(self):
        """If SMS sending fails, Redis keys should be cleaned up."""
        # Mock Arkesel to fail, verify no orphaned Redis keys
```

### test_phone_verification.py

```python
"""Tests for phone verification endpoints."""

class TestSendPhoneOTP:
    async def test_send_otp_success(self):
        """POST /auth/send-phone-otp should send OTP to user's phone."""

    async def test_send_otp_no_phone(self):
        """Should return 400 if user has no phone number."""

    async def test_send_otp_requires_auth(self):
        """Should return 401 without JWT."""

    async def test_send_otp_rate_limited(self):
        """Second request within 60 seconds should return 429."""

class TestVerifyPhone:
    async def test_verify_success(self):
        """POST /auth/verify-phone with correct code sets phone_verified=True."""

    async def test_verify_updates_timestamp(self):
        """phone_verified_at should be set on success."""

    async def test_verify_invalid_code(self):
        """Invalid code should return 400."""

    async def test_verify_creates_audit_log(self):
        """Successful verification should create audit event."""
```

### test_sms_password_reset.py

```python
"""Tests for SMS-based password reset."""

class TestForgotPasswordSMS:
    async def test_existing_phone_sends_otp(self):
        """Should send OTP when phone exists (verify via mock)."""

    async def test_nonexistent_phone_returns_same_response(self):
        """Should return same generic message for non-existent phone (anti-enumeration)."""

    async def test_generic_message_format(self):
        """Response should be: 'If an account with this phone number exists...'"""

class TestResetPasswordSMS:
    async def test_reset_success(self):
        """Correct phone + OTP + valid password should reset password."""

    async def test_reset_blacklists_tokens(self):
        """All existing tokens should be blacklisted after reset."""

    async def test_reset_activates_pending_user(self):
        """PENDING user should become ACTIVE after password reset."""

    async def test_reset_invalid_otp(self):
        """Invalid OTP should return 400."""

    async def test_reset_weak_password(self):
        """Password not meeting complexity should return 422."""

    async def test_reset_creates_audit_log(self):
        """Password reset should create audit event."""

    async def test_can_login_with_new_password(self):
        """After reset, user should be able to login with new password."""
```

---

## Phase 1C: Bulk User Import

### test_bulk_user_import.py

```python
"""Tests for bulk user CSV import."""

class TestImportTemplate:
    async def test_download_template(self):
        """GET /users/import/template should return CSV with correct headers."""

    async def test_template_has_example_rows(self):
        """Template should include example data rows."""

class TestImportPreview:
    async def test_preview_valid_csv(self):
        """Preview mode should validate without creating users."""

    async def test_preview_shows_errors_per_row(self):
        """Invalid rows should have errors in preview."""

    async def test_preview_created_count_is_zero(self):
        """Preview should not create any users."""

class TestImportValidation:
    async def test_missing_required_column(self):
        """CSV missing required column should fail."""

    async def test_invalid_email_format(self):
        """Invalid email should show error for that row."""

    async def test_duplicate_email_in_file(self):
        """Duplicate emails within the file should be caught."""

    async def test_duplicate_email_in_database(self):
        """Email that already exists in the tenant should be caught."""

    async def test_invalid_role(self):
        """Invalid role value should show error with valid options."""

    async def test_platform_admin_role_rejected(self):
        """platform_admin is not an importable role."""

    async def test_chain_admin_role_rejected(self):
        """chain_admin is not an importable role."""

    async def test_parent_role_rejected(self):
        """parent is not an importable role (staff roles only)."""

    async def test_max_200_rows(self):
        """CSV with >200 rows should fail with limit error."""

class TestImportExecution:
    async def test_import_creates_users(self):
        """Valid CSV should create users with PENDING status."""

    async def test_import_returns_credentials(self):
        """Import result should include temporary passwords."""

    async def test_imported_users_have_pending_status(self):
        """All imported users should have status=PENDING."""

    async def test_imported_users_not_email_verified(self):
        """Imported users should have email_verified=False."""

    async def test_import_creates_audit_log(self):
        """Bulk import should create audit event with counts."""

    async def test_import_requires_users_create_permission(self):
        """Endpoint should require users.create permission."""

    async def test_subscription_limit_enforced(self):
        """Import should fail if it would exceed plan user limit."""

class TestImportFileValidation:
    async def test_non_csv_rejected(self):
        """Non-CSV file should return 400."""

    async def test_large_file_rejected(self):
        """File >1MB should return 400."""

    async def test_empty_csv_handled(self):
        """Empty CSV (only headers) should return 0 total."""

    async def test_utf8_bom_handled(self):
        """CSV with UTF-8 BOM (from Excel) should parse correctly."""
```

---

## Phase 2: Session Timeout

### test_session_timeout.py

```python
"""Tests for session timeout and heartbeat."""

class TestHeartbeat:
    async def test_heartbeat_updates_last_activity(self):
        """POST /auth/heartbeat should update user.last_activity_at."""

    async def test_heartbeat_requires_auth(self):
        """Heartbeat should require JWT."""

    async def test_heartbeat_returns_204(self):
        """Heartbeat should return 204 No Content."""

class TestLoginSetsActivity:
    async def test_login_sets_last_activity(self):
        """Successful login should set last_activity_at."""

class TestHeartbeatCrossTenant:
    async def test_heartbeat_cross_tenant_rejected(self):
        """Heartbeat with JWT from tenant A should not update user in tenant B."""
        # Use ValidatedTokenTenant to ensure token tenant matches request tenant

class TestInactivityEnforcement:
    async def test_refresh_succeeds_within_timeout(self):
        """Token refresh should succeed if last_activity < 30 minutes."""

    async def test_refresh_rejected_after_timeout(self):
        """Token refresh should fail if last_activity > 30 minutes."""
        # Set last_activity_at to 31 minutes ago, attempt refresh → 401

    async def test_refresh_rejected_message(self):
        """Error should indicate inactivity timeout."""

    async def test_no_last_activity_allows_refresh(self):
        """If last_activity_at is NULL (legacy user), refresh should succeed."""
        # Defense-in-depth: don't break existing users
```

---

## Phase 3: MFA

### test_mfa.py

```python
"""Tests for TOTP MFA."""

class TestMFASetup:
    async def test_setup_returns_qr_and_secret(self):
        """POST /auth/mfa/setup should return QR code, secret, and backup codes."""

    async def test_setup_returns_10_backup_codes(self):
        """Should return exactly 10 backup codes."""

    async def test_setup_stores_pending_secret(self):
        """Pending secret should be stored (encrypted) on user model."""

    async def test_setup_fails_if_already_enabled(self):
        """Should return 400 if MFA is already enabled."""

    async def test_mfa_not_enabled_until_verify(self):
        """mfa_enabled should remain False after setup (before verify)."""

class TestMFAVerifySetup:
    async def test_verify_with_valid_code_enables_mfa(self):
        """Valid TOTP code should enable MFA."""

    async def test_verify_sets_mfa_enabled_true(self):
        """user.mfa_enabled should be True after verification."""

    async def test_verify_clears_pending_secret(self):
        """mfa_setup_pending_secret should be NULL after verification."""

    async def test_verify_with_invalid_code_fails(self):
        """Invalid code should return 400 without enabling MFA."""

    async def test_verify_without_setup_fails(self):
        """Should return 400 if no setup is in progress."""

class TestMFALogin:
    async def test_login_returns_mfa_required(self):
        """Login for MFA-enabled user should return mfa_required=True."""

    async def test_login_returns_mfa_pending_token(self):
        """Login should return a mfa_pending_token (not full tokens)."""

    async def test_mfa_verify_with_totp_code(self):
        """POST /auth/mfa/verify with correct TOTP should return full tokens."""

    async def test_mfa_verify_with_backup_code(self):
        """Backup code should also work for MFA verification."""

    async def test_backup_code_burned_after_use(self):
        """Used backup code should not work a second time."""

    async def test_mfa_pending_token_expires(self):
        """mfa_pending_token should expire after 5 minutes."""

    async def test_mfa_pending_token_rejected_at_other_endpoints(self):
        """mfa_pending token should NOT work at /students, /staff, etc."""

    async def test_invalid_mfa_code_returns_401(self):
        """Invalid TOTP code should return 401."""

class TestMFADisable:
    async def test_disable_with_correct_password(self):
        """POST /auth/mfa/disable should disable MFA with correct password."""

    async def test_disable_clears_all_mfa_fields(self):
        """Should clear mfa_secret, backup codes, pending secret."""

    async def test_disable_with_wrong_password_fails(self):
        """Should return 400 with incorrect password."""

    async def test_login_no_mfa_after_disable(self):
        """After disabling, login should not require MFA."""

class TestMFABackupCodes:
    async def test_regenerate_returns_new_codes(self):
        """POST /auth/mfa/backup-codes should return 10 new codes."""

    async def test_regenerate_invalidates_old_codes(self):
        """Old backup codes should no longer work after regeneration."""

    async def test_regenerate_requires_password(self):
        """Should require password confirmation."""

class TestMFAAdminDisable:
    async def test_admin_can_disable_user_mfa(self):
        """Admin with users.update should be able to force-disable MFA."""

    async def test_admin_disable_creates_audit_log(self):
        """Admin force-disable should create audit event."""

class TestMFACrossTenant:
    async def test_mfa_pending_token_cross_tenant_rejected(self):
        """MFA pending token from tenant A should be rejected at tenant B's /mfa/verify."""
        # Login at tenant A, get mfa_pending_token, try /mfa/verify at tenant B → 403

class TestMFABruteForce:
    async def test_mfa_brute_force_lockout(self):
        """After 5 failed MFA attempts, further attempts should return 429."""
        # Login, get mfa_pending_token, submit 5 wrong codes, 6th → 429

    async def test_mfa_pending_token_single_use(self):
        """MFA pending token should not be reusable after successful verification."""
        # Login, get mfa_pending_token, verify successfully, try again → 401

class TestMFASecurity:
    async def test_secret_encrypted_in_database(self):
        """mfa_secret should be encrypted (not base32 plaintext)."""
        # Read raw DB value, verify it's not a valid base32 string

    async def test_backup_codes_hashed_in_database(self):
        """Backup codes should be hashed (not plaintext)."""
        # Read raw DB value, verify JSON contains hashes not codes
```

---

## Phase 4: Custom Roles

### test_custom_roles.py

```python
"""Tests for custom role CRUD and permission resolution."""

class TestCreateCustomRole:
    async def test_create_role_success(self):
        """POST /custom-roles should create a role with valid data."""

    async def test_create_generates_slug(self):
        """Slug should be auto-generated from name."""

    async def test_create_validates_permissions_against_catalog(self):
        """Unknown permission keys should be rejected."""

    async def test_create_validates_permissions_against_base_role(self):
        """Permissions exceeding base_role ceiling should be rejected."""

    async def test_create_rejects_platform_admin_base_role(self):
        """platform_admin cannot be used as base_role."""

    async def test_create_rejects_chain_admin_base_role(self):
        """chain_admin cannot be used as base_role."""

    async def test_create_duplicate_name_fails(self):
        """Duplicate slug (from same name) should fail."""

    async def test_create_requires_users_create_permission(self):
        """Endpoint should require users.create permission."""

class TestUpdateCustomRole:
    async def test_update_name(self):
        """PUT /custom-roles/{id} should update name and slug."""

    async def test_update_permissions(self):
        """Should update permissions list."""

    async def test_update_system_role_fails(self):
        """System roles (is_system=True) cannot be modified."""

    async def test_update_validates_permissions(self):
        """Updated permissions still validated against base_role ceiling."""

class TestDeleteCustomRole:
    async def test_delete_success(self):
        """DELETE /custom-roles/{id} should soft-delete the role."""

    async def test_delete_blocked_with_assigned_users(self):
        """Should return 409 if users are assigned to the role."""

    async def test_delete_system_role_fails(self):
        """System roles cannot be deleted."""

class TestListCustomRoles:
    async def test_list_returns_roles_with_user_counts(self):
        """GET /custom-roles should return roles with user_count."""

    async def test_list_excludes_deleted_roles(self):
        """Soft-deleted roles should not appear in list."""

class TestPermissionsCatalog:
    async def test_catalog_returns_all_modules(self):
        """GET /custom-roles/permissions/catalog returns all modules."""

    async def test_catalog_filtered_by_base_role(self):
        """?base_role=teacher should only return teacher-allowed permissions."""

    async def test_catalog_teacher_excludes_finance(self):
        """Teacher base_role should not include finance permissions."""

class TestPermissionResolution:
    async def test_user_with_custom_role_gets_custom_permissions(self):
        """JWT for user with custom_role_id should contain custom permissions."""

    async def test_user_without_custom_role_gets_default_permissions(self):
        """JWT for user without custom_role_id should contain ROLE_PERMISSIONS."""

    async def test_deleted_custom_role_falls_back_to_base(self):
        """If custom role is deleted, user should fall back to base role permissions."""

    async def test_custom_permissions_enforced_at_endpoints(self):
        """User with custom role missing finance.read should get 403 on finance endpoints."""

class TestFeatureGate:
    async def test_starter_tier_cannot_create_roles(self):
        """Starter tier should be blocked from creating custom roles."""

    async def test_professional_tier_can_create_roles(self):
        """Professional tier should be able to create custom roles."""
```

### test_custom_roles_rls.py

```python
"""Tests for custom_roles RLS (cross-tenant isolation)."""

class TestCustomRolesRLS:
    async def test_roles_invisible_across_tenants(self):
        """Custom role from tenant A should not be visible in tenant B."""

    async def test_cannot_assign_cross_tenant_role(self):
        """User in tenant A should not be assignable to tenant B's custom role."""

    async def test_rls_policy_exists(self):
        """Verify RLS policy exists on custom_roles table."""
        # Query pg_policies for custom_roles table
```

---

## Shared Test Utilities

### Update `backend/tests/conftest.py`

```python
# Add to TENANT_SCOPED_TABLES (verify current count in conftest.py before updating):
"custom_roles",  # Phase 4 — total becomes existing + 1

# Add helper fixtures:
@pytest.fixture
async def hr_officer_user(db_session, tenant):
    """Create an HR Officer user for testing."""
    ...

@pytest.fixture
async def mfa_enabled_user(db_session, tenant):
    """Create a user with MFA enabled (pre-configured TOTP secret)."""
    ...

@pytest.fixture
async def custom_role(db_session, tenant):
    """Create a sample custom role for testing."""
    ...
```

---

## End-to-End Test Scenarios

### Happy Paths

1. **New school onboarding → bulk import → HR Officer login**
   - Register school → Admin imports 20 users via CSV → HR Officer logs in with temp password → Resets password → Can access staff module

2. **Teacher enables MFA → logs in with MFA**
   - Teacher navigates to account settings → Enables MFA → Scans QR code → Verifies with TOTP → Logs out → Logs in → Enters email/password → Enters TOTP → Dashboard loads

3. **Admin creates custom role → assigns to user**
   - Admin creates "Department Head" custom role (base: teacher + extra permissions) → Assigns to teacher → Teacher logs in → Has custom permissions in JWT → Can access additional endpoints

4. **Parent verifies phone → receives SMS notifications**
   - Parent logs in → Sees phone verification prompt → Sends OTP → Enters code → Phone verified → Receives SMS attendance alerts

5. **Session timeout → warning → continue**
   - User idle for 25 minutes → Warning dialog appears → User clicks "Continue" → Timer resets → Heartbeat sent

---

## Test Execution Commands

```bash
# Run all user management tests
pytest backend/tests/test_hr_officer_role.py backend/tests/test_otp_service.py \
       backend/tests/test_phone_verification.py backend/tests/test_sms_password_reset.py \
       backend/tests/test_bulk_user_import.py backend/tests/test_session_timeout.py \
       backend/tests/test_mfa.py backend/tests/test_custom_roles.py \
       backend/tests/test_custom_roles_rls.py -v

# Run by phase
pytest backend/tests/test_hr_officer_role.py -v                    # Phase 1A
pytest backend/tests/test_otp_service.py \
       backend/tests/test_phone_verification.py \
       backend/tests/test_sms_password_reset.py -v                 # Phase 1B
pytest backend/tests/test_bulk_user_import.py -v                   # Phase 1C
pytest backend/tests/test_session_timeout.py -v                    # Phase 2
pytest backend/tests/test_mfa.py -v                                # Phase 3
pytest backend/tests/test_custom_roles.py \
       backend/tests/test_custom_roles_rls.py -v                   # Phase 4
```
