# Coder Agent Memory - SIMS Plus Backend

## Tenants Table Schema (Actual)
The `tenants` table does NOT have `status` or `max_staff` columns. Key NOT NULL columns:
- `name`, `slug`, `subdomain`, `tenant_type`, `subscription_tier`, `max_students`, `is_active`
- Columns with defaults: `id` (gen_random_uuid()), `created_at`, `updated_at`, `primary_color` ('#1B4F72')
- Nullable: `email`, `phone`, `settings`, `logo_url`, `subscription_start`, `subscription_end`, `deleted_at`, `created_by`, `updated_by`

## Correct Tenant INSERT for Tests
```sql
INSERT INTO tenants (id, subdomain, slug, name, is_active,
    tenant_type, subscription_tier, max_students,
    created_at, updated_at)
VALUES (CAST(:id AS uuid), :sub, :slug, :name, true,
    'SINGLE_SCHOOL', 'TRIAL', 50,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
```

## Users Table - All NOT NULL Columns (No Defaults)
email, password_hash, first_name, last_name, role, status, email_verified, mfa_enabled, failed_login_attempts, timezone, tenant_id

## SQLAlchemy Identity Map + expire_all() Gotcha
When a service uses `self.db.expire_all()` (e.g., after raw SQL UPDATEs that bypass ORM),
callers holding ORM objects will get MissingGreenlet when accessing attributes in sync context.
**Fix:** Capture scalar IDs into local variables BEFORE calling any method that may expire objects.
```python
report_id = reports[0].id  # capture before expire_all
await service.calculate_rankings(...)  # internally calls expire_all()
report = await service.get_report(tenant_id, report_id)  # use captured ID
```

## Stale Identity Map Solutions (Ranked by Safety)
1. `populate_existing=True` on queries -- safest, forces fresh data on re-fetch
2. Direct SQL COUNT queries -- bypass identity map entirely for aggregates
3. `self.db.expire_all()` after raw SQL -- use with caution, capture IDs first
4. AVOID `self.db.expire(obj)` -- causes MissingGreenlet if caller holds reference

## BaseHTTPMiddleware: No HTTPException
FastAPI's `BaseHTTPMiddleware.dispatch()` cannot raise `HTTPException` -- it won't convert to HTTP response.
**Fix:** Use `return JSONResponse(status_code=..., content={"detail": ...})` instead.

## JWT Token Uniqueness
Tokens generated in the same second are identical without a unique claim.
**Fix:** Add `"jti": str(uuid4())` to token payloads.

## Enum Values in DB (classlevel)
Valid `classlevel` values: `nursery_1`, `nursery_2`, `preschool`, `kg_1`, `kg_2`,
`primary_1`-`primary_6`, `jhs_1`-`jhs_3`, `shs_1`-`shs_3`. NOT plain `"nursery"`.

## InvoiceIssue Endpoint Requires Body
POST `/finance/invoices/{id}/issue` expects JSON body: `{"issue_date": "YYYY-MM-DD"}` (optional field, but body must be present).

## User Model Import Path
`User` model lives in `app.models.user`, NOT `app.models.tenant`.

## Migration Chain (Current Head)
`5e70fd6d9695` -> `20260220_0100` (notifications + sms_log tables)

## TENANT_SCOPED_TABLES Count
50 tables total (48 original + notifications + sms_log). Must stay in sync with
`tests/conftest.py` TENANT_SCOPED_TABLES list and RLS migration.

## New Models (2026-02-20)
- `Notification` (app.models.notification) - in-app user alerts, tenant-scoped
  - Enums: NotificationType (info/success/warning/error/system), NotificationCategory (academic/finance/attendance/exam/general/admin)
- `SMSLog` (app.models.sms) - outbound SMS tracking, tenant-scoped
  - Enums: SMSProvider (hubtel/arkesel/twilio), SMSStatus (pending/sent/delivered/failed)

## New Services (2026-02-20 Batch 1)
- `NotificationService` (app.services.notification) - CRUD for in-app notifications, pagination, mark read/all read
- `SMSService` (app.services.sms) - stub SMS sending + log retrieval, will integrate Hubtel/Arkesel/Twilio later
- `FinanceReportService` (app.services.finance.reports) - fee collection by type, outstanding fees, payment method summary
- `AuthService.invite_user()` - creates user with temp password + sends invite email
- `AttendanceService.get_attendance_report_data()` - per-student attendance aggregation with case() counts
- `EmailService` new methods: send_attendance_alert, send_exam_results_notification, send_fee_reminder, send_user_invite

## Finance Model Join Path for Reports
FeeType is reached via FeeItem.fee_type_id (NOT through FeeStructure).
Join: Payment -> Invoice -> InvoiceItem -> FeeItem -> FeeType

## EmailService Pattern
Singleton instance: `email_service = EmailService()` at module level.
Not DB-dependent (no AsyncSession). Import as `from app.services.email import email_service`.

## Unit Tests (No DB Required) - tests/unit/
For tests that don't need PostgreSQL, place them in `tests/unit/`.
This directory has its own `conftest.py` that overrides the DB autouse fixtures from
the parent conftest with no-ops. This avoids connection errors when DB is unavailable.
- `tests/unit/__init__.py` -- package marker
- `tests/unit/conftest.py` -- overrides `_fix_schema_mismatches` as no-op
- `tests/unit/test_email_templates.py` -- 43 tests for EmailService rendering + MIME

## EmailService Template Details
- Only 2 Jinja2 templates on disk: `welcome.html`, `password_reset.html`
- Sprint 5-6 methods use inline f-string HTML (no template files): send_attendance_alert,
  send_exam_results_notification, send_fee_reminder, send_user_invite
- send_user_credentials_email and send_invoice_email also use inline f-strings
- send_fee_reminder takes `currency` param (not just amount_due)
- send_exam_results_notification does NOT take results_summary param (just student_name, exam_name, school_name)

## Test Suite Status (2026-02-17)
460 tests, all passing. Test files: test_academic.py, test_academic_year_service.py,
test_attendance_service.py, test_auth.py, test_class_service.py, test_department_service.py,
test_exams.py, test_fee_structure_service.py, test_finance.py, test_guardian_service.py,
test_idor.py, test_preschool.py, test_rate_limiting.py, test_rls_isolation.py,
test_scholarship_service.py, test_staff_service.py, test_student_service.py,
test_student_tenant_isolation.py, test_students.py, test_subject_service.py,
test_tenant_middleware.py
Plus: tests/unit/test_email_templates.py (43 tests)
