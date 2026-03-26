# Phase 4: Testing & Security Review

**Complexity:** Medium
**Dependencies:** Phase 3 (all features must be implemented)
**Estimated effort:** 2 days

---

## Summary

Write and run tests for all platform admin features, then perform a security review focused on the superuser engine, impersonation, and cross-tenant isolation.

---

## Test File Organization

| Test File | Coverage |
|-----------|----------|
| `backend/tests/test_platform_admin_login.py` | Login, MFA enforcement, lockout |
| `backend/tests/test_platform_admin_auth.py` | PlatformAdmin dependency, token validation |
| `backend/tests/test_platform_tenant_crud.py` | Tenant list, detail, update, suspend, activate |
| `backend/tests/test_platform_impersonation.py` | Impersonation token creation, usage, expiry |
| `backend/tests/test_platform_audit.py` | Audit log creation, query |
| `backend/tests/test_platform_analytics.py` | Cross-tenant analytics queries |

---

## Test Cases

### test_platform_admin_login.py

```python
class TestPlatformLogin:
    async def test_valid_credentials_returns_tokens(self):
        """Valid email + password for a platform admin returns access + refresh tokens."""

    async def test_invalid_password_returns_401(self):
        """Wrong password returns 401 with generic error message."""

    async def test_nonexistent_email_returns_401(self):
        """Email not found returns same 401 (no enumeration)."""

    async def test_school_admin_cannot_platform_login(self):
        """A school_admin user cannot log in via /platform/login even if
        they have the email — the query filters by tenant_id = PLATFORM_TENANT_ID."""

    async def test_platform_admin_at_school_login_fails(self):
        """A platform admin user cannot log in via /auth/login at a school subdomain
        because their tenant_id (_platform) doesn't match the school's tenant."""

    async def test_lockout_after_5_failed_attempts(self):
        """After 5 failed login attempts, account is locked for 30 minutes."""

    async def test_lockout_returns_429(self):
        """Locked account returns 429, not 401."""

    async def test_suspended_account_rejected(self):
        """Suspended platform admin cannot log in."""

    async def test_login_sets_last_activity_at(self):
        """Successful login sets user.last_activity_at."""

    async def test_mfa_setup_required_on_first_login(self):
        """First login (mfa_enabled=False) returns mfa_setup_required=True
        with a temporary access token."""

    async def test_mfa_required_when_enabled(self):
        """Login with MFA enabled returns mfa_required=True
        with a mfa_pending_token."""

    async def test_login_audited(self):
        """Successful login creates a platform_audit_log entry
        with action='platform_login'."""

    # RISK FIX (BUG-1/BUG-5): MFA flow tests
    async def test_mfa_verify_with_valid_code_returns_tokens(self):
        """POST /platform/mfa/verify with valid pending token and TOTP
        code returns access + refresh tokens."""

    async def test_mfa_verify_with_invalid_code_returns_401(self):
        """Invalid TOTP code returns 401."""

    async def test_mfa_verify_with_expired_token_returns_401(self):
        """Expired mfa_pending_token returns 401."""

    async def test_mfa_setup_with_valid_code_enables_mfa(self):
        """POST /platform/mfa/setup stores secret, enables MFA, returns tokens."""

    async def test_mfa_setup_when_already_enabled_returns_error(self):
        """Cannot call /platform/mfa/setup if MFA is already enabled."""

    async def test_mfa_generate_returns_secret_and_uri(self):
        """GET /platform/mfa/generate returns a TOTP secret and provisioning URI."""
```

### test_platform_admin_auth.py

```python
class TestPlatformAdminDependency:
    async def test_valid_platform_token_accepted(self):
        """JWT with role=platform_admin, is_platform=True,
        tenant_id=PLATFORM_TENANT_ID is accepted."""

    async def test_school_token_rejected(self):
        """JWT from a school login (no is_platform claim) is rejected at /platform/* endpoints."""

    async def test_missing_is_platform_claim_rejected(self):
        """JWT with role=platform_admin but missing is_platform=True is rejected."""

    async def test_wrong_tenant_id_rejected(self):
        """JWT with role=platform_admin but tenant_id != PLATFORM_TENANT_ID is rejected."""

    async def test_refresh_token_rejected(self):
        """Refresh token (type=refresh) rejected at /platform/* endpoints."""

    async def test_expired_token_rejected(self):
        """Expired platform JWT returns 401."""

    async def test_blacklisted_token_rejected(self):
        """Blacklisted platform JWT returns 401."""

    async def test_mfa_pending_token_rejected(self):
        """mfa_pending token rejected at /platform/* endpoints (type != access)."""

    async def test_mfa_setup_token_rejected(self):
        """MFA setup token (mfa_setup_required=True) rejected at /platform/* endpoints.
        SECURITY: MFA setup tokens must ONLY be usable at the MFA setup endpoint,
        not for full platform admin access."""

    async def test_impersonation_token_rejected_at_platform_endpoints(self):
        """Impersonation token (is_impersonation=True) rejected at /platform/* endpoints.
        SECURITY: Impersonation tokens are scoped to a target tenant and must not
        be usable to access platform admin operations."""

    async def test_suspended_user_token_rejected(self):
        """JWT for a suspended platform admin user is rejected (DB lookup check).
        SECURITY: PlatformAdminUser verifies the user is still active in DB."""

    async def test_deleted_user_token_rejected(self):
        """JWT for a soft-deleted platform admin user is rejected (DB lookup check)."""

class TestPlatformEndpointAccess:
    async def test_platform_endpoints_skip_tenant_middleware(self):
        """/api/v1/platform/* paths do not require subdomain in request."""

    async def test_platform_endpoints_skip_subscription_check(self):
        """/api/v1/platform/* paths are exempt from subscription enforcement."""
```

### test_platform_tenant_crud.py

```python
class TestListTenants:
    async def test_returns_all_tenants(self):
        """GET /platform/tenants returns all non-platform tenants."""

    async def test_excludes_platform_tenant(self):
        """The _platform tenant is excluded from the list."""

    async def test_includes_counts(self):
        """Each tenant includes student_count, staff_count, school_count."""

    async def test_counts_accurate(self):
        """Counts match actual data in the respective tables."""

    async def test_search_by_name(self):
        """?search=presec filters by tenant name."""

    async def test_search_by_subdomain(self):
        """?search=presec also matches subdomain."""

    async def test_filter_by_status(self):
        """?status=active returns only active tenants."""

    async def test_filter_by_tier(self):
        """?tier=professional returns only professional tier tenants."""

    async def test_pagination(self):
        """page=2&page_size=5 returns correct offset."""

    async def test_max_page_size_100(self):
        """page_size > 100 is capped at 100."""

class TestGetTenant:
    async def test_returns_tenant_detail(self):
        """GET /platform/tenants/{id} returns full tenant details."""

    async def test_nonexistent_returns_404(self):
        """Nonexistent tenant ID returns 404."""

    async def test_platform_tenant_returns_404(self):
        """Cannot retrieve the _platform tenant via this endpoint."""

class TestUpdateTenant:
    async def test_update_subscription_tier(self):
        """PATCH /platform/tenants/{id} can change subscription_tier."""

    async def test_update_max_students(self):
        """Can update max_students limit."""

    async def test_update_audited(self):
        """Tenant update creates audit log entry with action='tenant_update'."""

class TestSuspendTenant:
    async def test_suspend_sets_status(self):
        """POST /platform/tenants/{id}/suspend sets status=suspended, is_active=false."""

    async def test_suspend_requires_reason(self):
        """Suspend without reason returns 422."""

    async def test_suspend_already_suspended_returns_409(self):
        """Suspending an already-suspended tenant returns 409."""

    async def test_suspend_audited(self):
        """Suspension creates audit log entry with reason in details."""

class TestActivateTenant:
    async def test_activate_sets_status(self):
        """POST /platform/tenants/{id}/activate sets status=active, is_active=true."""

    async def test_activate_audited(self):
        """Activation creates audit log entry."""
```

### test_platform_impersonation.py

```python
class TestImpersonation:
    async def test_impersonation_returns_token(self):
        """POST /platform/impersonate/{id} returns a JWT with the target tenant_id."""

    async def test_impersonation_token_has_target_tenant_id(self):
        """Impersonation JWT tenant_id matches the target tenant, NOT the platform tenant."""

    async def test_impersonation_token_has_is_impersonation(self):
        """Impersonation JWT has is_impersonation=True claim."""

    async def test_impersonation_token_has_original_tenant_id(self):
        """Impersonation JWT has original_tenant_id = PLATFORM_TENANT_ID."""

    async def test_impersonation_token_has_wildcard_permissions(self):
        """Impersonation JWT has permissions = ["*"]."""

    async def test_impersonation_token_expires_in_30_min(self):
        """Token expiry is ~30 minutes from creation."""

    async def test_impersonation_token_works_at_school_endpoints(self):
        """Impersonation token can be used at /api/v1/students (school endpoint)
        when the request subdomain matches the impersonation tenant."""

    async def test_impersonation_token_fails_at_wrong_school(self):
        """Impersonation token for tenant A rejected at tenant B's subdomain
        (ValidatedTokenTenant check)."""

    async def test_impersonation_audited(self):
        """Impersonation creates audit log entry with action='impersonate_start'."""

    async def test_nonexistent_tenant_returns_404(self):
        """Cannot impersonate a nonexistent tenant."""

    async def test_impersonation_of_platform_tenant_rejected(self):
        """Cannot impersonate the _platform tenant itself."""

class TestImpersonationRefreshBlocked:
    async def test_impersonation_token_cannot_refresh(self):
        """Impersonation token should NOT be usable to get a refresh token.
        (No refresh token is issued during impersonation.)
        Defense-in-depth: even if someone crafts a refresh token with the
        impersonation user's subject, AuthService.refresh_tokens() rejects
        it because the platform admin user's tenant_id (_platform) does
        not match the school tenant_id from the request."""

    async def test_impersonation_token_at_school_refresh_endpoint(self):
        """SECURITY: Submitting the impersonation ACCESS token to /auth/refresh
        fails because it is not a refresh token (type=access, not type=refresh)."""

    async def test_impersonation_token_cannot_create_new_impersonation(self):
        """SECURITY: An impersonation token used at /platform/impersonate/{id}
        is rejected because PlatformAdminUser blocks is_impersonation=True tokens."""

class TestImpersonationSQLInjection:
    async def test_tenant_counts_uses_parameterized_queries(self):
        """SECURITY: _get_tenant_counts uses parameterized queries (ANY(CAST(:ids AS uuid[]))),
        NOT f-string interpolation. Verify by checking that tenant IDs with SQL
        injection payloads do not execute arbitrary SQL."""
```

### test_platform_audit.py

```python
class TestPlatformAuditLog:
    async def test_login_creates_entry(self):
        """Platform login creates audit entry."""

    async def test_audit_entry_has_ip_address(self):
        """Audit entries include client IP address."""

    async def test_get_audit_log_returns_entries(self):
        """GET /platform/audit-log returns paginated entries."""

    async def test_filter_by_action(self):
        """?action=tenant_suspend filters entries."""

    async def test_entries_ordered_by_created_at_desc(self):
        """Most recent entries appear first."""

    async def test_audit_log_not_visible_to_school_users(self):
        """School admin cannot access /platform/audit-log."""
```

### test_platform_analytics.py

```python
class TestPlatformAnalytics:
    async def test_returns_tenant_counts(self):
        """GET /platform/analytics returns correct tenant counts by status."""

    async def test_returns_student_staff_counts(self):
        """Analytics includes total_students and total_staff across all tenants."""

    async def test_returns_tenants_by_plan(self):
        """Analytics includes plan breakdown."""

    async def test_returns_recent_registrations(self):
        """Analytics includes last 10 registered tenants."""

    async def test_analytics_audited(self):
        """Analytics access creates audit entry."""

    async def test_school_user_cannot_access_analytics(self):
        """School admin gets 401 at /platform/analytics."""
```

---

## Regression Tests

Run the **full existing test suite** to verify no regressions:

```bash
cd backend && pytest -x -v --timeout=120
```

**Critical regressions to check:**
- School login still works at school subdomains
- Chain admin login still works
- School switching via X-Active-School still works
- ValidatedTokenTenant still rejects cross-tenant tokens
- Tenant middleware still resolves subdomains correctly
- "admin" subdomain removed from backend `RESERVED_SUBDOMAINS` in middleware but KEPT in frontend proxy.ts and `reserved_subdomains` DB table (RISK FIX R-BC1, R-BC3)
- `test_tenant_middleware.py:40` updated to reflect new admin behavior (RISK FIX R9)
- `test_onboarding.py:115` still passes (admin still rejected at registration via DB table)
- Subscription enforcement skips /platform/* paths
- Rate limiting applied to platform endpoints
- `?subdomain=admin` on localhost does NOT set x-subdomain cookie (prevented by proxy.ts RESERVED_SUBDOMAINS)

**RISK FIX (R-TEST1):** Cross-tenant query tests must:
1. Create 2-3 test tenants with students/staff using the admin engine
2. Verify analytics returns aggregated counts across all tenants
3. Verify tenant list includes counts for each tenant
4. Clean up test data after each test (use admin engine for cleanup)

**RISK FIX (R-TEST3):** proxy.ts manual test checklist:
- [ ] `admin.localhost:3000` shows platform login page
- [ ] `?subdomain=admin` on localhost shows platform login page
- [ ] `presec.localhost:3000` still shows school login (unaffected)
- [ ] `?subdomain=presec` on localhost still routes to school (unaffected)
- [ ] After visiting `?subdomain=admin`, navigating to `localhost:3000` does NOT route to admin portal (cookie not set)

---

## Security Review Checklist

### Superuser Engine Isolation

- [ ] `get_platform_admin_session_maker()` is defined in `session.py` only
- [ ] The session maker is NEVER registered as a FastAPI dependency
- [ ] Only `PlatformService` methods call it
- [ ] Grep for `platform_admin_session_maker` — should only appear in `session.py` and `platform.py`
- [ ] Pool size is limited: `pool_size=2, max_overflow=3`
- [ ] `echo=False` always (superuser queries never logged)
- [ ] `_get_tenant_counts` uses parameterized queries (ANY(CAST(:ids AS uuid[]))), NOT f-string interpolation
- [ ] `_get_tenant_counts` validates table names against `_ALLOWED_COUNT_TABLES` allowlist
- [ ] `get_audit_log` uses superuser engine (sims_app_user has INSERT only on platform_audit_log)

### Impersonation Token Security

- [ ] Impersonation token has `tenant_id` = target tenant (NOT platform)
- [ ] Impersonation token has `is_impersonation: true`
- [ ] Impersonation token has `original_tenant_id` = platform tenant
- [ ] Impersonation token expires in 30 minutes
- [ ] No refresh token issued for impersonation
- [ ] Impersonation token passes `ValidatedTokenTenant` at target subdomain
- [ ] Impersonation token rejected at wrong subdomain
- [ ] Impersonation token REJECTED at /platform/* endpoints (is_impersonation check)
- [ ] Impersonation token cannot be used to create another impersonation token (escalation loop blocked)
- [ ] All impersonation events logged to `platform_audit_log`

### Platform Admin Authentication

- [ ] Platform login only queries users in platform tenant (`tenant_id = PLATFORM_TENANT_ID`)
- [ ] Platform login only accepts `role = platform_admin`
- [ ] School-level platform_admin users CANNOT log in via /platform/login (wrong tenant_id)
- [ ] Platform admin users CANNOT log in via /auth/login at school subdomains (tenant_id mismatch)
- [ ] MFA is mandatory for platform admins (enforced on first login)
- [ ] MFA setup token CANNOT access /platform/* endpoints (mfa_setup_required check)
- [ ] MFA setup token does NOT carry permissions=["*"] (no wildcard in pre-MFA state)
- [ ] MFA pending token uses jose_jwt.encode with type="mfa_pending" (NOT create_access_token)
- [ ] Account lockout works (5 failed attempts → 30-min lock)
- [ ] Token blacklisting works for platform admin tokens
- [ ] Login error messages are uniform for all failure modes (no account enumeration)
- [ ] PlatformAdminUser dependency verifies user still active in DB (cached 60s in Redis)

### Cross-Tenant Isolation

- [ ] Platform admin users in `users` table invisible to school tenants (RLS scopes to platform tenant)
- [ ] `platform_audit_log` has NO RLS (intentional — no tenant_id column)
- [ ] `platform_audit_log` grants INSERT only to sims_app_user (no SELECT)
- [ ] Platform tenant row excluded from tenant list endpoint (WHERE subdomain != '_platform')
- [ ] Superuser engine queries never set RLS context — reads all tenants
- [ ] Regular `get_db()` and `get_unscoped_db()` do NOT use superuser engine
- [ ] Cross-tenant data is read-only from analytics — no writes via superuser engine

### Cookie Security

- [ ] Platform cookies (`platform_access_token`) are `httpOnly: true`
- [ ] Platform cookies are separate from school cookies (`access_token`)
- [ ] Platform cookies have `secure: true` in production
- [ ] Platform cookies have `sameSite: lax`
- [ ] Logging out from platform portal clears only platform cookies
- [ ] Logging out from school dashboard clears only school cookies

### Update Schema Safety

- [ ] `TenantUpdateRequest` does NOT include `status` field (use /suspend and /activate instead)
- [ ] `update_tenant` validates fields against `_ALLOWED_UPDATE_FIELDS` allowlist
- [ ] `max_students` and `max_staff` have `ge=0` validation

### Middleware / Routing

- [ ] `/api/v1/platform/*` paths skip tenant resolution (no subdomain needed)
- [ ] `/api/v1/platform/*` paths skip subscription enforcement
- [ ] `/api/v1/platform/login` and `/api/v1/platform/refresh` in `_PUBLIC_PATH_PREFIXES`
- [ ] "admin" removed from backend `RESERVED_SUBDOMAINS` (tenant.py) but KEPT in frontend proxy.ts and DB table (RISK FIX R-BC1/R-BC3)
- [ ] proxy.ts handles admin.simsplus.io without setting x-subdomain
- [ ] School subdomains still resolve correctly after "admin" removal

---

## Go/No-Go Criteria for Production

| Criterion | Status |
|-----------|--------|
| All platform admin tests pass | |
| All existing tests pass (zero regressions) | |
| Security review checklist complete | |
| Superuser engine grep shows only 2 files | |
| MFA setup tested end-to-end for platform admin | |
| Impersonation tested end-to-end (enter + exit) | |
| Platform audit log has entries for all actions | |
| Rate limits verified on platform endpoints | |
| DNS configured for admin.simsplus.io (staging first) | |
| First platform admin created via CLI | |
