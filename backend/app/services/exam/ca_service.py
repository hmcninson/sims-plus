"""
SIMS Plus - Continuous Assessment Service

Business logic for continuous assessment management.
"""

from datetime import datetime, UTC, date
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.exam import (
    ContinuousAssessment,
    AssessmentType,
)


class CAService:
    """Service for managing continuous assessments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_ca(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        student_id: UUID,
        assessment_type: str,
        title: str,
        assessment_date: date,
        max_score: Decimal = Decimal("10.00"),
        score: Optional[Decimal] = None,
        entered_by: Optional[UUID] = None,
    ) -> ContinuousAssessment:
        """Create a continuous assessment entry."""
        ca = ContinuousAssessment(
            tenant_id=tenant_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            class_id=class_id,
            subject_id=subject_id,
            student_id=student_id,
            assessment_type=AssessmentType(assessment_type),
            title=title,
            assessment_date=assessment_date,
            max_score=max_score,
            score=score,
            entered_by=entered_by,
        )
        self.db.add(ca)
        await self.db.flush()
        await self.db.refresh(ca)
        return ca

    async def bulk_create_ca(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        assessment_type: str,
        title: str,
        assessment_date: date,
        max_score: Decimal,
        scores: list[dict],
        entered_by: Optional[UUID] = None,
    ) -> dict:
        """Bulk create CA entries for multiple students."""
        success_count = 0
        failed_count = 0
        errors = []

        for score_entry in scores:
            try:
                await self.create_ca(
                    tenant_id=tenant_id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    class_id=class_id,
                    subject_id=subject_id,
                    student_id=score_entry["student_id"],
                    assessment_type=assessment_type,
                    title=title,
                    assessment_date=assessment_date,
                    max_score=max_score,
                    score=score_entry.get("score"),
                    entered_by=entered_by,
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "student_id": str(score_entry.get("student_id")),
                    "error": str(e),
                })

        return {
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
        }

    async def get_ca(self, tenant_id: UUID, ca_id: UUID) -> Optional[ContinuousAssessment]:
        """Get CA entry by ID."""
        result = await self.db.execute(
            select(ContinuousAssessment)
            .where(
                and_(
                    ContinuousAssessment.id == ca_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ContinuousAssessment.tenant_id == tenant_id,
                    ContinuousAssessment.deleted_at.is_(None),
                )
            )
            .options(
                joinedload(ContinuousAssessment.student),
                joinedload(ContinuousAssessment.subject),
            )
        )
        return result.scalar_one_or_none()

    async def list_ca(
        self,
        tenant_id: UUID,
        term_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
        subject_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        assessment_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[ContinuousAssessment], int]:
        """List CA entries with filters."""
        query = select(ContinuousAssessment).where(
            and_(
                ContinuousAssessment.tenant_id == tenant_id,
                ContinuousAssessment.deleted_at.is_(None),
            )
        )

        if term_id:
            query = query.where(ContinuousAssessment.term_id == term_id)
        if class_id:
            query = query.where(ContinuousAssessment.class_id == class_id)
        if subject_id:
            query = query.where(ContinuousAssessment.subject_id == subject_id)
        if student_id:
            query = query.where(ContinuousAssessment.student_id == student_id)
        if assessment_type:
            query = query.where(
                ContinuousAssessment.assessment_type == AssessmentType(assessment_type)
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(ContinuousAssessment.student),
            joinedload(ContinuousAssessment.subject),
            joinedload(ContinuousAssessment.class_),
        ).order_by(desc(ContinuousAssessment.assessment_date))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_ca(
        self, ca_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[ContinuousAssessment]:
        """Update CA entry."""
        ca = await self.get_ca(tenant_id, ca_id)
        if not ca:
            return None

        if "assessment_type" in kwargs and kwargs["assessment_type"]:
            kwargs["assessment_type"] = AssessmentType(kwargs["assessment_type"])

        for key, value in kwargs.items():
            if value is not None and hasattr(ca, key):
                setattr(ca, key, value)

        ca.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(ca)
        return ca

    async def delete_ca(self, ca_id: UUID, tenant_id: UUID) -> bool:
        """Delete CA entry."""
        ca = await self.get_ca(tenant_id, ca_id)
        if not ca:
            return False

        await self.db.delete(ca)
        await self.db.flush()
        return True

    async def get_ca_summary(
        self,
        tenant_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_id: UUID,
    ) -> list[dict]:
        """Get CA summary totals per student for a subject."""
        # Get subject info
        from app.models.academic import Subject
        subject_result = await self.db.execute(
            select(Subject).where(
                and_(Subject.id == subject_id, Subject.tenant_id == tenant_id)
            )
        )
        subject = subject_result.scalar_one_or_none()
        subject_name = subject.name if subject else "Unknown"

        # Get all CA entries (exclude soft-deleted)
        result = await self.db.execute(
            select(ContinuousAssessment)
            .where(
                and_(
                    ContinuousAssessment.tenant_id == tenant_id,
                    ContinuousAssessment.term_id == term_id,
                    ContinuousAssessment.class_id == class_id,
                    ContinuousAssessment.subject_id == subject_id,
                    ContinuousAssessment.deleted_at.is_(None),
                )
            )
            .options(joinedload(ContinuousAssessment.student))
        )
        ca_entries = result.scalars().unique().all()

        # Group by student
        student_totals = {}
        for ca in ca_entries:
            sid = ca.student_id
            if sid not in student_totals:
                student_totals[sid] = {
                    "student_id": sid,
                    "student_name": f"{ca.student.first_name} {ca.student.last_name}",
                    "total_max_score": Decimal("0"),
                    "total_score": Decimal("0"),
                    "count": 0,
                }
            student_totals[sid]["total_max_score"] += ca.max_score
            if ca.score is not None:
                student_totals[sid]["total_score"] += ca.score
            student_totals[sid]["count"] += 1

        # Calculate averages
        summaries = []
        for data in student_totals.values():
            avg = Decimal("0")
            if data["total_max_score"] > 0:
                avg = (data["total_score"] / data["total_max_score"]) * 100
            summaries.append({
                "student_id": data["student_id"],
                "student_name": data["student_name"],
                "subject_id": subject_id,
                "subject_name": subject_name,
                "total_assessments": data["count"],
                "total_max_score": data["total_max_score"],
                "total_score": data["total_score"],
                "average_percentage": avg.quantize(Decimal("0.01")),
            })

        return summaries
