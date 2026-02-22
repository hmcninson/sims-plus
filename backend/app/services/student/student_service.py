"""
SIMS Plus - Student Core Service

Student CRUD operations, ID generation, stats, and bulk creation.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.student import (
    Student,
    StudentStatus,
    Gender,
    Guardian,
    StudentGuardian,
    GuardianRelationship,
)
from app.models.academic import Class, ClassSection
from app.utils.sanitize import escape_ilike

from app.services.student._shared import StudentServiceError


class StudentCoreMixin:
    """Mixin providing core student CRUD operations."""

    # Type hints for self.db -- set by StudentService.__init__
    db: AsyncSession

    # =========================
    # Student Methods
    # =========================

    async def create_student(
        self,
        tenant_id: UUID,
        student_id: str,
        first_name: str,
        last_name: str,
        date_of_birth,
        gender: str,
        middle_name: Optional[str] = None,
        previous_student_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        ghana_card_number: Optional[str] = None,
        nhis_number: Optional[str] = None,
        school_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        admission_date=None,
        admission_number: Optional[str] = None,
        status: str = "active",
        is_boarder: bool = False,
        blood_group: Optional[str] = None,
        medical_conditions: Optional[str] = None,
        allergies: Optional[str] = None,
        photo_url: Optional[str] = None,
        notes: Optional[str] = None,
        guardians: Optional[list[dict]] = None,
    ) -> Student:
        """Create a new student."""
        # Check for duplicate student_id
        existing = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.student_id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StudentServiceError(
                f"Student ID '{student_id}' already exists",
                code="duplicate_student_id",
            )

        student = Student(
            tenant_id=tenant_id,
            student_id=student_id,
            previous_student_id=previous_student_id,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=Gender(gender),
            email=email,
            phone=phone,
            address=address,
            city=city,
            region=region,
            ghana_card_number=ghana_card_number,
            nhis_number=nhis_number,
            school_id=school_id,
            class_id=class_id,
            section_id=section_id,
            admission_date=admission_date,
            admission_number=admission_number,
            status=StudentStatus(status),
            is_boarder=is_boarder,
            blood_group=blood_group,
            medical_conditions=medical_conditions,
            allergies=allergies,
            photo_url=photo_url,
            notes=notes,
        )
        self.db.add(student)
        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_students_student_id_tenant" in error_msg or "student_id" in error_msg.lower():
                raise StudentServiceError(
                    f"Student ID '{student_id}' already exists (concurrent creation detected)",
                    code="duplicate_student_id",
                )
            raise StudentServiceError(
                f"Database error while creating student: {error_msg}",
                code="database_error",
            )

        # Create guardians if provided
        if guardians:
            for guardian_data in guardians:
                # Create the guardian
                guardian = Guardian(
                    tenant_id=tenant_id,
                    first_name=guardian_data["guardian"]["first_name"],
                    last_name=guardian_data["guardian"]["last_name"],
                    phone=guardian_data["guardian"]["phone"],
                    phone_secondary=guardian_data["guardian"].get("phone_secondary"),
                    email=guardian_data["guardian"].get("email"),
                    address=guardian_data["guardian"].get("address"),
                    city=guardian_data["guardian"].get("city"),
                    region=guardian_data["guardian"].get("region"),
                    occupation=guardian_data["guardian"].get("occupation"),
                    workplace=guardian_data["guardian"].get("workplace"),
                    work_phone=guardian_data["guardian"].get("work_phone"),
                    ghana_card_number=guardian_data["guardian"].get("ghana_card_number"),
                    photo_url=guardian_data["guardian"].get("photo_url"),
                    notes=guardian_data["guardian"].get("notes"),
                )
                self.db.add(guardian)
                await self.db.flush()

                # Link guardian to student
                student_guardian = StudentGuardian(
                    tenant_id=tenant_id,
                    student_id=student.id,
                    guardian_id=guardian.id,
                    relation_type=GuardianRelationship(guardian_data["relationship"]),
                    is_primary=guardian_data.get("is_primary", False),
                    is_emergency_contact=guardian_data.get("is_emergency_contact", True),
                    can_pickup=guardian_data.get("can_pickup", True),
                )
                self.db.add(student_guardian)

        await self.db.flush()
        await self.db.refresh(student)
        return student

    async def get_student(
        self, tenant_id: UUID, student_id: UUID, include_guardians: bool = False
    ) -> Optional[Student]:
        """Get student by ID with related class, section, and school."""
        query = select(Student).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
        )
        # Always load class/section/school for the detail view
        query = query.options(
            selectinload(Student.class_),
            selectinload(Student.section),
            selectinload(Student.school),
        )
        if include_guardians:
            query = query.options(
                selectinload(Student.guardians).selectinload(StudentGuardian.guardian_rel)
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_student_by_student_id(
        self, tenant_id: UUID, student_id: str
    ) -> Optional[Student]:
        """Get student by student ID (the school-assigned ID)."""
        result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.student_id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_students(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        school_id: Optional[UUID] = None,
        status: Optional[str] = None,
        gender: Optional[str] = None,
        is_boarder: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Student], int]:
        """List students with filters and pagination."""
        conditions = [
            Student.tenant_id == tenant_id,
            Student.deleted_at.is_(None),
        ]

        if search:
            # Escape ILIKE wildcards to prevent wildcard injection
            search_term = f"%{escape_ilike(search)}%"
            conditions.append(
                or_(
                    Student.first_name.ilike(search_term),
                    Student.last_name.ilike(search_term),
                    Student.middle_name.ilike(search_term),
                    Student.student_id.ilike(search_term),
                )
            )

        if class_id:
            conditions.append(Student.class_id == class_id)
        if section_id:
            conditions.append(Student.section_id == section_id)
        if school_id:
            conditions.append(Student.school_id == school_id)
        if status:
            conditions.append(Student.status == StudentStatus(status))
        if gender:
            conditions.append(Student.gender == Gender(gender))
        if is_boarder is not None:
            conditions.append(Student.is_boarder == is_boarder)

        # Get total count
        count_query = select(func.count(Student.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Get paginated results
        query = (
            select(Student)
            .where(and_(*conditions))
            .options(
                selectinload(Student.class_),
                selectinload(Student.section),
            )
            .order_by(Student.last_name, Student.first_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        students = result.scalars().all()

        return students, total

    async def update_student(
        self, tenant_id: UUID, student_id: UUID, **kwargs
    ) -> Optional[Student]:
        """Update a student."""
        student = await self.get_student(tenant_id, student_id)
        if not student:
            return None

        # Handle enum conversions
        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = StudentStatus(kwargs["status"])
        if "gender" in kwargs and kwargs["gender"]:
            kwargs["gender"] = Gender(kwargs["gender"])

        for key, value in kwargs.items():
            if value is not None and hasattr(student, key):
                setattr(student, key, value)

        student.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(student)
        return student

    async def delete_student(self, tenant_id: UUID, student_id: UUID) -> bool:
        """Soft delete a student."""
        student = await self.get_student(tenant_id, student_id)
        if not student:
            return False

        student.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def generate_student_id(
        self, tenant_id: UUID, prefix: str = "STU", max_retries: int = 10
    ) -> str:
        """
        Generate a unique student ID for the tenant.

        Format: {PREFIX}-{YEAR}-{SEQUENCE}
        Example: STU-2026-001, STU-2026-002

        This method finds the highest existing sequence number for the given
        prefix and year pattern, then increments it. It includes retry logic
        for race condition protection.

        Args:
            tenant_id: The tenant UUID
            prefix: The student ID prefix (default: STU)
            max_retries: Maximum number of retry attempts for race conditions

        Returns:
            A unique student ID string

        Raises:
            StudentServiceError: If unable to generate unique ID after max retries
        """
        import re

        current_year = datetime.now().year
        pattern = f"{prefix}-{current_year}-%"

        # Find the highest existing sequence number for this prefix and year
        # This query finds all student IDs matching the pattern and extracts the max sequence
        result = await self.db.execute(
            select(Student.student_id).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.student_id.like(pattern),
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
            # Format: PREFIX-YEAR-SEQUENCE (3 digits minimum, auto-expand if needed)
            if next_seq < 1000:
                student_id = f"{prefix}-{current_year}-{next_seq:03d}"
            else:
                # Support larger schools with more than 999 students
                student_id = f"{prefix}-{current_year}-{next_seq}"

            # Check if this ID already exists (including soft-deleted for safety)
            existing = await self.db.execute(
                select(Student.id).where(
                    and_(
                        Student.tenant_id == tenant_id,
                        Student.student_id == student_id,
                    )
                )
            )
            if not existing.scalar_one_or_none():
                return student_id

            # ID exists, try next sequence number
            next_seq += 1

        # If we've exhausted all retries, raise an error
        raise StudentServiceError(
            f"Unable to generate unique student ID after {max_retries} attempts. "
            f"Please try again or assign a student ID manually.",
            code="id_generation_failed",
        )

    async def get_student_stats(self, tenant_id: UUID) -> dict:
        """Get student statistics for a tenant."""
        base_conditions = [
            Student.tenant_id == tenant_id,
            Student.deleted_at.is_(None),
        ]

        # Total count
        total = (
            await self.db.execute(
                select(func.count(Student.id)).where(and_(*base_conditions))
            )
        ).scalar_one()

        # By status
        status_counts = {}
        for status in StudentStatus:
            count = (
                await self.db.execute(
                    select(func.count(Student.id)).where(
                        and_(*base_conditions, Student.status == status)
                    )
                )
            ).scalar_one()
            status_counts[status.value] = count

        # By gender
        male_count = (
            await self.db.execute(
                select(func.count(Student.id)).where(
                    and_(*base_conditions, Student.gender == Gender.MALE)
                )
            )
        ).scalar_one()

        female_count = (
            await self.db.execute(
                select(func.count(Student.id)).where(
                    and_(*base_conditions, Student.gender == Gender.FEMALE)
                )
            )
        ).scalar_one()

        # Boarders vs day students
        boarder_count = (
            await self.db.execute(
                select(func.count(Student.id)).where(
                    and_(*base_conditions, Student.is_boarder == True)
                )
            )
        ).scalar_one()

        return {
            "total": total,
            "active": status_counts.get("active", 0),
            "inactive": status_counts.get("inactive", 0),
            "graduated": status_counts.get("graduated", 0),
            "transferred": status_counts.get("transferred", 0),
            "withdrawn": status_counts.get("withdrawn", 0),
            "suspended": status_counts.get("suspended", 0),
            "male": male_count,
            "female": female_count,
            "boarders": boarder_count,
            "day_students": total - boarder_count,
        }

    async def bulk_create_students(
        self,
        tenant_id: UUID,
        students_data: list[dict],
    ) -> dict:
        """Bulk create students."""
        created = 0
        failed = 0
        errors = []

        for i, student_data in enumerate(students_data):
            try:
                await self.create_student(
                    tenant_id=tenant_id,
                    **student_data,
                )
                created += 1
            except StudentServiceError as e:
                failed += 1
                errors.append({
                    "index": i,
                    "student_id": student_data.get("student_id"),
                    "error": e.message,
                })
            except Exception as e:
                failed += 1
                errors.append({
                    "index": i,
                    "student_id": student_data.get("student_id"),
                    "error": str(e),
                })

        return {
            "created": created,
            "failed": failed,
            "errors": errors,
        }

    async def promote_students(
        self,
        tenant_id: UUID,
        from_class_id: UUID,
        to_class_id: UUID,
        student_ids: list[UUID],
    ) -> dict:
        """Promote students from one class to another."""
        from app.models.academic import Class as ClassModel

        # Validate from_class belongs to tenant
        from_class = (
            await self.db.execute(
                select(ClassModel).where(
                    and_(
                        ClassModel.id == from_class_id,
                        ClassModel.tenant_id == tenant_id,
                        ClassModel.deleted_at.is_(None),
                    )
                )
            )
        ).scalar_one_or_none()
        if not from_class:
            raise StudentServiceError("Source class not found", code="class_not_found")

        # Validate to_class belongs to tenant
        to_class = (
            await self.db.execute(
                select(ClassModel).where(
                    and_(
                        ClassModel.id == to_class_id,
                        ClassModel.tenant_id == tenant_id,
                        ClassModel.deleted_at.is_(None),
                    )
                )
            )
        ).scalar_one_or_none()
        if not to_class:
            raise StudentServiceError("Target class not found", code="class_not_found")

        promoted = 0
        failed = 0
        errors = []

        for sid in student_ids:
            student_result = await self.db.execute(
                select(Student).where(
                    and_(
                        Student.id == sid,
                        Student.tenant_id == tenant_id,
                        Student.class_id == from_class_id,
                        Student.deleted_at.is_(None),
                    )
                )
            )
            student = student_result.scalar_one_or_none()
            if not student:
                failed += 1
                errors.append({"student_id": str(sid), "error": "Student not found in source class"})
                continue

            student.class_id = to_class_id
            # Clear section on promotion since sections differ between classes
            student.section_id = None
            promoted += 1

        await self.db.flush()

        return {"promoted": promoted, "failed": failed, "errors": errors}

    async def export_students_csv(
        self,
        tenant_id: UUID,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Export students as list of dicts for CSV writer."""
        conditions = [
            Student.tenant_id == tenant_id,
            Student.deleted_at.is_(None),
        ]
        if class_id:
            conditions.append(Student.class_id == class_id)
        if section_id:
            conditions.append(Student.section_id == section_id)

        query = (
            select(Student)
            .where(and_(*conditions))
            .options(
                selectinload(Student.class_),
                selectinload(Student.section),
            )
            .order_by(Student.last_name, Student.first_name)
        )
        result = await self.db.execute(query)
        students = result.scalars().all()

        return [
            {
                "student_id": s.student_id,
                "first_name": s.first_name,
                "middle_name": s.middle_name or "",
                "last_name": s.last_name,
                "date_of_birth": str(s.date_of_birth) if s.date_of_birth else "",
                "gender": s.gender.value if s.gender else "",
                "email": s.email or "",
                "phone": s.phone or "",
                "address": s.address or "",
                "city": s.city or "",
                "region": s.region or "",
                "class_name": s.class_.name if s.class_ else "",
                "section_name": s.section.name if s.section else "",
                "status": s.status.value if s.status else "",
            }
            for s in students
        ]
