"""
SIMS Plus - Preschool Pickup & Dietary Service

Business logic for authorized pickups, pickup logs, and allergy/dietary management.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preschool import AuthorizedPickup, PickupLog
from app.models.student import Student, StudentGuardian
from app.schemas.preschool.pickup import (
    AuthorizedPickupCreate,
    AuthorizedPickupUpdate,
    PickupLogCreate,
)
from app.services.preschool._shared import PreschoolServiceError


class PreschoolPickupService:
    """Service for authorized pickups, pickup logs, and dietary management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Authorized Pickup Methods
    # =========================

    async def add_authorized_pickup(
        self,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        data: AuthorizedPickupCreate,
        added_by: uuid.UUID,
    ) -> AuthorizedPickup:
        """Add an authorized pickup person for a student."""
        # Defense-in-depth: verify student belongs to tenant
        student = await self._get_student(tenant_id, student_id)

        pickup = AuthorizedPickup(
            tenant_id=tenant_id,
            school_id=student.school_id,
            student_id=student_id,
            full_name=data.full_name,
            phone=data.phone,
            relationship_to_student=data.relationship_to_student,
            photo_url=data.photo_url,
            id_document_url=data.id_document_url,
            notes=data.notes,
            added_by=added_by,
        )
        self.db.add(pickup)
        await self.db.flush()
        await self.db.refresh(pickup)
        return pickup

    async def list_authorized_pickups(
        self, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> Sequence[AuthorizedPickup]:
        """List all authorized pickup persons for a student (active + inactive)."""
        result = await self.db.execute(
            select(AuthorizedPickup)
            .where(AuthorizedPickup.tenant_id == tenant_id)
            .where(AuthorizedPickup.student_id == student_id)
            .where(AuthorizedPickup.deleted_at.is_(None))
            .order_by(AuthorizedPickup.full_name)
        )
        return result.scalars().all()

    async def update_authorized_pickup(
        self,
        tenant_id: uuid.UUID,
        pickup_id: uuid.UUID,
        data: AuthorizedPickupUpdate,
    ) -> AuthorizedPickup:
        """Update an authorized pickup person."""
        result = await self.db.execute(
            select(AuthorizedPickup)
            .where(AuthorizedPickup.id == pickup_id)
            .where(AuthorizedPickup.tenant_id == tenant_id)
            .where(AuthorizedPickup.deleted_at.is_(None))
        )
        pickup = result.scalar_one_or_none()
        if not pickup:
            raise PreschoolServiceError(
                "Authorized pickup not found", code="PICKUP_PERSON_NOT_FOUND"
            )

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(pickup, field, value)

        await self.db.flush()
        await self.db.refresh(pickup)
        return pickup

    async def deactivate_authorized_pickup(
        self, tenant_id: uuid.UUID, pickup_id: uuid.UUID
    ) -> None:
        """Soft-delete an authorized pickup person."""
        result = await self.db.execute(
            select(AuthorizedPickup)
            .where(AuthorizedPickup.id == pickup_id)
            .where(AuthorizedPickup.tenant_id == tenant_id)
            .where(AuthorizedPickup.deleted_at.is_(None))
        )
        pickup = result.scalar_one_or_none()
        if not pickup:
            raise PreschoolServiceError(
                "Authorized pickup not found", code="PICKUP_PERSON_NOT_FOUND"
            )

        pickup.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    # =========================
    # Pickup Log Methods
    # =========================

    async def record_pickup(
        self,
        tenant_id: uuid.UUID,
        data: PickupLogCreate,
        verified_by: uuid.UUID,
    ) -> PickupLog:
        """
        Record a student pickup event.

        Validates that:
        - Student belongs to tenant
        - If guardian: guardian is linked to student with can_pickup=True
        - If authorized_person: authorized pickup is active for this student
        """
        # Verify student belongs to tenant and capture school_id
        student = await self._get_student(tenant_id, data.student_id)

        # Validate the pickup person based on type
        if data.picked_up_by_type == "guardian":
            guardian_result = await self.db.execute(
                select(StudentGuardian)
                .where(StudentGuardian.student_id == data.student_id)
                .where(StudentGuardian.guardian_id == data.picked_up_by_guardian_id)
                .where(StudentGuardian.tenant_id == tenant_id)
            )
            sg = guardian_result.scalar_one_or_none()
            if not sg:
                raise PreschoolServiceError(
                    "Guardian is not linked to this student",
                    code="GUARDIAN_NOT_LINKED",
                )
            if not sg.can_pickup:
                raise PreschoolServiceError(
                    "Guardian is not authorized for pickup",
                    code="GUARDIAN_PICKUP_NOT_AUTHORIZED",
                )
        elif data.picked_up_by_type == "authorized_person":
            auth_result = await self.db.execute(
                select(AuthorizedPickup)
                .where(AuthorizedPickup.id == data.picked_up_by_authorized_id)
                .where(AuthorizedPickup.student_id == data.student_id)
                .where(AuthorizedPickup.tenant_id == tenant_id)
                .where(AuthorizedPickup.is_active.is_(True))
                .where(AuthorizedPickup.deleted_at.is_(None))
            )
            if not auth_result.scalar_one_or_none():
                raise PreschoolServiceError(
                    "Authorized pickup person not found or inactive",
                    code="AUTHORIZED_PICKUP_NOT_FOUND",
                )

        log = PickupLog(
            tenant_id=tenant_id,
            school_id=student.school_id,  # Set from student record (chain support)
            student_id=data.student_id,
            pickup_date=date.today(),  # Server-side date, not client-provided
            pickup_time=data.pickup_time,
            picked_up_by_type=data.picked_up_by_type,
            picked_up_by_guardian_id=data.picked_up_by_guardian_id,
            picked_up_by_authorized_id=data.picked_up_by_authorized_id,
            verified_by=verified_by,
            notes=data.notes,
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def list_pickup_logs(
        self,
        tenant_id: uuid.UUID,
        *,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[PickupLog]:
        """List pickup logs with optional filters."""
        query = (
            select(PickupLog)
            .where(PickupLog.tenant_id == tenant_id)
            .order_by(PickupLog.pickup_date.desc(), PickupLog.pickup_time.desc())
        )
        if student_id:
            query = query.where(PickupLog.student_id == student_id)
        if class_id:
            # Defense-in-depth: also filter joined Student by tenant_id
            query = query.join(
                Student, PickupLog.student_id == Student.id
            ).where(
                Student.class_id == class_id,
                Student.tenant_id == tenant_id,
            )
        if date_from:
            query = query.where(PickupLog.pickup_date >= date_from)
        if date_to:
            query = query.where(PickupLog.pickup_date <= date_to)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    # =========================
    # Allergy / Dietary Methods
    # =========================

    async def get_student_dietary_requirements(
        self, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> dict | None:
        """Get structured dietary requirements for a student."""
        result = await self.db.execute(
            select(Student.dietary_requirements)
            .where(Student.id == student_id)
            .where(Student.tenant_id == tenant_id)
        )
        row = result.one_or_none()
        if row is None:
            raise PreschoolServiceError(
                "Student not found", code="STUDENT_NOT_FOUND"
            )
        return row[0]  # dietary_requirements column value (may be None)

    async def update_dietary_requirements(
        self,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        dietary_data: dict | None,
    ) -> None:
        """Update dietary requirements JSONB for a student."""
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .where(Student.tenant_id == tenant_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError(
                "Student not found", code="STUDENT_NOT_FOUND"
            )

        student.dietary_requirements = dietary_data
        await self.db.flush()

    async def get_class_allergy_alerts(
        self, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> list[dict]:
        """
        Get all students in a class who have allergies or dietary restrictions.

        Returns a list of dicts with student_id, student_name, allergies,
        dietary_restrictions, and notes. Used to show allergy alerts when
        teachers open daily log forms.
        """
        result = await self.db.execute(
            select(
                Student.id,
                Student.first_name,
                Student.last_name,
                Student.dietary_requirements,
            )
            .where(Student.tenant_id == tenant_id)
            .where(Student.class_id == class_id)
            .where(Student.dietary_requirements.isnot(None))
            .where(Student.deleted_at.is_(None))
            .order_by(Student.first_name, Student.last_name)
        )
        rows = result.all()

        alerts = []
        for row in rows:
            dietary = row.dietary_requirements or {}
            allergies = dietary.get("allergies", [])
            restrictions = dietary.get("dietary_restrictions", [])
            # Only include students who actually have allergies or restrictions
            if allergies or restrictions:
                alerts.append({
                    "student_id": str(row.id),
                    "student_name": f"{row.first_name} {row.last_name}",
                    "allergies": allergies,
                    "dietary_restrictions": restrictions,
                    "notes": dietary.get("notes"),
                })
        return alerts

    # ---------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------

    async def _get_student(
        self, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> Student:
        """Verify student belongs to tenant and return the record."""
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .where(Student.tenant_id == tenant_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError(
                "Student not found", code="STUDENT_NOT_FOUND"
            )
        return student
