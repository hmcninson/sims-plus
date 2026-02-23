"""
SIMS Plus - Teacher Reports Service

Handles report card comments for class teachers and head teachers.
Class teachers write per-student comments for students in their section.
Head teachers (school_admin role) can write head teacher comments.
"""

from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicYear, ClassSection, Term
from app.models.staff import Staff, StaffClassAssignment
from app.models.student import Student, StudentStatus
from app.models.teacher import ReportComment

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherReportsService:
    """
    Report comment management for class teachers and head teachers.

    Class teachers can write/sign class_teacher_comment for students in
    sections where is_class_teacher=True. Head teachers (admins) can
    write/sign head_teacher_comment for any student.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_report_comments(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        term_id: UUID,
        section_id: UUID | None = None,
        is_head_teacher: bool = False,
    ) -> list[dict]:
        """
        Get report comments for a term, optionally filtered by section.

        For class teachers, this returns comments for students in their section.
        When no section_id is given, only show comments this teacher authored
        to prevent regular teachers from viewing other teachers' comments.

        The is_head_teacher flag controls whether draft (unsigned) head teacher
        comments are visible. Regular teachers only see head_teacher_comment
        when head_teacher_signed is True.
        """
        query = (
            select(ReportComment)
            .options(selectinload(ReportComment.student))
            .where(
                and_(
                    ReportComment.tenant_id == tenant_id,
                    ReportComment.term_id == term_id,
                    ReportComment.deleted_at.is_(None),
                )
            )
        )

        if section_id:
            # Filter to students in this section
            query = query.where(
                ReportComment.student_id.in_(
                    select(Student.id)
                    .where(
                        and_(
                            Student.tenant_id == tenant_id,
                            Student.section_id == section_id,
                            Student.status == StudentStatus.ACTIVE,
                            Student.deleted_at.is_(None),
                        )
                    )
                )
            )
        else:
            # No section filter: scope to only this teacher's own comments
            # so regular teachers cannot see comments from other class teachers
            query = query.where(ReportComment.class_teacher_id == staff_id)

        result = await self.db.execute(query.order_by(ReportComment.created_at))
        comments = result.scalars().all()

        return [
            self._format_comment(c, c.student, is_head_teacher=is_head_teacher)
            for c in comments
        ]

    async def upsert_class_teacher_comment(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        student_id: UUID,
        term_id: UUID,
        academic_year_id: UUID,
        comment: str,
    ) -> dict:
        """
        Create or update a class teacher comment for a student.

        The teacher must be the class teacher for the student's section.
        If a comment already exists, it updates the class_teacher_comment field.
        """
        # Verify student exists and get their section
        student = await self._get_student(student_id, tenant_id)

        # Verify this teacher is the class teacher for this section
        if student.section_id:
            is_ct = await self._is_class_teacher(staff_id, tenant_id, student.section_id)
            if not is_ct:
                raise TeacherServiceError(
                    "You are not the class teacher for this student's section",
                    code="access_denied",
                )
        else:
            raise TeacherServiceError(
                "Student is not assigned to a section",
                code="student_not_in_section",
            )

        # Upsert comment
        existing_result = await self.db.execute(
            select(ReportComment)
            .where(
                and_(
                    ReportComment.tenant_id == tenant_id,
                    ReportComment.student_id == student_id,
                    ReportComment.term_id == term_id,
                    ReportComment.deleted_at.is_(None),
                )
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.class_teacher_comment = comment
            existing.class_teacher_id = staff_id
            await self.db.flush()
            await self.db.refresh(existing)
            return self._format_comment(existing, student)
        else:
            new_comment = ReportComment(
                tenant_id=tenant_id,
                student_id=student_id,
                term_id=term_id,
                academic_year_id=academic_year_id,
                class_teacher_comment=comment,
                class_teacher_id=staff_id,
            )
            self.db.add(new_comment)
            await self.db.flush()
            await self.db.refresh(new_comment)
            return self._format_comment(new_comment, student)

    async def sign_class_teacher_comment(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        student_id: UUID,
        term_id: UUID,
    ) -> dict:
        """
        Sign off a class teacher comment.

        Marks the class_teacher_signed flag as True. The comment must exist
        and the teacher must be the class teacher for the student's section.
        """
        student = await self._get_student(student_id, tenant_id)

        if student.section_id:
            is_ct = await self._is_class_teacher(staff_id, tenant_id, student.section_id)
            if not is_ct:
                raise TeacherServiceError(
                    "You are not the class teacher for this student's section",
                    code="access_denied",
                )

        comment = await self._get_comment(tenant_id, student_id, term_id)
        if not comment.class_teacher_comment:
            raise TeacherServiceError(
                "Cannot sign: no class teacher comment written yet",
                code="no_comment",
            )

        comment.class_teacher_signed = True
        comment.class_teacher_id = staff_id
        await self.db.flush()
        await self.db.refresh(comment)

        return self._format_comment(comment, student)

    async def upsert_head_teacher_comment(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        student_id: UUID,
        term_id: UUID,
        academic_year_id: UUID,
        comment: str,
    ) -> dict:
        """
        Create or update a head teacher comment for a student.

        The caller must have head teacher / school_admin permissions.
        Access verification is done at the endpoint level.
        """
        student = await self._get_student(student_id, tenant_id)

        existing_result = await self.db.execute(
            select(ReportComment)
            .where(
                and_(
                    ReportComment.tenant_id == tenant_id,
                    ReportComment.student_id == student_id,
                    ReportComment.term_id == term_id,
                    ReportComment.deleted_at.is_(None),
                )
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.head_teacher_comment = comment
            existing.head_teacher_id = staff_id
            await self.db.flush()
            await self.db.refresh(existing)
            return self._format_comment(existing, student, is_head_teacher=True)
        else:
            new_comment = ReportComment(
                tenant_id=tenant_id,
                student_id=student_id,
                term_id=term_id,
                academic_year_id=academic_year_id,
                head_teacher_comment=comment,
                head_teacher_id=staff_id,
            )
            self.db.add(new_comment)
            await self.db.flush()
            await self.db.refresh(new_comment)
            return self._format_comment(new_comment, student, is_head_teacher=True)

    async def sign_head_teacher_comment(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        student_id: UUID,
        term_id: UUID,
    ) -> dict:
        """Sign off a head teacher comment."""
        student = await self._get_student(student_id, tenant_id)
        comment = await self._get_comment(tenant_id, student_id, term_id)

        if not comment.head_teacher_comment:
            raise TeacherServiceError(
                "Cannot sign: no head teacher comment written yet",
                code="no_comment",
            )

        comment.head_teacher_signed = True
        comment.head_teacher_id = staff_id
        await self.db.flush()
        await self.db.refresh(comment)

        return self._format_comment(comment, student, is_head_teacher=True)

    async def _get_student(self, student_id: UUID, tenant_id: UUID) -> Student:
        """Get a student by ID, verifying tenant scope."""
        result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise TeacherServiceError("Student not found", code="not_found")
        return student

    async def _get_comment(
        self, tenant_id: UUID, student_id: UUID, term_id: UUID
    ) -> ReportComment:
        """Get an existing report comment, raising error if not found."""
        result = await self.db.execute(
            select(ReportComment)
            .where(
                and_(
                    ReportComment.tenant_id == tenant_id,
                    ReportComment.student_id == student_id,
                    ReportComment.term_id == term_id,
                    ReportComment.deleted_at.is_(None),
                )
            )
        )
        comment = result.scalar_one_or_none()
        if not comment:
            raise TeacherServiceError(
                "Report comment not found for this student and term",
                code="not_found",
            )
        return comment

    async def _is_class_teacher(
        self, staff_id: UUID, tenant_id: UUID, section_id: UUID
    ) -> bool:
        """Check if staff is the class teacher for a section."""
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

    @staticmethod
    def _format_comment(
        comment: ReportComment,
        student: Student | None,
        is_head_teacher: bool = False,
    ) -> dict:
        """
        Format a report comment for API response.

        Draft head teacher comments (head_teacher_signed=False) are only
        visible to head teachers. Regular teachers see None until the
        head teacher signs off.
        """
        # Only reveal head_teacher_comment if it's been signed off
        # or the requester is a head teacher who can see their own drafts
        head_teacher_comment = None
        if comment.head_teacher_signed or is_head_teacher:
            head_teacher_comment = comment.head_teacher_comment

        return {
            "id": comment.id,
            "student_id": comment.student_id,
            "student_name": (
                f"{student.first_name} {student.last_name}"
                if student else None
            ),
            "term_id": comment.term_id,
            "academic_year_id": comment.academic_year_id,
            "class_teacher_comment": comment.class_teacher_comment,
            "head_teacher_comment": head_teacher_comment,
            "class_teacher_signed": comment.class_teacher_signed,
            "head_teacher_signed": comment.head_teacher_signed,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
        }
