# Phase 2: Admission Letters, Offer Acceptance & Waitlist Management

**Covers:** GAP 5 (EM-052 to EM-058), GAP 3 partial (EM-029)
**Estimated Effort:** 2 weeks (1 sprint)
**New Tables:** 0 (column additions only)
**Modified Tables:** 3
**New Endpoints:** 8
**New Tests:** ~40
**New Celery Tasks:** 2
**New PDF Templates:** 2

---

### Prerequisites

**Celery Bootstrap Required:** This phase introduces the first Celery Beat periodic tasks in the admissions module. Before implementation, verify:
1. `celery_app` instance exists and is configured (check `backend/app/tasks/__init__.py`)
2. Celery worker process is defined in `docker-compose.yml`
3. Celery Beat scheduler is configured
4. Redis broker connection is verified

If Celery infrastructure does not exist, bootstrap it first (estimated 2-3 dev-days). Reference the existing `backend/app/tasks/tenant_cleanup.py` for the task registration pattern.

---

## 1. Database Schema

### 1.1 New Enums

Add to `backend/app/models/admissions/enums.py`:

```python
class OfferResponse(str, Enum):
    """Applicant's response to an admission offer."""
    ACCEPTED = "accepted"
    DECLINED = "declined"
```

### 1.2 Column Additions to Existing Tables

#### `admission_decisions` table — waitlist + rejection letter

```sql
ALTER TABLE admission_decisions ADD COLUMN rejection_reason TEXT;
ALTER TABLE admission_decisions ADD COLUMN rejection_letter_url VARCHAR(500);
ALTER TABLE admission_decisions ADD COLUMN waitlist_rank INTEGER;
ALTER TABLE admission_decisions ADD COLUMN waitlist_notes TEXT;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `rejection_reason` | TEXT | Yes | | Structured reason for rejection letter |
| `rejection_letter_url` | VARCHAR(500) | Yes | | S3 URL for generated rejection letter PDF |
| `waitlist_rank` | INTEGER | Yes | | Priority ranking on waitlist (1 = highest) |
| `waitlist_notes` | TEXT | Yes | | Internal notes for waitlist ordering |

**Model change:** Add to `AdmissionDecision` class in `backend/app/models/admissions/decision.py`:

```python
rejection_reason: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment="Structured reason for rejection letter",
)
rejection_letter_url: Mapped[str | None] = mapped_column(
    String(500),
    nullable=True,
    comment="Generated rejection letter PDF S3 URL",
)
waitlist_rank: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    comment="Priority ranking on waitlist (1 = highest priority)",
)
waitlist_notes: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment="Internal notes for waitlist ordering decisions",
)
```

**New index:**
```sql
CREATE INDEX ix_decisions_waitlist
    ON admission_decisions(tenant_id, waitlist_rank)
    WHERE decision_type = 'waitlisted' AND waitlist_rank IS NOT NULL AND deleted_at IS NULL;
```

#### `applications` table — offer response tracking

```sql
ALTER TABLE applications ADD COLUMN offer_responded_at TIMESTAMPTZ;
ALTER TABLE applications ADD COLUMN offer_response VARCHAR(20);
ALTER TABLE applications ADD COLUMN offer_response_notes TEXT;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `offer_responded_at` | TIMESTAMPTZ | Yes | | When applicant accepted/rejected offer |
| `offer_response` | VARCHAR(20) | Yes | | `accepted` or `declined` (OfferResponse enum) |
| `offer_response_notes` | TEXT | Yes | | Applicant's notes on their response |

**Model change:** Add to `Application` class in `backend/app/models/admissions/application.py`:

```python
from sqlalchemy import DateTime

offer_responded_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    comment="When applicant accepted/declined the offer",
)
offer_response: Mapped[str | None] = mapped_column(
    String(20),
    nullable=True,
    comment="OfferResponse enum value: accepted, declined",
)
offer_response_notes: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment="Applicant's notes on their offer response",
)
```

#### `admission_periods` table — reminder configuration

```sql
ALTER TABLE admission_periods ADD COLUMN reminder_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE admission_periods ADD COLUMN reminder_days_before_close INTEGER;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `reminder_enabled` | BOOLEAN | No | `false` | Enable auto-reminders for incomplete applications |
| `reminder_days_before_close` | INTEGER | Yes | | Days before close date to send reminder |

**Model change:** Add to `AdmissionPeriod` class in `backend/app/models/admissions/period.py`:

```python
reminder_enabled: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default="false",
    comment="Enable auto-reminders for incomplete applications before close date",
)
reminder_days_before_close: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    comment="Days before end_date to send reminder to applicants with DRAFT status",
)
```

---

## 2. PDF Templates

### 2.1 Admission Letter: `backend/app/templates/admissions/admission_letter.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Admission Letter</title>
    <style>
        @page {
            size: A4;
            margin: 2cm 2.5cm;
        }
        body {
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #333;
        }
        .letterhead {
            text-align: center;
            margin-bottom: 2cm;
            border-bottom: 3px solid {{ school_color }};
            padding-bottom: 1cm;
        }
        .letterhead .logo {
            max-height: 80px;
            max-width: 200px;
            margin-bottom: 0.5cm;
        }
        .letterhead .school-name {
            font-size: 20pt;
            font-weight: bold;
            color: {{ school_color }};
            margin: 0;
        }
        .letterhead .school-motto {
            font-style: italic;
            color: #666;
            margin: 0.2cm 0 0 0;
        }
        .letterhead .school-address {
            font-size: 10pt;
            color: #666;
            margin: 0.3cm 0 0 0;
        }
        .date-line {
            text-align: right;
            margin-bottom: 1cm;
        }
        .reference-line {
            margin-bottom: 1cm;
            font-weight: bold;
        }
        .salutation {
            margin-bottom: 0.5cm;
        }
        .body-text {
            margin-bottom: 0.5cm;
            text-align: justify;
        }
        .highlight-box {
            background: #f0f7ff;
            border-left: 4px solid {{ school_color }};
            padding: 0.8cm;
            margin: 1cm 0;
        }
        .highlight-box p {
            margin: 0.2cm 0;
        }
        .highlight-box .label {
            font-weight: bold;
            color: {{ school_color }};
        }
        .conditions-box {
            border: 1px solid #ddd;
            padding: 0.6cm;
            margin: 0.8cm 0;
            background: #fffef0;
        }
        .conditions-box h3 {
            margin-top: 0;
            font-size: 12pt;
            color: {{ school_color }};
        }
        .next-steps {
            margin: 1cm 0;
        }
        .next-steps ol {
            padding-left: 1.5cm;
        }
        .next-steps li {
            margin-bottom: 0.3cm;
        }
        .deadline-warning {
            font-weight: bold;
            color: #c0392b;
            margin: 0.8cm 0;
        }
        .signature-block {
            margin-top: 2cm;
        }
        .signature-block .role {
            font-weight: bold;
        }
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 8pt;
            color: #999;
            border-top: 1px solid #ddd;
            padding-top: 0.3cm;
        }
    </style>
</head>
<body>
    <div class="letterhead">
        {% if safe_logo_url %}
        <img src="{{ safe_logo_url }}" alt="{{ school.name }}" class="logo">
        {% endif %}
        <p class="school-name">{{ school.name }}</p>
        {% if school.motto %}
        <p class="school-motto">&ldquo;{{ school.motto }}&rdquo;</p>
        {% endif %}
        {% if school.address %}
        <p class="school-address">{{ school.address }}</p>
        {% endif %}
    </div>

    <div class="date-line">
        {{ decision.decision_date.strftime('%d %B %Y') }}
    </div>

    <div class="reference-line">
        Ref: ADM/{{ tracking_code[:12] | upper }}
    </div>

    <div class="salutation">
        Dear Parent/Guardian,
    </div>

    <div class="body-text">
        We are pleased to inform you that <strong>{{ applicant_name }}</strong>
        has been offered admission to {{ school.name }} for the
        {{ academic_year_name }} academic year.
    </div>

    <div class="highlight-box">
        <p><span class="label">Student Name:</span> {{ applicant_name }}</p>
        <p><span class="label">Tracking Code:</span> {{ tracking_code }}</p>
        <p><span class="label">Offered Class:</span> {{ offered_class_name }}</p>
        {% if response_deadline %}
        <p><span class="label">Response Deadline:</span> {{ response_deadline.strftime('%d %B %Y') }}</p>
        {% endif %}
    </div>

    {% if conditions %}
    <div class="conditions-box">
        <h3>Conditions of Admission</h3>
        <p>{{ conditions }}</p>
    </div>
    {% endif %}

    {% if response_deadline %}
    <div class="deadline-warning">
        Please note: You must respond to this offer by {{ response_deadline.strftime('%d %B %Y') }}.
        Failure to respond by the deadline may result in the offer being withdrawn.
    </div>
    {% endif %}

    <div class="next-steps">
        <p><strong>Next Steps:</strong></p>
        <ol>
            <li>Accept or decline this offer using the applicant portal or by contacting the school directly.</li>
            <li>Upon acceptance, complete the enrollment process including payment of required fees.</li>
            <li>Submit any outstanding documents as requested by the admissions office.</li>
            {% if conditions %}
            <li>Ensure all conditions of admission are met before the commencement of the academic year.</li>
            {% endif %}
        </ol>
    </div>

    <div class="body-text">
        We look forward to welcoming {{ applicant_name }} to the {{ school.name }} family.
    </div>

    <div class="signature-block">
        <p>Yours sincerely,</p>
        <br><br>
        <p class="role">Head of Admissions</p>
        <p>{{ school.name }}</p>
    </div>

    <div class="footer">
        This is an official admission letter from {{ school.name }}.
        Tracking Code: {{ tracking_code }}
    </div>
</body>
</html>
```

### 2.2 Rejection Letter: `backend/app/templates/admissions/rejection_letter.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Admissions Decision</title>
    <style>
        @page {
            size: A4;
            margin: 2cm 2.5cm;
        }
        body {
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #333;
        }
        .letterhead {
            text-align: center;
            margin-bottom: 2cm;
            border-bottom: 3px solid {{ school_color }};
            padding-bottom: 1cm;
        }
        .letterhead .logo {
            max-height: 80px;
            max-width: 200px;
            margin-bottom: 0.5cm;
        }
        .letterhead .school-name {
            font-size: 20pt;
            font-weight: bold;
            color: {{ school_color }};
            margin: 0;
        }
        .letterhead .school-motto {
            font-style: italic;
            color: #666;
            margin: 0.2cm 0 0 0;
        }
        .letterhead .school-address {
            font-size: 10pt;
            color: #666;
            margin: 0.3cm 0 0 0;
        }
        .date-line {
            text-align: right;
            margin-bottom: 1cm;
        }
        .reference-line {
            margin-bottom: 1cm;
            font-weight: bold;
        }
        .salutation {
            margin-bottom: 0.5cm;
        }
        .body-text {
            margin-bottom: 0.5cm;
            text-align: justify;
        }
        .reason-box {
            border: 1px solid #ddd;
            padding: 0.6cm;
            margin: 0.8cm 0;
            background: #fafafa;
        }
        .reason-box h3 {
            margin-top: 0;
            font-size: 12pt;
            color: #555;
        }
        .signature-block {
            margin-top: 2cm;
        }
        .signature-block .role {
            font-weight: bold;
        }
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 8pt;
            color: #999;
            border-top: 1px solid #ddd;
            padding-top: 0.3cm;
        }
    </style>
</head>
<body>
    <div class="letterhead">
        {% if safe_logo_url %}
        <img src="{{ safe_logo_url }}" alt="{{ school.name }}" class="logo">
        {% endif %}
        <p class="school-name">{{ school.name }}</p>
        {% if school.motto %}
        <p class="school-motto">&ldquo;{{ school.motto }}&rdquo;</p>
        {% endif %}
        {% if school.address %}
        <p class="school-address">{{ school.address }}</p>
        {% endif %}
    </div>

    <div class="date-line">
        {{ decision.decision_date.strftime('%d %B %Y') }}
    </div>

    <div class="reference-line">
        Ref: ADM/{{ tracking_code[:12] | upper }}
    </div>

    <div class="salutation">
        Dear Parent/Guardian,
    </div>

    <div class="body-text">
        Thank you for your interest in {{ school.name }} and for submitting an application
        for <strong>{{ applicant_name }}</strong> for the {{ academic_year_name }} academic year.
    </div>

    <div class="body-text">
        After careful review of all applications received, we regret to inform you that
        we are unable to offer {{ applicant_name }} a place at this time. This was a
        highly competitive admissions cycle and many qualified applicants could not be
        accommodated.
    </div>

    {% if rejection_reason %}
    <div class="reason-box">
        <h3>Additional Information</h3>
        <p>{{ rejection_reason }}</p>
    </div>
    {% endif %}

    <div class="body-text">
        We encourage you to consider applying again in the future. We wish
        {{ applicant_name }} every success in their academic journey.
    </div>

    <div class="body-text">
        Should you have any questions regarding this decision, please do not hesitate
        to contact our admissions office.
    </div>

    <div class="signature-block">
        <p>Yours sincerely,</p>
        <br><br>
        <p class="role">Head of Admissions</p>
        <p>{{ school.name }}</p>
    </div>

    <div class="footer">
        This is an official communication from {{ school.name }}.
        Tracking Code: {{ tracking_code }}
    </div>
</body>
</html>
```

---

## 3. Schemas

### 3.1 New Schemas in `backend/app/schemas/admissions.py`

Add the following schemas:

```python
# =========================
# Offer Response Schemas
# =========================


class OfferResponseEnum(str, Enum):
    """Applicant's response to an admission offer."""
    ACCEPTED = "accepted"
    DECLINED = "declined"


class OfferResponseRequest(BaseSchema):
    """Accept or decline an admission offer."""
    response: OfferResponseEnum
    notes: Optional[str] = Field(None, max_length=2000)


class OfferDetailResponse(BaseSchema):
    """Full offer details for applicant portal."""
    application_id: UUID
    applicant_name: str
    tracking_code: str
    school_name: str
    offered_class_name: Optional[str] = None
    decision_type: str
    decision_date: date
    conditions: Optional[str] = None
    response_deadline: Optional[date] = None
    decision_letter_url: Optional[str] = None
    offer_responded_at: Optional[datetime] = None
    offer_response: Optional[str] = None
    offer_response_notes: Optional[str] = None
    is_expired: bool = False


# =========================
# Waitlist Schemas
# =========================


class WaitlistRankUpdate(BaseSchema):
    """Update waitlist rank for a single decision."""
    rank: int = Field(..., ge=1, le=9999)


class WaitlistReorderRequest(BaseSchema):
    """Bulk reorder waitlist by specifying ordered decision IDs."""
    period_id: UUID
    ordered_decision_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Decision IDs in desired rank order (index 0 = rank 1)",
    )


class WaitlistPromoteRequest(BaseSchema):
    """Promote a waitlisted applicant to offered status."""
    offered_class_id: UUID
    response_deadline: Optional[date] = None
    conditions: Optional[str] = None


class WaitlistEntryResponse(BaseSchema):
    """Waitlist entry with application details."""
    decision_id: UUID
    application_id: UUID
    applicant_name: str
    tracking_code: str
    target_class_name: Optional[str] = None
    waitlist_rank: Optional[int] = None
    waitlist_notes: Optional[str] = None
    decision_date: date
    created_at: datetime


class WaitlistListResponse(BaseSchema):
    """Paginated waitlist."""
    items: list[WaitlistEntryResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Letter Generation Schemas
# =========================


class GenerateLetterResponse(BaseSchema):
    """Response after generating a letter PDF."""
    decision_id: UUID
    letter_url: str
    letter_type: str  # "admission" or "rejection"


# =========================
# Reminder Config Schemas
# =========================


class ReminderConfigUpdate(BaseSchema):
    """Update reminder settings on an admission period."""
    reminder_enabled: bool
    reminder_days_before_close: Optional[int] = Field(None, ge=1, le=90)

    @field_validator("reminder_days_before_close")
    @classmethod
    def days_required_when_enabled(cls, v: int | None, info) -> int | None:
        enabled = info.data.get("reminder_enabled")
        if enabled and v is None:
            raise ValueError("reminder_days_before_close is required when reminder_enabled is True")
        return v
```

### 3.2 Update `AdmissionDecisionResponse` in `backend/app/schemas/admissions.py`

Add the new fields to the existing response schema:

```python
class AdmissionDecisionResponse(BaseSchema):
    """Admission decision detail."""

    id: UUID
    application_id: UUID
    decision_type: str
    decided_by: UUID
    decided_by_name: Optional[str] = None
    offered_class_id: Optional[UUID] = None
    offered_class_name: Optional[str] = None
    conditions: Optional[str] = None
    decision_date: date
    response_deadline: Optional[date] = None
    decision_letter_url: Optional[str] = None
    # Phase 2 additions
    rejection_reason: Optional[str] = None
    rejection_letter_url: Optional[str] = None
    waitlist_rank: Optional[int] = None
    waitlist_notes: Optional[str] = None
    created_at: datetime
```

### 3.3 Update `AdmissionPeriodResponse` in `backend/app/schemas/admissions.py`

Add the reminder fields:

```python
# Add to AdmissionPeriodResponse:
reminder_enabled: bool = False
reminder_days_before_close: Optional[int] = None
```

---

## 4. Services

### 4.1 Modified: `backend/app/services/admissions/decision_service.py`

Add the following methods to the existing `DecisionService` class:

```python
import uuid
from datetime import date, datetime, UTC
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from weasyprint import HTML

from app.models.academic import AcademicYear, Class
from app.models.admissions import (
    AdmissionApplicationStatus,
    AdmissionDecision,
    Application,
    ApplicationStatusHistory,
    DecisionType,
    VALID_TRANSITIONS,
)
from app.models.admissions.period import AdmissionPeriod
from app.models.school import School
from app.services.s3 import get_s3_service

logger = structlog.get_logger(__name__)

# Templates directory for admission letters
_ADMISSIONS_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "admissions"


class DecisionService:
    # ... existing __init__, decide(), bulk_decide(), _get_application() ...

    # ---- Letter Generation ----

    async def generate_admission_letter(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
    ) -> str:
        """
        Generate admission letter PDF, upload to S3, and return presigned URL.

        Only valid for decisions with decision_type = 'accepted'.
        Uses WeasyPrint + Jinja2 template from templates/admissions/admission_letter.html.

        S3 key format: admissions/{tenant_id}/letters/{decision_id}_admission.pdf
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.ACCEPTED.value:
            raise DecisionServiceError(
                "Admission letter can only be generated for acceptance decisions",
                code="INVALID_DECISION_TYPE",
            )

        # Load application with related data for the template
        app_result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.admission_period).selectinload(
                    AdmissionPeriod.academic_year
                ),
            )
            .filter(
                Application.id == decision.application_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise DecisionServiceError("Application not found", code="NOT_FOUND")

        # Load school
        school = await self._get_school(tenant_id, application.school_id)

        # Load offered class name
        offered_class_name = ""
        if decision.offered_class_id:
            cls_result = await self.db.execute(
                select(Class.name).filter(
                    Class.id == decision.offered_class_id,
                    Class.tenant_id == tenant_id,
                )
            )
            offered_class_name = cls_result.scalar_one_or_none() or ""

        # Build template context
        applicant_name = f"{application.applicant_first_name} {application.applicant_last_name}"
        academic_year_name = (
            application.admission_period.academic_year.name
            if application.admission_period and application.admission_period.academic_year
            else ""
        )

        # Validate color and logo URL to prevent CSS/HTML injection in PDF template
        import re
        HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

        safe_color = (
            school.primary_color
            if school.primary_color and HEX_COLOR_RE.match(school.primary_color)
            else '#1B4F72'
        )
        safe_logo_url = None
        if school.logo_url and school.logo_url.startswith("https://"):
            safe_logo_url = school.logo_url

        context = {
            "school": school,
            "school_color": safe_color,
            "safe_logo_url": safe_logo_url,
            "decision": decision,
            "applicant_name": applicant_name,
            "tracking_code": application.tracking_code,
            "offered_class_name": offered_class_name,
            "academic_year_name": academic_year_name,
            "conditions": decision.conditions,
            "response_deadline": decision.response_deadline,
        }

        # Render PDF
        pdf_bytes = self._render_pdf("admission_letter.html", context)

        # Upload to S3
        s3_key = f"admissions/{tenant_id}/letters/{decision_id}_admission.pdf"
        s3 = get_s3_service()
        s3.upload_file(pdf_bytes, s3_key, "application/pdf")

        # Update decision record with S3 URL
        decision.decision_letter_url = s3_key
        await self.db.flush()
        await self.db.refresh(decision)

        # Return presigned URL (1 hour TTL)
        presigned_url = s3.generate_presigned_url(s3_key, expires_in=3600)

        logger.info(
            "admission_letter_generated",
            decision_id=str(decision_id),
            application_id=str(application.id),
        )
        return presigned_url

    async def generate_rejection_letter(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        *,
        rejection_reason: str | None = None,
    ) -> str:
        """
        Generate rejection letter PDF, upload to S3, and return presigned URL.

        Only valid for decisions with decision_type = 'rejected'.
        If rejection_reason is provided, it is persisted on the decision record
        and included in the letter.

        S3 key format: admissions/{tenant_id}/letters/{decision_id}_rejection.pdf
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.REJECTED.value:
            raise DecisionServiceError(
                "Rejection letter can only be generated for rejection decisions",
                code="INVALID_DECISION_TYPE",
            )

        # Persist rejection reason if provided
        if rejection_reason is not None:
            decision.rejection_reason = rejection_reason

        # Load application with related data
        app_result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.admission_period).selectinload(
                    AdmissionPeriod.academic_year
                ),
            )
            .filter(
                Application.id == decision.application_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise DecisionServiceError("Application not found", code="NOT_FOUND")

        school = await self._get_school(tenant_id, application.school_id)

        applicant_name = f"{application.applicant_first_name} {application.applicant_last_name}"
        academic_year_name = (
            application.admission_period.academic_year.name
            if application.admission_period and application.admission_period.academic_year
            else ""
        )

        # Validate color and logo URL to prevent CSS/HTML injection in PDF template
        import re
        HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

        safe_color = (
            school.primary_color
            if school.primary_color and HEX_COLOR_RE.match(school.primary_color)
            else '#1B4F72'
        )
        safe_logo_url = None
        if school.logo_url and school.logo_url.startswith("https://"):
            safe_logo_url = school.logo_url

        context = {
            "school": school,
            "school_color": safe_color,
            "safe_logo_url": safe_logo_url,
            "decision": decision,
            "applicant_name": applicant_name,
            "tracking_code": application.tracking_code,
            "academic_year_name": academic_year_name,
            "rejection_reason": decision.rejection_reason,
        }

        pdf_bytes = self._render_pdf("rejection_letter.html", context)

        s3_key = f"admissions/{tenant_id}/letters/{decision_id}_rejection.pdf"
        s3 = get_s3_service()
        s3.upload_file(pdf_bytes, s3_key, "application/pdf")

        decision.rejection_letter_url = s3_key
        await self.db.flush()
        await self.db.refresh(decision)

        presigned_url = s3.generate_presigned_url(s3_key, expires_in=3600)

        logger.info(
            "rejection_letter_generated",
            decision_id=str(decision_id),
            application_id=str(application.id),
        )
        return presigned_url

    # ---- Waitlist Management ----

    async def update_waitlist_rank(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        *,
        rank: int,
    ) -> AdmissionDecision:
        """
        Set or update waitlist rank for a single waitlisted decision.

        Uses pg_advisory_xact_lock to prevent concurrent rank updates
        from creating duplicate ranks within the same tenant.
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.WAITLISTED.value:
            raise DecisionServiceError(
                "Waitlist rank can only be set for waitlisted decisions",
                code="INVALID_DECISION_TYPE",
            )

        # Advisory lock scoped to tenant to prevent concurrent rank collisions
        lock_key = hash(f"{tenant_id}_waitlist_rank") & 0x7FFFFFFFFFFFFFFF
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": lock_key},
        )

        decision.waitlist_rank = rank
        await self.db.flush()
        await self.db.refresh(decision)

        logger.info(
            "waitlist_rank_updated",
            decision_id=str(decision_id),
            rank=rank,
        )
        return decision

    async def reorder_waitlist(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        period_id: uuid.UUID,
        ordered_decision_ids: list[uuid.UUID],
    ) -> list[AdmissionDecision]:
        """
        Bulk reorder waitlist by assigning sequential ranks.

        ordered_decision_ids[0] gets rank 1, ordered_decision_ids[1] gets rank 2, etc.
        All decisions must be waitlisted and belong to the specified period.

        Uses pg_advisory_xact_lock to prevent concurrent reorder operations.
        """
        # Advisory lock scoped to tenant + period
        lock_key = hash(f"{tenant_id}_waitlist_reorder_{period_id}") & 0x7FFFFFFFFFFFFFFF
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": lock_key},
        )

        # Fetch all decisions in the list in one query
        result = await self.db.execute(
            select(AdmissionDecision)
            .join(Application, AdmissionDecision.application_id == Application.id)
            .filter(
                AdmissionDecision.tenant_id == tenant_id,
                AdmissionDecision.id.in_(ordered_decision_ids),
                AdmissionDecision.decision_type == DecisionType.WAITLISTED.value,
                Application.admission_period_id == period_id,
                Application.school_id == school_id,
                # Defense-in-depth: filter by tenant_id on both tables
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        decisions_by_id = {d.id: d for d in result.scalars().all()}

        # Validate all IDs were found
        missing = set(ordered_decision_ids) - set(decisions_by_id.keys())
        if missing:
            raise DecisionServiceError(
                f"Decisions not found or not waitlisted: {[str(m) for m in missing]}",
                code="NOT_FOUND",
            )

        # Assign sequential ranks
        updated = []
        for rank, decision_id in enumerate(ordered_decision_ids, start=1):
            decision = decisions_by_id[decision_id]
            decision.waitlist_rank = rank
            updated.append(decision)

        await self.db.flush()
        for d in updated:
            await self.db.refresh(d)

        logger.info(
            "waitlist_reordered",
            period_id=str(period_id),
            count=len(updated),
        )
        return updated

    async def promote_from_waitlist(
        self,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        *,
        offered_class_id: uuid.UUID,
        response_deadline: date | None = None,
        conditions: str | None = None,
        promoted_by: uuid.UUID,
    ) -> AdmissionDecision:
        """
        Promote a waitlisted applicant to 'offered' status.

        Steps:
        1. Validate decision is waitlisted
        2. Transition application status: WAITLISTED -> OFFERED
        3. Update decision: type = accepted, offered_class_id, clear waitlist fields
        4. Record status history
        5. Send notification to guardian
        """
        decision = await self._get_decision(tenant_id, decision_id)

        if decision.decision_type != DecisionType.WAITLISTED.value:
            raise DecisionServiceError(
                "Only waitlisted decisions can be promoted",
                code="INVALID_DECISION_TYPE",
            )

        # Get application and validate status transition
        application = await self._get_application(tenant_id, decision.application_id)
        current_status = AdmissionApplicationStatus(application.status)
        target_status = AdmissionApplicationStatus.OFFERED

        allowed = VALID_TRANSITIONS.get(current_status, [])
        if target_status not in allowed:
            raise DecisionServiceError(
                f"Cannot transition application from {current_status.value} to {target_status.value}",
                code="INVALID_TRANSITION",
            )

        # Update decision
        old_type = decision.decision_type
        decision.decision_type = DecisionType.ACCEPTED.value
        decision.offered_class_id = offered_class_id
        decision.conditions = conditions
        decision.response_deadline = response_deadline
        # Clear waitlist-specific fields
        decision.waitlist_rank = None
        decision.waitlist_notes = None

        # Transition application status
        old_status = application.status
        application.status = target_status.value

        # Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application.id,
            from_status=old_status,
            to_status=target_status.value,
            changed_by=promoted_by,
            reason=f"Promoted from waitlist (was rank {decision.waitlist_rank or 'unranked'})",
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(decision)

        # Send notification (best effort)
        try:
            from app.services.admissions.notification_service import (
                AdmissionNotificationService,
            )

            notifier = AdmissionNotificationService(self.db)
            extra = {}
            if response_deadline:
                extra["deadline"] = response_deadline.strftime("%d/%m/%Y")
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application.id,
                new_status="offered",
                extra_context=extra,
            )
        except Exception:
            logger.exception("waitlist_promotion_notification_failed")

        logger.info(
            "waitlist_promoted",
            decision_id=str(decision_id),
            application_id=str(application.id),
            from_type=old_type,
        )
        return decision

    async def list_waitlisted(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        period_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        List waitlisted decisions ordered by rank (nulls last).

        Returns dicts with decision + application data for the response schema.
        """
        query = (
            select(AdmissionDecision, Application)
            .join(Application, AdmissionDecision.application_id == Application.id)
            .filter(
                AdmissionDecision.tenant_id == tenant_id,
                AdmissionDecision.decision_type == DecisionType.WAITLISTED.value,
                Application.school_id == school_id,
                # Defense-in-depth: filter by tenant_id on both tables
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )

        if period_id:
            query = query.filter(Application.admission_period_id == period_id)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Order: ranked first (ascending), then unranked (nulls last)
        query = query.order_by(
            AdmissionDecision.waitlist_rank.asc().nullslast(),
            AdmissionDecision.created_at.asc(),
        )
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        items = []
        for decision, application in result.all():
            items.append({
                "decision_id": decision.id,
                "application_id": application.id,
                "applicant_name": f"{application.applicant_first_name} {application.applicant_last_name}",
                "tracking_code": application.tracking_code,
                "target_class_name": None,  # Populated by endpoint if needed
                "waitlist_rank": decision.waitlist_rank,
                "waitlist_notes": decision.waitlist_notes,
                "decision_date": decision.decision_date,
                "created_at": decision.created_at,
            })

        return items, total

    # ---- Private helpers (new) ----

    async def _get_decision(
        self, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> AdmissionDecision:
        """Get decision by ID with defense-in-depth tenant check."""
        result = await self.db.execute(
            select(AdmissionDecision).filter(
                AdmissionDecision.id == decision_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                AdmissionDecision.tenant_id == tenant_id,
            )
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise DecisionServiceError("Decision not found", code="NOT_FOUND")
        return decision

    async def _get_school(
        self, tenant_id: uuid.UUID, school_id: uuid.UUID
    ) -> School:
        """Get school for template rendering."""
        result = await self.db.execute(
            select(School).filter(
                School.id == school_id,
                School.tenant_id == tenant_id,
            )
        )
        school = result.scalar_one_or_none()
        if not school:
            raise DecisionServiceError("School not found", code="NOT_FOUND")
        return school

    @staticmethod
    def _render_pdf(template_name: str, context: dict) -> bytes:
        """Render a Jinja2 template to PDF bytes using WeasyPrint."""
        env = Environment(
            loader=FileSystemLoader(str(_ADMISSIONS_TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template(template_name)
        html_content = template.render(**context)

        html = HTML(string=html_content)
        pdf_buffer = BytesIO()
        html.write_pdf(pdf_buffer)
        return pdf_buffer.getvalue()
```

### 4.2 Modified: `backend/app/services/admissions/applicant_service.py`

Add the following methods to the existing `ApplicantAccountService` class:

```python
class ApplicantAccountService:
    # ... existing methods ...

    async def respond_to_offer(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        response: str,
        notes: str | None = None,
    ) -> Application:
        """
        Accept or decline an admission offer.

        Validations:
        1. Application exists and belongs to this tenant
        2. IDOR check: application.applicant_user_id == user_id
        3. Application status must be 'offered'
        4. Response must be 'accepted' or 'declined'

        Effects:
        - accepted: status -> ACCEPTED, offer_responded_at, offer_response
        - declined: status -> WITHDRAWN, offer_responded_at, offer_response

        Sends notification to school admissions office.
        """
        from app.models.admissions import (
            AdmissionApplicationStatus,
            ApplicationStatusHistory,
            VALID_TRANSITIONS,
        )

        application = await self._get_applicant_application(
            tenant_id, application_id, user_id
        )

        if application.status != AdmissionApplicationStatus.OFFERED.value:
            raise ApplicantAccountError(
                "This application is not in 'offered' status. Cannot respond to offer.",
                code="INVALID_STATUS",
            )

        valid_responses = {"accepted", "declined"}
        if response not in valid_responses:
            raise ApplicantAccountError(
                f"Invalid response: must be one of {valid_responses}",
                code="INVALID_RESPONSE",
            )

        # Determine target status
        if response == "accepted":
            target_status = AdmissionApplicationStatus.ACCEPTED
        else:
            target_status = AdmissionApplicationStatus.WITHDRAWN

        # Validate transition
        current = AdmissionApplicationStatus(application.status)
        allowed = VALID_TRANSITIONS.get(current, [])
        if target_status not in allowed:
            raise ApplicantAccountError(
                f"Cannot transition from {current.value} to {target_status.value}",
                code="INVALID_TRANSITION",
            )

        # Update application
        old_status = application.status
        application.status = target_status.value
        application.offer_responded_at = datetime.now(UTC)
        application.offer_response = response
        application.offer_response_notes = notes

        # Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application.id,
            from_status=old_status,
            to_status=target_status.value,
            changed_by=user_id,
            reason=f"Applicant {'accepted' if response == 'accepted' else 'declined'} offer"
            + (f": {notes}" if notes else ""),
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)

        # Send notification to school (best effort)
        try:
            from app.services.admissions.notification_service import (
                AdmissionNotificationService,
            )

            notifier = AdmissionNotificationService(self.db)
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application.id,
                new_status=f"offer_{response}",
                extra_context={},
            )
        except Exception:
            logger.exception("offer_response_notification_failed")

        logger.info(
            "offer_responded",
            application_id=str(application_id),
            response=response,
            user_id=str(user_id),
        )
        return application

    async def get_offer_details(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
    ) -> dict:
        """
        Get full offer details for the applicant portal.

        IDOR check: verifies application.applicant_user_id == user_id.
        Returns decision + conditions + deadline + letter URL + response status.
        """
        from app.models.admissions import AdmissionDecision
        from app.models.academic import Class

        application = await self._get_applicant_application(
            tenant_id, application_id, user_id
        )

        # Load decision
        decision_result = await self.db.execute(
            select(AdmissionDecision).filter(
                AdmissionDecision.application_id == application.id,
                AdmissionDecision.tenant_id == tenant_id,
            )
        )
        decision = decision_result.scalar_one_or_none()
        if not decision:
            raise ApplicantAccountError("No decision found for this application", code="NOT_FOUND")

        # Load school name
        from app.models.school import School

        school_result = await self.db.execute(
            select(School.name).filter(
                School.id == application.school_id,
                School.tenant_id == tenant_id,
            )
        )
        school_name = school_result.scalar_one_or_none() or ""

        # Load offered class name
        offered_class_name = None
        if decision.offered_class_id:
            cls_result = await self.db.execute(
                select(Class.name).filter(
                    Class.id == decision.offered_class_id,
                    Class.tenant_id == tenant_id,
                )
            )
            offered_class_name = cls_result.scalar_one_or_none()

        # Generate presigned URL for letter if it exists
        letter_url = None
        if decision.decision_letter_url:
            from app.services.s3 import get_s3_service

            s3 = get_s3_service()
            letter_url = s3.generate_presigned_url(decision.decision_letter_url, expires_in=3600)

        # Check if offer has expired
        is_expired = False
        if (
            decision.response_deadline
            and application.offer_responded_at is None
            and decision.response_deadline < datetime.now(UTC).date()
        ):
            is_expired = True

        return {
            "application_id": application.id,
            "applicant_name": f"{application.applicant_first_name} {application.applicant_last_name}",
            "tracking_code": application.tracking_code,
            "school_name": school_name,
            "offered_class_name": offered_class_name,
            "decision_type": decision.decision_type,
            "decision_date": decision.decision_date,
            "conditions": decision.conditions,
            "response_deadline": decision.response_deadline,
            "decision_letter_url": letter_url,
            "offer_responded_at": application.offer_responded_at,
            "offer_response": application.offer_response,
            "offer_response_notes": application.offer_response_notes,
            "is_expired": is_expired,
        }

    async def _get_applicant_application(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Application:
        """
        Get application with IDOR check: applicant_user_id must match user_id.
        """
        result = await self.db.execute(
            select(Application).filter(
                Application.id == application_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = result.scalar_one_or_none()
        if not application:
            raise ApplicantAccountError("Application not found", code="NOT_FOUND")

        # IDOR check: only the owning applicant can interact with this offer
        if str(application.applicant_user_id) != str(user_id):
            raise ApplicantAccountError("Application not found", code="NOT_FOUND")

        return application
```

### 4.3 Update `backend/app/services/admissions/__init__.py`

No new service classes to re-export. The methods are added to existing `DecisionService` and `ApplicantAccountService`.

---

## 5. Celery Tasks

### 5.1 New File: `backend/app/tasks/admission_reminders.py`

```python
"""
SIMS Plus - Incomplete Application Reminder Task

Daily Celery task that sends SMS/email reminders to applicants with
DRAFT applications on admission periods approaching their close date.

Runs daily at 09:00 UTC via Celery Beat.
Uses the platform admin superuser engine to iterate tenants, then
sets tenant context per-tenant in isolated sessions for RLS-scoped queries.

CRITICAL: Each tenant is processed in its own session to prevent
cross-tenant context leaking on error (C1 security fix).
"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_platform_admin_session_maker
from app.models.admissions import AdmissionApplicationStatus, Application
from app.models.admissions.application import ApplicationGuardian
from app.models.admissions.period import AdmissionPeriod
from app.models.tenant import Tenant

logger = structlog.get_logger(__name__)


async def _send_reminders_for_tenant(
    session: AsyncSession,
    tenant_id: str,
    tenant_subdomain: str,
) -> int:
    """
    Send reminders for a single tenant.

    Caller is responsible for setting/clearing tenant context and
    committing/rolling back the session.

    Returns the number of reminders sent.
    """
    today = datetime.now(UTC).date()

    # Find active periods with reminders enabled and approaching close date
    period_result = await session.execute(
        select(AdmissionPeriod).filter(
            AdmissionPeriod.tenant_id == tenant_id,
            AdmissionPeriod.status == "open",
            AdmissionPeriod.reminder_enabled.is_(True),
            AdmissionPeriod.reminder_days_before_close.isnot(None),
            AdmissionPeriod.deleted_at.is_(None),
        )
    )
    periods = period_result.scalars().all()

    sent_count = 0

    for period in periods:
        # Calculate reminder trigger date
        reminder_date = period.end_date - timedelta(
            days=period.reminder_days_before_close
        )

        # Only send on or after the trigger date, but before close
        if not (reminder_date <= today <= period.end_date):
            continue

        # Find DRAFT applications for this period
        app_result = await session.execute(
            select(Application)
            .filter(
                Application.tenant_id == tenant_id,
                Application.admission_period_id == period.id,
                Application.status == AdmissionApplicationStatus.DRAFT.value,
                Application.deleted_at.is_(None),
            )
        )
        draft_apps = app_result.scalars().all()

        for application in draft_apps:
            try:
                # Get primary guardian for notification
                guardian_result = await session.execute(
                    select(ApplicationGuardian).filter(
                        ApplicationGuardian.tenant_id == tenant_id,
                        ApplicationGuardian.application_id == application.id,
                        ApplicationGuardian.is_primary.is_(True),
                        ApplicationGuardian.deleted_at.is_(None),
                    )
                )
                guardian = guardian_result.scalar_one_or_none()
                if not guardian:
                    continue

                # Send notification via notification service
                from app.services.admissions.notification_service import (
                    AdmissionNotificationService,
                )

                notifier = AdmissionNotificationService(session)
                await notifier.notify_status_change(
                    tenant_id=tenant_id,
                    application_id=application.id,
                    new_status="incomplete_reminder",
                    extra_context={
                        "deadline": period.end_date.strftime("%d/%m/%Y"),
                        "days_remaining": (period.end_date - today).days,
                    },
                )
                sent_count += 1
            except Exception:
                logger.exception(
                    "reminder_send_failed",
                    application_id=str(application.id),
                    tenant_id=tenant_id,
                )

    return sent_count


async def send_incomplete_application_reminders() -> dict:
    """
    Main task entry point. Iterates all active tenants and sends
    reminders for incomplete applications approaching deadline.

    CRITICAL: Uses a separate session per tenant to prevent cross-tenant
    context leaking if one tenant's work fails mid-transaction.

    Returns: { tenants_processed: N, reminders_sent: N }
    """
    session_maker = get_platform_admin_session_maker()
    tenants_processed = 0
    total_reminders = 0

    # First, fetch all active tenants in a read-only session
    async with session_maker() as session:
        result = await session.execute(
            select(Tenant.id, Tenant.subdomain).filter(
                Tenant.status.in_(["active", "trial"]),
                Tenant.deleted_at.is_(None),
            )
        )
        tenants = result.all()

    # Process each tenant in its own isolated session
    for tenant_id, subdomain in tenants:
        async with session_maker() as per_tenant_session:
            try:
                await per_tenant_session.execute(
                    text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                    {"tid": str(tenant_id)},
                )
                count = await _send_reminders_for_tenant(
                    per_tenant_session, str(tenant_id), subdomain
                )
                await per_tenant_session.commit()
                total_reminders += count
                tenants_processed += 1
            except Exception:
                await per_tenant_session.rollback()
                logger.exception(
                    "reminder_tenant_failed",
                    tenant_id=str(tenant_id),
                )
            finally:
                try:
                    await per_tenant_session.execute(text("SELECT clear_tenant_context()"))
                except Exception:
                    pass  # Connection may already be closed

    summary = {
        "tenants_processed": tenants_processed,
        "reminders_sent": total_reminders,
    }
    logger.info("incomplete_reminders_complete", **summary)
    return summary
```

### 5.2 New File: `backend/app/tasks/offer_expiry.py`

```python
"""
SIMS Plus - Offer Expiry Task

Daily Celery task that expires unanswered admission offers past their
response_deadline.

Runs daily at 00:00 UTC via Celery Beat.
Uses the platform admin superuser engine to iterate tenants, then
sets tenant context per-tenant in isolated sessions for RLS-scoped queries.

CRITICAL: Each tenant is processed in its own session to prevent
cross-tenant context leaking on error (C1 security fix).
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_platform_admin_session_maker
from app.models.admissions import (
    AdmissionApplicationStatus,
    AdmissionDecision,
    Application,
    ApplicationStatusHistory,
    DecisionType,
)
from app.models.tenant import Tenant

logger = structlog.get_logger(__name__)


async def _expire_offers_for_tenant(
    session: AsyncSession,
    tenant_id: str,
) -> int:
    """
    Expire unanswered offers for a single tenant.

    Caller is responsible for setting/clearing tenant context and
    committing/rolling back the session.

    Finds applications where:
    - status = 'offered'
    - decision.response_deadline < today
    - offer_responded_at IS NULL (not yet responded)

    Transitions them to EXPIRED status.
    Returns the number of expired offers.
    """
    today = datetime.now(UTC).date()

    # Find offered applications with expired deadlines
    result = await session.execute(
        select(Application, AdmissionDecision)
        .join(AdmissionDecision, AdmissionDecision.application_id == Application.id)
        .filter(
            Application.tenant_id == tenant_id,
            Application.status == AdmissionApplicationStatus.OFFERED.value,
            Application.offer_responded_at.is_(None),
            Application.deleted_at.is_(None),
            AdmissionDecision.tenant_id == tenant_id,
            AdmissionDecision.response_deadline.isnot(None),
            AdmissionDecision.response_deadline < today,
        )
    )
    rows = result.all()

    expired_count = 0

    for application, decision in rows:
        try:
            old_status = application.status
            application.status = AdmissionApplicationStatus.EXPIRED.value

            # Record status history
            history = ApplicationStatusHistory(
                tenant_id=tenant_id,
                application_id=application.id,
                from_status=old_status,
                to_status=AdmissionApplicationStatus.EXPIRED.value,
                changed_by=None,  # System action
                reason=f"Offer expired: response deadline was {decision.response_deadline.strftime('%d/%m/%Y')}",
            )
            session.add(history)

            # Send notification (best effort)
            try:
                from app.services.admissions.notification_service import (
                    AdmissionNotificationService,
                )

                notifier = AdmissionNotificationService(session)
                await notifier.notify_status_change(
                    tenant_id=tenant_id,
                    application_id=application.id,
                    new_status="expired",
                    extra_context={
                        "deadline": decision.response_deadline.strftime("%d/%m/%Y"),
                    },
                )
            except Exception:
                logger.exception(
                    "expiry_notification_failed",
                    application_id=str(application.id),
                )

            expired_count += 1
        except Exception:
            logger.exception(
                "offer_expiry_failed",
                application_id=str(application.id),
                tenant_id=tenant_id,
            )

    return expired_count


async def expire_unanswered_offers() -> dict:
    """
    Main task entry point. Iterates all active tenants and expires
    offers past their response deadline.

    CRITICAL: Uses a separate session per tenant to prevent cross-tenant
    context leaking if one tenant's work fails mid-transaction.

    Returns: { tenants_processed: N, offers_expired: N }
    """
    session_maker = get_platform_admin_session_maker()
    tenants_processed = 0
    total_expired = 0

    # First, fetch all active tenants in a read-only session
    async with session_maker() as session:
        result = await session.execute(
            select(Tenant.id).filter(
                Tenant.status.in_(["active", "trial"]),
                Tenant.deleted_at.is_(None),
            )
        )
        tenant_ids = [row[0] for row in result.all()]

    # Process each tenant in its own isolated session
    for tid in tenant_ids:
        async with session_maker() as per_tenant_session:
            try:
                await per_tenant_session.execute(
                    text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                    {"tid": str(tid)},
                )
                count = await _expire_offers_for_tenant(per_tenant_session, str(tid))
                await per_tenant_session.commit()
                total_expired += count
                tenants_processed += 1
            except Exception:
                await per_tenant_session.rollback()
                logger.exception(
                    "expiry_tenant_failed",
                    tenant_id=str(tid),
                )
            finally:
                try:
                    await per_tenant_session.execute(text("SELECT clear_tenant_context()"))
                except Exception:
                    pass  # Connection may already be closed

    summary = {
        "tenants_processed": tenants_processed,
        "offers_expired": total_expired,
    }
    logger.info("offer_expiry_complete", **summary)
    return summary
```

### 5.3 Celery Beat Registration

Add to the Celery Beat schedule in `backend/app/tasks/__init__.py`:

```python
from celery.schedules import crontab

# Add to CELERYBEAT_SCHEDULE:
"expire-unanswered-offers": {
    "task": "app.tasks.offer_expiry.expire_unanswered_offers",
    "schedule": crontab(minute=0, hour=0),  # Daily at 00:00 UTC
},
"send-incomplete-application-reminders": {
    "task": "app.tasks.admission_reminders.send_incomplete_application_reminders",
    "schedule": crontab(minute=0, hour=9),  # Daily at 09:00 UTC
},
```

---

## 6. Endpoints

### 6.1 Add to `backend/app/api/v1/endpoints/admissions/decisions.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| POST | `/admissions/decisions/{id}/generate-letter` | Generate admission letter PDF | admissions.decide | - | GenerateLetterResponse (201) |
| POST | `/admissions/decisions/{id}/generate-rejection-letter` | Generate rejection letter PDF | admissions.decide | `{ rejection_reason?: str }` | GenerateLetterResponse (201) |
| PATCH | `/admissions/decisions/{id}/waitlist-rank` | Set waitlist rank | admissions.decide | WaitlistRankUpdate | AdmissionDecisionResponse |
| POST | `/admissions/decisions/reorder-waitlist` | Bulk reorder waitlist | admissions.decide | WaitlistReorderRequest | list[AdmissionDecisionResponse] |
| POST | `/admissions/decisions/{id}/promote-waitlist` | Promote waitlisted to offered | admissions.decide | WaitlistPromoteRequest | AdmissionDecisionResponse |
| GET | `/admissions/decisions/waitlist` | List waitlisted by rank | admissions.read | Query: period_id, page, page_size | WaitlistListResponse |

**Endpoint implementation:**

```python
# Add to existing decisions.py router:

@router.post(
    "/{decision_id}/generate-letter",
    response_model=GenerateLetterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate admission letter PDF",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def generate_admission_letter(
    decision_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> GenerateLetterResponse:
    """Generate admission letter PDF and upload to S3. Returns presigned URL."""
    service = DecisionService(db)
    try:
        letter_url = await service.generate_admission_letter(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
        )
        return GenerateLetterResponse(
            decision_id=decision_id,
            letter_url=letter_url,
            letter_type="admission",
        )
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{decision_id}/generate-rejection-letter",
    response_model=GenerateLetterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate rejection letter PDF",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def generate_rejection_letter(
    decision_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    rejection_reason: str | None = None,
) -> GenerateLetterResponse:
    """Generate rejection letter PDF and upload to S3. Returns presigned URL."""
    service = DecisionService(db)
    try:
        letter_url = await service.generate_rejection_letter(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
            rejection_reason=rejection_reason,
        )
        return GenerateLetterResponse(
            decision_id=decision_id,
            letter_url=letter_url,
            letter_type="rejection",
        )
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{decision_id}/waitlist-rank",
    response_model=AdmissionDecisionResponse,
    summary="Update waitlist rank",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def update_waitlist_rank(
    decision_id: UUID,
    data: WaitlistRankUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionDecisionResponse:
    """Set or update the waitlist rank for a waitlisted decision."""
    service = DecisionService(db)
    try:
        decision = await service.update_waitlist_rank(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
            rank=data.rank,
        )
        return AdmissionDecisionResponse.model_validate(decision)
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/reorder-waitlist",
    response_model=list[AdmissionDecisionResponse],
    summary="Bulk reorder waitlist",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def reorder_waitlist(
    data: WaitlistReorderRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[AdmissionDecisionResponse]:
    """Bulk reorder waitlist by specifying decision IDs in desired rank order."""
    service = DecisionService(db)
    try:
        decisions = await service.reorder_waitlist(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            period_id=data.period_id,
            ordered_decision_ids=data.ordered_decision_ids,
        )
        return [AdmissionDecisionResponse.model_validate(d) for d in decisions]
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{decision_id}/promote-waitlist",
    response_model=AdmissionDecisionResponse,
    summary="Promote waitlisted applicant to offered",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def promote_from_waitlist(
    decision_id: UUID,
    data: WaitlistPromoteRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionDecisionResponse:
    """Promote a waitlisted applicant to offered status."""
    service = DecisionService(db)
    try:
        decision = await service.promote_from_waitlist(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
            offered_class_id=data.offered_class_id,
            response_deadline=data.response_deadline,
            conditions=data.conditions,
            promoted_by=UUID(user["user_id"]),
        )
        return AdmissionDecisionResponse.model_validate(decision)
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.get(
    "/waitlist",
    response_model=WaitlistListResponse,
    summary="List waitlisted decisions",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_waitlist(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    period_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> WaitlistListResponse:
    """List waitlisted decisions ordered by rank. Nulls appear last."""
    import math

    service = DecisionService(db)
    try:
        items, total = await service.list_waitlisted(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            period_id=period_id,
            page=page,
            page_size=page_size,
        )
        return WaitlistListResponse(
            items=[WaitlistEntryResponse(**item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except DecisionServiceError as e:
        raise _handle_error(e)
```

Update `_handle_error` to include new error codes:

```python
def _handle_error(e: DecisionServiceError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_TRANSITION": 422,
        "INVALID_DECISION_TYPE": 422,
        "MISSING_CLASS": 422,
        "DECISION_EXISTS": 409,
        # Phase 2 additions
        "INVALID_STATUS": 422,
        "INVALID_RESPONSE": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )
```

### 6.2 Add to `backend/app/api/v1/endpoints/admissions/applicant.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| GET | `/admissions/applicant/offers/{application_id}` | Get offer details | role=applicant | - | OfferDetailResponse |
| POST | `/admissions/applicant/offers/{application_id}/respond` | Accept/decline offer | role=applicant | OfferResponseRequest | OfferDetailResponse |

**Endpoint implementation:**

```python
# Add to existing applicant.py router:

@router.get(
    "/offers/{application_id}",
    response_model=OfferDetailResponse,
    summary="Get offer details",
)
async def get_offer_details(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> OfferDetailResponse:
    """
    Get full offer details for an application.

    IDOR check: only the owning applicant can view offer details.
    Returns decision info, conditions, deadline, letter URL, and response status.
    """
    service = ApplicantAccountService(db)
    try:
        details = await service.get_offer_details(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            user_id=UUID(user["user_id"]),
        )
        return OfferDetailResponse(**details)
    except ApplicantAccountError as e:
        raise HTTPException(
            status_code=_error_status(e.code),
            detail=e.message,
        )


@router.post(
    "/offers/{application_id}/respond",
    response_model=OfferDetailResponse,
    summary="Accept or decline admission offer",
)
async def respond_to_offer(
    application_id: UUID,
    data: OfferResponseRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> OfferDetailResponse:
    """
    Accept or decline an admission offer.

    IDOR check: only the owning applicant can respond.
    - accepted: transitions application to ACCEPTED status
    - declined: transitions application to WITHDRAWN status
    """
    service = ApplicantAccountService(db)
    try:
        application = await service.respond_to_offer(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            user_id=UUID(user["user_id"]),
            response=data.response.value,
            notes=data.notes,
        )
        # Re-fetch full offer details for the response
        details = await service.get_offer_details(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            user_id=UUID(user["user_id"]),
        )
        return OfferDetailResponse(**details)
    except ApplicantAccountError as e:
        raise HTTPException(
            status_code=_error_status(e.code),
            detail=e.message,
        )
```

Update `_error_status` in `applicant.py` to include new codes:

```python
def _error_status(code: str) -> int:
    status_map = {
        # ... existing mappings ...
        "INVALID_STATUS": 422,
        "INVALID_RESPONSE": 422,
        "INVALID_TRANSITION": 422,
    }
    return status_map.get(code, 400)
```

---

## 7. Migration

### File: `backend/alembic/versions/20260408_0100_letters_and_waitlist.py`

```python
"""Admission letters, offer response tracking, waitlist management, and reminders.

Revision ID: 20260408_0100
Revises: <CURRENT_HEAD>
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260408_0100"
down_revision = "<CURRENT_HEAD>"  # Replace with actual current head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========== PHASE 1: Column Additions ==========

    # admission_decisions — rejection letter + waitlist fields
    op.add_column(
        "admission_decisions",
        sa.Column("rejection_reason", sa.Text, nullable=True),
    )
    op.add_column(
        "admission_decisions",
        sa.Column("rejection_letter_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "admission_decisions",
        sa.Column("waitlist_rank", sa.Integer, nullable=True),
    )
    op.add_column(
        "admission_decisions",
        sa.Column("waitlist_notes", sa.Text, nullable=True),
    )

    # applications — offer response tracking
    op.add_column(
        "applications",
        sa.Column("offer_responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("offer_response", sa.String(20), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("offer_response_notes", sa.Text, nullable=True),
    )

    # admission_periods — reminder configuration
    op.add_column(
        "admission_periods",
        sa.Column(
            "reminder_enabled",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "admission_periods",
        sa.Column("reminder_days_before_close", sa.Integer, nullable=True),
    )

    # ========== PHASE 2: Indexes ==========

    # Waitlist index for efficient ordering queries
    op.create_index(
        "ix_decisions_waitlist",
        "admission_decisions",
        ["tenant_id", "waitlist_rank"],
        postgresql_where=sa.text(
            "decision_type = 'waitlisted' AND waitlist_rank IS NOT NULL AND deleted_at IS NULL"
        ),
    )

    # Offer response tracking — find unanswered offers efficiently
    op.create_index(
        "ix_applications_offer_pending",
        "applications",
        ["tenant_id", "status"],
        postgresql_where=sa.text(
            "status = 'offered' AND offer_responded_at IS NULL AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_applications_offer_pending", table_name="applications")
    op.drop_index("ix_decisions_waitlist", table_name="admission_decisions")

    # Drop columns (reverse order of addition)
    op.drop_column("admission_periods", "reminder_days_before_close")
    op.drop_column("admission_periods", "reminder_enabled")

    op.drop_column("applications", "offer_response_notes")
    op.drop_column("applications", "offer_response")
    op.drop_column("applications", "offer_responded_at")

    op.drop_column("admission_decisions", "waitlist_notes")
    op.drop_column("admission_decisions", "waitlist_rank")
    op.drop_column("admission_decisions", "rejection_letter_url")
    op.drop_column("admission_decisions", "rejection_reason")
```

> **RLS Note:** This migration adds columns to existing tables only — no new tables. Existing
> row-level security policies on `admission_decisions`, `applications`, and `admission_periods`
> already cover all columns in those tables (policies filter by `tenant_id` at the row level),
> so no RLS policy changes are needed. No updates to `verify_rls.py` or `TENANT_SCOPED_TABLES`
> in `conftest.py` are required.

---

## 8. Frontend

### 8.1 Types: `frontend/types/admissions.type.ts` (additions)

Add the following types to the existing admissions types file:

```typescript
// Offer Response
export type OfferResponseType = "accepted" | "declined";

export interface OfferResponseRequest {
  response: OfferResponseType;
  notes?: string;
}

export interface OfferDetailResponse {
  application_id: string;
  applicant_name: string;
  tracking_code: string;
  school_name: string;
  offered_class_name: string | null;
  decision_type: string;
  decision_date: string;
  conditions: string | null;
  response_deadline: string | null;
  decision_letter_url: string | null;
  offer_responded_at: string | null;
  offer_response: string | null;
  offer_response_notes: string | null;
  is_expired: boolean;
}

// Waitlist
export interface WaitlistRankUpdate {
  rank: number;
}

export interface WaitlistReorderRequest {
  period_id: string;
  ordered_decision_ids: string[];
}

export interface WaitlistPromoteRequest {
  offered_class_id: string;
  response_deadline?: string;
  conditions?: string;
}

export interface WaitlistEntryResponse {
  decision_id: string;
  application_id: string;
  applicant_name: string;
  tracking_code: string;
  target_class_name: string | null;
  waitlist_rank: number | null;
  waitlist_notes: string | null;
  decision_date: string;
  created_at: string;
}

export interface WaitlistListResponse {
  items: WaitlistEntryResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Letter Generation
export interface GenerateLetterResponse {
  decision_id: string;
  letter_url: string;
  letter_type: "admission" | "rejection";
}

// Reminder Config
export interface ReminderConfigUpdate {
  reminder_enabled: boolean;
  reminder_days_before_close: number | null;
}
```

### 8.2 Server Actions: `frontend/actions/admissions.action.ts` (additions)

Add the following actions to the existing admissions actions file:

```typescript
// Letter generation
export async function generateAdmissionLetter(decisionId: string) {
  return apiPost<GenerateLetterResponse>(
    `/admissions/decisions/${decisionId}/generate-letter`
  );
}

export async function generateRejectionLetter(
  decisionId: string,
  rejectionReason?: string
) {
  return apiPost<GenerateLetterResponse>(
    `/admissions/decisions/${decisionId}/generate-rejection-letter`,
    { rejection_reason: rejectionReason }
  );
}

// Waitlist management
export async function updateWaitlistRank(decisionId: string, rank: number) {
  return apiPatch<AdmissionDecisionResponse>(
    `/admissions/decisions/${decisionId}/waitlist-rank`,
    { rank }
  );
}

export async function reorderWaitlist(data: WaitlistReorderRequest) {
  return apiPost<AdmissionDecisionResponse[]>(
    "/admissions/decisions/reorder-waitlist",
    data
  );
}

export async function promoteFromWaitlist(
  decisionId: string,
  data: WaitlistPromoteRequest
) {
  return apiPost<AdmissionDecisionResponse>(
    `/admissions/decisions/${decisionId}/promote-waitlist`,
    data
  );
}

export async function getWaitlist(params?: {
  period_id?: string;
  page?: number;
  page_size?: number;
}) {
  const query = new URLSearchParams();
  if (params?.period_id) query.set("period_id", params.period_id);
  if (params?.page) query.set("page", params.page.toString());
  if (params?.page_size) query.set("page_size", params.page_size.toString());
  return apiGet<WaitlistListResponse>(
    `/admissions/decisions/waitlist?${query.toString()}`
  );
}

// Applicant offer actions
export async function getOfferDetails(applicationId: string) {
  return apiGet<OfferDetailResponse>(
    `/admissions/applicant/offers/${applicationId}`
  );
}

export async function respondToOffer(
  applicationId: string,
  data: OfferResponseRequest
) {
  return apiPost<OfferDetailResponse>(
    `/admissions/applicant/offers/${applicationId}/respond`,
    data
  );
}
```

### 8.3 Pages

**Modified: `/admissions/decisions/page.tsx`** (Decisions Management)

Add a "Waitlist" tab alongside the existing decisions list:

- Waitlist tab shows `WaitlistTable` component with drag-and-drop reordering
- Each row has: Rank, Applicant Name, Tracking Code, Target Class, Date, Actions
- Actions: Promote (opens WaitlistPromoteDialog), Edit Rank, Add Notes
- Bulk "Save Order" button calls `reorderWaitlist()`
- Letter generation buttons on accepted/rejected decision rows

**Modified: `/admissions/applicant/dashboard/page.tsx`** (Applicant Dashboard)

Add offer response UI when application status is "offered":

- Highlight banner: "You have been offered admission!"
- View Offer Details button -> opens `OfferDetailPanel`
- Accept / Decline buttons with confirmation dialog
- Download admission letter link (if generated)
- Deadline countdown display

### 8.4 Components

| Component | Props | Description |
|-----------|-------|-------------|
| `waitlist-table.tsx` | items, onReorder, onPromote, onEditRank | TanStack Table with drag-and-drop row reordering via @dnd-kit/sortable |
| `waitlist-promote-dialog.tsx` | decisionId, onPromote | Dialog: select class, set deadline, add conditions |
| `letter-preview.tsx` | letterUrl, letterType | Iframe/embed PDF preview with download button |
| `generate-letter-button.tsx` | decisionId, decisionType, existingUrl | Button that generates PDF on click, shows loading state, opens preview |
| `offer-response-form.tsx` | applicationId, offerDetails, onRespond | Accept/Decline form with optional notes field and confirmation step |
| `offer-detail-panel.tsx` | details: OfferDetailResponse | Full offer details card: school, class, conditions, deadline, letter download |
| `reminder-settings.tsx` | periodId, config, onUpdate | Toggle + days input for incomplete application reminders |
| `deadline-countdown.tsx` | deadline: string | Countdown display with color coding (green > 7 days, yellow 3-7, red < 3) |

### 8.5 Sidebar Update

No sidebar changes needed. The waitlist tab is added to the existing decisions page. Offer response is added to the existing applicant dashboard.

---

## 9. Tests

### 9.1 `backend/tests/test_admission_letters.py` (~8 tests)

Follow the two-engine pattern from `test_admission_applications.py`:

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestAdmissionLetters:
    """Tests for admission and rejection letter PDF generation."""

    async def test_generate_admission_letter_success(self, app_session, prereqs):
        """Generate admission letter for an accepted decision. Verifies S3 upload and URL returned."""

    async def test_generate_admission_letter_rejects_non_acceptance(self, app_session, prereqs):
        """Attempting to generate admission letter for a rejected decision raises error."""

    async def test_generate_admission_letter_updates_decision_url(self, app_session, prereqs):
        """After generation, decision.decision_letter_url is set to S3 key."""

    async def test_generate_rejection_letter_success(self, app_session, prereqs):
        """Generate rejection letter for a rejected decision."""

    async def test_generate_rejection_letter_with_reason(self, app_session, prereqs):
        """Rejection reason is persisted on decision and included in letter context."""

    async def test_generate_rejection_letter_rejects_non_rejection(self, app_session, prereqs):
        """Attempting to generate rejection letter for an accepted decision raises error."""

    async def test_admission_letter_template_renders_school_info(self, app_session, prereqs):
        """Verify the Jinja2 template includes school name, logo, and primary color."""

    async def test_letter_presigned_url_returned(self, app_session, prereqs):
        """Verify the returned URL is a presigned S3 URL (contains Signature param)."""
```

### 9.2 `backend/tests/test_offer_acceptance.py` (~10 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestOfferAcceptance:
    """Tests for applicant offer accept/decline flow."""

    async def test_accept_offer_transitions_to_accepted(self, app_session, prereqs):
        """Accepting an offered application transitions status to ACCEPTED."""

    async def test_decline_offer_transitions_to_withdrawn(self, app_session, prereqs):
        """Declining an offered application transitions status to WITHDRAWN."""

    async def test_respond_sets_timestamp_and_response(self, app_session, prereqs):
        """offer_responded_at, offer_response, and offer_response_notes are set."""

    async def test_respond_creates_status_history(self, app_session, prereqs):
        """Status history record is created with applicant as changed_by."""

    async def test_respond_rejects_non_offered_status(self, app_session, prereqs):
        """Attempting to respond to a non-offered application raises INVALID_STATUS."""

    async def test_respond_rejects_invalid_response_value(self, app_session, prereqs):
        """Response must be 'accepted' or 'declined'. Other values raise INVALID_RESPONSE."""

    async def test_idor_prevention_wrong_user(self, app_session, prereqs):
        """Applicant A cannot respond to applicant B's offer."""

    async def test_get_offer_details_success(self, app_session, prereqs):
        """Get offer details returns decision, conditions, deadline, and letter URL."""

    async def test_get_offer_details_idor(self, app_session, prereqs):
        """Applicant A cannot view applicant B's offer details."""

    async def test_get_offer_details_shows_expired_flag(self, app_session, prereqs):
        """When response_deadline has passed and no response, is_expired is True."""
```

### 9.3 `backend/tests/test_waitlist_management.py` (~10 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestWaitlistManagement:
    """Tests for waitlist ranking, reordering, and promotion."""

    async def test_set_waitlist_rank(self, app_session, prereqs):
        """Set rank on a waitlisted decision."""

    async def test_set_rank_rejects_non_waitlisted(self, app_session, prereqs):
        """Cannot set waitlist rank on an accepted decision."""

    async def test_reorder_waitlist_assigns_sequential_ranks(self, app_session, prereqs):
        """Reorder assigns rank 1, 2, 3... in order of provided IDs."""

    async def test_reorder_validates_all_ids_exist(self, app_session, prereqs):
        """Reorder with a non-existent decision ID raises NOT_FOUND."""

    async def test_reorder_validates_all_are_waitlisted(self, app_session, prereqs):
        """Reorder with an accepted decision in the list raises NOT_FOUND."""

    async def test_reorder_uses_advisory_lock(self, app_session, prereqs):
        """Concurrent reorders are serialized via pg_advisory_xact_lock."""

    async def test_promote_from_waitlist_to_offered(self, app_session, prereqs):
        """Promoting transitions decision type to accepted and application to offered."""

    async def test_promote_clears_waitlist_fields(self, app_session, prereqs):
        """After promotion, waitlist_rank and waitlist_notes are cleared."""

    async def test_promote_sends_notification(self, app_session, prereqs):
        """Promotion sends notification to primary guardian (mocked)."""

    async def test_list_waitlisted_ordered_by_rank(self, app_session, prereqs):
        """Listing waitlisted returns ranked first, then unranked, ordered ascending."""
```

### 9.4 `backend/tests/test_offer_expiry_task.py` (~6 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestOfferExpiryTask:
    """Tests for the daily offer expiry Celery task."""

    async def test_expires_past_deadline_offers(self, app_session, prereqs):
        """Offers with response_deadline in the past are transitioned to EXPIRED."""

    async def test_skips_already_responded_offers(self, app_session, prereqs):
        """Offers where offer_responded_at is set are not expired."""

    async def test_skips_offers_without_deadline(self, app_session, prereqs):
        """Offers with no response_deadline are not expired."""

    async def test_creates_status_history_for_expired(self, app_session, prereqs):
        """Status history record is created with reason including original deadline."""

    async def test_does_not_expire_future_deadline(self, app_session, prereqs):
        """Offers with response_deadline in the future are not expired."""

    async def test_multi_tenant_isolation(self, app_session, prereqs):
        """Expired offers in tenant A do not affect tenant B's offers."""
```

### 9.5 `backend/tests/test_incomplete_reminders.py` (~6 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestIncompleteReminders:
    """Tests for the daily incomplete application reminder Celery task."""

    async def test_sends_reminders_within_window(self, app_session, prereqs):
        """Reminders sent for DRAFT apps when within reminder_days_before_close."""

    async def test_skips_periods_without_reminders_enabled(self, app_session, prereqs):
        """Periods with reminder_enabled=False are skipped."""

    async def test_skips_submitted_applications(self, app_session, prereqs):
        """Only DRAFT applications receive reminders, not submitted ones."""

    async def test_skips_before_reminder_window(self, app_session, prereqs):
        """Reminders not sent if today < end_date - reminder_days_before_close."""

    async def test_skips_after_period_close(self, app_session, prereqs):
        """Reminders not sent if today > end_date."""

    async def test_sends_to_primary_guardian(self, app_session, prereqs):
        """Reminder notification targets the primary guardian of the application."""
```

---

## 10. Task Checklist

Developers should complete these tasks in order:

- [ ] **P2-01**: Add `OfferResponse` enum to `backend/app/models/admissions/enums.py`
- [ ] **P2-02**: Add columns to `AdmissionDecision` model (`rejection_reason`, `rejection_letter_url`, `waitlist_rank`, `waitlist_notes`)
- [ ] **P2-03**: Add columns to `Application` model (`offer_responded_at`, `offer_response`, `offer_response_notes`)
- [ ] **P2-04**: Add columns to `AdmissionPeriod` model (`reminder_enabled`, `reminder_days_before_close`)
- [ ] **P2-05**: Create migration `20260408_0100_letters_and_waitlist.py` (column additions + indexes)
- [ ] **P2-06**: Create PDF template `backend/app/templates/admissions/admission_letter.html`
- [ ] **P2-07**: Create PDF template `backend/app/templates/admissions/rejection_letter.html`
- [ ] **P2-08**: Add schemas to `backend/app/schemas/admissions.py` (OfferResponseRequest, OfferDetailResponse, WaitlistRankUpdate, WaitlistReorderRequest, WaitlistPromoteRequest, WaitlistEntryResponse, WaitlistListResponse, GenerateLetterResponse, ReminderConfigUpdate)
- [ ] **P2-09**: Update `AdmissionDecisionResponse` schema with new fields
- [ ] **P2-10**: Add letter generation methods to `DecisionService` (`generate_admission_letter`, `generate_rejection_letter`, `_render_pdf`, `_get_decision`, `_get_school`)
- [ ] **P2-11**: Add waitlist methods to `DecisionService` (`update_waitlist_rank`, `reorder_waitlist`, `promote_from_waitlist`, `list_waitlisted`)
- [ ] **P2-12**: Add offer response methods to `ApplicantAccountService` (`respond_to_offer`, `get_offer_details`, `_get_applicant_application`)
- [ ] **P2-13**: Add notification templates for `incomplete_reminder`, `offer_accepted`, `offer_declined`, `expired` to `notification_service.py`
- [ ] **P2-14**: Add 6 decision endpoints to `backend/app/api/v1/endpoints/admissions/decisions.py`
- [ ] **P2-15**: Add 2 applicant endpoints to `backend/app/api/v1/endpoints/admissions/applicant.py`
- [ ] **P2-16**: Create `backend/app/tasks/offer_expiry.py` (Celery task)
- [ ] **P2-17**: Create `backend/app/tasks/admission_reminders.py` (Celery task)
- [ ] **P2-18**: Register tasks in Celery Beat schedule (`backend/app/tasks/__init__.py`)
- [ ] **P2-19**: Write `backend/tests/test_admission_letters.py` (~8 tests)
- [ ] **P2-20**: Write `backend/tests/test_offer_acceptance.py` (~10 tests)
- [ ] **P2-21**: Write `backend/tests/test_waitlist_management.py` (~10 tests)
- [ ] **P2-22**: Write `backend/tests/test_offer_expiry_task.py` (~6 tests)
- [ ] **P2-23**: Write `backend/tests/test_incomplete_reminders.py` (~6 tests)
- [ ] **P2-24**: Add TypeScript types to `frontend/types/admissions.type.ts`
- [ ] **P2-25**: Add server actions to `frontend/actions/admissions.action.ts`
- [ ] **P2-26**: Create waitlist components (WaitlistTable, WaitlistPromoteDialog)
- [ ] **P2-27**: Create letter components (LetterPreview, GenerateLetterButton)
- [ ] **P2-28**: Create offer response components (OfferResponseForm, OfferDetailPanel, DeadlineCountdown)
- [ ] **P2-29**: Create ReminderSettings component
- [ ] **P2-30**: Update decisions management page with waitlist tab and letter buttons
- [ ] **P2-31**: Update applicant dashboard with offer accept/decline UI
- [ ] **P2-32**: Run all tests, verify migration up/down
