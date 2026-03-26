"""
SIMS Plus - Staff Workload Service

Calculates teaching workload from timetable and class assignments.
Read-only service — no mutations.
"""

from uuid import UUID

import structlog
from sqlalchemy import func, select, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import ClassSection, Subject
from app.models.academic.timetable_models import ClassTimetable
from app.models.staff import Staff, StaffClassAssignment, StaffType

logger = structlog.get_logger()


class StaffWorkloadService:
    """Calculates teaching workload from timetable and class assignments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def get_staff_workload(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> dict:
        """
        Get teaching workload for a single staff member.

        Loads assignments with section/class/subject relationships,
        then counts timetable periods for each assignment.
        """
        # Fetch staff with assignments and nested section -> class, plus subject
        result = await self.db.execute(
            select(Staff)
            .options(
                selectinload(Staff.class_assignments)
                .selectinload(StaffClassAssignment.section)
                .selectinload(ClassSection.class_),
            )
            .where(
                Staff.id == staff_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Staff.tenant_id == tenant_id,
                Staff.deleted_at.is_(None),
            )
        )
        staff = result.scalar_one_or_none()
        if not staff:
            raise self.Error("Staff member not found", 404)

        # Build section details with period counts
        sections = []
        total_periods = 0
        class_teacher_of = None
        subjects_taught: set[str] = set()

        for assignment in staff.class_assignments:
            # Count timetable periods for this staff + section combination
            period_count = await self._count_periods(
                tenant_id, staff_id, assignment.section_id, assignment.subject_id
            )

            section_name = assignment.section.name if assignment.section else "Unknown"
            class_name = (
                assignment.section.class_.name
                if assignment.section and assignment.section.class_
                else "Unknown"
            )

            # Load subject name if subject_id is set
            subject_name = None
            if assignment.subject_id:
                sub_result = await self.db.execute(
                    select(Subject.name).where(
                        Subject.id == assignment.subject_id,
                        Subject.tenant_id == tenant_id,
                    )
                )
                subject_name = sub_result.scalar_one_or_none()

            if assignment.is_class_teacher:
                class_teacher_of = f"{class_name} {section_name}"

            if subject_name:
                subjects_taught.add(subject_name)

            sections.append({
                "section_id": assignment.section_id,
                "section_name": section_name,
                "class_name": class_name,
                "subject_name": subject_name,
                "is_class_teacher": assignment.is_class_teacher,
                "periods_per_week": period_count,
            })
            total_periods += period_count

        return {
            "staff_id": staff.id,
            "staff_name": f"{staff.first_name} {staff.last_name}",
            "total_periods_per_week": total_periods,
            "total_sections": len(sections),
            "class_teacher_of": class_teacher_of,
            "subjects_taught": sorted(subjects_taught),
            "sections": sections,
        }

    async def get_all_staff_workload(
        self,
        tenant_id: UUID,
        school_id: UUID | None = None,
    ) -> list[dict]:
        """
        Get workload summary for ALL teaching staff using an aggregate query.
        Avoids N+1 by joining staff -> assignments -> timetable in one pass.
        """
        # Subquery: count timetable periods per staff member
        # ClassTimetable has teacher_id directly (flat model, not two-table join)
        period_counts = (
            select(
                ClassTimetable.teacher_id.label("staff_id"),
                func.count().label("total_periods"),
            )
            .where(
                ClassTimetable.tenant_id == tenant_id,
                ClassTimetable.teacher_id.isnot(None),
            )
            .group_by(ClassTimetable.teacher_id)
            .subquery("period_counts")
        )

        # Main query: teaching staff with assignment counts and period totals
        query = (
            select(
                Staff.id,
                Staff.first_name,
                Staff.last_name,
                Staff.department,
                func.count(func.distinct(StaffClassAssignment.section_id)).label("total_sections"),
                func.coalesce(period_counts.c.total_periods, 0).label("total_periods_per_week"),
                # Check if staff is class teacher of any section
                func.bool_or(StaffClassAssignment.is_class_teacher).label("is_class_teacher_any"),
            )
            .outerjoin(StaffClassAssignment, StaffClassAssignment.staff_id == Staff.id)
            .outerjoin(period_counts, period_counts.c.staff_id == Staff.id)
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Staff.tenant_id == tenant_id,
                Staff.staff_type == StaffType.TEACHING,
                Staff.deleted_at.is_(None),
            )
            .group_by(
                Staff.id,
                Staff.first_name,
                Staff.last_name,
                Staff.department,
                period_counts.c.total_periods,
            )
            .order_by(Staff.last_name, Staff.first_name)
        )

        if school_id:
            query = query.where(Staff.school_id == school_id)

        result = await self.db.execute(query)
        rows = result.all()

        # For staff who are class teachers, fetch the section name
        class_teacher_map: dict[UUID, str] = {}
        class_teacher_ids = [r[0] for r in rows if r[6]]  # is_class_teacher_any
        if class_teacher_ids:
            ct_result = await self.db.execute(
                select(
                    StaffClassAssignment.staff_id,
                    ClassSection.name.label("section_name"),
                )
                .join(ClassSection, ClassSection.id == StaffClassAssignment.section_id)
                .where(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.staff_id.in_(class_teacher_ids),
                    StaffClassAssignment.is_class_teacher.is_(True),
                )
            )
            for ct_row in ct_result.all():
                class_teacher_map[ct_row[0]] = ct_row[1]

        return [
            {
                "staff_id": row[0],
                "staff_name": f"{row[1]} {row[2]}",
                "department": row[3],
                "total_sections": row[4],
                "total_periods_per_week": row[5],
                "is_class_teacher": bool(row[6]),
                "class_teacher_of": class_teacher_map.get(row[0]),
            }
            for row in rows
        ]

    async def _count_periods(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        section_id: UUID,
        subject_id: UUID | None,
    ) -> int:
        """
        Count timetable periods for a specific staff+section+subject combination.

        ClassTimetable is a flat model where each row is one period with
        teacher_id, section_id, and subject_id columns directly.
        """
        conditions = [
            ClassTimetable.section_id == section_id,
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            ClassTimetable.tenant_id == tenant_id,
            ClassTimetable.teacher_id == staff_id,
        ]
        if subject_id:
            conditions.append(ClassTimetable.subject_id == subject_id)

        result = await self.db.execute(
            select(func.count()).select_from(ClassTimetable).where(*conditions)
        )
        return result.scalar() or 0
