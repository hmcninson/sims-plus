"""
SIMS Plus - Staff Employment History Service

Tracks employment events: promotions, transfers, department changes,
title changes, status changes, etc.
"""

from datetime import date
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import (
    Staff,
    StaffEmploymentHistory,
    EmploymentEventType,
    EmploymentType,
    StaffStatus,
    StaffType,
)
from app.services.staff._shared import StaffServiceError

logger = structlog.get_logger()


class StaffHistoryService:
    """Service for tracking and querying staff employment history events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_event(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        event_type: str,
        effective_date: date,
        recorded_by: UUID,
        school_id: Optional[UUID] = None,
        previous_value: Optional[str] = None,
        new_value: Optional[str] = None,
        previous_department_id: Optional[UUID] = None,
        new_department_id: Optional[UUID] = None,
        previous_job_title: Optional[str] = None,
        new_job_title: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> StaffEmploymentHistory:
        """Record a single employment history event.

        Validates that the staff member exists and the event_type is valid.
        """
        # Defense-in-depth: verify staff exists and belongs to tenant
        await self._get_staff_or_raise(tenant_id, staff_id)

        # Validate event_type is a known enum value
        try:
            event_type_enum = EmploymentEventType(event_type)
        except ValueError:
            valid = ", ".join(e.value for e in EmploymentEventType)
            raise StaffServiceError(
                f"Invalid event type: {event_type}. Valid: {valid}",
                code="invalid_event_type",
            )

        record = StaffEmploymentHistory(
            tenant_id=tenant_id,
            staff_id=staff_id,
            school_id=school_id,
            event_type=event_type_enum,
            effective_date=effective_date,
            recorded_by=recorded_by,
            previous_value=previous_value,
            new_value=new_value,
            previous_department_id=previous_department_id,
            new_department_id=new_department_id,
            previous_job_title=previous_job_title,
            new_job_title=new_job_title,
            notes=notes,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_history(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> list[StaffEmploymentHistory]:
        """List employment history for a staff member, ordered by effective_date DESC."""
        # Defense-in-depth: verify staff exists and belongs to tenant
        await self._get_staff_or_raise(tenant_id, staff_id)

        result = await self.db.execute(
            select(StaffEmploymentHistory)
            .where(StaffEmploymentHistory.tenant_id == tenant_id)
            .where(StaffEmploymentHistory.staff_id == staff_id)
            .order_by(StaffEmploymentHistory.effective_date.desc())
        )
        return list(result.scalars().all())

    async def auto_record_changes(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        old_staff: Staff,
        new_data: dict,
        recorded_by: UUID,
        school_id: Optional[UUID] = None,
    ) -> list[StaffEmploymentHistory]:
        """Automatically track changes to tracked fields.

        Compares old_staff attribute values to new_data dict and creates
        appropriate history events for each changed field.
        Tracked fields: job_title, department_id, status, employment_type.
        """
        from datetime import date as date_type

        records: list[StaffEmploymentHistory] = []
        today = date_type.today()

        # --- job_title ---
        if "job_title" in new_data and new_data["job_title"] is not None:
            old_val = old_staff.job_title
            new_val = new_data["job_title"]
            if old_val != new_val:
                record = StaffEmploymentHistory(
                    tenant_id=tenant_id,
                    staff_id=staff_id,
                    school_id=school_id,
                    event_type=EmploymentEventType.TITLE_CHANGED,
                    effective_date=today,
                    previous_job_title=old_val,
                    new_job_title=new_val,
                    recorded_by=recorded_by,
                )
                self.db.add(record)
                records.append(record)

        # --- department_id ---
        if "department_id" in new_data and new_data["department_id"] is not None:
            old_val = old_staff.department_id
            new_val = new_data["department_id"]
            if str(old_val) != str(new_val) if old_val else True:
                record = StaffEmploymentHistory(
                    tenant_id=tenant_id,
                    staff_id=staff_id,
                    school_id=school_id,
                    event_type=EmploymentEventType.DEPARTMENT_CHANGED,
                    effective_date=today,
                    previous_department_id=old_val,
                    new_department_id=new_val,
                    recorded_by=recorded_by,
                )
                self.db.add(record)
                records.append(record)

        # --- status ---
        if "status" in new_data and new_data["status"] is not None:
            # Normalize to string for comparison (old_staff.status may be enum)
            old_val = old_staff.status.value if hasattr(old_staff.status, "value") else str(old_staff.status)
            new_val = new_data["status"]
            if old_val != new_val:
                record = StaffEmploymentHistory(
                    tenant_id=tenant_id,
                    staff_id=staff_id,
                    school_id=school_id,
                    event_type=EmploymentEventType.STATUS_CHANGED,
                    effective_date=today,
                    previous_value=old_val,
                    new_value=new_val,
                    recorded_by=recorded_by,
                )
                self.db.add(record)
                records.append(record)

        # --- employment_type ---
        if "employment_type" in new_data and new_data["employment_type"] is not None:
            old_val = (
                old_staff.employment_type.value
                if old_staff.employment_type and hasattr(old_staff.employment_type, "value")
                else str(old_staff.employment_type) if old_staff.employment_type else None
            )
            new_val = new_data["employment_type"]
            if old_val != new_val:
                record = StaffEmploymentHistory(
                    tenant_id=tenant_id,
                    staff_id=staff_id,
                    school_id=school_id,
                    event_type=EmploymentEventType.CONTRACT_RENEWED,
                    effective_date=today,
                    previous_value=old_val,
                    new_value=new_val,
                    recorded_by=recorded_by,
                    notes="Employment type changed",
                )
                self.db.add(record)
                records.append(record)

        if records:
            await self.db.flush()
            for r in records:
                await self.db.refresh(r)

        return records

    # =========================
    # Private Helpers
    # =========================

    async def _get_staff_or_raise(self, tenant_id: UUID, staff_id: UUID) -> Staff:
        """Fetch staff by ID with tenant scoping, raise if not found."""
        result = await self.db.execute(
            select(Staff)
            .where(Staff.tenant_id == tenant_id)
            .where(Staff.id == staff_id)
            .where(Staff.deleted_at.is_(None))
        )
        staff = result.scalar_one_or_none()
        if not staff:
            raise StaffServiceError("Staff member not found", code="staff_not_found")
        return staff
