"""
SIMS Plus - Preschool Report Service

Business logic for preschool reports.
"""

from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.preschool import (
    LearningArea,
    PreschoolRating,
    PreschoolReport,
    StudentSkillAssessment,
    DevelopmentalSkill,
)
from app.models.student import Student
from app.schemas.preschool import (
    PreschoolReportCreate,
    PreschoolReportUpdate,
)
from app.services.preschool._shared import PreschoolServiceError


class PreschoolReportService:
    """Service for preschool reports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_report(
        self,
        tenant_id: UUID,
        data: PreschoolReportCreate,
    ) -> PreschoolReport:
        """Create a preschool report."""
        report = PreschoolReport(
            tenant_id=tenant_id,
            student_id=data.student_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            days_present=data.days_present,
            days_absent=data.days_absent,
            total_school_days=data.total_school_days,
            # mode='json' ensures UUIDs are serialized as strings for JSONB storage
            learning_area_summaries=[s.model_dump(mode='json') for s in data.learning_area_summaries] if data.learning_area_summaries else None,
            overall_progress=data.overall_progress,
            strengths=data.strengths,
            areas_for_growth=data.areas_for_growth,
            teacher_recommendations=data.teacher_recommendations,
            highlights=data.highlights,
            next_term_goals=data.next_term_goals,
            class_teacher_remark=data.class_teacher_remark,
            head_teacher_remark=data.head_teacher_remark,
            report_type=data.report_type,
            photo_urls=data.photo_urls,
        )
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def get_report(
        self,
        tenant_id: UUID,
        report_id: UUID,
    ) -> PreschoolReport:
        """Get a report by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(PreschoolReport)
            .where(
                and_(
                    PreschoolReport.id == report_id,
                    PreschoolReport.tenant_id == tenant_id,
                    PreschoolReport.deleted_at.is_(None),
                )
            )
        )
        report = result.scalar_one_or_none()
        if not report:
            raise PreschoolServiceError("Report not found", "not_found")
        return report

    async def list_reports(
        self,
        tenant_id: UUID,
        student_id: UUID | None = None,
        term_id: UUID | None = None,
        class_id: UUID | None = None,
        is_published: bool | None = None,
    ) -> Sequence[PreschoolReport]:
        """List reports with filters."""
        query = select(PreschoolReport).where(
            and_(
                PreschoolReport.tenant_id == tenant_id,
                PreschoolReport.deleted_at.is_(None),
            )
        )

        if student_id:
            query = query.where(PreschoolReport.student_id == student_id)
        if term_id:
            query = query.where(PreschoolReport.term_id == term_id)
        if class_id:
            query = query.where(PreschoolReport.class_id == class_id)
        if is_published is not None:
            query = query.where(PreschoolReport.is_published == is_published)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_report(
        self,
        report: PreschoolReport,
        data: PreschoolReportUpdate,
    ) -> PreschoolReport:
        """Update a report."""
        update_data = data.model_dump(exclude_unset=True)
        if "learning_area_summaries" in update_data and update_data["learning_area_summaries"]:
            update_data["learning_area_summaries"] = [
                s.model_dump() if hasattr(s, "model_dump") else s
                for s in update_data["learning_area_summaries"]
            ]
        for field, value in update_data.items():
            setattr(report, field, value)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def publish_reports(
        self,
        tenant_id: UUID,
        report_ids: list[UUID],
    ) -> list[PreschoolReport]:
        """Publish multiple reports."""
        result = await self.db.execute(
            select(PreschoolReport)
            .where(
                and_(
                    PreschoolReport.tenant_id == tenant_id,
                    PreschoolReport.id.in_(report_ids),
                    PreschoolReport.deleted_at.is_(None),
                )
            )
        )
        reports = list(result.scalars().all())
        if not reports:
            raise PreschoolServiceError("No matching reports found to publish", "not_found")
        now = datetime.utcnow()
        for report in reports:
            report.is_published = True
            report.published_at = now
        await self.db.flush()
        return reports

    async def generate_reports(
        self,
        tenant_id: UUID,
        class_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        report_type: str = "term",
    ) -> dict:
        """Generate reports for all students in a class for a given term.

        Pre-computes chart_data (radar chart) from skill assessments for each student.
        """
        # Get all active students in the class
        students_result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.class_id == class_id,
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                )
            )
        )
        students = students_result.scalars().all()

        # Determine which students already have reports for this term + type
        existing_reports_result = await self.db.execute(
            select(PreschoolReport.student_id).where(
                and_(
                    PreschoolReport.tenant_id == tenant_id,
                    PreschoolReport.class_id == class_id,
                    PreschoolReport.academic_year_id == academic_year_id,
                    PreschoolReport.term_id == term_id,
                    PreschoolReport.report_type == report_type,
                    PreschoolReport.deleted_at.is_(None),
                )
            )
        )
        existing_student_ids = set(existing_reports_result.scalars().all())

        # Create blank reports for students who don't have one yet
        generated_count = 0
        for student in students:
            if student.id not in existing_student_ids:
                # Pre-compute chart data from skill assessments
                chart_data = await self._compute_chart_data(
                    tenant_id, student.id, term_id
                )
                report = PreschoolReport(
                    tenant_id=tenant_id,
                    student_id=student.id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    class_id=class_id,
                    report_type=report_type,
                    chart_data=chart_data,
                )
                self.db.add(report)
                generated_count += 1

        if generated_count > 0:
            await self.db.flush()

        return {"generated": generated_count, "total_students": len(students)}

    async def _compute_chart_data(
        self,
        tenant_id: UUID,
        student_id: UUID,
        term_id: UUID,
    ) -> dict | None:
        """Compute radar chart data from student skill assessments.

        Returns: {
            "labels": ["SED", "LL", "MT", ...],
            "values": [3.5, 2.8, 4.0, ...],  # avg numeric_value per learning area
            "max_value": 4  # maximum possible rating value
        }

        Each value is the average numeric_value of all rated skills in that
        learning area for the given student and term.
        """
        # Get all assessments for this student/term that have ratings
        result = await self.db.execute(
            select(
                LearningArea.code.label("area_code"),
                func.avg(PreschoolRating.numeric_value).label("avg_value"),
            )
            .select_from(StudentSkillAssessment)
            .join(
                DevelopmentalSkill,
                DevelopmentalSkill.id == StudentSkillAssessment.skill_id,
            )
            .join(
                LearningArea,
                LearningArea.id == DevelopmentalSkill.learning_area_id,
            )
            .join(
                PreschoolRating,
                PreschoolRating.id == StudentSkillAssessment.rating_id,
            )
            .where(
                and_(
                    StudentSkillAssessment.tenant_id == tenant_id,
                    StudentSkillAssessment.student_id == student_id,
                    StudentSkillAssessment.term_id == term_id,
                    StudentSkillAssessment.rating_id.isnot(None),
                )
            )
            .group_by(LearningArea.code, LearningArea.display_order)
            .order_by(LearningArea.display_order)
        )
        rows = result.all()

        if not rows:
            return None

        labels = [row.area_code for row in rows]
        values = [round(float(row.avg_value), 2) for row in rows]

        # Determine max possible rating value from the tenant's rating scale
        max_result = await self.db.execute(
            select(func.max(PreschoolRating.numeric_value)).where(
                PreschoolRating.tenant_id == tenant_id,
            )
        )
        max_value = max_result.scalar() or 4

        return {
            "labels": labels,
            "values": values,
            "max_value": max_value,
        }
