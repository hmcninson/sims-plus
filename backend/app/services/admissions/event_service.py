"""
SIMS Plus - School Event Service

Manages school tours, open days, and orientation events.
EventRegistration uses hard deletes; registered_count is maintained atomically.
"""

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import EventStatus, EventType, SchoolEvent, EventRegistration

logger = structlog.get_logger(__name__)


class EventServiceError(Exception):
    def __init__(self, message: str, code: str = "EVENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        event_type: str,
        name: str,
        description: str | None = None,
        event_date,
        start_time=None,
        end_time=None,
        venue: str | None = None,
        capacity: int | None = None,
        guide_id: uuid.UUID | None = None,
    ) -> SchoolEvent:
        """Create a new school event."""
        # Validate event_type against known enum values
        if event_type not in [e.value for e in EventType]:
            raise EventServiceError(
                f"Invalid event type: {event_type}", "INVALID_TYPE"
            )

        event = SchoolEvent(
            tenant_id=tenant_id,
            school_id=school_id,
            event_type=event_type,
            name=name,
            description=description,
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            capacity=capacity,
            registered_count=0,
            status=EventStatus.UPCOMING.value,
            guide_id=guide_id,
        )
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)

        logger.info(
            "school_event_created",
            event_id=str(event.id),
            event_type=event_type,
            event_date=str(event_date),
        )
        return event

    # Fields that must never be overwritten via update kwargs
    _PROTECTED_FIELDS = {
        "id",
        "tenant_id",
        "school_id",
        "created_at",
        "updated_at",
        "deleted_at",
        "registered_count",
        "status",
    }

    async def update_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        **kwargs,
    ) -> SchoolEvent:
        """Update event details. Only upcoming events can be modified."""
        event = await self._get_event(tenant_id, event_id)

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Only upcoming events can be updated",
                "NOT_UPCOMING",
            )

        for key, value in kwargs.items():
            # Skip protected fields to prevent accidental overwrites of immutable columns
            if key in self._PROTECTED_FIELDS:
                continue
            if value is not None and hasattr(event, key):
                setattr(event, key, value)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def cancel_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> SchoolEvent:
        """Cancel an upcoming event."""
        event = await self._get_event(tenant_id, event_id)

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Only upcoming events can be cancelled",
                "NOT_UPCOMING",
            )

        event.status = EventStatus.CANCELLED.value
        await self.db.flush()
        await self.db.refresh(event)

        logger.info("school_event_cancelled", event_id=str(event_id))
        return event

    async def complete_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> SchoolEvent:
        """Mark an upcoming event as completed."""
        event = await self._get_event(tenant_id, event_id)

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Only upcoming events can be marked as completed",
                "NOT_UPCOMING",
            )

        event.status = EventStatus.COMPLETED.value
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def list_events(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        event_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SchoolEvent], int]:
        """List events with optional filters and pagination."""
        query = select(SchoolEvent).filter(
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            SchoolEvent.tenant_id == tenant_id,
            SchoolEvent.school_id == school_id,
            SchoolEvent.deleted_at.is_(None),
        )

        if event_type:
            query = query.filter(SchoolEvent.event_type == event_type)
        if status:
            query = query.filter(SchoolEvent.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(SchoolEvent.event_date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        return list(result.scalars().all()), total

    async def register(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        *,
        registrant_name: str,
        registrant_phone: str,
        registrant_email: str | None = None,
        student_name: str | None = None,
        notes: str | None = None,
    ) -> EventRegistration:
        """
        Register a prospective family for an event.

        Checks capacity before registering. Uses with_for_update() on the
        event row to prevent race conditions when checking/incrementing count.
        """
        # Lock the event row to prevent race conditions on registered_count
        event_result = await self.db.execute(
            select(SchoolEvent)
            .filter(
                SchoolEvent.id == event_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                SchoolEvent.tenant_id == tenant_id,
                SchoolEvent.deleted_at.is_(None),
            )
            .with_for_update()
        )
        event = event_result.scalar_one_or_none()
        if not event:
            raise EventServiceError("Event not found", "NOT_FOUND")

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Cannot register for a non-upcoming event",
                "NOT_UPCOMING",
            )

        # Capacity check -- advisory per AD-4 but events enforce hard limit
        if event.capacity is not None and event.registered_count >= event.capacity:
            raise EventServiceError(
                "Event is at full capacity",
                "EVENT_FULL",
            )

        # Check for duplicate registration by phone number
        existing_reg = await self.db.execute(
            select(EventRegistration).filter(
                EventRegistration.tenant_id == tenant_id,
                EventRegistration.event_id == event_id,
                EventRegistration.registrant_phone == registrant_phone,
            )
        )
        if existing_reg.scalar_one_or_none():
            raise EventServiceError(
                "This phone number is already registered for this event",
                "DUPLICATE_REGISTRATION",
            )

        registration = EventRegistration(
            tenant_id=tenant_id,
            event_id=event_id,
            registrant_name=registrant_name,
            registrant_phone=registrant_phone,
            registrant_email=registrant_email,
            student_name=student_name,
            notes=notes,
        )
        self.db.add(registration)

        # Atomically increment registered_count via in-place update
        event.registered_count += 1

        await self.db.flush()
        await self.db.refresh(registration)

        logger.info(
            "event_registration_created",
            registration_id=str(registration.id),
            event_id=str(event_id),
        )
        return registration

    async def delete_registration(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        registration_id: uuid.UUID,
    ) -> None:
        """
        Hard-delete a registration and decrement the event's registered_count.

        Uses with_for_update() to prevent race conditions.
        IDOR check: registration must belong to the specified event.
        """
        # Lock event row for atomic decrement
        event_result = await self.db.execute(
            select(SchoolEvent)
            .filter(
                SchoolEvent.id == event_id,
                SchoolEvent.tenant_id == tenant_id,
                SchoolEvent.deleted_at.is_(None),
            )
            .with_for_update()
        )
        event = event_result.scalar_one_or_none()
        if not event:
            raise EventServiceError("Event not found", "NOT_FOUND")

        # Get registration with IDOR check: must belong to this event
        reg_result = await self.db.execute(
            select(EventRegistration).filter(
                EventRegistration.id == registration_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                EventRegistration.tenant_id == tenant_id,
                EventRegistration.event_id == event_id,  # IDOR prevention
            )
        )
        registration = reg_result.scalar_one_or_none()
        if not registration:
            raise EventServiceError("Registration not found", "REG_NOT_FOUND")

        await self.db.delete(registration)

        # Atomically decrement registered_count (floor at 0)
        if event.registered_count > 0:
            event.registered_count -= 1

        await self.db.flush()

        logger.info(
            "event_registration_deleted",
            registration_id=str(registration_id),
            event_id=str(event_id),
        )

    async def mark_attendance(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        registration_id: uuid.UUID,
        *,
        attended: bool,
    ) -> EventRegistration:
        """
        Mark attendance for a registration.
        IDOR check: registration must belong to the specified event.
        """
        # IDOR: verify registration belongs to the specified event
        reg_result = await self.db.execute(
            select(EventRegistration).filter(
                EventRegistration.id == registration_id,
                EventRegistration.tenant_id == tenant_id,
                EventRegistration.event_id == event_id,  # IDOR prevention
            )
        )
        registration = reg_result.scalar_one_or_none()
        if not registration:
            raise EventServiceError("Registration not found", "REG_NOT_FOUND")

        registration.attended = attended
        await self.db.flush()
        await self.db.refresh(registration)
        return registration

    async def list_registrations(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[EventRegistration], int]:
        """List registrations for an event, paginated."""
        # Verify event exists first
        await self._get_event(tenant_id, event_id)

        query = select(EventRegistration).filter(
            EventRegistration.tenant_id == tenant_id,
            EventRegistration.event_id == event_id,
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(EventRegistration.registered_at.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        return list(result.scalars().all()), total

    async def get_event_stats(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> dict:
        """Get attendance and registration stats for an event."""
        event = await self._get_event(tenant_id, event_id)

        # Count attended using SQL aggregation
        attended_result = await self.db.execute(
            select(func.count(EventRegistration.id)).filter(
                EventRegistration.tenant_id == tenant_id,
                EventRegistration.event_id == event_id,
                EventRegistration.attended.is_(True),
            )
        )
        attended_count = attended_result.scalar() or 0

        total = event.registered_count
        attendance_rate = (
            round(attended_count / total * 100, 1) if total > 0 else 0.0
        )
        fill_rate = None
        if event.capacity and event.capacity > 0:
            fill_rate = round(total / event.capacity * 100, 1)

        return {
            "event_id": event.id,
            "event_name": event.name,
            "total_registered": total,
            "total_attended": attended_count,
            "attendance_rate": attendance_rate,
            "capacity": event.capacity,
            "fill_rate": fill_rate,
        }

    async def _get_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> SchoolEvent:
        """Get event by ID with defense-in-depth tenant check."""
        result = await self.db.execute(
            select(SchoolEvent).filter(
                SchoolEvent.id == event_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                SchoolEvent.tenant_id == tenant_id,
                SchoolEvent.deleted_at.is_(None),
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            raise EventServiceError("Event not found", "NOT_FOUND")
        return event
