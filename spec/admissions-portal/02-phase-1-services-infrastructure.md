# Phase 1: Services & Infrastructure

**Sprint:** 19-20
**Agent:** 2 (Core Services + Infrastructure)
**Depends on:** Nothing (runs parallel with Agent 1 — models)
**Produces:** All services + infrastructure changes needed before endpoints can be built

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 2.1 | Create `get_public_tenant_db()` | `backend/app/api/deps.py` | 0.5d |
| 2.2 | Create Turnstile verification | `backend/app/utils/turnstile.py`, `backend/app/core/config.py` | 0.5d |
| 2.3 | Update PUBLIC_PATH_PREFIXES | `backend/app/middleware/tenant.py`, `backend/app/api/deps.py` | 0.25d |
| 2.4 | Update rate limits | `backend/app/middleware/rate_limit.py`, `backend/app/core/config.py` | 0.25d |
| 2.5 | Update auth permissions | `backend/app/services/auth.py` | 0.25d |
| 2.6 | Add jsonschema dependency | `backend/requirements.txt` | 0.1d |
| 2.7 | Create AdmissionPeriodService | `backend/app/services/admissions/period_service.py` | 1d |
| 2.8 | Create ApplicationService | `backend/app/services/admissions/application_service.py` | 2d |
| 2.9 | Create ApplicationPaymentService | `backend/app/services/admissions/payment_service.py` | 1.5d |
| 2.10 | Create AdmissionNotificationService | `backend/app/services/admissions/notification_service.py` | 0.5d |
| 2.11 | Create EnrollmentService | `backend/app/services/admissions/enrollment_service.py` | 2d |
| 2.12 | Create ExamService | `backend/app/services/admissions/exam_service.py` | 1d |
| 2.13 | Create DecisionService | `backend/app/services/admissions/decision_service.py` | 1d |
| 2.14 | Create ClassPromotionService | `backend/app/services/admissions/promotion_service.py` | 1.5d |
| 2.14b | Create ReturnIntentService | `backend/app/services/admissions/return_intent_service.py` | 0.75d |
| 2.15 | Create services `__init__.py` | `backend/app/services/admissions/__init__.py` | 0.1d |

---

## 2.1 `get_public_tenant_db()` — Public Tenant-Scoped DB Session

**File to modify:** `backend/app/api/deps.py`

This is the key infrastructure piece that enables unauthenticated writes to RLS-protected tables. It reads `tenant_id` from `request.state` (set by `TenantMiddleware` from subdomain) and creates a tenant-scoped session without JWT.

```python
from starlette.requests import Request

async def get_public_tenant_db(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Tenant-scoped DB session for public (unauthenticated) endpoints.

    Used by the Admissions Portal public form endpoints. Reads tenant_id
    from request.state (set by TenantMiddleware from subdomain resolution).

    Unlike get_db(), this does NOT require JWT authentication.
    Unlike get_unscoped_db(), this DOES set RLS tenant context.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="School not found. Please check the URL.",
        )

    async with async_session_maker() as session:
        # Set RLS context — all queries will be filtered by this tenant
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(tenant_id)},
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Clear tenant context to prevent leaking to next connection user
            await session.execute(text("SELECT clear_tenant_context()"))
```

**Important:** The `async_session_maker` reference matches the existing `get_db()` import.

---

## 2.2 Cloudflare Turnstile Verification

**New file:** `backend/app/utils/turnstile.py`

```python
"""
SIMS Plus - Cloudflare Turnstile CAPTCHA Verification

Verifies Turnstile tokens to prevent bot submissions on public forms.
In development (TURNSTILE_SECRET_KEY not set), verification is skipped.
"""

import structlog
import httpx

from app.core.config import settings

logger = structlog.get_logger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str) -> bool:
    """
    Verify a Cloudflare Turnstile token.

    Args:
        token: The turnstile response token from the frontend widget.

    Returns:
        True if the token is valid, False otherwise.
        Returns True in development when TURNSTILE_SECRET_KEY is not configured.
    """
    if not settings.TURNSTILE_SECRET_KEY:
        logger.warning("turnstile_skipped", reason="TURNSTILE_SECRET_KEY not configured")
        return True

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": settings.TURNSTILE_SECRET_KEY,
                    "response": token,
                },
            )
            result = response.json()
            success = result.get("success", False)

            if not success:
                logger.warning(
                    "turnstile_verification_failed",
                    error_codes=result.get("error-codes", []),
                )

            return success

    except httpx.TimeoutException:
        logger.error("turnstile_timeout")
        return False
    except Exception:
        logger.exception("turnstile_error")
        # Fail CLOSED in production — reject submission, applicant can retry
        # Rate limiting alone is not sufficient against distributed attacks
        return False
```

**Config additions** to `backend/app/core/config.py`:

```python
# Cloudflare Turnstile (CAPTCHA)
TURNSTILE_SECRET_KEY: str = ""   # Server-side secret key
TURNSTILE_SITE_KEY: str = ""     # Client-side site key (exposed to frontend)
```

---

## 2.3 Update PUBLIC_PATH_PREFIXES

**IMPORTANT DISTINCTION:** `PUBLIC_PATH_PREFIXES` has different meanings in different files:
- In `middleware/tenant.py`: paths that SKIP subdomain resolution entirely (no tenant context set)
- In `api/deps.py`: paths that skip JWT authentication but still need tenant context

Admissions public endpoints NEED subdomain resolution (to know which school) but DON'T need JWT auth.
The Paystack webhook needs NEITHER subdomain resolution NOR JWT auth (tenant comes from metadata).

**File:** `backend/app/middleware/tenant.py` — add ONLY the webhook path:

```python
PUBLIC_PATH_PREFIXES = (
    # ... existing entries ...
    "/api/v1/admissions/public/webhook/",   # Paystack webhook — tenant from metadata, not subdomain
)
```

**File:** `backend/app/api/deps.py` — add both paths (skips JWT auth):

```python
_PUBLIC_PATH_PREFIXES = (
    # ... existing entries ...
    "/api/v1/admissions/public/",           # Public application form — no JWT, tenant from subdomain
)
```

**Why the difference:** Public form endpoints (`/public/school-info`, `/public/applications`, etc.) still need `TenantMiddleware` to resolve the subdomain to `tenant_id`. Only the webhook path should skip tenant middleware because it extracts `tenant_id` from Paystack payment metadata.

---

## 2.4 Update Rate Limits

**File:** `backend/app/middleware/rate_limit.py`

Add to `ENDPOINT_LIMITS`:

```python
ENDPOINT_LIMITS = {
    # ... existing entries ...
    # Admissions public endpoints — strict limits to prevent abuse
    "/api/v1/admissions/public/applications": ("admissions_submit", "admissions_submit"),
}
```

**File:** `backend/app/core/config.py` — add rate limit settings:

```python
# Admissions rate limits
RATE_LIMIT_ADMISSIONS_SUBMIT_REQUESTS: int = 3
RATE_LIMIT_ADMISSIONS_SUBMIT_WINDOW: int = 60   # 3 submissions per minute per IP

# Admissions daily cap (per-tenant, defense against distributed attacks)
ADMISSIONS_DAILY_CAP_PER_TENANT: int = 500  # Max applications per tenant per day
```

The general default rate limit (100 req/min) applies to other admissions public endpoints (periods, school-info, status check), which is sufficient.

---

## 2.5 Update Auth Permissions

**File:** `backend/app/services/auth.py` — add to `ROLE_PERMISSIONS`:

```python
ROLE_PERMISSIONS = {
    # ... existing ...
    "chain_admin": [
        # ... existing entries ...
        "admissions.*",
    ],
    "school_admin": [
        # ... existing entries ...
        "admissions.*",
    ],
    "academic_head": [
        # ... existing entries ...
        "admissions.read",
        "admissions.review",
    ],
    # Other roles: no admissions access
}
```

---

## 2.6 Add jsonschema Dependency

**File:** `backend/requirements.txt` — add:

```
jsonschema>=4.20.0
```

Used for validating custom form fields against JSON Schema in `ApplicationService.submit()`.

---

## 2.7 AdmissionPeriodService

**File:** `backend/app/services/admissions/period_service.py`

```python
"""
SIMS Plus - Admission Period Service

CRUD operations for admission periods with overlap validation.
"""

import uuid
from datetime import date

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admissions import (
    AdmissionFormConfig,
    AdmissionPeriod,
    AdmissionPeriodStatus,
    Application,
)

logger = structlog.get_logger(__name__)


class AdmissionPeriodError(Exception):
    """Raised when an admission period operation fails."""

    def __init__(self, message: str, code: str = "PERIOD_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class AdmissionPeriodService:
    """Service for managing admission periods."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        name: str,
        academic_year_id: uuid.UUID,
        start_date: date,
        end_date: date,
        application_fee_amount: float | None = None,
        application_fee_required: bool = False,
        entrance_exam_required: bool = False,
        max_applications: int | None = None,
        target_classes: list[uuid.UUID] | None = None,
    ) -> AdmissionPeriod:
        """
        Create a new admission period.

        Validates:
        - start_date < end_date
        - No overlapping non-archived periods for same target classes

        Raises AdmissionPeriodError on validation failure.
        """
        if start_date >= end_date:
            raise AdmissionPeriodError(
                "Start date must be before end date",
                code="INVALID_DATES",
            )

        target_class_list = [str(c) for c in (target_classes or [])]

        # Check for overlapping periods
        await self._validate_no_overlap(
            tenant_id=tenant_id,
            school_id=school_id,
            start_date=start_date,
            end_date=end_date,
            target_classes=target_class_list,
            exclude_period_id=None,
        )

        period = AdmissionPeriod(
            tenant_id=tenant_id,
            school_id=school_id,
            academic_year_id=academic_year_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            status=AdmissionPeriodStatus.DRAFT.value,
            application_fee_amount=application_fee_amount,
            application_fee_required=application_fee_required,
            entrance_exam_required=entrance_exam_required,
            max_applications=max_applications,
            target_classes=target_class_list,
        )
        self.db.add(period)
        await self.db.flush()
        await self.db.refresh(period)
        return period

    async def update_status(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
        new_status: str,
    ) -> AdmissionPeriod:
        """
        Transition period status.

        Valid transitions:
          draft → open
          open → closed
          closed → archived
        """
        valid_transitions = {
            "draft": ["open"],
            "open": ["closed"],
            "closed": ["archived"],
        }

        period = await self._get_period(tenant_id, period_id)
        allowed = valid_transitions.get(period.status, [])

        if new_status not in allowed:
            raise AdmissionPeriodError(
                f"Cannot transition from {period.status} to {new_status}",
                code="INVALID_TRANSITION",
            )

        period.status = new_status
        await self.db.flush()
        await self.db.refresh(period)
        return period

    async def update_form_config(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
        form_schema: dict,
        required_documents: list[str],
    ) -> AdmissionFormConfig:
        """Create or update form configuration for a period."""
        period = await self._get_period(tenant_id, period_id)

        # Validate the schema itself
        from jsonschema import Draft7Validator
        import json

        try:
            Draft7Validator.check_schema(form_schema)
        except Exception as e:
            raise AdmissionPeriodError(
                f"Invalid JSON Schema: {str(e)}", code="INVALID_SCHEMA"
            )

        # Disallow $ref to prevent SSRF during validation
        schema_str = json.dumps(form_schema)
        if "$ref" in schema_str:
            raise AdmissionPeriodError(
                "$ref is not allowed in form schemas", code="INVALID_SCHEMA"
            )

        # Limit nesting depth to prevent stack overflow during validation
        if _json_depth(form_schema) > 5:
            raise AdmissionPeriodError(
                "Schema nesting depth exceeds maximum of 5 levels",
                code="INVALID_SCHEMA",
            )

        result = await self.db.execute(
            select(AdmissionFormConfig).where(
                AdmissionFormConfig.tenant_id == tenant_id,
                AdmissionFormConfig.admission_period_id == period_id,
            )
        )
        config = result.scalar_one_or_none()

        if config:
            config.form_schema = form_schema
            config.required_documents = required_documents
        else:
            config = AdmissionFormConfig(
                tenant_id=tenant_id,
                school_id=period.school_id,
                admission_period_id=period_id,
                form_schema=form_schema,
                required_documents=required_documents,
            )
            self.db.add(config)

        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def get_open_periods(
        self,
        tenant_id: uuid.UUID,
    ) -> list[AdmissionPeriod]:
        """Get all currently open periods (for public endpoint)."""
        today = date.today()
        result = await self.db.execute(
            select(AdmissionPeriod)
            .where(
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.status == AdmissionPeriodStatus.OPEN.value,
                AdmissionPeriod.start_date <= today,
                AdmissionPeriod.end_date >= today,
                AdmissionPeriod.deleted_at.is_(None),
            )
            .order_by(AdmissionPeriod.end_date.asc())
        )
        return list(result.scalars().all())

    async def _validate_no_overlap(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        start_date: date,
        end_date: date,
        target_classes: list[str],
        exclude_period_id: uuid.UUID | None,
    ) -> None:
        """
        Check for overlapping admission periods.

        Two periods overlap if:
        1. Their date ranges intersect
        2. Their target_classes arrays share at least one element
        3. Neither is archived
        """
        if not target_classes:
            return

        query = (
            select(AdmissionPeriod)
            .where(
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.school_id == school_id,
                AdmissionPeriod.status != AdmissionPeriodStatus.ARCHIVED.value,
                AdmissionPeriod.deleted_at.is_(None),
                # Date overlap: existing.start <= new.end AND existing.end >= new.start
                AdmissionPeriod.start_date <= end_date,
                AdmissionPeriod.end_date >= start_date,
            )
        )

        if exclude_period_id:
            query = query.where(AdmissionPeriod.id != exclude_period_id)

        result = await self.db.execute(query)
        existing_periods = result.scalars().all()

        target_set = set(target_classes)
        for existing in existing_periods:
            existing_classes = set(existing.target_classes or [])
            if target_set & existing_classes:
                raise AdmissionPeriodError(
                    f"Admission period overlaps with '{existing.name}' "
                    f"for classes: {target_set & existing_classes}",
                    code="PERIOD_OVERLAP",
                )

    async def _get_period(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> AdmissionPeriod:
        """Fetch period with defense-in-depth tenant check."""
        result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == period_id,
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.deleted_at.is_(None),
            )
        )
        period = result.scalar_one_or_none()
        if not period:
            raise AdmissionPeriodError("Period not found", code="NOT_FOUND")
        return period
```

---

## 2.8 ApplicationService

**File:** `backend/app/services/admissions/application_service.py`

```python
"""
SIMS Plus - Application Service

Handles application submission, status transitions, search, and waivers.
"""

import secrets
import uuid
from datetime import UTC, datetime

import structlog
from jsonschema import ValidationError, validate
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.admissions import (
    AdmissionFormConfig,
    AdmissionPeriod,
    AdmissionPeriodStatus,
    Application,
    ApplicationGuardian,
    AdmissionApplicationStatus,
    ApplicationStatusHistory,
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
)
from app.utils.turnstile import verify_turnstile

logger = structlog.get_logger(__name__)


class ApplicationServiceError(Exception):
    def __init__(self, message: str, code: str = "APPLICATION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        turnstile_token: str,
        admission_period_id: uuid.UUID,
        applicant_first_name: str,
        applicant_last_name: str,
        applicant_other_names: str | None,
        date_of_birth: str,  # ISO date
        gender: str,
        nationality: str | None,
        target_class_id: uuid.UUID,
        custom_fields: dict,
        previous_school: str | None,
        medical_info: str | None,
        guardians: list[dict],
    ) -> Application:
        """
        Submit a new application (public endpoint).

        Steps:
        1. Verify Turnstile token
        2. Validate period is open and has capacity
        3. Validate custom_fields against form_schema (if configured)
        4. Generate tracking_code
        5. Create Application + ApplicationGuardian records
        6. Create initial status history entry
        7. If fee not required, auto-transition to SUBMITTED

        Raises ApplicationServiceError on failure.
        """
        # 1. Turnstile verification
        if not await verify_turnstile(turnstile_token):
            raise ApplicationServiceError(
                "CAPTCHA verification failed. Please try again.",
                code="CAPTCHA_FAILED",
            )

        # 1b. Per-tenant daily submission cap (defense against distributed attacks)
        daily_count = await self._get_daily_submission_count(tenant_id)
        if daily_count >= settings.ADMISSIONS_DAILY_CAP_PER_TENANT:
            raise ApplicationServiceError(
                "This school has reached the maximum number of applications for today. "
                "Please try again tomorrow.",
                code="DAILY_CAP_EXCEEDED",
            )

        # 2. Period validation
        period = await self._get_open_period(tenant_id, admission_period_id)

        if period.max_applications:
            count = await self._count_applications(tenant_id, admission_period_id)
            if count >= period.max_applications:
                raise ApplicationServiceError(
                    "This admission period has reached its application limit.",
                    code="PERIOD_FULL",
                )

        # 3. Validate custom fields against form schema
        await self._validate_custom_fields(tenant_id, admission_period_id, custom_fields)

        # 4. Generate tracking code
        tracking_code = secrets.token_urlsafe(48)

        # 5. Determine initial status
        # If fee not required or waived, go straight to SUBMITTED
        initial_status = AdmissionApplicationStatus.DRAFT.value
        submitted_at = None

        if not period.application_fee_required:
            initial_status = AdmissionApplicationStatus.SUBMITTED.value
            submitted_at = datetime.now(UTC)

        # 6. Create application
        application = Application(
            tenant_id=tenant_id,
            school_id=school_id,
            admission_period_id=admission_period_id,
            tracking_code=tracking_code,
            applicant_first_name=applicant_first_name.strip(),
            applicant_last_name=applicant_last_name.strip(),
            applicant_other_names=applicant_other_names.strip() if applicant_other_names else None,
            date_of_birth=date_of_birth,
            gender=gender.lower(),
            nationality=nationality,
            target_class_id=target_class_id,
            status=initial_status,
            custom_fields=custom_fields,
            previous_school=previous_school,
            medical_info=medical_info,
            submitted_at=submitted_at,
        )
        self.db.add(application)
        await self.db.flush()

        # 7. Create guardian records
        if not guardians:
            raise ApplicationServiceError(
                "At least one guardian is required.",
                code="NO_GUARDIANS",
            )

        for g_data in guardians:
            guardian = ApplicationGuardian(
                tenant_id=tenant_id,
                application_id=application.id,
                first_name=g_data["first_name"].strip(),
                last_name=g_data["last_name"].strip(),
                phone=g_data["phone"].strip(),
                email=g_data.get("email", "").strip() or None,
                relationship=g_data["relationship"],
                is_primary=g_data.get("is_primary", False),
                occupation=g_data.get("occupation"),
                address=g_data.get("address"),
            )
            self.db.add(guardian)

        # 8. Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application.id,
            from_status=None,
            to_status=initial_status,
            changed_by=None,  # Public action
            reason="Application submitted via public form",
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "application_submitted",
            application_id=str(application.id),
            tracking_code=tracking_code,
            tenant_id=str(tenant_id),
            period_id=str(admission_period_id),
        )

        return application

    async def transition_status(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: str,
        changed_by: uuid.UUID,
        reason: str | None = None,
    ) -> Application:
        """
        Transition application to a new status.

        Validates against VALID_TRANSITIONS dict.
        Creates status history record.
        """
        application = await self._get_application(tenant_id, application_id)
        current = AdmissionApplicationStatus(application.status)
        target = AdmissionApplicationStatus(new_status)

        allowed = VALID_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise ApplicationServiceError(
                f"Cannot transition from {current.value} to {target.value}",
                code="INVALID_TRANSITION",
            )

        # Gate checks
        if target == AdmissionApplicationStatus.SUBMITTED:
            # Fee gate: must be paid or waived
            if not application.fee_waived:
                has_payment = await self._has_completed_payment(tenant_id, application_id)
                if not has_payment:
                    raise ApplicationServiceError(
                        "Application fee must be paid before submission",
                        code="FEE_REQUIRED",
                    )

        if target == AdmissionApplicationStatus.OFFERED and current == AdmissionApplicationStatus.SHORTLISTED:
            # Exam gate (only when going directly from shortlisted)
            if not application.exam_waived:
                raise ApplicationServiceError(
                    "Entrance exam not waived. Schedule exam first.",
                    code="EXAM_REQUIRED",
                )

        old_status = application.status
        application.status = target.value

        if target == AdmissionApplicationStatus.SUBMITTED and not application.submitted_at:
            application.submitted_at = datetime.now(UTC)

        # Record history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application_id,
            from_status=old_status,
            to_status=target.value,
            changed_by=changed_by,
            reason=reason,
        )
        self.db.add(history)

        await self.db.flush()
        await self.db.refresh(application)
        return application

    async def get_by_tracking_code(
        self,
        tenant_id: uuid.UUID,
        tracking_code: str,
    ) -> dict:
        """
        Public status lookup. Returns MINIMAL data only — no PII.
        """
        result = await self.db.execute(
            select(Application).where(
                Application.tenant_id == tenant_id,
                Application.tracking_code == tracking_code,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise ApplicationServiceError("Application not found", code="NOT_FOUND")

        return {
            "status": app.status,
            "applicant_first_name": app.applicant_first_name,
            "submitted_at": app.submitted_at,
            "last_updated_at": app.updated_at,
        }

    async def list_applications(
        self,
        tenant_id: uuid.UUID,
        *,
        status: str | None = None,
        admission_period_id: uuid.UUID | None = None,
        target_class_id: uuid.UUID | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Application], int]:
        """
        Admin: list applications with filters and pagination.
        Returns (applications, total_count).
        """
        query = (
            select(Application)
            .where(
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )

        if status:
            query = query.where(Application.status == status)
        if admission_period_id:
            query = query.where(Application.admission_period_id == admission_period_id)
        if target_class_id:
            query = query.where(Application.target_class_id == target_class_id)
        if search:
            from app.utils.sanitize import escape_ilike
            escaped = escape_ilike(search)
            search_term = f"%{escaped}%"
            query = query.where(
                or_(
                    Application.applicant_first_name.ilike(search_term),
                    Application.applicant_last_name.ilike(search_term),
                    Application.tracking_code.ilike(search_term),
                )
            )

        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Paginate
        query = (
            query
            .order_by(Application.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def waive_fee(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """Admin: waive application fee."""
        app = await self._get_application(tenant_id, application_id)
        app.fee_waived = True

        # If app is in DRAFT and fee was the only blocker, transition to SUBMITTED
        if app.status == AdmissionApplicationStatus.DRAFT.value:
            app.status = AdmissionApplicationStatus.SUBMITTED.value
            app.submitted_at = datetime.now(UTC)
            history = ApplicationStatusHistory(
                tenant_id=tenant_id,
                application_id=application_id,
                from_status=AdmissionApplicationStatus.DRAFT.value,
                to_status=AdmissionApplicationStatus.SUBMITTED.value,
                changed_by=None,
                reason="Fee waived — auto-submitted",
            )
            self.db.add(history)

        await self.db.flush()
        await self.db.refresh(app)
        return app

    async def waive_exam(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Application:
        """Admin: waive entrance exam requirement."""
        app = await self._get_application(tenant_id, application_id)
        app.exam_waived = True
        await self.db.flush()
        await self.db.refresh(app)
        return app

    # ---- Private helpers ----

    async def _get_open_period(
        self, tenant_id: uuid.UUID, period_id: uuid.UUID
    ) -> AdmissionPeriod:
        from datetime import date as date_type

        result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == period_id,
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.status == AdmissionPeriodStatus.OPEN.value,
                AdmissionPeriod.deleted_at.is_(None),
            )
        )
        period = result.scalar_one_or_none()
        if not period:
            raise ApplicationServiceError(
                "Admission period not found or not open",
                code="PERIOD_NOT_OPEN",
            )

        today = date_type.today()
        if today < period.start_date or today > period.end_date:
            raise ApplicationServiceError(
                "Admission period is not currently accepting applications",
                code="PERIOD_NOT_ACTIVE",
            )
        return period

    async def _validate_custom_fields(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
        custom_fields: dict,
    ) -> None:
        result = await self.db.execute(
            select(AdmissionFormConfig).where(
                AdmissionFormConfig.tenant_id == tenant_id,
                AdmissionFormConfig.admission_period_id == period_id,
            )
        )
        config = result.scalar_one_or_none()
        if config and config.form_schema:
            try:
                validate(instance=custom_fields, schema=config.form_schema)
            except ValidationError as e:
                raise ApplicationServiceError(
                    f"Invalid custom fields: {e.message}",
                    code="VALIDATION_ERROR",
                )

    async def _get_application(
        self, tenant_id: uuid.UUID, app_id: uuid.UUID
    ) -> Application:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise ApplicationServiceError("Application not found", code="NOT_FOUND")
        return app

    async def _count_applications(
        self, tenant_id: uuid.UUID, period_id: uuid.UUID
    ) -> int:
        result = await self.db.execute(
            select(func.count(Application.id)).where(
                Application.tenant_id == tenant_id,
                Application.admission_period_id == period_id,
                Application.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def _get_daily_submission_count(self, tenant_id: uuid.UUID) -> int:
        """Count today's submissions for this tenant (Redis-backed with DB fallback)."""
        today = datetime.now(UTC).date()
        result = await self.db.execute(
            select(func.count(Application.id)).where(
                Application.tenant_id == tenant_id,
                func.date(Application.created_at) == today,
                Application.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    async def _has_completed_payment(
        self, tenant_id: uuid.UUID, app_id: uuid.UUID
    ) -> bool:
        from app.models.admissions import ApplicationPayment

        result = await self.db.execute(
            select(func.count(ApplicationPayment.id)).where(
                ApplicationPayment.tenant_id == tenant_id,
                ApplicationPayment.application_id == app_id,
                ApplicationPayment.status == "completed",
            )
        )
        return (result.scalar() or 0) > 0
```

---

## 2.9 ApplicationPaymentService

**File:** `backend/app/services/admissions/payment_service.py`

Adapts the Paystack pattern from `services/payment/online_payment.py`.

```python
"""
SIMS Plus - Application Payment Service

Handles Paystack payment initialization and webhook processing
for application fees. Separate from the main payment system since
applicants are not yet students.
"""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.admissions import Application, ApplicationPayment, AdmissionApplicationStatus

logger = structlog.get_logger(__name__)

PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"


class ApplicationPaymentError(Exception):
    def __init__(self, message: str, code: str = "PAYMENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ApplicationPaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_payment(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_id: uuid.UUID,
        tracking_code: str,
    ) -> dict:
        """
        Initialize Paystack payment for application fee.

        Returns: { authorization_url, reference, amount }
        """
        # Get application + period
        app = await self._get_application(tenant_id, application_id)

        if app.fee_waived:
            raise ApplicationPaymentError("Application fee has been waived", code="FEE_WAIVED")

        # Get fee amount from period
        from app.models.admissions import AdmissionPeriod

        period_result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == app.admission_period_id,
                AdmissionPeriod.tenant_id == tenant_id,
            )
        )
        period = period_result.scalar_one_or_none()
        if not period or not period.application_fee_amount:
            raise ApplicationPaymentError("No fee configured for this period", code="NO_FEE")

        amount_pesewas = int(period.application_fee_amount * 100)

        # Get primary guardian email for Paystack
        from app.models.admissions import ApplicationGuardian

        guardian_result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.is_primary == True,
            )
        )
        guardian = guardian_result.scalar_one_or_none()
        email = guardian.email if guardian and guardian.email else f"{tracking_code}@applicant.simsplus.io"

        # Create payment record
        payment = ApplicationPayment(
            tenant_id=tenant_id,
            application_id=application_id,
            amount=period.application_fee_amount,
            currency="GHS",
            status="pending",
        )
        self.db.add(payment)
        await self.db.flush()

        # Call Paystack
        callback_url = f"https://{settings.FRONTEND_DOMAIN}/apply/pay/callback"

        payload = {
            "email": email,
            "amount": amount_pesewas,
            "currency": "GHS",
            "callback_url": callback_url,
            "metadata": {
                "application_id": str(application_id),
                "payment_id": str(payment.id),
                "tenant_id": str(tenant_id),
                "school_id": str(school_id),
                "tracking_code": tracking_code,
                "context": "application_fee",
                "custom_fields": [
                    {
                        "display_name": "Application",
                        "variable_name": "tracking_code",
                        "value": tracking_code,
                    }
                ],
            },
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                PAYSTACK_INIT_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code != 200:
            logger.error("paystack_init_failed", status=response.status_code)
            raise ApplicationPaymentError("Payment initialization failed", code="INIT_FAILED")

        data = response.json().get("data", {})
        reference = data.get("reference")

        payment.provider_reference = reference
        await self.db.flush()

        return {
            "authorization_url": data.get("authorization_url"),
            "reference": reference,
            "amount": float(period.application_fee_amount),
        }

    async def handle_webhook(
        self,
        db: AsyncSession,
        payload_body: bytes,
        signature: str,
    ) -> None:
        """
        Process Paystack webhook for application payments.

        Uses UnscopedDatabaseSession — manually sets tenant context
        from webhook metadata.

        Security: Verifies HMAC-SHA512 signature before processing.
        """
        # 1. Verify signature
        # Prefer dedicated webhook secret, fall back to API secret key
        secret_key = getattr(settings, "PAYSTACK_WEBHOOK_SECRET", None) or settings.PAYSTACK_SECRET_KEY
        secret = secret_key.encode()
        expected = hmac.new(secret, payload_body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ApplicationPaymentError("Invalid webhook signature", code="INVALID_SIGNATURE")

        # 2. Parse payload
        import json

        payload = json.loads(payload_body)
        event = payload.get("event")
        if event != "charge.success":
            return  # Ignore non-success events

        data = payload.get("data", {})
        metadata = data.get("metadata", {})

        # Only process application_fee context
        if metadata.get("context") != "application_fee":
            return

        # 3. Extract and validate tenant_id
        webhook_tenant_id = metadata.get("tenant_id")
        payment_id = metadata.get("payment_id")
        reference = data.get("reference")

        if not all([webhook_tenant_id, payment_id, reference]):
            logger.warning("webhook_missing_metadata")
            return

        try:
            uuid.UUID(webhook_tenant_id)
            uuid.UUID(payment_id)
        except ValueError:
            logger.warning("webhook_invalid_uuid")
            return

        # 4. Look up payment by provider_reference (UNIQUE, no tenant context needed)
        result = await db.execute(
            select(ApplicationPayment).where(
                ApplicationPayment.provider_reference == reference,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            logger.warning("webhook_payment_not_found", reference=reference)
            return

        # 5. Cross-validate tenant_id from metadata against DB record
        if str(payment.tenant_id) != webhook_tenant_id:
            logger.error(
                "webhook_tenant_mismatch",
                expected=str(payment.tenant_id),
                received=webhook_tenant_id,
            )
            return

        # 6. Set tenant context with VALIDATED tenant_id
        await db.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(payment.tenant_id)},
        )

        if payment.status == "completed":
            return  # Already processed — idempotent

        payment.status = "completed"
        payment.paid_at = datetime.now(UTC)
        payment.provider_reference = reference
        payment.payment_method = data.get("channel", "unknown")
        payment.metadata = {
            "paystack_reference": reference,
            "channel": data.get("channel"),
            "ip_address": data.get("ip_address"),
        }

        # 7. If application is in DRAFT, transition to SUBMITTED
        app_result = await db.execute(
            select(Application).where(
                Application.id == payment.application_id,
                Application.tenant_id == payment.tenant_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if app and app.status == AdmissionApplicationStatus.DRAFT.value:
            from app.models.admissions import ApplicationStatusHistory

            app.status = AdmissionApplicationStatus.SUBMITTED.value
            app.submitted_at = datetime.now(UTC)

            history = ApplicationStatusHistory(
                tenant_id=payment.tenant_id,
                application_id=app.id,
                from_status=AdmissionApplicationStatus.DRAFT.value,
                to_status=AdmissionApplicationStatus.SUBMITTED.value,
                changed_by=None,
                reason="Application fee payment confirmed via Paystack",
            )
            db.add(history)

        await db.commit()

        logger.info(
            "application_payment_completed",
            payment_id=payment_id,
            application_id=str(payment.application_id),
            reference=reference,
        )

    async def _get_application(
        self, tenant_id: uuid.UUID, app_id: uuid.UUID
    ) -> Application:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise ApplicationPaymentError("Application not found", code="NOT_FOUND")
        return app
```

---

## 2.10 AdmissionNotificationService

**File:** `backend/app/services/admissions/notification_service.py`

```python
"""
SIMS Plus - Admission Notification Service

Sends SMS and email notifications to applicant guardians.
Uses SMSService and EmailComposeService directly (NOT NotificationDispatcher,
which requires a user_id — applicants don't have platform accounts).
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import Application, ApplicationGuardian

logger = structlog.get_logger(__name__)

# Notification templates — use $variable syntax for safe_substitute()
TEMPLATES = {
    "submitted": {
        "sms": "Your application to $school has been received. Tracking code: $tracking_code. Keep this code to check your application status.",
        "email_subject": "Application Received — $school",
        "email_body": """Dear $guardian_name,

Your application for $applicant_name to $school has been received successfully.

Tracking Code: $tracking_code

You can check the application status at any time using this tracking code at $status_url.

Thank you for your interest in $school.
""",
    },
    "exam_scheduled": {
        "sms": "Entrance exam for $applicant_name at $school: $exam_date at $venue. Please arrive 30 minutes early.",
        "email_subject": "Entrance Exam Scheduled — $school",
        "email_body": """Dear $guardian_name,

An entrance exam has been scheduled for $applicant_name's application to $school.

Date: $exam_date
Time: $exam_time
Venue: $venue

Please ensure the candidate arrives at least 30 minutes before the exam.

Tracking Code: $tracking_code
""",
    },
    "offered": {
        "sms": "Congratulations! $applicant_name has been offered admission to $school. Please respond by $deadline. Check status with code: $tracking_code",
        "email_subject": "Admission Offer — $school",
        "email_body": """Dear $guardian_name,

We are pleased to inform you that $applicant_name has been offered admission to $school.

Please respond to this offer by $deadline.

To accept or for more details, please contact the school or check your application status using tracking code: $tracking_code

Congratulations!
""",
    },
    "enrolled": {
        "sms": "Welcome! $applicant_name is now enrolled at $school. Student ID: $student_id. Check your email for next steps.",
        "email_subject": "Enrollment Confirmed — Welcome to $school!",
        "email_body": """Dear $guardian_name,

$applicant_name has been successfully enrolled at $school.

Student ID: $student_id

Next steps:
1. Complete any outstanding fee payments
2. Submit required documents if not already done
3. Check the school portal for orientation details

Welcome to the $school family!
""",
    },
}


class AdmissionNotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_status_change(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: str,
        extra_context: dict | None = None,
    ) -> None:
        """
        Send notification to primary guardian on status change.

        Only sends for statuses that have templates defined.
        Failures are logged but do not raise — best effort.
        """
        template = TEMPLATES.get(new_status)
        if not template:
            return  # No notification for this status

        # Get application + primary guardian
        app_result = await self.db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.tenant_id == tenant_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if not app:
            return

        guardian_result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.is_primary == True,
            )
        )
        guardian = guardian_result.scalar_one_or_none()
        if not guardian:
            # Fallback: get first guardian
            guardian_result = await self.db.execute(
                select(ApplicationGuardian).where(
                    ApplicationGuardian.application_id == application_id,
                    ApplicationGuardian.tenant_id == tenant_id,
                ).limit(1)
            )
            guardian = guardian_result.scalar_one_or_none()

        if not guardian:
            logger.warning("no_guardian_for_notification", application_id=str(application_id))
            return

        # Build context
        context = {
            "school": "the school",  # TODO: Fetch school name
            "applicant_name": f"{app.applicant_first_name} {app.applicant_last_name}",
            "guardian_name": f"{guardian.first_name} {guardian.last_name}",
            "tracking_code": app.tracking_code,
            "status_url": f"https://apply.simsplus.io/status",
            **(extra_context or {}),
        }

        # Send SMS
        if guardian.phone:
            try:
                from string import Template as StringTemplate
                from app.services.messaging.sms_service import SMSService

                sms_service = SMSService(self.db)
                sms_text = StringTemplate(template["sms"]).safe_substitute(context)
                await sms_service.send_sms(
                    tenant_id=tenant_id,
                    school_id=app.school_id,
                    recipient_phone=guardian.phone,
                    message=sms_text[:160],
                    sent_by=None,
                )
            except Exception:
                logger.exception("admission_sms_failed", application_id=str(application_id))

        # Send email
        if guardian.email:
            try:
                from string import Template as StringTemplate
                from app.services.messaging.email_compose_service import EmailComposeService

                email_service = EmailComposeService(self.db)
                await email_service.send_email(
                    tenant_id=tenant_id,
                    school_id=app.school_id,
                    recipient_email=guardian.email,
                    recipient_name=f"{guardian.first_name} {guardian.last_name}",
                    subject=StringTemplate(template["email_subject"]).safe_substitute(context),
                    body=StringTemplate(template["email_body"]).safe_substitute(context),
                    sent_by=None,
                )
            except Exception:
                logger.exception("admission_email_failed", application_id=str(application_id))
```

---

## 2.11 EnrollmentService

**File:** `backend/app/services/admissions/enrollment_service.py`

```python
"""
SIMS Plus - Enrollment Service

Atomic conversion of accepted applicants into student records.
This is the most critical service — touches 6+ tables in one transaction.
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    Application,
    ApplicationGuardian,
    AdmissionApplicationStatus,
    ApplicationStatusHistory,
)

logger = structlog.get_logger(__name__)


class EnrollmentError(Exception):
    def __init__(self, message: str, code: str = "ENROLLMENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EnrollmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def enroll(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_id: uuid.UUID,
        enrolled_by: uuid.UUID,
    ) -> dict:
        """
        Convert accepted applicant to student record.

        Steps:
        1. Validate application status=ACCEPTED, converted_student_id=NULL
        2. Deduplicate guardians (by email OR phone within tenant)
        3. Create Student record
        4. Create StudentGuardian junction records
        5. Generate first invoice (if fee structure exists)
        6. Update application status=ENROLLED + converted_student_id
        7. Log status change
        8. Send notification
        9. Create parent User account (if guardian has email)

        All within single transaction (flush() not commit()).

        Returns: { application_id, student_id, student_number, guardian_count, invoice_id }
        """
        # 1. Validate
        app = await self._get_application(tenant_id, application_id)

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                f"Application must be in ACCEPTED status (current: {app.status})",
                code="INVALID_STATUS",
            )

        if app.converted_student_id is not None:
            # Idempotency — already enrolled
            return {
                "application_id": str(application_id),
                "student_id": str(app.converted_student_id),
                "student_number": None,
                "guardian_count": 0,
                "invoice_id": None,
                "already_enrolled": True,
            }

        # Get guardians
        guardian_result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.deleted_at.is_(None),
            )
        )
        app_guardians = list(guardian_result.scalars().all())

        # Determine class — use decision's offered_class if available
        from app.models.admissions import AdmissionDecision

        decision_result = await self.db.execute(
            select(AdmissionDecision).where(
                AdmissionDecision.application_id == application_id,
                AdmissionDecision.tenant_id == tenant_id,
            )
        )
        decision = decision_result.scalar_one_or_none()
        class_id = decision.offered_class_id if decision and decision.offered_class_id else app.target_class_id

        # 2-4. Create guardians + student + junction records
        from app.models.student import Guardian, Student, StudentGuardian

        guardian_ids = []
        for ag in app_guardians:
            existing = await self._find_existing_guardian(tenant_id, ag.email, ag.phone)
            if existing:
                guardian_ids.append((existing.id, ag.relationship, ag.is_primary))
            else:
                new_guardian = Guardian(
                    tenant_id=tenant_id,
                    first_name=ag.first_name,
                    last_name=ag.last_name,
                    phone=ag.phone,
                    email=ag.email,
                    occupation=ag.occupation,
                    address=ag.address,
                )
                self.db.add(new_guardian)
                await self.db.flush()
                guardian_ids.append((new_guardian.id, ag.relationship, ag.is_primary))

        # 3. Create student
        # Fetch school for student_id_prefix
        from app.models.school import School

        school_result = await self.db.execute(
            select(School).where(School.id == school_id, School.tenant_id == tenant_id)
        )
        school = school_result.scalar_one()

        # Use existing StudentService pattern for ID generation
        from app.services.student.student_service import StudentService

        student_service = StudentService(self.db)
        # Actual signature: generate_student_id(tenant_id, prefix="STU")
        # The prefix comes from school.student_id_prefix
        student_number = await student_service.generate_student_id(
            tenant_id, prefix=school.student_id_prefix or "STU"
        )

        student = Student(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=student_number,
            first_name=app.applicant_first_name,
            last_name=app.applicant_last_name,
            other_names=app.applicant_other_names,
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            nationality=app.nationality,
            class_id=class_id,
            status="active",
            previous_school=app.previous_school,
            medical_info=app.medical_info,
        )
        self.db.add(student)
        await self.db.flush()

        # 4. Junction records
        for gid, relationship, is_primary in guardian_ids:
            sg = StudentGuardian(
                tenant_id=tenant_id,
                student_id=student.id,
                guardian_id=gid,
                relationship=relationship,
                is_primary=is_primary,
            )
            self.db.add(sg)

        # 5. Generate invoice
        # NOTE: InvoiceService.generate_for_student() is a new method that must be
        # added to backend/app/services/finance/invoice_service.py. It wraps the
        # existing bulk invoice generation logic for a single student:
        #
        # async def generate_for_student(
        #     self, student_id: UUID, class_id: UUID, academic_year_id: UUID,
        #     tenant_id: UUID, school_id: UUID,
        # ) -> Invoice | None:
        #     """Generate invoice for a single student based on fee structure.
        #     Returns None if no fee structure exists for the class."""
        invoice_id = None
        try:
            from app.services.finance.invoice_service import InvoiceService

            invoice_service = InvoiceService(self.db)
            invoice = await invoice_service.generate_for_student(
                tenant_id=tenant_id,
                school_id=school_id,
                student_id=student.id,
                class_id=class_id,
            )
            if invoice:
                invoice_id = str(invoice.id)
        except Exception as e:
            # If fee structure exists for this class, invoice failure is a hard error
            # The enrollment should NOT proceed without the invoice
            # If no fee structure exists for the target class,
            # generate_for_student() returns None (not an error).
            # The exception handler only fires on actual failures.
            logger.error(
                "enrollment_invoice_failed",
                application_id=str(application_id),
                error=str(e),
            )
            raise EnrollmentError(
                f"Invoice generation failed: {str(e)}. Enrollment rolled back.",
                code="INVOICE_GENERATION_FAILED",
            )

        # 6. Update application
        app.status = AdmissionApplicationStatus.ENROLLED.value
        app.converted_student_id = student.id

        # 7. Status history
        history = ApplicationStatusHistory(
            tenant_id=tenant_id,
            application_id=application_id,
            from_status=AdmissionApplicationStatus.ACCEPTED.value,
            to_status=AdmissionApplicationStatus.ENROLLED.value,
            changed_by=enrolled_by,
            reason="Applicant enrolled as student",
        )
        self.db.add(history)

        await self.db.flush()

        # 8. Notification (best effort)
        try:
            from app.services.admissions.notification_service import AdmissionNotificationService

            notifier = AdmissionNotificationService(self.db)
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application_id,
                new_status="enrolled",
                extra_context={"student_id": student_number},
            )
        except Exception:
            logger.exception("enrollment_notification_failed")

        # 9. Create parent account (best effort)
        for ag in app_guardians:
            if ag.email:
                try:
                    from app.services.parent.parent_onboarding import ParentOnboardingService

                    onboarding = ParentOnboardingService(self.db)
                    await onboarding.create_parent_account(
                        tenant_id=tenant_id,
                        email=ag.email,
                        first_name=ag.first_name,
                        last_name=ag.last_name,
                        phone=ag.phone,
                    )
                except Exception:
                    logger.warning("parent_account_creation_skipped", email=ag.email)

        logger.info(
            "applicant_enrolled",
            application_id=str(application_id),
            student_id=str(student.id),
            student_number=student_number,
        )

        return {
            "application_id": str(application_id),
            "student_id": str(student.id),
            "student_number": student_number,
            "guardian_count": len(guardian_ids),
            "invoice_id": invoice_id,
            "already_enrolled": False,
        }

    async def bulk_enroll(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_ids: list[uuid.UUID],
        enrolled_by: uuid.UUID,
    ) -> dict:
        """
        Bulk enroll multiple accepted applicants.

        Each enrollment runs in its own savepoint for partial success.
        Returns: { succeeded: [...], failed: [...] }
        """
        succeeded = []
        failed = []

        for app_id in application_ids:
            try:
                async with self.db.begin_nested():
                    result = await self.enroll(
                        tenant_id=tenant_id,
                        school_id=school_id,
                        application_id=app_id,
                        enrolled_by=enrolled_by,
                    )
                    succeeded.append(result)
            except Exception as e:
                error_msg = str(e) if isinstance(e, EnrollmentError) else "Enrollment failed"
                failed.append({
                    "application_id": str(app_id),
                    "error": error_msg,
                })

        return {"succeeded": succeeded, "failed": failed}

    async def _find_existing_guardian(
        self,
        tenant_id: uuid.UUID,
        email: str | None,
        phone: str,
    ):
        """
        Deduplicate: find existing guardian by email OR phone within tenant.
        """
        from app.models.student import Guardian

        if email:
            result = await self.db.execute(
                select(Guardian).where(
                    Guardian.tenant_id == tenant_id,
                    Guardian.email == email,
                    Guardian.deleted_at.is_(None),
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        # Fallback: match by phone
        result = await self.db.execute(
            select(Guardian).where(
                Guardian.tenant_id == tenant_id,
                Guardian.phone == phone,
                Guardian.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_application(
        self, tenant_id: uuid.UUID, app_id: uuid.UUID
    ) -> Application:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise EnrollmentError("Application not found", code="NOT_FOUND")
        return app
```

---

## 2.12–2.14 Remaining Services (Skeleton)

### ExamService (`exam_service.py`)

```python
class EntranceExamServiceError(Exception):
    def __init__(self, message: str, code: str = "EXAM_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EntranceExamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_exam(self, tenant_id, school_id, *, admission_period_id, name, exam_date, start_time, end_time, venue, capacity, instructions) -> EntranceExam:
        """Create entrance exam session. Validates period exists and is not archived."""

    async def register_applicants(self, tenant_id, exam_id, application_ids: list[uuid.UUID]) -> dict:
        """
        Register applicants for exam. Checks:
        - Exam capacity not exceeded
        - Applications are in SHORTLISTED status
        - Not already registered
        Transitions application status to EXAM_SCHEDULED.
        Returns: { registered_count, already_registered_count }
        """

    async def record_results(self, tenant_id, exam_id, results: list[dict], scored_by: uuid.UUID) -> int:
        """
        Enter exam results. Each result: { application_id, score, max_score, grade, passed, remarks }
        Creates EntranceExamResult records.
        Transitions application status to EXAM_COMPLETED.
        Sends notification via AdmissionNotificationService.
        Returns: count of results recorded.
        """

    async def mark_attendance(self, tenant_id, exam_id, attendees: list[uuid.UUID]) -> int:
        """Mark which registered applicants attended. Returns count updated."""
```

### DecisionService (`decision_service.py`)

```python
class DecisionServiceError(Exception):
    def __init__(self, message: str, code: str = "DECISION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class DecisionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def decide(self, tenant_id, *, application_id, decision_type, decided_by, offered_class_id=None, conditions=None, response_deadline=None) -> AdmissionDecision:
        """
        Make admission decision for single application.
        Creates AdmissionDecision record.
        Transitions application status:
          accepted → OFFERED (with response_deadline)
          rejected → REJECTED
          waitlisted → WAITLISTED
          deferred → DEFERRED
        Sends notification.
        """

    async def bulk_decide(self, tenant_id, *, application_ids, decision_type, decided_by, offered_class_id=None, conditions=None, response_deadline=None) -> dict:
        """
        Bulk decide. Each in own savepoint.
        Returns: { succeeded: [...], failed: [...] }
        """
```

### ClassPromotionService (`promotion_service.py`)

```python
class ClassPromotionError(Exception):
    def __init__(self, message: str, code: str = "PROMOTION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ClassPromotionService:
    """
    Manages end-of-year class promotion operations.

    Workflow:
    1. Admin creates a promotion batch (draft)
    2. System generates preview entries for all active students
       in the school (default action: promote to next class,
       terminal class students: graduate)
    3. Admin reviews and adjusts individual entries (repeat/withdraw)
    4. Admin executes the batch — students are re-assigned to new classes
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_batch(self, tenant_id, school_id, *, source_academic_year_id, target_academic_year_id, name) -> ClassPromotion:
        """
        Create promotion batch in draft status.
        Validates: both academic years exist, source != target,
        no existing batch for same source/target combination.
        """

    async def generate_preview(self, tenant_id, promotion_id) -> ClassPromotion:
        """
        Generate ClassPromotionEntry records for all active students.
        Default logic:
        - Students in non-terminal classes → action=promote, target_class=next class
        - Students in terminal class (e.g., JHS 3, SHS 3) → action=graduate, target_class=null
        - Sets batch status to 'preview'
        Requires: class ordering (Class.order_index) to determine "next class"
        """

    async def update_entry(self, tenant_id, entry_id, *, action, target_class_id=None, target_section_id=None, reason=None) -> ClassPromotionEntry:
        """
        Admin adjusts individual student's action.
        Validates: batch is in 'preview' status (not yet executed).
        """

    async def bulk_update_entries(self, tenant_id, promotion_id, updates: list[dict]) -> dict:
        """
        Bulk update entries. Each update: {entry_id, action, target_class_id?, reason?}
        Returns: { succeeded: int, failed: [{entry_id, error}] }
        """

    async def execute_batch(self, tenant_id, promotion_id, executed_by) -> ClassPromotion:
        """
        Execute the promotion batch. For each entry:
        - promote: Update student's class_id + section assignment
        - repeat: Keep student in same class (update section if specified)
        - graduate: Set student status to 'graduated'
        - withdraw: Set student status to 'withdrawn'

        Each entry processed in its own savepoint (partial success).
        Updates batch counts and sets status to 'completed'.

        Uses SELECT FOR UPDATE to prevent concurrent execution of the same batch.
        """
        # Use SELECT FOR UPDATE to prevent concurrent execution of the same batch
        batch = await self._get_batch_for_update(tenant_id, promotion_id)

    async def _get_batch_for_update(
        self, tenant_id: uuid.UUID, promotion_id: uuid.UUID
    ) -> ClassPromotion:
        """Fetch batch with row-level lock to prevent concurrent execution."""
        result = await self.db.execute(
            select(ClassPromotion)
            .where(
                ClassPromotion.id == promotion_id,
                ClassPromotion.tenant_id == tenant_id,
                ClassPromotion.deleted_at.is_(None),
            )
            .with_for_update()
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise ClassPromotionError("Promotion batch not found", code="NOT_FOUND")
        return batch

    async def get_batch(self, tenant_id, promotion_id) -> ClassPromotion:
        """Get batch with summary stats."""

    async def list_batches(self, tenant_id, school_id, *, page=1, page_size=20) -> tuple[list, int]:
        """List promotion batches for a school."""

    async def get_entries(self, tenant_id, promotion_id, *, source_class_id=None, action=None, page=1, page_size=50) -> tuple[list, int]:
        """List entries with optional filters."""
```

### ReturnIntentService (`return_intent_service.py`)

```python
class ReturnIntentError(Exception):
    def __init__(self, message: str, code: str = "RETURN_INTENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ReturnIntentService:
    """
    Optional intent-to-return survey for boarding/private schools.
    Results are advisory only — does NOT block promotion or enrollment.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_campaign(self, tenant_id, school_id, *, academic_year_id, name, target_classes, message_template=None, deadline=None) -> ReturnIntentCampaign:
        """Create return intent campaign in draft status."""

    async def send_campaign(self, tenant_id, campaign_id) -> int:
        """
        Send campaign: creates ReturnIntent records for all active students
        in target classes, sends SMS/email to their guardians.
        Returns: number of notifications sent.
        Uses AdmissionNotificationService for each guardian.
        """

    async def respond(self, tenant_id, intent_id, *, intent, responded_by, reason=None) -> ReturnIntent:
        """Parent responds to survey. intent: returning/not_returning/undecided."""

    async def get_campaign_stats(self, tenant_id, campaign_id) -> dict:
        """Returns: { total, pending, returning, not_returning, undecided }"""

    async def list_campaigns(self, tenant_id, school_id, *, page=1, page_size=20) -> tuple[list, int]:
        """List return intent campaigns for a school."""

    async def get_campaign_intents(self, tenant_id, campaign_id, *, intent_filter=None, page=1, page_size=50) -> tuple[list, int]:
        """Get student intents for a campaign with optional filter."""
```

---

## 2.15 Services Package `__init__.py`

**File:** `backend/app/services/admissions/__init__.py`

```python
"""SIMS Plus - Admissions Services Package"""

from app.services.admissions.application_service import (
    ApplicationService,
    ApplicationServiceError,
)
from app.services.admissions.decision_service import (
    DecisionService,
    DecisionServiceError,
)
from app.services.admissions.enrollment_service import (
    EnrollmentError,
    EnrollmentService,
)
from app.services.admissions.exam_service import (
    EntranceExamService,
    EntranceExamServiceError,
)
from app.services.admissions.notification_service import AdmissionNotificationService
from app.services.admissions.payment_service import (
    ApplicationPaymentError,
    ApplicationPaymentService,
)
from app.services.admissions.period_service import (
    AdmissionPeriodError,
    AdmissionPeriodService,
)
from app.services.admissions.promotion_service import (
    ClassPromotionError,
    ClassPromotionService,
)
from app.services.admissions.return_intent_service import (
    ReturnIntentError,
    ReturnIntentService,
)

__all__ = [
    "AdmissionPeriodService",
    "AdmissionPeriodError",
    "ApplicationService",
    "ApplicationServiceError",
    "ApplicationPaymentService",
    "ApplicationPaymentError",
    "AdmissionNotificationService",
    "EnrollmentService",
    "EnrollmentError",
    "EntranceExamService",
    "EntranceExamServiceError",
    "DecisionService",
    "DecisionServiceError",
    "ClassPromotionService",
    "ClassPromotionError",
    "ReturnIntentService",
    "ReturnIntentError",
]
```

---

## 2.16 Offer Expiry Background Task

**File:** `backend/app/tasks/admissions.py`

A Celery periodic task that transitions OFFERED applications to EXPIRED when the `response_deadline` passes.

```python
"""Admissions background tasks."""

from datetime import UTC, datetime

import structlog
from celery import shared_task
from sqlalchemy import select, update

from app.db.session import sync_session_maker
from app.models.admissions import AdmissionDecision, Application
from app.models.admissions.enums import AdmissionApplicationStatus

logger = structlog.get_logger(__name__)


@shared_task(name="expire_overdue_offers")
def expire_overdue_offers() -> dict:
    """
    Expire applications with passed response deadlines.

    Runs daily via Celery Beat. Finds all OFFERED applications where
    the associated decision's response_deadline < today and transitions
    them to EXPIRED.

    Uses unscoped session — iterates all tenants.
    """
    today = datetime.now(UTC).date()
    expired_count = 0

    with sync_session_maker() as session:
        # Find offered applications with expired deadlines
        result = session.execute(
            select(Application.id, Application.tenant_id)
            .join(AdmissionDecision, AdmissionDecision.application_id == Application.id)
            .where(
                Application.status == AdmissionApplicationStatus.OFFERED.value,
                Application.deleted_at.is_(None),
                AdmissionDecision.response_deadline < today,
                AdmissionDecision.deleted_at.is_(None),
            )
        )
        rows = result.all()

        for app_id, tenant_id in rows:
            session.execute(
                update(Application)
                .where(Application.id == app_id)
                .values(status=AdmissionApplicationStatus.EXPIRED.value)
            )
            expired_count += 1

        session.commit()

    logger.info("expire_overdue_offers_complete", expired_count=expired_count)
    return {"expired_count": expired_count}
```

**Celery Beat schedule** — add to existing beat config:

```python
CELERY_BEAT_SCHEDULE = {
    # ... existing tasks ...
    "expire-overdue-offers": {
        "task": "expire_overdue_offers",
        "schedule": crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}
```

---

## Acceptance Criteria

- [ ] `get_public_tenant_db()` added to `deps.py` — creates tenant-scoped session from subdomain
- [ ] `verify_turnstile()` created in `utils/turnstile.py` — skips in dev when key not set
- [ ] `TURNSTILE_SECRET_KEY` and `TURNSTILE_SITE_KEY` added to config
- [ ] PUBLIC_PATH_PREFIXES updated: webhook path in `middleware/tenant.py`, public prefix in `api/deps.py`
- [ ] Rate limits added for application submission (3/min)
- [ ] `admissions.*` added to school_admin + chain_admin; `admissions.read` + `admissions.review` to academic_head
- [ ] `jsonschema>=4.20.0` in requirements.txt
- [ ] All 9 service files created with proper class structure
- [ ] All services use `flush()/refresh()` not `commit()`
- [ ] All services filter by `tenant_id` (defense-in-depth)
- [ ] ApplicationService validates Turnstile + custom fields (jsonschema)
- [ ] PaymentService webhook uses UnscopedDatabaseSession + manual tenant context
- [ ] EnrollmentService performs atomic conversion with guardian dedup
- [ ] EnrollmentService bulk_enroll uses savepoints for partial success
- [ ] NotificationService uses SMSService + EmailComposeService directly (not NotificationDispatcher)
- [ ] PeriodService validates no overlapping periods
