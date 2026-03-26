# Phase 2: Services & Endpoints — Enhancement & Integration

**Sprint:** 21
**Depends on:** Phase 2 Models & Migration (doc 05)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 6.1 | Learning story schemas + service + endpoints | `schemas/preschool.py`, `services/preschool.py`, `endpoints/preschool.py` | 1.5d |
| 6.2 | Extended care schemas + service + endpoints | Same files | 1.5d |
| 6.3 | Caregiver ratio schemas + service + endpoints | Same files | 0.5d |
| 6.4 | Progress timeline endpoint | Same files | 0.75d |
| 6.5 | Daily report sending service + endpoints | Same files | 0.75d |
| 6.6 | Report enhancement (charts, photos, interim) | Same files + PDF template | 1d |
| 6.7 | Sibling discount logic | `services/finance/`, `schemas/finance.py` | 1d |

---

## 6.1 Learning Stories

### Schemas

```python
class LearningStoryCreate(BaseSchema):
    student_id: UUID
    term_id: UUID | None = None
    title: Annotated[str, Field(min_length=3, max_length=255)]
    narrative: Annotated[str, Field(min_length=10, max_length=10000)]
    learning_area_ids: list[UUID] | None = None
    skill_ids: list[UUID] | None = None
    observation_ids: list[UUID] | None = None
    attachments: list[AttachmentSchema] | None = None
    is_shared_with_parents: bool = True

class LearningStoryUpdate(BaseSchema):
    title: Annotated[str | None, Field(min_length=3, max_length=255)] = None
    narrative: Annotated[str | None, Field(min_length=10, max_length=10000)] = None
    learning_area_ids: list[UUID] | None = None
    skill_ids: list[UUID] | None = None
    observation_ids: list[UUID] | None = None
    attachments: list[AttachmentSchema] | None = None
    is_shared_with_parents: bool | None = None

class LearningStoryResponse(BaseSchema):
    id: UUID
    tenant_id: UUID
    student_id: UUID
    term_id: UUID | None = None
    title: str
    narrative: str
    learning_area_ids: list[UUID] | None = None
    skill_ids: list[UUID] | None = None
    observation_ids: list[UUID] | None = None
    attachments: list[AttachmentSchema] | None = None
    is_shared_with_parents: bool
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

### Service Methods

```python
async def create_learning_story(self, tenant_id, data, created_by) -> LearningStory:
    """
    Create a learning story. Validates student belongs to tenant.

    SECURITY: Also validates that all learning_area_ids, skill_ids, and observation_ids
    (if provided) belong to the same tenant and are not soft-deleted. This prevents
    cross-tenant reference injection via the JSONB arrays.
    """

async def list_learning_stories(self, tenant_id, *, student_id=None, term_id=None,
                                 shared_only=False, skip=0, limit=50) -> Sequence[LearningStory]:
    """List stories with filters. shared_only=True for parent portal."""

async def get_learning_story(self, tenant_id, story_id) -> LearningStory:
    """Get single story. Raises STORY_NOT_FOUND."""

async def update_learning_story(self, tenant_id, story_id, data) -> LearningStory:
    """Update story fields."""

async def delete_learning_story(self, tenant_id, story_id) -> None:
    """Soft-delete story."""
```

### Endpoints

| Method | Path | Status | Permission |
|--------|------|--------|------------|
| POST | `/preschool/learning-stories` | 201 | `preschool.create` |
| GET | `/preschool/learning-stories` | 200 | `preschool.read` |
| GET | `/preschool/learning-stories/{id}` | 200 | `preschool.read` |
| PUT | `/preschool/learning-stories/{id}` | 200 | `preschool.update` |
| DELETE | `/preschool/learning-stories/{id}` | 204 | `preschool.delete` |

Query params for list: `student_id`, `term_id`, `shared_only` (bool).

---

## 6.2 Extended Care

### Schemas

```python
class ExtendedCareCheckInRequest(BaseSchema):
    student_id: UUID
    session_type: Annotated[str, Field(pattern=r"^(before_care|after_care)$")]
    notes: Annotated[str | None, Field(max_length=2000)] = None

class ExtendedCareCheckOutRequest(BaseSchema):
    notes: Annotated[str | None, Field(max_length=2000)] = None

class ExtendedCareSessionResponse(BaseSchema):
    id: UUID
    tenant_id: UUID
    student_id: UUID
    session_date: date
    session_type: str
    check_in_time: time
    check_out_time: time | None = None
    duration_minutes: int | None = None
    checked_in_by: UUID | None = None
    checked_out_by: UUID | None = None
    notes: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ExtendedCareBillingSummary(BaseSchema):
    student_id: UUID
    student_name: str
    total_sessions: int
    total_minutes: int
    total_hours: Decimal  # Use Decimal for financial precision
    rate_per_hour: Decimal | None = None
    flat_rate: Decimal | None = None
    estimated_charge: Decimal  # Use Decimal, matches finance module Numeric(12, 2)
```

### Service Methods

```python
async def check_in_extended_care(self, tenant_id, data, checked_in_by) -> ExtendedCareSession:
    """
    Check in a student for extended care.
    Validates student belongs to tenant.
    Sets session_date = today, check_in_time = now.
    """

async def check_out_extended_care(self, tenant_id, session_id, checked_out_by, notes=None) -> ExtendedCareSession:
    """
    Check out a student.
    Calculates duration_minutes = (check_out_time - check_in_time).
    Raises error if already checked out.
    """

async def list_extended_care_sessions(self, tenant_id, *, student_id=None, class_id=None,
                                       date_from=None, date_to=None, checked_out=None,
                                       skip=0, limit=50) -> Sequence[ExtendedCareSession]:
    """List sessions with filters. checked_out=False shows active (not yet checked out)."""

async def get_extended_care_billing_summary(self, tenant_id, *, student_id=None,
                                             class_id=None, date_from, date_to) -> list[dict]:
    """
    Calculate billing summary for extended care sessions.
    Groups by student, sums duration_minutes.
    Reads rate from schools.preschool_settings:
      - extended_care_rate_per_hour (Decimal)
      - extended_care_flat_rate (Decimal, per session)
    If flat_rate: estimated_charge = total_sessions × flat_rate
    If hourly: estimated_charge = total_hours × rate_per_hour
    """
```

### Endpoints

| Method | Path | Status | Permission |
|--------|------|--------|------------|
| POST | `/preschool/extended-care/check-in` | 201 | `preschool.create` |
| POST | `/preschool/extended-care/{session_id}/check-out` | 200 | `preschool.update` |
| GET | `/preschool/extended-care/sessions` | 200 | `preschool.read` |
| GET | `/preschool/extended-care/billing-summary` | 200 | `preschool.read` |

Query params for billing-summary: `student_id`, `class_id`, `date_from` (required), `date_to` (required).

---

## 6.3 Caregiver Ratios

### Schemas

```python
class CaregiverRatioSet(BaseSchema):
    max_children_per_caregiver: Annotated[int, Field(ge=1, le=50)]
    current_caregiver_count: Annotated[int, Field(ge=0, le=100)]

class CaregiverRatioResponse(BaseSchema):
    id: UUID
    tenant_id: UUID
    class_id: UUID
    academic_year_id: UUID
    max_children_per_caregiver: int
    current_caregiver_count: int
    max_capacity: int          # Computed: ratio × count
    current_enrollment: int    # Queried from students table
    is_compliant: bool         # current_enrollment <= max_capacity
    model_config = ConfigDict(from_attributes=True)
```

### Service Methods

```python
async def list_caregiver_ratios(self, tenant_id, academic_year_id=None) -> list[dict]:
    """
    List caregiver ratios for all preschool classes.
    Joins with students to compute current_enrollment.
    Computes is_compliant = enrollment <= (ratio × caregiver_count).
    """

async def set_caregiver_ratio(self, tenant_id, class_id, academic_year_id, data) -> ClassCaregiverRatio:
    """Upsert caregiver ratio for a class/year combination."""
```

### Endpoints

| Method | Path | Status | Permission |
|--------|------|--------|------------|
| GET | `/preschool/caregiver-ratios` | 200 | `preschool.read` |
| PUT | `/preschool/caregiver-ratios/{class_id}` | 200 | `preschool.update` |

Query params for list: `academic_year_id`.
Body for PUT: `CaregiverRatioSet` + `academic_year_id` query param.

---

## 6.4 Progress Timeline

### Schema

```python
class TimelineEntry(BaseSchema):
    date: date
    type: str          # "assessment", "observation", "incident", "learning_story"
    title: str
    summary: str | None = None
    details: dict      # Type-specific payload
    id: UUID
```

### Service Method

```python
async def get_student_timeline(self, tenant_id, student_id, *,
                                date_from=None, date_to=None,
                                limit=100) -> list[dict]:
    """
    Aggregated timeline of a student's preschool journey.

    Queries 4 tables:
    1. student_skill_assessments (by assessed_at date)
    2. progress_observations (by observation_date)
    3. preschool_incidents (by incident_date)
    4. learning_stories (by created_at date)

    Merges results into a unified timeline sorted by date DESC.

    Implementation approach: 4 separate queries (not UNION ALL) because
    the columns are different. Each query returns max `limit` rows,
    then Python merges and sorts. For preschool volumes (1 student,
    1–3 terms), this is fast enough.
    """
```

### Endpoint

| Method | Path | Status | Permission |
|--------|------|--------|------------|
| GET | `/preschool/students/{student_id}/timeline` | 200 | `preschool.read` |

Query params: `date_from`, `date_to`, `limit` (default 100).

---

## 6.5 Daily Report Sending

### Service Methods

```python
async def send_daily_log_to_parents(self, tenant_id, log_id, sent_by) -> dict:
    """
    Send a single daily log summary to the student's guardians.

    1. Load daily log with student → guardians (via selectinload)
    2. Format human-readable summary:
       - Mood: {arrival_mood}
       - Meals: {meal summaries}
       - Nap: {nap_start}–{nap_end} ({nap_quality})
       - Activities: {activity list}
       - Highlights: {highlights}
    3. For SMS: Brief message (<160 chars):
       "Daily report for {child}: Mood: {mood}, Meals: ate well, Nap: good. Details on parent portal."
    4. For Email: Full formatted summary with all sections
    5. Uses NotificationDispatcher.send() for each guardian
    6. Respects parent notification preferences

    Returns: {sent_count: int, failed_count: int}
    """

async def bulk_send_daily_logs(self, tenant_id, class_id, log_date, sent_by) -> dict:
    """
    Send daily logs for all students in a class for a given date.

    1. Query all daily_activity_logs for class_id + log_date
    2. For each log, call send_daily_log_to_parents()
    3. Returns: {total_students: int, sent_count: int, no_log_count: int, failed_count: int}

    Rate limit: Max 50 students per call (synchronous).
    For classes > 50, return error suggesting Celery task (future work).
    """
```

### Endpoints

| Method | Path | Status | Permission | Rate Limit |
|--------|------|--------|------------|------------|
| POST | `/preschool/daily-logs/{log_id}/send-to-parents` | 200 | `preschool.update` | 10/min |
| POST | `/preschool/daily-logs/bulk-send` | 200 | `preschool.update` | 5/min |

Body for bulk-send: `{ class_id: UUID, log_date: date }`.

---

## 6.6 Report Enhancements

### Schema Updates

Update existing `PreschoolReportCreate` and `PreschoolReportUpdate`:

```python
class PreschoolReportCreate(BaseSchema):
    # ... existing fields ...
    report_type: Annotated[str, Field(pattern=r"^(term|interim|progress_update)$")] = "term"
    photo_urls: list[dict] | None = None  # [{url, caption}]

class PreschoolReportUpdate(BaseSchema):
    # ... existing fields ...
    photo_urls: list[dict] | None = None
    chart_data: dict | None = None

class PreschoolReportResponse(BaseSchema):
    # ... existing fields ...
    report_type: str
    photo_urls: list[dict] | None = None
    chart_data: dict | None = None
```

### Service Enhancement

Update existing `generate_reports` method:
- Accept `report_type` parameter (default "term")
- When generating, pre-compute `chart_data` from student assessments:

```python
async def _compute_chart_data(self, tenant_id, student_id, term_id) -> dict:
    """
    Compute radar chart data from student skill assessments.

    Returns: {
        "labels": ["SED", "LL", "MT", "SE", "PD-GM", "PD-FM", "CA", "PHSC"],
        "values": [3.5, 2.8, 4.0, 3.2, 2.5, 3.0, 3.8, 4.2],  # avg numeric_value per area
        "max_value": 4  # maximum possible rating value
    }

    Each value is the average numeric_value of all rated skills in that learning area.
    """
```

### PDF Template Update

**File:** `backend/app/templates/reports/preschool_report.html`

Add after the learning areas section:

1. **SVG Radar Chart** — rendered from `chart_data`:
```html
{% if report.chart_data and report.chart_data.values %}
<div class="chart-section">
    <h3>Developmental Progress Overview</h3>
    <svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
        <!-- Pentagon/octagon background grid -->
        <!-- Data polygon from values -->
        <!-- Labels around the perimeter -->
    </svg>
</div>
{% endif %}
```

2. **Photo Grid** — rendered from `photo_urls`:
```html
{% if report.photo_urls %}
<div class="photo-section">
    <h3>Learning Highlights</h3>
    <div class="photo-grid">
        {% for photo in report.photo_urls %}
        <div class="photo-item">
            <img src="{{ photo.url }}" alt="{{ photo.caption or 'Learning highlight' }}">
            {% if photo.caption %}<p class="caption">{{ photo.caption }}</p>{% endif %}
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}
```

**SVG radar chart implementation notes:**
- 8 axes for 8 learning areas
- Each axis from center to edge, with concentric polygons at 25%, 50%, 75%, 100% of max
- Data polygon filled with semi-transparent school primary color
- Labels at each axis endpoint
- All SVG, no JavaScript — WeasyPrint compatible

---

## 6.7 Sibling Discount

### Approach

Extend the existing scholarship system in `backend/app/services/finance/`:

1. Add `SIBLING_DISCOUNT` to the `ScholarshipType` enum (if not already present)
2. Add a sibling detection query to the finance service
3. Add configuration endpoints for sibling discount rules

### Service Method (Finance Module)

```python
async def detect_sibling_groups(self, tenant_id, school_id=None) -> list[dict]:
    """
    Detect sibling groups within a tenant by finding students who share guardians.

    Returns: [
        {
            "guardian_id": "...",
            "guardian_name": "Mr. Mensah",
            "students": [
                {"id": "...", "name": "Kofi Mensah", "class": "KG1"},
                {"id": "...", "name": "Ama Mensah", "class": "Nursery 2"},
            ]
        },
        ...
    ]

    Query: GROUP BY guardian_id HAVING COUNT(student_id) > 1,
    filtered by tenant_id and optionally school_id.
    """
```

### Endpoints (Finance Module)

| Method | Path | Status | Permission |
|--------|------|--------|------------|
| GET | `/finance/sibling-groups` | 200 | `finance.read` |

Query param: `school_id` (optional).

**Note on sibling discount application:**
The actual discount application happens during invoice generation. When generating invoices, the finance service checks:
1. Does the student have siblings enrolled? (via `detect_sibling_groups`)
2. Is there a sibling discount scholarship configured?
3. If yes, auto-apply the discount

This logic extends the existing scholarship auto-application code path in the finance invoice generation service. The exact implementation depends on the current finance service structure — the developer should read `backend/app/services/finance/invoice_service.py` and follow the existing scholarship auto-application pattern.

---

## Phase 2 Testing

### New Test Files

| File | Tests | Focus |
|------|-------|-------|
| `test_learning_stories.py` | 8 | CRUD, link to observations, parent sharing |
| `test_extended_care.py` | 8 | Check-in, check-out, duration calc, billing summary |
| `test_caregiver_ratios.py` | 5 | Upsert, compliance check, capacity calc |
| `test_student_timeline.py` | 5 | Aggregation across 4 types, date filtering, ordering |
| `test_daily_report_send.py` | 4 | Single send, bulk send, preference respect |
| `test_preschool_phase2_rls.py` | 3 | Tenant isolation for 3 new tables |
| **Total** | **33** | |

### Key Test Scenarios

**Extended Care:**
- Check-in → check-out → verify `duration_minutes` calculated correctly
- Check-out already-checked-out session → error
- Billing summary: 3 sessions × 2 hours each at $5/hr = $30
- Active sessions filter: `checked_out=False` returns only unchecked-out

**Timeline:**
- Create 1 assessment, 1 observation, 1 incident, 1 story for same student
- Get timeline → verify 4 entries, sorted by date DESC
- Date range filter → verify only matching entries returned
- Different types have correct `type` field

**Caregiver Ratios:**
- Set ratio 1:10 with 2 caregivers for class with 18 students → compliant
- Set ratio 1:10 with 2 caregivers for class with 22 students → not compliant
- Upsert: update existing ratio for same class/year
