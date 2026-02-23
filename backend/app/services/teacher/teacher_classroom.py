"""
SIMS Plus - Teacher Classroom Service

Provides class overview and student list functionality for teachers.
A teacher can view classes they are assigned to (via StaffClassAssignment
or ClassTimetable) and list students in those classes.
"""

from uuid import UUID

import structlog
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    Class,
    ClassSection,
    ClassSubject,
    ClassTimetable,
    Subject,
)
from app.models.staff import Staff, StaffClassAssignment
from app.models.student import Student, StudentStatus

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherClassroomService:
    """
    Provides classroom data scoped to a specific teacher.

    All queries filter by tenant_id for defense-in-depth on top of RLS.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_my_classes(
        self, staff_id: UUID, tenant_id: UUID
    ) -> list[dict]:
        """
        Get all classes/sections assigned to this teacher.

        Combines data from StaffClassAssignment (explicit assignments)
        and ClassTimetable (timetable-based assignments) to build a
        comprehensive list of class-section combinations.
        """
        # Get sections from StaffClassAssignment
        assignment_result = await self.db.execute(
            select(StaffClassAssignment)
            .options(
                selectinload(StaffClassAssignment.section),
            )
            .where(
                and_(
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                )
            )
        )
        assignments = assignment_result.scalars().all()

        # Build a map of section_id -> class info
        class_map: dict[UUID, dict] = {}
        section_to_class: dict[UUID, UUID] = {}

        for assignment in assignments:
            section = assignment.section
            if section and section.id not in class_map:
                class_map[section.id] = {
                    "section_id": section.id,
                    "section_name": section.name,
                    "class_id": section.class_id,
                    "is_class_teacher": assignment.is_class_teacher,
                }
                section_to_class[section.id] = section.class_id

        # Also check timetable for additional classes not in assignments
        tt_result = await self.db.execute(
            select(
                distinct(ClassTimetable.section_id),
                ClassTimetable.class_id,
            )
            .where(
                and_(
                    ClassTimetable.teacher_id == staff_id,
                    ClassTimetable.tenant_id == tenant_id,
                    ClassTimetable.is_active.is_(True),
                    ClassTimetable.section_id.isnot(None),
                )
            )
        )
        for row in tt_result.all():
            section_id, class_id = row
            if section_id and section_id not in class_map:
                class_map[section_id] = {
                    "section_id": section_id,
                    "section_name": None,  # Will be populated below
                    "class_id": class_id,
                    "is_class_teacher": False,
                }

        if not class_map:
            return []

        # Fetch class and section details
        all_class_ids = {v["class_id"] for v in class_map.values()}
        all_section_ids = set(class_map.keys())

        classes_result = await self.db.execute(
            select(Class)
            .where(
                and_(
                    Class.id.in_(all_class_ids),
                    Class.tenant_id == tenant_id,
                    Class.deleted_at.is_(None),
                )
            )
        )
        classes_by_id = {c.id: c for c in classes_result.scalars().all()}

        sections_result = await self.db.execute(
            select(ClassSection)
            .where(
                and_(
                    ClassSection.id.in_(all_section_ids),
                    ClassSection.tenant_id == tenant_id,
                    ClassSection.deleted_at.is_(None),
                )
            )
        )
        sections_by_id = {s.id: s for s in sections_result.scalars().all()}

        # Count students per section
        student_counts_result = await self.db.execute(
            select(
                Student.section_id,
                func.count(Student.id),
            )
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.section_id.in_(all_section_ids),
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
            .group_by(Student.section_id)
        )
        student_counts = dict(student_counts_result.all())

        # Build response
        result = []
        for section_id, info in class_map.items():
            cls = classes_by_id.get(info["class_id"])
            sec = sections_by_id.get(section_id)
            if not cls:
                continue

            result.append({
                "class_id": info["class_id"],
                "class_name": cls.name,
                "section_id": section_id,
                "section_name": sec.name if sec else info.get("section_name"),
                "student_count": student_counts.get(section_id, 0),
                "is_class_teacher": info["is_class_teacher"],
            })

        # Sort by class name then section name
        result.sort(key=lambda x: (x["class_name"] or "", x["section_name"] or ""))
        return result

    async def get_class_students(
        self, staff_id: UUID, tenant_id: UUID,
        class_id: UUID, section_id: UUID | None = None,
    ) -> list[Student]:
        """
        Get students in a specific class (or class+section).

        Only returns active, non-deleted students sorted by last name.
        The caller must verify class access before calling this method.
        """
        query = (
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
        )

        if section_id:
            query = query.where(Student.section_id == section_id)
        else:
            # All sections in the class
            query = query.join(
                ClassSection, Student.section_id == ClassSection.id
            ).where(ClassSection.class_id == class_id)

        query = query.order_by(Student.last_name, Student.first_name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_class_overview(
        self, staff_id: UUID, tenant_id: UUID, class_id: UUID,
        section_id: UUID | None = None,
    ) -> dict:
        """
        Get an overview of a class the teacher teaches.

        Includes class/section info, student count, and subjects taught.
        """
        # Get class details
        cls_result = await self.db.execute(
            select(Class)
            .where(
                and_(
                    Class.id == class_id,
                    Class.tenant_id == tenant_id,
                    Class.deleted_at.is_(None),
                )
            )
        )
        cls = cls_result.scalar_one_or_none()
        if not cls:
            raise TeacherServiceError("Class not found", code="not_found")

        section_name = None
        if section_id:
            sec_result = await self.db.execute(
                select(ClassSection)
                .where(
                    and_(
                        ClassSection.id == section_id,
                        ClassSection.tenant_id == tenant_id,
                        ClassSection.class_id == class_id,
                        ClassSection.deleted_at.is_(None),
                    )
                )
            )
            sec = sec_result.scalar_one_or_none()
            section_name = sec.name if sec else None

        # Count students
        student_query = (
            select(func.count(Student.id))
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
        )
        if section_id:
            student_query = student_query.where(Student.section_id == section_id)
        else:
            student_query = student_query.join(
                ClassSection, Student.section_id == ClassSection.id
            ).where(ClassSection.class_id == class_id)

        count_result = await self.db.execute(student_query)
        student_count = count_result.scalar_one()

        # Get subjects this teacher teaches in this class
        subjects_result = await self.db.execute(
            select(Subject)
            .join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                    ClassSubject.teacher_id == staff_id,
                    Subject.deleted_at.is_(None),
                )
            )
        )
        subjects = subjects_result.scalars().all()

        # Check if class teacher
        is_ct = False
        if section_id:
            ct_result = await self.db.execute(
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
            is_ct = ct_result.scalar_one_or_none() is not None

        return {
            "class_id": class_id,
            "class_name": cls.name,
            "section_id": section_id,
            "section_name": section_name,
            "student_count": student_count,
            "subjects": [
                {"subject_id": s.id, "subject_name": s.name, "class_count": 1}
                for s in subjects
            ],
            "is_class_teacher": is_ct,
        }
