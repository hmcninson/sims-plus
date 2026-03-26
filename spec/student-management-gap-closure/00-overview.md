# Student Management Gap Closure — Implementation Plan

**Author:** SIMS Plus Engineering
**Date:** 2026-03-25
**Status:** Approved for Implementation
**Estimated Effort:** 4 Phases
**Branch:** `feat/student-management-gap-closure`

---

## Table of Contents

| Document | Covers |
|----------|--------|
| [00-overview.md](00-overview.md) | This file — gap matrix, architecture decisions, migration chain, testing strategy |
| [01-phase-1-history-and-analytics.md](01-phase-1-history-and-analytics.md) | Class assignment history, enrollment status tracking, enrollment analytics |
| [02-phase-2-transfer-and-withdrawal.md](02-phase-2-transfer-and-withdrawal.md) | Withdrawal processing, transfer certificates, inter-school transfer, fee checks, academic record export |
| [03-phase-3-documents-and-profile.md](03-phase-3-documents-and-profile.md) | Student document repository, previous school history, birth certificate number, structured medical data |
| [04-phase-4-promotion-rules-and-graduation.md](04-phase-4-promotion-rules-and-graduation.md) | Configurable auto-promotion rules, graduation certificate PDF |

---

## 1. Executive Summary

The Student Management module is production-ready with comprehensive student CRUD, guardian management, bulk import, and class promotion features. This gap closure addresses **14 identified gaps** across student records, enrollment history, transfer/withdrawal workflows, document management, and configurable promotion rules.

### What Already Exists

| Area | Status | Key Files |
|------|--------|-----------|
| Student CRUD (name, DOB, gender, photo, contact, IDs) | Complete | `models/student.py`, `services/student/student_service.py` |
| Student ID auto-generation (PREFIX-YEAR-SEQ) | Complete | `services/student/student_service.py:generate_student_id()` |
| Bulk CSV/Excel import with auto-column mapping | Complete | `services/student/import_service.py` |
| Guardian CRUD with primary/emergency/pickup flags | Complete | `services/student/guardian_service.py` |
| Multiple guardians per student, multiple children per guardian | Complete | `StudentGuardian` junction table |
| Ghana Card + NHIS number fields | Complete | `Student.ghana_card_number`, `Student.nhis_number` |
| Medical fields (text-based) | Complete | `Student.blood_group`, `Student.medical_conditions`, `Student.allergies` |
| Student statuses (active, inactive, graduated, transferred, withdrawn, suspended) | Complete | `StudentStatus` enum |
| End-of-year batch promotion (draft→preview→execute) | Complete | `ClassPromotion`, `ClassPromotionEntry`, `PromotionService` |
| Repetition with reason recording | Complete | `ClassPromotionEntry.reason` |
| Enrollment from admissions (Application→Student conversion) | Complete | `EnrollmentService` |
| Basic student stats (counts by status, gender, boarder) | Complete | `StudentService.get_student_stats()` |
| Student export to CSV | Complete | `StudentService.export_students_csv()` |

### What This Plan Adds

| Phase | Priority | New Tables | New Columns | New Endpoints | New Tests | PDF Templates |
|-------|----------|-----------|-------------|---------------|-----------|---------------|
| Phase 1: History & Analytics | Must | 2 | 0 | 3 | ~18 | 0 |
| Phase 2: Transfer & Withdrawal | Must | 1 | 0 | 10 | ~30 | 2 |
| Phase 3: Documents & Profile | Should | 2 | 2 | 8 | ~24 | 0 |
| Phase 4: Promotion Rules & Graduation | Should | 1 | 0 | 5 | ~16 | 1 |
| **Total** | | **6** | **2** | **~26** | **~88** | **3** |

---

## 2. Requirement-to-Implementation Matrix

### 10.1 Student Records

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| STU-001 | Full name, DOB, gender, photo, contact info | Must | DONE | — | `Student` model has all fields |
| STU-002 | Ghana Card / Birth Certificate number | Should | **GAP** | 3 | Add `birth_certificate_number VARCHAR(50)` column to `students` table |
| STU-003 | NHIS number | Should | DONE | — | `Student.nhis_number` field exists |
| STU-004 | Auto-generate unique student ID per school format | Must | DONE | — | `generate_student_id()` with PREFIX-YEAR-SEQ and retry logic |
| STU-005 | Bulk student import via CSV/Excel | Must | DONE | — | `StudentImportMixin` with auto-column mapping, preview, encoding detection |
| STU-006 | Student records linked to guardians | Must | DONE | — | `StudentGuardian` junction with 9 relationship types |
| SM-014 | Medical information and allergies recording | Should | **GAP** | 3 | Add `structured_medical JSONB` column for structured conditions/allergies/medications/emergency |
| SM-015 | Previous school history for transfers | Should | **GAP** | 3 | New `previous_schools` table (school_name, address, last_class, years, reason) |
| SM-017 | Class/Form assignment and history tracking | Must | **GAP** | 1 | New `student_class_history` table tracking assignments per academic year |
| SM-018 | House/Dormitory assignment for boarding | Should | DONE | — | `Student.is_boarder` + boarding module with `student_boarding` table |
| SM-019 | Document repository per student | Should | **GAP** | 3 | New `student_documents` table with S3 storage, upload/download/delete |

### 10.2 Guardian Management

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| STU-010 | Each student SHALL have at least one guardian | Must | DONE | — | Enforced in business logic during student creation |
| STU-011 | Guardian: name, relationship, phone, email | Must | DONE | — | `Guardian` model + `StudentGuardian.relationship` enum |
| STU-012 | Multiple guardians per student | Must | DONE | — | Many-to-many via `StudentGuardian` junction |
| STU-013 | One guardian designated as primary contact | Must | DONE | — | `StudentGuardian.is_primary` with auto-unset logic |
| STU-014 | Guardians with multiple children linked | Must | DONE | — | Supported with `student_count` in guardian listings |

### 10.3 Enrollment & Promotion

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| STU-020 | Track enrollment history | Must | **GAP** | 1 | New `student_status_changes` table — unified audit trail for all status transitions |
| STU-021 | Promotion, repetition, transfer, withdrawal | Must | PARTIAL | 1+2 | Promotion/repetition done via `ClassPromotion`. Transfer/withdrawal workflows added in Phase 2 |
| STU-022 | Enrollment statistics | Must | **GAP** | 1 | Enhanced analytics: trends over time, per-class breakdown, attrition rates, new enrollments per term |
| STU-023 | Mid-year enrollment | Must | DONE | — | Students can be enrolled at any time |
| SM-040 | End-of-year bulk promotion | Must | DONE | — | `ClassPromotion` batch system (draft→preview→execute) with partial success |
| SM-041 | Configurable promotion rules (auto/manual) | Should | **GAP** | 4 | New `promotion_rules` table with min_average, min_attendance, core_subject_pass_count, auto_apply |
| SM-042 | Repetition with reason recording | Must | DONE | — | `ClassPromotionEntry.reason` field |
| SM-043 | Graduation processing and certificate | Should | **GAP** | 4 | Graduation cert PDF template + generation endpoint |

### 10.4 Transfers and Withdrawal

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|-------------|----------|--------|-------|----------------|
| SM-030 | Student withdrawal with reason tracking | Must | **GAP** | 2 | Withdrawal workflow: initiate→clearance→complete, reason + effective_date + clearance checklist |
| SM-031 | Transfer certificate generation | Must | **GAP** | 2 | PDF template with student info, class history, academic summary, conduct |
| SM-032 | Inter-school transfer within chain | Must | **GAP** | 2 | `transfer_within_chain()` — update school_id/class_id, record history, same tenant |
| SM-033 | Outstanding fee check before transfer/withdrawal | Should | **GAP** | 2 | `check_outstanding_fees()` — queries invoices, warns admin, allows override with logging |
| SM-034 | Academic record portability on transfer | Should | **GAP** | 2 | Full student record export (PDF + JSON) including grades, attendance, class history |

---

## 3. Architecture Decisions

### AD-1: Unified Status Change Table

**Decision:** Use a single `student_status_changes` table as the audit trail for ALL status transitions (enrollment, withdrawal, transfer, graduation, suspension) rather than separate tables per transition type.

**Rationale:**
- Avoids table proliferation (one table vs. 4-5 separate tables)
- Provides a complete student lifecycle view from a single query
- The `metadata JSONB` column captures transition-specific context (e.g., destination school for transfers, clearance status for withdrawals)
- Follows the same pattern as `application_status_history` in the admissions module

### AD-2: Structured Medical as JSONB Column

**Decision:** Add a `structured_medical JSONB` column on the `students` table rather than a separate `student_medical_records` table.

**Rationale:**
- Most schools need a simple structured view of medical info (conditions, allergies, medications, emergency protocol)
- A separate table adds complexity for a "Should" priority feature
- JSONB provides schema flexibility without migration overhead for adding new medical field types
- The existing text fields (`medical_conditions`, `allergies`, `blood_group`) remain for backward compatibility — no existing code breaks
- If per-condition audit history is needed later, a table can be added without disrupting this design

### AD-3: Class History Backfill

**Decision:** The Phase 1 migration backfills `student_class_history` from the current state of the `students` table (one row per active student with their current class assignment).

**Rationale:**
- Without backfill, the history tab would show nothing for existing students
- The backfill uses `admission_date` (if present) or `created_at` as the `enrolled_date`
- Only active students are backfilled — graduated/transferred/withdrawn students already left their class
- This is a one-time INSERT...SELECT in the migration, safe for production

### AD-4: Fee Check is Advisory, Not Blocking

**Decision:** The outstanding fee check before transfer/withdrawal warns the admin but does not block the operation. Admin can override with confirmation.

**Rationale:**
- In practice, Ghanaian schools sometimes need to release students despite outstanding fees (legal requirements, hardship cases)
- A hard block would force workarounds (e.g., writing off fees just to process a transfer)
- The override is logged in `student_status_changes.metadata` with `{fee_override: true, outstanding_amount: "150.00", overridden_by: "user-uuid"}` for audit purposes
- Schools can choose their own policy via the UI confirmation dialog

### AD-5: Inter-School Transfer Stays Within Same Tenant

**Decision:** Inter-school chain transfers (SM-032) update the student record in place (change `school_id`, `class_id`) rather than creating a new student record at the destination school.

**Rationale:**
- Both schools are within the same tenant, so RLS works seamlessly
- The student keeps their UUID, preserving all historical references (grades, attendance, invoices)
- Class history records both the source and destination via separate entries (close old, open new)
- The `student_status_changes.metadata` records `{transfer_type: "intra_chain", from_school_id: ..., to_school_id: ...}`
- Student status remains `active` — it does NOT change to `transferred` (that status is for external transfers out of the platform)

### AD-6: Audit Record Immutability

**Decision:** `student_status_changes` and `student_class_history` do NOT use `SoftDeleteMixin`. They are audit records with restricted mutability.

**Rationale:**
- These tables serve as the official historical record of a student's lifecycle
- Deleting or modifying audit entries would compromise data integrity
- Follows the same pattern as `application_status_history`, `finance_audit_log`, and `score_change_logs`

**Mutability levels:**
- `student_status_changes` — **Append-only**. `GRANT SELECT, INSERT` only (no UPDATE/DELETE). Records are never modified after creation.
- `student_class_history` — **Append-mostly**. `GRANT SELECT, INSERT, UPDATE` (no DELETE). UPDATE is needed only for setting `left_date` and `reason` when closing an assignment.

### AD-7: StudentService Mixin Composition

**Decision:** New functionality is added as additional mixins (`StudentHistoryMixin`, `StudentLifecycleMixin`, `StudentDocumentMixin`) composed into the existing `StudentService` class.

**Rationale:**
- Follows the established pattern (`StudentCoreMixin`, `StudentImportMixin`, `StudentGuardianMixin`)
- Each mixin is in its own file for code organization
- The composed `StudentService` class remains the single entry point for dependency injection
- All mixins share `self.db: AsyncSession` from the `__init__` in `StudentService`

---

## 4. New Database Tables Summary

| Table | Phase | Purpose | RLS | Soft Delete | Immutable |
|-------|-------|---------|-----|-------------|-----------|
| `student_class_history` | 1 | Track class/section assignments per academic year | Yes | No | Yes |
| `student_status_changes` | 1 | Audit trail for all student status transitions | Yes | No | Yes |
| `withdrawal_clearances` | 2 | Clearance checklist for withdrawal/transfer processing | Yes | No | No |
| `student_documents` | 3 | Per-student document repository (S3-backed) | Yes | Yes | No |
| `previous_schools` | 3 | Structured previous school history for transfer students | Yes | No | No |
| `promotion_rules` | 4 | Configurable auto-promotion criteria per school/year/class | Yes | Yes | No |

### Column Additions (Phase 3)

| Table | Column | Type | Nullable | Purpose |
|-------|--------|------|----------|---------|
| `students` | `birth_certificate_number` | `VARCHAR(50)` | Yes | National birth certificate reference (STU-002) |
| `students` | `structured_medical` | `JSONB` | Yes | Structured medical data: conditions, allergies, medications, emergency (SM-014) |

---

## 5. Migration Chain

All migrations follow the project naming convention `YYYYMMDD_NNNN_description.py`.

| Migration ID | Phase | Revises | Content |
|-------------|-------|---------|---------|
| `20260425_0100_student_history_tables` | 1 | `20260422_0100` (HEAD) | 2 tables + RLS + indexes + backfill from current students |
| `20260425_0200_withdrawal_transfer` | 2 | `20260425_0100` | 1 table + RLS + indexes |
| `20260425_0300_student_documents_profile` | 3 | `20260425_0200` | 2 tables + 2 columns on students + 1 enum + RLS + indexes |
| `20260425_0400_promotion_rules_graduation` | 4 | `20260425_0300` | 1 table + RLS + indexes |

> **Note:** Migration IDs use dates after the current HEAD (`20260422_0100`). Code development for Phases 2 and 3 can proceed in parallel, but migrations must be applied in order.

**TENANT_SCOPED_TABLES update:** +6 tables added to **all three** tracking files:
- `backend/tests/conftest.py` (test RLS enforcement)
- `backend/scripts/verify_rls.py` (production RLS verification)
- `backend/app/tasks/tenant_cleanup.py` (tenant deletion cascade)

```python
# Student Management Gap Closure
"student_class_history",      # Phase 1
"student_status_changes",     # Phase 1
"withdrawal_clearances",      # Phase 2
"student_documents",          # Phase 3
"previous_schools",           # Phase 3
"promotion_rules",            # Phase 4
```

Current count: 119 → New count: **125**

---

## 6. Service Layer Architecture

### Current StudentService Composition

```python
# backend/app/services/student/__init__.py (CURRENT)
class StudentService(StudentCoreMixin, StudentImportMixin, StudentGuardianMixin):
    def __init__(self, db: AsyncSession):
        self.db = db
```

### Updated StudentService Composition (After All Phases)

```python
# backend/app/services/student/__init__.py (AFTER GAP CLOSURE)
class StudentService(
    StudentCoreMixin,        # Existing: CRUD, ID gen, stats, bulk create, promote
    StudentImportMixin,      # Existing: CSV/Excel import
    StudentGuardianMixin,    # Existing: Guardian CRUD, student-guardian links
    StudentHistoryMixin,     # Phase 1: Class history, status changes, analytics
    StudentLifecycleMixin,   # Phase 2: Withdrawal, transfer, fee check, PDF gen
    StudentDocumentMixin,    # Phase 3: Document upload/download, previous schools
):
    def __init__(self, db: AsyncSession):
        self.db = db
```

### New Service Files

| File | Phase | Mixin | Methods |
|------|-------|-------|---------|
| `services/student/history_service.py` | 1 | `StudentHistoryMixin` | `record_class_assignment`, `close_class_assignment`, `get_class_history`, `record_status_change`, `get_status_history`, `get_enrollment_analytics` |
| `services/student/lifecycle_service.py` | 2 | `StudentLifecycleMixin` | `initiate_withdrawal`, `get_withdrawal_clearance`, `update_clearance`, `complete_withdrawal`, `check_outstanding_fees`, `initiate_transfer`, `complete_transfer`, `transfer_within_chain`, `generate_transfer_certificate`, `generate_withdrawal_letter`, `export_student_record` |
| `services/student/document_service.py` | 3 | `StudentDocumentMixin` | `upload_document`, `list_documents`, `delete_document`, `get_document_download_url`, `add_previous_school`, `list_previous_schools`, `update_previous_school`, `delete_previous_school` |

Phase 4 promotion rules are added to the existing `services/admissions/promotion_service.py` since they integrate with the existing `ClassPromotion` batch system.

---

## 7. Integration Points

| Source | Target | Integration | Phase |
|--------|--------|-------------|-------|
| `StudentCoreMixin.update_student()` | `StudentHistoryMixin.record_status_change()` | Call when `status` field changes | 1 |
| `PromotionService.execute_batch()` | `StudentHistoryMixin.record_class_assignment()` / `close_class_assignment()` | Call when promoting/repeating/graduating students | 1 |
| `StudentLifecycleMixin` | `Invoice` model (finance) | Query outstanding invoices for fee check | 2 |
| `StudentLifecycleMixin` | `StudentBoardingAssignment` (boarding) | Check active bed assignment for clearance | 2 |
| `StudentLifecycleMixin` | `ExamScore`, `TermReport` (exams) | Include academic summary in transfer cert and record export | 2 |
| `StudentDocumentMixin` | `S3Service` (media) | Upload/download documents to/from S3 | 3 |
| `PromotionService.generate_preview()` | `PromotionRule` model | Auto-populate promotion entries based on rules | 4 |
| `PromotionService` | `TermReport`, `StudentAttendance` | Query grades and attendance for rule evaluation | 4 |

---

## 8. Feature Gating by Subscription Plan

| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| Class history / Status history | Yes | Yes | Yes |
| Enrollment analytics | Yes | Yes | Yes |
| Withdrawal processing | Yes | Yes | Yes |
| Transfer certificate PDF | Yes | Yes | Yes |
| Withdrawal letter PDF | Yes | Yes | Yes |
| Student documents (S3 storage) | 50 MB/student | 200 MB/student | 1 GB/student |
| Inter-school chain transfer | N/A | N/A | Yes (chain only) |
| Auto-promotion rules | No | Yes | Yes |
| Graduation certificate PDF | Yes | Yes | Yes |
| Academic record export (PDF/JSON) | No | Yes | Yes |

---

## 9. Security Considerations

### Row-Level Security

All 6 new tables follow the standard RLS pattern:

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_{table} ON {table}
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

-- GRANT varies by table mutability:
-- Immutable audit tables (student_status_changes): SELECT, INSERT only
-- Append-mostly tables (student_class_history): SELECT, INSERT, UPDATE (UPDATE for left_date)
-- Normal tables: SELECT, INSERT, UPDATE, DELETE
GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO sims_app_user;
```

> **Important:** Policy names must follow the convention `tenant_isolation_{table_name}` (e.g., `tenant_isolation_student_class_history`). Prefer using `rls_helpers.enable_rls_for_table()` / `disable_rls_for_table()` where available.

### Defense-in-Depth

All service queries include explicit `.filter(Model.tenant_id == tenant_id)` in addition to RLS. This is the established project pattern.

### IDOR Prevention

- Document download endpoints verify `student.tenant_id == tenant_id` before returning presigned S3 URLs
- Clearance update endpoints verify the clearance belongs to the student specified in the URL path
- Previous school and document delete endpoints verify ownership

### Audit Trail

- All status changes are immutable records in `student_status_changes`
- Fee check overrides are logged in `metadata` JSONB
- Document uploads record `uploaded_by` user ID
- Clearance completions record `cleared_by` and `cleared_at`

### File Upload Security

Document uploads reuse the existing media upload pattern:
- Magic byte validation (not just MIME type checking)
- File size limit: 10 MB per document
- Allowed MIME types: `application/pdf`, `image/jpeg`, `image/png`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- S3 path includes tenant_id prefix: `{tenant_id}/students/{student_id}/documents/{uuid}_{filename}`
- Download via presigned URLs (15-minute expiry), no public read access

### Rate Limiting

| Endpoint Type | Limit | Reason |
|--------------|-------|--------|
| PDF generation (transfer cert, withdrawal letter, graduation cert, record export) | 5/min | Prevent WeasyPrint resource exhaustion |
| Document upload | 20/min | Standard file upload limit |
| All other new endpoints | 100/min | Standard API limit |

---

## 10. Testing Strategy

### Test File Organization

| Test File | Phase | Coverage |
|-----------|-------|----------|
| `tests/test_student_class_history.py` | 1 | Class history CRUD, backfill verification, promotion integration |
| `tests/test_student_status_changes.py` | 1 | Status change recording, timeline queries, analytics |
| `tests/test_student_withdrawal.py` | 2 | Withdrawal workflow: initiate→clearance→complete, fee check, letter PDF |
| `tests/test_student_transfer.py` | 2 | External transfer, chain transfer, transfer cert PDF, record export |
| `tests/test_student_documents.py` | 3 | Document upload/list/delete, presigned URLs, file validation |
| `tests/test_previous_schools.py` | 3 | Previous school CRUD, structured medical JSONB |
| `tests/test_student_mgmt_rls.py` | 1-3 | RLS enforcement on all new tables (cross-tenant isolation) |
| `tests/test_promotion_rules.py` | 4 | Rule CRUD, auto-apply evaluation, integration with batch preview |

### Test Patterns (Follow Existing Conventions)

```python
# Two-engine pattern (from conftest.py)
# admin_engine: superuser for DDL, seeding (bypasses RLS)
# app_engine: sims_app_user (RLS enforced)

# UUID bind params: CAST(:param AS uuid)
# Enum values: lowercase strings
# Raw SQL: include ALL NOT NULL columns
# After tenant context switch: session.expire_all()
```

### RLS Test Pattern

```python
async def test_student_class_history_rls(admin_session, app_session):
    """Verify tenant isolation on student_class_history table."""
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()

    # Seed data for both tenants via admin (bypasses RLS)
    # ...

    # Switch app_session to tenant A
    await app_session.execute(text("SELECT set_tenant_context(CAST(:tid AS uuid))"), {"tid": str(tenant_a_id)})

    # Query should only return tenant A records
    result = await app_session.execute(text("SELECT count(*) FROM student_class_history"))
    assert result.scalar() == <expected_tenant_a_count>
```

---

## 11. Phase Dependencies

```
Phase 1 (History & Analytics)
    │
    ├──→ Phase 2 (Transfer & Withdrawal)
    │       │
    │       └──→ Phase 4 (Promotion Rules & Graduation)
    │
    └──→ Phase 3 (Documents & Profile)  ← Can run in parallel with Phase 2
```

- **Phase 1** has no dependencies — start here
- **Phase 2** depends on Phase 1 (needs `student_status_changes` and `student_class_history`)
- **Phase 3** is independent of Phase 2 — code development can proceed in parallel, but migrations must be applied in order (serial chain)
- **Phase 4** depends on Phase 1 (class history for graduation cert) and Phase 2 (status change recording)

---

## 12. Frontend Impact Summary

### Student Detail Page (`frontend/app/(dashboard)/students/[id]/page.tsx`)

New tabs/sections added across phases:

| Tab/Section | Phase | Content |
|-------------|-------|---------|
| "History" tab | 1 | Class assignment timeline + status change timeline (chronological) |
| "Documents" tab | 3 | Document upload area, document list with download/delete, document type filter |
| "Previous Schools" section | 3 | Inline add/edit/delete for previous school records |
| "Medical" section (enhanced) | 3 | Structured form for conditions, allergies, medications, emergency protocol, doctor info |
| "Withdraw" action button | 2 | Opens withdrawal dialog with reason, date, fee warning, clearance checklist |
| "Transfer" action button | 2 | Opens transfer dialog (external vs. chain, destination, class assignment) |
| "Download" dropdown | 2 | Transfer certificate, withdrawal letter, academic record export |
| "Graduation Certificate" button | 4 | Download graduation cert PDF (only visible when status=graduated) |

### Student Create/Edit Forms

| Field | Phase | Location |
|-------|-------|----------|
| `birth_certificate_number` | 3 | Next to `ghana_card_number` and `nhis_number` in the ID documents section |

### New Pages

| Page | Phase | Path |
|------|-------|------|
| Enrollment Analytics | 1 | `/students/analytics` or section within `/dashboard` |
| Promotion Rules Settings | 4 | `/settings/promotion-rules` |

### Server Actions

| File | Phase | New Functions |
|------|-------|---------------|
| `actions/students.action.ts` | 1-3 | `getClassHistory`, `getStatusHistory`, `getEnrollmentAnalytics`, `initiateWithdrawal`, `updateClearance`, `completeWithdrawal`, `initiateTransfer`, `chainTransfer`, `checkOutstandingFees`, `downloadTransferCert`, `downloadWithdrawalLetter`, `downloadAcademicRecord`, `uploadDocument`, `listDocuments`, `deleteDocument`, `addPreviousSchool`, `listPreviousSchools`, `updatePreviousSchool`, `deletePreviousSchool` |
| `actions/admissions.action.ts` | 4 | `getPromotionRules`, `createPromotionRule`, `updatePromotionRule`, `deletePromotionRule`, `downloadGraduationCert` |

### TypeScript Types

Add to `frontend/types/index.ts`:

```typescript
// Phase 1
export interface StudentClassHistory { ... }
export interface StudentStatusChange { ... }
export interface EnrollmentAnalytics { ... }

// Phase 2
export interface WithdrawalClearance { ... }
export interface OutstandingFeeCheck { ... }
export interface WithdrawalRequest { ... }
export interface TransferRequest { ... }
export interface ChainTransferRequest { ... }

// Phase 3
export interface StudentDocument { ... }
export interface PreviousSchool { ... }
export interface StructuredMedical { ... }

// Phase 4
export interface PromotionRule { ... }
```

---

## 13. Rollback Strategy

All migrations are additive (new tables, new columns). No existing tables or columns are modified or dropped.

- `downgrade()` for each migration drops the new tables and removes added columns
- No data loss risk to existing functionality
- Frontend changes are additive (new tabs, buttons, dialogs) — removing them has no side effects
- Service mixins are additive — removing a mixin from `StudentService` composition does not affect existing methods

---

## 14. Open Questions

| # | Question | Recommendation | Decision |
|---|----------|---------------|----------|
| 1 | Should `structured_medical` require a separate permission (`students.medical.read`)? | Use `students.read` for MVP; add granular medical permissions later if schools request it | Pending |
| 2 | Should transfer certificates include a digital signature or QR code? | Defer. Plain PDF with school stamp placeholder is sufficient for current market | Deferred |
| 3 | How are "core subjects" identified for auto-promotion rules? | Use existing `Subject.subject_type` field if a `core` value exists, or add `is_core` boolean to `subjects` | Needs verification |
| 4 | Should document storage limits be enforced at upload time? | Yes, query total document size per student before allowing upload; return 413 if exceeded | Pending |
| 5 | Should withdrawal clearance items be configurable per school? | No for MVP — use fixed checklist (library, finance, property, boarding). Configurable items can be added later | Pending |

---

## 15. Post-Review Findings & Resolutions

The implementation plan was reviewed by 5 specialized agents (Security, Database, Tenancy Architect, Code Reviewer, Solution Architect). Below are the consolidated findings and their resolutions, applied across all phase documents.

### Critical Fixes Applied

| # | Finding | Source | Resolution |
|---|---------|--------|------------|
| F-1 | `performed_by` on `student_status_changes` is `nullable=False` with `ondelete="SET NULL"` — contradictory constraints that block user deletion | DB, Code, Arch | **Changed to `nullable=True`** in both migration and model. SET NULL is the correct behavior for audit records when users are deleted. |
| F-2 | `uploaded_by` on `student_documents` has the same NOT NULL + SET NULL conflict | DB, Code | **Changed to `nullable=True`** in both migration and model. |
| F-3 | Phase 1 backfill JOIN produces cartesian product for chain tenants with multiple active academic years | DB, Code, Arch | **Added `AND ay.school_id = s.school_id` to JOIN condition** in migration. Also added `DISTINCT ON (s.id)` as safety net. |
| F-4 | Migration chain references wrong HEAD — current HEAD is `20260422_0100`, not `20260326_*` dates | DB | **Updated migration IDs** to `20260425_0100` through `20260425_0400` and set `down_revision = "20260422_0100"` for Phase 1. |
| F-5 | All new endpoints use `Depends(get_db)` / `Depends(ValidatedUser)` but existing `students.py` uses `DatabaseSession` / `RequestTenant` annotated aliases | Code | **Updated all endpoint examples** to use `tenant: RequestTenant, db: DatabaseSession` pattern. Added note that `ValidatedUser` is needed additionally for endpoints requiring `performed_by`. |
| F-6 | N+1 query in enrollment analytics — 25 queries in a loop for 5 academic years | Code, Arch | **Replaced loop with single aggregated query** using conditional `func.count().filter()`. |
| F-7 | `db.get(StudentStatusChange, ...)` in `complete_withdrawal()` bypasses defense-in-depth tenant filter | Tenancy | **Replaced with explicit `select().where(tenant_id == ...)` query.** |

### High Fixes Applied

| # | Finding | Source | Resolution |
|---|---------|--------|------------|
| F-8 | RLS policy naming uses `tenant_isolation` but project convention is `tenant_isolation_{table_name}` | DB | **Updated all migration RLS statements** to use `tenant_isolation_{table_name}` pattern. Added note to use `rls_helpers.py` functions where available. |
| F-9 | Immutable audit tables (`student_status_changes`, `student_class_history`) granted UPDATE/DELETE unnecessarily | DB, Tenancy, Arch | **Changed GRANTs**: `student_status_changes` gets `SELECT, INSERT` only. `student_class_history` gets `SELECT, INSERT, UPDATE` (needs UPDATE for `left_date`). Removed DELETE from both. Updated AD-6 text to clarify `student_status_changes` is "append-only" while `student_class_history` is "append-mostly" (UPDATE allowed for closing assignments). |
| F-10 | `metadata` column name shadows SQLAlchemy reserved `Base.metadata` attribute | DB, Arch | **Renamed Python attribute to `change_metadata`** with explicit column mapping `mapped_column("metadata", JSONB, ...)`. DB column remains `metadata`. |
| F-11 | Missing magic byte validation on document upload — only checks client-provided MIME type | Security | **Added explicit `validate_file_magic()` call** in `upload_document()` service method spec, referencing existing `app/utils/sanitize.py`. |
| F-12 | Chain transfer does not verify user has access to destination school (only checks `tenant_id`) | Security | **Added `accessible_school_ids` check** — endpoint must verify the current user has access to both source and destination schools via the existing school access pattern. |
| F-13 | `structured_medical` JSONB has no bounds (no `max_length` on text fields, no `max_items` on lists) and no HTML sanitization | Security | **Added `max_length` validators** on all text fields, `max_items=50` on lists, and **`nh3.clean()` sanitization** on `emergency_protocol` and all `notes` fields. |
| F-14 | PDF template injection — user-controlled values rendered in WeasyPrint without confirmed autoescape | Security | **Added note** requiring `autoescape=True` in Jinja2 environment (verified this is the existing pattern in `PDFService`). Added explicit `nh3.clean()` call for `transfer_reason` and `destination_school` before passing to template context. |
| F-15 | `previous_schools` table missing `school_id` column (inconsistent with all other new tables) | Arch, Tenancy | **Added `school_id` FK** to `previous_schools` table schema, migration, and model. |
| F-16 | Race condition in withdrawal initiation — no database-level lock prevents concurrent initiation | Arch | **Added `.with_for_update()` on student row** before checking for existing clearances. Added `IntegrityError` catch on the unique index as a safety net. |
| F-17 | `initiate_withdrawal` creates status change with `to_status="withdrawn"` prematurely (before clearance) | Arch | **Changed to create status change only at `complete_withdrawal()` time.** Initiation now only creates the clearance record. The status change is the final step after clearance is verified. |
| F-18 | N+1 query in promotion rule evaluation — 40-160 queries per batch of students | Code | **Added batch query pattern** — load all students in one query, batch term averages/attendance/core passes into grouped queries, join results in Python. |
| F-19 | Server actions missing `getAuthContext()` call (no `token`/`subdomain` passed to `apiGet`) | Code | **Updated all server action examples** to include `getAuthContext()` and pass `{ token, subdomain }`. |
| F-20 | New tables not added to `verify_rls.py` and `tenant_cleanup.py` (recurring gap in specs) | Tenancy | **Added checklist items** in each phase to update `backend/scripts/verify_rls.py` and `backend/app/tasks/tenant_cleanup.py`. |

### Medium Fixes Applied

| # | Finding | Source | Resolution |
|---|---------|--------|------------|
| F-21 | `withdrawal_clearances.type` has no CHECK constraint | DB | **Added CHECK constraint** `type IN ('withdrawal', 'transfer')` to migration. |
| F-22 | Phase 3 claims "can run in parallel with Phase 2" but migration chain is serial | Arch | **Clarified in overview**: code development can be parallel, but migrations must be applied in order. Updated dependency diagram text. |
| F-23 | `student_class_history` CASCADE on `class_id` and `academic_year_id` deletes audit history | DB | **Changed both to `ondelete="RESTRICT"`** — prevents class/year deletion when history records exist. Same for `student_status_changes.school_id`. |
| F-24 | Response schemas use `str` for datetime fields instead of `datetime` | Code | **Changed to `datetime` type** in all response schemas for consistency with existing patterns. |
| F-25 | `WithdrawalClearanceUpdateRequest` cannot clear fields to None | Code | **Added note** to use `model_dump(exclude_unset=True)` pattern in endpoints. |
| F-26 | Chain transfer fee check blocks instead of warning (inconsistent with AD-4) | Arch | **Documented as intentional deviation** in AD-4 — chain transfers block with override since they don't have a clearance step. |
| F-27 | S3 key uses unsanitized filename | Security | **Added filename sanitization** — strip path separators and non-alphanumeric chars before constructing S3 key. |
| F-28 | `student_class_history` indexes missing `tenant_id` as leading column | DB | **Added `tenant_id` to `ix_sch_class_year` index** for multi-tenant query performance. |
