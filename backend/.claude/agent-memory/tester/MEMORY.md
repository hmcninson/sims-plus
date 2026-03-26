# Test Agent Memory

## Finance Report Tests
- File: `tests/test_finance_reports.py` (14 tests, all passing as of 2026-02-20)
- Service: `app/services/finance/reports.py` (`FinanceReportService`)
- Three report methods: `get_fee_collection_data`, `get_outstanding_fees_data`, `get_payment_summary_data`
- Join path for fee collection: Payment -> Invoice -> InvoiceItem -> FeeItem -> FeeType
- Fee collection has join fan-out: single payment appears once per fee type on the invoice

## Test Data Seeding Pattern (Finance)
- Use `create_test_tenant()` and `create_test_user()` from conftest
- Raw SQL with `CAST(:param AS uuid)` for all UUID bind params
- Enum values lowercase in DB: 'issued', 'completed', 'cash', 'basic', 'active'
- `admin_session.commit()` after seeding (services use flush/refresh but tests need explicit commit)
- `set_app_tenant_context(app_session, tenant_id)` before service calls

## Conftest Fixtures Available
- `admin_session` -- superuser, bypasses RLS (for DDL and seeding)
- `app_session` -- `sims_app_user`, RLS enforced
- `create_test_tenant(admin_session)` -> dict with id, subdomain
- `create_test_user(admin_session, tenant_id)` -> dict with id
- `set_app_tenant_context(app_session, tenant_id)` -- sets RLS context

## AuditLog Model Fix (2026-02-20)
- `AuditLog` inherits from `Base` which defines `updated_at`, but the DB table has no `updated_at` column
- Fix: add `updated_at = None` to the `AuditLog` class to exclude the inherited column
- File: `app/models/audit_log.py`
- This pattern (`column_name = None`) works in SQLAlchemy to exclude inherited columns from child models
- `audit_logs` table has NO RLS -- queries use `admin_session` only
- `tenant_id` is nullable on `audit_logs` (platform-level events have no tenant)

## Key Patterns
- Tests use class-based organization (`class TestFinanceReports`)
- `pytestmark = [pytest.mark.asyncio, pytest.mark.integration]`
- Tenant isolation tests: seed data in tenant_a, set RLS to tenant_b, verify empty results
- Cross-tenant academic year test: use tenant_a's ay_id from tenant_b context, yields nothing
- Test isolation: use unique action strings with `uuid4().hex[:8]` to avoid cross-test interference

## Cross-Session Verification (Critical Pattern)
- `app_session` and `admin_session` are separate DB connections/transactions
- Data created via `app_session.flush()` is NOT visible to `admin_session` (different transaction)
- When verifying data state via `admin_session` after an `app_session` operation, seed the data via `admin_session` + `commit()` FIRST, then use `app_session` for the operation under test
- Applies to: cross-tenant isolation tests, cross-user isolation tests, any test that verifies data wasn't modified

## Notification Tests (2026-02-20)
- File: `tests/test_notifications.py` (15 tests, all passing)
- Migration `20260220_0100` must be applied to test DB (notifications + sms_log tables)
- After creating tables via DDL, must GRANT SELECT/INSERT/UPDATE/DELETE to `sims_app_user`
- Enum types: `notificationtype`, `notificationcategory` (lowercase values)
- Test DB alembic version: `20260425_0400`

## Student Management Gap Closure Tests (2026-03-25)
- 8 new test files, 79 tests, all passing
- Files: test_student_class_history, test_student_status_changes, test_student_mgmt_rls, test_student_withdrawal, test_student_transfer, test_student_documents, test_previous_schools, test_promotion_rules
- Migration bug: `20260425_0300` has enum double-creation (studentdocumenttype created at line 50, then op.create_table tries again). Workaround: apply via raw SQL.
- Full suite: 2027 tests, 2019 passed, 8 failed, 0 skipped

## Pre-Existing Test Failures (not related to student mgmt)
- test_boarding_service: 2 failures (roll call service, roll call report) -- test data/timing issue
- test_boarding_transport_rls: 1 failure (cross_tenant_roll_call_blocked) -- same root cause
- test_extended_care: 3 failures (check_out tests) -- ck_checkout_after_checkin constraint violated, test data sets checkout time <= checkin time
- test_rls_isolation: 2 failures (test_no_null_bypass_in_policies, test_no_platform_admin_bypass_in_policies) -- deadlock in fixture setup, flaky
