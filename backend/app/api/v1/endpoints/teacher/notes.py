"""
SIMS Plus - Teacher Portal Notes Endpoints

CRUD operations for teacher notes about students. Notes are visible
to parents through the parent portal when is_visible_to_parent is True.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import (
    TeacherNoteCreate,
    TeacherNoteListResponse,
    TeacherNoteResponse,
)
from app.services.teacher import (
    TeacherContextService,
    TeacherNotesService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

from sqlalchemy import and_, select

from app.models.academic import ClassSection
from app.models.parent import NoteType
from app.models.student import Student

router = APIRouter()


@router.get(
    "/notes",
    response_model=TeacherNoteListResponse,
    summary="Get my teacher notes",
    dependencies=[Depends(require_permissions("teacher.notes.read"))],
)
async def list_my_notes(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    student_id: UUID | None = Query(None, description="Filter by student"),
    note_type: str | None = Query(None, description="Filter by note type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TeacherNoteListResponse:
    """
    List teacher notes written by the authenticated teacher.

    Supports filtering by student and note type with pagination.
    """
    user_id = _get_user_id(user)

    try:
        # Verify teacher identity
        context = TeacherContextService(db)
        await context.get_staff_for_user(user_id, tenant.tenant_id)

        notes_service = TeacherNotesService(db)
        result = await notes_service.list_notes(
            tenant_id=tenant.tenant_id,
            teacher_id=user_id,
            student_id=student_id,
            note_type=note_type,
            limit=limit,
            offset=offset,
        )

        return TeacherNoteListResponse(
            notes=[TeacherNoteResponse(**n) for n in result["notes"]],
            total=result["total"],
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.post(
    "/notes",
    response_model=TeacherNoteResponse,
    summary="Create a teacher note",
    dependencies=[Depends(require_permissions("teacher.notes.write"))],
    status_code=201,
)
async def create_note(
    body: TeacherNoteCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> TeacherNoteResponse:
    """
    Create a new teacher note about a student.

    The teacher must be assigned to the student's class (verified via
    class access check). Notes can be made visible to parents.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Verify student exists and is enrolled in a class
        student_result = await db.execute(
            select(Student)
            .where(
                and_(
                    Student.id == body.student_id,
                    Student.tenant_id == tenant.tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise TeacherServiceError("Student not found", code="not_found")

        # Authorization: verify teacher is assigned to the student's class
        if not student.section_id:
            raise TeacherServiceError(
                "Student is not enrolled in any class section",
                code="student_not_in_section",
            )
        section_result = await db.execute(
            select(ClassSection.class_id)
            .where(
                and_(
                    ClassSection.id == student.section_id,
                    ClassSection.tenant_id == tenant.tenant_id,
                )
            )
        )
        student_class_id = section_result.scalar_one_or_none()
        if not student_class_id:
            raise TeacherServiceError(
                "Student's class section not found", code="not_found"
            )
        await context.verify_class_access(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=student_class_id,
        )

        # Get school_id from staff
        school_id = staff.school_id
        if not school_id:
            raise TeacherServiceError(
                "Teacher has no school association", code="teacher_error"
            )

        notes_service = TeacherNotesService(db)
        note_data = await notes_service.create_note(
            tenant_id=tenant.tenant_id,
            teacher_id=user_id,
            school_id=school_id,
            student_id=body.student_id,
            content=body.content,
            note_type=NoteType(body.note_type.value),
            subject_id=body.subject_id,
            is_visible_to_parent=body.is_visible_to_parent,
        )

        return TeacherNoteResponse(
            student_name=f"{student.first_name} {student.last_name}",
            **note_data,
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)
