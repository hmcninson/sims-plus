"""
SIMS Plus - Teacher Note Service

Business logic for managing teacher notes about individual students.
Notes can be visible to parents via the parent portal, with acknowledgement tracking.
"""

import math
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.academic import Subject
from app.models.parent import NoteType, TeacherNote
from app.models.student import Student
from app.models.user import User

logger = structlog.get_logger()


class TeacherNoteServiceError(Exception):
    """Base exception for teacher note service errors."""

    def __init__(self, message: str, code: str = "teacher_note_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class TeacherNoteService:
    """Service for managing teacher notes about students.

    Notes are created by teachers and optionally visible to parents
    through the parent portal. Parents can acknowledge notes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_note(
        self,
        tenant_id: UUID,
        school_id: UUID,
        teacher_id: UUID,
        data: "TeacherNoteCreate",
    ) -> TeacherNote:
        """Create a teacher note for a student.

        Validates that the student exists and belongs to the same tenant.
        If the note is visible to parents and the note_type is concern or
        action_required, this is a signal to the caller to trigger a parent
        notification (not handled here to avoid coupling).
        """
        # Verify the student exists and belongs to this tenant
        await self._validate_student_exists(tenant_id, data.student_id)

        # Verify the subject exists if provided
        if data.subject_id:
            await self._validate_subject_exists(tenant_id, data.subject_id)

        note = TeacherNote(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=data.student_id,
            teacher_id=teacher_id,
            subject_id=data.subject_id,
            note_type=NoteType(data.note_type.value),
            content=data.content,
            is_visible_to_parent=data.is_visible_to_parent,
        )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note)

        logger.info(
            "teacher_note_created",
            note_id=str(note.id),
            student_id=str(data.student_id),
            teacher_id=str(teacher_id),
            note_type=note.note_type.value,
            visible_to_parent=note.is_visible_to_parent,
        )
        return note

    async def update_note(
        self,
        tenant_id: UUID,
        note_id: UUID,
        teacher_id: UUID,
        data: "TeacherNoteUpdate",
    ) -> TeacherNote:
        """Update a teacher note. Only the creating teacher can update.

        Raises TeacherNoteServiceError if the note does not exist, is deleted,
        or was created by a different teacher.
        """
        note = await self._get_note_or_raise(tenant_id, note_id)

        # Only the teacher who created the note can update it
        if note.teacher_id != teacher_id:
            raise TeacherNoteServiceError(
                "Only the teacher who created this note can update it",
                code="forbidden",
            )

        if data.content is not None:
            note.content = data.content
        if data.note_type is not None:
            note.note_type = NoteType(data.note_type.value)
        if data.is_visible_to_parent is not None:
            note.is_visible_to_parent = data.is_visible_to_parent

        await self.db.flush()
        await self.db.refresh(note)

        logger.info(
            "teacher_note_updated",
            note_id=str(note.id),
            teacher_id=str(teacher_id),
        )
        return note

    async def delete_note(
        self,
        tenant_id: UUID,
        note_id: UUID,
        requesting_user_id: UUID,
        is_admin: bool = False,
    ) -> None:
        """Soft delete a teacher note.

        The creating teacher can always delete their own notes.
        Admins (is_admin=True) can delete any note within their tenant.
        """
        note = await self._get_note_or_raise(tenant_id, note_id)

        # Check authorization: creating teacher or admin
        if note.teacher_id != requesting_user_id and not is_admin:
            raise TeacherNoteServiceError(
                "Only the creating teacher or an admin can delete this note",
                code="forbidden",
            )

        note.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "teacher_note_deleted",
            note_id=str(note.id),
            deleted_by=str(requesting_user_id),
            is_admin=is_admin,
        )

    async def get_note(
        self,
        tenant_id: UUID,
        note_id: UUID,
    ) -> TeacherNote:
        """Get a single note by ID with student, teacher, and subject names loaded.

        The TeacherNote model has relationships for student and teacher,
        but subject is loaded via a separate query since there is no
        ORM relationship defined on the model.
        """
        # Defense-in-depth: always filter by tenant_id even though RLS handles isolation
        stmt = (
            select(TeacherNote)
            .where(
                and_(
                    TeacherNote.tenant_id == tenant_id,
                    TeacherNote.id == note_id,
                    TeacherNote.deleted_at.is_(None),
                )
            )
            .options(
                joinedload(TeacherNote.student),
                joinedload(TeacherNote.teacher),
            )
        )
        result = await self.db.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            raise TeacherNoteServiceError(
                "Teacher note not found",
                code="not_found",
            )

        return note

    async def list_notes_for_student(
        self,
        tenant_id: UUID,
        student_id: UUID,
        include_hidden: bool = True,
        page: int = 1,
        page_size: int = 50,
        note_type: Optional[str] = None,
    ) -> dict:
        """List all notes for a student (teacher/admin view).

        Args:
            tenant_id: Tenant scope for defense-in-depth
            student_id: The student to list notes for
            include_hidden: If True, include notes not visible to parents (admin/teacher view)
            page: Current page (1-indexed)
            page_size: Items per page
            note_type: Optional filter by note type
        """
        conditions = [
            TeacherNote.tenant_id == tenant_id,
            TeacherNote.student_id == student_id,
            TeacherNote.deleted_at.is_(None),
        ]

        if not include_hidden:
            # Parent view: only show notes marked as visible to parents
            conditions.append(TeacherNote.is_visible_to_parent == True)  # noqa: E712

        if note_type:
            conditions.append(TeacherNote.note_type == NoteType(note_type))

        # Count total
        count_stmt = select(func.count()).select_from(
            select(TeacherNote.id).where(and_(*conditions)).subquery()
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        # Get paginated results with teacher name loaded
        stmt = (
            select(TeacherNote)
            .where(and_(*conditions))
            .options(
                joinedload(TeacherNote.teacher),
                joinedload(TeacherNote.student),
            )
            .order_by(desc(TeacherNote.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().unique().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def list_notes_for_parent(
        self,
        tenant_id: UUID,
        student_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """List only parent-visible notes for a student.

        Filters to is_visible_to_parent=True and deleted_at IS NULL.
        Returns notes with teacher name and subject name loaded.
        """
        conditions = [
            TeacherNote.tenant_id == tenant_id,
            TeacherNote.student_id == student_id,
            TeacherNote.deleted_at.is_(None),
            # Only show notes explicitly marked as visible to parents
            TeacherNote.is_visible_to_parent == True,  # noqa: E712
        ]

        # Count total
        count_stmt = select(func.count()).select_from(
            select(TeacherNote.id).where(and_(*conditions)).subquery()
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        # Paginated results sorted by most recent first
        stmt = (
            select(TeacherNote)
            .where(and_(*conditions))
            .options(
                joinedload(TeacherNote.teacher),
                joinedload(TeacherNote.student),
            )
            .order_by(desc(TeacherNote.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().unique().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def acknowledge_note(
        self,
        tenant_id: UUID,
        note_id: UUID,
        student_id: UUID,
    ) -> TeacherNote:
        """Mark a note as acknowledged by a parent.

        Sets parent_acknowledged=True and parent_acknowledged_at to the current time.
        The student_id parameter is an IDOR check: the note must belong to
        the specified student so a parent cannot acknowledge notes for other students.
        """
        # Defense-in-depth: filter by tenant_id, note_id, AND student_id (IDOR prevention)
        stmt = select(TeacherNote).where(
            and_(
                TeacherNote.tenant_id == tenant_id,
                TeacherNote.id == note_id,
                TeacherNote.student_id == student_id,
                TeacherNote.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            raise TeacherNoteServiceError(
                "Teacher note not found for this student",
                code="not_found",
            )

        if not note.is_visible_to_parent:
            raise TeacherNoteServiceError(
                "This note is not visible to parents",
                code="not_visible",
            )

        if note.parent_acknowledged:
            # Idempotent: already acknowledged, just return it
            return note

        note.parent_acknowledged = True
        note.parent_acknowledged_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(note)

        logger.info(
            "teacher_note_acknowledged",
            note_id=str(note.id),
            student_id=str(student_id),
        )
        return note

    async def list_notes_by_teacher(
        self,
        tenant_id: UUID,
        teacher_id: UUID,
        page: int = 1,
        page_size: int = 20,
        note_type: Optional[str] = None,
        student_id: Optional[UUID] = None,
    ) -> dict:
        """List notes written by a specific teacher (teacher's own view).

        Args:
            tenant_id: Tenant scope for defense-in-depth
            teacher_id: The teacher whose notes to list
            page: Current page (1-indexed)
            page_size: Items per page
            note_type: Optional filter by note type
            student_id: Optional filter by student
        """
        conditions = [
            TeacherNote.tenant_id == tenant_id,
            TeacherNote.teacher_id == teacher_id,
            TeacherNote.deleted_at.is_(None),
        ]

        if note_type:
            conditions.append(TeacherNote.note_type == NoteType(note_type))

        if student_id:
            conditions.append(TeacherNote.student_id == student_id)

        # Count total
        count_stmt = select(func.count()).select_from(
            select(TeacherNote.id).where(and_(*conditions)).subquery()
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        # Paginated results with student name loaded
        stmt = (
            select(TeacherNote)
            .where(and_(*conditions))
            .options(
                joinedload(TeacherNote.student),
                joinedload(TeacherNote.teacher),
            )
            .order_by(desc(TeacherNote.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().unique().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def get_subject_name(
        self,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> Optional[str]:
        """Look up a subject name by ID.

        The TeacherNote model has a subject_id FK but no ORM relationship to Subject,
        so callers that need the subject name for response construction should use this
        helper. Returns None if the subject does not exist or is deleted.
        """
        stmt = select(Subject.name).where(
            and_(
                Subject.tenant_id == tenant_id,
                Subject.id == subject_id,
                Subject.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_unacknowledged_count(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> int:
        """Count parent-visible notes that have not been acknowledged.

        Useful for showing a badge count on the parent portal.
        """
        stmt = select(func.count()).select_from(TeacherNote).where(
            and_(
                TeacherNote.tenant_id == tenant_id,
                TeacherNote.student_id == student_id,
                TeacherNote.deleted_at.is_(None),
                TeacherNote.is_visible_to_parent == True,  # noqa: E712
                TeacherNote.parent_acknowledged == False,  # noqa: E712
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    # ==========================
    # Private helpers
    # ==========================

    async def _get_note_or_raise(
        self,
        tenant_id: UUID,
        note_id: UUID,
    ) -> TeacherNote:
        """Fetch a teacher note by ID or raise TeacherNoteServiceError.

        Uses tenant_id filter for defense-in-depth on top of RLS.
        Does not load relationships (use get_note() for that).
        """
        stmt = select(TeacherNote).where(
            and_(
                TeacherNote.tenant_id == tenant_id,
                TeacherNote.id == note_id,
                TeacherNote.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        note = result.scalar_one_or_none()
        if not note:
            raise TeacherNoteServiceError(
                "Teacher note not found",
                code="not_found",
            )
        return note

    async def _validate_student_exists(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> None:
        """Verify a student exists and belongs to this tenant.

        Raises TeacherNoteServiceError if the student is not found or is soft-deleted.
        """
        stmt = select(Student.id).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise TeacherNoteServiceError(
                "Student not found",
                code="student_not_found",
            )

    async def _validate_subject_exists(
        self,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> None:
        """Verify a subject exists and belongs to this tenant.

        Raises TeacherNoteServiceError if the subject is not found or is soft-deleted.
        """
        stmt = select(Subject.id).where(
            and_(
                Subject.tenant_id == tenant_id,
                Subject.id == subject_id,
                Subject.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise TeacherNoteServiceError(
                "Subject not found",
                code="subject_not_found",
            )
