# Preschool / Early Childhood Education — Gap Closure Overview

**Module:** Preschool / Early Childhood Education
**Sprint:** 20.5–22
**Complexity:** 6/10
**Author:** SIMS Plus Team
**Date:** 2026-03-23
**Status:** Implementation Plan

---

## 1. Executive Summary

The Preschool module was originally built in Sprints 11–12 with a strong foundation: developmental assessment (learning areas, skills, rating scales), progress observations, daily activity logs, and narrative-based progress reports with PDF generation. This gap closure addresses **9 fully missing features** and **9 partially implemented features** identified against the full requirements specification (PS-001 through PS-045).

The gaps fall into five categories:

1. **Daily Operations** — Incident/accident reporting with workflow, pickup authorization management, structured allergy/dietary alerts
2. **Enrollment Configuration** — Half-day/full-day session types, extended care tracking, caregiver-to-child ratio compliance
3. **Assessment Enhancement** — Visual progress timeline, learning stories/portfolios
4. **Report Enhancement** — Radar charts in PDF reports, photo inclusion, interim report types
5. **Fee Integration** — Session-based fee differentiation, extended care billing, sibling discount auto-detection

### What Already Works (DO NOT Re-implement)

| Feature | Status | Evidence |
|---------|--------|----------|
| Class levels: Creche, Nursery 1/2, KG1/KG2 | ✅ Done | `ClassLevel` enum in `academic/class_models.py` |
| Flexible class naming | ✅ Done | `Class.name` field separate from `Class.level` |
| Learning areas (8 defaults + CRUD) | ✅ Done | `LearningArea` model, 8 seed areas |
| Developmental skills (59 defaults + CRUD) | ✅ Done | `DevelopmentalSkill` model with age ranges |
| Configurable rating scales | ✅ Done | `PreschoolRatingScale` + `PreschoolRating` models |
| Teacher observations with attachments | ✅ Done | `ProgressObservation` model with JSONB attachments |
| Skill assessments (single + bulk) | ✅ Done | `StudentSkillAssessment` with upsert |
| Daily activity logs (meals, naps, diapers) | ✅ Done | `DailyActivityLog` model |
| Preschool progress reports | ✅ Done | `PreschoolReport` model + PDF template |
| No class ranking (age-appropriate) | ✅ Done | No ranking logic in preschool module |
| `can_pickup` flag on guardians | ✅ Done | `StudentGuardian.can_pickup` boolean |
| Free-text allergies field | ✅ Done | `Student.allergies` text column |
| Fee structures with `level_category` | ✅ Done | `FeeStructure.level_category = "preschool"` |

### Scope

| In Scope | Out of Scope |
|----------|-------------|
| Incident/accident reporting with status workflow | Medical record management / immunizations |
| Authorized pickup persons registry + pickup logs | Real-time photo verification at pickup |
| Structured dietary requirements (JSONB) | Meal planning / cafeteria management |
| Half-day/full-day enrollment sessions | Flexible weekly schedule (e.g., MWF only) |
| Extended care check-in/out + billing summary | Automated invoice generation from billing |
| Caregiver-to-child ratio configuration | Real-time occupancy monitoring |
| Learning stories / portfolio entries | Video portfolio streaming |
| Progress timeline (aggregated view) | AI-generated developmental insights |
| Report charts (SVG radar), photos, interim types | Multi-language report templates |
| Session-based fee differentiation | Hourly billing (sub-session granularity) |
| Sibling discount auto-detection | Cross-tenant sibling detection |
| Daily report sending to parents (SMS/email) | Real-time push notifications for each log entry |
| Supplies tracking (simple inventory) | Full inventory management (SKUs, POs) |

### Effort Estimate

| Metric | Value |
|--------|-------|
| New database tables | 7 |
| New enum types | 4 |
| New columns on existing tables | 6 |
| New API endpoints | ~35 |
| New Pydantic schemas | ~30 |
| New service methods | ~35 |
| New frontend pages | 5 |
| New frontend components | ~15 |
| New test files | ~10 |
| Estimated dev-days (raw) | 15–18 |
| Estimated dev-days (with 25% buffer) | 19–23 |

---

## 2. Architecture Decisions

### Decision 1: Allergy/Dietary Data as JSONB on Students (Not a Separate Table)

Structured dietary requirements are stored as a JSONB column (`dietary_requirements`) on the existing `students` table rather than a separate `student_allergies` table.

**Rationale:** Most students have 0–3 allergies. A JSONB column avoids a join for every daily log form load, aligns with the established JSONB pattern (`preschool_settings` on schools, `meals` on daily logs), and keeps the allergy data co-located with the student record for simple querying. A GIN index enables efficient filtering for class-wide allergy alerts.

### Decision 2: Incident Model is Preschool-Specific (Not Reusing Boarding Incidents)

A new `preschool_incidents` table is created rather than reusing `boarding_incidents`. Preschool incidents have different semantics (minor scrapes vs. disciplinary), different severities (minor/moderate/serious vs. low/medium/high/critical), a parent-notification workflow, and first-aid tracking.

**Rationale:** The boarding incident model is designed for SHS residential contexts. Preschool incidents require age-appropriate fields (first_aid_given, parent_notified_at) and a simpler workflow. Sharing a table would require awkward conditionals and risk exposing the wrong incident types in the wrong context.

### Decision 3: Extended Care as Separate Sessions (Not Extending Daily Logs)

Extended care is tracked via a separate `extended_care_sessions` table rather than adding fields to `daily_activity_logs`.

**Rationale:** A student may have both a daily log AND extended care on the same day — these are conceptually different (daily log = classroom activities; extended care = after-school supervision). A separate table also cleanly supports billing calculation without polluting the daily log query path.

### Decision 4: Learning Stories as Separate Table (Not Extending Observations)

Learning stories live in a new `learning_stories` table rather than being a new `ObservationType`.

**Rationale:** Observations are point-in-time notes by a teacher. Learning stories are curated narratives that reference multiple observations, span multiple learning areas, and include rich media. They are a portfolio-level construct that aggregates observations, not another observation type.

### Decision 5: Report Charts as Server-Side SVG (Not Client-Side JS)

Developmental domain radar charts in PDF reports are generated as inline SVG in the Jinja2 template, not via Recharts or Chart.js.

**Rationale:** WeasyPrint (the PDF engine) cannot execute JavaScript. SVG is natively supported by WeasyPrint and produces crisp, scalable charts. The radar chart data is passed as template context and rendered with SVG `<polygon>` and `<text>` elements.

### Decision 6: Sibling Discount via Existing Scholarship System

Sibling discounts are implemented as a new scholarship type (`SIBLING_DISCOUNT`) rather than a separate discount system.

**Rationale:** The scholarship system already has the infrastructure for auto-applying discounts to invoices at generation time. Adding a sibling detection query (shared guardian records) and a new scholarship type reuses proven code paths and keeps discount logic centralized.

### Decision 7: Single Migration per Phase

Each phase has one migration file to avoid branch conflicts and ensure atomic rollback:
- Phase 1: `20260328_0100_preschool_phase1.py`
- Phase 2: `20260330_0100_preschool_phase2.py`
- Phase 3: `20260401_0100_preschool_phase3.py`

---

## 3. Requirements Traceability

### 7.1 Preschool Configuration

| ID | Requirement | Priority | Status | Implementation |
|----|-------------|----------|--------|----------------|
| PS-001 | Creche level (0–2 years) | Must | ✅ Done | `ClassLevel.CRECHE` |
| PS-002 | Nursery levels (Nursery 1, 2) | Must | ✅ Done | `ClassLevel.NURSERY_1`, `NURSERY_2` |
| PS-003 | Kindergarten levels (KG1, KG2) | Must | ✅ Done | `ClassLevel.KG_1`, `KG_2` |
| PS-004 | Flexible class naming | Should | ✅ Done | `Class.name` field |
| PS-005 | Caregiver-to-child ratios | Should | ❌ Gap | Phase 2: `class_caregiver_ratios` table |
| PS-006 | Half-day/full-day enrollment | Must | ❌ Gap | Phase 1: `students.enrollment_session` column |
| PS-007 | Extended care tracking | Should | ❌ Gap | Phase 2: `extended_care_sessions` table |

### 7.2 Developmental Assessment

| ID | Requirement | Priority | Status | Implementation |
|----|-------------|----------|--------|----------------|
| PS-010 | Developmental domains | Must | ✅ Done | `LearningArea` model (8 defaults) |
| PS-011 | Milestone/skill checklist | Must | ✅ Done | `DevelopmentalSkill` (59 defaults) |
| PS-012 | Rating scale (non-numeric) | Must | ✅ Done | `PreschoolRatingScale` + `PreschoolRating` |
| PS-013 | Teacher observation notes | Must | ✅ Done | `ProgressObservation` model |
| PS-014 | Photo/video attachment | Should | ✅ Done | `ProgressObservation.attachments` JSONB |
| PS-015 | Progress timeline | Must | ⚠️ Partial | Phase 2: Timeline aggregation endpoint + UI |
| PS-016 | Learning stories / portfolios | Should | ❌ Gap | Phase 2: `learning_stories` table |
| PS-017 | No class ranking | Must | ✅ Done | No ranking logic exists |

### 7.3 Preschool Progress Reports

| ID | Requirement | Priority | Status | Implementation |
|----|-------------|----------|--------|----------------|
| PS-020 | Skill-based report templates | Must | ✅ Done | `PreschoolReport` + PDF template |
| PS-021 | Visual indicators (charts) | Must | ⚠️ Partial | Phase 2: SVG radar chart in PDF |
| PS-022 | Teacher narrative comments | Must | ✅ Done | `overall_progress`, `strengths`, etc. |
| PS-023 | Photos in reports | Should | ❌ Gap | Phase 2: `photo_urls` JSONB column |
| PS-024 | Next steps / goals | Should | ✅ Done | `next_term_goals` JSONB field |
| PS-025 | Parent-friendly language | Must | ✅ Done | Narrative-based, not grade-based |
| PS-026 | Interim report formats | Should | ❌ Gap | Phase 2: `report_type` column |

### 7.4 Preschool Daily Operations

| ID | Requirement | Priority | Status | Implementation |
|----|-------------|----------|--------|----------------|
| PS-030 | Daily activity logging | Should | ✅ Done | `DailyActivityLog` model |
| PS-031 | Pickup authorization | Must | ⚠️ Partial | Phase 1: `authorized_pickups` + `pickup_logs` |
| PS-032 | Pickup/drop-off time for billing | Should | ⚠️ Partial | Phase 2: Extended care integration |
| PS-033 | Allergy/dietary alerts | Must | ⚠️ Partial | Phase 1: `students.dietary_requirements` JSONB |
| PS-034 | Incident/accident reporting | Must | ⚠️ Partial | Phase 1: `preschool_incidents` table |
| PS-035 | Daily report to parents | Should | ❌ Gap | Phase 2: Send via NotificationDispatcher |
| PS-036 | Nap time tracking | Could | ✅ Done | `DailyActivityLog.nap_*` fields |
| PS-037 | Supplies tracking | Could | ❌ Gap | Phase 3: `preschool_supplies` table |

### 7.5 Preschool-Specific Fees

| ID | Requirement | Priority | Status | Implementation |
|----|-------------|----------|--------|----------------|
| PS-040 | Feeding program fees | Must | ⚠️ Partial | Can create manually; no auto-link |
| PS-041 | Half-day/full-day fee differentiation | Must | ❌ Gap | Phase 1: `fee_structures.session_type` |
| PS-042 | Extended care fees | Should | ❌ Gap | Phase 2: Billing summary endpoint |
| PS-043 | Supplies fee | Should | ✅ Done | Generic `FeeType` covers this |
| PS-044 | Registration deposit | Should | ✅ Done | Generic `FeeType` covers this |
| PS-045 | Sibling discount | Should | ⚠️ Partial | Phase 2: Auto-detect via shared guardians |

---

## 4. Phase Summary

### Phase 1: Must Have — Safety & Enrollment (Sprint 20.5)

**Focus:** Child safety features (incidents, pickups, allergies) and session-based enrollment/fees.

| Deliverable | New Tables | Modified Tables | New Endpoints | Est. Days |
|-------------|-----------|-----------------|---------------|-----------|
| Incident reporting | `preschool_incidents` | — | 6 | 2 |
| Pickup authorization | `authorized_pickups`, `pickup_logs` | — | 6 | 2 |
| Allergy/dietary alerts | — | `students` (+1 col) | 3 | 1 |
| Session enrollment | — | `students` (+1 col) | 0 (extend existing) | 0.5 |
| Session-based fees | — | `fee_structures` (+1 col) | 0 (extend existing) | 0.5 |
| Migration + tests | — | `conftest.py` | — | 1 |
| **Total** | **3** | **2** | **15** | **7** |

### Phase 2: Should Have — Enhancement & Integration (Sprint 21)

**Focus:** Portfolio features, timeline, report enhancements, extended care, parent communication.

| Deliverable | New Tables | Modified Tables | New Endpoints | Est. Days |
|-------------|-----------|-----------------|---------------|-----------|
| Learning stories | `learning_stories` | — | 5 | 2 |
| Extended care | `extended_care_sessions` | — | 4 | 2 |
| Caregiver ratios | `class_caregiver_ratios` | — | 2 | 0.5 |
| Progress timeline | — | — | 1 | 1 |
| Report enhancements | — | `preschool_reports` (+3 cols) | 0 (extend existing) | 1 |
| Daily report sending | — | — | 2 | 1 |
| Sibling discount | — | — | 3 | 1 |
| Migration + tests | — | `conftest.py` | — | 1 |
| **Total** | **3** | **1** | **17** | **9.5** |

### Phase 3: Could Have — Supplies (Sprint 22)

| Deliverable | New Tables | Modified Tables | New Endpoints | Est. Days |
|-------------|-----------|-----------------|---------------|-----------|
| Supplies tracking | `preschool_supplies` | — | 5 | 1.5 |
| Migration + tests | — | `conftest.py` | — | 0.5 |
| **Total** | **1** | **0** | **5** | **2** |

---

## 5. New Database Tables Summary

| # | Table | Phase | Purpose | RLS | Soft Delete |
|---|-------|-------|---------|-----|-------------|
| 1 | `preschool_incidents` | 1 | Incident/accident reports with workflow | Yes | Yes |
| 2 | `authorized_pickups` | 1 | Non-guardian authorized pickup persons | Yes | Yes |
| 3 | `pickup_logs` | 1 | Record of each pickup/drop-off event | Yes | No |
| 4 | `learning_stories` | 2 | Portfolio entries / curated narratives | Yes | Yes |
| 5 | `extended_care_sessions` | 2 | Before/after school care tracking | Yes | No |
| 6 | `class_caregiver_ratios` | 2 | Staff-to-child ratio configuration | Yes | No |
| 7 | `preschool_supplies` | 3 | Per-student supply inventory | Yes | Yes |

All tables include `tenant_id` (via TenantMixin) and `school_id` (nullable, for chain support).

---

## 6. Modified Tables Summary

| Table | Column Added | Type | Phase | Reason |
|-------|-------------|------|-------|--------|
| `students` | `enrollment_session` | VARCHAR(20), nullable | 1 | Half-day/full-day tracking (PS-006) |
| `students` | `dietary_requirements` | JSONB, nullable | 1 | Structured allergy data (PS-033) |
| `fee_structures` | `session_type` | VARCHAR(20), nullable | 1 | Session-based fee differentiation (PS-041) |
| `preschool_reports` | `report_type` | VARCHAR(20), default 'term' | 2 | Interim/progress update reports (PS-026) |
| `preschool_reports` | `photo_urls` | JSONB, nullable | 2 | Photos in reports (PS-023) |
| `preschool_reports` | `chart_data` | JSONB, nullable | 2 | Radar chart data for PDF (PS-021) |

---

## 7. New Enum Types

| Enum | Values | Phase | Table |
|------|--------|-------|-------|
| `PreschoolSessionType` | `half_day_morning`, `half_day_afternoon`, `full_day`, `extended` | 1 | `students.enrollment_session` |
| `PreschoolIncidentType` | `accident`, `illness`, `behavioral`, `allergic_reaction`, `other` | 1 | `preschool_incidents.incident_type` |
| `PreschoolIncidentSeverity` | `minor`, `moderate`, `serious` | 1 | `preschool_incidents.severity` |
| `PreschoolIncidentStatus` | `reported`, `reviewed`, `parent_notified`, `resolved` | 1 | `preschool_incidents.status` |

---

## 8. File Structure (New Files)

**IMPORTANT: File Splitting Required.** The existing preschool files already exceed recommended sizes (service: 1321 lines, endpoints: 1112 lines). Before Phase 1 implementation, **split into packages** following the existing `finance/`, `exam/`, `staff/` patterns:

- `backend/app/services/preschool/` — package with `__init__.py` re-exporting, split by domain
- `backend/app/api/v1/endpoints/preschool/` — package with combined router
- `backend/app/schemas/preschool/` — package split by domain

```
backend/
├── alembic/versions/
│   ├── 20260328_0100_preschool_phase1.py       # Phase 1 migration
│   ├── 20260330_0100_preschool_phase2.py       # Phase 2 migration
│   └── 20260401_0100_preschool_phase3.py       # Phase 3 migration
├── app/models/
│   └── preschool.py                            # MODIFIED: add 3 models (Phase 1), 3 models (Phase 2), 1 model (Phase 3)
├── app/schemas/preschool/                      # SPLIT from preschool.py into package
│   ├── __init__.py                             # Re-exports all schemas
│   ├── core.py                                 # Existing learning area, skill, rating, assessment schemas
│   ├── observation.py                          # Existing observation, daily log schemas
│   ├── report.py                               # Existing report schemas + Phase 2 additions
│   ├── incident.py                             # Phase 1: incident, allergy schemas
│   └── pickup.py                               # Phase 1: pickup, dietary schemas
├── app/services/preschool/                     # SPLIT from preschool.py into package
│   ├── __init__.py                             # Re-exports PreschoolService (or domain services)
│   ├── core_service.py                         # Existing: learning areas, skills, ratings, assessments
│   ├── observation_service.py                  # Existing: observations, daily logs
│   ├── report_service.py                       # Existing: reports + Phase 2 chart/photo enhancements
│   ├── incident_service.py                     # Phase 1: incidents
│   ├── pickup_service.py                       # Phase 1: pickups, allergy alerts
│   ├── portfolio_service.py                    # Phase 2: learning stories, timeline
│   └── extended_care_service.py                # Phase 2: extended care, caregiver ratios
├── app/api/v1/endpoints/preschool/             # SPLIT from preschool.py into package
│   ├── __init__.py                             # Combined router
│   ├── core.py                                 # Existing: learning areas, skills, ratings
│   ├── assessment.py                           # Existing: assessments
│   ├── observation.py                          # Existing: observations, daily logs
│   ├── report.py                               # Existing: reports
│   ├── incident.py                             # Phase 1: incidents
│   ├── pickup.py                               # Phase 1: pickups, allergy/dietary
│   ├── portfolio.py                            # Phase 2: learning stories, timeline
│   └── extended_care.py                        # Phase 2: extended care, caregiver ratios
└── tests/
    ├── test_preschool_incidents.py              # Phase 1
    ├── test_preschool_pickups.py                # Phase 1
    ├── test_preschool_allergy_alerts.py         # Phase 1
    ├── test_preschool_session_fees.py           # Phase 1
    ├── test_preschool_incidents_rls.py          # Phase 1
    ├── test_learning_stories.py                 # Phase 2
    ├── test_extended_care.py                    # Phase 2
    ├── test_student_timeline.py                 # Phase 2
    ├── test_daily_report_send.py                # Phase 2
    └── test_preschool_supplies.py               # Phase 3

frontend/
├── actions/
│   └── preschool.action.ts                     # MODIFIED: add ~20 new actions
├── types/
│   └── index.ts                                # MODIFIED: add new TypeScript interfaces
├── app/(dashboard)/preschool/
│   ├── incidents/page.tsx                       # Phase 1: NEW
│   ├── pickups/page.tsx                         # Phase 1: NEW
│   ├── portfolio/page.tsx                       # Phase 2: NEW
│   ├── extended-care/page.tsx                   # Phase 2: NEW
│   └── timeline/page.tsx                        # Phase 2: NEW
├── components/preschool/
│   ├── IncidentForm.tsx                         # Phase 1: NEW
│   ├── IncidentTimeline.tsx                     # Phase 1: NEW
│   ├── AuthorizedPickupList.tsx                 # Phase 1: NEW
│   ├── PickupLogForm.tsx                        # Phase 1: NEW
│   ├── AllergyAlert.tsx                         # Phase 1: NEW
│   ├── DietaryRequirementsForm.tsx              # Phase 1: NEW
│   ├── LearningStoryCard.tsx                    # Phase 2: NEW
│   ├── LearningStoryForm.tsx                    # Phase 2: NEW
│   ├── ProgressTimeline.tsx                     # Phase 2: NEW
│   ├── ExtendedCareCheckIn.tsx                  # Phase 2: NEW
│   ├── CaregiverRatioConfig.tsx                 # Phase 2: NEW
│   ├── ReportCharts.tsx                         # Phase 2: NEW (client-side preview)
│   ├── DailyReportSendButton.tsx                # Phase 2: NEW
│   ├── SupplyInventory.tsx                      # Phase 3: NEW
│   └── index.ts                                # MODIFIED: export new components
└── components/dashboard/
    └── app-sidebar.tsx                          # MODIFIED: add sidebar items
```

---

## 9. Integration Points

| Source | Target | Type | Description |
|--------|--------|------|-------------|
| Preschool incidents | Messaging (NotificationDispatcher) | Service call | Send SMS/email to guardians on serious incidents |
| Preschool daily logs | Messaging (NotificationDispatcher) | Service call | Send daily summary to parents |
| Extended care sessions | Finance (billing summary) | Data reference | Hours × rate calculation for manual invoicing |
| Student enrollment_session | Finance (fee structures) | Column filter | Fee lookup matches session_type |
| Sibling discount | Finance (scholarships) | Logic extension | Auto-detect siblings via shared guardian joins |
| Supplies low stock | Messaging (NotificationDispatcher) | Service call | Notify parents when supplies run low |

---

## 10. Migration Chain

```
user_sessions (file: 20260327_0100_user_sessions.py)
    → 20260328_0100_preschool_phase1
        → 20260330_0100_preschool_phase2
            → 20260401_0100_preschool_phase3
```

**Note:** The `down_revision` for Phase 1 must be `"user_sessions"` (the revision ID string), NOT `"20260327_0100"` (the filename prefix). Always check the actual `revision` variable in the target file.

---

## 11. Open Decisions (Resolved)

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Extended care billing: auto-invoice or manual? | Manual (billing summary endpoint) | Start simple; auto-invoice can be added later without schema changes |
| 2 | Sibling discount scope: same school or cross-school? | Same school for single-tenant; cross-school for chains | Aligns with existing chain model; `school_id` on `student_guardians` makes this queryable |
| 3 | Incident auto-escalation to school admin? | Yes, for "serious" severity | Child safety requires administrative awareness of serious incidents |
| 4 | Daily report SMS format? | Brief SMS + detailed email | SMS has 160-char limit; SMS is a prompt ("Daily report ready"), email has full details |
| 5 | Pickup photo verification? | Manual (teacher views stored photo) | Real-time comparison is Phase 4+ scope |
