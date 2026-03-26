# Admissions Portal Risk Analysis

**Date:** 2026-02-25
**Analyst:** Risk Analyst Agent
**Feature:** Admissions Portal (Phase 3, Sprints 19-24)
**Overall Risk Level:** HIGH
**Complexity Score:** 8/10

---

## Executive Summary

The Admissions Portal is a **high-complexity feature (overall score: 8/10)** that introduces the first truly public-facing, unauthenticated data-entry surface in SIMS Plus. This fundamentally changes the security model: every other module assumes authenticated users with tenant context from JWT. The Admissions Portal must accept data from anonymous internet users, route it to the correct tenant via subdomain alone, process payments for application fees, handle document uploads from untrusted sources, and eventually perform an atomic conversion of applicant data into the existing student/guardian/finance data model.

The estimated effort is **81-102 developer-days** (realistic: 101-128 with 25% buffer), spanning **3 full sprints (6 weeks)** with 2 backend and 1-2 frontend developers.

The three highest-severity risks are:

1. **Public endpoint security** -- the application form creates an unauthenticated write path into tenant-scoped tables, requiring a novel approach to RLS context that has no existing precedent in the codebase
2. **Applicant-to-student conversion atomicity** -- the conversion touches 6+ tables (students, guardians, student_guardians, invoices, invoice_items, class enrollments) in a single transaction that must be idempotent and reversible
3. **Document upload abuse** -- anonymous file uploads are a spam and storage cost vector that requires CAPTCHA, virus scanning, and aggressive size/type constraints

---

## Component Complexity

| # | Component | Complexity | Estimate (dev-days) | Notes |
|---|-----------|------------|---------------------|-------|
| 1 | Data Model (new tables, enums, RLS) | 5 | 5-7 | ~8-10 new tables with RLS policies, indexes, and migration |
| 2 | Public Application Form (unauthenticated) | 8 | 10-12 | Hardest component. Must set tenant context from subdomain without auth. CAPTCHA, rate limiting, JSONB dynamic fields |
| 3 | Application Workflow Engine | 5 | 7-8 | State machine with 7 states, transition validation, status history |
| 4 | Admission Decision Management | 3 | 4-5 | Accept/reject/waitlist with bulk actions, letter generation |
| 5 | Applicant -> Student Conversion | 8 | 8-10 | Atomic creation across 6+ tables, guardian deduplication, idempotent |
| 6 | Re-enrollment for Existing Students | 3 | 4-5 | Campaign management, bulk SMS/email |
| 7 | Application Fee Payment | 5 | 6-8 | Adapted Paystack flow for anonymous applicants |
| 8 | Document Upload Handling | 5 | 5-6 | Anonymous uploads, virus scanning, per-tenant quotas |
| 9 | Admin Dashboard & Analytics | 3 | 6-8 | Pipeline view, conversion funnel, demographic breakdowns |
| 10 | Automated Notifications | 3 | 5-6 | SMS/email to non-platform-users (raw phone/email) |
| 11 | Admissions Settings / Form Builder | 5 | 5-7 | Admission periods, custom form fields (JSONB), entrance exam config |
| 12 | Frontend: Public Application Portal | 5 | 8-10 | Standalone branded pages, multi-step wizard, mobile-responsive |
| 13 | Tests (unit, integration, RLS, e2e) | 5 | 8-10 | 30-40% of total effort for multi-tenant features |

**Total Estimated Effort:** 81-102 developer-days (raw)
**Confidence Level:** Medium -- Public-form and conversion components have significant unknowns
**Recommended Buffer:** 25%
**Buffered Total:** 101-128 developer-days

---

## Risk Register

| ID | Risk | Category | Severity | Probability | Impact | Mitigation |
|----|------|----------|----------|-------------|--------|------------|
| R1 | Public endpoints bypass all existing auth guards. No pattern for unauthenticated writes to tenant-scoped tables exists in codebase. | Multi-Tenancy / Security | **Critical** | High | Cross-tenant data leakage or RLS bypass | Create `get_public_tenant_db()` dependency resolving tenant from `request.state.tenant_id` (set by TenantMiddleware). Add integration tests verifying cross-tenant isolation for applications. |
| R2 | Application form is a spam and abuse vector. Anonymous users can submit unlimited fake applications. | Security | **High** | High | S3 storage cost, admin fatigue, DDoS | reCAPTCHA v3, rate limit (3/IP/10min), per-tenant daily cap (100 default), honeypot fields, file size limits. |
| R3 | Applicant-to-student conversion not atomic. Creates records in 6+ tables. | Data Integrity | **Critical** | Medium | Orphaned records, billing inconsistencies | Single transaction with flush() between steps. Add `converted_student_id` to applications for idempotency. |
| R4 | Guardian deduplication during conversion. Guardian email uniqueness constraint may conflict. | Data Integrity | **High** | High | IntegrityError, duplicate guardians | Query by email+tenant_id first; link existing if found; fallback to phone+name matching. |
| R5 | Customizable form fields (JSONB) create validation complexity. | Technical | **High** | High | Invalid data stored, broken forms on schema change | JSON Schema validation with `jsonschema` library. Version schemas per admission period. |
| R6 | Application fee payments without user account. Existing payment flow assumes student_id + invoice_id. | Integration | **High** | Medium | Payment not linked to application | Separate `ApplicationPaymentService` with `application_payments` table. Store application_id in Paystack metadata. |
| R7 | Document uploads from untrusted sources may contain malware. | Security | **High** | Medium | Malware distribution to admin devices | Async virus scanning: upload to quarantine prefix, scan via ClamAV/Lambda, move on pass. |
| R8 | Applications table will grow large over time. | Performance | **Medium** | Medium | Slow admin dashboard, analytics timeouts | Composite indexes, cursor-based pagination, archive old periods. |
| R9 | Admission period date conflicts. Overlapping periods for same class/year. | Business Logic | **Medium** | Medium | Misrouted applications | PostgreSQL EXCLUDE constraint or service-level overlap validation. |
| R10 | Entrance exams cannot reuse existing exam infrastructure. FK constraints require student_id. | Technical | **High** | High | Must build separate tracking | Create `entrance_exams` and `entrance_exam_results` tables. Import scores post-conversion. |
| R11 | Notification dispatch to non-platform-users. NotificationDispatcher assumes User with user_id. | Integration | **Medium** | High | Silent notification failures | AdmissionNotificationService wrapping SMSService + email_service directly. |
| R12 | Public form needs school branding without auth. No public branding endpoint exists. | Technical | **Low** | High | Broken public form UI | New endpoint `GET /api/v1/admissions/school-info` returning branding only. Rate-limit heavily. |
| R13 | Re-enrollment campaigns may trigger bulk SMS exceeding current limits (MAX_BULK_RECIPIENTS=200). | Performance / Cost | **Medium** | Medium | Campaign failure, unexpected costs | Route through Celery with batching (50/batch, 5s delay). Require confirmation for >200 recipients. |
| R14 | Migration blast radius -- 8-10 new tables in one migration. | Quality | **Medium** | Low | Incomplete migration state | Split into 2-3 migrations. Test on staging clone before production. |
| R15 | CSSPS/WAEC integration for SHS admissions is a future dependency. | Compliance | **Medium** | Low | Potential conflict with centralized placements | Scope as "supplementary". Add optional `cssps_placement_number` field. Defer API integration. |
| R16 | Public form needs CSRF protection without session-based tokens. | Security | **Medium** | Medium | CSRF attacks submitting fake applications | Rely on reCAPTCHA v3 as primary protection (already needed for R2). Optional: double-submit cookie pattern. |

---

## Multi-Tenancy Risk Assessment

### New Tables Requiring RLS Policies (8-10 tables)

- `admission_periods` -- tenant_id + school_id scoped
- `application_forms` -- tenant_id + school_id scoped (form configuration)
- `applications` -- tenant_id + school_id scoped (core application record)
- `application_documents` -- tenant_id scoped (FK to applications)
- `application_payments` -- tenant_id scoped (FK to applications)
- `application_notes` -- tenant_id scoped (internal admin notes)
- `application_status_history` -- tenant_id scoped (audit trail)
- `entrance_exams` -- tenant_id + school_id scoped
- `entrance_exam_results` -- tenant_id scoped (FK to entrance_exams + applications)
- `re_enrollment_campaigns` -- tenant_id + school_id scoped

All follow existing RLS pattern:
```sql
ALTER TABLE [table] ENABLE ROW LEVEL SECURITY;
ALTER TABLE [table] FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON [table]
    FOR ALL
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
```

### Cross-Tenant Data Access Vectors

1. **Public form without proper tenant context** -- Safe failure with hardened RLS (INSERT rejected), but confusing error message
2. **Sequential application reference numbers** -- Could enumerate across tenants. Use tenant-scoped IDs or random UUIDs
3. **Document S3 paths** -- Must include tenant_id: `admissions/{tenant_id}/{application_id}/{filename}`
4. **Paystack webhook replay** -- Mitigated by tenant_id in metadata + HMAC signature verification

### Cache/Session Tenant Bleed Risks

- **Low risk** -- Portal is stateless. Redis tenant lookup caching already correctly scoped.
- **Potential risk**: Application form config cached in Redis must use key `{tenant_id}:admission_form:{form_id}`

### Background Job Tenant Context

- Notification Celery tasks: must receive + set tenant_id
- Document virus scanning: callback must restore tenant context
- Re-enrollment campaigns: must carry tenant_id + school_id

---

## Dependencies

### Internal Dependencies

| Component | Depends On | Status | Risk |
|-----------|------------|--------|------|
| Public application form | TenantMiddleware subdomain resolution | Ready | New public path prefix needed |
| Application fee payment | Paystack integration (online_payment.py) | Ready | Adapt for non-student payments |
| Applicant -> Student conversion | StudentService.create_student() | Ready | Existing pattern works |
| Guardian deduplication | Guardian model + uniqueness constraints | Ready | Email + phone matching |
| Invoice generation | InvoiceService | Ready | Needs student_id from same transaction |
| Document uploads | S3Service | Ready | Add admissions/ prefix + anonymous path |
| Notifications | SMSService + email_service | Ready | Bypass NotificationDispatcher |
| Re-enrollment | Messaging module (Sprint 18.5) | Ready | Use recipient_resolver pattern |
| Admin dashboard | Academic module (classes, terms) | Ready | Class list for admission period config |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| Google reCAPTCHA v3 | Google | Low | 1-2 days | Free tier. Test Ghana IP coverage. |
| Paystack | Paystack | Low | Already integrated | New metadata structure only |
| ClamAV / virus scanning | Self-hosted / AWS | Medium | 3-5 days | Lambda or Docker container |
| Hubtel/Arkesel SMS | Hubtel | Low | Already integrated | Different recipient source |
| CSSPS API (future) | GES/CSSPS | High | Unknown | Defer to Phase 4 |

---

## Sprint Planning Recommendation

### Sprint 19-20: MVP Admissions (4 weeks)

**Track A (Backend Dev 1) -- Core:**
1. Data model + migration (5d)
2. Public tenant-context dependency (1d)
3. Public school-info endpoint (1d)
4. Application submission endpoint with CAPTCHA (3d)
5. Application CRUD for admin (3d)
6. Workflow engine with state machine (3d)

**Track B (Backend Dev 2) -- Integrations:**
1. Application fee payment (Paystack) (4d)
2. Payment webhook handler (2d)
3. Document upload for anonymous users (3d)
4. Admission notification service (3d)
5. Admission settings endpoints (3d)

**Track C (Frontend Dev) -- UI:**
1. Public application form wizard (5d)
2. Payment flow (Paystack redirect/callback) (2d)
3. Admin applications list page (3d)
4. Admin application detail page (3d)
5. Admin admission settings page (3d)

### Sprint 21-22: Conversion + Advanced (4 weeks)

**Track A (Backend):**
1. Applicant-to-student conversion service (5d)
2. Guardian deduplication logic (3d)
3. Admission invoice generation (2d)
4. Entrance exam tables + service (4d)
5. Re-enrollment campaign service (3d)

**Track B (Frontend):**
1. Conversion UI (3d)
2. Entrance exam pages (3d)
3. Re-enrollment campaign UI (3d)
4. Analytics dashboard (4d)

**Track C (Testing):**
1. RLS isolation tests for all new tables (3d)
2. Public form + cross-tenant tests (3d)
3. Conversion atomicity tests (2d)
4. Payment webhook tests (2d)

### Sprint 23-24: Polish + Deferred (if needed)

- Custom form builder UI polish
- Advanced analytics
- CSSPS field support (optional)
- Performance optimization
- Documentation

---

## Critical Path

```
Migration (2d) --> Public tenant dep (1d) --> Application submission (3d) --> Workflow engine (2d)
                                                    |
                                              Application payment (3d)
                                                    |
Acceptance decisions (2d) --> Conversion service (5d) --> Invoice generation (2d) --> Testing (5d)
```

**Minimum Timeline (MVP):** 18 dev-days / 3 weeks with 2 developers
**Minimum Timeline (Full):** 35 dev-days / 5 weeks with 2 developers
**Realistic Timeline (Full + frontend + tests):** 85-106 dev-days / 6-8 weeks with 3 developers

---

## MVP vs Full Feature Scope

### MVP (Sprint 19-20)
- Public application form (basic fields, no custom form builder)
- Application submission with CAPTCHA
- Application fee payment via Paystack
- Document upload (PDF + images, no virus scan)
- Admin: view/filter/search applications
- Admin: change status (accept/reject/waitlist)
- SMS/email notifications on status changes
- School branding on public form

### Full Feature (Sprint 21-22)
- Applicant -> Student conversion (atomic)
- Guardian deduplication
- Admission invoice generation
- Entrance exam scheduling and results
- Re-enrollment campaigns
- Custom form builder (JSONB schema)
- Analytics dashboard
- Document virus scanning

### Deferred (Phase 4)
- CSSPS/WAEC integration
- Ghana Card verification
- Online entrance exam
- Application fee refunds
- Multi-language support
- Bulk application import

---

## Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| Google reCAPTCHA v3 API key | Bot protection | 1 day | Free |
| S3 storage expansion | Application documents | Already provisioned | ~$6/month for 50 schools |
| ClamAV or AWS Lambda | Virus scanning | 3-5 days | Lambda: ~$0.20/1000 scans |
| Additional Celery workers | Async tasks during peak | Already provisioned | ~$10/month additional |
| CloudFront cache | Public form assets | Already provisioned | Negligible |

---

## Key Codebase Files to Modify

| File | Modification |
|------|-------------|
| `/backend/app/middleware/tenant.py` (line 114) | Add `/api/v1/admissions/apply` to `PUBLIC_PATH_PREFIXES` |
| `/backend/app/api/deps.py` (line 39) | Add `/api/v1/admissions/` to `_PUBLIC_PATH_PREFIXES` |
| `/backend/app/middleware/rate_limit.py` (line 29) | Add admissions endpoints to `ENDPOINT_LIMITS` |
| `/backend/tests/conftest.py` (line 62) | Add 8-10 new tables to `TENANT_SCOPED_TABLES` |
| `/backend/scripts/verify_rls.py` | Add new tables to RLS verification |
| `/backend/app/models/__init__.py` | Import new admissions models |

## Technical Spikes (Pre-Sprint 19)

1. **Public tenant-scoped writes** (2 days) -- POC for unauthenticated INSERT into tenant-scoped tables
2. **Dynamic form validation** (1 day) -- jsonschema library performance with 50-field forms
3. **Anonymous Paystack payment** (2 days) -- Full flow with application_id in metadata
4. **ClamAV scanning latency** (1 day) -- Benchmark 5MB PDF scan time, sync vs async decision
