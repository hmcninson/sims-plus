"""
SIMS Plus - Student Guardian Service

Guardian CRUD and student-guardian link management.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.student import (
    Student,
    Guardian,
    StudentGuardian,
    GuardianRelationship,
)
from app.utils.sanitize import escape_ilike

from app.services.student._shared import StudentServiceError


class StudentGuardianMixin:
    """Mixin providing guardian and student-guardian link methods for StudentService."""

    # Type hints for self.db -- set by StudentService.__init__
    db: AsyncSession

    # =========================
    # Guardian Methods
    # =========================

    async def create_guardian(
        self,
        tenant_id: UUID,
        first_name: str,
        last_name: str,
        phone: str,
        phone_secondary: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        occupation: Optional[str] = None,
        workplace: Optional[str] = None,
        work_phone: Optional[str] = None,
        ghana_card_number: Optional[str] = None,
        photo_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Guardian:
        """Create a new guardian."""
        # Check for duplicate email if provided
        if email:
            existing = await self.db.execute(
                select(Guardian).where(
                    and_(
                        Guardian.tenant_id == tenant_id,
                        Guardian.email == email,
                        Guardian.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise StudentServiceError(
                    f"A guardian with email '{email}' already exists",
                    code="duplicate_guardian_email",
                )

        guardian = Guardian(
            tenant_id=tenant_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            phone_secondary=phone_secondary,
            email=email,
            address=address,
            city=city,
            region=region,
            occupation=occupation,
            workplace=workplace,
            work_phone=work_phone,
            ghana_card_number=ghana_card_number,
            photo_url=photo_url,
            notes=notes,
        )
        self.db.add(guardian)
        await self.db.flush()
        await self.db.refresh(guardian)
        return guardian

    async def get_guardian(self, tenant_id: UUID, guardian_id: UUID) -> Optional[Guardian]:
        """Get guardian by ID."""
        result = await self.db.execute(
            select(Guardian).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Guardian.tenant_id == tenant_id,
                    Guardian.id == guardian_id,
                    Guardian.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_guardians(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """List guardians with pagination and student counts."""
        conditions = [
            Guardian.tenant_id == tenant_id,
            Guardian.deleted_at.is_(None),
        ]

        if search:
            # Escape ILIKE wildcards to prevent wildcard injection
            search_term = f"%{escape_ilike(search)}%"
            conditions.append(
                or_(
                    Guardian.first_name.ilike(search_term),
                    Guardian.last_name.ilike(search_term),
                    Guardian.phone.ilike(search_term),
                    Guardian.email.ilike(search_term),
                )
            )

        # Get total count
        count_query = select(func.count(Guardian.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Subquery for student count
        student_count_subq = (
            select(func.count(StudentGuardian.id))
            .where(StudentGuardian.guardian_id == Guardian.id)
            .correlate(Guardian)
            .scalar_subquery()
        )

        # Get paginated results with student count
        query = (
            select(Guardian, student_count_subq.label("student_count"))
            .where(and_(*conditions))
            .order_by(Guardian.last_name, Guardian.first_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        rows = result.all()

        # Convert to list of dicts with student_count
        guardians_with_counts = []
        for row in rows:
            guardian = row[0]
            student_count = row[1] or 0
            guardian_dict = {
                "id": guardian.id,
                "first_name": guardian.first_name,
                "last_name": guardian.last_name,
                "phone": guardian.phone,
                "phone_secondary": guardian.phone_secondary,
                "email": guardian.email,
                "address": guardian.address,
                "city": guardian.city,
                "region": guardian.region,
                "occupation": guardian.occupation,
                "workplace": guardian.workplace,
                "work_phone": guardian.work_phone,
                "ghana_card_number": guardian.ghana_card_number,
                "photo_url": guardian.photo_url,
                "notes": guardian.notes,
                "created_at": guardian.created_at,
                "updated_at": guardian.updated_at,
                "student_count": student_count,
            }
            guardians_with_counts.append(guardian_dict)

        return guardians_with_counts, total

    async def update_guardian(
        self, tenant_id: UUID, guardian_id: UUID, **kwargs
    ) -> Optional[Guardian]:
        """Update a guardian."""
        guardian = await self.get_guardian(tenant_id, guardian_id)
        if not guardian:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(guardian, key):
                setattr(guardian, key, value)

        guardian.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(guardian)
        return guardian

    async def get_guardian_linked_students_count(self, tenant_id: UUID, guardian_id: UUID) -> int:
        """Get the count of students linked to a guardian."""
        result = await self.db.execute(
            select(func.count(StudentGuardian.id)).where(
                and_(
                    # Defense-in-depth: scope to tenant
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.guardian_id == guardian_id,
                )
            )
        )
        return result.scalar() or 0

    async def delete_guardian(self, tenant_id: UUID, guardian_id: UUID) -> bool:
        """
        Soft delete a guardian.

        Raises:
            StudentServiceError: If guardian has linked students
        """
        guardian = await self.get_guardian(tenant_id, guardian_id)
        if not guardian:
            return False

        # Check if guardian has linked students
        linked_count = await self.get_guardian_linked_students_count(tenant_id, guardian_id)
        if linked_count > 0:
            raise StudentServiceError(
                f"Cannot delete guardian with {linked_count} linked student(s). "
                "Please unlink all students first.",
                code="guardian_has_linked_students"
            )

        guardian.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    # =========================
    # Student-Guardian Link Methods
    # =========================

    async def link_guardian_to_student(
        self,
        tenant_id: UUID,
        student_id: UUID,
        guardian_id: UUID,
        relationship: str,
        is_primary: bool = False,
        is_emergency_contact: bool = True,
        can_pickup: bool = True,
    ) -> StudentGuardian:
        """Link an existing guardian to a student."""
        # Verify student and guardian exist (tenant-scoped for defense-in-depth)
        student = await self.get_student(tenant_id, student_id)
        guardian = await self.get_guardian(tenant_id, guardian_id)

        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")
        if not guardian:
            raise StudentServiceError("Guardian not found", code="guardian_not_found")

        # Check for existing link
        existing = await self.db.execute(
            select(StudentGuardian).where(
                and_(
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.student_id == student_id,
                    StudentGuardian.guardian_id == guardian_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StudentServiceError(
                "Guardian is already linked to this student",
                code="duplicate_link",
            )

        # If setting as primary, unset other primary guardians
        if is_primary:
            await self._unset_primary_guardian(tenant_id, student_id)

        link = StudentGuardian(
            tenant_id=tenant_id,
            student_id=student_id,
            guardian_id=guardian_id,
            relation_type=GuardianRelationship(relationship),
            is_primary=is_primary,
            is_emergency_contact=is_emergency_contact,
            can_pickup=can_pickup,
        )
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def update_student_guardian_link(
        self,
        link_id: UUID,
        tenant_id: UUID,
        student_id: UUID,
        **kwargs,
    ) -> Optional[StudentGuardian]:
        """Update a student-guardian link."""
        result = await self.db.execute(
            select(StudentGuardian).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.id == link_id,
                    # IDOR check: verify link belongs to the expected student
                    StudentGuardian.student_id == student_id,
                )
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            return None

        # Handle relationship enum conversion (API uses 'relationship', model uses 'relation_type')
        if "relationship" in kwargs and kwargs["relationship"]:
            kwargs["relation_type"] = GuardianRelationship(kwargs["relationship"])
            del kwargs["relationship"]

        # If setting as primary, unset other primary guardians
        if kwargs.get("is_primary"):
            await self._unset_primary_guardian(tenant_id, student_id)

        for key, value in kwargs.items():
            if value is not None and hasattr(link, key):
                setattr(link, key, value)

        link.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def unlink_guardian_from_student(
        self, tenant_id: UUID, student_id: UUID, guardian_id: UUID
    ) -> bool:
        """Remove a guardian link from a student."""
        result = await self.db.execute(
            select(StudentGuardian).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.student_id == student_id,
                    StudentGuardian.guardian_id == guardian_id,
                )
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            return False

        await self.db.delete(link)
        await self.db.flush()
        return True

    async def get_student_guardians(
        self, tenant_id: UUID, student_id: UUID
    ) -> Sequence[StudentGuardian]:
        """Get all guardians linked to a student."""
        result = await self.db.execute(
            select(StudentGuardian)
            .where(
                and_(
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.student_id == student_id,
                )
            )
            .options(selectinload(StudentGuardian.guardian_rel))
        )
        return result.scalars().all()

    async def get_guardian_students(
        self, tenant_id: UUID, guardian_id: UUID
    ) -> Sequence[StudentGuardian]:
        """Get all students linked to a guardian."""
        result = await self.db.execute(
            select(StudentGuardian)
            .where(
                and_(
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.guardian_id == guardian_id,
                )
            )
            .options(
                selectinload(StudentGuardian.student_rel)
                .selectinload(Student.class_),
                selectinload(StudentGuardian.student_rel)
                .selectinload(Student.section),
            )
        )
        return result.scalars().all()

    async def _unset_primary_guardian(
        self, tenant_id: UUID, student_id: UUID
    ) -> None:
        """Unset primary flag for all guardians of a student."""
        result = await self.db.execute(
            select(StudentGuardian).where(
                and_(
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.student_id == student_id,
                    StudentGuardian.is_primary == True,
                )
            )
        )
        for link in result.scalars().all():
            link.is_primary = False
