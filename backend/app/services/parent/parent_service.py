"""
SIMS Plus - Core Parent Service

Core parent data access layer: child resolution, access verification, and child details.

The parent-to-student link is resolved through email matching:
  User.email == Guardian.email (within the same tenant)
because the Guardian model has no direct user_id foreign key.

All methods that return student data enforce parent-child access verification
to ensure parents can only see their own children.
"""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicYear, Term
from app.models.school import School
from app.models.student import Guardian, Student, StudentGuardian
from app.models.user import User

from app.services.parent._shared import ParentServiceError

logger = structlog.get_logger()


class ParentService:
    """
    Core service for parent portal data access.

    Resolves the parent-to-student relationship via email matching
    (User.email == Guardian.email within the same tenant) and provides
    access verification gates used by all other parent services.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_guardian_for_user(
        self, user_id: UUID, tenant_id: UUID
    ) -> Optional[Guardian]:
        """
        Find the guardian record associated with a user account.

        The link is: User.email == Guardian.email within the same tenant.
        Returns the guardian or None if no matching guardian exists.
        """
        result = await self.db.execute(
            select(Guardian)
            .join(User, and_(
                Guardian.email == User.email,
                # Defense-in-depth: both user and guardian must belong to same tenant
                Guardian.tenant_id == User.tenant_id,
            ))
            .where(
                and_(
                    User.id == user_id,
                    User.tenant_id == tenant_id,
                    Guardian.tenant_id == tenant_id,
                    Guardian.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_my_children(
        self, user_id: UUID, tenant_id: UUID
    ) -> list[Student]:
        """
        Get all students linked to this parent via email-matched guardian records.

        Query flow:
        1. Find guardian where Guardian.email == User.email (same tenant)
        2. Follow student_guardians junction to get linked students
        3. Return only active, non-deleted students

        Args:
            user_id: The authenticated user's ID
            tenant_id: The tenant ID (defense-in-depth with RLS)

        Returns:
            List of Student objects with class_ and section relationships loaded
        """
        result = await self.db.execute(
            select(Student)
            .join(StudentGuardian, Student.id == StudentGuardian.student_id)
            .join(Guardian, StudentGuardian.guardian_id == Guardian.id)
            .join(User, and_(
                Guardian.email == User.email,
                Guardian.tenant_id == User.tenant_id,
            ))
            .where(
                and_(
                    User.id == user_id,
                    # Defense-in-depth: scope everything to tenant
                    Student.tenant_id == tenant_id,
                    StudentGuardian.tenant_id == tenant_id,
                    Guardian.tenant_id == tenant_id,
                    User.tenant_id == tenant_id,
                    # Exclude soft-deleted records
                    Student.deleted_at.is_(None),
                    Guardian.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Student.class_),
                selectinload(Student.section),
                # Load school for chain tenants where children attend different schools
                selectinload(Student.school),
            )
            .order_by(Student.last_name, Student.first_name)
        )
        return list(result.scalars().unique().all())

    async def verify_parent_child_access(
        self, user_id: UUID, student_id: UUID, tenant_id: UUID
    ) -> bool:
        """
        SECURITY GATE: Verify that this user is a guardian of the specified student.

        Returns True only if an active guardian link exists between the user
        (via email matching) and the student within the same tenant.

        This method is called by ALL parent service methods before returning
        any student-specific data. Returns False (does not raise) so callers
        can convert to HTTP 403.

        Args:
            user_id: The authenticated user's ID
            student_id: The student ID to verify access for
            tenant_id: The tenant ID (defense-in-depth with RLS)

        Returns:
            True if access is allowed, False otherwise
        """
        result = await self.db.execute(
            select(
                exists(
                    select(StudentGuardian.id)
                    .join(Guardian, StudentGuardian.guardian_id == Guardian.id)
                    .join(User, and_(
                        Guardian.email == User.email,
                        Guardian.tenant_id == User.tenant_id,
                    ))
                    .where(
                        and_(
                            User.id == user_id,
                            StudentGuardian.student_id == student_id,
                            # Defense-in-depth: full tenant scoping
                            StudentGuardian.tenant_id == tenant_id,
                            Guardian.tenant_id == tenant_id,
                            User.tenant_id == tenant_id,
                            # Exclude soft-deleted
                            Guardian.deleted_at.is_(None),
                            User.deleted_at.is_(None),
                        )
                    )
                )
            )
        )
        return result.scalar() or False

    async def require_parent_child_access(
        self, user_id: UUID, student_id: UUID, tenant_id: UUID
    ) -> None:
        """
        Convenience wrapper that raises ParentServiceError if access is denied.

        Used internally by other parent services to gate access before
        returning any student data.

        Raises:
            ParentServiceError: With code "access_denied" and status-appropriate code
        """
        has_access = await self.verify_parent_child_access(
            user_id, student_id, tenant_id
        )
        if not has_access:
            raise ParentServiceError(
                "You do not have access to this student's records",
                code="access_denied",
            )

    async def get_child_detail(
        self, user_id: UUID, student_id: UUID, tenant_id: UUID
    ) -> dict:
        """
        Get detailed child info after verifying parent access.

        Includes: student profile, class, section, class teacher name,
        current term name, and academic year name.

        Args:
            user_id: The authenticated user's ID
            student_id: The student to retrieve
            tenant_id: The tenant ID (defense-in-depth with RLS)

        Returns:
            Dict with child detail fields matching ChildDetail schema

        Raises:
            ParentServiceError: If access denied or student not found
        """
        await self.require_parent_child_access(user_id, student_id, tenant_id)

        # Fetch student with class, section loaded
        result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Student.class_),
                selectinload(Student.section),
                selectinload(Student.school),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise ParentServiceError("Student not found", code="student_not_found")

        # Get current academic year and term
        current_year_name = None
        current_term_name = None
        current_year_result = await self.db.execute(
            select(AcademicYear)
            .where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.is_current == True,
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        current_year = current_year_result.scalar_one_or_none()
        if current_year:
            current_year_name = current_year.name

        current_term_result = await self.db.execute(
            select(Term)
            .where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.is_current == True,
                    Term.deleted_at.is_(None),
                )
            )
        )
        current_term = current_term_result.scalar_one_or_none()
        if current_term:
            current_term_name = current_term.name

        # Resolve class teacher name from section's class_teacher_id
        class_teacher_name = None
        if student.section and student.section.class_teacher_id:
            teacher_result = await self.db.execute(
                select(User.first_name, User.last_name)
                .where(
                    and_(
                        User.id == student.section.class_teacher_id,
                        User.tenant_id == tenant_id,
                        User.deleted_at.is_(None),
                    )
                )
            )
            teacher_row = teacher_result.one_or_none()
            if teacher_row:
                class_teacher_name = f"{teacher_row.first_name} {teacher_row.last_name}"

        return {
            "id": student.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "photo_url": student.photo_url,
            "class_name": student.class_.name if student.class_ else None,
            "section_name": student.section.name if student.section else None,
            "admission_number": student.admission_number,
            "date_of_birth": student.date_of_birth,
            "gender": student.gender.value if student.gender else None,
            "enrollment_status": student.status.value if student.status else None,
            "class_teacher_name": class_teacher_name,
            "current_term": current_term_name,
            "academic_year": current_year_name,
            "class_id": student.class_id,
            "section_id": student.section_id,
            # School context for chain tenants
            "school_id": student.school_id,
            "school_name": student.school.name if student.school else None,
        }
