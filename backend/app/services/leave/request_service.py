"""
SIMS Plus - Leave Request Service

Full lifecycle: submit, approve, reject, cancel, list, calendar.
"""

from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicYear
from app.models.academic.timetable_models import SchoolHoliday
from app.models.leave import LeaveBalance, LeaveRequest, LeaveRequestStatus, LeaveType
from app.models.staff import Staff, StaffStatus
from app.models.user import User

logger = structlog.get_logger()


class LeaveRequestService:
    """Service for leave request lifecycle management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def submit(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        data: dict,
        school_id: Optional[UUID] = None,
    ) -> LeaveRequest:
        """
        Submit a new leave request.

        Validates: active leave type, date range, no overlaps,
        calculates working days (excluding weekends + holidays),
        checks balance, creates request, increments pending_days.
        Auto-approves if leave type doesn't require approval.
        """
        start_date = data["start_date"]
        end_date = data["end_date"]
        leave_type_id = data["leave_type_id"]

        # Validate date range
        if end_date < start_date:
            raise self.Error("End date must be on or after start date")
        if start_date < date.today():
            raise self.Error("Start date cannot be in the past")

        # Validate leave type is active
        leave_type = await self._get_leave_type(tenant_id, leave_type_id)

        # Check for overlapping pending/approved requests for same staff
        await self._check_overlap(tenant_id, staff_id, start_date, end_date)

        # Get current academic year for balance lookup
        academic_year_id = await self._get_current_academic_year_id(tenant_id)
        if not academic_year_id:
            raise self.Error(
                "No active academic year found. Cannot submit leave request."
            )

        # Calculate working days (exclude weekends + holidays)
        days = await self._calculate_working_days(tenant_id, start_date, end_date)
        if days <= Decimal("0"):
            raise self.Error(
                "No working days in the selected date range "
                "(all days are weekends or holidays)"
            )

        # Check balance with FOR UPDATE lock to prevent race conditions
        balance = await self._get_balance_for_update(
            tenant_id, staff_id, leave_type_id, academic_year_id
        )
        if not balance:
            raise self.Error(
                "No leave balance found. Please ask your admin to "
                "initialize leave balances for this academic year."
            )

        remaining = (
            balance.entitled_days + balance.carried_over
            - balance.used_days - balance.pending_days
        )
        if remaining < days:
            raise self.Error(
                f"Insufficient leave balance. "
                f"Available: {remaining} days, Requested: {days} days"
            )

        # Create the request
        request = LeaveRequest(
            tenant_id=tenant_id,
            school_id=school_id,
            staff_id=staff_id,
            leave_type_id=leave_type_id,
            academic_year_id=academic_year_id,
            start_date=start_date,
            end_date=end_date,
            days_requested=days,
            reason=data["reason"],
            status=LeaveRequestStatus.PENDING,
        )
        self.db.add(request)

        # Increment pending days on balance
        balance.pending_days += days
        await self.db.flush()
        await self.db.refresh(request)

        logger.info(
            "leave_request_submitted",
            request_id=str(request.id),
            staff_id=str(staff_id),
            days=str(days),
            tenant_id=str(tenant_id),
        )

        # Auto-approve if leave type doesn't require approval
        if not leave_type.requires_approval:
            return await self.approve(
                tenant_id, request.id, reviewer_id=None, notes="Auto-approved"
            )

        return request

    async def approve(
        self,
        tenant_id: UUID,
        request_id: UUID,
        reviewer_id: Optional[UUID],
        notes: Optional[str] = None,
    ) -> LeaveRequest:
        """
        Approve a pending leave request.
        Moves days from pending to used on the balance.
        Updates staff status to on_leave if leave starts today or earlier.
        """
        request = await self._get_request(tenant_id, request_id)
        if request.status != LeaveRequestStatus.PENDING:
            raise self.Error("Can only approve pending requests", 409)

        # Lock balance row to prevent race conditions
        balance = await self._get_balance_for_update(
            tenant_id, request.staff_id, request.leave_type_id,
            request.academic_year_id,
        )
        if not balance:
            raise self.Error("Leave balance not found for this request")

        request.status = LeaveRequestStatus.APPROVED
        request.reviewed_by = reviewer_id
        request.reviewed_at = datetime.now(UTC)
        request.review_notes = notes

        # Move from pending to used
        balance.pending_days -= request.days_requested
        balance.used_days += request.days_requested

        # If leave starts today or earlier, update staff status
        if request.start_date <= date.today():
            staff_result = await self.db.execute(
                select(Staff).where(
                    Staff.id == request.staff_id,
                    Staff.tenant_id == tenant_id,
                    Staff.deleted_at.is_(None),
                )
            )
            staff = staff_result.scalar_one_or_none()
            if staff and staff.status == StaffStatus.ACTIVE:
                staff.status = StaffStatus.ON_LEAVE

        await self.db.flush()
        await self.db.refresh(request)

        logger.info(
            "leave_request_approved",
            request_id=str(request_id),
            staff_id=str(request.staff_id),
            reviewer_id=str(reviewer_id) if reviewer_id else "auto",
            tenant_id=str(tenant_id),
        )
        return request

    async def reject(
        self,
        tenant_id: UUID,
        request_id: UUID,
        reviewer_id: UUID,
        notes: Optional[str] = None,
    ) -> LeaveRequest:
        """Reject a pending request. Reverse pending_days on balance."""
        request = await self._get_request(tenant_id, request_id)
        if request.status != LeaveRequestStatus.PENDING:
            raise self.Error("Can only reject pending requests", 409)

        # Lock balance to prevent race conditions
        balance = await self._get_balance_for_update(
            tenant_id, request.staff_id, request.leave_type_id,
            request.academic_year_id,
        )
        if balance:
            balance.pending_days -= request.days_requested

        request.status = LeaveRequestStatus.REJECTED
        request.reviewed_by = reviewer_id
        request.reviewed_at = datetime.now(UTC)
        request.review_notes = notes

        await self.db.flush()
        await self.db.refresh(request)

        logger.info(
            "leave_request_rejected",
            request_id=str(request_id),
            staff_id=str(request.staff_id),
            tenant_id=str(tenant_id),
        )
        return request

    async def cancel(
        self,
        tenant_id: UUID,
        request_id: UUID,
        staff_id: UUID,
    ) -> LeaveRequest:
        """
        Cancel own request (only if pending or approved-but-not-started).
        If was approved, reverses used_days back to balance.
        """
        request = await self._get_request(tenant_id, request_id)

        # Only the requesting staff member can cancel
        if request.staff_id != staff_id:
            raise self.Error("Can only cancel your own requests", 403)

        if request.status not in (
            LeaveRequestStatus.PENDING,
            LeaveRequestStatus.APPROVED,
        ):
            raise self.Error("Cannot cancel this request", 409)

        # Cannot cancel approved leave that has already started
        if (
            request.status == LeaveRequestStatus.APPROVED
            and request.start_date <= date.today()
        ):
            raise self.Error(
                "Cannot cancel leave that has already started", 409
            )

        # Lock balance to prevent race conditions
        balance = await self._get_balance_for_update(
            tenant_id, request.staff_id, request.leave_type_id,
            request.academic_year_id,
        )
        if balance:
            if request.status == LeaveRequestStatus.PENDING:
                balance.pending_days -= request.days_requested
            elif request.status == LeaveRequestStatus.APPROVED:
                # Reverse the used_days that were added during approval
                balance.used_days -= request.days_requested

        request.status = LeaveRequestStatus.CANCELLED
        await self.db.flush()
        await self.db.refresh(request)

        logger.info(
            "leave_request_cancelled",
            request_id=str(request_id),
            staff_id=str(staff_id),
            tenant_id=str(tenant_id),
        )
        return request

    async def get_request(
        self,
        tenant_id: UUID,
        request_id: UUID,
    ) -> dict:
        """Get a single leave request with related names."""
        request = await self._get_request_with_relations(tenant_id, request_id)
        return self._request_to_dict(request)

    async def list_requests(
        self,
        tenant_id: UUID,
        status: Optional[str] = None,
        staff_id: Optional[UUID] = None,
        leave_type_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """List leave requests with filters."""
        query = (
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.leave_type),
                selectinload(LeaveRequest.staff),
                selectinload(LeaveRequest.reviewer),
            )
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                LeaveRequest.tenant_id == tenant_id,
            )
            .order_by(LeaveRequest.created_at.desc())
        )

        if status:
            query = query.where(LeaveRequest.status == status)
        if staff_id:
            query = query.where(LeaveRequest.staff_id == staff_id)
        if leave_type_id:
            query = query.where(LeaveRequest.leave_type_id == leave_type_id)
        if start_date:
            query = query.where(LeaveRequest.end_date >= start_date)
        if end_date:
            query = query.where(LeaveRequest.start_date <= end_date)

        result = await self.db.execute(query)
        requests = result.scalars().all()
        return [self._request_to_dict(r) for r in requests]

    async def update_request(
        self,
        tenant_id: UUID,
        request_id: UUID,
        staff_id: UUID,
        data: dict,
    ) -> LeaveRequest:
        """
        Update a pending leave request (before approval).
        Only the requesting staff member can update.
        Recalculates working days if dates change.
        """
        request = await self._get_request(tenant_id, request_id)

        if request.staff_id != staff_id:
            raise self.Error("Can only update your own requests", 403)
        if request.status != LeaveRequestStatus.PENDING:
            raise self.Error("Can only update pending requests", 409)

        new_start = data.get("start_date", request.start_date)
        new_end = data.get("end_date", request.end_date)
        dates_changed = (
            new_start != request.start_date or new_end != request.end_date
        )

        if new_end < new_start:
            raise self.Error("End date must be on or after start date")
        if new_start < date.today():
            raise self.Error("Start date cannot be in the past")

        if dates_changed:
            # Check for overlaps with other requests (exclude self)
            await self._check_overlap(
                tenant_id, staff_id, new_start, new_end,
                exclude_request_id=request_id,
            )

            # Recalculate working days
            new_days = await self._calculate_working_days(
                tenant_id, new_start, new_end
            )
            if new_days <= Decimal("0"):
                raise self.Error(
                    "No working days in the selected date range"
                )

            # Adjust pending_days on balance
            balance = await self._get_balance_for_update(
                tenant_id, staff_id, request.leave_type_id,
                request.academic_year_id,
            )
            if balance:
                # Recheck balance with new days
                old_days = request.days_requested
                balance.pending_days = balance.pending_days - old_days + new_days
                remaining = (
                    balance.entitled_days + balance.carried_over
                    - balance.used_days - balance.pending_days
                )
                if remaining < Decimal("0"):
                    # Rollback the pending_days change
                    balance.pending_days = balance.pending_days + old_days - new_days
                    raise self.Error(
                        f"Insufficient leave balance for updated dates. "
                        f"Available: {remaining + new_days} days, "
                        f"Requested: {new_days} days"
                    )

            request.start_date = new_start
            request.end_date = new_end
            request.days_requested = new_days

        if "reason" in data and data["reason"] is not None:
            request.reason = data["reason"]

        await self.db.flush()
        await self.db.refresh(request)
        return request

    async def get_calendar(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Get all approved/pending leave for calendar view within date range."""
        result = await self.db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.leave_type),
                selectinload(LeaveRequest.staff),
            )
            .where(
                LeaveRequest.tenant_id == tenant_id,
                LeaveRequest.status.in_([
                    LeaveRequestStatus.APPROVED,
                    LeaveRequestStatus.PENDING,
                ]),
                # Overlap check: request overlaps with the requested range
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
            )
            .order_by(LeaveRequest.start_date)
        )
        requests = result.scalars().all()

        return [
            {
                "staff_id": r.staff_id,
                "staff_name": (
                    f"{r.staff.first_name} {r.staff.last_name}"
                    if r.staff else "Unknown"
                ),
                "leave_type_name": r.leave_type.name if r.leave_type else "Unknown",
                "leave_type_color": r.leave_type.color if r.leave_type else None,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "days": r.days_requested,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
            }
            for r in requests
        ]

    # ===========================
    # Private Helper Methods
    # ===========================

    async def _get_leave_type(self, tenant_id: UUID, leave_type_id: UUID) -> LeaveType:
        """Fetch an active leave type or raise."""
        result = await self.db.execute(
            select(LeaveType).where(
                LeaveType.id == leave_type_id,
                LeaveType.tenant_id == tenant_id,
                LeaveType.is_active.is_(True),
                LeaveType.deleted_at.is_(None),
            )
        )
        lt = result.scalar_one_or_none()
        if not lt:
            raise self.Error("Leave type not found or inactive", 404)
        return lt

    async def _get_request(self, tenant_id: UUID, request_id: UUID) -> LeaveRequest:
        """Fetch a leave request or raise."""
        result = await self.db.execute(
            select(LeaveRequest).where(
                LeaveRequest.id == request_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                LeaveRequest.tenant_id == tenant_id,
            )
        )
        request = result.scalar_one_or_none()
        if not request:
            raise self.Error("Leave request not found", 404)
        return request

    async def _get_request_with_relations(
        self, tenant_id: UUID, request_id: UUID
    ) -> LeaveRequest:
        """Fetch a leave request with related leave_type, staff, and reviewer."""
        result = await self.db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.leave_type),
                selectinload(LeaveRequest.staff),
                selectinload(LeaveRequest.reviewer),
            )
            .where(
                LeaveRequest.id == request_id,
                LeaveRequest.tenant_id == tenant_id,
            )
        )
        request = result.scalar_one_or_none()
        if not request:
            raise self.Error("Leave request not found", 404)
        return request

    async def _get_balance_for_update(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        leave_type_id: UUID,
        academic_year_id: UUID,
    ) -> Optional[LeaveBalance]:
        """Fetch balance with FOR UPDATE lock to prevent race conditions."""
        result = await self.db.execute(
            select(LeaveBalance)
            .where(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.staff_id == staff_id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.academic_year_id == academic_year_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _check_overlap(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        start_date: date,
        end_date: date,
        exclude_request_id: Optional[UUID] = None,
    ) -> None:
        """Check for overlapping pending/approved requests for same staff."""
        query = select(LeaveRequest).where(
            LeaveRequest.tenant_id == tenant_id,
            LeaveRequest.staff_id == staff_id,
            LeaveRequest.status.in_([
                LeaveRequestStatus.PENDING,
                LeaveRequestStatus.APPROVED,
            ]),
            # Date range overlap: existing.start <= new.end AND existing.end >= new.start
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        if exclude_request_id:
            query = query.where(LeaveRequest.id != exclude_request_id)

        result = await self.db.execute(query)
        overlap = result.scalar_one_or_none()
        if overlap:
            raise self.Error(
                f"Overlapping leave request exists "
                f"({overlap.start_date} to {overlap.end_date})",
                409,
            )

    async def _get_current_academic_year_id(self, tenant_id: UUID) -> Optional[UUID]:
        """Get the current (active) academic year for the tenant."""
        from app.models.academic.year_models import AcademicYearStatus

        result = await self.db.execute(
            select(AcademicYear.id).where(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.is_current.is_(True),
                AcademicYear.deleted_at.is_(None),
            )
        )
        year_id = result.scalar_one_or_none()
        if year_id:
            return year_id

        # Fallback: get the most recent active year
        result = await self.db.execute(
            select(AcademicYear.id)
            .where(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.status == AcademicYearStatus.ACTIVE,
                AcademicYear.deleted_at.is_(None),
            )
            .order_by(AcademicYear.start_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _calculate_working_days(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """
        Calculate working days between two dates, excluding:
        1. Weekends (Saturday=5, Sunday=6)
        2. School holidays (from school_holidays table)

        Returns Decimal for future half-day support.
        """
        # Fetch holidays in range
        holiday_result = await self.db.execute(
            select(SchoolHoliday.date).where(
                SchoolHoliday.tenant_id == tenant_id,
                SchoolHoliday.date >= start_date,
                SchoolHoliday.date <= end_date,
            )
        )
        holiday_dates = {row[0] for row in holiday_result.all()}

        count = Decimal("0")
        current = start_date
        while current <= end_date:
            # weekday(): Monday=0 ... Sunday=6; skip Sat(5) and Sun(6)
            if current.weekday() < 5 and current not in holiday_dates:
                count += Decimal("1")
            current += timedelta(days=1)

        return count

    @staticmethod
    def _request_to_dict(request: LeaveRequest) -> dict:
        """Convert a request to a response dict with related names."""
        return {
            "id": request.id,
            "staff_id": request.staff_id,
            "staff_name": (
                f"{request.staff.first_name} {request.staff.last_name}"
                if request.staff else None
            ),
            "leave_type_id": request.leave_type_id,
            "leave_type_name": request.leave_type.name if request.leave_type else None,
            "leave_type_color": request.leave_type.color if request.leave_type else None,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "days_requested": request.days_requested,
            "reason": request.reason,
            "status": (
                request.status.value
                if hasattr(request.status, "value")
                else request.status
            ),
            "reviewed_by": request.reviewed_by,
            "reviewer_name": (
                f"{request.reviewer.first_name} {request.reviewer.last_name}"
                if request.reviewer else None
            ),
            "reviewed_at": request.reviewed_at,
            "review_notes": request.review_notes,
            "created_at": request.created_at,
        }
