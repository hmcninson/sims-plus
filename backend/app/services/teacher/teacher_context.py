"""
SIMS Plus - Teacher Context Service

Resolves the user-to-staff mapping and verifies that a teacher has
access to specific classes and subjects. This is the foundational
service that all other teacher services depend on for authorization.

Key resolution: User.id → Staff.user_id (1:1 link)
Access check: StaffClassAssignment + ClassTimetable + ClassSubject
"""

from uuid import UUID

import structlog
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    AcademicYear,
    Class,
    ClassSection,
    ClassSubject,
    ClassTimetable,
    Subject,
    Term,
)
from app.models.staff import Staff, StaffClassAssignment
from app.models.student import Student, StudentStatus

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherContextService:
    """
    Resolves teacher identity and verifies class/subject access.

    All teacher portal operations go through this service first to:
    1. Resolve user_id → staff record (via Staff.user_id)
    2. Verify the teacher is assigned to the requested class/subject
    3. Get the current academic year and term context
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_staff_for_user(
        self, user_id: UUID, tenant_id: UUID
    ) -> Staff:
        """
        Resolve a user account to its linked staff record.

        The Staff model has a user_id FK that links a staff record to a User
        for login access. This method finds that link.

        Note: Staff.user_id has a unique constraint, so there is at most one
        staff record per user per tenant. For chain tenants where a teacher
        works at multiple schools, school-level filtering happens downstream
        in class/subject queries, not here.

        Raises TeacherServiceError if no staff record is found, meaning
        the user does not have a teacher profile in this tenant.
        """
        result = await self.db.execute(
            select(Staff)
            .where(
                and_(
                    Staff.user_id == user_id,
                    Staff.tenant_id == tenant_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        staff = result.scalar_one_or_none()
        if not staff:
            raise TeacherServiceError(
                "No teacher profile found for this user",
                code="not_a_teacher",
            )
        return staff

    async def get_current_academic_year(
        self, tenant_id: UUID
    ) -> AcademicYear:
        """
        Get the current (is_current=True) academic year for this tenant.

        Raises TeacherServiceError if no current academic year is set,
        which typically means the school hasn't completed academic setup.
        """
        result = await self.db.execute(
            select(AcademicYear)
            .where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.is_current.is_(True),
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        year = result.scalar_one_or_none()
        if not year:
            raise TeacherServiceError(
                "No current academic year is set",
                code="no_academic_year",
            )
        return year

    async def get_current_term(
        self, tenant_id: UUID, academic_year_id: UUID
    ) -> Term:
        """
        Get the current (is_current=True) term within the given academic year.

        Raises TeacherServiceError if no current term is set.
        """
        result = await self.db.execute(
            select(Term)
            .where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.academic_year_id == academic_year_id,
                    Term.is_current.is_(True),
                    Term.deleted_at.is_(None),
                )
            )
        )
        term = result.scalar_one_or_none()
        if not term:
            raise TeacherServiceError(
                "No current term is set",
                code="no_current_term",
            )
        return term

    async def get_teacher_class_ids(
        self, staff_id: UUID, tenant_id: UUID,
        school_id: UUID | None = None,
    ) -> list[UUID]:
        """
        Get all class section IDs the teacher is assigned to.

        Uses StaffClassAssignment to find section assignments, then
        also checks ClassTimetable for timetable-based assignments.
        Returns a deduplicated list.

        When school_id is provided (chain tenants), filters assignments
        to only those belonging to the specified school.
        """
        # From StaffClassAssignment
        assignment_query = (
            select(distinct(StaffClassAssignment.section_id))
            .where(
                and_(
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                )
            )
        )
        # Chain support: filter to assignments at the active school
        if school_id:
            assignment_query = assignment_query.where(
                StaffClassAssignment.school_id == school_id
            )

        assignment_result = await self.db.execute(assignment_query)
        section_ids = set(assignment_result.scalars().all())

        # Also from ClassTimetable (teacher may be on timetable without assignment record)
        timetable_query = (
            select(distinct(ClassTimetable.section_id))
            .where(
                and_(
                    ClassTimetable.teacher_id == staff_id,
                    ClassTimetable.tenant_id == tenant_id,
                    ClassTimetable.is_active.is_(True),
                    ClassTimetable.section_id.isnot(None),
                )
            )
        )
        # Chain support: filter timetable entries by school via ClassSection join
        if school_id:
            timetable_query = timetable_query.join(
                ClassSection, ClassTimetable.section_id == ClassSection.id
            ).where(ClassSection.school_id == school_id)

        timetable_result = await self.db.execute(timetable_query)
        section_ids.update(timetable_result.scalars().all())

        return list(section_ids)

    async def get_teacher_subject_ids(
        self, staff_id: UUID, tenant_id: UUID,
        school_id: UUID | None = None,
    ) -> list[UUID]:
        """
        Get all subject IDs the teacher teaches.

        Combines subjects from class_subjects (teacher_id) and timetable entries.

        When school_id is provided (chain tenants), filters to subjects
        taught at the specified school only.
        """
        # From ClassSubject (explicit teacher assignment)
        cs_query = (
            select(distinct(ClassSubject.subject_id))
            .where(
                and_(
                    ClassSubject.teacher_id == staff_id,
                    ClassSubject.tenant_id == tenant_id,
                )
            )
        )
        # Chain support: filter class_subjects by school via the parent Class
        if school_id:
            cs_query = cs_query.join(
                Class, ClassSubject.class_id == Class.id
            ).where(Class.school_id == school_id)

        cs_result = await self.db.execute(cs_query)
        subject_ids = set(cs_result.scalars().all())

        # From timetable entries
        tt_query = (
            select(distinct(ClassTimetable.subject_id))
            .where(
                and_(
                    ClassTimetable.teacher_id == staff_id,
                    ClassTimetable.tenant_id == tenant_id,
                    ClassTimetable.is_active.is_(True),
                    ClassTimetable.subject_id.isnot(None),
                )
            )
        )
        # Chain support: filter timetable entries by school via ClassSection
        if school_id:
            tt_query = tt_query.join(
                ClassSection, ClassTimetable.section_id == ClassSection.id
            ).where(ClassSection.school_id == school_id)

        tt_result = await self.db.execute(tt_query)
        subject_ids.update(tt_result.scalars().all())

        return list(subject_ids)

    async def verify_class_access(
        self, staff_id: UUID, tenant_id: UUID, class_id: UUID,
        section_id: UUID | None = None,
    ) -> None:
        """
        Verify the teacher has access to a specific class (and optionally section).

        Checks StaffClassAssignment and ClassTimetable. Raises TeacherServiceError
        if the teacher is not assigned to the requested class.
        """
        # Check StaffClassAssignment for any section in this class
        assignment_query = (
            select(func.count())
            .select_from(StaffClassAssignment)
            .join(ClassSection, StaffClassAssignment.section_id == ClassSection.id)
            .where(
                and_(
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                    ClassSection.class_id == class_id,
                )
            )
        )
        if section_id:
            assignment_query = assignment_query.where(
                StaffClassAssignment.section_id == section_id
            )

        result = await self.db.execute(assignment_query)
        if result.scalar_one() > 0:
            return

        # Fallback: check timetable entries
        tt_query = (
            select(func.count())
            .select_from(ClassTimetable)
            .where(
                and_(
                    ClassTimetable.teacher_id == staff_id,
                    ClassTimetable.tenant_id == tenant_id,
                    ClassTimetable.class_id == class_id,
                    ClassTimetable.is_active.is_(True),
                )
            )
        )
        if section_id:
            tt_query = tt_query.where(ClassTimetable.section_id == section_id)

        result = await self.db.execute(tt_query)
        if result.scalar_one() > 0:
            return

        raise TeacherServiceError(
            "You are not assigned to this class",
            code="access_denied",
        )

    async def verify_subject_access(
        self, staff_id: UUID, tenant_id: UUID, subject_id: UUID,
        class_id: UUID | None = None,
    ) -> None:
        """
        Verify the teacher teaches a specific subject (optionally in a specific class).

        Checks ClassSubject.teacher_id and ClassTimetable entries.
        """
        # Check ClassSubject
        cs_query = (
            select(func.count())
            .select_from(ClassSubject)
            .where(
                and_(
                    ClassSubject.teacher_id == staff_id,
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        )
        if class_id:
            cs_query = cs_query.where(ClassSubject.class_id == class_id)

        result = await self.db.execute(cs_query)
        if result.scalar_one() > 0:
            return

        # Fallback: check timetable
        tt_query = (
            select(func.count())
            .select_from(ClassTimetable)
            .where(
                and_(
                    ClassTimetable.teacher_id == staff_id,
                    ClassTimetable.tenant_id == tenant_id,
                    ClassTimetable.subject_id == subject_id,
                    ClassTimetable.is_active.is_(True),
                )
            )
        )
        if class_id:
            tt_query = tt_query.where(ClassTimetable.class_id == class_id)

        result = await self.db.execute(tt_query)
        if result.scalar_one() > 0:
            return

        raise TeacherServiceError(
            "You are not assigned to this subject",
            code="access_denied",
        )

    async def get_students_in_section(
        self, tenant_id: UUID, section_id: UUID
    ) -> list[Student]:
        """
        Get all active, non-deleted students enrolled in a specific section.
        """
        result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.section_id == section_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
            .order_by(Student.last_name, Student.first_name)
        )
        return list(result.scalars().all())

    async def get_students_in_class(
        self, tenant_id: UUID, class_id: UUID
    ) -> list[Student]:
        """
        Get all active, non-deleted students enrolled in any section of a class.
        """
        result = await self.db.execute(
            select(Student)
            .join(ClassSection, Student.section_id == ClassSection.id)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    ClassSection.class_id == class_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
            .order_by(Student.last_name, Student.first_name)
        )
        return list(result.scalars().all())

    async def is_class_teacher_for_section(
        self, staff_id: UUID, tenant_id: UUID, section_id: UUID
    ) -> bool:
        """Check if the staff member is the class teacher for a section."""
        result = await self.db.execute(
            select(StaffClassAssignment.is_class_teacher)
            .where(
                and_(
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.section_id == section_id,
                    StaffClassAssignment.is_class_teacher.is_(True),
                )
            )
        )
        return result.scalar_one_or_none() is not None
