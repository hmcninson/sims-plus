# Testing & Quality Assurance

**Purpose:** Complete testing strategy for multi-curriculum support across all 3 phases. Covers unit tests, integration tests, RLS isolation tests, and GES regression tests.

---

## Test Infrastructure

### New Tables for `TENANT_SCOPED_TABLES` in `conftest.py`

**Phase 1 (4 tables):**
```python
"curriculum_profiles",
"assessment_structures",
"assessment_components",
"report_card_configs",
```

**Phase 2 (2 tables):**
```python
"grade_equivalencies",
"subject_curriculum_mappings",
```

**Phase 3 (3 tables):**
```python
"external_exam_registrations",
"student_credit_accumulations",
"predicted_grades",
```

**Updated count:** 91 existing + 9 new = **100 total** (verify with `verify_rls.py`)

### Test Fixtures

Add to `conftest.py` or a dedicated `conftest_curriculum.py`:

```python
from decimal import Decimal

@pytest.fixture
async def curriculum_profile(db: AsyncSession, tenant_id: uuid.UUID, school_id: uuid.UUID):
    """Create a test GES curriculum profile."""
    from app.models.curriculum import CurriculumProfile
    profile = CurriculumProfile(
        tenant_id=tenant_id,
        school_id=school_id,
        name="GES Standard",
        curriculum_type="ges",
        academic_calendar_type="terms",
        periods_per_year=3,
        score_display_mode="grade_and_score",
        show_position=True,
        show_class_average=True,
        is_default=True,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@pytest.fixture
async def cambridge_profile(db: AsyncSession, tenant_id: uuid.UUID, school_id: uuid.UUID):
    """Create a test Cambridge IGCSE curriculum profile."""
    from app.models.curriculum import CurriculumProfile
    profile = CurriculumProfile(
        tenant_id=tenant_id,
        school_id=school_id,
        name="Cambridge IGCSE",
        curriculum_type="cambridge",
        academic_calendar_type="terms",
        periods_per_year=3,
        score_display_mode="grade_only",
        show_position=False,
        show_class_average=False,
        use_criterion_grading=True,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@pytest.fixture
async def american_profile(db: AsyncSession, tenant_id: uuid.UUID, school_id: uuid.UUID):
    """Create a test American curriculum profile."""
    from app.models.curriculum import CurriculumProfile
    profile = CurriculumProfile(
        tenant_id=tenant_id,
        school_id=school_id,
        name="American Standard",
        curriculum_type="american",
        academic_calendar_type="semesters",
        periods_per_year=2,
        score_display_mode="gpa",
        show_position=False,
        show_class_average=True,
        use_gpa=True,
        use_credits=True,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@pytest.fixture
async def assessment_structure(db: AsyncSession, tenant_id: uuid.UUID, curriculum_profile):
    """Create a test assessment structure with components."""
    from app.models.curriculum import AssessmentStructure, AssessmentComponent
    structure = AssessmentStructure(
        tenant_id=tenant_id,
        curriculum_profile_id=curriculum_profile.id,
        name="Standard GES Structure",
    )
    db.add(structure)
    await db.flush()
    await db.refresh(structure)

    components = [
        AssessmentComponent(
            tenant_id=tenant_id,
            assessment_structure_id=structure.id,
            component_type="class_work",
            name="Class Work",
            weight=Decimal("20.00"),
            max_score=Decimal("20.00"),
            sequence=1,
            maps_to_ca=True,
        ),
        AssessmentComponent(
            tenant_id=tenant_id,
            assessment_structure_id=structure.id,
            component_type="homework",
            name="Homework",
            weight=Decimal("10.00"),
            max_score=Decimal("10.00"),
            sequence=2,
            maps_to_ca=True,
        ),
        AssessmentComponent(
            tenant_id=tenant_id,
            assessment_structure_id=structure.id,
            component_type="midterm",
            name="Midterm",
            weight=Decimal("20.00"),
            max_score=Decimal("20.00"),
            sequence=3,
            maps_to_ca=True,
        ),
        AssessmentComponent(
            tenant_id=tenant_id,
            assessment_structure_id=structure.id,
            component_type="end_term",
            name="End of Term Exam",
            weight=Decimal("50.00"),
            max_score=Decimal("50.00"),
            sequence=4,
            maps_to_exam=True,
        ),
    ]
    for comp in components:
        db.add(comp)
    await db.flush()
    for comp in components:
        await db.refresh(comp)
    structure.components = components
    return structure
```

---

## Phase 1 Tests

### `test_curriculum_profiles.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 1.1 | `test_create_profile_ges` | Create GES profile → 201, correct defaults |
| 1.2 | `test_create_profile_cambridge` | Create Cambridge profile → 201, `show_position=False`, `use_criterion_grading=True` |
| 1.3 | `test_create_profile_american` | Create American profile → 201, `use_gpa=True`, `use_credits=True` |
| 1.4 | `test_create_profile_ib` | Create IB profile → 201, `use_criterion_grading=True` |
| 1.5 | `test_create_profile_french` | Create French profile → 201, `score_display_mode="mention"` |
| 1.6 | `test_create_profile_montessori` | Create Montessori profile → 201, `score_display_mode="narrative"` |
| 1.7 | `test_list_profiles` | List all profiles → returns array, sorted by name |
| 1.8 | `test_get_profile_detail` | Get profile by ID → includes `assessment_structure` and `report_config` |
| 1.9 | `test_update_profile` | Update profile name/settings → 200, fields updated |
| 1.10 | `test_delete_profile` | Soft delete profile → `deleted_at` set, not in list results |
| 1.11 | `test_set_default_profile` | Set profile as default → previous default unset, new default set |
| 1.12 | `test_only_one_default_per_school` | Create 2 defaults → only latest is default |
| 1.13 | `test_create_profile_invalid_type` | Invalid curriculum_type → 422 |
| 1.14 | `test_create_profile_missing_name` | Missing name → 422 |
| 1.15 | `test_profile_rls_isolation` | Tenant B cannot see Tenant A's profile |
| 1.16 | `test_create_profile_starter_plan_blocks_non_ges` | Starter tenant, `curriculum_type="cambridge"` → 403 plan_limit |
| 1.17 | `test_create_profile_professional_allows_one_non_ges` | Professional tenant, first non-GES → 201; second non-GES → 403 |
| 1.18 | `test_create_profile_enterprise_allows_unlimited` | Enterprise tenant, multiple non-GES profiles → all succeed |
| 1.19 | `test_create_from_template_respects_plan_limits` | Starter tenant, `template_key="cambridge_igcse"` → 403 |
| 1.20 | `test_cross_tenant_profile_assignment_blocked` | Assign Tenant B's profile to Tenant A's class → 404 |

### `test_assessment_structures.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 2.1 | `test_create_structure_with_components` | Create structure with 4 components → 201, components attached |
| 2.2 | `test_add_component` | Add component to existing structure → 201 |
| 2.3 | `test_update_component` | Update component weight → 200 |
| 2.4 | `test_delete_component` | Delete component → 204, removed from structure |
| 2.5 | `test_validate_structure_valid` | 4 components summing to 100% → `is_valid=True` |
| 2.6 | `test_validate_structure_invalid_weight` | Weights sum to 90% → `is_valid=False`, message contains "100" |
| 2.7 | `test_validate_structure_zero_components` | Empty structure → `is_valid=False` |
| 2.8 | `test_year_specific_structure` | Create structure with `academic_year_id` → resolves correctly |
| 2.9 | `test_structure_resolution_year_specific_over_default` | Year-specific structure takes precedence over default |
| 2.10 | `test_structure_rls_isolation` | Tenant B cannot see Tenant A's structures |

### `test_curriculum_templates.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 3.1 | `test_list_templates` | List all templates → returns 10 templates |
| 3.2 | `test_create_from_template_ges` | Create from `ges_standard` → profile + structure + config |
| 3.3 | `test_create_from_template_cambridge` | Create from `cambridge_igcse` → correct 3 components (Coursework 25%, Controlled Assessment 25%, External Exam 50%) |
| 3.4 | `test_create_from_template_american` | Create from `american_standard` → `use_gpa=True`, 4 components |
| 3.5 | `test_create_from_template_ib_dp` | Create from `ib_dp` → 7 components including EE/TOK/CAS |
| 3.6 | `test_create_from_template_french` | Create from `french_bac` → `score_display_mode="mention"`, coefficient-based |
| 3.7 | `test_create_from_template_invalid_key` | Invalid template key → 404 |
| 3.8 | `test_create_from_template_custom_name` | Override template name → profile uses custom name |
| 3.9 | `test_template_creates_correct_assessment_components` | For each template, verify component count, types, and weight sum = 100% |

### `test_report_card_configs.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 4.1 | `test_get_report_config` | Get config for profile → returns config with defaults |
| 4.2 | `test_update_report_config` | Update config toggles → 200, toggles persisted |
| 4.3 | `test_report_config_ges_defaults` | GES template → `show_position=True`, `show_effort_grade=False` |
| 4.4 | `test_report_config_cambridge_defaults` | Cambridge template → `show_effort_grade=True`, `show_predicted_grades=True` |
| 4.5 | `test_report_config_american_defaults` | American template → `show_gpa=True`, `show_credits=True`, `show_honor_roll=True` |
| 4.6 | `test_report_config_rls_isolation` | Tenant B cannot see Tenant A's config |

### `test_curriculum_class_integration.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 5.1 | `test_assign_profile_to_class` | Update class with `curriculum_profile_id` → 200 |
| 5.2 | `test_assign_profile_to_school` | Update school with `default_curriculum_profile_id` → 200 |
| 5.3 | `test_resolve_profile_from_class` | Class has profile → resolves to class profile |
| 5.4 | `test_resolve_profile_from_school` | Class has no profile, school has default → resolves to school default |
| 5.5 | `test_resolve_profile_fallback_none` | No profile anywhere → returns None (GES fallback) |
| 5.6 | `test_cannot_assign_other_tenant_profile` | Try to assign Tenant B's profile to Tenant A's class → 403/404 |

---

## Phase 2 Tests

### `test_score_strategies.py`

**Critical:** These test the core scoring engine for each curriculum type.

| # | Test Case | Description |
|---|-----------|-------------|
| 6.1 | `test_ges_strategy_standard` | GES: CA=40, Exam=60 → total=100, grade from scale |
| 6.2 | `test_ges_strategy_ca_breakdown` | GES: Class Work=15, Homework=8, Midterm=17, Exam=50 → CA=40, total=90 |
| 6.3 | `test_ges_strategy_zero_exam` | GES: CA=40, Exam=0 → total=40, grade correct |
| 6.4 | `test_ges_strategy_grade_boundaries` | GES: verify each grade boundary (A1=80+, B2=70-79, B3=65-69, etc.) |
| 6.5 | `test_cambridge_strategy` | Cambridge: components sum correctly, A*-G mapping |
| 6.6 | `test_cambridge_strategy_with_effort` | Cambridge: effort grade passed through |
| 6.7 | `test_cambridge_strategy_predicted` | Cambridge: includes predicted grade in result |
| 6.8 | `test_american_strategy_gpa` | American: score 95 → A → 4.0 GPA |
| 6.9 | `test_american_strategy_weighted_gpa` | American: AP course → 5.0 max, Honors → 4.5 max |
| 6.10 | `test_american_strategy_credits` | American: credits attempted/earned calculated |
| 6.11 | `test_ib_strategy_criterion` | IB: criterion grades (1-7) averaged, IB total calculated |
| 6.12 | `test_ib_strategy_total_points` | IB: 6 subjects × 7 + 3 bonus = 45 max |
| 6.13 | `test_french_strategy_coefficient` | French: score × coefficient, weighted average /20 |
| 6.14 | `test_french_strategy_mention` | French: 16+ = Très Bien, 14+ = Bien, 12+ = Assez Bien, 10+ = Passable |
| 6.15 | `test_montessori_strategy` | Montessori: narrative text returned, progress level set |
| 6.16 | `test_strategy_factory` | `get_score_strategy("cambridge")` → CambridgeScoreStrategy instance |
| 6.17 | `test_strategy_factory_unknown` | `get_score_strategy("unknown")` → GESScoreStrategy (fallback) |
| 6.18 | `test_strategy_factory_none` | `get_score_strategy(None)` → GESScoreStrategy (fallback) |

### `test_grade_equivalencies.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 7.1 | `test_create_equivalency` | Map WAEC A1 ↔ Cambridge A* → 201 |
| 7.2 | `test_list_equivalencies` | List all mappings between two scales → returns array |
| 7.3 | `test_delete_equivalency` | Delete mapping → 204 |
| 7.4 | `test_bulk_create_equivalencies` | Bulk create 8 mappings → 201, all created |
| 7.5 | `test_duplicate_equivalency` | Same source+target → 409 conflict |
| 7.6 | `test_equivalency_rls_isolation` | Tenant B cannot see Tenant A's mappings |

### `test_subject_curriculum_mappings.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 8.1 | `test_create_mapping` | Map subject to curriculum profile → 201 |
| 8.2 | `test_create_mapping_with_credits` | American: subject with credits=1.0 → 201, credits stored |
| 8.3 | `test_create_mapping_with_coefficient` | French: subject with coefficient=4 → 201 |
| 8.4 | `test_create_mapping_hl` | IB: subject with is_hl=True → 201 |
| 8.5 | `test_list_mappings_by_profile` | List mappings for profile → filtered results |
| 8.6 | `test_update_mapping` | Update external_code → 200 |
| 8.7 | `test_delete_mapping` | Delete mapping → 204 |
| 8.8 | `test_mapping_rls_isolation` | Tenant B cannot see Tenant A's mappings |

### `test_term_report_multicurriculum.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 9.1 | `test_generate_ges_report` | GES profile → report with position, class average (existing behavior) |
| 9.2 | `test_generate_cambridge_report` | Cambridge profile → report with effort grade, no position |
| 9.3 | `test_generate_american_report` | American profile → report with GPA, credits, honor roll |
| 9.4 | `test_generate_ib_report` | IB profile → report with IB total points |
| 9.5 | `test_generate_french_report` | French profile → report with mention, weighted average |
| 9.6 | `test_generate_montessori_report` | Montessori profile → report with narrative sections |
| 9.7 | `test_generate_report_no_profile` | No profile → GES fallback, identical to existing behavior |
| 9.8 | `test_report_pdf_template_selection` | Cambridge → `report_card_cambridge.html`, American → `report_card_american.html` |
| 9.9 | `test_calculate_student_term_scores_dispatched` | Cambridge profile → `calculate_student_term_scores()` uses strategy, not legacy GES logic |
| 9.10 | `test_calculate_student_term_scores_legacy` | No profile → `calculate_student_term_scores()` uses legacy GES logic unchanged |

---

## Phase 3 Tests

### `test_external_exam_registrations.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 10.1 | `test_create_registration` | Register student for WAEC → 201 |
| 10.2 | `test_create_registration_cambridge` | Register for Cambridge → 201, subjects with levels |
| 10.3 | `test_list_registrations` | List all → returns array |
| 10.4 | `test_list_registrations_filter_board` | Filter by exam_board=waec → only WAEC results |
| 10.5 | `test_list_registrations_filter_session` | Filter by exam_session → correct results |
| 10.6 | `test_get_registration` | Get by ID → 200, includes subjects array |
| 10.7 | `test_update_registration` | Update candidate_number → 200 |
| 10.8 | `test_update_registration_status` | Update status to "confirmed" → 200 |
| 10.9 | `test_duplicate_registration` | Same student+board+session → 409 conflict |
| 10.10 | `test_bulk_register` | Register 5 students at once → 201, count=5 |
| 10.11 | `test_bulk_register_max_200` | Register 201 students → 422 |
| 10.12 | `test_import_results` | Add results to registration → results stored in JSONB |
| 10.13 | `test_registration_rls_isolation` | Tenant B cannot see Tenant A's registrations |
| 10.14 | `test_delete_registration` | Soft delete → `deleted_at` set |

### `test_results_csv_import.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 11.1 | `test_import_waec_csv_preview` | Valid WAEC CSV, dryRun=True → preview with matched count |
| 11.2 | `test_import_waec_csv_commit` | Valid WAEC CSV, dryRun=False → results saved |
| 11.3 | `test_import_cambridge_csv_preview` | Valid Cambridge CSV → preview with matched count |
| 11.4 | `test_import_csv_no_match` | CSV with unknown candidate numbers → unmatched count > 0 |
| 11.5 | `test_import_csv_invalid_format` | Missing required columns → error with line numbers |
| 11.6 | `test_import_csv_partial_match` | Some rows match, some don't → correct matched/unmatched counts |
| 11.7 | `test_import_csv_empty` | Empty CSV → total_rows=0 |
| 11.8 | `test_import_csv_duplicate_rows` | Duplicate candidate+subject → error flagged |
| 11.9 | `test_import_csv_too_large` | File > 5MB → HTTP 413 |
| 11.10 | `test_import_csv_too_many_rows` | File > 2000 rows → error |
| 11.11 | `test_import_csv_formula_injection` | Cell starting with `=SUM(` → leading `=` stripped |
| 11.12 | `test_import_csv_invalid_encoding` | Non-UTF-8 file → error |

### `test_waec_cambridge_export.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 12.1 | `test_export_waec` | Export WAEC registrations → CSV with correct columns |
| 12.2 | `test_export_waec_empty` | No WAEC registrations → empty CSV with headers |
| 12.3 | `test_export_cambridge` | Export Cambridge registrations → CSV with correct columns |
| 12.4 | `test_export_filters_by_session` | Export with session filter → only that session's data |

### `test_credits_gpa.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 13.1 | `test_get_student_credits` | Student with 3 credit records → summary correct |
| 13.2 | `test_gpa_calculation_standard` | 3 subjects: A, B, C → GPA = (4.0+3.0+2.0)/3 = 3.0 |
| 13.3 | `test_gpa_calculation_with_ap` | AP course grade B → weighted = 4.0 (3.0+1.0) |
| 13.4 | `test_gpa_calculation_with_honors` | Honors course grade A → weighted = 4.5 (4.0+0.5) |
| 13.5 | `test_gpa_calculation_ap_cap` | AP course grade A → weighted = 5.0 (capped, not 5.0+1.0=6.0) |
| 13.6 | `test_cumulative_gpa` | Credits across 3 terms → cumulative GPA correct |
| 13.7 | `test_honor_roll_threshold` | GPA >= 3.5 → `honor_roll=True` |
| 13.8 | `test_honor_roll_below` | GPA = 3.4 → `honor_roll=False` |
| 13.9 | `test_credits_earned_vs_attempted` | Failed subject: attempted=1.0, earned=0 → totals correct |
| 13.10 | `test_recalculate_credits` | Modify score → recalculate → updated GPA |
| 13.11 | `test_credit_rls_isolation` | Tenant B cannot see Tenant A's credits |

### `test_predicted_grades.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 14.1 | `test_create_predicted_grade` | Create prediction → 201 |
| 14.2 | `test_update_predicted_grade` | Update predicted_grade → 200 |
| 14.3 | `test_list_predicted_grades` | List by student → returns array |
| 14.4 | `test_bulk_set_predicted_grades` | Bulk set for 20 students × 1 subject → 201 |
| 14.5 | `test_duplicate_predicted_grade` | Same student+subject+year+term → 409 conflict |
| 14.6 | `test_predicted_grade_includes_teacher` | `predicted_by` populated from current user |
| 14.7 | `test_predicted_grade_rls_isolation` | Tenant B cannot see Tenant A's predictions |

### `test_transcript.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 15.1 | `test_generate_transcript_data` | American student with 2 terms → correct structure |
| 15.2 | `test_transcript_cumulative_gpa` | Verify cumulative GPA matches manual calculation |
| 15.3 | `test_transcript_credits_remaining` | 18 earned, 24 required → 6 remaining |
| 15.4 | `test_transcript_pdf_generation` | Generate PDF → valid PDF bytes returned |
| 15.5 | `test_transcript_no_credits` | Student with no credit records → empty terms array |

---

## GES Regression Tests

**Purpose:** Ensure existing GES schools experience ZERO changes after multi-curriculum deployment.

### `test_ges_regression.py`

| # | Test Case | Description |
|---|-----------|-------------|
| R.1 | `test_ges_exam_score_entry_unchanged` | Enter CA + Exam scores without curriculum profile → works exactly as before |
| R.2 | `test_ges_term_report_unchanged` | Generate term report without curriculum profile → same format, same fields |
| R.3 | `test_ges_position_calculation_unchanged` | Class positions calculated the same way |
| R.4 | `test_ges_class_average_unchanged` | Class averages calculated the same way |
| R.5 | `test_ges_assessment_weights_still_work` | Existing `assessment_weights` table still used when no profile |
| R.6 | `test_ges_report_card_pdf_unchanged` | PDF report card for GES school → identical to pre-multicurriculum output |
| R.7 | `test_ges_grading_scales_unchanged` | WAEC/GPA/Percentage/Custom scales still work |
| R.8 | `test_ges_ca_management_unchanged` | CA CRUD still works without profile |
| R.9 | `test_ges_score_change_audit_unchanged` | Score change logging still works |
| R.10 | `test_ges_exam_analytics_unchanged` | Exam analytics/insights still work |

**Implementation approach:** Run the exact same test scenarios as existing exam tests but confirm no behavior change when `curriculum_profile_id` is NULL on the class/school.

---

## RLS Isolation Tests

### `test_curriculum_rls.py`

Test cross-tenant data isolation for all 9 new curriculum tables:

```python
@pytest.mark.parametrize("table_name", [
    "curriculum_profiles",
    "assessment_structures",
    "assessment_components",
    "report_card_configs",
    "grade_equivalencies",
    "subject_curriculum_mappings",
    "external_exam_registrations",
    "student_credit_accumulations",
    "predicted_grades",
])
async def test_rls_select_isolation(admin_engine, table_name, tenant_a_id, tenant_b_id):
    """Tenant B cannot SELECT tenant A's rows."""
    async with admin_engine.connect() as conn:
        # Insert a row for tenant A
        await conn.execute(text(f"""
            INSERT INTO {table_name} (id, tenant_id, ...)
            VALUES (gen_random_uuid(), :tenant_a_id, ...)
        """), {"tenant_a_id": str(tenant_a_id)})
        await conn.commit()

    # Switch to tenant B context
    async with app_engine.connect() as conn:
        await conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"),
                          {"tid": str(tenant_b_id)})
        result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        count = result.scalar()
        assert count == 0, f"Tenant B can see tenant A's {table_name} rows"


@pytest.mark.parametrize("table_name", [
    "curriculum_profiles",
    "assessment_structures",
    "assessment_components",
    "report_card_configs",
    "grade_equivalencies",
    "subject_curriculum_mappings",
    "external_exam_registrations",
    "student_credit_accumulations",
    "predicted_grades",
])
async def test_rls_insert_isolation(admin_engine, table_name, tenant_a_id, tenant_b_id):
    """Tenant B cannot INSERT into tenant A's rows (WITH CHECK)."""
    async with app_engine.connect() as conn:
        await conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"),
                          {"tid": str(tenant_b_id)})
        with pytest.raises(Exception):  # RLS WITH CHECK violation
            await conn.execute(text(f"""
                INSERT INTO {table_name} (id, tenant_id, ...)
                VALUES (gen_random_uuid(), :tenant_a_id, ...)
            """), {"tenant_a_id": str(tenant_a_id)})
```

### Dynamic RLS Verification

Extend the existing dynamic RLS test to include the new tables:

```python
async def test_all_tenant_scoped_tables_have_rls(admin_engine):
    """
    Query information_schema to verify ALL tenant-scoped tables have RLS.
    This catches future tables that are added but not secured.
    """
    async with admin_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT tablename, rowsecurity
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN (
                SELECT table_name FROM information_schema.columns
                WHERE column_name = 'tenant_id' AND table_schema = 'public'
            )
        """))
        rows = result.fetchall()
        for tablename, rowsecurity in rows:
            assert rowsecurity is True, f"Table {tablename} has tenant_id but RLS is not enabled"
```

---

## Integration Tests

### `test_curriculum_workflow_integration.py`

End-to-end workflow tests that verify multiple services work together:

| # | Test Case | Description |
|---|-----------|-------------|
| I.1 | `test_full_ges_workflow` | Create GES profile from template → assign to class → enter scores → generate report → verify report format |
| I.2 | `test_full_cambridge_workflow` | Create Cambridge profile → assign → enter scores with effort grades → generate report → verify no positions |
| I.3 | `test_full_american_workflow` | Create American profile → assign → enter scores → credits accumulated → GPA calculated → transcript generated |
| I.4 | `test_full_ib_workflow` | Create IB profile → assign → enter criterion grades → IB total calculated → report with learner profile |
| I.5 | `test_full_french_workflow` | Create French profile → assign → enter /20 scores → weighted average with coefficients → mention assigned |
| I.6 | `test_profile_switch` | Change class from GES to Cambridge → new reports use Cambridge format, old reports unchanged |
| I.7 | `test_external_exam_full_cycle` | Register → update status → import CSV results → verify results on student record |
| I.8 | `test_credit_accumulation_cycle` | Enter scores over 3 terms → credits accumulate → cumulative GPA correct → transcript complete |
| I.9 | `test_predicted_vs_actual` | Set predicted grades → enter actual scores → both visible on student profile |

---

## Performance Tests

### `test_curriculum_performance.py`

| # | Test Case | Description | Target |
|---|-----------|-------------|--------|
| P.1 | `test_profile_list_performance` | List 50 profiles → response time | < 200ms |
| P.2 | `test_score_calculation_performance` | Calculate scores for 200 students × 10 subjects | < 5s |
| P.3 | `test_report_generation_performance` | Generate 1 report card with curriculum data | < 3s |
| P.4 | `test_gpa_calculation_performance` | Calculate GPA for student with 4 years of data | < 500ms |
| P.5 | `test_transcript_generation_performance` | Generate transcript for student with 8 terms | < 5s |
| P.6 | `test_csv_import_performance` | Import 500-row results CSV (preview) | < 10s |

---

## Test Execution Commands

```bash
# Phase 1 tests
pytest tests/test_curriculum_profiles.py tests/test_assessment_structures.py \
       tests/test_curriculum_templates.py tests/test_report_card_configs.py \
       tests/test_curriculum_class_integration.py tests/test_curriculum_rls.py -v

# Phase 2 tests
pytest tests/test_score_strategies.py tests/test_grade_equivalencies.py \
       tests/test_subject_curriculum_mappings.py tests/test_term_report_multicurriculum.py -v

# Phase 3 tests
pytest tests/test_external_exam_registrations.py tests/test_results_csv_import.py \
       tests/test_waec_cambridge_export.py tests/test_credits_gpa.py \
       tests/test_predicted_grades.py tests/test_transcript.py -v

# GES regression tests
pytest tests/test_ges_regression.py -v

# All curriculum tests
pytest tests/test_curriculum*.py tests/test_score_strategies.py tests/test_grade*.py \
       tests/test_subject_curriculum*.py tests/test_term_report_multi*.py \
       tests/test_external_exam*.py tests/test_results_csv*.py tests/test_waec*.py \
       tests/test_credits*.py tests/test_predicted*.py tests/test_transcript.py \
       tests/test_ges_regression.py -v

# RLS verification
python scripts/verify_rls.py  # Should report 100 tables passing
```

---

## Test Coverage Targets

| Area | Target | Notes |
|------|--------|-------|
| Score Strategies | 100% | Critical business logic — every branch tested |
| GPA Calculation | 100% | Financial/academic accuracy critical |
| RLS Isolation | 100% | Security critical — all 9 tables |
| Profile CRUD | 90%+ | Standard CRUD with edge cases |
| Template Instantiation | 100% | All 10 templates verified |
| CSV Import | 90%+ | Valid, invalid, partial match, edge cases |
| GES Regression | 100% | All 10 regression scenarios pass |
| Frontend Components | 80%+ | Key interactions, not pure UI |

---

## Additional Test Cases (From Review Findings)

### `test_downstream_services.py`

Tests for services that contain independent GES-specific logic that must be updated.

| # | Test Case | Description |
|---|-----------|-------------|
| 15.1 | `test_parent_portal_grades_cambridge` | Student in Cambridge class → `parent_academic.get_child_grades()` returns Cambridge-formatted grades (not GES) |
| 15.2 | `test_parent_portal_grades_ges_unchanged` | Student in GES class → parent portal grades unchanged from current behavior |
| 15.3 | `test_analytics_service_cambridge` | Analytics for Cambridge class → uses correct score interpretation (not percentage-based) |
| 15.4 | `test_analytics_service_ges_unchanged` | Analytics for GES class → unchanged from current behavior |
| 15.5 | `test_pdf_service_strategy_dispatch` | `pdf.py` calls score results with correct strategy for non-GES class |

### `test_curriculum_switch.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 16.1 | `test_switch_curriculum_no_scores` | Switch class curriculum with no scores → immediate switch, no confirmation needed |
| 16.2 | `test_switch_curriculum_with_scores_no_confirm` | Switch with existing scores, `confirm=False` → returns impact summary, no switch |
| 16.3 | `test_switch_curriculum_with_scores_confirm` | Switch with existing scores, `confirm=True` → switch succeeds, audit event logged |
| 16.4 | `test_switch_curriculum_audit_event` | Switch → audit log contains old_profile_id, new_profile_id, affected counts |
| 16.5 | `test_switch_flags_reports_for_recalculation` | Switch → existing term reports flagged with `needs_recalculation` |

### `test_feature_flags_mutations.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 17.1 | `test_update_profile_type_starter_blocked` | Starter tenant: `update_profile()` changing type from GES to Cambridge → 403 |
| 17.2 | `test_update_profile_type_professional_allowed` | Professional tenant: change GES to Cambridge → allowed (first non-GES) |
| 17.3 | `test_set_default_non_ges_starter_blocked` | Starter tenant: `set_default_profile()` on Cambridge profile → 403 |
| 17.4 | `test_class_update_non_ges_profile_starter_blocked` | Starter tenant: `ClassService.update_class()` with Cambridge profile → 403 |

### `test_jsonb_validation.py`

| # | Test Case | Description |
|---|-----------|-------------|
| 18.1 | `test_config_over_10kb_rejected` | Create profile with >10KB config → validation error |
| 18.2 | `test_config_nested_too_deep_rejected` | Create profile with config nested >5 levels → validation error |
| 18.3 | `test_header_text_html_stripped` | Report config with `<script>alert(1)</script>` in header_text → tags stripped |
| 18.4 | `test_custom_columns_over_10kb_rejected` | Report config with >10KB custom_columns → validation error |
