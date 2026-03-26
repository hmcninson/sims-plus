"""
SIMS Plus - Capacity Planning Service

Manages enrollment targets and provides capacity dashboard data.
Dashboard queries use SQL aggregation (not Python-side loops) for efficiency.

AD-4: Capacity is advisory only -- warns but does not block enrollment.
"""

import uuid

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    AdmissionApplicationStatus,
    Application,
    EnrollmentTarget,
    TERMINAL_STATUSES,
)
from app.models.academic import AcademicYear, Class
from app.models.student import Student

logger = structlog.get_logger(__name__)


class CapacityServiceError(Exception):
    def __init__(self, message: str, code: str = "CAPACITY_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class CapacityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def set_target(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        academic_year_id: uuid.UUID,
        class_id: uuid.UUID,
        target_count: int,
        boarding_target: int | None = None,
        day_target: int | None = None,
    ) -> EnrollmentTarget:
        """
        Upsert enrollment target for a class/year.

        If a target already exists for this class/year, updates it.
        Otherwise, creates a new one.
        """
        # Validate academic year exists and belongs to tenant
        year_result = await self.db.execute(
            select(AcademicYear).filter(
                AcademicYear.id == academic_year_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if not year_result.scalar_one_or_none():
            raise CapacityServiceError("Academic year not found", "YEAR_NOT_FOUND")

        # Validate class exists and belongs to tenant
        class_result = await self.db.execute(
            select(Class).filter(
                Class.id == class_id,
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
            )
        )
        if not class_result.scalar_one_or_none():
            raise CapacityServiceError("Class not found", "CLASS_NOT_FOUND")

        # Check for existing target (upsert)
        existing_result = await self.db.execute(
            select(EnrollmentTarget).filter(
                EnrollmentTarget.tenant_id == tenant_id,
                EnrollmentTarget.academic_year_id == academic_year_id,
                EnrollmentTarget.class_id == class_id,
                EnrollmentTarget.deleted_at.is_(None),
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.target_count = target_count
            existing.boarding_target = boarding_target
            existing.day_target = day_target
            await self.db.flush()
            await self.db.refresh(existing)
            logger.info(
                "enrollment_target_updated",
                target_id=str(existing.id),
                class_id=str(class_id),
                target_count=target_count,
            )
            return existing

        target = EnrollmentTarget(
            tenant_id=tenant_id,
            school_id=school_id,
            academic_year_id=academic_year_id,
            class_id=class_id,
            target_count=target_count,
            boarding_target=boarding_target,
            day_target=day_target,
        )
        self.db.add(target)
        await self.db.flush()
        await self.db.refresh(target)

        logger.info(
            "enrollment_target_created",
            target_id=str(target.id),
            class_id=str(class_id),
            target_count=target_count,
        )
        return target

    async def get_targets(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> list[EnrollmentTarget]:
        """Get all enrollment targets for a school/year."""
        result = await self.db.execute(
            select(EnrollmentTarget)
            .filter(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                EnrollmentTarget.tenant_id == tenant_id,
                EnrollmentTarget.school_id == school_id,
                EnrollmentTarget.academic_year_id == academic_year_id,
                EnrollmentTarget.deleted_at.is_(None),
            )
            .order_by(EnrollmentTarget.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_dashboard(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> dict:
        """
        Build capacity dashboard with a single efficient query.

        For each class: joins classes, enrollment_targets, students (count),
        and applications (pipeline count) using SQL aggregation.
        """
        # Validate academic year
        year_result = await self.db.execute(
            select(AcademicYear).filter(
                AcademicYear.id == academic_year_id,
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if not year_result.scalar_one_or_none():
            raise CapacityServiceError("Academic year not found", "YEAR_NOT_FOUND")

        # Subquery: count of active students per class
        student_counts = (
            select(
                Student.class_id,
                func.count(Student.id).label("enrolled_count"),
            )
            .filter(
                Student.tenant_id == tenant_id,
                Student.school_id == school_id,
                Student.status == "active",
                Student.deleted_at.is_(None),
            )
            .group_by(Student.class_id)
            .subquery("student_counts")
        )

        # Subquery: count of non-terminal applications per target_class
        pipeline_statuses = [
            s.value
            for s in AdmissionApplicationStatus
            if s not in TERMINAL_STATUSES
        ]
        pipeline_counts = (
            select(
                Application.target_class_id,
                func.count(Application.id).label("pipeline_count"),
            )
            .filter(
                Application.tenant_id == tenant_id,
                Application.school_id == school_id,
                Application.status.in_(pipeline_statuses),
                Application.deleted_at.is_(None),
            )
            .group_by(Application.target_class_id)
            .subquery("pipeline_counts")
        )

        # Main query: classes LEFT JOIN targets, student counts, pipeline counts
        query = (
            select(
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Class.capacity.label("class_capacity"),
                EnrollmentTarget.target_count,
                EnrollmentTarget.boarding_target,
                EnrollmentTarget.day_target,
                func.coalesce(student_counts.c.enrolled_count, 0).label(
                    "current_enrolled"
                ),
                func.coalesce(pipeline_counts.c.pipeline_count, 0).label(
                    "applications_in_pipeline"
                ),
            )
            .select_from(Class)
            .outerjoin(
                EnrollmentTarget,
                and_(
                    EnrollmentTarget.class_id == Class.id,
                    EnrollmentTarget.academic_year_id == academic_year_id,
                    EnrollmentTarget.tenant_id == tenant_id,
                    EnrollmentTarget.deleted_at.is_(None),
                ),
            )
            .outerjoin(student_counts, student_counts.c.class_id == Class.id)
            .outerjoin(
                pipeline_counts, pipeline_counts.c.target_class_id == Class.id
            )
            .filter(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
                Class.is_active.is_(True),
            )
            .order_by(Class.sequence.asc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        classes = []
        total_capacity = 0
        total_target = 0
        total_enrolled = 0
        total_pipeline = 0

        for row in rows:
            capacity = row.class_capacity
            enrolled = row.current_enrolled
            target = row.target_count

            # Calculate utilization as percentage of physical capacity
            utilization = 0.0
            if capacity and capacity > 0:
                utilization = round(enrolled / capacity * 100, 1)

            classes.append(
                {
                    "class_id": row.class_id,
                    "class_name": row.class_name,
                    "capacity": capacity,
                    "target": target,
                    "boarding_target": row.boarding_target,
                    "day_target": row.day_target,
                    "current_enrolled": enrolled,
                    "applications_in_pipeline": row.applications_in_pipeline,
                    "utilization_pct": utilization,
                }
            )

            if capacity:
                total_capacity += capacity
            if target:
                total_target += target
            total_enrolled += enrolled
            total_pipeline += row.applications_in_pipeline

        return {
            "academic_year_id": academic_year_id,
            "school_id": school_id,
            "total_capacity": total_capacity or None,
            "total_target": total_target or None,
            "total_enrolled": total_enrolled,
            "total_pipeline": total_pipeline,
            "classes": classes,
        }

    async def check_capacity(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> dict:
        """
        Quick capacity check for a single class.

        Returns current enrollment vs physical capacity from the Class model.
        Used by application submission and enrollment endpoints to warn
        (advisory only, per AD-4) about full classes.
        """
        # Get class with capacity
        class_result = await self.db.execute(
            select(Class).filter(
                Class.id == class_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
            )
        )
        cls = class_result.scalar_one_or_none()
        if not cls:
            raise CapacityServiceError("Class not found", "CLASS_NOT_FOUND")

        # Count active students in this class
        count_result = await self.db.execute(
            select(func.count(Student.id)).filter(
                Student.class_id == class_id,
                Student.tenant_id == tenant_id,
                Student.school_id == school_id,
                Student.status == "active",
                Student.deleted_at.is_(None),
            )
        )
        current = count_result.scalar() or 0

        capacity = cls.capacity
        remaining = (capacity - current) if capacity is not None else None
        is_full = remaining is not None and remaining <= 0

        return {
            "class_id": class_id,
            "class_name": cls.name,
            "capacity": capacity,
            "current_enrolled": current,
            "remaining": remaining,
            "is_full": is_full,
        }
