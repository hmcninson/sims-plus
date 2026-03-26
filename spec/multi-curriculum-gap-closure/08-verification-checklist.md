# Verification Checklist: Multi-Curriculum Gap Closure

Use this checklist to verify that all 37 requirements are satisfied after gap closure.

---

## How to Use

For each requirement:
1. **Before:** Note the current status
2. **After:** Perform the verification step
3. **Pass/Fail:** Mark the result
4. **Notes:** Record any observations

---

## 8.2 Curriculum Configuration

| ID | Requirement | Priority | Phase | Verification Step | Pass? |
|----|-------------|----------|-------|-------------------|-------|
| MC-001 | School-level curriculum selection | Must | Done | 1. Go to Settings > Curriculum > Profiles. 2. Create a Cambridge profile. 3. Set as default for school. 4. Verify school.curriculum_profile_id is set in DB. | |
| MC-002 | Class-level curriculum assignment | Must | Done | 1. Edit a class. 2. Set its curriculum profile to Cambridge (different from school default). 3. Verify class.curriculum_profile_id in DB. 4. Generate a report — should use Cambridge template. | |
| MC-003 | Student-level curriculum tracking | Must | Done | 1. Edit a student. 2. Set curriculum_profile_id. 3. Set previous_curriculum_type (for transfer). 4. Verify report uses student's profile, not class's. | |
| MC-004 | Custom curriculum definition | Should | Done | 1. Create a profile with type "custom". 2. Define custom assessment structure. 3. Enter scores. 4. Verify score calculation uses GES strategy (default for custom). | |
| MC-005 | Curriculum-specific calendar | Must | Phase 5 | 1. Set school to American profile (semesters, periods=2). 2. Create 2 terms — no warning. 3. Create a 3rd term — warning appears. 4. Verify term is still created (warning, not block). | |
| MC-006 | Subject mapping across curricula | Should | Done | 1. Go to Settings > Curriculum > Subject Mappings. 2. Map "Maths" to Cambridge code "0580". 3. Verify mapping saved. 4. Check export includes external code. | |

## 8.3 Grading Systems

| ID | Requirement | Priority | Phase | Verification Step | Pass? |
|----|-------------|----------|-------|-------------------|-------|
| MC-010 | Multiple grading scales per school | Must | Done | 1. Create WAEC scale and American GPA scale. 2. Link WAEC to GES profile, American to American profile. 3. Verify each profile resolves correct scale in reports. | |
| MC-011 | Ghana GES scale | Must | Done | 1. Enter scores for GES class. 2. Generate report. 3. Verify A1-F9 grading, CA/Exam split, class position. | |
| MC-012 | Cambridge/Edexcel scale A*-G | Must | Done | 1. Enter scores for Cambridge class. 2. Generate report. 3. Verify A*-G grades appear on Cambridge template. | |
| MC-013 | American letter grades A-F | Should | Phase 1 | 1. Enter scores for American class. 2. Generate report. 3. Verify A+/A/A-/B+/.../F grades. 4. Verify GPA is calculated and shown on report. | |
| MC-014 | American GPA calculation | Should | Phase 1 | 1. After report generation, check TermReport.gpa is not NULL. 2. Verify GPA range (0.0-4.0). 3. Check PDF shows GPA value. 4. Check cumulative GPA across 2 terms. | |
| MC-015 | IB scale 1-7 | Should | Phase 1 | 1. Enter scores for IB class. 2. Generate report. 3. Verify TermReport.ib_total_points is not NULL. 4. Check IB template shows total points out of 45. | |
| MC-016 | French scale 0-20 with mentions | Could | Phase 1 | 1. Enter scores for French class. 2. Generate report. 3. Verify TermReport.french_mention is set. 4. Verify mention text (Bien, Assez Bien, etc.) on report. | |
| MC-017 | Montessori narrative assessment | Should | Phase 4 | 1. Navigate to Montessori class score entry. 2. Verify narrative form appears (not numeric grid). 3. Enter developmental areas, skills, work samples, goals. 4. Save and verify stored in TermReport.extra_data. 5. Generate PDF — verify narrative content renders. | |
| MC-018 | Grade equivalency mapping | Could | Done | 1. Go to Settings > Curriculum > Grade Equivalencies. 2. Map WAEC A1 → Cambridge A*. 3. Use convert endpoint to verify. | |

## 8.4 Assessment Structures

| ID | Requirement | Priority | Phase | Verification Step | Pass? |
|----|-------------|----------|-------|-------------------|-------|
| MC-020 | Configurable assessment components | Must | Done | 1. Edit a curriculum profile's assessment structure. 2. Add/remove/reorder components. 3. Verify weights sum to 100. 4. Save and verify stored correctly. | |
| MC-021 | GES CA + Exam weighting | Must | Done | 1. Check default GES profile has class_work (20%), homework (10%), midterm (20%), end_term (50%). 2. Enter scores. 3. Verify report shows CA and Exam split. | |
| MC-022 | Cambridge assessment structure | Should | Done | 1. Create Cambridge profile from template. 2. Verify 3 components: Coursework (25%), Controlled Assessment (25%), External Exam (50%). | |
| MC-023 | IB IA + EA structure | Should | Done | 1. Create IB DP profile from template. 2. Verify 2 components: Internal Assessment (25%), External Assessment (75%). | |
| MC-024 | American assessment weighting | Should | Done | 1. Create American profile from template. 2. Verify 5 components: Homework, Quizzes, Tests, Projects, Finals. | |
| MC-025 | Predicted grades tracking | Should | Done | 1. Go to Exams > Predicted Grades. 2. Enter predictions for Cambridge students. 3. Verify saved with predicted_by and predicted_at. | |
| MC-026 | Criterion-referenced assessment | Could | Phase 7 | 1. Set IB MYP class with use_criterion_grading=true. 2. Enter criterion scores (A: 6, B: 5, C: 7, D: 6). 3. Verify total computed (24/32). 4. Verify final grade derived (level 6). 5. Verify criterion_scores JSONB stored on ExamScore. | |
| MC-027 | Credit/unit accumulation | Should | Done | 1. Go to Students > [student] > Credits. 2. View GPA dashboard. 3. Verify credits earned, GPA, honor roll. 4. Go to transcript page — verify full academic record. | |

## 8.5 Curriculum-Specific Report Cards

| ID | Requirement | Priority | Phase | Verification Step | Pass? |
|----|-------------|----------|-------|-------------------|-------|
| MC-030 | Curriculum-specific templates | Must | Done | 1. Generate reports for GES, Cambridge, American, IB, French, Montessori classes. 2. Verify each uses the correct HTML template. 3. Verify PDF renders correctly. | |
| MC-031 | GES report card | Must | Done | 1. Generate GES report. 2. Verify: scores, grades (A1-F9), class position, rankings, CA/Exam split. | |
| MC-032 | Cambridge report with effort grades | Should | Phase 2 | 1. Enter scores with effort_grade for Cambridge class. 2. Generate report. 3. Verify effort grade badges appear (1-5 colored). 4. Verify component grades shown. | |
| MC-033 | American report with GPA | Should | Phase 1 | 1. Generate American report after Phase 1 fix. 2. Verify GPA summary section shows term GPA, cumulative GPA, weighted GPA. 3. Verify credits earned. 4. Verify honor roll banner (if GPA >= 3.5). | |
| MC-034 | IB report with ATL/Learner Profile | Should | Phase 1 | 1. Generate IB report. 2. Verify IB total points shown. 3. ATL skills and Learner Profile will show "N/A" until data entry is implemented (acceptable for now). | |
| MC-035 | Montessori narrative report | Should | Phase 4 | 1. Enter Montessori narrative assessment. 2. Generate PDF. 3. Verify developmental areas, skills with progress levels, work samples, and goals render on report. | |
| MC-036 | Dual-track report | Should | Phase 4 | 1. Configure dual-track class (GES + Cambridge). 2. Set report_card_config.template_key = "dual_track". 3. Generate report. 4. Verify two result tables: GES and Cambridge. 5. Verify combined summary section. | |
| MC-037 | Transcript generation | Must | Done | 1. Go to Students > [student] > Transcript. 2. Select American profile. 3. Verify academic records by year/term. 4. Verify cumulative GPA and credits. 5. Print — verify print layout. | |

## 8.6 External Examinations

| ID | Requirement | Priority | Phase | Verification Step | Pass? |
|----|-------------|----------|-------|-------------------|-------|
| MC-040 | WAEC registration export | Must | Done | 1. Register students for WAEC. 2. Export as CSV. 3. Verify CSV columns: CandidateNumber, SubjectCode, SubjectName, Level. | |
| MC-041 | Cambridge registration support | Should | Done | 1. Register students for Cambridge IGCSE. 2. Export as CSV. 3. Verify CSV includes CenterNumber, ComponentCode. | |
| MC-042 | Edexcel registration support | Could | Phase 6 | 1. Register students for Edexcel. 2. Export as CSV. 3. Verify Edexcel-specific fields: QualificationCode, OptionCode, EntryLevel. | |
| MC-043 | IB registration support | Could | Phase 6 | 1. Register students for IB DP. 2. Export as CSV. 3. Verify IB fields: SchoolCode, Programme, SubjectGroup, Level (HL/SL). | |
| MC-044 | External exam results import | Should | Done | 1. Import WAEC results CSV. 2. Preview (dry-run). 3. Commit import. 4. Verify results stored in registration.results JSONB. | |
| MC-045 | Exam centre/candidate tracking | Should | Done | 1. Create registration with center_number and candidate_number. 2. Update them. 3. Verify stored and displayed. | |
| MC-046 | Mock exam curriculum integration | Should | Phase 5 | 1. Create mock exam for Cambridge class. 2. Enter and publish results. 3. Click "Generate Predicted Grades from Mock Results". 4. Verify PredictedGrade records created. 5. Go to Predicted Grades page — verify auto-generated entries with notes. | |

---

## Regression Verification

These tests verify that existing functionality is NOT broken by gap closure changes:

| # | Check | Steps | Pass? |
|---|-------|-------|-------|
| R1 | GES report generation unchanged | Generate a report for a GES class (no curriculum profile). Verify total_score, average_score, class_position are correct. GPA fields should be NULL. | |
| R2 | GES score entry unchanged | Enter scores for GES class. Verify no effort_grade column appears. Verify CA+Exam split works. | |
| R3 | GES parent portal unchanged | Login as GES parent. View grades. Verify CA+Exam format, no GPA section. | |
| R4 | Existing assessments unchanged | Run generate_term_reports for a class that was working before. Verify scores match previous values. | |
| R5 | Legacy assessment_weights still work | For a GES school using the old assessment_weights table (not migrated to assessment_structures), verify reports still generate correctly. | |
| R6 | PDF generation timing | Generate 30 reports for a class. Verify p95 < 5 seconds per report. No N+1 regressions. | |
| R7 | RLS isolation | Use test_curriculum_rls.py to verify all 9 curriculum tables still enforce tenant isolation. | |

---

## Sign-Off

| Phase | Developer | Reviewer | QA Verified | Date |
|-------|-----------|----------|-------------|------|
| Phase 1: Report Bridge | | | | |
| Phase 2: Score Entry | | | | |
| Phase 3: Parent + Analytics | | | | |
| Phase 4: Montessori + Dual-Track | | | | |
| Phase 5: Mock + Calendar | | | | |
| Phase 6: Export Extensions | | | | |
| Phase 7: Criterion Grading | | | | |
