# Verification Checklist

**Purpose:** End-to-end verification steps, cross-tenant security checks, and deployment checklist. Use this after all implementation is complete.

---

## 1. Pre-Deployment Checks

### 1.1 Database — Phase 1

- [ ] Migration `20260310_0100_curriculum_foundation.py` runs cleanly on fresh database
- [ ] Migration downgrade drops all tables + enums without errors
- [ ] New enum `curriculumtype` created with 8 values: ges, cambridge, edexcel, american, ib, french, montessori, custom
- [ ] New enum `assessmentcomponenttype` created with 25 values
- [ ] New enum `scoredisplaymode` created with 7 values
- [ ] `gradingscaletype` enum extended with 6 new values: cambridge, edexcel, ib, french, narrative, american
- [ ] 4 new tables created: `curriculum_profiles`, `assessment_structures`, `assessment_components`, `report_card_configs`
- [ ] All 4 tables have RLS enabled + forced
- [ ] All 4 tables have `tenant_isolation` policy using `get_current_tenant_id()`
- [ ] All 4 tables have `GRANT SELECT, INSERT, UPDATE, DELETE ON ... TO sims_app_user` (via `rls_helpers.enable_rls_for_table()`)
- [ ] RLS uses `enable_rls_for_table()` helper — NOT hand-written DDL
- [ ] Grants target `sims_app_user` — NOT `sims_admin`
- [ ] `curriculum_profile_id` column added to `schools`, `classes`, `students` (nullable FK)
- [ ] Data migration: GES Default profile created for every existing tenant with active schools
- [ ] Data migration: `ReportCardConfig` created for each GES Default profile
- [ ] Data migration: existing `assessment_weights` rows converted to `assessment_structures` + `assessment_components`
- [ ] Data migration: `ca_total_weight`/`exam_total_weight` from `assessment_weights` correctly normalized into component weights
- [ ] Unique constraint on `curriculum_profiles`: `(tenant_id, name)` prevents duplicate names per tenant
- [ ] COALESCE-based unique constraint on `assessment_structures`: `(tenant_id, curriculum_profile_id, COALESCE(academic_year_id, nil_uuid))`
- [ ] All indexes created (verify with `\di` in psql)

### 1.2 Database — Phase 2

- [ ] Migration `20260315_0100_grading_engine.py` runs cleanly
- [ ] 2 new tables created: `grade_equivalencies`, `subject_curriculum_mappings`
- [ ] Both tables have RLS enabled + forced + policies + grants
- [ ] 10 new columns added to `term_reports`: `curriculum_profile_id`, `gpa`, `weighted_gpa`, `cumulative_gpa`, `total_credits_earned`, `cumulative_credits`, `honor_roll`, `ib_total_points`, `french_mention`, `extra_data`
- [ ] `effort_grade` column added to `exam_scores` (VARCHAR(5), nullable)
- [ ] `credit_value` and `coefficient` columns added to `subjects` (NUMERIC, nullable)

### 1.3 Database — Phase 3

- [ ] Migration `20260320_0100_external_exams_and_credits.py` runs cleanly
- [ ] New enum `externalexamboard` created with 6 values
- [ ] 3 new tables created: `external_exam_registrations`, `student_credit_accumulations`, `predicted_grades`
- [ ] All 3 tables have RLS enabled + forced + policies + grants
- [ ] JSONB columns on `external_exam_registrations`: `subjects` (NOT NULL), `results` (nullable)
- [ ] COALESCE-based unique constraints on `student_credit_accumulations` and `predicted_grades`
- [ ] Run `python scripts/verify_rls.py` → all **100 tables** passing (91 existing + 9 new)

### 1.4 Backend Code

- [ ] All 9 new models registered in `backend/app/models/__init__.py`
- [ ] All models use `TenantMixin` (+ `SoftDeleteMixin` where specified) and `lazy="raise"` on relationships
- [ ] All enums use `values_callable=lambda x: [e.value for e in x]`
- [ ] All services use `flush()/refresh()` not `commit()`
- [ ] All services have defense-in-depth `.filter(Model.tenant_id == tenant_id)`
- [ ] `CURRICULUM_TEMPLATES` dictionary contains all 10 templates (ges_standard, cambridge_igcse, cambridge_a_level, edexcel_igcse, american_standard, american_ap, ib_myp, ib_dp, french_bac, montessori)
- [ ] Score strategy classes exist: GES, Cambridge, American, IB, French, Montessori
- [ ] `get_score_strategy(None)` returns `GESScoreStrategy` (fallback)
- [ ] `_resolve_curriculum_profile()` resolution chain: Student → Class → School → None
- [ ] Curriculum permissions added to `ROLE_PERMISSIONS` in `services/auth.py`:
  - `chain_admin`: `curriculum.*`
  - `school_admin`: `curriculum.*`
  - `academic_head`: `curriculum.read`
- [ ] Curriculum router registered in `backend/app/api/v1/router.py`
- [ ] No `from __future__ import annotations` in any endpoint files
- [ ] `TENANT_SCOPED_TABLES` in `conftest.py` updated with 9 new tables (total: 100)
- [ ] CSV import parser handles WAEC and Cambridge formats
- [ ] Transcript PDF template created at `backend/app/templates/reports/transcript.html`
- [ ] 5 curriculum-specific report card templates created (cambridge, american, ib, french, montessori)
- [ ] `SoftDeleteMixin` on: `CurriculumProfile`, `AssessmentStructure`, `ReportCardConfig`, `PredictedGrade`
- [ ] `curriculum_profiles` uses partial unique index `WHERE deleted_at IS NULL` (not table-level UNIQUE)
- [ ] Feature flag checks on ALL mutation paths: `create_profile`, `create_from_template`, `update_profile` (type change), `set_default_profile` (non-GES)
- [ ] All text ILIKE searches use `escape_ilike()` from `app.utils.sanitize`
- [ ] Jinja2 report templates use `autoescape=True`; `header_text`/`footer_text` stripped of HTML tags via Pydantic validator
- [ ] JSONB config fields validated: max 10KB, max nesting depth 5
- [ ] `parent_academic.py:get_child_grades()` updated to use strategy dispatch (not GES-specific)
- [ ] `analytics_service.py` updated for non-GES curricula
- [ ] `pdf.py` third caller of score results updated for strategy dispatch

### 1.5 Frontend Code

- [ ] TypeScript types created in `frontend/types/curriculum.type.ts`
- [ ] Server actions created in `frontend/actions/curriculum.action.ts`
- [ ] Sidebar "Curriculum" item added under Settings (school_admin+ only)
- [ ] Sidebar "External Exams" and "Predicted Grades" items added under Exams
- [ ] Curriculum settings pages created under `frontend/app/(dashboard)/settings/curriculum/`
- [ ] External exams pages created under `frontend/app/(dashboard)/exams/external/`
- [ ] Predicted grades page created at `frontend/app/(dashboard)/exams/predicted-grades/`
- [ ] Student transcript page created at `frontend/app/(dashboard)/students/[id]/transcript/`
- [ ] Student credits page created at `frontend/app/(dashboard)/students/[id]/credits/`
- [ ] Class create/edit forms include `CurriculumSelector` dropdown
- [ ] Score entry form shows effort grade column for Cambridge/Edexcel profiles
- [ ] Report card viewer switches layout based on curriculum type

---

## 2. End-to-End Functional Verification

### 2.1 Profile Management

- [ ] **Step 1:** Navigate to Settings > Curriculum → overview page loads
- [ ] **Step 2:** Click "Create Profile" → wizard opens
- [ ] **Step 3:** Select "Start from template" → template cards displayed (10 templates)
- [ ] **Step 4:** Select "Cambridge IGCSE" template → name pre-filled, settings pre-configured
- [ ] **Step 5:** Review assessment structure → 3 components (Coursework 25%, Controlled Assessment 25%, External Exam 50%), weights sum to 100%
- [ ] **Step 6:** Review report config → `show_effort_grade=true`, `show_predicted_grades=true`, `show_position=false`
- [ ] **Step 7:** Click "Create" → profile created, redirected to profile detail page
- [ ] **Step 8:** Edit profile name → saves successfully
- [ ] **Step 9:** Set as default → star icon appears, previous default unset
- [ ] **Step 10:** Delete profile (not default) → soft deleted, removed from list

### 2.2 Assessment Structure

- [ ] Navigate to profile detail → assessment structure section visible
- [ ] Add component → new row in table with type, name, weight inputs
- [ ] Edit component weight → running total updates
- [ ] Weights sum to 100% → green indicator
- [ ] Weights sum to != 100% → red indicator, save disabled
- [ ] Delete component → removed, total recalculates
- [ ] Validate structure → "Valid: weights total 100%" message
- [ ] Reorder components → sequence numbers update

### 2.3 Class Assignment

- [ ] Create new class → curriculum profile dropdown visible, optional
- [ ] Select Cambridge profile for a class → saves successfully
- [ ] Edit existing class → can change/add/remove curriculum profile
- [ ] Class with no profile → uses school default or GES fallback

### 2.4 Score Entry with Curriculum

- [ ] Cambridge class: score entry form shows effort grade column
- [ ] GES class: score entry form does NOT show effort grade column
- [ ] Cambridge: enter effort grade (1-5) → saved with score
- [ ] Score calculation uses correct strategy based on class's curriculum profile
- [ ] Score entry for class without profile → existing GES behavior unchanged

### 2.5 Report Card Generation

- [ ] Generate report for GES class → existing format with positions, class average
- [ ] Generate report for Cambridge class → no positions, effort grade shown, predicted grade shown
- [ ] Generate report for American class → GPA, credits, honor roll badge
- [ ] Generate report for IB class → IB total points, learner profile section
- [ ] Generate report for French class → /20 scores, coefficients, mention banner
- [ ] Generate report for Montessori class → narrative sections, progress levels
- [ ] Generate report for class with no profile → GES format (backward compatible)

### 2.6 Grade Equivalencies

- [ ] Navigate to Settings > Curriculum > Grade Equivalencies
- [ ] Select source scale (WAEC) and target scale (Cambridge IGCSE)
- [ ] Click cell to create mapping (WAEC A1 ↔ Cambridge A*)
- [ ] Existing mappings shown as filled cells
- [ ] Hover/click mapping shows notes field
- [ ] Save all → mappings persisted

### 2.7 External Exams

- [ ] Navigate to Exams > External Exams → list page loads
- [ ] Click "Register Student" → form opens
- [ ] Select exam board, session, student → add subjects → save
- [ ] Registration appears in list with correct status
- [ ] Click "Import Results" → wizard opens
- [ ] Upload valid WAEC CSV → preview shows matched/unmatched
- [ ] Confirm import → results saved to registrations
- [ ] Click "Export" > "WAEC Registration Export" → CSV downloaded
- [ ] View registration detail → subjects and results displayed

### 2.8 Credits & GPA (American Curriculum)

- [ ] Student in American class → credits tab visible on student profile
- [ ] Enter scores → credits auto-accumulated
- [ ] Navigate to student credits page → GPA trend chart, credit breakdown visible
- [ ] GPA calculation correct (verify manually)
- [ ] Honor roll badge shown when GPA >= 3.5
- [ ] AP course → weighted GPA bonus of +1.0
- [ ] Honors course → weighted GPA bonus of +0.5

### 2.9 Transcripts

- [ ] Student in American/credit-based class → transcript tab visible
- [ ] Navigate to transcript page → formatted transcript loads
- [ ] Term-by-term breakdown with correct subjects, grades, credits
- [ ] Cumulative summary correct
- [ ] Click "Download PDF" → PDF generated and downloaded
- [ ] Click "Print" → print dialog opens with clean A4 layout

### 2.10 Predicted Grades (Cambridge/IB)

- [ ] Navigate to Exams > Predicted Grades → page loads
- [ ] Select class with Cambridge profile, select subject
- [ ] Spreadsheet grid shows students with current average
- [ ] Enter predicted grade and target grade → inline editing works
- [ ] Click "Save All" → grades saved
- [ ] View student profile → predicted grades visible in tab

---

## 3. Cross-Tenant Security Verification

### 3.1 RLS Isolation — All 9 New Tables

- [ ] Tenant B cannot SELECT tenant A's `curriculum_profiles`
- [ ] Tenant B cannot SELECT tenant A's `assessment_structures`
- [ ] Tenant B cannot SELECT tenant A's `assessment_components`
- [ ] Tenant B cannot SELECT tenant A's `report_card_configs`
- [ ] Tenant B cannot SELECT tenant A's `grade_equivalencies`
- [ ] Tenant B cannot SELECT tenant A's `subject_curriculum_mappings`
- [ ] Tenant B cannot SELECT tenant A's `external_exam_registrations`
- [ ] Tenant B cannot SELECT tenant A's `student_credit_accumulations`
- [ ] Tenant B cannot SELECT tenant A's `predicted_grades`
- [ ] Tenant B cannot INSERT into any of tenant A's 9 tables (WITH CHECK prevents)
- [ ] Tenant B cannot UPDATE any of tenant A's 9 tables
- [ ] Tenant B cannot DELETE any of tenant A's 9 tables

### 3.2 Cross-Profile Security

- [ ] Cannot assign Tenant B's curriculum profile to Tenant A's class
- [ ] Cannot assign Tenant B's curriculum profile to Tenant A's school
- [ ] Cannot create assessment structure referencing Tenant B's profile
- [ ] Cannot create grade equivalency between Tenant B's grading scales
- [ ] Cannot create subject mapping to Tenant B's profile

### 3.3 Permission Enforcement

- [ ] Teacher cannot create/update/delete curriculum profiles (requires `curriculum.create`)
- [ ] Teacher cannot modify assessment structures (requires `curriculum.create`)
- [ ] Teacher CAN enter predicted grades (requires `exams.scores`)
- [ ] Finance Officer cannot access curriculum endpoints
- [ ] Academic Head can read but not modify profiles
- [ ] School Admin has full access to curriculum operations
- [ ] Parent cannot access any curriculum management endpoints

### 3.4 Defense-in-Depth

- [ ] All curriculum service methods include explicit `.filter(Model.tenant_id == tenant_id)`
- [ ] All FK references validated within same tenant (cannot reference cross-tenant entities)
- [ ] Soft-deleted profiles excluded from list queries but accessible by direct ID for audit

---

## 4. Backward Compatibility Verification

### 4.1 GES Schools — Zero Impact

- [ ] School with no curriculum profile → all features work exactly as before
- [ ] Exam creation unchanged
- [ ] CA management unchanged
- [ ] Score entry form unchanged (no effort grade column)
- [ ] Grade calculation unchanged (assessment_weights table still used)
- [ ] Report card generation → same PDF output
- [ ] Position calculation → same algorithm
- [ ] Class average → same calculation
- [ ] Score change audit logging → unchanged
- [ ] Exam analytics → unchanged

### 4.2 API Backward Compatibility

- [ ] `POST /exams/{id}/scores` still works without curriculum fields
- [ ] `GET /exams/{id}/report-cards` still works without curriculum profile
- [ ] `GET /academic/classes` response unchanged (new `curriculum_profile_id` field is optional)
- [ ] `GET /students` response unchanged (new `curriculum_profile_id` field is optional)
- [ ] No existing API contracts broken (all new fields are optional/additive)

### 4.3 Data Integrity

- [ ] Data migration created GES Default profiles only for tenants with active schools
- [ ] Data migration correctly converted assessment_weights → assessment_components
- [ ] Converted components have correct `maps_to_ca` / `maps_to_exam` flags
- [ ] Converted component weights match original assessment_weights percentages
- [ ] Original `assessment_weights` table NOT modified (still used by GES fallback path)
- [ ] No orphaned data after migration

---

## 5. Performance Verification

- [ ] Profile list with 50 profiles: < 200ms
- [ ] Template instantiation (create from template): < 1s
- [ ] Score calculation for 200 students × 10 subjects: < 5s
- [ ] Report card PDF generation with curriculum data: < 3s
- [ ] GPA calculation for student with 4 years of data: < 500ms
- [ ] Transcript generation for 8 terms: < 5s
- [ ] Results CSV import preview (500 rows): < 10s
- [ ] Grade equivalency matrix load (2 scales × 15 grades): < 200ms
- [ ] All composite indexes verified for query patterns used by services

---

## 6. Deployment Checklist

### 6.1 Migration Execution

```bash
# 1. Run all 3 curriculum migrations in order
alembic upgrade 20260310_0100  # Phase 1: Foundation
alembic upgrade 20260315_0100  # Phase 2: Grading engine
alembic upgrade 20260320_0100  # Phase 3: External exams & credits

# 2. Verify RLS
python scripts/verify_rls.py   # Should report 100 tables passing

# 3. Verify data migration
psql -c "SELECT COUNT(*) FROM curriculum_profiles WHERE curriculum_type = 'ges';"
# Should match number of active tenants with schools
```

### 6.2 Report Card Templates

Verify all 6 report card templates exist:
```bash
ls backend/app/templates/reports/
# Should include:
# report_card.html           (existing GES template)
# report_card_cambridge.html
# report_card_american.html
# report_card_ib.html
# report_card_french.html
# report_card_montessori.html
# transcript.html
```

### 6.3 Docker Rebuild

```bash
# Rebuild backend image (no new pip dependencies for curriculum)
docker compose build backend

# Rebuild frontend image
docker compose build frontend

# Restart
docker compose up -d
```

### 6.4 Post-Deployment Smoke Test

1. Login as school_admin
2. Navigate to Settings > Curriculum → page loads
3. Create a Cambridge IGCSE profile from template → success
4. Assign profile to a test class → success
5. Enter test scores for that class → effort grade column visible
6. Generate report card → Cambridge format rendered
7. Navigate to existing GES class → score entry unchanged, report card unchanged
8. Run `python scripts/verify_rls.py` → all 100 tables passing

### 6.5 Feature Flag Verification

- [ ] Starter plan tenant: can only create GES profiles
- [ ] Professional plan tenant: can create one non-GES profile
- [ ] Enterprise plan tenant: can create unlimited profiles (dual-track/hybrid)
- [ ] Attempting to create a profile beyond plan limits → 403 with clear message

---

## 7. Rollback Plan

If issues are found after deployment:

### 7.1 Phase 3 Rollback (Independent)

```bash
alembic downgrade 20260315_0100  # Roll back Phase 3 only
```
Drops: `external_exam_registrations`, `student_credit_accumulations`, `predicted_grades`, `externalexamboard` enum. Phase 1+2 features continue working.

### 7.2 Phase 2 Rollback

```bash
alembic downgrade 20260310_0100  # Roll back Phase 2 only
```
Drops: `grade_equivalencies`, `subject_curriculum_mappings`. Removes added columns from `term_reports`, `exam_scores`, `subjects`. Phase 1 features continue working. Report cards fall back to GES format.

### 7.3 Full Rollback

```bash
alembic downgrade 20260303_0200  # Roll back all curriculum changes (to last pre-curriculum migration)
```
Drops all 9 tables + 4 enums. Removes `curriculum_profile_id` from `schools`, `classes`, `students`. Existing GES functionality fully intact because:
- `assessment_weights` table was never modified
- Score calculation code has `if profile is None` fallback
- Report card generation has GES default path

### 7.4 Data Preservation

Before rolling back, export curriculum data:
```sql
-- Export profiles
COPY (SELECT * FROM curriculum_profiles) TO '/tmp/curriculum_profiles_backup.csv' CSV HEADER;

-- Export assessment structures
COPY (SELECT * FROM assessment_structures) TO '/tmp/assessment_structures_backup.csv' CSV HEADER;

-- Export external exam data
COPY (SELECT * FROM external_exam_registrations WHERE deleted_at IS NULL)
    TO '/tmp/external_exams_backup.csv' CSV HEADER;
```

### 7.5 Frontend Rollback

- Remove curriculum settings pages (returns 404 — no user-facing breakage since it's a new module)
- Remove external exams pages
- Remove curriculum-related sidebar items
- Score entry form reverts to no effort grade column
- Report cards revert to GES-only format
- No existing functionality affected

---

## 8. Monitoring Post-Deployment

### 8.1 Error Alerts

Watch for these in Sentry/logs during the first 48 hours:

- `CurriculumServiceError` exceptions
- Score strategy errors (incorrect curriculum type dispatch)
- Report card template rendering failures
- GPA calculation errors (division by zero, overflow)
- CSV import parsing errors
- RLS violations (should be zero — indicates a bug)

### 8.2 Metrics to Track

- Curriculum profile creation rate (expect low initially)
- Template usage distribution (which templates are popular)
- Report card generation time by curriculum type (compare to GES baseline)
- Score entry time with effort grades vs without
- External exam registration volume
- GPA calculation duration

### 8.3 Success Criteria

- Zero GES regression issues reported
- All 100 tables passing RLS verification
- Report card generation time within 20% of GES baseline
- No cross-tenant data leaks
- Score calculation accuracy verified against manual calculations
