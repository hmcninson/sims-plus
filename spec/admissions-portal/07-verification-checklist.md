# Verification Checklist

**Purpose:** End-to-end verification steps, cross-tenant security checks, and deployment checklist. Use this after all implementation is complete.

---

## 1. Pre-Deployment Checks

### 1.1 Database

- [ ] Migration `20260303_0100_admissions_tables.py` runs cleanly on fresh database
- [ ] Migration downgrade drops all 16 tables + 6 enums without errors
- [ ] All 16 tables have RLS enabled: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`
- [ ] All 16 tables have RLS forced: `ALTER TABLE ... FORCE ROW LEVEL SECURITY`
- [ ] All 16 tables have `tenant_isolation` policy using `get_current_tenant_id()`
- [ ] All 16 tables have `GRANT SELECT, INSERT, UPDATE, DELETE ON ... TO sims_app_user`
- [ ] Run `python scripts/verify_rls.py` → all 71 tables passing (55 existing + 16 new)
- [ ] All indexes created (verify with `\di` in psql)
- [ ] Migration chain: `20260302_0100 → 20260303_0100` (no branch conflicts)

### 1.2 Backend Code

- [ ] All 16 models registered in `backend/app/models/__init__.py`
- [ ] All models use `TenantMixin + SoftDeleteMixin` and `lazy="raise"` on relationships
- [ ] All enums use `values_callable=lambda x: [e.value for e in x]`
- [ ] All services use `flush()/refresh()` not `commit()`
- [ ] All services have defense-in-depth `.filter(Model.tenant_id == tenant_id)`
- [ ] `get_public_tenant_db()` added to `backend/app/api/deps.py`
- [ ] `PublicTenantSession` type alias added
- [ ] Public paths added to BOTH `middleware/tenant.py` AND `api/deps.py`:
  - `/api/v1/admissions/public/`
  - `/api/v1/admissions/public/webhook/`
- [ ] Rate limits configured in `middleware/rate_limit.py` for all public endpoints
- [ ] Admissions permissions added to `ROLE_PERMISSIONS` in `services/auth.py`:
  - `chain_admin`: `admissions.*`
  - `school_admin`: `admissions.*`
  - `academic_head`: `admissions.read`, `admissions.review`
- [ ] `TURNSTILE_SECRET_KEY` and `TURNSTILE_SITE_KEY` in `backend/app/core/config.py`
- [ ] `jsonschema>=4.20.0` in `backend/requirements.txt`
- [ ] Admissions router registered in `backend/app/api/v1/router.py`
- [ ] No `from __future__ import annotations` in endpoint files

### 1.3 Frontend Code

- [ ] Sidebar "Enrollment" group added with all sub-items
- [ ] Public apply pages under `frontend/app/(auth)/apply/`
- [ ] Admin pages under `frontend/app/(dashboard)/admissions/`
- [ ] `NEXT_PUBLIC_TURNSTILE_SITE_KEY` in frontend environment
- [ ] Students/enrollments page redirects to `/admissions/enrollment`

### 1.4 Tests

- [ ] `TENANT_SCOPED_TABLES` in `conftest.py` updated with 16 new tables (total: 71)
- [ ] All 98 tests pass: `pytest tests/test_admission*.py tests/test_enrollment*.py tests/test_class_promotions.py tests/test_return_intents.py tests/test_admissions_rls.py -v`
- [ ] RLS dynamic test catches all 16 new tables
- [ ] No test pollution (each test cleans up after itself)

---

## 2. End-to-End Functional Verification

### 2.1 Public Application Flow

- [ ] **Step 1:** Visit `presec.simsplus.io/apply` → landing page loads with school branding (logo, name, motto, colors)
- [ ] **Step 2:** See list of open admission periods with target classes and fee info
- [ ] **Step 3:** Click "Apply Now" → multi-step form loads with correct custom fields
- [ ] **Step 4:** Fill personal info (first name, last name, DOB, gender, target class)
- [ ] **Step 5:** Fill guardian info (at least 1, phone required, email optional)
- [ ] **Step 6:** Upload documents (PDF/JPG/PNG, max 5MB each, max 5 per application)
- [ ] **Step 7:** Review all information on summary page
- [ ] **Step 8:** Cloudflare Turnstile widget renders and can be completed
- [ ] **Step 9:** Submit → receive tracking code (64 chars, URL-safe)
- [ ] **Step 10:** If payment required → redirect to Paystack → complete payment
- [ ] **Step 11:** Paystack callback page shows success
- [ ] **Step 12:** Check status using tracking code → shows status + first name only

### 2.2 Payment Flow

- [ ] Paystack transaction created with correct metadata (application_id, tenant_id, school_id, context)
- [ ] MoMo payment works (test mode: +233541234567)
- [ ] Card payment works (test card: 4084 0840 8408 4081)
- [ ] Webhook received and processed → payment status updated to 'completed'
- [ ] Application status transitions from DRAFT to SUBMITTED after payment
- [ ] Duplicate webhook is idempotent (no error, no duplicate payment)

### 2.3 Fee & Exam Waivers

- [ ] Admin can waive application fee → fee_waived=true
- [ ] Waived application skips payment, goes directly to SUBMITTED
- [ ] Admin can waive entrance exam → exam_waived=true
- [ ] Waived application skips EXAM_SCHEDULED/EXAM_COMPLETED stages

### 2.4 Admin Review Flow

- [ ] Admin sees applications in list with filters (status, class, period, search)
- [ ] Admin opens application detail → sees all info, guardians, docs, payments
- [ ] Admin changes status: SUBMITTED → UNDER_REVIEW → SHORTLISTED
- [ ] Status history records each transition with reason and changed_by
- [ ] Admin adds internal note to application

### 2.5 Entrance Exam Flow

- [ ] Admin creates exam session (date, venue, capacity)
- [ ] Admin registers shortlisted applicants → status becomes EXAM_SCHEDULED
- [ ] Seat numbers auto-assigned
- [ ] Registration respects capacity (cannot exceed)
- [ ] Admin enters exam results (score, max_score, grade, passed)
- [ ] Application status → EXAM_COMPLETED after results entered
- [ ] Exam waived applicants skip this entire flow

### 2.6 Decision Flow

- [ ] Admin makes acceptance decision → application status = OFFERED
- [ ] Decision includes offered_class_id and response_deadline
- [ ] Notification sent to guardian (SMS + email) on acceptance
- [ ] Admin makes rejection → status = REJECTED, notification sent
- [ ] Admin waitlists → status = WAITLISTED
- [ ] Bulk accept: select 10 applicants → "Accept Selected" → partial success response
- [ ] Bulk reject: confirmation dialog → all rejected

### 2.7 Enrollment (Critical)

- [ ] Admin enrolls accepted applicant → student record created
- [ ] Student has auto-generated student ID (school prefix + sequential number)
- [ ] Guardian records created (or existing ones linked via deduplication)
- [ ] StudentGuardian junction records created with correct relationships
- [ ] Invoice generated if fee structure exists for target class
- [ ] Application status = ENROLLED, converted_student_id set
- [ ] Parent User account created if guardian has email
- [ ] Notification sent to guardian
- [ ] Enrolled student appears in Students list with correct class
- [ ] **Idempotency:** Enrolling same application again returns existing student (no duplicate)
- [ ] **Atomicity:** If invoice generation fails, entire transaction rolls back (no orphaned student)
- [ ] Bulk enroll: 5 applicants → 4 succeed, 1 fails (guardian conflict) → partial success response
- [ ] Bulk enroll: all fail → HTTP 422 with error details

### 2.8 Class Promotion Flow

- [ ] Admin creates promotion batch (select academic year, source classes)
- [ ] Admin generates preview → system auto-assigns default actions (promote/graduate based on class level)
- [ ] Preview shows all active students in selected classes with default actions
- [ ] Admin adjusts individual entries (change action: promote, repeat, graduate, withdraw)
- [ ] Admin adjusts target_class_id for promoted students (defaults to next class)
- [ ] Admin bulk-updates entries (e.g., select 10 students → set to "repeat")
- [ ] Admin executes batch → students promoted/graduated/repeated atomically
- [ ] Promoted students: `current_class_id` updated to target class
- [ ] Graduated students: `enrollment_status = 'graduated'`
- [ ] Repeated students: `current_class_id` unchanged (stay in same class)
- [ ] Withdrawn students: `enrollment_status = 'withdrawn'`
- [ ] Batch status transitions: draft → preview → in_progress → completed
- [ ] **Partial failure:** If 1 of 50 entries fails, 49 succeed (savepoint-per-entry)
- [ ] **Idempotency:** Executing already-completed batch returns error (no double promotion)
- [ ] **Lock:** Cannot update entries after batch is executed

### 2.9 Return Intent Survey Flow

- [ ] Admin creates campaign targeting classes + academic year + message template
- [ ] Admin sends campaign → SMS/email dispatched to guardians of students in target classes
- [ ] Campaign status = 'sent', sent_at + sent_count updated
- [ ] Parent responds via parent portal (returning / not_returning / undecided)
- [ ] Admin views campaign stats: returning count, not_returning count, undecided count, no_response count
- [ ] **Informational only:** Survey responses do NOT affect promotion or enrollment
- [ ] Cannot send already-sent campaign again

### 2.10 Offer Expiry (Background Task)

- [ ] Celery Beat task `expire_overdue_offers` runs daily at 1 AM
- [ ] Applications with OFFERED status + passed `response_deadline` → EXPIRED
- [ ] Expired applications can be re-offered by admin (EXPIRED → OFFERED)

### 2.11 Dashboard

- [ ] Pipeline stats load correctly (total, by status, by class)
- [ ] Conversion rate calculated (enrolled / total applications)
- [ ] Pending decisions count accurate
- [ ] Pending enrollment count accurate (accepted but not enrolled)
- [ ] Recent applications list shows last 10
- [ ] Demographics: gender, nationality, previous school, age distribution

---

## 3. Cross-Tenant Security Verification

### 3.1 RLS Isolation

- [ ] Tenant B cannot SELECT tenant A's admission periods
- [ ] Tenant B cannot SELECT tenant A's applications
- [ ] Tenant B cannot SELECT tenant A's application guardians
- [ ] Tenant B cannot SELECT tenant A's application documents
- [ ] Tenant B cannot SELECT tenant A's application payments
- [ ] Tenant B cannot SELECT tenant A's application status history
- [ ] Tenant B cannot SELECT tenant A's application notes
- [ ] Tenant B cannot SELECT tenant A's entrance exams
- [ ] Tenant B cannot SELECT tenant A's exam registrations
- [ ] Tenant B cannot SELECT tenant A's exam results
- [ ] Tenant B cannot SELECT tenant A's admission decisions
- [ ] Tenant B cannot SELECT tenant A's class promotions
- [ ] Tenant B cannot SELECT tenant A's class promotion entries
- [ ] Tenant B cannot SELECT tenant A's return intent campaigns
- [ ] Tenant B cannot SELECT tenant A's return intents
- [ ] Tenant B cannot INSERT into tenant A's tables (WITH CHECK prevents)
- [ ] Tenant B cannot UPDATE tenant A's records
- [ ] Tenant B cannot DELETE tenant A's records

### 3.2 Public Endpoint Security

- [ ] Public endpoints only work with valid subdomain (TenantMiddleware rejects unknown)
- [ ] Public endpoints set RLS context correctly (get_public_tenant_db)
- [ ] Status endpoint returns ONLY: status, first_name, submitted_at, last_updated_at (no PII)
- [ ] Tracking code has 384 bits entropy (token_urlsafe(48)) — not guessable
- [ ] Document upload path includes tenant_id: `admissions/{tenant_id}/{application_id}/...`
- [ ] No S3 public read ACL on uploaded documents
- [ ] Rate limits enforced on all public endpoints (especially submit: 3/min)
- [ ] Turnstile token verified before application submission
- [ ] Turnstile fails CLOSED on Cloudflare outage (does NOT silently pass)
- [ ] Per-tenant daily application cap enforced (default 500/day)
- [ ] Webhook cross-validates metadata `tenant_id` against payment record's `tenant_id`
- [ ] Webhook uses `PAYSTACK_WEBHOOK_SECRET` with fallback to `PAYSTACK_SECRET_KEY`
- [ ] `callback_url` validated to HTTPS on `*.simsplus.io` domain only
- [ ] `form_schema` validated: no `$ref` allowed, max nesting depth 5
- [ ] Notification templates use `Template.safe_substitute()` (not `str.format()`)
- [ ] All unique constraints are composite with `tenant_id`: tracking_code, provider_reference, form_config.admission_period_id, decision.application_id
- [ ] Document upload presigned URL includes `Content-Type` condition matching declared MIME type
- [ ] `AdmissionApplicationStatus` enum name used (not `ApplicationStatus` — avoids finance module collision)

### 3.3 Webhook Security

- [ ] Paystack webhook verifies HMAC-SHA512 signature
- [ ] Invalid signature → HTTP 401 (not 200)
- [ ] Webhook extracts tenant_id from metadata (not from URL/header)
- [ ] Webhook uses UnscopedDatabaseSession + manual set_tenant_context
- [ ] Non-application_fee context events are ignored (return 200)

### 3.4 S3 Path Isolation

- [ ] All document S3 keys follow: `admissions/{tenant_id}/{application_id}/{uuid}.{ext}`
- [ ] tenant_id in path matches the application's tenant_id
- [ ] Presigned URLs are time-limited (1 hour expiry)
- [ ] No public read access on admissions S3 prefix

---

## 4. Performance Verification

- [ ] Application list query with 1000+ applications completes in <500ms
- [ ] Dashboard stats query completes in <1s
- [ ] Document upload presigned URL generation completes in <100ms
- [ ] Paystack payment initiation completes in <2s (includes external API call)
- [ ] Enrollment conversion (single) completes in <3s (6+ table operations)
- [ ] Bulk enrollment (50 applicants) completes in <30s
- [ ] Class promotion preview generation (500 students) completes in <5s
- [ ] Class promotion execution (500 students) completes in <60s
- [ ] All composite indexes verified for common query patterns

---

## 5. Deployment Checklist

### 5.1 Environment Variables

```env
# Backend — add to production .env
TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret-key>
TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>

# Frontend — add to production .env
NEXT_PUBLIC_TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
```

### 5.2 Dependencies

```bash
# Backend
pip install jsonschema>=4.20.0

# Or add to requirements.txt and rebuild Docker image
```

### 5.3 Database Migration

```bash
# Run on staging first
alembic upgrade head

# Verify
python scripts/verify_rls.py

# Run on production
alembic upgrade head
```

### 5.4 Cloudflare Turnstile Setup

1. Log into Cloudflare Dashboard → Turnstile
2. Create a new site widget
3. Add domains: `*.simsplus.io` (or specific school subdomains)
4. Choose "Managed" challenge type
5. Copy Site Key → `TURNSTILE_SITE_KEY` / `NEXT_PUBLIC_TURNSTILE_SITE_KEY`
6. Copy Secret Key → `TURNSTILE_SECRET_KEY`
7. Test with Turnstile test keys first (always passes)

### 5.5 Paystack Webhook Configuration

1. Log into Paystack Dashboard → Settings → Webhooks
2. Add webhook URL: `https://api.simsplus.io/api/v1/admissions/public/webhook/paystack`
3. Or for subdomain-based: `https://{any-school}.simsplus.io/api/v1/admissions/public/webhook/paystack`
4. Note: Paystack sends to ONE URL. Use the central API URL with X-Subdomain header, OR route all webhooks through the existing pattern (tenant from metadata).
5. Enable events: `charge.success`
6. Copy webhook secret for signature verification (should match PAYSTACK_SECRET_KEY)

### 5.6 Docker Rebuild

```bash
# Rebuild backend image with new dependencies
docker compose build backend

# Restart
docker compose up -d
```

### 5.7 Post-Deployment Smoke Test

1. Visit `presec.simsplus.io/apply` → Should show landing page
2. Submit a test application → Should get tracking code
3. Check status → Should show "submitted"
4. Login as admin → Should see application in dashboard
5. Run `python scripts/verify_rls.py` on production → All tables passing

---

## 6. Rollback Plan

If issues are found after deployment:

1. **Database rollback:**
   ```bash
   alembic downgrade 20260302_0100  # Roll back to pre-admissions migration
   ```
   This drops all 16 admissions tables + 6 enums. No existing data is affected.

2. **Code rollback:**
   ```bash
   git revert <commit-hash>  # Revert the admissions PR
   ```

3. **Frontend rollback:**
   - Remove `/apply` route (returns 404)
   - Remove "Enrollment" nav group from sidebar
   - No user-facing breakage (new module only)

4. **Data preservation:**
   - Before rolling back, export any submitted applications:
     ```sql
     COPY (SELECT * FROM applications WHERE status != 'draft') TO '/tmp/applications_backup.csv' CSV HEADER;
     ```
