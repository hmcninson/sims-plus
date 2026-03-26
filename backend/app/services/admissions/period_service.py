"""
SIMS Plus - Admission Period Service

CRUD operations for admission periods with overlap validation and
form configuration management.
"""

import json
import uuid
from datetime import date

import structlog
from jsonschema import Draft7Validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


def _json_depth(obj: object, current: int = 0) -> int:
    """Calculate maximum nesting depth of a JSON-like structure."""
    if isinstance(obj, dict):
        if not obj:
            return current + 1
        return max(_json_depth(v, current + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return current + 1
        return max(_json_depth(v, current + 1) for v in obj)
    return current


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
        description: str | None = None,
        application_fee_amount: float | None = None,
        application_fee_required: bool = False,
        entrance_exam_required: bool = False,
        max_applications: int | None = None,
        target_classes: list[uuid.UUID] | None = None,
        require_applicant_account: bool = False,
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

        # Prevent overlapping periods for the same classes
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
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=AdmissionPeriodStatus.DRAFT.value,
            application_fee_amount=application_fee_amount,
            application_fee_required=application_fee_required,
            entrance_exam_required=entrance_exam_required,
            max_applications=max_applications,
            target_classes=target_class_list,
            require_applicant_account=require_applicant_account,
        )
        self.db.add(period)
        await self.db.flush()
        await self.db.refresh(period)
        return period

    async def update(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
        **kwargs,
    ) -> AdmissionPeriod:
        """
        Update an admission period.

        Only draft or open periods can be updated. Re-validates overlap
        if date or class fields change.
        """
        period = await self._get_period(tenant_id, period_id)

        if period.status not in (
            AdmissionPeriodStatus.DRAFT.value,
            AdmissionPeriodStatus.OPEN.value,
        ):
            raise AdmissionPeriodError(
                "Only draft or open periods can be updated",
                code="PERIOD_LOCKED",
            )

        # Apply allowed field updates
        updatable = {
            "name", "description", "start_date", "end_date",
            "application_fee_amount", "application_fee_required",
            "entrance_exam_required", "max_applications", "target_classes",
            "require_applicant_account",
        }
        for key, value in kwargs.items():
            if key in updatable and value is not None:
                if key == "target_classes":
                    value = [str(c) for c in value]
                setattr(period, key, value)

        # Re-validate dates if changed
        if period.start_date >= period.end_date:
            raise AdmissionPeriodError(
                "Start date must be before end date",
                code="INVALID_DATES",
            )

        # Re-validate overlap if dates or classes changed
        target_class_list = period.target_classes or []
        if target_class_list:
            await self._validate_no_overlap(
                tenant_id=tenant_id,
                school_id=period.school_id,
                start_date=period.start_date,
                end_date=period.end_date,
                target_classes=target_class_list,
                exclude_period_id=period_id,
            )

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
          draft -> open
          open -> closed
          closed -> archived
        """
        valid_transitions: dict[str, list[str]] = {
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

    async def get_period(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> AdmissionPeriod:
        """Get a single period by ID."""
        return await self._get_period(tenant_id, period_id)

    async def list_periods(
        self,
        tenant_id: uuid.UUID,
        *,
        school_id: uuid.UUID | None = None,
        status: str | None = None,
        academic_year_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdmissionPeriod], int]:
        """List periods with optional filters and pagination."""
        query = (
            select(AdmissionPeriod)
            .where(
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.deleted_at.is_(None),
            )
        )

        if school_id:
            query = query.where(AdmissionPeriod.school_id == school_id)
        if status:
            query = query.where(AdmissionPeriod.status == status)
        if academic_year_id:
            query = query.where(AdmissionPeriod.academic_year_id == academic_year_id)

        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Paginate
        query = (
            query
            .order_by(AdmissionPeriod.start_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

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

    async def update_form_config(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
        form_schema: dict,
        required_documents: list[str],
    ) -> AdmissionFormConfig:
        """Create or update form configuration for a period."""
        period = await self._get_period(tenant_id, period_id)

        # Validate the schema itself is well-formed
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

    async def get_form_config(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> AdmissionFormConfig | None:
        """Get form configuration for a period."""
        result = await self.db.execute(
            select(AdmissionFormConfig).where(
                AdmissionFormConfig.tenant_id == tenant_id,
                AdmissionFormConfig.admission_period_id == period_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete(
        self,
        tenant_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> None:
        """Soft-delete a period. Only draft periods can be deleted."""
        period = await self._get_period(tenant_id, period_id)
        if period.status != AdmissionPeriodStatus.DRAFT.value:
            raise AdmissionPeriodError(
                "Only draft periods can be deleted",
                code="PERIOD_LOCKED",
            )

        from datetime import UTC, datetime as dt

        period.deleted_at = dt.now(UTC)
        await self.db.flush()

    # ---- Private helpers ----

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
            overlap = target_set & existing_classes
            if overlap:
                raise AdmissionPeriodError(
                    f"Admission period overlaps with '{existing.name}' "
                    f"for classes: {overlap}",
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
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.deleted_at.is_(None),
            )
        )
        period = result.scalar_one_or_none()
        if not period:
            raise AdmissionPeriodError("Period not found", code="NOT_FOUND")
        return period
