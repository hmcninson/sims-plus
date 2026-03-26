"""
SIMS Plus - Admissions Analytics Service

Provides enrollment funnel, trends, lead source effectiveness, re-enrollment
rates, attrition analysis, and enrollment-vs-capacity comparisons.

All analytics use SQL aggregation -- no bulk-loading records into Python.
"""

import uuid

import structlog
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class
from app.models.admissions import (
    AdmissionApplicationStatus,
    Application,
    EnrollmentTarget,
    ReturnIntent,
    TERMINAL_STATUSES,
)
from app.models.student import Student

logger = structlog.get_logger(__name__)


class AnalyticsServiceError(Exception):
    def __init__(self, message: str, code: str = "ANALYTICS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class AdmissionsAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_full_funnel(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        period_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Full admissions funnel: inquiry -> application -> offered -> accepted -> enrolled.

        Each stage shows its count and conversion rate from the previous stage.
        Uses SQL COUNT with CASE expressions for single-pass aggregation.
        """
        # Inquiry count (from inquiries table if Phase 1 is deployed)
        inquiry_count = 0
        try:
            from app.models.admissions.inquiry import Inquiry

            inquiry_query = select(func.count(Inquiry.id)).filter(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Inquiry.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                Inquiry.deleted_at.is_(None),
            )
            inquiry_result = await self.db.execute(inquiry_query)
            inquiry_count = inquiry_result.scalar() or 0
        except Exception:
            # Inquiry model may not be available; graceful fallback
            pass

        # Application stage counts -- single query with CASE aggregation
        base_filter = [
            Application.tenant_id == tenant_id,
            Application.school_id == school_id,
            Application.deleted_at.is_(None),
        ]
        if period_id:
            base_filter.append(Application.admission_period_id == period_id)

        app_stats = await self.db.execute(
            select(
                func.count(Application.id).label("total"),
                func.count(
                    case(
                        (
                            Application.status.in_(
                                [
                                    AdmissionApplicationStatus.OFFERED.value,
                                    AdmissionApplicationStatus.ACCEPTED.value,
                                    AdmissionApplicationStatus.ENROLLED.value,
                                ]
                            ),
                            Application.id,
                        ),
                    )
                ).label("offered"),
                func.count(
                    case(
                        (
                            Application.status.in_(
                                [
                                    AdmissionApplicationStatus.ACCEPTED.value,
                                    AdmissionApplicationStatus.ENROLLED.value,
                                ]
                            ),
                            Application.id,
                        ),
                    )
                ).label("accepted"),
                func.count(
                    case(
                        (
                            Application.status
                            == AdmissionApplicationStatus.ENROLLED.value,
                            Application.id,
                        ),
                    )
                ).label("enrolled"),
            ).filter(*base_filter)
        )
        row = app_stats.one()
        application_count = row.total
        offered_count = row.offered
        accepted_count = row.accepted
        enrolled_count = row.enrolled

        def rate(numerator: int, denominator: int) -> float | None:
            if denominator == 0:
                return None
            return round(numerator / denominator * 100, 1)

        stages = [
            {
                "stage": "inquiry",
                "count": inquiry_count,
                "conversion_rate": None,
            },
            {
                "stage": "application",
                "count": application_count,
                "conversion_rate": rate(application_count, inquiry_count),
            },
            {
                "stage": "offered",
                "count": offered_count,
                "conversion_rate": rate(offered_count, application_count),
            },
            {
                "stage": "accepted",
                "count": accepted_count,
                "conversion_rate": rate(accepted_count, offered_count),
            },
            {
                "stage": "enrolled",
                "count": enrolled_count,
                "conversion_rate": rate(enrolled_count, accepted_count),
            },
        ]

        return {
            "school_id": school_id,
            "period_id": period_id,
            "stages": stages,
        }

    async def get_enrollment_trends(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        year_count: int = 3,
    ) -> dict:
        """
        Year-over-year enrollment counts by class.

        Queries the N most recent academic years and counts active students
        per class within each year. Uses SQL aggregation with GROUP BY.

        Note: Student model does not have academic_year_id; we count students
        currently in each class regardless of year. The "year" dimension
        comes from the academic year being the organizational context.
        """
        # Get the most recent N academic years
        years_result = await self.db.execute(
            select(AcademicYear)
            .filter(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
            .order_by(AcademicYear.start_date.desc())
            .limit(year_count)
        )
        years = list(years_result.scalars().all())

        if not years:
            return {"school_id": school_id, "years": []}

        # For trends, we count active students per class for the school.
        # Since students don't have academic_year_id, we provide current
        # enrollment breakdown for the most recent year and historical
        # application-based data for older years.
        year_data = []
        for year in reversed(years):  # Chronological order
            # Count enrolled applications per class for this year's periods
            from app.models.admissions import AdmissionPeriod

            counts_result = await self.db.execute(
                select(
                    Class.id.label("class_id"),
                    Class.name.label("class_name"),
                    func.count(Application.id).label("count"),
                )
                .select_from(Application)
                .join(
                    AdmissionPeriod,
                    Application.admission_period_id == AdmissionPeriod.id,
                )
                .join(Class, Application.target_class_id == Class.id)
                .filter(
                    Application.tenant_id == tenant_id,
                    Application.school_id == school_id,
                    Application.status == AdmissionApplicationStatus.ENROLLED.value,
                    Application.deleted_at.is_(None),
                    AdmissionPeriod.academic_year_id == year.id,
                    Class.deleted_at.is_(None),
                )
                .group_by(Class.id, Class.name)
                .order_by(Class.name)
            )
            class_counts = [
                {
                    "class_id": r.class_id,
                    "class_name": r.class_name,
                    "count": r.count,
                }
                for r in counts_result.all()
            ]

            total = sum(c["count"] for c in class_counts)

            year_data.append(
                {
                    "academic_year_id": year.id,
                    "academic_year_name": year.name,
                    "total_enrolled": total,
                    "by_class": class_counts,
                }
            )

        return {"school_id": school_id, "years": year_data}

    async def get_lead_source_effectiveness(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        period_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Lead source effectiveness: inquiries -> applications -> enrollments per source.

        Requires Phase 1 (inquiry model) to be deployed. Falls back gracefully
        if the inquiry table doesn't exist.
        """
        try:
            from app.models.admissions.inquiry import Inquiry

            base_filter = [
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Inquiry.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                Inquiry.deleted_at.is_(None),
            ]

            # Count inquiries, applications (converted), and enrollments per source
            source_stats = await self.db.execute(
                select(
                    Inquiry.source,
                    func.count(Inquiry.id).label("inquiry_count"),
                    func.count(
                        case(
                            (
                                Inquiry.status.in_(["applied", "enrolled"]),
                                Inquiry.id,
                            ),
                        )
                    ).label("application_count"),
                    func.count(
                        case(
                            (Inquiry.status == "enrolled", Inquiry.id),
                        )
                    ).label("enrollment_count"),
                )
                .filter(*base_filter)
                .group_by(Inquiry.source)
                .order_by(func.count(Inquiry.id).desc())
            )

            sources = []
            for row in source_stats.all():
                inq = row.inquiry_count
                app = row.application_count
                enr = row.enrollment_count
                sources.append(
                    {
                        "source": row.source,
                        "inquiry_count": inq,
                        "application_count": app,
                        "enrollment_count": enr,
                        "inquiry_to_application_rate": (
                            round(app / inq * 100, 1) if inq > 0 else 0.0
                        ),
                        "inquiry_to_enrollment_rate": (
                            round(enr / inq * 100, 1) if inq > 0 else 0.0
                        ),
                    }
                )

            return {
                "school_id": school_id,
                "period_id": period_id,
                "sources": sources,
            }

        except Exception:
            logger.warning(
                "lead_source_analytics_unavailable",
                reason="inquiry model not deployed",
            )
            return {
                "school_id": school_id,
                "period_id": period_id,
                "sources": [],
            }

    async def get_re_enrollment_rates(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        year_count: int = 3,
    ) -> dict:
        """
        Re-enrollment rates over multiple years.

        Uses return_intents data to determine how many students indicated
        they would return vs total surveyed, per academic year.
        """
        # Get recent years
        years_result = await self.db.execute(
            select(AcademicYear)
            .filter(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
            .order_by(AcademicYear.start_date.desc())
            .limit(year_count)
        )
        years = list(years_result.scalars().all())

        year_data = []
        for year in reversed(years):
            # Count return intents for this year using SQL aggregation
            stats_result = await self.db.execute(
                select(
                    func.count(ReturnIntent.id).label("total"),
                    func.count(
                        case(
                            (ReturnIntent.intent == "returning", ReturnIntent.id),
                        )
                    ).label("returning"),
                ).filter(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ReturnIntent.tenant_id == tenant_id,
                    ReturnIntent.school_id == school_id,
                    ReturnIntent.academic_year_id == year.id,
                    ReturnIntent.deleted_at.is_(None),
                )
            )
            row = stats_result.one()
            total = row.total
            returning = row.returning

            year_data.append(
                {
                    "academic_year_id": year.id,
                    "academic_year_name": year.name,
                    "total_students": total,
                    "returning_count": returning,
                    "re_enrollment_rate": (
                        round(returning / total * 100, 1) if total > 0 else 0.0
                    ),
                }
            )

        return {"school_id": school_id, "years": year_data}

    async def get_attrition_analysis(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Attrition analysis: withdrawn students and not-returning intents with reasons.

        Aggregates reasons from:
        1. Students with status='withdrawn' (from Student model)
        2. ReturnIntents with intent='not_returning' (from return intent surveys)
        """
        # Withdrawn students -- count
        withdrawn_filter = [
            Student.tenant_id == tenant_id,
            Student.school_id == school_id,
            Student.status == "withdrawn",
            Student.deleted_at.is_(None),
        ]

        withdrawn_result = await self.db.execute(
            select(func.count(Student.id)).filter(*withdrawn_filter)
        )
        withdrawn_count = withdrawn_result.scalar() or 0

        # Withdrawal reasons -- Student model may not have withdrawal_reason column
        withdrawal_reasons: list[dict] = []

        # Not-returning intents
        nr_filter = [
            ReturnIntent.tenant_id == tenant_id,
            ReturnIntent.school_id == school_id,
            ReturnIntent.intent == "not_returning",
            ReturnIntent.deleted_at.is_(None),
        ]
        if academic_year_id:
            nr_filter.append(ReturnIntent.academic_year_id == academic_year_id)

        nr_result = await self.db.execute(
            select(func.count(ReturnIntent.id)).filter(*nr_filter)
        )
        not_returning_count = nr_result.scalar() or 0

        # Not-returning reasons grouped
        nr_reason_result = await self.db.execute(
            select(
                ReturnIntent.reason,
                func.count(ReturnIntent.id).label("count"),
            )
            .filter(
                *nr_filter,
                ReturnIntent.reason.isnot(None),
            )
            .group_by(ReturnIntent.reason)
            .order_by(func.count(ReturnIntent.id).desc())
        )
        not_returning_reasons = [
            {"reason": r.reason, "count": r.count}
            for r in nr_reason_result.all()
        ]

        return {
            "school_id": school_id,
            "academic_year_id": academic_year_id,
            "withdrawn_count": withdrawn_count,
            "not_returning_count": not_returning_count,
            "total_attrition": withdrawn_count + not_returning_count,
            "withdrawal_reasons": withdrawal_reasons,
            "not_returning_reasons": not_returning_reasons,
        }

    async def get_enrollment_vs_capacity(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> dict:
        """
        Per-class comparison of target, actual enrollment, and physical capacity.

        Single efficient query joining classes, enrollment_targets, and student counts.
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
            raise AnalyticsServiceError(
                "Academic year not found", "YEAR_NOT_FOUND"
            )

        # Student counts per class (subquery)
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

        # Main query
        query = (
            select(
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Class.capacity.label("capacity"),
                EnrollmentTarget.target_count.label("target"),
                func.coalesce(student_counts.c.enrolled_count, 0).label(
                    "actual_enrolled"
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
        total_target = 0
        total_enrolled = 0
        total_capacity = 0

        for row in rows:
            target = row.target
            actual = row.actual_enrolled
            capacity = row.capacity

            variance = (actual - target) if target is not None else None
            fill_pct = (
                round(actual / capacity * 100, 1)
                if capacity and capacity > 0
                else None
            )

            classes.append(
                {
                    "class_id": row.class_id,
                    "class_name": row.class_name,
                    "target": target,
                    "actual_enrolled": actual,
                    "capacity": capacity,
                    "variance": variance,
                    "fill_pct": fill_pct,
                }
            )

            if target:
                total_target += target
            total_enrolled += actual
            if capacity:
                total_capacity += capacity

        return {
            "school_id": school_id,
            "academic_year_id": academic_year_id,
            "classes": classes,
            "total_target": total_target or None,
            "total_enrolled": total_enrolled,
            "total_capacity": total_capacity or None,
        }
