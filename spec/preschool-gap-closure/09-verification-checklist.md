# Verification Checklist

Use this checklist to verify each phase is complete before moving to the next.

---

## Phase 1 Verification

### Database & Migration

- [ ] Migration `20260328_0100_preschool_phase1.py` runs without errors
- [ ] Migration rollback (`downgrade`) runs without errors
- [ ] 3 new tables exist: `preschool_incidents`, `authorized_pickups`, `pickup_logs`
- [ ] 4 new enum types created: `preschoolsessiontype`, `preschoolincidenttype`, `preschoolincidentseverity`, `preschoolincidentstatus`
- [ ] `students.enrollment_session` column exists (VARCHAR(20), nullable)
- [ ] `students.dietary_requirements` column exists (JSONB, nullable)
- [ ] `fee_structures.session_type` column exists (VARCHAR(20), nullable)
- [ ] GIN index on `students.dietary_requirements` exists
- [ ] All 3 new tables have RLS via `enable_rls_for_table()` from `app.db.rls_helpers`
- [ ] Policy names follow `tenant_isolation_{table_name}` convention (created by helper)
- [ ] All 3 new tables granted to `sims_app_user` (done by helper)
- [ ] CHECK constraints on `preschool_incidents` (incident_type, severity, status)
- [ ] CHECK constraint on `pickup_logs` (discriminator: exactly one pickup person ID set)
- [ ] `authorized_pickups` unique constraint is PARTIAL index (`WHERE deleted_at IS NULL`)
- [ ] `TENANT_SCOPED_TABLES` in `conftest.py` updated (+3, total 105)
- [ ] `verify_rls.py` updated (+3)

### Models

- [ ] `PreschoolIncident`, `AuthorizedPickup`, `PickupLog` models defined in `preschool.py`
- [ ] 4 enums defined: `PreschoolSessionType`, `PreschoolIncidentType`, `PreschoolIncidentSeverity`, `PreschoolIncidentStatus`
- [ ] `VALID_INCIDENT_TRANSITIONS` dict defined
- [ ] All relationships use `lazy="raise"`
- [ ] `PreschoolIncident` has `SoftDeleteMixin`
- [ ] `PickupLog` does NOT have `SoftDeleteMixin`
- [ ] All models have `school_id` (nullable)
- [ ] Models registered in `db/base.py`

### Schemas

- [ ] `AttachmentSchema` defined with HTTPS-only URL validation
- [ ] All create/update/response schemas defined for incidents, pickups, allergies
- [ ] `PickupLogCreate` validates exactly one pickup person ID provided
- [ ] `PreschoolIncidentCreate.description` has `min_length=10`
- [ ] `PreschoolIncidentCreate.incident_date` has future date validator
- [ ] `AllergyEntry.severity` validates against `mild|moderate|severe`
- [ ] `AuthorizedPickupCreate.photo_url/id_document_url` have HTTPS-only validators
- [ ] All response schemas have `model_config = ConfigDict(from_attributes=True)`

### Service Layer

- [ ] 6 incident methods: create, list, get, update, notify_parent, resolve
- [ ] 4 authorized pickup methods: add, list, update, deactivate
- [ ] 2 pickup log methods: record, list
- [ ] 3 allergy methods: get, update, get_class_alerts
- [ ] All methods filter by `tenant_id` (defense-in-depth)
- [ ] `record_pickup` validates `can_pickup` for guardians
- [ ] `record_pickup` validates active status for authorized persons
- [ ] `record_pickup` sets `pickup_date = date.today()` server-side
- [ ] Status transitions validated against `VALID_INCIDENT_TRANSITIONS`
- [ ] Student ownership verified before operations

### Endpoints

- [ ] All endpoints use `DatabaseSession`, `ValidatedUser`, `RequestTenant` type aliases (NOT `Depends(get_db)`)
- [ ] All endpoints use `convert_uuid(tenant.tenant_id)` when passing to service
- [ ] All endpoints use `dependencies=[Depends(require_permissions(...))]` in decorator
- [ ] 6 incident endpoints registered on router
- [ ] 4 authorized pickup endpoints registered
- [ ] 2 pickup log endpoints registered
- [ ] 3 allergy/dietary endpoints registered
- [ ] All endpoints require appropriate permissions
- [ ] Error codes mapped correctly (404 for not found, 403 for unauthorized pickup)
- [ ] Audit logging calls present on incident create, notify, and resolve endpoints

### Frontend

- [ ] TypeScript types added for all new models
- [ ] Server actions added for all new endpoints
- [ ] Incidents page renders and loads data
- [ ] Pickups page renders with 2 tabs
- [ ] AllergyAlert banner shows in daily log form
- [ ] DietaryRequirementsForm creates/updates dietary data
- [ ] Sidebar shows "Incidents" and "Pickups" items
- [ ] ConfigurationSettings shows new toggle cards

### Tests

- [ ] `test_preschool_incidents.py` — all tests pass
- [ ] `test_preschool_pickups.py` — all tests pass
- [ ] `test_preschool_allergy_alerts.py` — all tests pass
- [ ] `test_preschool_session_fees.py` — all tests pass
- [ ] `test_preschool_phase1_rls.py` — all tests pass
- [ ] Existing preschool tests still pass (no regressions)

### Security

- [ ] No IDOR vulnerabilities — cross-student access blocked
- [ ] Incident status transitions enforce valid paths only
- [ ] **Severity gate:** moderate/serious incidents require parent notification before resolution
- [ ] **Notification ordering:** SMS/email dispatched BEFORE status updated to parent_notified
- [ ] Pickup validation prevents unauthorized pickups
- [ ] `record_pickup` sets both `school_id` and server-side `pickup_date`
- [ ] `update_incident` uses PROTECTED_FIELDS blocklist
- [ ] S3 presigned URLs validated via HTTPS-only Pydantic validators
- [ ] No HTML injection in description/notes fields (plain text only)
- [ ] Student JOIN queries include `Student.tenant_id` filter (defense-in-depth)

---

## Phase 2 Verification

### Database & Migration

- [ ] Migration `20260330_0100_preschool_phase2.py` runs without errors
- [ ] 3 new tables: `learning_stories`, `extended_care_sessions`, `class_caregiver_ratios`
- [ ] `preschool_reports.report_type` column exists (VARCHAR(20), default 'term')
- [ ] `preschool_reports.photo_urls` column exists (JSONB, nullable)
- [ ] `preschool_reports.chart_data` column exists (JSONB, nullable)
- [ ] `uq_preschool_report` replaced with `uq_preschool_report_v2` (includes report_type)
- [ ] RLS enabled on all 3 new tables via `enable_rls_for_table()` helper
- [ ] CHECK constraints on `extended_care_sessions` (session_type, duration >= 0, checkout > checkin)
- [ ] `TENANT_SCOPED_TABLES` updated (+3 = total 108)

### Service Layer

- [ ] Learning story CRUD methods (5 methods)
- [ ] Extended care check-in/out methods (4 methods)
- [ ] Caregiver ratio methods (2 methods)
- [ ] Timeline aggregation method (1 method)
- [ ] Daily report sending methods (2 methods)
- [ ] Chart data computation method (_compute_chart_data)
- [ ] Billing summary calculation correct (hours × rate or sessions × flat_rate)
- [ ] Duration calculated correctly on check-out

### Frontend

- [ ] Portfolio page renders with story cards
- [ ] Extended Care page with check-in/out functionality
- [ ] Timeline page with visual timeline component
- [ ] CaregiverRatioConfig component in settings
- [ ] DailyReportSendButton works in daily logs
- [ ] Sidebar updated with 3 new items

### PDF Template

- [ ] SVG radar chart renders in PDF (test with WeasyPrint)
- [ ] Photo grid renders in PDF
- [ ] Interim reports render correctly (subset of fields)

### Tests

- [ ] All Phase 2 test files pass
- [ ] Phase 1 tests still pass (no regressions)

---

## Phase 3 Verification

### Database & Migration

- [ ] Migration `20260401_0100_preschool_phase3.py` runs without errors
- [ ] `preschool_supplies` table exists with RLS via helper
- [ ] CHECK constraints on `preschool_supplies` (quantity >= 0, threshold >= 0)
- [ ] `school_id` index exists on `preschool_supplies`
- [ ] `TENANT_SCOPED_TABLES` updated (+1 = total 109)

### Functionality

- [ ] Add supply, use supply, restock supply all work
- [ ] Low stock detection triggers correctly
- [ ] Cannot decrement below 0
- [ ] Restock sets `last_restocked_at`

### Tests

- [ ] All Phase 3 tests pass
- [ ] All Phase 1 + 2 tests still pass

---

## Cross-Phase Verification

- [ ] Full migration chain runs from scratch: `user_sessions` → `20260328_0100` → `20260330_0100` → `20260401_0100`
- [ ] Full rollback chain works in reverse (including `disable_rls_for_table()` calls)
- [ ] `verify_rls.py` passes with all 109 tables
- [ ] All RLS policies use `enable_rls_for_table()` from `app.db.rls_helpers` (not hand-rolled)
- [ ] No `from __future__ import annotations` in any endpoint files
- [ ] All raw SQL in tests uses `CAST(:param AS uuid)` for UUID params
- [ ] All enum values in raw SQL are lowercase
- [ ] No lazy loading violations at runtime (all relationships use `lazy="raise"`)
