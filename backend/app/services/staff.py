"""
SIMS Plus - Staff Service

Business logic for staff management.
"""

from datetime import datetime, UTC, date
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.staff import (
    Staff,
    StaffType,
    StaffStatus,
    StaffClassAssignment,
)
from app.models.student import Gender
from app.models.academic import ClassSection, Subject


class StaffServiceError(Exception):
    """Base exception for staff service errors."""

    def __init__(self, message: str, code: str = "staff_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class StaffService:
    """Service for managing staff members."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Staff Methods
    # =========================

    async def create_staff(
        self,
        tenant_id: UUID,
        staff_id: str,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        gender: str,
        job_title: str,
        employment_date: date,
        middle_name: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        phone_secondary: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
        emergency_contact_relationship: Optional[str] = None,
        ghana_card_number: Optional[str] = None,
        ssnit_number: Optional[str] = None,
        teacher_license_number: Optional[str] = None,
        staff_type: str = "teaching",
        status: str = "active",
        department: Optional[str] = None,
        termination_date: Optional[date] = None,
        qualifications: Optional[list] = None,
        bank_name: Optional[str] = None,
        bank_branch: Optional[str] = None,
        account_number: Optional[str] = None,
        photo_url: Optional[str] = None,
        notes: Optional[str] = None,
        school_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> Staff:
        """Create a new staff member."""
        # Check for duplicate staff_id
        existing = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.staff_id == staff_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StaffServiceError(
                f"Staff ID '{staff_id}' already exists",
                code="duplicate_staff_id",
            )

        # Check for duplicate email
        existing_email = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.email == email,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        if existing_email.scalar_one_or_none():
            raise StaffServiceError(
                f"A staff member with email '{email}' already exists",
                code="duplicate_staff_email",
            )

        staff = Staff(
            tenant_id=tenant_id,
            staff_id=staff_id,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=Gender(gender),
            email=email,
            phone=phone,
            phone_secondary=phone_secondary,
            address=address,
            city=city,
            region=region,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relationship=emergency_contact_relationship,
            ghana_card_number=ghana_card_number,
            ssnit_number=ssnit_number,
            teacher_license_number=teacher_license_number,
            staff_type=StaffType(staff_type),
            status=StaffStatus(status),
            job_title=job_title,
            department=department,
            employment_date=employment_date,
            termination_date=termination_date,
            qualifications=qualifications or [],
            bank_name=bank_name,
            bank_branch=bank_branch,
            account_number=account_number,
            photo_url=photo_url,
            notes=notes,
            school_id=school_id,
            user_id=user_id,
        )
        self.db.add(staff)
        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_staff_staff_id_tenant" in error_msg or "staff_id" in error_msg.lower():
                raise StaffServiceError(
                    f"Staff ID '{staff_id}' already exists (concurrent creation detected)",
                    code="duplicate_staff_id",
                )
            if "uq_staff_email_tenant" in error_msg or "email" in error_msg.lower():
                raise StaffServiceError(
                    f"Email '{email}' already exists (concurrent creation detected)",
                    code="duplicate_staff_email",
                )
            raise StaffServiceError(
                f"Database error while creating staff: {error_msg}",
                code="database_error",
            )

        await self.db.commit()
        await self.db.refresh(staff)
        return staff

    async def get_staff(
        self, staff_id: UUID, include_assignments: bool = False
    ) -> Optional[Staff]:
        """Get staff by ID."""
        query = select(Staff).where(
            and_(
                Staff.id == staff_id,
                Staff.deleted_at.is_(None),
            )
        )
        if include_assignments:
            query = query.options(
                selectinload(Staff.class_assignments).selectinload(StaffClassAssignment.section)
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_staff_by_staff_id(
        self, tenant_id: UUID, staff_id: str
    ) -> Optional[Staff]:
        """Get staff by staff ID (the school-assigned ID)."""
        result = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.staff_id == staff_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_staff_by_user_id(
        self, tenant_id: UUID, user_id: UUID
    ) -> Optional[Staff]:
        """Get staff by linked user ID."""
        result = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.user_id == user_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_staff(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
        staff_type: Optional[str] = None,
        status: Optional[str] = None,
        gender: Optional[str] = None,
        department: Optional[str] = None,
        school_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Staff], int]:
        """List staff with filters and pagination."""
        conditions = [
            Staff.tenant_id == tenant_id,
            Staff.deleted_at.is_(None),
        ]

        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    Staff.first_name.ilike(search_term),
                    Staff.last_name.ilike(search_term),
                    Staff.middle_name.ilike(search_term),
                    Staff.staff_id.ilike(search_term),
                    Staff.email.ilike(search_term),
                    Staff.job_title.ilike(search_term),
                )
            )

        if staff_type:
            conditions.append(Staff.staff_type == StaffType(staff_type))
        if status:
            conditions.append(Staff.status == StaffStatus(status))
        if gender:
            conditions.append(Staff.gender == Gender(gender))
        if department:
            conditions.append(Staff.department.ilike(f"%{department}%"))
        if school_id:
            conditions.append(Staff.school_id == school_id)

        # Get total count
        count_query = select(func.count(Staff.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Get paginated results
        query = (
            select(Staff)
            .where(and_(*conditions))
            .options(selectinload(Staff.school))
            .order_by(Staff.last_name, Staff.first_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        staff_list = result.scalars().all()

        return staff_list, total

    async def update_staff(
        self, staff_id: UUID, **kwargs
    ) -> Optional[Staff]:
        """Update a staff member."""
        staff = await self.get_staff(staff_id)
        if not staff:
            return None

        # Handle enum conversions
        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = StaffStatus(kwargs["status"])
        if "gender" in kwargs and kwargs["gender"]:
            kwargs["gender"] = Gender(kwargs["gender"])
        if "staff_type" in kwargs and kwargs["staff_type"]:
            kwargs["staff_type"] = StaffType(kwargs["staff_type"])

        for key, value in kwargs.items():
            if value is not None and hasattr(staff, key):
                setattr(staff, key, value)

        staff.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(staff)
        return staff

    async def delete_staff(self, staff_id: UUID) -> bool:
        """Soft delete a staff member."""
        staff = await self.get_staff(staff_id)
        if not staff:
            return False

        staff.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def generate_staff_id(
        self, tenant_id: UUID, prefix: str = "STF", max_retries: int = 10
    ) -> str:
        """
        Generate a unique staff ID for the tenant.

        Format: {PREFIX}-{YEAR}-{SEQUENCE}
        Example: STF-2026-001, STF-2026-002
        """
        import re

        current_year = datetime.now().year
        pattern = f"{prefix}-{current_year}-%"

        # Find the highest existing sequence number for this prefix and year
        result = await self.db.execute(
            select(Staff.staff_id).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.staff_id.like(pattern),
                )
            )
        )
        existing_ids = result.scalars().all()

        # Extract sequence numbers from existing IDs
        max_seq = 0
        seq_pattern = re.compile(rf"^{re.escape(prefix)}-{current_year}-(\d+)$")
        for existing_id in existing_ids:
            match = seq_pattern.match(existing_id)
            if match:
                seq = int(match.group(1))
                if seq > max_seq:
                    max_seq = seq

        # Start from the next sequence number
        next_seq = max_seq + 1

        # Retry loop for race condition protection
        for attempt in range(max_retries):
            # Format: PREFIX-YEAR-SEQUENCE (3 digits minimum)
            if next_seq < 1000:
                new_staff_id = f"{prefix}-{current_year}-{next_seq:03d}"
            else:
                new_staff_id = f"{prefix}-{current_year}-{next_seq}"

            # Check if this ID already exists
            existing = await self.db.execute(
                select(Staff.id).where(
                    and_(
                        Staff.tenant_id == tenant_id,
                        Staff.staff_id == new_staff_id,
                    )
                )
            )
            if not existing.scalar_one_or_none():
                return new_staff_id

            next_seq += 1

        raise StaffServiceError(
            f"Unable to generate unique staff ID after {max_retries} attempts.",
            code="id_generation_failed",
        )

    async def get_staff_stats(self, tenant_id: UUID) -> dict:
        """Get staff statistics for a tenant."""
        base_conditions = [
            Staff.tenant_id == tenant_id,
            Staff.deleted_at.is_(None),
        ]

        # Total count
        total = (
            await self.db.execute(
                select(func.count(Staff.id)).where(and_(*base_conditions))
            )
        ).scalar_one()

        # By status
        status_counts = {}
        for status in StaffStatus:
            count = (
                await self.db.execute(
                    select(func.count(Staff.id)).where(
                        and_(*base_conditions, Staff.status == status)
                    )
                )
            ).scalar_one()
            status_counts[status.value] = count

        # By type
        type_counts = {}
        for staff_type in StaffType:
            count = (
                await self.db.execute(
                    select(func.count(Staff.id)).where(
                        and_(*base_conditions, Staff.staff_type == staff_type)
                    )
                )
            ).scalar_one()
            type_counts[staff_type.value] = count

        # By gender
        male_count = (
            await self.db.execute(
                select(func.count(Staff.id)).where(
                    and_(*base_conditions, Staff.gender == Gender.MALE)
                )
            )
        ).scalar_one()

        female_count = (
            await self.db.execute(
                select(func.count(Staff.id)).where(
                    and_(*base_conditions, Staff.gender == Gender.FEMALE)
                )
            )
        ).scalar_one()

        return {
            "total": total,
            "active": status_counts.get("active", 0),
            "on_leave": status_counts.get("on_leave", 0),
            "suspended": status_counts.get("suspended", 0),
            "terminated": status_counts.get("terminated", 0),
            "retired": status_counts.get("retired", 0),
            "teaching": type_counts.get("teaching", 0),
            "non_teaching": type_counts.get("non_teaching", 0),
            "administrative": type_counts.get("administrative", 0),
            "male": male_count,
            "female": female_count,
        }

    # =========================
    # Staff Class Assignment Methods
    # =========================

    async def assign_staff_to_section(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        section_id: UUID,
        is_class_teacher: bool = False,
        subject_id: Optional[UUID] = None,
    ) -> StaffClassAssignment:
        """Assign a staff member to a class section."""
        # Verify staff exists
        staff = await self.get_staff(staff_id)
        if not staff:
            raise StaffServiceError("Staff member not found", code="staff_not_found")

        # Verify section exists
        section_result = await self.db.execute(
            select(ClassSection).where(
                and_(
                    ClassSection.id == section_id,
                    ClassSection.tenant_id == tenant_id,
                    ClassSection.deleted_at.is_(None),
                )
            )
        )
        if not section_result.scalar_one_or_none():
            raise StaffServiceError("Class section not found", code="section_not_found")

        # Check for existing assignment
        existing = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.section_id == section_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StaffServiceError(
                "Staff is already assigned to this section",
                code="duplicate_assignment",
            )

        # If setting as class teacher, unset other class teachers for this section
        if is_class_teacher:
            await self._unset_class_teacher(tenant_id, section_id)

        assignment = StaffClassAssignment(
            tenant_id=tenant_id,
            staff_id=staff_id,
            section_id=section_id,
            is_class_teacher=is_class_teacher,
            subject_id=subject_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def update_staff_assignment(
        self,
        assignment_id: UUID,
        tenant_id: UUID,
        **kwargs,
    ) -> Optional[StaffClassAssignment]:
        """Update a staff class assignment."""
        result = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.id == assignment_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return None

        # If setting as class teacher, unset other class teachers for this section
        if kwargs.get("is_class_teacher"):
            await self._unset_class_teacher(tenant_id, assignment.section_id)

        for key, value in kwargs.items():
            if value is not None and hasattr(assignment, key):
                setattr(assignment, key, value)

        assignment.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def remove_staff_from_section(
        self, tenant_id: UUID, staff_id: UUID, section_id: UUID
    ) -> bool:
        """Remove a staff assignment from a section."""
        result = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.section_id == section_id,
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.commit()
        return True

    async def get_staff_assignments(
        self, tenant_id: UUID, staff_id: UUID
    ) -> Sequence[StaffClassAssignment]:
        """Get all class assignments for a staff member."""
        result = await self.db.execute(
            select(StaffClassAssignment)
            .where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.staff_id == staff_id,
                )
            )
            .options(
                selectinload(StaffClassAssignment.section),
            )
        )
        return result.scalars().all()

    async def get_section_staff(
        self, tenant_id: UUID, section_id: UUID
    ) -> Sequence[StaffClassAssignment]:
        """Get all staff assigned to a section."""
        result = await self.db.execute(
            select(StaffClassAssignment)
            .where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.section_id == section_id,
                )
            )
            .options(
                selectinload(StaffClassAssignment.staff),
            )
        )
        return result.scalars().all()

    async def get_class_teacher(
        self, tenant_id: UUID, section_id: UUID
    ) -> Optional[Staff]:
        """Get the class teacher for a section."""
        result = await self.db.execute(
            select(StaffClassAssignment)
            .where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.section_id == section_id,
                    StaffClassAssignment.is_class_teacher == True,
                )
            )
            .options(selectinload(StaffClassAssignment.staff))
        )
        assignment = result.scalar_one_or_none()
        return assignment.staff if assignment else None

    async def _unset_class_teacher(
        self, tenant_id: UUID, section_id: UUID
    ) -> None:
        """Unset class teacher flag for all staff in a section."""
        result = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.section_id == section_id,
                    StaffClassAssignment.is_class_teacher == True,
                )
            )
        )
        for assignment in result.scalars().all():
            assignment.is_class_teacher = False

    # =========================
    # Teaching Staff Specific Methods
    # =========================

    async def get_teaching_staff(
        self, tenant_id: UUID, school_id: Optional[UUID] = None
    ) -> Sequence[Staff]:
        """Get all active teaching staff."""
        conditions = [
            Staff.tenant_id == tenant_id,
            Staff.staff_type == StaffType.TEACHING,
            Staff.status == StaffStatus.ACTIVE,
            Staff.deleted_at.is_(None),
        ]
        if school_id:
            conditions.append(Staff.school_id == school_id)

        result = await self.db.execute(
            select(Staff)
            .where(and_(*conditions))
            .order_by(Staff.last_name, Staff.first_name)
        )
        return result.scalars().all()
