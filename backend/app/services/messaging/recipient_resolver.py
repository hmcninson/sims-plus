"""
SIMS Plus - Recipient Resolver

Resolves audience segments (all_parents, all_staff, class_parents) into
concrete lists of recipients with name, phone, and email.

All queries are defense-in-depth scoped by tenant_id even though RLS
provides isolation at the database level.
"""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class, ClassSection
from app.models.staff import Staff, StaffStatus
from app.models.student import (
    Guardian,
    Student,
    StudentGuardian,
    StudentStatus,
)

logger = structlog.get_logger()


class RecipientResolverError(Exception):
    """Error during recipient resolution."""

    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


class RecipientResolver:
    """Resolve audience segments into lists of {name, phone, email, type}."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve(
        self,
        tenant_id: UUID,
        audience: str,
        school_id: UUID | None = None,
        class_id: UUID | None = None,
    ) -> list[dict]:
        """
        Resolve an audience string into a de-duplicated recipient list.

        Args:
            tenant_id: Tenant scope for defense-in-depth filtering.
            audience: One of all_parents, all_staff, class_parents, specific.
            school_id: Optional school-level scoping for chain tenants.
            class_id: Required when audience is class_parents.

        Returns:
            List of dicts: [{name, phone, email, type}, ...]
        """
        if audience == "all_parents":
            return await self._resolve_all_parents(tenant_id, school_id)
        elif audience == "all_staff":
            return await self._resolve_all_staff(tenant_id, school_id)
        elif audience == "class_parents":
            if not class_id:
                raise RecipientResolverError(
                    "class_id is required for class_parents audience"
                )
            return await self._resolve_class_parents(tenant_id, class_id, school_id)
        elif audience == "specific":
            # Caller provides the list directly; nothing to resolve
            return []
        else:
            raise RecipientResolverError(f"Unknown audience type: {audience}")

    async def _resolve_all_parents(
        self, tenant_id: UUID, school_id: UUID | None
    ) -> list[dict]:
        """
        Fetch all guardians of active students in this tenant.

        Joins through student_guardians -> students to ensure we only
        include guardians whose students are currently enrolled.
        """
        # Build query: guardians linked to active students
        stmt = (
            select(Guardian)
            .join(
                StudentGuardian,
                StudentGuardian.guardian_id == Guardian.id,
            )
            .join(
                Student,
                Student.id == StudentGuardian.student_id,
            )
            # Defense-in-depth: tenant scope on all three tables
            .where(Guardian.tenant_id == tenant_id)
            .where(StudentGuardian.tenant_id == tenant_id)
            .where(Student.tenant_id == tenant_id)
            .where(Student.status == StudentStatus.ACTIVE)
            .where(Student.deleted_at.is_(None))
            .where(Guardian.deleted_at.is_(None))
        )

        if school_id:
            stmt = stmt.where(Student.school_id == school_id)

        # Distinct guardians (one guardian may have multiple students)
        stmt = stmt.distinct(Guardian.id)

        result = await self.db.execute(stmt)
        guardians = result.scalars().all()

        return [
            {
                "name": g.full_name,
                "phone": g.phone,
                "email": g.email,
                "type": "parent",
            }
            for g in guardians
        ]

    async def _resolve_all_staff(
        self, tenant_id: UUID, school_id: UUID | None
    ) -> list[dict]:
        """Fetch all active staff members in this tenant."""
        stmt = (
            select(Staff)
            .where(Staff.tenant_id == tenant_id)
            .where(Staff.status == StaffStatus.ACTIVE)
            .where(Staff.deleted_at.is_(None))
        )

        if school_id:
            stmt = stmt.where(Staff.school_id == school_id)

        result = await self.db.execute(stmt)
        staff_list = result.scalars().all()

        return [
            {
                "name": f"{s.first_name} {s.last_name}",
                "phone": s.phone,
                "email": s.email,
                "type": "staff",
            }
            for s in staff_list
        ]

    async def _resolve_class_parents(
        self, tenant_id: UUID, class_id: UUID, school_id: UUID | None
    ) -> list[dict]:
        """
        Fetch guardians of active students enrolled in a specific class.

        Joins students -> student_guardians -> guardians, filtering by
        class_id on the student.
        """
        # Verify class exists in tenant (defense-in-depth + IDOR check)
        class_check = await self.db.execute(
            select(Class.id)
            .where(Class.tenant_id == tenant_id)
            .where(Class.id == class_id)
            .where(Class.deleted_at.is_(None))
        )
        if not class_check.scalar_one_or_none():
            raise RecipientResolverError("Class not found", 404)

        stmt = (
            select(Guardian)
            .join(
                StudentGuardian,
                StudentGuardian.guardian_id == Guardian.id,
            )
            .join(
                Student,
                Student.id == StudentGuardian.student_id,
            )
            .where(Guardian.tenant_id == tenant_id)
            .where(StudentGuardian.tenant_id == tenant_id)
            .where(Student.tenant_id == tenant_id)
            .where(Student.class_id == class_id)
            .where(Student.status == StudentStatus.ACTIVE)
            .where(Student.deleted_at.is_(None))
            .where(Guardian.deleted_at.is_(None))
        )

        if school_id:
            stmt = stmt.where(Student.school_id == school_id)

        stmt = stmt.distinct(Guardian.id)

        result = await self.db.execute(stmt)
        guardians = result.scalars().all()

        return [
            {
                "name": g.full_name,
                "phone": g.phone,
                "email": g.email,
                "type": "parent",
            }
            for g in guardians
        ]
