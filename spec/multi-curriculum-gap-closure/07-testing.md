# Testing Plan: Multi-Curriculum Gap Closure

**Scope:** All 7 phases of the gap closure plan
**Existing Test Base:** 7 test files with 400+ cases (curriculum_profiles, external_exams, predicted_grades, feature_flags, rls, equivalencies, credits)

---

## Test File Organization

| File | Phase | New Cases | Focus |
|------|-------|-----------|-------|
| `test_curriculum_reports.py` (new) | 1 | 12-15 | Report generation aggregate population |
| `test_curriculum_score_entry.py` (new) | 2 | 8-10 | Effort grade entry, curriculum-aware forms |
| `test_parent_curriculum.py` (new) | 3 | 8-10 | Parent portal curriculum awareness |
| `test_analytics_curriculum.py` (new) | 3 | 6-8 | Analytics with curriculum pass marks |
| `test_montessori_assessment.py` (new) | 4 | 10-12 | Montessori narrative entry and reports |
| `test_dual_track_reports.py` (new) | 4 | 6-8 | Dual-track report generation |
| `test_mock_predicted_grades.py` (new) | 5 | 6-8 | Mock → predicted grade generation |
| `test_calendar_validation.py` (new) | 5 | 4-5 | Term count vs curriculum periods |
| Extend `test_curriculum_external_exams.py` | 6 | 4-6 | Edexcel/IB export formats |
| `test_criterion_scoring.py` (new) | 7 | 8-10 | Criterion-referenced grading |

**Total new test cases: ~75-90**

---

## Phase 1 Tests: Report Generation Bridge

### File: `backend/tests/test_curriculum_reports.py`

#### Setup Fixtures

```python
@pytest.fixture
async def american_profile(db, tenant_a_id, school_a_id):
    """Create an American curriculum profile with grading scale and assessment structure."""
    # 1. Create grading scale with A-F grades and grade points
    scale = GradingScale(
        tenant_id=tenant_a_id,
        name="American GPA Scale",
        scale_type="american",
    )
    db.add(scale)
    await db.flush()

    # Add grades: A+ (4.0), A (4.0), A- (3.7), B+ (3.3), ..., F (0.0)
    grades_data = [
        ("A+", 97, 100, Decimal("4.0")),
        ("A", 93, 96, Decimal("4.0")),
        ("A-", 90, 92, Decimal("3.7")),
        ("B+", 87, 89, Decimal("3.3")),
        ("B", 83, 86, Decimal("3.0")),
        ("B-", 80, 82, Decimal("2.7")),
        ("C+", 77, 79, Decimal("2.3")),
        ("C", 73, 76, Decimal("2.0")),
        ("C-", 70, 72, Decimal("1.7")),
        ("D+", 67, 69, Decimal("1.3")),
        ("D", 60, 66, Decimal("1.0")),
        ("F", 0, 59, Decimal("0.0")),
    ]
    for name, min_score, max_score, points in grades_data:
        db.add(Grade(
            tenant_id=tenant_a_id,
            grading_scale_id=scale.id,
            name=name,
            min_score=min_score,
            max_score=max_score,
            grade_point=points,
        ))

    # 2. Create curriculum profile
    profile = CurriculumProfile(
        tenant_id=tenant_a_id,
        school_id=school_a_id,
        name="American Standard",
        curriculum_type="american",
        grading_scale_id=scale.id,
        use_gpa=True,
        use_credits=True,
        score_display_mode="gpa",
    )
    db.add(profile)
    await db.flush()

    # 3. Create assessment structure with components
    structure = AssessmentStructure(
        tenant_id=tenant_a_id,
        curriculum_profile_id=profile.id,
        name="American Default",
        is_active=True,
    )
    db.add(structure)
    await db.flush()

    components = [
        ("homework", "Homework", Decimal("15")),
        ("quiz", "Quizzes", Decimal("15")),
        ("test", "Tests", Decimal("30")),
        ("project", "Projects", Decimal("10")),
        ("final", "Final Exam", Decimal("30")),
    ]
    for comp_type, name, weight in components:
        db.add(AssessmentComponent(
            tenant_id=tenant_a_id,
            assessment_structure_id=structure.id,
            component_type=comp_type,
            name=name,
            weight=weight,
            max_score=Decimal("100"),
        ))

    await db.flush()
    return profile
```

#### Test Cases

```python
class TestCurriculumReportGeneration:
    """Tests for curriculum-specific aggregate fields on TermReport."""

    @pytest.mark.asyncio
    async def test_american_gpa_populated(self, db, tenant_a_id, american_profile, ...):
        """GPA should be set on TermReport for American curriculum."""
        # Setup: class with american_profile, 3 students, exam with scores
        # Action: generate_term_reports()
        # Assert: report.gpa is not None
        # Assert: 0.0 <= report.gpa <= 4.0
        # Assert: report.curriculum_profile_id == american_profile.id

    @pytest.mark.asyncio
    async def test_american_honor_roll_true(self, db, ...):
        """Honor roll should be True when GPA >= 3.5."""
        # Setup: student scores averaging A- (90+) → GPA ~3.7
        # Assert: report.honor_roll == True

    @pytest.mark.asyncio
    async def test_american_honor_roll_false(self, db, ...):
        """Honor roll should be False when GPA < 3.5."""
        # Setup: student scores averaging C+ → GPA ~2.3
        # Assert: report.honor_roll == False

    @pytest.mark.asyncio
    async def test_cumulative_gpa_first_term(self, db, ...):
        """First term cumulative GPA equals term GPA."""
        # Assert: report.cumulative_gpa == report.gpa

    @pytest.mark.asyncio
    async def test_cumulative_gpa_multi_term(self, db, ...):
        """Cumulative GPA averages across terms."""
        # Term 1 GPA: 3.5, Term 2 GPA: 3.0
        # Assert: Term 2 report.cumulative_gpa == 3.25

    @pytest.mark.asyncio
    async def test_ib_total_points_populated(self, db, ...):
        """IB total points should be set for IB curriculum."""
        # Setup: IB profile, 6 subjects, each scored level 5
        # Assert: report.ib_total_points == 30

    @pytest.mark.asyncio
    async def test_french_mention_populated(self, db, ...):
        """French mention should be set for French curriculum."""
        # Setup: French profile, scores averaging 15/20
        # Assert: report.french_mention == "Bien"

    @pytest.mark.asyncio
    async def test_ges_unchanged(self, db, ...):
        """GES schools should not have curriculum fields populated."""
        # Setup: no curriculum profile (GES default)
        # Assert: report.gpa is None
        # Assert: report.ib_total_points is None
        # Assert: report.french_mention is None
        # Assert: report.total_score is not None (still works)

    @pytest.mark.asyncio
    async def test_subject_position_in_curriculum_path(self, db, ...):
        """Subject positions should be calculated for non-GES curricula."""
        # Setup: Cambridge profile, 3 students, different scores per subject
        # Assert: highest scorer has subject_position == 1

    @pytest.mark.asyncio
    async def test_pdf_context_not_none_for_american(self, db, ...):
        """PDF template context should have actual GPA data."""
        # Setup: American profile, generate report with GPA
        # Mock or capture PDF template context
        # Assert: context["term_gpa"] == report.gpa
        # Assert: context["honor_roll"] == report.honor_roll
```

---

## Phase 2 Tests: Score Entry

### File: `backend/tests/test_curriculum_score_entry.py`

```python
class TestEffortGradeEntry:
    """Tests for effort grade in score entry."""

    @pytest.mark.asyncio
    async def test_effort_grade_saved(self, db, tenant_a_id, ...):
        """Effort grade should be saved with score entry."""
        # Setup: Cambridge class, enter scores with effort_grade="2"
        # Assert: ExamScore.effort_grade == "2"

    @pytest.mark.asyncio
    async def test_effort_grade_optional(self, db, ...):
        """Score entry without effort_grade should work (backward compat)."""
        # Setup: GES class, enter scores WITHOUT effort_grade
        # Assert: no error, ExamScore.effort_grade is None

    @pytest.mark.asyncio
    async def test_effort_grade_validation(self, db, ...):
        """Invalid effort grade values should be rejected."""
        # Setup: effort_grade="X" or "10"
        # Assert: 422 validation error

    @pytest.mark.asyncio
    async def test_score_form_includes_curriculum_context(self, db, ...):
        """Score entry form should include curriculum_type for Cambridge."""
        # Setup: Cambridge class
        # Action: get_score_entry_form()
        # Assert: response includes curriculum_type="cambridge"
        # Assert: response includes show_effort_grade=True

    @pytest.mark.asyncio
    async def test_score_form_ges_no_effort_grade(self, db, ...):
        """GES score form should not show effort grade."""
        # Assert: response includes show_effort_grade=False

    @pytest.mark.asyncio
    async def test_effort_grade_in_report_results(self, db, ...):
        """Effort grade should appear in subject results for Cambridge."""
        # Setup: Cambridge class, scores with effort_grade
        # Action: get_student_subject_results()
        # Assert: subject_result["effort_grade"] == "2"
```

---

## Phase 3 Tests: Parent Portal & Analytics

### File: `backend/tests/test_parent_curriculum.py`

```python
class TestParentCurriculumGrades:
    @pytest.mark.asyncio
    async def test_parent_sees_gpa_for_american_child(self, db, ...):
        """Parent of American-curriculum child sees GPA."""
        # Assert: response includes gpa, honor_roll

    @pytest.mark.asyncio
    async def test_parent_sees_ib_points(self, db, ...):
        """Parent of IB child sees total IB points."""
        # Assert: response includes ib_total_points

    @pytest.mark.asyncio
    async def test_parent_ges_unchanged(self, db, ...):
        """GES parent sees unchanged grade format."""
        # Assert: gpa is None, standard CA+Exam display

    @pytest.mark.asyncio
    async def test_grade_trend_american_shows_gpa(self, db, ...):
        """American grade trend shows GPA metric."""
        # Assert: trend entries have metric="gpa"
```

### File: `backend/tests/test_analytics_curriculum.py`

```python
class TestAnalyticsCurriculum:
    @pytest.mark.asyncio
    async def test_pass_mark_american(self, db, ...):
        """American curriculum uses 60% pass mark."""
        # Assert: analytics uses 60% not 50%

    @pytest.mark.asyncio
    async def test_montessori_no_pass_fail(self, db, ...):
        """Montessori analytics has null pass/fail rates."""
        # Assert: pass_rate is None, fail_rate is None

    @pytest.mark.asyncio
    async def test_analytics_includes_curriculum_type(self, db, ...):
        """Analytics response includes curriculum context."""
        # Assert: response.curriculum_type == "cambridge"
```

---

## Phase 4 Tests: Montessori & Dual-Track

### File: `backend/tests/test_montessori_assessment.py`

```python
class TestMontessoriAssessment:
    @pytest.mark.asyncio
    async def test_save_assessment(self, db, ...):
        """Save Montessori narrative assessment."""
        # Assert: TermReport.extra_data contains developmental_areas

    @pytest.mark.asyncio
    async def test_reject_for_non_montessori(self, db, ...):
        """Reject narrative assessment for non-Montessori classes."""
        # Assert: 400 error with "invalid_curriculum"

    @pytest.mark.asyncio
    async def test_html_stripped_from_narrative(self, db, ...):
        """HTML tags should be stripped from narrative text."""
        # Input: "Student is <script>alert('xss')</script> progressing"
        # Assert: stored as "Student is alert('xss') progressing"

    @pytest.mark.asyncio
    async def test_pdf_renders_with_montessori_data(self, db, ...):
        """Montessori PDF should include developmental areas."""
        # Assert: template context["developmental_areas"] is not empty

    @pytest.mark.asyncio
    async def test_update_existing_assessment(self, db, ...):
        """Updating assessment overwrites extra_data."""
        # Save once, save again with different data
        # Assert: only latest data is stored
```

### File: `backend/tests/test_dual_track_reports.py`

```python
class TestDualTrackReports:
    @pytest.mark.asyncio
    async def test_dual_track_generates_both_result_sets(self, db, ...):
        """Dual-track report has both GES and international results."""
        # Assert: context has ges_results and international_results

    @pytest.mark.asyncio
    async def test_dual_track_template_selected(self, db, ...):
        """Dual-track config selects dual_track_report.html template."""
        # Assert: template == "dual_track_report.html"

    @pytest.mark.asyncio
    async def test_non_dual_track_uses_single_template(self, db, ...):
        """Non-dual-track classes use standard single template."""
        # Assert: Cambridge class uses cambridge_report.html, not dual_track
```

---

## Phase 5 Tests: Mock Exams & Calendar

### File: `backend/tests/test_mock_predicted_grades.py`

```python
class TestMockToPredictedGrades:
    @pytest.mark.asyncio
    async def test_generate_predicted_grades_from_mock(self, db, ...):
        """Published mock results generate predicted grades."""
        # Assert: created > 0

    @pytest.mark.asyncio
    async def test_reject_non_mock_exam(self, db, ...):
        """Non-mock exams cannot generate predicted grades."""
        # Assert: error "invalid_type"

    @pytest.mark.asyncio
    async def test_reject_unpublished_mock(self, db, ...):
        """Unpublished mock results cannot generate predicted grades."""
        # Assert: error "invalid_status"

    @pytest.mark.asyncio
    async def test_updates_existing_predicted_grades(self, db, ...):
        """Existing predicted grades are updated, not duplicated."""
        # Run twice, assert no duplicates, updated count > 0

    @pytest.mark.asyncio
    async def test_absent_students_skipped(self, db, ...):
        """Students marked absent in mock are skipped."""
        # Assert: skipped > 0
```

### File: `backend/tests/test_calendar_validation.py`

```python
class TestCalendarValidation:
    @pytest.mark.asyncio
    async def test_warning_when_exceeding_periods(self, db, ...):
        """Warning when creating 3rd term for 2-semester curriculum."""
        # Setup: profile with periods_per_year=2
        # Create 2 terms (no warning), then 3rd
        # Assert: warning is not None

    @pytest.mark.asyncio
    async def test_no_warning_within_limits(self, db, ...):
        """No warning when term count matches periods_per_year."""
        # Setup: profile with periods_per_year=3
        # Create 3 terms
        # Assert: warning is None for all three

    @pytest.mark.asyncio
    async def test_no_warning_without_profile(self, db, ...):
        """No warning when school has no curriculum profile."""
        # Assert: warning is None regardless of term count
```

---

## RLS Test Extensions

### File: `backend/tests/test_curriculum_rls.py` (extend existing)

Verify that all new data flows respect tenant isolation:

> **>>REVIEW FIX (M-6):** The tenancy architect flagged that cross-tenant isolation tests
> were only planned for Montessori. Add tests for ALL new data paths.

```python
class TestCurriculumGapClosureRLSIsolation:
    """Verify all new data paths respect tenant isolation."""

    @pytest.mark.asyncio
    @pytest.mark.rls
    async def test_montessori_assessment_tenant_isolated(self, ...):
        """Tenant B cannot see Tenant A's Montessori assessments."""
        # Save assessment for Tenant A
        # Switch to Tenant B context
        # Assert: cannot read Tenant A's TermReport

    @pytest.mark.asyncio
    @pytest.mark.rls
    async def test_cumulative_gpa_tenant_isolated(self, ...):
        """Cumulative GPA query only reads current tenant's TermReports."""
        # Create TermReports for Tenant A and Tenant B
        # Compute cumulative GPA for Tenant A student
        # Assert: only Tenant A's TermReports are included

    @pytest.mark.asyncio
    @pytest.mark.rls
    async def test_mock_predicted_grades_tenant_isolated(self, ...):
        """Mock → predicted grades only creates records in current tenant."""
        # Generate predicted grades for Tenant A's mock exam
        # Switch to Tenant B
        # Assert: Tenant B cannot see Tenant A's predicted grades

    @pytest.mark.asyncio
    @pytest.mark.rls
    async def test_dual_track_results_tenant_isolated(self, ...):
        """Dual-track report generation uses only current tenant's data."""
        # Generate dual-track report for Tenant A
        # Assert: both GES and international results are Tenant A's only

    @pytest.mark.asyncio
    @pytest.mark.rls
    async def test_subject_positions_tenant_isolated(self, ...):
        """Subject position calculation uses only current tenant's students."""
        # Pre-compute rankings for Tenant A's class
        # Assert: only Tenant A's students are ranked
```

---

## Test Infrastructure Notes

### Fixtures to Add to `conftest.py`

```python
@pytest.fixture
async def american_class(db, tenant_a_id, school_a_id, american_profile):
    """A class with American curriculum profile."""
    cls = Class(
        tenant_id=tenant_a_id,
        school_id=school_a_id,
        name="Grade 10",
        curriculum_profile_id=american_profile.id,
    )
    db.add(cls)
    await db.flush()
    return cls

@pytest.fixture
async def cambridge_class(db, tenant_a_id, school_a_id, cambridge_profile):
    """A class with Cambridge IGCSE curriculum profile."""
    ...

@pytest.fixture
async def montessori_class(db, tenant_a_id, school_a_id, montessori_profile):
    """A class with Montessori curriculum profile."""
    ...
```

### Subscription Tier in Tests

Many curriculum features require Professional+ plan. Ensure test tenant has `subscription_tier = "professional"` or `"enterprise"`:

```python
@pytest.fixture
async def professional_tenant(db, tenant_a_id):
    """Upgrade tenant to professional plan for curriculum tests."""
    await db.execute(
        update(Tenant)
        .where(Tenant.id == tenant_a_id)
        .values(subscription_tier="professional")
    )
    await db.flush()
```

### Test Markers

Add custom markers for selective running:

```python
# conftest.py or pytest.ini
[pytest.ini_options]
markers = [
    "curriculum: multi-curriculum tests",
    "curriculum_reports: curriculum report generation tests",
    "montessori: Montessori-specific tests",
    "dual_track: dual-track reporting tests",
]
```

Run specific phases:
```bash
pytest -m curriculum_reports   # Phase 1 only
pytest -m montessori           # Phase 4 Montessori only
pytest -m curriculum           # All curriculum tests
```

---

## Defense-in-Depth Tests (Tenancy Architect Recommendations)

> **>>REVIEW FIX (M-1, M-5):** The tenancy architect identified that the curriculum-path
> Grade query (report_service.py ~line 1212) and Subject JOIN (~line 1188) are missing
> explicit `tenant_id` filters. While RLS protects at the DB level, defense-in-depth
> requires application-level filters too. Add these tests to verify the fix:

```python
class TestDefenseInDepthFilters:
    """Verify all new queries include explicit tenant_id filters."""

    @pytest.mark.asyncio
    async def test_grade_query_includes_tenant_id(self, ...):
        """Grade resolution in curriculum path filters by tenant_id."""
        # Create grades for Tenant A and Tenant B with same grading_scale structure
        # Compute scores for Tenant A
        # Assert: only Tenant A's grades are used (even without RLS)

    @pytest.mark.asyncio
    async def test_cumulative_credits_query_includes_tenant_id(self, ...):
        """Cumulative credits query filters by tenant_id."""
        # Create credit records for both tenants
        # Query for Tenant A
        # Assert: only Tenant A's credits summed

    @pytest.mark.asyncio
    async def test_db_get_replaced_with_tenant_scoped_query(self, ...):
        """All db.get(CurriculumProfile, id) calls use tenant-scoped queries instead."""
        # This is a code audit test — grep for db.get(CurriculumProfile
        # and verify all are replaced with tenant-scoped selects
```
