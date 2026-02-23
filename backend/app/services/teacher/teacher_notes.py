"""
SIMS Plus - Teacher Notes Service

CRUD operations for teacher notes about students. Handles note listing
with batch subject name resolution and note creation with tenant isolation.
"""

from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Subject
from app.models.parent import NoteType, TeacherNote

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherNotesService:
    """
    Teacher note operations for the teacher portal.

    Handles listing, creating, and managing notes about students.
    All queries filter by tenant_id for defense-in-depth.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_notes(
        self,
        tenant_id: UUID,
        teacher_id: UUID,
        student_id: UUID | None = None,
        note_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        List teacher notes with pagination and optional filters.

        Returns notes with student and subject names pre-resolved
        to avoid N+1 queries.
        """
        # Defense-in-depth: always scope to tenant + teacher
        base_filter = and_(
            TeacherNote.tenant_id == tenant_id,
            TeacherNote.teacher_id == teacher_id,
            TeacherNote.deleted_at.is_(None),
        )

        query = select(TeacherNote).where(base_filter)
        count_query = select(func.count(TeacherNote.id)).where(base_filter)

        if student_id:
            query = query.where(TeacherNote.student_id == student_id)
            count_query = count_query.where(TeacherNote.student_id == student_id)
        if note_type:
            query = query.where(TeacherNote.note_type == NoteType(note_type))
            count_query = count_query.where(TeacherNote.note_type == NoteType(note_type))

        total = (await self.db.execute(count_query)).scalar_one()

        query = (
            query
            .options(selectinload(TeacherNote.student))
            .order_by(TeacherNote.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        notes = (await self.db.execute(query)).scalars().all()

        # Batch-fetch subject names to avoid N+1 queries
        # Defense-in-depth: scope to tenant even though RLS enforces isolation
        subject_ids = {n.subject_id for n in notes if n.subject_id}
        subject_name_map: dict[UUID, str] = {}
        if subject_ids:
            subj_result = await self.db.execute(
                select(Subject.id, Subject.name)
                .where(
                    and_(
                        Subject.id.in_(subject_ids),
                        Subject.tenant_id == tenant_id,
                    )
                )
            )
            subject_name_map = dict(subj_result.all())

        note_list = []
        for n in notes:
            note_list.append({
                "id": n.id,
                "student_id": n.student_id,
                "student_name": (
                    f"{n.student.first_name} {n.student.last_name}"
                    if n.student else None
                ),
                "subject_id": n.subject_id,
                "subject_name": subject_name_map.get(n.subject_id) if n.subject_id else None,
                "note_type": n.note_type.value if n.note_type else "information",
                "content": n.content,
                "is_visible_to_parent": n.is_visible_to_parent,
                "parent_acknowledged": n.parent_acknowledged,
                "parent_acknowledged_at": n.parent_acknowledged_at,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
            })

        return {"notes": note_list, "total": total}

    async def create_note(
        self,
        tenant_id: UUID,
        teacher_id: UUID,
        school_id: UUID,
        student_id: UUID,
        content: str,
        note_type: NoteType,
        subject_id: UUID | None = None,
        is_visible_to_parent: bool = True,
    ) -> dict:
        """
        Create a new teacher note about a student.

        Returns the created note with resolved subject name.
        """
        note = TeacherNote(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=student_id,
            teacher_id=teacher_id,  # TeacherNote uses user_id as teacher_id
            subject_id=subject_id,
            note_type=note_type,
            content=content,
            is_visible_to_parent=is_visible_to_parent,
        )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note)

        # Resolve subject name
        # Defense-in-depth: scope to tenant even though RLS enforces isolation
        subject_name = None
        if note.subject_id:
            subj = (await self.db.execute(
                select(Subject.name).where(
                    and_(
                        Subject.id == note.subject_id,
                        Subject.tenant_id == tenant_id,
                    )
                )
            )).scalar_one_or_none()
            subject_name = subj

        return {
            "id": note.id,
            "student_id": note.student_id,
            "subject_id": note.subject_id,
            "subject_name": subject_name,
            "note_type": note.note_type.value,
            "content": note.content,
            "is_visible_to_parent": note.is_visible_to_parent,
            "parent_acknowledged": note.parent_acknowledged,
            "parent_acknowledged_at": note.parent_acknowledged_at,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
