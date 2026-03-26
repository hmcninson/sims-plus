# Enrollment Management Gap Closure — Implementation Plan

**Author:** SIMS Plus Engineering
**Date:** 2026-03-24
**Status:** Approved for Implementation
**Estimated Effort:** 4 Phases (8 weeks, 2 developers)
**Branch:** `feat/enrollment-gap-closure`

---

## Table of Contents

| Document | Covers |
|----------|--------|
| [00-overview.md](00-overview.md) | This file — gap matrix, architecture decisions, CSSPS format, migration chain |
| [01-phase-1-inquiry-and-interviews.md](01-phase-1-inquiry-and-interviews.md) | Inquiry/Lead Management + Interview/Screening |
| [02-phase-2-letters-offers-waitlist.md](02-phase-2-letters-offers-waitlist.md) | Admission Letters, Offer Acceptance, Waitlist Ranking |
| [03-phase-3-enrollment-confirmation-cssps.md](03-phase-3-enrollment-confirmation-cssps.md) | Enrollment Confirmation Workflow + CSSPS Import |
| [04-phase-4-capacity-reenrollment-tours-analytics.md](04-phase-4-capacity-reenrollment-tours-analytics.md) | Capacity Planning, Re-enrollment, Tours, Analytics |

---

## 1. Executive Summary

The existing admissions module is production-ready with **16 tables, 11 services, 13 endpoint files, and 11 test files** covering application submission through enrollment. This gap closure addresses **9 identified gaps** across inquiry management, interview scheduling, admission letters, offer acceptance, enrollment confirmation, re-enrollment, capacity planning, and analytics.

### What Already Exists

| Area | Status | Tables | Endpoints |
|------|--------|--------|-----------|
| Application lifecycle (14-state machine) | Complete | 6 | 14 |
| Applicant accounts (register, login, dashboard) | Complete | 0 (reuses users) | 18 |
| Entrance exams (schedule, register, score) | Complete | 3 | 9 |
| Admission decisions (accept/reject/waitlist/defer) | Complete | 1 | 3 |
| Enrollment (atomic applicant-to-student conversion) | Complete | 0 | 2 |
| Class promotions (end-of-year) | Complete | 2 | 8 |
| Return intent surveys | Complete | 2 | 5 |
| Paystack payment integration | Complete | 1 | 3 |
| Document uploads (S3) | Complete | 1 | 2 |
| Admin dashboard + analytics | Partial | 0 | 2 |

### What This Plan Adds

| Phase | New Tables | Modified Tables | New Endpoints | New Tests | Celery Tasks |
|-------|-----------|----------------|---------------|-----------|-------------|
| Phase 1 | 5 | 3 | 25 | ~46 | 0 |
| Phase 2 | 0 | 3 | 8 | ~40 | 2 |
| Phase 3 | 2 | 2 | 9 | ~42 | 0 |
| Phase 4 | 3 | 1 | 19 | ~44 | 0 |
| **Total** | **10** | **9** (unique) | **~61** | **~172** | **2** |

---

## 2. Requirement-to-Implementation Matrix

Every requirement from the spec is mapped below. Green = already implemented. Yellow = this plan. Red = deferred.

### 9.1 Inquiry and Lead Management

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-001 | Inquiry capture form with lead source tracking | Must | GAP | 1 | New `inquiries` table + InquiryService.create() + admin form page |
| EM-002 | Prospective parent/student profile creation | Must | GAP | 1 | Inquiry model stores student + guardian info; converts to Application on progression |
| EM-003 | Inquiry source tracking for marketing ROI | Should | GAP | 1 | `InquirySource` enum (website, walk_in, phone, referral, event, social_media, other) |
| EM-004 | Lead status workflow | Must | GAP | 1 | `InquiryStatus` enum (new, contacted, interested, applied, enrolled, lost) with transition validation |
| EM-005 | Follow-up task assignment and reminders | Should | GAP | 1 | `inquiry_follow_ups` table with assigned_to, due_date, priority |
| EM-006 | Communication history per inquiry | Should | GAP | 1 | `inquiry_communications` table (append-only log: sms, email, phone, in_person) |
| EM-007 | Inquiry-to-application conversion tracking | Should | GAP | 1 | `converted_application_id` FK on inquiries + analytics service |
| EM-008 | Bulk inquiry import from events/fairs | Could | GAP | 1 | InquiryService.bulk_import() with CSV/Excel parser, dedup by phone |
| EM-009 | Duplicate inquiry detection | Should | GAP | 1 | InquiryService.check_duplicate() matches on phone + email within tenant |

### 9.2 School Tours and Open Days

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-010 | Open day event creation and scheduling | Should | GAP | 4 | New `school_events` table + EventService.create_event() |
| EM-011 | Online registration with capacity management | Should | GAP | 4 | `event_registrations` table + capacity check on register |
| EM-012 | Individual school tour booking | Should | GAP | 4 | `event_type="tour"` on school_events, same CRUD |
| EM-013 | Tour guide/staff assignment | Could | GAP | 4 | `guide_id` FK to users on school_events |
| EM-014 | Attendance tracking for events | Should | GAP | 4 | `attended` boolean on event_registrations + mark endpoint |
| EM-015 | Post-event follow-up automation | Could | DEFER | - | Requires Celery Beat scheduling; deferred to Phase 5 |
| EM-016 | Event capacity limits and waitlists | Should | GAP | 4 | `capacity` on school_events; registration rejected when full |

### 9.3 Application Processing

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-020 | Online application form (public, mobile responsive) | Must | DONE | - | Public portal at /apply with multi-step wizard |
| EM-021 | Configurable application form fields per level | Must | DONE | - | `admission_form_configs` with JSONB schema |
| EM-022 | Sibling applications | Should | DONE | - | Applicant accounts support multi-child applications |
| EM-023 | Required document checklist per application type | Must | DONE | - | `required_documents` JSONB on form config |
| EM-024 | Document upload with file type validation | Must | DONE | - | S3 upload + magic byte validation + 5MB limit |
| EM-025 | Application fee payment via Mobile Money | Must | DONE | - | Paystack integration (MTN MoMo, Vodafone Cash, AirtelTigo) |
| EM-026 | Application fee waiver management | Should | DONE | - | `fee_waived` flag + admin waiver endpoint |
| EM-027 | Application status tracking | Must | DONE | - | 14-state machine with ApplicationStatusHistory audit |
| EM-028 | Applicant portal for self-service | Should | DONE | - | /apply/dashboard with my-applications, drafts, print |
| EM-029 | Incomplete application reminders (automated) | Should | GAP | 2 | Celery Beat task `send_incomplete_application_reminders` |
| EM-030 | Application acknowledgment auto-email/SMS | Must | DONE | - | AdmissionNotificationService.notify_application_submitted() |
| EM-031 | Application reference number generation | Must | DONE | - | `tracking_code` via secrets.token_urlsafe(48) |
| EM-033 | CSSPS placement data import for SHS | Must | GAP | 3 | CSSPSImportService with defined file format (see Section 5) |

### 9.4 Selection and Screening

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-040 | Entrance examination scheduling | Should | DONE | - | `entrance_exams` table + EntranceExamService |
| EM-041 | Exam venue/session management with capacity | Should | DONE | - | venue, capacity, seat_number fields |
| EM-042 | Entrance exam score recording | Must | DONE | - | `entrance_exam_results` + bulk score entry endpoint |
| EM-043 | Interview scheduling for selective schools | Should | GAP | 1 | New `interviews` table + InterviewService.schedule() |
| EM-044 | Interview feedback/scoring form | Should | GAP | 1 | InterviewService.record_feedback() with JSONB scoring_criteria |
| EM-045 | Assessment criteria configuration (weighted scoring) | Should | GAP | 1 | JSONB `scoring_criteria` on interviews + `weight` on exam results |
| EM-048 | Previous academic records evaluation | Should | GAP | 1 | Screening checklist item category "academic" |
| EM-049 | Screening checklist completion tracking | Should | GAP | 1 | New `screening_checklists` table with progress tracking |

### 9.5 Admission Decisions and Offers

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-050 | Admission decision recording | Must | DONE | - | `admission_decisions` with DecisionType enum |
| EM-051 | Conditional admission support | Should | DONE | - | `conditions` text field on admission_decisions |
| EM-052 | Admission letter generation (PDF) | Must | GAP | 2 | WeasyPrint template + S3 upload + `decision_letter_url` |
| EM-053 | Offer letter with acceptance deadline | Must | DONE | - | `response_deadline` date on admission_decisions |
| EM-054 | Digital offer acceptance by parent | Should | GAP | 2 | ApplicantService.respond_to_offer() + applicant UI |
| EM-055 | Offer acceptance tracking | Must | DONE | - | Application status transitions to ACCEPTED |
| EM-056 | Rejection letter generation | Should | GAP | 2 | WeasyPrint template + `rejection_letter_url` column |
| EM-057 | Waitlist management and ranking | Should | GAP | 2 | `waitlist_rank` column + reorder/promote endpoints |
| EM-058 | Waitlist-to-offer conversion | Should | DONE | - | WAITLISTED -> OFFERED transition exists in state machine |
| EM-060 | Bulk admission decision processing | Should | DONE | - | DecisionService.bulk_decide() + /decisions/bulk endpoint |

### 9.6 Enrollment Confirmation

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-070 | Enrollment deposit/commitment fee payment | Must | GAP | 3 | `enrollment_deposit_*` columns on applications + admin recording |
| EM-072 | Enrollment contract/agreement generation | Should | GAP | 3 | Part of enrollment confirmation PDF (terms section) |
| EM-074 | Enrollment checklist (documents, payments, forms) | Must | GAP | 3 | New `enrollment_checklists` + `enrollment_checklist_items` tables |
| EM-075 | Enrollment confirmation letter | Must | GAP | 3 | WeasyPrint template + EnrollmentService.generate_confirmation() |
| EM-076 | Automatic student record creation | Must | DONE | - | EnrollmentService.enroll() — atomic, idempotent |
| EM-077 | Class/section assignment during enrollment | Must | DONE | - | offered_class_id on decision, section assignment in enroll() |
| EM-078 | Boarding status assignment | Must | GAP | 3 | `boarding_status` column on applications + assign endpoint |
| EM-079 | Welcome pack / orientation info delivery | Should | GAP | 3 | EnrollmentService.send_welcome_pack() via email/SMS |

### 9.7 Re-enrollment (Existing Students)

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-080 | Re-enrollment campaign creation per year | Must | DONE | - | `return_intent_campaigns` table |
| EM-081 | Re-enrollment invitation via email/SMS | Must | DONE | - | ReturnIntentService.send_campaign() |
| EM-082 | Online re-enrollment confirmation by parent | Must | GAP | 4 | ReturnIntentService.confirm_re_enrollment() + parent UI |
| EM-083 | Re-enrollment deadline management | Must | DONE | - | `deadline` field on return_intent_campaigns |
| EM-086 | Intent to withdraw with reason | Must | DONE | - | `not_returning` intent + `reason` field |
| EM-087 | Re-enrollment status tracking per student | Must | DONE | - | ReturnIntent.intent per student per year |
| EM-088 | Outstanding fee check before re-enrollment | Should | GAP | 4 | Finance service integration in confirm_re_enrollment() |
| EM-089 | Re-enrollment summary reports | Must | GAP | 4 | ReturnIntentService.get_re_enrollment_summary() + report page |

### 9.8 Enrollment Capacity Planning

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-100 | Class/section capacity limits configuration | Must | GAP | 4 | New `enrollment_targets` table with per-class targets |
| EM-101 | Grade level enrollment targets | Should | GAP | 4 | `target_count`, `boarding_target`, `day_target` columns |
| EM-102 | Real-time enrollment vs capacity dashboard | Must | GAP | 4 | CapacityService.get_dashboard() + frontend chart page |
| EM-103 | Automatic capacity enforcement | Should | GAP | 4 | CapacityService.check_capacity() called during enrollment (advisory by default) |
| EM-107 | Boarding vs day student ratio tracking | Should | GAP | 4 | `boarding_target`/`day_target` on enrollment_targets |

### 9.9 Enrollment Analytics and Reporting

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| EM-130 | Inquiry-to-enrollment conversion funnel | Should | GAP | 4 | AnalyticsService.get_full_funnel() (requires Phase 1 inquiry data) |
| EM-131 | Applications by status report | Must | DONE | - | Dashboard stats endpoint with by_status dict |
| EM-132 | Enrollment by grade level report | Must | DONE | - | Demographics endpoint with by-class breakdown |
| EM-133 | Enrollment trends (year-over-year) | Should | GAP | 4 | AnalyticsService.get_enrollment_trends() |
| EM-134 | Lead source effectiveness analysis | Should | GAP | 4 | AnalyticsService.get_lead_source_effectiveness() (requires Phase 1) |
| EM-136 | Re-enrollment rate tracking | Must | GAP | 4 | AnalyticsService.get_re_enrollment_rates() |
| EM-137 | Withdrawal/attrition analysis | Should | GAP | 4 | AnalyticsService.get_attrition_analysis() |

---

## 3. Architecture Decisions

### AD-1: Inquiry Module is Admin-Only (No Public Form)

**Decision:** The inquiry capture form (EM-001) is admin-entered only. No public-facing inquiry form.

**Rationale:** Adding a new public endpoint surface expands the attack surface (unauthenticated writes). The application portal already handles public submissions. School staff record inquiries from walk-ins, phone calls, and events.

**Future:** A public inquiry widget can be added in Phase 5 if schools request it, reusing the `PublicTenantSession` dependency pattern from the application portal.

### AD-2: Interview Scoring Uses JSONB (School-Configurable)

**Decision:** Interview scoring criteria are stored in a `scoring_criteria` JSONB field, not a fixed schema.

**Rationale:** Schools have wildly different interview formats. Some score "communication, aptitude, confidence." Others score "English, Math, General Knowledge." A JSONB field lets each school define their own criteria names. The total score = sum of criteria values.

**Example stored value:**
```json
{
  "communication": { "score": 8, "max": 10 },
  "aptitude": { "score": 7, "max": 10 },
  "confidence": { "score": 9, "max": 10 }
}
```

### AD-3: Enrollment Checklist is Optional (Backward-Compatible)

**Decision:** The enrollment checklist only blocks enrollment when explicitly created for an application. The existing enrollment flow works unchanged for applications without a checklist.

**Rationale:** Existing enrolled applications have no checklist. Schools should not be forced to use checklists. The check in `EnrollmentService.enroll()` is:
```python
if checklist_exists and not all_required_items_completed:
    raise EnrollmentError("Checklist incomplete", "CHECKLIST_INCOMPLETE")
# If no checklist exists, proceed normally (legacy behavior)
```

### AD-4: Capacity Enforcement is Advisory by Default

**Decision:** Exceeding class capacity shows a warning in the UI but does NOT block enrollment. Schools can opt into hard enforcement.

**Rationale:** Many schools routinely over-enroll. Hard blocking would frustrate admins. The capacity dashboard provides visibility; enforcement is the school's choice.

**Implementation:** `CapacityService.check_capacity()` returns `{ capacity, current, remaining, is_full }`. The enrollment endpoint includes this data in the response. The frontend shows a yellow warning badge when `remaining <= 0`. Hard blocking is a future per-school setting.

### AD-5: Anonymous Applicants Cannot Self-Service Accept Offers

**Decision:** Only applicants with registered accounts can accept/decline offers from the portal. Anonymous applicants are managed by school admin (admin marks the application as ACCEPTED).

**Rationale:** Anonymous applications have no authenticated session. Providing offer acceptance via tracking code alone would be insecure (tracking codes could be shared). Schools should encourage `require_applicant_account=true` on admission periods.

### AD-6: Enrollment Deposit is Manual Recording (Not Paystack)

**Decision:** For MVP, enrollment deposits are recorded manually by admin (enters amount + reference). Paystack integration for deposits is deferred.

**Rationale:** Deposit payment methods vary widely (bank transfer, cash, cheque). Most schools accept deposits in person. Paystack integration would add complexity for a rarely-online flow.

### AD-7: Admission Letter Templates are Fixed with School Branding

**Decision:** Admission and rejection letters use fixed HTML/CSS templates with school branding (logo, name, address, colors). Schools cannot edit template content.

**Rationale:** A full template editor is complex (rich text, variable substitution, preview). Fixed templates with dynamic school branding cover 95% of use cases. Custom content is handled via the `conditions` field on the decision.

### AD-8: CSSPS File Format is Standardized (See Section 5)

**Decision:** We define a standard CSV/Excel format for CSSPS placement imports. The parser supports configurable column mapping for variations.

**Rationale:** The actual CSSPS file format is not officially documented and varies. Defining our own standard format with a column mapping UI gives schools flexibility to import any format.

---

## 4. Migration Chain

```
Current head (latest existing migration)
    └── 20260401_0200_inquiry_and_interview.py       (Phase 1: 5 tables + 3 enums + column additions)
        └── 20260408_0100_letters_and_waitlist.py     (Phase 2: column additions only, no new tables)
            └── 20260415_0100_enrollment_checklists.py (Phase 3: 2 tables + column additions)
                └── 20260422_0100_capacity_events.py   (Phase 4: 3 tables + column additions)
```

### Rollback Strategy

Each migration is independently reversible:
- **Phase 1:** DROP 5 tables + 3 enums + remove 5 added columns
- **Phase 2:** Remove 9 added columns (no tables to drop)
- **Phase 3:** DROP 2 tables + remove 9 added columns
- **Phase 4:** DROP 3 tables + remove 4 added columns

### TENANT_SCOPED_TABLES Updates

The test `conftest.py` TENANT_SCOPED_TABLES list must be updated:

```
After Phase 1: +5 = inquiries, inquiry_communications, inquiry_follow_ups, interviews, screening_checklists
After Phase 3: +2 = enrollment_checklists, enrollment_checklist_items
After Phase 4: +3 = enrollment_targets, school_events, event_registrations
Total new: +10
```

**Note:** `inquiry_communications` uses NO SoftDeleteMixin (append-only log). `event_registrations` uses NO SoftDeleteMixin (hard delete for cancellations). Both still need RLS and tenant_id.

---

## 5. CSSPS Placement File Format Definition

The Computerised School Selection and Placement System (CSSPS) places JHS graduates into SHS. Schools receive placement lists that need to be imported as applications.

### Standard Import Format (CSV or Excel)

We define the following standard column format. Schools can map their actual file columns to these fields during import.

| Column | Required | Type | Description | Example |
|--------|----------|------|-------------|---------|
| `index_number` | Yes | String | BECE index number (unique identifier) | `0120301234` |
| `first_name` | Yes | String | Student first name | `Kwame` |
| `last_name` | Yes | String | Student surname | `Mensah` |
| `other_names` | No | String | Middle/other names | `Kofi` |
| `gender` | Yes | String | M or F | `M` |
| `date_of_birth` | No | Date | DD/MM/YYYY format | `15/03/2011` |
| `programme` | Yes | String | SHS programme placed into | `General Science` |
| `aggregate` | No | Integer | BECE aggregate score (6-54) | `12` |
| `jhs_school` | No | String | Previous JHS name | `Accra Academy JHS` |
| `jhs_district` | No | String | JHS district | `Accra Metro` |
| `region` | No | String | Home region | `Greater Accra` |
| `parent_name` | No | String | Parent/guardian name | `Ama Mensah` |
| `parent_phone` | No | String | Parent phone number | `0241234567` |
| `residential_status` | No | String | Boarding or Day | `Boarding` |
| `house` | No | String | Assigned house (if applicable) | `Aggrey House` |

### Sample CSV

```csv
index_number,first_name,last_name,other_names,gender,date_of_birth,programme,aggregate,jhs_school,jhs_district,region,parent_name,parent_phone,residential_status,house
0120301234,Kwame,Mensah,Kofi,M,15/03/2011,General Science,12,Accra Academy JHS,Accra Metro,Greater Accra,Ama Mensah,0241234567,Boarding,Aggrey House
0120301235,Abena,Asante,,F,22/07/2011,General Arts,18,Achimota JHS,Achimota,Greater Accra,Yaw Asante,0551234567,Day,
0120301236,Kojo,Owusu,Nana,M,03/11/2010,Business,15,Prempeh JHS,Kumasi Metro,Ashanti,Akua Owusu,0271234567,Boarding,Mensah House
```

### Column Mapping Configuration

During import, the admin sees a preview step where they map their actual file columns to our standard fields:

```json
{
  "column_mapping": {
    "index_number": "INDEX NO",
    "first_name": "FIRST NAME",
    "last_name": "SURNAME",
    "gender": "SEX",
    "programme": "PROGRAMME",
    "aggregate": "BECE AGGREGATE",
    "parent_phone": "GUARDIAN PHONE"
  },
  "programme_to_class_mapping": {
    "General Science": "class-uuid-for-science",
    "General Arts": "class-uuid-for-arts",
    "Business": "class-uuid-for-business",
    "Visual Arts": "class-uuid-for-visual-arts",
    "Home Economics": "class-uuid-for-home-ec",
    "Technical": "class-uuid-for-technical",
    "Agricultural Science": "class-uuid-for-agric"
  }
}
```

### Import Workflow

1. Admin uploads CSV/Excel file
2. System parses file, shows preview with row count and sample data
3. Admin maps columns (if headers don't match standard format)
4. Admin maps programmes to school classes
5. System validates: required fields present, no duplicate index_numbers
6. Admin clicks "Import"
7. For each row:
   - Create `Application` with status=`submitted`, source-metadata `{"cssps": true, "index_number": "..."}`
   - Set `target_class_id` from programme mapping
   - Create `ApplicationGuardian` if parent_name/phone present
   - Set `boarding_status` from residential_status (if applicable)
8. Return summary: `{ imported: N, skipped: N, errors: [...] }`

### Deduplication

- Check `index_number` against existing applications' `custom_fields.index_number` within the same period
- If duplicate found: skip row, add to `skipped` count with reason

---

## 6. New Permissions

No new permission keys are needed. All new endpoints use the existing `admissions.*` permission set:

| Permission Key | Used By |
|----------------|---------|
| `admissions.read` | All GET endpoints (inquiries, interviews, checklists, capacity, events, analytics) |
| `admissions.create` | Create inquiry, create event, CSSPS import, set capacity targets |
| `admissions.update` | Status changes, assign inquiry, complete checklist items, boarding status, deposits |
| `admissions.review` | Generate letters, waitlist management, interview feedback |
| `admissions.delete` | Soft-delete inquiries, cancel events |

The existing permission catalog entry (line 139-146 in `backend/app/constants/permissions.py`) already includes `admissions.create`, `admissions.update`, `admissions.delete`, `admissions.read`, `admissions.review`. No modifications needed.

---

## 7. Risk Assessment

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| CSSPS file format varies by year/region | Import fails for SHS schools | Configurable column mapping UI; preview step; validate before import |
| Offer expiry Celery task missing tenant context | Cross-tenant data leak | Task iterates tenants explicitly with `set_tenant_context()` per tenant; superuser engine for tenant list |
| PDF letter generation slow on bulk decisions | Timeout on 50+ letters | Generate async; return 202 Accepted with poll endpoint; or generate on-demand per decision |
| Enrollment checklist blocks existing flow | Schools without checklists cannot enroll | Checklist is optional — only enforced when checklist record exists |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Inquiry duplicate detection false positives | Staff confusion | Detection is advisory (warning banner), not blocking |
| Waitlist rank concurrency (two admins reordering) | Duplicate ranks | `pg_advisory_xact_lock` on reorder operations |
| Capacity enforcement race condition | Over-enrollment | Advisory warnings by default; `SELECT ... FOR UPDATE` on class row for hard enforcement |
| Analytics queries slow on large datasets | Dashboard timeout | Indexed queries; pagination; consider materialized views if > 10k applications |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tour event registration spam | Fake registrations | Rate limit 10/min on registration endpoint |
| Interview time conflicts | Double-booked interviewer | Overlap check in InterviewService.schedule() |

---

## 8. Resolved Decisions (Previously Open Questions)

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Inquiry form public or admin-only? | **Admin-only** | Avoids new public endpoint surface; school staff record inquiries |
| 2 | Interview scoring criteria? | **JSONB (school-configurable)** | Schools define own criteria names; total = sum of criteria |
| 3 | Admission letter template customization? | **Fixed template with school branding** | Custom content via conditions field; template editor deferred |
| 4 | Anonymous applicant offer acceptance? | **Admin-managed** | No secure way to authenticate anonymous applicants for offers |
| 5 | CSSPS file format? | **Defined standard format** (see Section 5) | Column mapping UI handles variations |
| 6 | Enrollment deposit payment method? | **Manual recording** | Most deposits are cash/bank; Paystack deferred |
| 7 | Capacity enforcement strictness? | **Advisory (warn, don't block)** | Schools routinely over-enroll; hard block is opt-in |
| 8 | Event registration public or authenticated? | **Admin-only for MVP** | Public registration deferred to avoid new public endpoints |

---

## 9. Phase Dependencies

```
Phase 1 ─────────────────┐
(Inquiry + Interview)     │
                          ├──► Phase 2
Celery Bootstrap ─────────┘    (Letters + Offers + Waitlist)
(prerequisite)                        │
                                      ▼
                                Phase 3
                                (Enrollment Confirmation + CSSPS)
                                      │
                                      ▼
                                Phase 4
                                (Capacity + Re-enrollment + Tours + Analytics)
```

**Hard dependencies:**
- Phase 2 depends on Phase 1: Admission letter references interview/screening scores
- Phase 2 depends on Celery Bootstrap: Reminder and expiry tasks require Celery worker infrastructure
- Phase 3 depends on Phase 2: Enrollment checklist verifies offer was accepted
- Phase 4 depends on Phase 1: Analytics funnel requires inquiry data

**Parallel opportunities within each phase:**
- Phase 1: Inquiry module and Interview module can be built in parallel
- Phase 2: Letters and Waitlist can be built in parallel; Offer acceptance depends on Letters
- Phase 3: CSSPS import and Enrollment checklist can be built in parallel
- Phase 4: All 4 sub-modules (Capacity, Re-enrollment, Tours, Analytics) can be built in parallel

---

## 10. Review Findings Applied

The following critical findings from 5 independent reviews (Security, Code Quality, Tenancy, Database, Risk) have been incorporated into the phase documents:

### Security (1 CRITICAL, 3 HIGH)
- **C1 FIXED**: Celery tasks now use session-per-tenant with try/finally (Phase 2)
- **H1 FIXED**: PROTECTED_FIELDS blocklist added to all setattr loops (Phases 1, 4)
- **H2 FIXED**: PDF templates validate primary_color as hex, logo_url as https (Phases 2, 3)
- **H3 FIXED**: CSSPS import enforces 5MB file limit + 1000 row cap (Phase 3)

### Database (4 ERRORS)
- **E3 FIXED**: inquiry_follow_ups.assigned_to changed from CASCADE to RESTRICT (Phase 1)
- **E4 FIXED**: enrollment_checklist_items.metadata renamed to item_metadata to avoid SQLAlchemy collision (Phase 3)
- **S1 FIXED**: Removed dead PostgreSQL enum type creation -- columns use VARCHAR(20) (Phase 1)
- **D10 FIXED**: enrollment_checklist_template type annotation corrected to Mapped[list] (Phase 3)

### Code Quality (7 BREAKS)
- **B1 FIXED**: All endpoints use school.school_id not school.id (all phases)
- **B2 FIXED**: All endpoints use UUID(user["tenant_id"]) consistently (all phases)
- **B3 FIXED**: Enum values explicitly unpacked, not passed via model_dump() (Phase 1)
- **B5 FIXED**: User imported from app.models.tenant (matching existing pattern) (all phases)
- **B6 FIXED**: checklist_template uses Mapped[list] not Mapped[dict] (Phase 3)
- **B7 FIXED**: _render_pdf helper method defined in DecisionService (Phase 2)
- **I6 FIXED**: Dead PostgreSQL enums removed from migration (Phase 1)

### Tenancy
- **I-1 FIXED**: verify_rls.py update instructions added to all phases
- **I-2 FIXED**: tenant_cleanup.py deletion order instructions added to all phases
- **server_default values**: Added to all columns with Python defaults across all phases

### Risk
- **R-001 ADDRESSED**: Celery bootstrap prerequisite documented as blocker for Phase 2
- **R-003 ADDRESSED**: CSSPS row cap added (1000 rows max per import)
- **Effort estimates**: Risk analysis suggests 80 dev-days realistic (vs 40 in original spec). Developers should plan accordingly.

---

## 11. File Summary (All New + Modified Files)

### New Backend Files

| Category | File Path | Phase |
|----------|-----------|-------|
| Model | `backend/app/models/admissions/inquiry.py` | 1 |
| Model | `backend/app/models/admissions/interview.py` | 1 |
| Model | `backend/app/models/admissions/enrollment_checklist.py` | 3 |
| Model | `backend/app/models/admissions/capacity.py` | 4 |
| Model | `backend/app/models/admissions/event.py` | 4 |
| Schema | `backend/app/schemas/inquiry.py` | 1 |
| Schema | `backend/app/schemas/interview.py` | 1 |
| Schema | `backend/app/schemas/enrollment_checklist.py` | 3 |
| Schema | `backend/app/schemas/cssps.py` | 3 |
| Schema | `backend/app/schemas/capacity.py` | 4 |
| Schema | `backend/app/schemas/event.py` | 4 |
| Schema | `backend/app/schemas/enrollment_analytics.py` | 4 |
| Service | `backend/app/services/admissions/inquiry_service.py` | 1 |
| Service | `backend/app/services/admissions/interview_service.py` | 1 |
| Service | `backend/app/services/admissions/cssps_service.py` | 3 |
| Service | `backend/app/services/admissions/capacity_service.py` | 4 |
| Service | `backend/app/services/admissions/event_service.py` | 4 |
| Service | `backend/app/services/admissions/analytics_service.py` | 4 |
| Endpoint | `backend/app/api/v1/endpoints/admissions/inquiries.py` | 1 |
| Endpoint | `backend/app/api/v1/endpoints/admissions/interviews.py` | 1 |
| Endpoint | `backend/app/api/v1/endpoints/admissions/enrollment_checklist.py` | 3 |
| Endpoint | `backend/app/api/v1/endpoints/admissions/cssps.py` | 3 |
| Endpoint | `backend/app/api/v1/endpoints/admissions/capacity.py` | 4 |
| Endpoint | `backend/app/api/v1/endpoints/admissions/events.py` | 4 |
| Endpoint | `backend/app/api/v1/endpoints/admissions/analytics.py` | 4 |
| Task | `backend/app/tasks/admission_reminders.py` | 2 |
| Task | `backend/app/tasks/offer_expiry.py` | 2 |
| Template | `backend/app/templates/admissions/admission_letter.html` | 2 |
| Template | `backend/app/templates/admissions/rejection_letter.html` | 2 |
| Template | `backend/app/templates/admissions/enrollment_confirmation.html` | 3 |
| Migration | `backend/alembic/versions/20260401_0200_inquiry_and_interview.py` | 1 |
| Migration | `backend/alembic/versions/20260408_0100_letters_and_waitlist.py` | 2 |
| Migration | `backend/alembic/versions/20260415_0100_enrollment_checklists.py` | 3 |
| Migration | `backend/alembic/versions/20260422_0100_capacity_events.py` | 4 |

### New Frontend Files

| Category | File Path | Phase |
|----------|-----------|-------|
| Action | `frontend/actions/inquiries.action.ts` | 1 |
| Action | `frontend/actions/interviews.action.ts` | 1 |
| Action | `frontend/actions/capacity.action.ts` | 4 |
| Action | `frontend/actions/events.action.ts` | 4 |
| Type | `frontend/types/inquiry.type.ts` | 1 |
| Type | `frontend/types/interview.type.ts` | 1 |
| Type | `frontend/types/enrollment-checklist.type.ts` | 3 |
| Type | `frontend/types/capacity.type.ts` | 4 |
| Type | `frontend/types/event.type.ts` | 4 |
| Page | `frontend/app/(dashboard)/admissions/inquiries/page.tsx` | 1 |
| Page | `frontend/app/(dashboard)/admissions/inquiries/[id]/page.tsx` | 1 |
| Page | `frontend/app/(dashboard)/admissions/enrollment/[id]/checklist/page.tsx` | 3 |
| Page | `frontend/app/(dashboard)/admissions/cssps/page.tsx` | 3 |
| Page | `frontend/app/(dashboard)/admissions/capacity/page.tsx` | 4 |
| Page | `frontend/app/(dashboard)/admissions/events/page.tsx` | 4 |
| Page | `frontend/app/(dashboard)/admissions/analytics/page.tsx` | 4 |
| Component | `frontend/components/admissions/inquiry-form.tsx` | 1 |
| Component | `frontend/components/admissions/inquiry-status-badge.tsx` | 1 |
| Component | `frontend/components/admissions/inquiry-table.tsx` | 1 |
| Component | `frontend/components/admissions/communication-log.tsx` | 1 |
| Component | `frontend/components/admissions/follow-up-list.tsx` | 1 |
| Component | `frontend/components/admissions/bulk-import-dialog.tsx` | 1 |
| Component | `frontend/components/admissions/duplicate-warning.tsx` | 1 |
| Component | `frontend/components/admissions/interview-scheduler.tsx` | 1 |
| Component | `frontend/components/admissions/interview-feedback-form.tsx` | 1 |
| Component | `frontend/components/admissions/screening-checklist.tsx` | 1 |
| Component | `frontend/components/admissions/waitlist-table.tsx` | 2 |
| Component | `frontend/components/admissions/letter-preview.tsx` | 2 |
| Component | `frontend/components/admissions/offer-response-form.tsx` | 2 |
| Component | `frontend/components/admissions/reminder-settings.tsx` | 2 |
| Component | `frontend/components/admissions/enrollment-checklist-ui.tsx` | 3 |
| Component | `frontend/components/admissions/deposit-payment.tsx` | 3 |
| Component | `frontend/components/admissions/boarding-selector.tsx` | 3 |
| Component | `frontend/components/admissions/cssps-upload.tsx` | 3 |
| Component | `frontend/components/admissions/welcome-pack-preview.tsx` | 3 |
| Component | `frontend/components/admissions/capacity-chart.tsx` | 4 |
| Component | `frontend/components/admissions/capacity-table.tsx` | 4 |
| Component | `frontend/components/admissions/enrollment-funnel.tsx` | 4 |
| Component | `frontend/components/admissions/trend-chart.tsx` | 4 |
| Component | `frontend/components/admissions/lead-source-chart.tsx` | 4 |
| Component | `frontend/components/admissions/attrition-report.tsx` | 4 |
| Component | `frontend/components/admissions/event-form.tsx` | 4 |
| Component | `frontend/components/admissions/event-registration-table.tsx` | 4 |
| Component | `frontend/components/admissions/re-enrollment-confirmation.tsx` | 4 |

### Modified Files

| File Path | Phase(s) | Changes |
|-----------|----------|---------|
| `backend/app/models/admissions/__init__.py` | 1, 3, 4 | Re-export new models and enums |
| `backend/app/models/admissions/enums.py` | 1 | Add InquirySource, InquiryStatus, InterviewStatus enums |
| `backend/app/models/admissions/application.py` | 1, 3 | Add inquiry_id, enrollment_deposit_*, boarding_status, enrollment_confirmation_url, welcome_pack_sent columns |
| `backend/app/models/admissions/decision.py` | 1, 2 | Add interview_score, screening_score, rejection_reason, rejection_letter_url, waitlist_rank, waitlist_notes |
| `backend/app/models/admissions/exam.py` | 1 | Add subject_name, weight to EntranceExamResult |
| `backend/app/models/admissions/period.py` | 2, 3 | Add reminder_enabled, reminder_days_before_close, enrollment_deposit_required, enrollment_deposit_amount, enrollment_checklist_template |
| `backend/app/models/admissions/return_intent.py` | 4 | Add re_enrollment_confirmed, re_enrollment_confirmed_at, outstanding_fees_checked, outstanding_fee_amount |
| `backend/app/services/admissions/__init__.py` | 1, 3, 4 | Re-export new services |
| `backend/app/services/admissions/decision_service.py` | 2 | Add generate_admission_letter(), generate_rejection_letter(), waitlist methods |
| `backend/app/services/admissions/applicant_service.py` | 2 | Add respond_to_offer(), get_offer_details() |
| `backend/app/services/admissions/enrollment_service.py` | 3 | Add checklist methods, deposit recording, boarding assignment, confirmation generation, welcome pack |
| `backend/app/services/admissions/return_intent_service.py` | 4 | Add confirm_re_enrollment(), get_re_enrollment_summary() |
| `backend/app/api/v1/endpoints/admissions/__init__.py` | 1, 3, 4 | Register new sub-routers |
| `backend/app/api/v1/endpoints/admissions/decisions.py` | 2 | Add letter generation, waitlist endpoints |
| `backend/app/api/v1/endpoints/admissions/applicant.py` | 2 | Add offer response endpoints |
| `backend/app/api/v1/endpoints/admissions/return_intents.py` | 4 | Add re-enrollment confirmation endpoint |
| `backend/tests/conftest.py` | 1, 3, 4 | Add 10 tables to TENANT_SCOPED_TABLES |
| `frontend/components/dashboard/app-sidebar.tsx` | 1, 4 | Add Inquiries, Capacity, Events, Analytics nav items |
| `frontend/actions/admissions.action.ts` | 2, 3, 4 | Add letter, waitlist, checklist, deposit, capacity action functions |
| `frontend/actions/applicant.action.ts` | 2 | Add getOfferDetails(), respondToOffer() |
| `frontend/types/admissions.type.ts` | 2, 3, 4 | Add waitlist, checklist, deposit types |
| `frontend/app/(dashboard)/admissions/admissions-dashboard.tsx` | 1, 4 | Add inquiry stats widget, capacity widget |
| `frontend/app/(dashboard)/admissions/decisions/decisions-management.tsx` | 2 | Add waitlist tab, letter generation buttons |
| `frontend/app/(auth)/apply/dashboard/[id]/page.tsx` | 2 | Add offer accept/decline UI for applicants |
