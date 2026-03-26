"""
SIMS Plus - Credit Accumulation Service

Business logic for tracking student credit accumulation, GPA calculation,
and transcript data generation for American and IB curricula.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

import re

import structlog
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicYear, Subject, Term
from app.models.curriculum import CurriculumProfile, StudentCreditAccumulation
from app.models.school import School
from app.models.student import Student
from app.services.curriculum._shared import CurriculumServiceError

logger = structlog.get_logger()

# Strict hex color regex for CSS injection prevention
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# GPA thresholds for honor roll classification
_HONOR_ROLL_GPA = Decimal("3.5")

# Maximum GPA caps for weighted calculations
_MAX_AP_GPA = Decimal("5.0")
_MAX_HONORS_GPA = Decimal("4.5")
_MAX_STANDARD_GPA = Decimal("4.0")


class CreditService:
    """Service for student credit accumulation and GPA calculations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Tenant FK Validation
    # =========================

    async def _validate_student(self, student_id: UUID, tenant_id: UUID) -> Student:
        """Validate that a student exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Student).where(
                Student.id == student_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Student.tenant_id == tenant_id,
                Student.deleted_at.is_(None),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise CurriculumServiceError("Student not found", "not_found")
        return student

    async def _validate_profile(
        self, profile_id: UUID, tenant_id: UUID
    ) -> CurriculumProfile:
        """Validate that a curriculum profile exists and belongs to the tenant."""
        result = await self.db.execute(
            select(CurriculumProfile).where(
                CurriculumProfile.id == profile_id,
                CurriculumProfile.tenant_id == tenant_id,
                CurriculumProfile.deleted_at.is_(None),
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise CurriculumServiceError(
                "Curriculum profile not found", "not_found"
            )
        return profile

    async def _validate_subject(self, subject_id: UUID, tenant_id: UUID) -> Subject:
        """Validate that a subject exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.tenant_id == tenant_id,
                Subject.deleted_at.is_(None),
            )
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise CurriculumServiceError("Subject not found", "not_found")
        return subject

    async def _validate_academic_year(
        self, academic_year_id: UUID, tenant_id: UUID
    ) -> AcademicYear:
        """Validate that an academic year exists and belongs to the tenant."""
        result = await self.db.execute(
            select(AcademicYear).where(
                AcademicYear.id == academic_year_id,
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        year = result.scalar_one_or_none()
        if not year:
            raise CurriculumServiceError("Academic year not found", "not_found")
        return year

    # =========================
    # Credit CRUD
    # =========================

    async def record_credit(
        self,
        tenant_id: UUID,
        school_id: UUID,
        data,
    ) -> StudentCreditAccumulation:
        """
        Create or update a credit record for a student.

        Uses upsert semantics: if a record already exists for the same
        student/subject/year/term combination, it is updated in place.
        """
        # Validate all FK references belong to this tenant
        await self._validate_student(data.student_id, tenant_id)
        await self._validate_subject(data.subject_id, tenant_id)
        await self._validate_profile(data.curriculum_profile_id, tenant_id)
        await self._validate_academic_year(data.academic_year_id, tenant_id)

        if data.term_id:
            term_result = await self.db.execute(
                select(Term).where(
                    Term.id == data.term_id,
                    Term.tenant_id == tenant_id,
                )
            )
            if not term_result.scalar_one_or_none():
                raise CurriculumServiceError("Term not found", "not_found")

        # Calculate weighted grade points for AP/Honors courses
        weighted_gp = data.weighted_grade_points
        if weighted_gp is None and data.grade_points is not None:
            weighted_gp = self._calculate_weighted_grade_points(
                data.grade_points, data.is_ap, data.is_honors
            )

        # Check for existing record (upsert)
        term_filter = (
            StudentCreditAccumulation.term_id == data.term_id
            if data.term_id
            else StudentCreditAccumulation.term_id.is_(None)
        )
        existing_result = await self.db.execute(
            select(StudentCreditAccumulation).where(
                StudentCreditAccumulation.tenant_id == tenant_id,
                StudentCreditAccumulation.student_id == data.student_id,
                StudentCreditAccumulation.subject_id == data.subject_id,
                StudentCreditAccumulation.academic_year_id == data.academic_year_id,
                term_filter,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.credits_attempted = data.credits_attempted
            existing.credits_earned = data.credits_earned
            existing.grade_points = data.grade_points
            existing.weighted_grade_points = weighted_gp
            existing.is_ap = data.is_ap
            existing.is_honors = data.is_honors
            existing.curriculum_profile_id = data.curriculum_profile_id
            await self.db.flush()
            await self.db.refresh(existing)

            logger.info(
                "credit_record_updated",
                student_id=str(data.student_id),
                subject_id=str(data.subject_id),
            )
            return existing

        record = StudentCreditAccumulation(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=data.student_id,
            subject_id=data.subject_id,
            curriculum_profile_id=data.curriculum_profile_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            credits_attempted=data.credits_attempted,
            credits_earned=data.credits_earned,
            grade_points=data.grade_points,
            weighted_grade_points=weighted_gp,
            is_ap=data.is_ap,
            is_honors=data.is_honors,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        logger.info(
            "credit_record_created",
            student_id=str(data.student_id),
            subject_id=str(data.subject_id),
        )
        return record

    async def get_student_credits(
        self,
        tenant_id: UUID,
        student_id: UUID,
        profile_id: UUID,
        academic_year_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[StudentCreditAccumulation], int]:
        """Get paginated credit records for a student under a curriculum profile."""
        await self._validate_student(student_id, tenant_id)
        await self._validate_profile(profile_id, tenant_id)

        base_filter = and_(
            StudentCreditAccumulation.tenant_id == tenant_id,
            StudentCreditAccumulation.student_id == student_id,
            StudentCreditAccumulation.curriculum_profile_id == profile_id,
        )
        if academic_year_id:
            base_filter = and_(
                base_filter,
                StudentCreditAccumulation.academic_year_id == academic_year_id,
            )

        # Count
        count_result = await self.db.execute(
            select(func.count(StudentCreditAccumulation.id)).where(base_filter)
        )
        total = count_result.scalar_one()

        # Paginated query
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(StudentCreditAccumulation)
            .where(base_filter)
            .order_by(StudentCreditAccumulation.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        records = list(result.scalars().all())

        return records, total

    # =========================
    # GPA Calculation
    # =========================

    @staticmethod
    def _calculate_weighted_grade_points(
        grade_points: Decimal,
        is_ap: bool,
        is_honors: bool,
    ) -> Decimal:
        """
        Calculate weighted grade points based on course type.

        AP courses receive a +1.0 bonus (capped at 5.0).
        Honors courses receive a +0.5 bonus (capped at 4.5).
        """
        if is_ap:
            return min(grade_points + Decimal("1.0"), _MAX_AP_GPA)
        if is_honors:
            return min(grade_points + Decimal("0.5"), _MAX_HONORS_GPA)
        return min(grade_points, _MAX_STANDARD_GPA)

    async def get_student_gpa(
        self,
        tenant_id: UUID,
        student_id: UUID,
        profile_id: UUID,
        academic_year_id: UUID | None = None,
        term_id: UUID | None = None,
    ) -> dict:
        """
        Calculate GPA for a student.

        Returns both term-specific and cumulative GPAs:
        - Unweighted GPA = sum(grade_points) / count(subjects with grade_points)
        - Weighted GPA = sum(weighted_grade_points) / count(subjects with weighted_grade_points)
        """
        await self._validate_student(student_id, tenant_id)
        await self._validate_profile(profile_id, tenant_id)

        base_filter = and_(
            StudentCreditAccumulation.tenant_id == tenant_id,
            StudentCreditAccumulation.student_id == student_id,
            StudentCreditAccumulation.curriculum_profile_id == profile_id,
        )

        # Term/year-specific GPA
        term_gpa = None
        weighted_gpa = None
        if term_id or academic_year_id:
            term_filter = base_filter
            if academic_year_id:
                term_filter = and_(
                    term_filter,
                    StudentCreditAccumulation.academic_year_id == academic_year_id,
                )
            if term_id:
                term_filter = and_(
                    term_filter,
                    StudentCreditAccumulation.term_id == term_id,
                )

            term_result = await self.db.execute(
                select(
                    (
                        func.sum(StudentCreditAccumulation.grade_points * StudentCreditAccumulation.credits_attempted)
                        / func.nullif(func.sum(StudentCreditAccumulation.credits_attempted), 0)
                    ),
                    (
                        func.sum(StudentCreditAccumulation.weighted_grade_points * StudentCreditAccumulation.credits_attempted)
                        / func.nullif(func.sum(StudentCreditAccumulation.credits_attempted), 0)
                    ),
                ).where(
                    term_filter,
                    StudentCreditAccumulation.grade_points.isnot(None),
                )
            )
            row = term_result.one()
            term_gpa = (
                row[0].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if row[0] is not None
                else None
            )
            weighted_gpa = (
                row[1].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if row[1] is not None
                else None
            )

        # Cumulative GPA (all years) — credit-weighted
        cum_result = await self.db.execute(
            select(
                (
                    func.sum(StudentCreditAccumulation.grade_points * StudentCreditAccumulation.credits_attempted)
                    / func.nullif(func.sum(StudentCreditAccumulation.credits_attempted), 0)
                ),
                (
                    func.sum(StudentCreditAccumulation.weighted_grade_points * StudentCreditAccumulation.credits_attempted)
                    / func.nullif(func.sum(StudentCreditAccumulation.credits_attempted), 0)
                ),
                func.sum(StudentCreditAccumulation.credits_attempted),
                func.sum(StudentCreditAccumulation.credits_earned),
            ).where(
                base_filter,
                StudentCreditAccumulation.grade_points.isnot(None),
            )
        )
        cum_row = cum_result.one()

        cumulative_gpa = (
            cum_row[0].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if cum_row[0] is not None
            else None
        )
        cumulative_weighted_gpa = (
            cum_row[1].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if cum_row[1] is not None
            else None
        )
        total_attempted = cum_row[2] or Decimal("0")
        total_earned = cum_row[3] or Decimal("0")

        # Honor roll: cumulative weighted GPA >= 3.5
        honor_roll = (
            cumulative_weighted_gpa >= _HONOR_ROLL_GPA
            if cumulative_weighted_gpa is not None
            else False
        )

        return {
            "student_id": student_id,
            "curriculum_profile_id": profile_id,
            "term_gpa": term_gpa,
            "weighted_gpa": weighted_gpa,
            "cumulative_gpa": cumulative_gpa,
            "cumulative_weighted_gpa": cumulative_weighted_gpa,
            "total_credits_attempted": total_attempted,
            "total_credits_earned": total_earned,
            "honor_roll": honor_roll,
        }

    # =========================
    # Recalculation
    # =========================

    async def recalculate_credits(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_id: UUID,
        profile_id: UUID,
    ) -> int:
        """
        Recalculate all credit records for a student from term reports.

        Deletes existing records and rebuilds from exam score data.
        Returns the count of records updated/created.
        """
        from app.models.curriculum import SubjectCurriculumMapping
        from app.models.exam import ExamScore, TermReport

        await self._validate_student(student_id, tenant_id)
        profile = await self._validate_profile(profile_id, tenant_id)

        if not profile.use_credits:
            raise CurriculumServiceError(
                "Credit tracking is not enabled for this curriculum profile",
                "invalid_operation",
            )

        # Delete existing credit records for this student+profile
        await self.db.execute(
            delete(StudentCreditAccumulation).where(
                StudentCreditAccumulation.tenant_id == tenant_id,
                StudentCreditAccumulation.student_id == student_id,
                StudentCreditAccumulation.curriculum_profile_id == profile_id,
            )
        )

        # Fetch subject-curriculum mappings that define credit values
        mapping_result = await self.db.execute(
            select(SubjectCurriculumMapping).where(
                SubjectCurriculumMapping.tenant_id == tenant_id,
                SubjectCurriculumMapping.curriculum_profile_id == profile_id,
            )
        )
        mappings = {m.subject_id: m for m in mapping_result.scalars().all()}

        if not mappings:
            logger.info(
                "no_subject_mappings_for_recalculation",
                student_id=str(student_id),
                profile_id=str(profile_id),
            )
            return 0

        # Fetch term reports for this student
        report_result = await self.db.execute(
            select(TermReport).where(
                TermReport.tenant_id == tenant_id,
                TermReport.student_id == student_id,
            )
        )
        reports = report_result.scalars().all()

        count = 0
        for report in reports:
            # Each term report contains subject scores in report_data JSONB
            if not report.report_data:
                continue

            subjects_data = report.report_data.get("subjects", [])
            for subj in subjects_data:
                subject_id_str = subj.get("subject_id")
                if not subject_id_str:
                    continue

                from uuid import UUID as _UUID

                try:
                    subject_id = _UUID(subject_id_str)
                except (ValueError, TypeError):
                    continue

                mapping = mappings.get(subject_id)
                if not mapping or not mapping.credits:
                    continue

                total_score = subj.get("total_score")
                grade_value = subj.get("grade")

                # Determine if credits were earned (passing grade)
                credits_attempted = mapping.credits
                # Credits earned only if score >= 50%
                credits_earned = (
                    credits_attempted
                    if total_score is not None and total_score >= 50
                    else Decimal("0")
                )

                # Grade points from score (simplified 4.0 scale)
                grade_points = None
                if total_score is not None:
                    grade_points = self._score_to_grade_points(Decimal(str(total_score)))

                # Determine AP/Honors from mapping level
                is_ap = (mapping.level or "").lower() == "ap"
                is_honors = (mapping.level or "").lower() == "honors"

                weighted_gp = None
                if grade_points is not None:
                    weighted_gp = self._calculate_weighted_grade_points(
                        grade_points, is_ap, is_honors
                    )

                record = StudentCreditAccumulation(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    student_id=student_id,
                    curriculum_profile_id=profile_id,
                    academic_year_id=report.academic_year_id,
                    term_id=report.term_id,
                    subject_id=subject_id,
                    credits_attempted=credits_attempted,
                    credits_earned=credits_earned,
                    grade_points=grade_points,
                    weighted_grade_points=weighted_gp,
                    is_ap=is_ap,
                    is_honors=is_honors,
                )
                self.db.add(record)
                count += 1

        await self.db.flush()

        logger.info(
            "credits_recalculated",
            student_id=str(student_id),
            profile_id=str(profile_id),
            records_created=count,
        )
        return count

    @staticmethod
    def _score_to_grade_points(score: Decimal) -> Decimal:
        """
        Convert a percentage score to a 4.0 scale grade point.

        Standard American GPA scale:
        A  (90-100) = 4.0
        B+ (85-89)  = 3.5
        B  (80-84)  = 3.0
        C+ (75-79)  = 2.5
        C  (70-74)  = 2.0
        D+ (65-69)  = 1.5
        D  (60-64)  = 1.0
        F  (0-59)   = 0.0
        """
        if score >= 90:
            return Decimal("4.0")
        if score >= 85:
            return Decimal("3.5")
        if score >= 80:
            return Decimal("3.0")
        if score >= 75:
            return Decimal("2.5")
        if score >= 70:
            return Decimal("2.0")
        if score >= 65:
            return Decimal("1.5")
        if score >= 60:
            return Decimal("1.0")
        return Decimal("0.0")

    # =========================
    # Transcript Data
    # =========================

    async def generate_transcript_data(
        self,
        tenant_id: UUID,
        student_id: UUID,
        profile_id: UUID,
        school_id: UUID | None = None,
    ) -> dict:
        """
        Generate full transcript data for a student.

        Assembles credit records grouped by academic year and term,
        with per-term and cumulative GPA calculations.
        """
        student = await self._validate_student(student_id, tenant_id)
        profile = await self._validate_profile(profile_id, tenant_id)

        # Fetch school for transcript header
        school_filter = [
            School.tenant_id == tenant_id,
            School.deleted_at.is_(None),
        ]
        if school_id:
            school_filter.append(School.id == school_id)
        school_result = await self.db.execute(
            select(School).where(*school_filter).limit(1)
        )
        school = school_result.scalar_one_or_none()

        # Fetch all credit records for this student+profile
        credit_result = await self.db.execute(
            select(StudentCreditAccumulation).where(
                StudentCreditAccumulation.tenant_id == tenant_id,
                StudentCreditAccumulation.student_id == student_id,
                StudentCreditAccumulation.curriculum_profile_id == profile_id,
            ).order_by(StudentCreditAccumulation.created_at)
        )
        records = credit_result.scalars().all()

        # Fetch subjects and academic years for display names
        subject_ids = {r.subject_id for r in records}
        year_ids = {r.academic_year_id for r in records}
        term_ids = {r.term_id for r in records if r.term_id}

        subjects_map = {}
        if subject_ids:
            subj_result = await self.db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.id.in_(subject_ids),
                )
            )
            subjects_map = {s.id: s for s in subj_result.scalars().all()}

        years_map = {}
        if year_ids:
            year_result = await self.db.execute(
                select(AcademicYear).where(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.id.in_(year_ids),
                )
            )
            years_map = {y.id: y for y in year_result.scalars().all()}

        terms_map = {}
        if term_ids:
            term_result = await self.db.execute(
                select(Term).where(
                    Term.tenant_id == tenant_id,
                    Term.id.in_(term_ids),
                )
            )
            terms_map = {t.id: t for t in term_result.scalars().all()}

        # Group records by academic_year + term
        from collections import defaultdict

        grouped: dict[tuple, list] = defaultdict(list)
        for r in records:
            key = (r.academic_year_id, r.term_id)
            grouped[key].append(r)

        academic_records = []
        total_credits_earned = Decimal("0")
        all_grade_points = []
        all_weighted_grade_points = []
        honors_list = []

        def _sort_key(item):
            year_id, term_id = item[0]
            year = years_map.get(year_id)
            term = terms_map.get(term_id) if term_id else None
            return (
                year.start_date if year and getattr(year, "start_date", None) else date.min,
                term.start_date if term and getattr(term, "start_date", None) else date.min,
            )

        for (year_id, t_id), group in sorted(grouped.items(), key=_sort_key):
            year = years_map.get(year_id)
            term = terms_map.get(t_id) if t_id else None

            term_subjects = []
            term_gp_sum = Decimal("0")
            term_weighted_gp_sum = Decimal("0")
            term_gp_credits = Decimal("0")
            term_credits = Decimal("0")

            for r in group:
                subj = subjects_map.get(r.subject_id)
                term_subjects.append({
                    "subject_name": subj.name if subj else "Unknown",
                    "subject_code": subj.code if subj and hasattr(subj, "code") else None,
                    "grade": None,  # Grade letter not stored on credit record
                    "credits_attempted": r.credits_attempted,
                    "credits_earned": r.credits_earned,
                    "grade_points": r.grade_points,
                    "is_ap": r.is_ap,
                    "is_honors": r.is_honors,
                })
                term_credits += r.credits_earned
                total_credits_earned += r.credits_earned

                if r.grade_points is not None:
                    term_gp_sum += r.grade_points * r.credits_attempted
                    term_gp_credits += r.credits_attempted
                    all_grade_points.append((r.grade_points, r.credits_attempted))
                if r.weighted_grade_points is not None:
                    term_weighted_gp_sum += r.weighted_grade_points * r.credits_attempted
                    all_weighted_grade_points.append((r.weighted_grade_points, r.credits_attempted))

            term_gpa = None
            if term_gp_credits > 0:
                term_gpa = (
                    term_gp_sum / term_gp_credits
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            academic_records.append({
                "academic_year": year.name if year else "Unknown",
                "term": term.name if term else None,
                "subjects": term_subjects,
                "term_gpa": term_gpa,
                "term_credits_earned": term_credits,
            })

        # Cumulative calculations — credit-weighted
        cumulative_gpa = None
        if all_grade_points:
            total_gp_credits = sum(c for _, c in all_grade_points)
            if total_gp_credits > 0:
                cumulative_gpa = (
                    sum(gp * c for gp, c in all_grade_points) / total_gp_credits
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        weighted_gpa = None
        if all_weighted_grade_points:
            total_wgp_credits = sum(c for _, c in all_weighted_grade_points)
            if total_wgp_credits > 0:
                weighted_gpa = (
                    sum(gp * c for gp, c in all_weighted_grade_points) / total_wgp_credits
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Honor roll check
        if weighted_gpa and weighted_gpa >= _HONOR_ROLL_GPA:
            honors_list.append("Honor Roll")
        if weighted_gpa and weighted_gpa >= Decimal("3.8"):
            honors_list.append("Dean's List")

        # Graduation credits from profile config
        graduation_credits = None
        credits_remaining = None
        if profile.config and isinstance(profile.config, dict):
            graduation_credits = profile.config.get("graduation_credits_required")
            if graduation_credits is not None:
                graduation_credits = Decimal(str(graduation_credits))
                credits_remaining = max(
                    graduation_credits - total_credits_earned, Decimal("0")
                )

        # Sanitize primary_color to prevent CSS injection in transcript template
        raw_color = getattr(school, "primary_color", None) or ""
        safe_color = raw_color if _HEX_COLOR_RE.match(raw_color) else None

        return {
            "student_id": student_id,
            "student_name": f"{student.first_name} {student.last_name}",
            "curriculum_profile": profile.name,
            "school": {
                "name": school.name if school else "Unknown",
                "address": getattr(school, "address", None),
                "logo_url": getattr(school, "logo_url", None),
                "primary_color": safe_color,
            },
            "academic_records": academic_records,
            "cumulative_gpa": cumulative_gpa,
            "weighted_gpa": weighted_gpa,
            "total_credits_earned": total_credits_earned,
            "graduation_credits_required": graduation_credits,
            "credits_remaining": credits_remaining,
            "honors": honors_list,
            "generated_at": datetime.now(timezone.utc),
        }
