# Phase 4: Montessori Narrative System & Dual-Track Reporting

**Priority:** Medium
**Effort:** 2 weeks
**Dependencies:** Phase 1 (report generation bridge)
**Unblocks:** MC-017 (Montessori narratives), MC-035 (Montessori reports), MC-036 (dual-track reports)

---

## Part A: Montessori Narrative Assessment System

### Problem Statement

Montessori schools do not use numeric grades. Assessment is narrative-based: teachers write qualitative descriptions of each student's progress across developmental domains, reference work samples, and set goals. The current system only supports numeric score entry via `ExamScore.score`, making it unusable for Montessori classes.

The `MontessoriScoreStrategy` correctly returns NULL `final_score`, and `montessori_report.html` template exists. But:
- No data entry interface for narrative observations
- Template variables `developmental_areas`, `work_samples`, `goals` are always None
- No backend model to store structured Montessori assessment data

### Design Decision: Storage Model

**Option A (Recommended): Use `TermReport.extra_data` JSONB**

Store Montessori-specific data in the existing `extra_data` JSONB column on TermReport:

```json
{
  "developmental_areas": [
    {
      "name": "Language & Literacy",
      "skills": [
        {"name": "Reading comprehension", "progress_level": "practicing"},
        {"name": "Writing fluency", "progress_level": "developing"}
      ],
      "narrative": "Shows strong interest in reading. Beginning to write simple sentences independently."
    },
    {
      "name": "Mathematics",
      "skills": [
        {"name": "Number recognition", "progress_level": "mastery"},
        {"name": "Basic operations", "progress_level": "practicing"}
      ],
      "narrative": "Confidently counts to 100 and performs addition with manipulatives."
    }
  ],
  "work_samples": [
    {"description": "Self-initiated story writing about family"},
    {"description": "Pattern block designs showing spatial awareness"}
  ],
  "goals": [
    "Practice writing multi-sentence paragraphs",
    "Begin multiplication concepts using bead chains"
  ],
  "general_narrative": "A curious and engaged learner who thrives in collaborative settings."
}
```

**Rationale:** Avoids adding a new table and migration. The data is per-student-per-term, which is exactly what TermReport represents. JSONB supports flexible schema evolution.

**Option B: New `montessori_assessments` table**

Only consider this if Montessori data needs to be queried independently (e.g., "find all students at mastery level for Number Recognition"). For now, Option A is simpler and sufficient.

---

## Task F1: Montessori Narrative Entry Endpoint

### Files
- `backend/app/schemas/exam.py` — New schemas
- `backend/app/services/exam/report_service.py` — New method
- `backend/app/api/v1/endpoints/exams/reports.py` — New endpoint

### New Schemas

```python
# schemas/exam.py

class MontessoriSkillEntry(BaseSchema):
    """Single skill within a developmental area."""
    name: str = Field(..., min_length=1, max_length=200)
    progress_level: str = Field(
        ...,
        pattern=r"^(emerging|developing|practicing|mastery)$",
        description="Progress level: emerging, developing, practicing, mastery"
    )

class MontessoriAreaEntry(BaseSchema):
    """A developmental area with skills and narrative."""
    name: str = Field(..., min_length=1, max_length=200)
    skills: list[MontessoriSkillEntry] = Field(default_factory=list, max_length=20)
    narrative: str = Field("", max_length=2000)

    @field_validator("narrative")
    @classmethod
    def strip_html(cls, v: str) -> str:
        # >>REVIEW FIX (H1): regex-based HTML stripping is trivially bypassable.
        # Use nh3 (preferred) or bleach for proper sanitization.
        import nh3
        return nh3.clean(v, tags=set())  # strip ALL HTML tags

class MontessoriWorkSample(BaseSchema):
    description: str = Field(..., min_length=1, max_length=500)

class MontessoriAssessmentCreate(BaseSchema):
    """Full Montessori assessment for a student-term."""
    student_id: UUID
    developmental_areas: list[MontessoriAreaEntry] = Field(..., min_length=1, max_length=15)
    work_samples: list[MontessoriWorkSample] = Field(default_factory=list, max_length=20)
    goals: list[str] = Field(default_factory=list, max_length=10)
    general_narrative: str = Field("", max_length=3000)

    @field_validator("goals", mode="before")
    @classmethod
    def validate_goals(cls, v):
        if v:
            return [g[:500] for g in v]  # truncate individual goals
        return v

    @field_validator("general_narrative")
    @classmethod
    def strip_html_narrative(cls, v: str) -> str:
        import nh3
        return nh3.clean(v, tags=set())

class MontessoriAssessmentResponse(BaseSchema):
    student_id: UUID
    student_name: str
    developmental_areas: list[dict]
    work_samples: list[dict]
    goals: list[str]
    general_narrative: str
    updated_at: datetime | None
```

### New Service Method

```python
# services/exam/report_service.py

async def save_montessori_assessment(
    self,
    tenant_id: UUID,
    academic_year_id: UUID,
    term_id: UUID,
    class_id: UUID,
    section_id: UUID | None,
    data: MontessoriAssessmentCreate,
) -> TermReport:
    """Save Montessori narrative assessment to TermReport.extra_data.

    Creates or updates the TermReport for the student-term, storing
    structured narrative data in the extra_data JSONB column.
    """
    # >>REVIEW FIX (H3): Check subscription tier — Montessori is a non-GES
    # curriculum and requires Professional+ plan.
    from app.services.curriculum._shared import check_multi_curriculum_access
    await check_multi_curriculum_access(self.db, tenant_id)

    # 1. Verify the class uses a Montessori curriculum profile
    # >>REVIEW FIX (C1): Correct call signature — class_id is 2nd positional arg
    profile = await self._resolve_curriculum_profile(
        tenant_id, class_id, student_id=data.student_id
    )
    if not profile or profile.curriculum_type.value != "montessori":
        raise TermReportServiceError(
            "Montessori assessment requires a Montessori curriculum profile",
            "invalid_curriculum"
        )

    # 2. Find or create TermReport
    result = await self.db.execute(
        select(TermReport).where(
            TermReport.tenant_id == tenant_id,
            TermReport.student_id == data.student_id,
            TermReport.academic_year_id == academic_year_id,
            TermReport.term_id == term_id,
            TermReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        report = TermReport(
            tenant_id=tenant_id,
            student_id=data.student_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            class_id=class_id,
            section_id=section_id,
            curriculum_profile_id=profile.id,
        )
        self.db.add(report)

    # 3. Build extra_data JSONB
    # >>REVIEW FIX (H3/L3): Include schema_version for future migration support
    report.extra_data = {
        "montessori_schema_version": 1,
        "developmental_areas": [
            {
                "name": area.name,
                "skills": [
                    {"name": s.name, "progress_level": s.progress_level}
                    for s in area.skills
                ],
                "narrative": area.narrative,
            }
            for area in data.developmental_areas
        ],
        "work_samples": [
            {"description": ws.description}
            for ws in data.work_samples
        ],
        "goals": data.goals,
        "general_narrative": data.general_narrative,
    }
    report.curriculum_profile_id = profile.id

    await self.db.flush()
    await self.db.refresh(report)
    return report
```

### New Endpoint

```python
# api/v1/endpoints/exams/reports.py

@router.post(
    "/montessori-assessment/{academic_year_id}/{term_id}",
    response_model=MontessoriAssessmentResponse,
    status_code=200,
)
async def save_montessori_assessment(
    academic_year_id: UUID,
    term_id: UUID,
    data: MontessoriAssessmentCreate,
    class_id: UUID = Query(...),
    section_id: UUID | None = Query(None),
    user: ValidatedUser = Depends(require_permissions("exams.scores")),
    db: AsyncSession = Depends(get_db),
):
    """Save or update Montessori narrative assessment for a student."""
    service = TermReportService(db)
    report = await service.save_montessori_assessment(
        tenant_id=user.tenant_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        data=data,
    )
    # Build response from report.extra_data
    ...
```

Also add a GET endpoint to retrieve existing assessments:

```python
@router.get(
    "/montessori-assessment/{academic_year_id}/{term_id}/{student_id}",
    response_model=MontessoriAssessmentResponse,
)
async def get_montessori_assessment(
    academic_year_id: UUID,
    term_id: UUID,
    student_id: UUID,
    user: ValidatedUser = Depends(require_permissions("exams.scores")),
    db: AsyncSession = Depends(get_db),
):
    """Get existing Montessori assessment for a student-term."""
    ...
```

---

## Task F2: Wire Montessori Data into Report Template Context

### File
`backend/app/services/pdf.py`

### Required Changes

In `generate_term_report_pdf()`, when the curriculum type is Montessori, read from `report.extra_data`:

```python
# In the template context building section:
if curriculum_type == "montessori" and report.extra_data:
    context.update({
        "developmental_areas": report.extra_data.get("developmental_areas", []),
        "work_samples": report.extra_data.get("work_samples", []),
        "goals": report.extra_data.get("goals", []),
        "general_narrative": report.extra_data.get("general_narrative", ""),
    })
```

### Template Variable Mapping

The `montessori_report.html` template expects:

| Variable | Type | Source |
|----------|------|--------|
| `developmental_areas` | list of dicts | `report.extra_data["developmental_areas"]` |
| `developmental_areas[].name` | str | Area name (e.g., "Language & Literacy") |
| `developmental_areas[].skills` | list | Skills within the area |
| `developmental_areas[].skills[].name` | str | Skill name |
| `developmental_areas[].skills[].progress_level` | str | "emerging"/"developing"/"practicing"/"mastery" |
| `developmental_areas[].narrative` | str | Teacher's narrative for this area |
| `work_samples` | list of dicts | `report.extra_data["work_samples"]` |
| `work_samples[].description` | str | Work sample description |
| `goals` | list of str | `report.extra_data["goals"]` |

---

## Task F3: Frontend — Montessori Narrative Entry Form

### Files
- `frontend/app/(dashboard)/exams/` — New Montessori assessment page
- `frontend/components/curriculum/MontessoriAssessmentForm.tsx` (new)
- `frontend/actions/exams.action.ts` — New server action

### Page Structure

When a teacher navigates to score entry for a Montessori class, instead of the numeric score grid, show the narrative assessment form:

```tsx
// Detection: check curriculum_type from class or exam context
if (curriculumType === "montessori") {
  return <MontessoriAssessmentPage />;
}
return <NumericScoreEntryPage />;
```

### MontessoriAssessmentForm Component

```tsx
interface MontessoriAssessmentFormProps {
  academicYearId: string;
  termId: string;
  classId: string;
  sectionId?: string;
  students: Student[];
}

function MontessoriAssessmentForm({ ... }: MontessoriAssessmentFormProps) {
  const [selectedStudent, setSelectedStudent] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      {/* Student selector */}
      <StudentSelector
        students={students}
        value={selectedStudent}
        onChange={setSelectedStudent}
      />

      {selectedStudent && (
        <MontessoriStudentAssessment
          studentId={selectedStudent}
          academicYearId={academicYearId}
          termId={termId}
          classId={classId}
        />
      )}
    </div>
  );
}
```

### MontessoriStudentAssessment Component

```tsx
function MontessoriStudentAssessment({ studentId, ... }) {
  // >>REVIEW FIX (L4): Use Server Action, not useQuery — project convention is
  // Server Actions (*.action.ts) for all data fetching. Fetch in the Server Component
  // parent and pass as a prop.
  // In the parent Server Component:
  //   const existing = await getMontessoriAssessment(academicYearId, termId, studentId);
  //   <MontessoriStudentAssessment existing={existing} ... />

  const form = useForm<MontessoriAssessmentData>({
    defaultValues: existing || {
      developmental_areas: DEFAULT_MONTESSORI_AREAS,
      work_samples: [],
      goals: [],
      general_narrative: "",
    },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        {/* Developmental Areas — Accordion */}
        <Accordion type="multiple">
          {fields.map((area, index) => (
            <AccordionItem key={area.id} value={`area-${index}`}>
              <AccordionTrigger>{area.name}</AccordionTrigger>
              <AccordionContent>
                {/* Skills with progress level selectors */}
                {area.skills.map((skill, skillIndex) => (
                  <div key={skillIndex} className="flex items-center gap-4">
                    <span className="flex-1">{skill.name}</span>
                    <Select
                      value={skill.progress_level}
                      onValueChange={/* ... */}
                    >
                      <SelectItem value="emerging">Emerging</SelectItem>
                      <SelectItem value="developing">Developing</SelectItem>
                      <SelectItem value="practicing">Practicing</SelectItem>
                      <SelectItem value="mastery">Mastery</SelectItem>
                    </Select>
                  </div>
                ))}

                {/* Narrative textarea */}
                <Textarea
                  placeholder="Write your observation for this area..."
                  className="mt-4"
                  {...form.register(`developmental_areas.${index}.narrative`)}
                />
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>

        {/* Work Samples */}
        <Card className="mt-6">
          <CardHeader><CardTitle>Work Samples</CardTitle></CardHeader>
          <CardContent>
            {/* Dynamic list of work sample descriptions */}
          </CardContent>
        </Card>

        {/* Goals */}
        <Card className="mt-6">
          <CardHeader><CardTitle>Goals for Next Term</CardTitle></CardHeader>
          <CardContent>
            {/* Dynamic list of goal text inputs */}
          </CardContent>
        </Card>

        {/* General Narrative */}
        <Card className="mt-6">
          <CardHeader><CardTitle>General Comments</CardTitle></CardHeader>
          <CardContent>
            <Textarea
              placeholder="Overall observations about the student..."
              {...form.register("general_narrative")}
            />
          </CardContent>
        </Card>

        <Button type="submit" className="mt-6">Save Assessment</Button>
      </form>
    </Form>
  );
}
```

### Default Developmental Areas

Pre-populate with standard Montessori domains:

```typescript
const DEFAULT_MONTESSORI_AREAS = [
  {
    name: "Practical Life",
    skills: [
      { name: "Care of self", progress_level: "emerging" },
      { name: "Care of environment", progress_level: "emerging" },
      { name: "Grace and courtesy", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Sensorial",
    skills: [
      { name: "Visual discrimination", progress_level: "emerging" },
      { name: "Auditory discrimination", progress_level: "emerging" },
      { name: "Tactile awareness", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Language",
    skills: [
      { name: "Phonemic awareness", progress_level: "emerging" },
      { name: "Reading comprehension", progress_level: "emerging" },
      { name: "Writing", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Mathematics",
    skills: [
      { name: "Number concepts", progress_level: "emerging" },
      { name: "Operations", progress_level: "emerging" },
      { name: "Geometry", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Cultural Studies",
    skills: [
      { name: "Geography", progress_level: "emerging" },
      { name: "Science", progress_level: "emerging" },
      { name: "Art & Music", progress_level: "emerging" },
    ],
    narrative: "",
  },
];
```

These defaults are customizable — teachers can add/remove/rename areas and skills.

---

## Part B: Dual-Track Reporting

### Problem Statement

Some Ghanaian private schools offer both GES and an international curriculum simultaneously. A student in such a school takes WASSCE (GES) AND Cambridge IGCSE exams. Their report card should show results from both systems side-by-side.

Currently, the system picks ONE curriculum profile per student and renders one template. There is no way to show both GES and international results on a single report.

### Design Decision

Create a `dual_track_report.html` template that renders two side-by-side result tables: one GES (with CA/Exam split, WAEC grades) and one international (with curriculum-specific grades). The report is triggered when:
1. The school has a "dual-track" configuration, OR
2. The class has `curriculum_profile_id` set to a non-GES profile AND the school default is GES

---

## Task G1: Dual-Track Report Template

### File
`backend/app/templates/reports/dual_track_report.html` (new)

### Template Structure

```html
{% extends "_report_base.html" %}

{% block content %}
<!-- School Header -->
{{ report_header(school, student, term, academic_year, class_name, section_name,
                 "Dual-Track Academic Report", header_text) }}

<!-- Section 1: GES Results -->
<div class="section">
  <h3>Ghana Education Service (GES) Results</h3>
  <table class="results-table">
    <thead>
      <tr>
        <th>Subject</th>
        <th>Class Score ({{ ges_ca_weight }}%)</th>
        <th>Exams Score ({{ ges_exam_weight }}%)</th>
        <th>Total (%)</th>
        <th>Grade</th>
        <th>Remark</th>
        {% if show_position %}<th>Position</th>{% endif %}
      </tr>
    </thead>
    <tbody>
      {% for subject in ges_results %}
      <tr>
        <td>{{ subject.subject_name }}</td>
        <td>{{ subject.class_score | round(1) }}</td>
        <td>{{ subject.exams_score | round(1) }}</td>
        <td>{{ subject.total_score | round(1) }}</td>
        <td>{{ subject.grade }}</td>
        <td>{{ subject.grade_remark }}</td>
        {% if show_position %}<td>{{ subject.subject_position or '-' }}</td>{% endif %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<!-- Section 2: International Results -->
<div class="section" style="margin-top: 24px;">
  <h3>{{ international_curriculum_name }} Results</h3>
  <table class="results-table">
    <thead>
      <tr>
        <th>Subject</th>
        {% for comp in international_components %}
        <th>{{ comp.name }} ({{ comp.weight }}%)</th>
        {% endfor %}
        <th>Final (%)</th>
        <th>Grade</th>
        {% if show_effort_grade %}<th>Effort</th>{% endif %}
      </tr>
    </thead>
    <tbody>
      {% for subject in international_results %}
      <tr>
        <td>{{ subject.subject_name }}</td>
        {% for comp in international_components %}
        <td>{{ subject.component_scores.get(comp.component_type, '-') }}</td>
        {% endfor %}
        <td>{{ subject.final_score | round(1) }}</td>
        <td>{{ subject.grade }}</td>
        {% if show_effort_grade %}<td>{{ subject.effort_grade or '-' }}</td>{% endif %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<!-- Combined Summary -->
<div class="summary-section">
  <table class="summary-table">
    <tr>
      <td><strong>GES Average:</strong> {{ ges_average }}%</td>
      <td><strong>GES Position:</strong> {{ ges_position }}</td>
    </tr>
    <tr>
      <td><strong>{{ international_curriculum_name }} Average:</strong> {{ international_average }}%</td>
      {% if gpa %}<td><strong>GPA:</strong> {{ gpa }}</td>{% endif %}
      {% if ib_total_points %}<td><strong>IB Total:</strong> {{ ib_total_points }}/45</td>{% endif %}
    </tr>
  </table>
</div>

<!-- Standard sections -->
{{ attendance_section(report) }}
{{ remarks_section(report) }}
{{ report_footer(school, current_date, next_term_begins, footer_text, signature_labels) }}
{% endblock %}
```

---

## Task G2: Dual-Track Report Generation Logic

### File
`backend/app/services/exam/report_service.py`

### New Method

```python
async def _get_dual_track_results(
    self,
    tenant_id: UUID,
    student_id: UUID,
    exam_id: UUID,
    class_id: UUID,
    section_id: UUID | None,
    ges_profile: CurriculumProfile | None,
    international_profile: CurriculumProfile,
) -> dict:
    """Compute results under BOTH GES and international scoring for dual-track.

    Returns a dict with both result sets for the dual-track template.
    """
    # 1. Get GES results using legacy path (or GES strategy)
    ges_results = await self._get_student_subject_results_legacy(
        tenant_id, student_id, exam_id, class_id, section_id
    )

    # 2. Get international results using curriculum strategy
    international_results = await self._get_student_subject_results_curriculum(
        tenant_id, student_id, exam_id, class_id, section_id,
        international_profile
    )

    # 3. Load international assessment components for column headers
    structure = await self._get_assessment_structure(
        tenant_id, international_profile.id
    )
    components = structure.components if structure else []

    return {
        "ges_results": ges_results,
        "international_results": international_results,
        "international_components": [
            {"name": c.name, "weight": c.weight, "component_type": c.component_type.value}
            for c in sorted(components, key=lambda c: c.sequence)
        ],
        "international_curriculum_name": international_profile.name,
    }
```

### Detection Logic

In `generate_term_report_pdf()`, detect dual-track scenarios:

> **>>REVIEW FIX (H4):** Use ONLY `report_config.template_key == "dual_track"` as the
> canonical flag. The original plan also checked `school.curriculum_settings.get("dual_track")`
> which creates two sources of truth and will cause confusion. One flag, one place.

```python
# After resolving curriculum profile:
is_dual_track = False

if profile and profile.curriculum_type.value != "ges":
    # Single canonical flag: ReportCardConfig.template_key
    if report_config and report_config.template_key == "dual_track":
        is_dual_track = True

if is_dual_track:
    template = "dual_track_report.html"
    dual_data = await self._get_dual_track_results(...)
    context.update(dual_data)
```

---

## Task G3: Add Dual-Track to Template Mapping

### File
`backend/app/services/pdf.py`

### Required Changes

```python
# REPORT_TEMPLATES mapping — add:
REPORT_TEMPLATES = {
    "ges": "term_report.html",
    "cambridge": "cambridge_report.html",
    "edexcel": "cambridge_report.html",
    "american": "american_report.html",
    "ib": "ib_report.html",
    "french": "french_report.html",
    "montessori": "montessori_report.html",
    "dual_track": "dual_track_report.html",  # NEW
}
```

### Frontend Configuration

In the Report Card Config settings for a curriculum profile, add a template_key dropdown that includes "dual_track" as an option:

```tsx
// In ReportCardConfig settings component:
<Select value={config.template_key} onValueChange={handleTemplateChange}>
  <SelectItem value="default">Default (auto-detect)</SelectItem>
  <SelectItem value="dual_track">Dual Track (GES + International)</SelectItem>
</Select>
```

---

## Checklist

### Task F1 (Montessori Narrative Entry)
- [ ] Create `MontessoriAssessmentCreate` schema with validation
- [ ] Create `MontessoriAreaEntry`, `MontessoriSkillEntry`, `MontessoriWorkSample` schemas
- [ ] HTML tag stripping on narrative fields
- [ ] Implement `save_montessori_assessment()` in report_service.py
- [ ] Validate curriculum profile is Montessori
- [ ] Store structured data in `TermReport.extra_data` JSONB
- [ ] Create POST endpoint for saving assessment
- [ ] Create GET endpoint for retrieving existing assessment
- [ ] Test: save and retrieve Montessori assessment
- [ ] Test: reject for non-Montessori curriculum

### Task F2 (Montessori Report Template Wiring)
- [ ] Read `report.extra_data` fields in pdf.py for Montessori templates
- [ ] Pass `developmental_areas`, `work_samples`, `goals` to template context
- [ ] Test: generate PDF for Montessori class with data
- [ ] Test: generate PDF for Montessori class without data (graceful fallback)

### Task F3 (Montessori Frontend)
- [ ] Create `MontessoriAssessmentForm` component
- [ ] Create `MontessoriStudentAssessment` component with accordion layout
- [ ] Default developmental areas (Practical Life, Sensorial, Language, Math, Cultural)
- [ ] Progress level selectors (emerging/developing/practicing/mastery)
- [ ] Work samples dynamic list
- [ ] Goals dynamic list
- [ ] General narrative textarea
- [ ] Auto-save or explicit save button
- [ ] Server actions for save/get Montessori assessment
- [ ] Detect Montessori curriculum and show narrative form instead of score grid
- [ ] Mobile responsive layout

### Task G1 (Dual-Track Template)
- [ ] Create `dual_track_report.html` with two result tables
- [ ] GES section with CA/Exam/Total/Grade/Remark/Position
- [ ] International section with component columns
- [ ] Combined summary section
- [ ] Standard attendance and remarks sections
- [ ] Print-friendly A4 layout

### Task G2 (Dual-Track Generation Logic)
- [ ] Implement `_get_dual_track_results()` method
- [ ] Compute GES results via legacy path
- [ ] Compute international results via curriculum strategy
- [ ] Load international assessment components for headers
- [ ] Detect dual-track scenario in report generation
- [ ] Test: dual-track report with GES + Cambridge data

### Task G3 (Template Mapping)
- [ ] Add "dual_track" to `REPORT_TEMPLATES` mapping
- [ ] Add template_key dropdown in ReportCardConfig frontend settings
- [ ] Test: selecting dual_track template generates correct report
