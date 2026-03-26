# Admissions Portal — Overview & Architecture

**Module:** Admissions Portal
**Phase:** 3 (Sprints 19-24)
**Complexity:** 8/10
**Author:** SIMS Plus Team
**Date:** 2026-02-25
**Status:** Implementation Plan

---

## 1. Executive Summary

The Admissions Portal introduces the first **public-facing, unauthenticated data-entry surface** in SIMS Plus. Prospective parents visit `{school}.simsplus.io/apply` to submit applications without creating an account. The module covers the full admissions lifecycle:

```
Inquiry → Application → Payment → Exam → Decision → Enrollment → Student Record
```

Plus re-enrollment campaigns for existing students.

**Key challenge:** Every other SIMS Plus module assumes authenticated users with tenant context from JWT. The Admissions Portal must accept data from anonymous internet users, route it to the correct tenant via subdomain alone, process payments for application fees, handle document uploads from untrusted sources, and perform an atomic conversion of applicant data into the student/guardian/finance data model.

### Scope

| In Scope | Out of Scope (Phase 4+) |
|----------|------------------------|
| Public application form with school branding | CSSPS/WAEC API integration |
| Application fee payment via Paystack | Ghana Card verification |
| Entrance exam scheduling + score entry | Online entrance exam (proctored) |
| Fee waiver and exam waiver | Application fee refunds |
| Admission decisions (single + bulk) | Multi-language form support |
| Applicant → Student atomic conversion | Bulk application import (CSV) |
| Class promotion (bulk promote/repeat/graduate) | ClamAV virus scanning (deferred) |
| Intent-to-return survey (optional, boarding/private) | Custom domain for application portal |
| Admin dashboard with pipeline analytics | |

### Effort Estimate

| Metric | Value |
|--------|-------|
| New database tables | 16 |
| New enum types | 6 |
| New backend files | ~35 |
| New frontend files | ~25 |
| Existing files to modify | 10 |
| Pydantic schemas | ~45 |
| API endpoints | ~30 |
| Test cases | 80+ |
| Estimated dev-days (raw) | 85-106 |
| Estimated dev-days (with 25% buffer) | 106-133 |
| Sprints | 3 (6 weeks) |

---

## 2. Architecture Decisions

### Decision 1: Applications are Separate from Students

Applications live in their own `applications` table. Only when an admin explicitly enrolls an accepted applicant does the system create a Student record. This prevents polluting the student table with rejected/withdrawn applicants and keeps the admissions pipeline cleanly separated.

### Decision 2: Public Form Uses Subdomain-Resolved Tenant Context

The existing `TenantMiddleware` already extracts the subdomain from the request URL and sets `request.state.tenant_id`. A new `get_public_tenant_db()` dependency reads this value and creates a tenant-scoped database session **without** requiring JWT authentication. This reuses the existing middleware infrastructure rather than creating a parallel tenant resolution path.

### Decision 3: Single Alembic Migration for All 16 Tables

All admissions tables are created in a single migration (`20260303_0100_admissions_tables.py`) to avoid branch conflicts and ensure atomic rollback. The migration includes table creation, enum types, RLS policies, indexes, and grants.

### Decision 4: JSONB Form Configuration (Not Hardcoded Fields)

Schools customize application fields via `admission_form_configs.form_schema` (JSONB column). The schema follows JSON Schema format and is validated at submission time using the `jsonschema` library. This allows each school to add custom fields (e.g., "Previous School", "Medical Conditions") without database schema changes.

### Decision 5: Tracking Code as Public Identifier

Applications are identified publicly by a `tracking_code` (`secrets.token_urlsafe(48)` — 384 bits of entropy) rather than UUID. This prevents enumeration attacks. The UUID primary key is used internally for admin operations.

### Decision 6: Fee Waiver and Exam Waiver as Boolean Flags

Rather than complex conditional logic, simple boolean flags (`fee_waived`, `exam_waived`) on the `applications` table control whether payment and entrance exam steps are required. Admins toggle these via dedicated endpoints.

### Decision 7: Guardian Deduplication on Enrollment

When converting an applicant to a student, the system checks for existing guardians by email OR phone within the same tenant before creating new records. This prevents duplicate guardian entries when siblings apply.

### Decision 8: Idempotent Enrollment via `converted_student_id`

The `applications.converted_student_id` column (nullable FK to `students`) serves as an idempotency guard. If non-null, the application has already been enrolled and the enrollment endpoint returns the existing student rather than creating a duplicate.

### Decision 9: Cloudflare Turnstile (Not reCAPTCHA)

Cloudflare Turnstile is chosen over Google reCAPTCHA v3 because:
- Better privacy (no tracking cookies)
- No user-facing challenges in most cases
- Already using Cloudflare for DNS/CDN
- Free tier sufficient for our volume

### Decision 10: Notification via SMS/Email Services Directly

The existing `NotificationDispatcher` requires a `user_id` (platform User). Applicant guardians don't have accounts. Instead, `AdmissionNotificationService` wraps `SMSService.send_sms(recipient_phone)` and `EmailComposeService.send_email(recipient_email)` directly — both already support raw contact info without User records.

---

## 3. Data Model (16 Tables, 6 Enums)

### 3.1 New Enum Types

All enums follow the project convention: `class Name(str, Enum)` with uppercase Python members and lowercase database values. PostgreSQL type names are all lowercase with no underscores.

| Python Class | PostgreSQL Type | Values |
|-------------|----------------|--------|
| `AdmissionApplicationStatus` | `applicationstatus` | draft, submitted, under_review, shortlisted, exam_scheduled, exam_completed, offered, accepted, waitlisted, rejected, enrolled, withdrawn, expired, deferred |
| `AdmissionPeriodStatus` | `admissionperiodstatus` | draft, open, closed, archived |
| `EntranceExamStatus` | `entranceexamstatus` | scheduled, in_progress, completed, cancelled |
| `DecisionType` | `decisiontype` | accepted, rejected, waitlisted, deferred |
| `PromotionBatchStatus` | `promotionbatchstatus` | draft, preview, in_progress, completed, failed |
| `PromotionAction` | `promotionaction` | promote, repeat, graduate, withdraw |

### 3.2 Table Definitions

All tables inherit `TenantMixin` (adds `tenant_id` FK with CASCADE) and `SoftDeleteMixin` (adds `deleted_at`). All have `id` (UUID PK), `created_at`, `updated_at`.

#### Table 1: `admission_periods`
**Purpose:** Intake windows (e.g., "2026/2027 Admissions for Form 1")

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | RLS scope |
| school_id | UUID | FK→schools.id, CASCADE, NOT NULL | |
| academic_year_id | UUID | FK→academic_years.id, NOT NULL | Target academic year |
| name | VARCHAR(255) | NOT NULL | e.g., "2026/2027 Admissions" |
| description | TEXT | NULLABLE | Rich text description |
| start_date | DATE | NOT NULL | Applications open |
| end_date | DATE | NOT NULL | Applications close |
| status | admissionperiodstatus | NOT NULL, default 'draft' | draft/open/closed/archived |
| application_fee_amount | NUMERIC(10,2) | NULLABLE | Fee amount (null = free) |
| application_fee_required | BOOLEAN | NOT NULL, default false | Whether payment needed |
| entrance_exam_required | BOOLEAN | NOT NULL, default false | Whether exam needed |
| max_applications | INTEGER | NULLABLE | Cap on total applications |
| target_classes | JSONB | NOT NULL, default '[]' | Array of class IDs this period accepts |
| created_at | TIMESTAMP(TZ) | NOT NULL, default now() | |
| updated_at | TIMESTAMP(TZ) | NOT NULL, default now() | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | Soft delete |

**Indexes:** `(tenant_id, school_id)`, `(tenant_id, academic_year_id)`, `(tenant_id, status)`

#### Table 2: `admission_form_configs`
**Purpose:** Customizable form field definitions per admission period

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| school_id | UUID | FK→schools.id, CASCADE, NOT NULL | |
| admission_period_id | UUID | FK→admission_periods.id, CASCADE, NOT NULL | One config per period |
| form_schema | JSONB | NOT NULL, default '{}' | JSON Schema for custom fields |
| required_documents | JSONB | NOT NULL, default '[]' | Array of required doc types |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Unique constraints:** `UNIQUE(tenant_id, admission_period_id)`
**Indexes:** `(tenant_id, admission_period_id)`

#### Table 3: `applications`
**Purpose:** Core application record — the central entity of the module

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| school_id | UUID | FK→schools.id, CASCADE, NOT NULL | |
| admission_period_id | UUID | FK→admission_periods.id, NOT NULL | |
| tracking_code | VARCHAR(100) | NOT NULL | Public identifier (token_urlsafe(48)) |
| applicant_first_name | VARCHAR(100) | NOT NULL | |
| applicant_last_name | VARCHAR(100) | NOT NULL | |
| applicant_other_names | VARCHAR(100) | NULLABLE | |
| date_of_birth | DATE | NOT NULL | |
| gender | VARCHAR(10) | NOT NULL | male/female |
| nationality | VARCHAR(100) | NULLABLE | |
| target_class_id | UUID | FK→classes.id, NOT NULL | Class applying to |
| status | applicationstatus | NOT NULL, default 'draft' | Current workflow state |
| custom_fields | JSONB | NOT NULL, default '{}' | Validated against form_schema |
| fee_waived | BOOLEAN | NOT NULL, default false | Skip payment requirement |
| exam_waived | BOOLEAN | NOT NULL, default false | Skip exam requirement |
| converted_student_id | UUID | FK→students.id, NULLABLE | Set on enrollment (idempotency) |
| applicant_photo_url | VARCHAR(500) | NULLABLE | S3 presigned URL |
| previous_school | VARCHAR(255) | NULLABLE | |
| medical_info | TEXT | NULLABLE | |
| submitted_at | TIMESTAMP(TZ) | NULLABLE | When moved from draft→submitted |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Unique constraints:** `UNIQUE(tenant_id, tracking_code)`
**Indexes:** `(tenant_id, school_id)`, `(tenant_id, admission_period_id)`, `(tenant_id, status)`, `(tenant_id, target_class_id)`, `(tenant_id, converted_student_id)` WHERE NOT NULL

#### Table 4: `application_guardians`
**Purpose:** Guardian/parent info submitted with the application

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | |
| first_name | VARCHAR(100) | NOT NULL | |
| last_name | VARCHAR(100) | NOT NULL | |
| phone | VARCHAR(20) | NOT NULL | Primary contact |
| email | VARCHAR(255) | NULLABLE | |
| relationship | VARCHAR(50) | NOT NULL | father/mother/guardian/other |
| is_primary | BOOLEAN | NOT NULL, default false | Primary contact for this app |
| occupation | VARCHAR(255) | NULLABLE | |
| address | TEXT | NULLABLE | |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, application_id)`

#### Table 5: `application_documents`
**Purpose:** Files uploaded with the application (birth cert, photos, transcripts)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | |
| document_type | VARCHAR(100) | NOT NULL | birth_certificate, passport_photo, transcript, etc. |
| file_name | VARCHAR(255) | NOT NULL | Original filename |
| s3_key | VARCHAR(500) | NOT NULL | `admissions/{tenant_id}/{application_id}/{uuid}.{ext}` |
| file_size | INTEGER | NOT NULL | Bytes (max 5MB = 5242880) |
| mime_type | VARCHAR(100) | NOT NULL | application/pdf, image/jpeg, image/png |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, application_id)`

#### Table 6: `application_payments`
**Purpose:** Application fee payment records

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | |
| amount | NUMERIC(10,2) | NOT NULL | Payment amount |
| currency | VARCHAR(3) | NOT NULL, default 'GHS' | |
| payment_method | VARCHAR(50) | NULLABLE | mobile_money, card, bank_transfer |
| provider_reference | VARCHAR(255) | NULLABLE | Paystack transaction reference |
| status | VARCHAR(20) | NOT NULL, default 'pending' | pending/completed/failed/refunded |
| paid_at | TIMESTAMP(TZ) | NULLABLE | When payment confirmed |
| metadata | JSONB | NOT NULL, default '{}' | Provider-specific data |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Unique constraints:** `UNIQUE(tenant_id, provider_reference)` WHERE NOT NULL
**Indexes:** `(tenant_id, application_id)`

#### Table 7: `application_status_history`
**Purpose:** Audit trail of all status transitions

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | |
| from_status | applicationstatus | NULLABLE | NULL for initial creation |
| to_status | applicationstatus | NOT NULL | |
| changed_by | UUID | FK→users.id, NULLABLE | NULL for public actions (submit) |
| reason | TEXT | NULLABLE | Why the change was made |
| created_at | TIMESTAMP(TZ) | NOT NULL, default now() | |

**Note:** No `updated_at` or `deleted_at` — this is an append-only audit log.

**Indexes:** `(tenant_id, application_id)`, `(tenant_id, created_at)`

#### Table 8: `application_notes`
**Purpose:** Internal reviewer notes on applications

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | |
| author_id | UUID | FK→users.id, NOT NULL | Who wrote the note |
| content | TEXT | NOT NULL | Note content |
| is_internal | BOOLEAN | NOT NULL, default true | Internal only (not shown to applicant) |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, application_id)`

#### Table 9: `entrance_exams`
**Purpose:** Exam session definitions (date, venue, capacity)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| school_id | UUID | FK→schools.id, CASCADE, NOT NULL | |
| admission_period_id | UUID | FK→admission_periods.id, CASCADE, NOT NULL | |
| name | VARCHAR(255) | NOT NULL | e.g., "Entrance Exam — Batch 1" |
| exam_date | DATE | NOT NULL | |
| start_time | TIME | NULLABLE | |
| end_time | TIME | NULLABLE | |
| venue | VARCHAR(255) | NOT NULL | |
| capacity | INTEGER | NOT NULL | Max seats |
| status | entranceexamstatus | NOT NULL, default 'scheduled' | |
| instructions | TEXT | NULLABLE | Instructions for candidates |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, admission_period_id)`, `(tenant_id, exam_date)`

#### Table 10: `entrance_exam_registrations`
**Purpose:** Links applicants to exam sessions with seat assignment

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| entrance_exam_id | UUID | FK→entrance_exams.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | |
| seat_number | VARCHAR(20) | NULLABLE | Assigned seat |
| attended | BOOLEAN | NOT NULL, default false | Marked by admin |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, entrance_exam_id)`, `(tenant_id, application_id)` UNIQUE (one registration per applicant)

#### Table 11: `entrance_exam_results`
**Purpose:** Exam scores per applicant

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| entrance_exam_id | UUID | FK→entrance_exams.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | |
| score | NUMERIC(6,2) | NOT NULL | Achieved score |
| max_score | NUMERIC(6,2) | NOT NULL | Maximum possible |
| grade | VARCHAR(10) | NULLABLE | Optional letter grade |
| passed | BOOLEAN | NOT NULL, default false | Admin determination |
| remarks | TEXT | NULLABLE | |
| scored_by | UUID | FK→users.id, NULLABLE | Who entered the score |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, entrance_exam_id)`, `(tenant_id, application_id)` UNIQUE

#### Table 12: `admission_decisions`
**Purpose:** Formal admission decision record

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| application_id | UUID | FK→applications.id, CASCADE, NOT NULL | One decision per application |
| decision_type | decisiontype | NOT NULL | accepted/rejected/waitlisted/deferred |
| decided_by | UUID | FK→users.id, NOT NULL | Admin who made the decision |
| offered_class_id | UUID | FK→classes.id, NULLABLE | May differ from target_class |
| conditions | TEXT | NULLABLE | Conditional offer terms |
| decision_date | DATE | NOT NULL | |
| response_deadline | DATE | NULLABLE | Deadline for applicant to accept |
| decision_letter_url | VARCHAR(500) | NULLABLE | Generated PDF letter |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Unique constraints:** `UNIQUE(tenant_id, application_id)`
**Indexes:** `(tenant_id, application_id)`, `(tenant_id, decision_type)`

#### Table 13: `class_promotions`
**Purpose:** Batch class promotion operation record (end-of-year promotion)

This is the primary tool for the Ghanaian academic year transition. Students are automatically promoted to the next class unless marked for repeat, graduation, or withdrawal.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| school_id | UUID | FK→schools.id, CASCADE, NOT NULL | |
| source_academic_year_id | UUID | FK→academic_years.id, NOT NULL | Current academic year |
| target_academic_year_id | UUID | FK→academic_years.id, NOT NULL | Next academic year |
| name | VARCHAR(255) | NOT NULL | e.g., "2025/2026 → 2026/2027 Promotion" |
| status | promotionbatchstatus | NOT NULL, default 'draft' | draft/preview/in_progress/completed/failed |
| total_students | INTEGER | NOT NULL, default 0 | Total students in batch |
| promoted_count | INTEGER | NOT NULL, default 0 | Successfully promoted |
| repeated_count | INTEGER | NOT NULL, default 0 | Marked for repeat |
| graduated_count | INTEGER | NOT NULL, default 0 | Graduated (terminal class) |
| withdrawn_count | INTEGER | NOT NULL, default 0 | Withdrawn/transferred |
| executed_at | TIMESTAMP(TZ) | NULLABLE | When promotion was executed |
| executed_by | UUID | FK→users.id, NULLABLE | Admin who executed |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, school_id)`, `(tenant_id, source_academic_year_id)`, `(tenant_id, target_academic_year_id)`

#### Table 14: `class_promotion_entries`
**Purpose:** Per-student promotion decision within a batch

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| promotion_id | UUID | FK→class_promotions.id, CASCADE, NOT NULL | |
| student_id | UUID | FK→students.id, CASCADE, NOT NULL | |
| source_class_id | UUID | FK→classes.id, NOT NULL | Current class |
| source_section_id | UUID | FK→class_sections.id, NULLABLE | Current section |
| target_class_id | UUID | FK→classes.id, NULLABLE | Next class (null for graduated/withdrawn) |
| target_section_id | UUID | FK→class_sections.id, NULLABLE | Assigned section in new class |
| action | promotionaction | NOT NULL, default 'promote' | promote/repeat/graduate/withdraw |
| reason | TEXT | NULLABLE | Reason for repeat/withdraw |
| processed | BOOLEAN | NOT NULL, default false | Whether this entry has been executed |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, promotion_id)`, `(tenant_id, student_id, promotion_id)` UNIQUE

**New Enum: `promotionbatchstatus`** — draft, preview, in_progress, completed, failed
**New Enum: `promotionaction`** — promote, repeat, graduate, withdraw

#### Table 15: `return_intent_campaigns`
**Purpose:** Optional intent-to-return survey for boarding/private schools (NOT a gate — purely informational)

In Ghana, students are automatically promoted. This feature is optional for schools that want to gauge how many students plan to return, especially boarding schools with limited bed space. It does NOT block promotion or enrollment.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| school_id | UUID | FK→schools.id, CASCADE, NOT NULL | |
| academic_year_id | UUID | FK→academic_years.id, NOT NULL | Target year |
| name | VARCHAR(255) | NOT NULL | e.g., "2026/2027 Return Intent Survey" |
| target_classes | JSONB | NOT NULL, default '[]' | Array of class IDs |
| message_template | TEXT | NULLABLE | SMS/email template |
| status | VARCHAR(20) | NOT NULL, default 'draft' | draft/sent/completed |
| sent_at | TIMESTAMP(TZ) | NULLABLE | When notifications sent |
| sent_count | INTEGER | NOT NULL, default 0 | Number of notifications sent |
| deadline | DATE | NULLABLE | Response deadline |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, school_id)`, `(tenant_id, academic_year_id)`

#### Table 16: `return_intents`
**Purpose:** Per-student intent-to-return response

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants.id, CASCADE, NOT NULL | |
| school_id | UUID | FK→schools.id, CASCADE, NOT NULL | |
| campaign_id | UUID | FK→return_intent_campaigns.id, CASCADE, NOT NULL | |
| student_id | UUID | FK→students.id, CASCADE, NOT NULL | |
| academic_year_id | UUID | FK→academic_years.id, NOT NULL | |
| intent | VARCHAR(20) | NOT NULL, default 'pending' | pending/returning/not_returning/undecided |
| responded_at | TIMESTAMP(TZ) | NULLABLE | |
| responded_by | UUID | FK→users.id, NULLABLE | Parent who responded |
| reason | TEXT | NULLABLE | Reason if not returning |
| notes | TEXT | NULLABLE | |
| created_at | TIMESTAMP(TZ) | NOT NULL | |
| updated_at | TIMESTAMP(TZ) | NOT NULL | |
| deleted_at | TIMESTAMP(TZ) | NULLABLE | |

**Indexes:** `(tenant_id, campaign_id)`, `(tenant_id, student_id, academic_year_id)` UNIQUE

### 3.3 Entity Relationship Summary

```
academic_years ─────────┬──→ admission_periods ──→ admission_form_configs
                        │           │
                        │           ├──→ applications ──┬──→ application_guardians
                        │           │         │         ├──→ application_documents
                        │           │         │         ├──→ application_payments
                        │           │         │         ├──→ application_status_history
                        │           │         │         ├──→ application_notes
                        │           │         │         └──→ admission_decisions
                        │           │         │
                        │           │         └──→ students (via converted_student_id)
                        │           │
                        │           └──→ entrance_exams ──→ entrance_exam_registrations
                        │                                 └──→ entrance_exam_results
                        │
                        ├──→ class_promotions ──→ class_promotion_entries ──→ students
                        │
                        └──→ return_intent_campaigns ──→ return_intents ──→ students
```

---

## 4. Application Status Machine

### 4.1 Valid Transitions

```python
VALID_TRANSITIONS: dict[AdmissionApplicationStatus, list[AdmissionApplicationStatus]] = {
    AdmissionApplicationStatus.DRAFT: [AdmissionApplicationStatus.SUBMITTED, AdmissionApplicationStatus.WITHDRAWN],
    AdmissionApplicationStatus.SUBMITTED: [AdmissionApplicationStatus.UNDER_REVIEW, AdmissionApplicationStatus.WITHDRAWN],
    AdmissionApplicationStatus.UNDER_REVIEW: [
        AdmissionApplicationStatus.SHORTLISTED,
        AdmissionApplicationStatus.REJECTED,
        AdmissionApplicationStatus.WAITLISTED,
        AdmissionApplicationStatus.DEFERRED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.SHORTLISTED: [
        AdmissionApplicationStatus.EXAM_SCHEDULED,
        AdmissionApplicationStatus.OFFERED,       # When exam_waived=true
        AdmissionApplicationStatus.REJECTED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.EXAM_SCHEDULED: [AdmissionApplicationStatus.EXAM_COMPLETED, AdmissionApplicationStatus.WITHDRAWN],
    AdmissionApplicationStatus.EXAM_COMPLETED: [
        AdmissionApplicationStatus.OFFERED,
        AdmissionApplicationStatus.REJECTED,
        AdmissionApplicationStatus.WAITLISTED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.OFFERED: [
        AdmissionApplicationStatus.ACCEPTED,
        AdmissionApplicationStatus.EXPIRED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.ACCEPTED: [AdmissionApplicationStatus.ENROLLED, AdmissionApplicationStatus.WITHDRAWN],
    AdmissionApplicationStatus.WAITLISTED: [AdmissionApplicationStatus.OFFERED, AdmissionApplicationStatus.REJECTED, AdmissionApplicationStatus.WITHDRAWN],
    AdmissionApplicationStatus.REJECTED: [],      # Terminal
    AdmissionApplicationStatus.ENROLLED: [],      # Terminal
    AdmissionApplicationStatus.WITHDRAWN: [],     # Terminal
    AdmissionApplicationStatus.EXPIRED: [AdmissionApplicationStatus.OFFERED],  # Can re-offer
    AdmissionApplicationStatus.DEFERRED: [AdmissionApplicationStatus.UNDER_REVIEW, AdmissionApplicationStatus.WITHDRAWN],
}
```

### 4.2 Transition Rules

| Rule | Description |
|------|-------------|
| **Fee gate** | DRAFT → SUBMITTED requires: `fee_waived=true` OR `application_payments.status='completed'` |
| **Exam gate** | SHORTLISTED → OFFERED requires: `exam_waived=true` OR exam result exists |
| **Enrollment gate** | ACCEPTED → ENROLLED requires: `converted_student_id` is NULL (idempotency) |
| **Withdrawal** | Allowed from any non-terminal state (REJECTED, ENROLLED, WITHDRAWN are terminal) |
| **Expiry** | OFFERED → EXPIRED triggered by background job when `response_deadline` passes |
| **Re-offer** | EXPIRED → OFFERED allowed (admin can extend deadline and re-offer) |

---

## 5. API Overview

### 5.1 Public Endpoints (8 endpoints, unauthenticated)

Base: `/api/v1/admissions/public`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/school-info` | School branding for form theming |
| GET | `/periods` | Open admission periods |
| GET | `/periods/{id}/form` | Form config + required docs |
| POST | `/applications` | Submit application |
| GET | `/applications/{tracking_code}/status` | Check status (minimal data) |
| POST | `/applications/{tracking_code}/documents` | Upload document |
| POST | `/applications/{tracking_code}/pay` | Initialize payment |
| POST | `/webhook/paystack` | Payment webhook |

### 5.2 Admin Endpoints (~22 endpoints, authenticated)

Base: `/api/v1/admissions`

**Periods (6):** CRUD + status change + form config
**Applications (6):** List, detail, status change, notes, fee waiver, exam waiver
**Exams (5):** CRUD, register applicants, enter results
**Decisions (2):** Single + bulk decide
**Enrollment (2):** Single + bulk enroll
**Class Promotion (5):** Create batch, preview, execute, list, detail
**Return Intent Survey (5):** Campaign CRUD + send + student list (optional feature)
**Dashboard (2):** Stats + demographics

### 5.3 Permissions

| Permission | Roles |
|------------|-------|
| `admissions.*` (wildcard) | platform_admin, chain_admin, school_admin |
| `admissions.read` | academic_head |
| `admissions.review` | academic_head |
| `admissions.manage` | (via wildcard only) |
| `admissions.decide` | (via wildcard only) |
| `admissions.enroll` | (via wildcard only) |

---

## 6. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| **Public write path to RLS tables** | `get_public_tenant_db()` sets tenant context from subdomain; RLS enforced at DB level |
| **Spam/abuse on application form** | Cloudflare Turnstile (fail-closed) + rate limit (3/min per IP) + per-tenant daily cap (500/day default) |
| **Tracking code enumeration** | 384 bits entropy (`token_urlsafe(48)`); status endpoint returns minimal data |
| **Status endpoint PII leakage** | Returns ONLY: status, first name, submitted_at, last_updated_at |
| **Document upload abuse** | Max 5MB, PDF/JPG/PNG only, magic byte validation, max 5 docs per application |
| **S3 path isolation** | `admissions/{tenant_id}/{application_id}/{uuid}.{ext}` — no public read |
| **Payment webhook spoofing** | HMAC-SHA512 signature verification + tenant_id cross-validation against DB record |
| **Cross-tenant data leakage** | RLS on all 16 tables + defense-in-depth `tenant_id` filtering in services |
| **CSRF on public form** | Turnstile token serves as CSRF protection (single-use, time-limited) |
| **Admission period overlap** | Service-level validation prevents overlapping periods for same classes |

---

## 7. File Organization Summary

### Backend (~35 new files)

```
backend/
├── app/
│   ├── models/admissions/          # 7 files (6 model files + __init__.py)
│   ├── schemas/admissions.py       # 1 file (~45 schemas)
│   ├── services/admissions/        # 9 files (8 services + __init__.py)
│   ├── api/v1/endpoints/admissions/# 11 files (10 endpoints + __init__.py)
│   └── utils/turnstile.py          # 1 file
├── alembic/versions/
│   └── 20260303_0100_admissions_tables.py  # 1 migration
└── tests/
    └── admissions/                 # 8 test files
```

### Frontend (~25 new files)

```
frontend/
├── app/(auth)/apply/              # 5 pages
├── app/(dashboard)/admissions/    # 10 pages
├── components/admissions/         # 8 components
├── actions/admissions.action.ts   # 1 file
└── types/admissions.type.ts       # 1 file
```

### Existing Files to Modify (10)

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Import admissions models |
| `backend/app/services/auth.py` | Add admissions permissions |
| `backend/app/api/v1/router.py` | Register admissions router |
| `backend/app/api/deps.py` | Add `get_public_tenant_db()` + public paths |
| `backend/app/middleware/tenant.py` | Add public paths |
| `backend/app/middleware/rate_limit.py` | Add rate limit entries |
| `backend/app/core/config.py` | Add Turnstile config |
| `backend/requirements.txt` | Add `jsonschema` |
| `backend/tests/conftest.py` | Add 16 tables to TENANT_SCOPED_TABLES |
| `backend/scripts/verify_rls.py` | Add 16 tables |
| `frontend/components/dashboard/app-sidebar.tsx` | Add Admissions nav group |

---

## 8. Sprint Plan Overview

| Sprint | Focus | Key Deliverables |
|--------|-------|-----------------|
| **19-20** | Core Backend + Public Form | 16 models, migration, 10 services, schemas, all endpoints, public form frontend |
| **21-22** | Admin Dashboard + Advanced | Exam/decision/class promotion/return intent services, admin frontend pages, parent portal integration |
| **23-24** | Testing + Reviews + Polish | 90+ tests, security review, tenancy review, code review, DevOps |

Detailed task breakdowns for each sprint are in the subsequent documents.
