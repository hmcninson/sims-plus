# Phase 3: Testing

**Sprint:** 23-24
**Agent:** 8 (Tester)
**Depends on:** All backend code (Agents 1-3, 5) and services must be complete
**Produces:** 98 test cases across 9 test files, test fixtures, RLS verification updates

---

## Task List

| # | Task | File | Tests | Est. |
|---|------|------|-------|------|
| 8.1 | Admission period tests | `test_admission_periods.py` | 10 | 1d |
| 8.2 | Application tests | `test_applications.py` | 18 | 1.5d |
| 8.3 | Application payment tests | `test_application_payment.py` | 12 | 1d |
| 8.4 | Entrance exam tests | `test_entrance_exams.py` | 10 | 1d |
| 8.5 | Admission decision tests | `test_admission_decisions.py` | 10 | 1d |
| 8.6 | Enrollment conversion tests | `test_enrollment_conversion.py` | 12 | 1.5d |
| 8.7 | Class promotion tests | `test_class_promotions.py` | 12 | 1.25d |
| 8.7b | Return intent tests | `test_return_intents.py` | 6 | 0.5d |
| 8.8 | RLS isolation tests | `test_admissions_rls.py` | 8 | 1d |
| 8.9 | Update conftest.py | `tests/conftest.py` | - | 0.25d |
| 8.10 | Update verify_rls.py | `scripts/verify_rls.py` | - | 0.25d |

---

## Test Infrastructure Updates

### 8.9 Update `backend/tests/conftest.py`

Add all 16 new admissions tables to the `TENANT_SCOPED_TABLES` list:

```python
# Add these 16 tables to the existing TENANT_SCOPED_TABLES list:
TENANT_SCOPED_TABLES = [
    # ... existing 55 tables ...

    # Admissions Portal (Sprint 19-24) — 16 tables
    "admission_periods",
    "admission_form_configs",
    "applications",
    "application_guardians",
    "application_documents",
    "application_payments",
    "application_status_history",
    "application_notes",
    "entrance_exams",
    "entrance_exam_registrations",
    "entrance_exam_results",
    "admission_decisions",
    "class_promotions",
    "class_promotion_entries",
    "return_intent_campaigns",
    "return_intents",
]
# Total: 71 tables
```

### Add Admissions Test Fixtures

Add to `conftest.py` or create a separate `tests/admissions_fixtures.py`:

```python
@pytest_asyncio.fixture
async def admission_period_id(admin_session, tenant_a_id, school_a_id, academic_year_id):
    """Create a test admission period for tenant A."""
    period_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, max_applications,
                target_classes, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, :start_date, :end_date, :status,
                :fee_amount, :fee_required, :exam_required, :max_apps,
                :target_classes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_id),
            "tid": str(tenant_a_id),
            "sid": str(school_a_id),
            "ayid": str(academic_year_id),
            "name": "2026/2027 Admissions",
            "start_date": "2026-06-01",
            "end_date": "2026-08-31",
            "status": "open",
            "fee_amount": 50.00,
            "fee_required": True,
            "exam_required": True,
            "max_apps": 200,
            "target_classes": "[]",  # JSONB
        },
    )
    await admin_session.commit()
    return period_id


@pytest_asyncio.fixture
async def application_id(admin_session, tenant_a_id, school_a_id, admission_period_id, class_id):
    """Create a test application for tenant A."""
    app_id = uuid4()
    import secrets
    tracking_code = secrets.token_urlsafe(48)
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tracking_code, :first_name, :last_name,
                :dob, :gender, CAST(:cid AS uuid), :status,
                :custom_fields, :fee_waived, :exam_waived,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id),
            "tid": str(tenant_a_id),
            "sid": str(school_a_id),
            "pid": str(admission_period_id),
            "tracking_code": tracking_code,
            "first_name": "Test",
            "last_name": "Applicant",
            "dob": "2010-05-15",
            "gender": "male",
            "cid": str(class_id),
            "status": "submitted",
            "custom_fields": "{}",
            "fee_waived": False,
            "exam_waived": False,
        },
    )
    await admin_session.commit()
    return app_id
```

### 8.10 Update `backend/scripts/verify_rls.py`

Add the 14 new tables to the RLS verification list:

```python
# Add to the TABLES_TO_VERIFY list:
TABLES_TO_VERIFY = [
    # ... existing tables ...

    # Admissions Portal
    "admission_periods",
    "admission_form_configs",
    "applications",
    "application_guardians",
    "application_documents",
    "application_payments",
    "application_status_history",
    "application_notes",
    "entrance_exams",
    "entrance_exam_registrations",
    "entrance_exam_results",
    "admission_decisions",
    "class_promotions",
    "class_promotion_entries",
    "return_intent_campaigns",
    "return_intents",
]
```

---

## 8.1 Admission Period Tests

**File:** `backend/tests/test_admission_periods.py`

```python
"""
Tests for AdmissionPeriodService.

Covers: CRUD, status transitions, form config, overlap validation, tenant isolation.
"""

# Test 1: test_create_admission_period
# - Create period with valid data
# - Assert all fields saved correctly
# - Assert status defaults to 'draft'
# - Assert form config record auto-created

# Test 2: test_create_period_validates_date_range
# - end_date <= start_date → AdmissionServiceError("VALIDATION_ERROR")

# Test 3: test_create_period_validates_academic_year
# - Non-existent academic_year_id → AdmissionServiceError("NOT_FOUND")

# Test 4: test_create_period_rejects_overlap
# - Create period A for Class 1, June-August
# - Create period B for Class 1, July-September → PERIOD_OVERLAP error
# - Create period C for Class 2, July-September → succeeds (different class)

# Test 5: test_update_period_draft_only
# - Draft period: update name, dates → succeeds
# - Open period: update dates → succeeds (flexible)
# - Archived period: update → error

# Test 6: test_status_transitions_valid
# - draft → open → closed → archived: all succeed
# - Assert status_history recorded for each transition

# Test 7: test_status_transitions_invalid
# - draft → closed → fails
# - open → draft → fails
# - archived → open → fails

# Test 8: test_list_periods_with_filters
# - Create 3 periods (draft, open, closed)
# - Filter by status='open' → 1 result
# - Filter by academic_year_id → correct results
# - Pagination: page=1, page_size=2 → 2 items + total=3

# Test 9: test_update_form_config
# - Update form_schema with JSON Schema
# - Update required_documents
# - Assert upsert behavior (create if not exists, update if exists)

# Test 10: test_period_tenant_isolation
# - Create period for tenant A
# - Switch to tenant B context
# - Query → empty results (RLS prevents cross-tenant access)
```

---

## 8.2 Application Tests

**File:** `backend/tests/test_applications.py`

```python
"""
Tests for ApplicationService.

Covers: submission, Turnstile, JSONB validation, status transitions,
search/filter, waivers, document upload, status check.
"""

# Test 1: test_submit_application_success
# - Mock Turnstile → True
# - Submit with valid data (personal + 2 guardians)
# - Assert application created with status=DRAFT (payment required)
# - Assert guardians created
# - Assert tracking_code is 64 chars (token_urlsafe(48))
# - Assert status_history entry (NULL → draft)
# - Assert notification sent to primary guardian (mock)

# Test 2: test_submit_application_turnstile_failure
# - Mock Turnstile → False
# - Submit → AdmissionServiceError("TURNSTILE_FAILED")

# Test 3: test_submit_application_period_not_open
# - Period status='closed'
# - Submit → AdmissionServiceError("PERIOD_NOT_OPEN")

# Test 4: test_submit_application_max_applications_reached
# - Period max_applications=1, already has 1 application
# - Submit → AdmissionServiceError("MAX_APPLICATIONS_REACHED")

# Test 5: test_submit_application_invalid_target_class
# - target_class_id not in period's target_classes
# - Submit → AdmissionServiceError("INVALID_TARGET_CLASS")

# Test 6: test_submit_application_jsonschema_validation
# - Form schema requires "religion" field (type: string)
# - Submit without "religion" → validation error
# - Submit with "religion" = 123 (wrong type) → validation error
# - Submit with "religion" = "Christian" → success

# Test 7: test_submit_application_fee_waived_auto_submits
# - fee_waived=true on period or application
# - Application goes directly to SUBMITTED status (skips DRAFT)

# Test 8: test_check_status_returns_minimal_data
# - Check status by tracking_code
# - Assert response has ONLY: status, applicant_first_name, submitted_at, last_updated_at
# - Assert NO guardian info, NO documents, NO PII beyond first name

# Test 9: test_check_status_invalid_tracking_code
# - Random tracking_code → NOT_FOUND error

# Test 10: test_change_status_valid_transition
# - SUBMITTED → UNDER_REVIEW → succeeds
# - Assert status_history entry with changed_by and reason

# Test 11: test_change_status_invalid_transition
# - SUBMITTED → ENROLLED → AdmissionServiceError("INVALID_STATUS_TRANSITION")
# - REJECTED → UNDER_REVIEW → fails (terminal state)

# Test 12: test_list_applications_with_filters
# - Create 5 applications (various statuses, classes)
# - Filter by status → correct subset
# - Filter by class → correct subset
# - Search by name → partial match (ILIKE)
# - Search by tracking_code → exact match

# Test 13: test_waive_fee_sets_flag
# - Waive fee with reason
# - Assert fee_waived=true
# - Assert status_history records waiver

# Test 14: test_waive_exam_sets_flag
# - Waive exam with reason
# - Assert exam_waived=true
# - After shortlisting, can go directly to decision (skip exam)

# Test 15: test_add_note_to_application
# - Add internal note
# - Assert note created with correct author_id and is_internal=true
# - Assert note appears in application detail

# Test 16: test_turnstile_fail_closed_on_error
# - Mock Turnstile HTTP call to raise ConnectionError
# - Submit application → CAPTCHA_FAILED error (fail closed, NOT pass-through)
# - Verify no application was created

# Test 17: test_daily_cap_per_tenant
# - Set ADMISSIONS_DAILY_CAP_PER_TENANT=2
# - Submit 2 applications → both succeed
# - Submit 3rd application → DAILY_CAP_EXCEEDED error

# Test 18: test_search_escapes_ilike_wildcards
# - Create application with name "100% Effort"
# - Search for "100%" → returns the application (literal match)
# - Search for "%" → does NOT return all applications (escaped, not wildcard)
```

---

## 8.3 Application Payment Tests

**File:** `backend/tests/test_application_payment.py`

```python
"""
Tests for ApplicationPaymentService.

Covers: Paystack flow, webhook processing, fee waiver, idempotency.
"""

# Test 1: test_initiate_payment_creates_record
# - Initiate payment for application with fee required
# - Mock Paystack API → returns authorization_url
# - Assert application_payments record created (status=pending)
# - Assert Paystack metadata includes application_id, tenant_id, school_id

# Test 2: test_initiate_payment_fee_waived
# - Application has fee_waived=true
# - Initiate payment → error "Fee has been waived"

# Test 3: test_initiate_payment_already_paid
# - Application has completed payment
# - Initiate payment → error "Payment already completed"

# Test 4: test_process_webhook_success
# - Create pending payment record
# - Call process_webhook with matching reference
# - Assert payment status → completed
# - Assert paid_at is set
# - Assert application status → SUBMITTED (was DRAFT)

# Test 5: test_process_webhook_idempotent
# - Process same webhook twice
# - Second call: no error, no duplicate payment
# - Payment status still 'completed'

# Test 6: test_process_webhook_unknown_reference
# - Process webhook with non-existent reference
# - Assert no error raised (webhook returns 200)
# - No records modified

# Test 7: test_webhook_signature_verification
# - Valid signature → processes normally
# - Invalid signature → HTTP 401

# Test 8: test_webhook_sets_tenant_context
# - Webhook uses UnscopedDatabaseSession
# - Verify set_tenant_context is called with tenant_id from metadata
# - Verify RLS allows the payment update

# Test 9: test_webhook_wrong_context_ignored
# - Webhook with context="student_fee" (not "application_fee")
# - Returns {"status": "ignored"}

# Test 10: test_webhook_tenant_id_cross_validation
# - Create payment for tenant A
# - Send webhook with correct reference but tenant B in metadata
# - Assert webhook returns {"status": "ignored", "reason": "tenant mismatch"}
# - Payment status remains 'pending' (not modified)

# Test 11: test_callback_url_validation
# - callback_url with http:// → rejected (must be https)
# - callback_url with https://evil.com/ → rejected (must be simsplus.io)
# - callback_url with https://presec.simsplus.io/apply/pay/callback → accepted

# Test 12: test_payment_status_transitions
# - pending → completed (via webhook)
# - pending → failed (via webhook with failed event)
# - completed → refunded (not implemented in MVP, verify it's rejected)
```

---

## 8.4 Entrance Exam Tests

**File:** `backend/tests/test_entrance_exams.py`

```python
"""
Tests for ExamService.

Covers: create, register, results, capacity, status transitions, waiver.
"""

# Test 1: test_create_exam_session
# - Create exam with valid data
# - Assert defaults: status='scheduled', registered_count=0

# Test 2: test_register_applicants_to_exam
# - Register 3 applicants
# - Assert registrations created with auto-assigned seat numbers
# - Assert application status → EXAM_SCHEDULED for each

# Test 3: test_register_exceeds_capacity
# - Exam capacity=2, register 3 applicants
# - Error: CAPACITY_EXCEEDED

# Test 4: test_register_duplicate_prevented
# - Register applicant A twice to same exam
# - Second attempt → error (unique constraint)

# Test 5: test_submit_exam_results
# - Submit results for 3 registered applicants
# - Assert results created with correct scores
# - Assert application status → EXAM_COMPLETED for each

# Test 6: test_submit_results_upsert
# - Submit results once
# - Submit again with different scores
# - Assert results updated (not duplicated)

# Test 7: test_submit_results_for_unregistered
# - Submit result for applicant not registered to this exam
# - Error: validation error

# Test 8: test_exam_status_transitions
# - scheduled → in_progress → completed: valid
# - completed → scheduled: invalid

# Test 9: test_exam_waiver_skips_exam
# - Set exam_waived=true on application
# - Shortlisted → can go directly to decision (skip EXAM_SCHEDULED)

# Test 10: test_exam_tenant_isolation
# - Create exam for tenant A
# - Register applicant from tenant A
# - Switch to tenant B → exam not visible
```

---

## 8.5 Admission Decision Tests

**File:** `backend/tests/test_admission_decisions.py`

```python
"""
Tests for DecisionService.

Covers: single/bulk decisions, offer management, notifications.
"""

# Test 1: test_make_acceptance_decision
# - Application in EXAM_COMPLETED status
# - Decide: accepted, offered_class_id, response_deadline
# - Assert decision record created
# - Assert application status → OFFERED
# - Assert notification sent to guardian (mock)

# Test 2: test_make_rejection_decision
# - Decide: rejected
# - Assert application status → REJECTED
# - Assert notification sent

# Test 3: test_make_waitlist_decision
# - Decide: waitlisted
# - Assert application status → WAITLISTED

# Test 4: test_decide_requires_offered_class_for_acceptance
# - Decide: accepted, no offered_class_id → validation error

# Test 5: test_decide_invalid_status
# - Application in DRAFT status (not ready for decision)
# - Decide → INVALID_STATUS_TRANSITION

# Test 6: test_decide_already_decided
# - Make decision once
# - Make decision again → ALREADY_DECIDED error

# Test 7: test_bulk_decide_partial_success
# - 5 applications: 3 in EXAM_COMPLETED, 2 in DRAFT
# - Bulk accept → 3 succeeded, 2 failed
# - Assert savepoint pattern (successful ones committed)

# Test 8: test_bulk_decide_all_fail
# - All applications in wrong status
# - Bulk decide → all_failed, HTTP 422

# Test 9: test_offer_acceptance_flow
# - Decision: accepted → status=OFFERED
# - Applicant accepts (admin sets ACCEPTED) → status=ACCEPTED
# - Ready for enrollment

# Test 10: test_offer_expiry
# - Decision with response_deadline=yesterday
# - Expire endpoint/background job → status=EXPIRED
# - Re-offer → status=OFFERED again
```

---

## 8.6 Enrollment Conversion Tests

**File:** `backend/tests/test_enrollment_conversion.py`

```python
"""
Tests for EnrollmentService (applicant → student conversion).

THE most critical test file. Covers: atomic conversion, guardian dedup,
invoice generation, idempotency, bulk partial success, parent account creation.
"""

# Test 1: test_enroll_creates_student
# - Application in ACCEPTED status with 2 guardians
# - Enroll → student record created
# - Assert student has auto-generated student_id (school prefix)
# - Assert application.converted_student_id = student.id
# - Assert application.status = ENROLLED

# Test 2: test_enroll_creates_guardians
# - Application with 2 guardians (father, mother)
# - Enroll → 2 guardian records created
# - Assert student_guardians junction records created
# - Assert guardian relationship types preserved

# Test 3: test_enroll_deduplicates_guardian_by_email
# - Existing guardian with email "parent@test.com" in tenant
# - Application guardian has same email
# - Enroll → links existing guardian (no duplicate created)
# - Assert only 1 guardian record with that email

# Test 4: test_enroll_deduplicates_guardian_by_phone
# - Existing guardian with phone "+233241234567" in tenant
# - Application guardian has same phone (no email match)
# - Enroll → links existing guardian

# Test 5: test_enroll_generates_invoice
# - Fee structure exists for target class
# - Enroll with generate_invoice=true
# - Assert invoice created with correct fee items
# - Assert invoice linked to new student

# Test 6: test_enroll_without_invoice
# - Enroll with generate_invoice=false
# - Assert NO invoice created
# - Student still created successfully

# Test 7: test_enroll_idempotent
# - Enroll same application twice
# - First call → success, student created
# - Second call → returns same student (no duplicate)
# - Assert converted_student_id matches both times

# Test 8: test_enroll_wrong_status
# - Application in SUBMITTED status (not ACCEPTED)
# - Enroll → INVALID_STATUS_TRANSITION error
# - Assert no student created (transaction rolled back)

# Test 9: test_enroll_atomic_rollback
# - Mock invoice generation to fail
# - Enroll → error raised
# - Assert no student created (entire transaction rolled back)
# - Assert no guardian records created
# - Assert application status unchanged

# Test 10: test_bulk_enroll_partial_success
# - 5 ACCEPTED applications
# - Mock: 3 succeed, 2 fail (guardian conflict)
# - Assert savepoint pattern: 3 students created, 2 rolled back
# - Response: succeeded=[3 items], failed=[2 items with error messages]

# Test 11: test_enroll_creates_parent_account
# - Application guardian has email
# - Enroll → parent User account created (via ParentOnboardingService)
# - Assert user created with role=parent
# - Assert parent_account_created=true in response

# Test 12: test_enroll_sends_notification
# - Enroll → notification sent to guardian
# - Assert SMS sent to primary guardian phone
# - Assert email sent to primary guardian email (if provided)
```

---

## 8.7 Class Promotion Tests

**File:** `backend/tests/test_class_promotions.py`

```python
"""
Tests for ClassPromotionService.

Covers: batch creation, preview generation, entry updates, execution,
tenant isolation.
"""

# Test 1: test_create_promotion_batch
# - Create batch with source and target academic years
# - Assert status='draft', all counts=0

# Test 2: test_create_batch_duplicate_years
# - Batch already exists for same source/target years
# - Create again → DUPLICATE_BATCH error

# Test 3: test_generate_preview
# - 10 students in Class 1, 5 in Class 2 (terminal)
# - Generate preview → 15 entries created
# - Class 1 students: action=promote, target_class=Class 2
# - Class 2 students (terminal): action=graduate, target_class=null
# - Batch status='preview', total_students=15

# Test 4: test_update_entry_to_repeat
# - Change student's action from promote → repeat
# - Assert target_class_id stays same (repeat = stay in same class)
# - Assert reason can be set

# Test 5: test_update_entry_to_withdraw
# - Change action to withdraw
# - Assert target_class_id set to null

# Test 6: test_bulk_update_entries
# - Update 5 entries at once (3 promote, 2 repeat)
# - Assert all updated correctly
# - Assert succeeded=5, failed=0

# Test 7: test_execute_batch_promote
# - Execute batch → promoted students have new class_id
# - Assert entry.processed=true for all
# - Assert batch promoted_count updated

# Test 8: test_execute_batch_graduate
# - Terminal class students → student.status='graduated'
# - Assert graduated_count updated

# Test 9: test_execute_batch_partial_failure
# - One student has conflicting data (deleted mid-process)
# - Savepoint pattern → other students still promoted
# - Batch status='completed' with correct counts

# Test 10: test_execute_already_completed
# - Batch status='completed'
# - Execute again → ALREADY_EXECUTED error

# Test 11: test_cannot_update_entry_after_execution
# - Batch status='completed'
# - Update entry → INVALID_STATUS error

# Test 12: test_promotion_tenant_isolation
# - Create batch for tenant A
# - Switch to tenant B → batch not visible
# - Tenant B students not included in tenant A batch
```

---

## 8.7b Return Intent Tests

**File:** `backend/tests/test_return_intents.py`

```python
"""
Tests for ReturnIntentService.

Covers: campaigns, send, responses, stats, tenant isolation.
"""

# Test 1: test_create_return_intent_campaign
# - Create campaign with 2 target classes
# - Assert status='draft', sent_count=0

# Test 2: test_send_campaign
# - Send campaign → return_intent records created for all active students
# - Notifications dispatched to guardians
# - Assert status='sent', sent_at set, sent_count matches

# Test 3: test_send_campaign_already_sent
# - Campaign status='sent'
# - Send again → ALREADY_SENT error

# Test 4: test_respond_returning
# - Parent responds with intent='returning'
# - Assert responded_at and responded_by set

# Test 5: test_campaign_stats
# - 10 students: 4 returning, 2 not_returning, 1 undecided, 3 pending
# - Assert stats match

# Test 6: test_campaign_tenant_isolation
# - Create campaign for tenant A
# - Switch to tenant B → not visible
```

---

## 8.8 RLS Isolation Tests

**File:** `backend/tests/test_admissions_rls.py`

```python
"""
RLS isolation tests for all 16 admissions tables.

Verifies that tenant B cannot see, modify, or delete tenant A's data.
Uses the two-engine test pattern (admin_session for seeding, app_session for RLS queries).
"""

# Test 1: test_admission_periods_isolation
# - Seed period for tenant A (via admin_session)
# - App session with tenant A context → sees period
# - App session with tenant B context → empty results

# Test 2: test_applications_isolation
# - Seed application for tenant A
# - Tenant B cannot SELECT → 0 rows
# - Tenant B cannot UPDATE (WHERE clause fails) → 0 rows affected
# - Tenant B cannot DELETE → 0 rows affected

# Test 3: test_application_guardians_isolation
# - Seed guardian for tenant A application
# - Tenant B → 0 rows

# Test 4: test_application_documents_isolation
# - Same pattern

# Test 5: test_application_payments_isolation
# - Same pattern

# Test 6: test_application_status_history_isolation
# - Same pattern (append-only, but SELECT still filtered)

# Test 7: test_entrance_exams_isolation
# - Same pattern

# Test 8: test_all_16_tables_rls_dynamic
# - Dynamic test: iterate all 16 table names
# - For each: seed a row for tenant A
# - Verify tenant B SELECT returns 0 rows
# - Verify tenant B INSERT with wrong tenant_id fails (WITH CHECK)
# - This catches any future tables added without proper RLS

# IMPORTANT: This test follows the same pattern as test_rls_isolation.py
# which dynamically checks all TENANT_SCOPED_TABLES.
# The 16 new tables are added to TENANT_SCOPED_TABLES in conftest.py,
# so the existing dynamic test will automatically cover them too.
# These explicit tests provide additional validation specific to admissions.
```

---

## Test Summary

| File | Tests | Focus Area |
|------|-------|-----------|
| `test_admission_periods.py` | 10 | Period CRUD, status, overlap, form config |
| `test_applications.py` | 18 | Submit, Turnstile fail-closed, JSONB, status machine, waivers, daily cap, ILIKE escaping |
| `test_application_payment.py` | 12 | Paystack flow, webhook, idempotency, tenant cross-validation, callback URL validation |
| `test_entrance_exams.py` | 10 | Exam CRUD, registration, results, capacity |
| `test_admission_decisions.py` | 10 | Single/bulk decisions, offer management |
| `test_enrollment_conversion.py` | 12 | Atomic conversion, guardian dedup, invoice, idempotency |
| `test_class_promotions.py` | 12 | Batch creation, preview, entry updates, execution |
| `test_return_intents.py` | 6 | Campaigns, send, responses, stats |
| `test_admissions_rls.py` | 8 | RLS on all 16 tables |
| **Total** | **98** | |

### Key Test Patterns

1. **Two-engine pattern**: `admin_session` (superuser) for seeding data, `app_session` (sims_app_user) for RLS-enforced queries
2. **Tenant context**: Always `CAST(:param AS uuid)` for UUID bind params
3. **Mock external services**: Turnstile verification, Paystack API, SMS/email sending
4. **Status machine validation**: Test both valid and invalid transitions
5. **Idempotency**: Test duplicate operations return same result without side effects
6. **Atomicity**: Verify rollback on failure leaves no orphaned records
7. **Partial success**: Verify savepoint pattern for bulk operations
8. **Tenant isolation**: Verify cross-tenant access is impossible at DB level

### Running Tests

```bash
# Run all admissions tests
cd backend
pytest tests/test_admission_periods.py tests/test_applications.py \
       tests/test_application_payment.py tests/test_entrance_exams.py \
       tests/test_admission_decisions.py tests/test_enrollment_conversion.py \
       tests/test_class_promotions.py tests/test_return_intents.py \
       tests/test_admissions_rls.py -v

# Run just the RLS tests
pytest tests/test_admissions_rls.py tests/test_rls_isolation.py -v

# Run with coverage
pytest tests/ -v --cov=app/services/admissions --cov-report=term-missing

# Verify RLS on all tables
python scripts/verify_rls.py
```
