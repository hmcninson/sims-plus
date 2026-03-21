"""
SIMS Plus - PDF Generation Service

Service for generating PDF documents using WeasyPrint.
"""

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.preschool import (
    PreschoolReport,
    LearningArea,
    DevelopmentalSkill,
    StudentSkillAssessment,
    PreschoolRating,
)
from app.models.student import Student
from app.models.school import School
from app.models.academic import AcademicYear, Term, Class, ClassSection, GradingScale, Grade, AssessmentWeight
from app.models.exam import TermReport
from app.models.finance import Invoice, InvoiceItem, Payment


class PDFService:
    """Service for generating PDF documents."""

    # Templates directory
    TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "reports"

    # Curriculum-specific report card templates.
    # Each key maps a CurriculumType value to its HTML template file.
    # Edexcel reuses the Cambridge layout since both follow the same
    # component-based British assessment structure.
    REPORT_TEMPLATES: dict[str, str] = {
        "ges": "term_report.html",
        "cambridge": "cambridge_report.html",
        "edexcel": "cambridge_report.html",
        "american": "american_report.html",
        "ib": "ib_report.html",
        "french": "french_report.html",
        "montessori": "montessori_report.html",
        "default": "term_report.html",
    }

    @classmethod
    def get_report_template(cls, profile) -> str:
        """
        Get the template filename for a curriculum profile.

        Falls back to the default GES template when the profile is None
        or when the curriculum type is not recognized (e.g., 'custom').
        """
        if profile is None:
            return cls.REPORT_TEMPLATES["default"]
        # Handle both enum instances and plain strings
        curriculum_type = (
            profile.curriculum_type.value
            if hasattr(profile.curriculum_type, "value")
            else profile.curriculum_type
        )
        return cls.REPORT_TEMPLATES.get(
            curriculum_type, cls.REPORT_TEMPLATES["default"]
        )

    @classmethod
    def _get_jinja_env(cls) -> Environment:
        """Get Jinja2 environment configured for PDF templates."""
        return Environment(
            loader=FileSystemLoader(str(cls.TEMPLATES_DIR)),
            autoescape=True,
        )

    @classmethod
    def _calculate_age(cls, date_of_birth: date | None) -> int:
        """Calculate age from date of birth."""
        if not date_of_birth:
            return 0
        today = date.today()
        age = today.year - date_of_birth.year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
        return age

    @classmethod
    async def generate_preschool_report_pdf(
        cls,
        db: AsyncSession,
        tenant_id: UUID,
        report_id: UUID,
    ) -> tuple[bytes, str]:
        """
        Generate a PDF for a preschool progress report.

        Returns tuple of (pdf_bytes, filename).
        """
        # Fetch the report with related data
        report_result = await db.execute(
            select(PreschoolReport)
            .where(
                and_(
                    PreschoolReport.id == report_id,
                    PreschoolReport.tenant_id == tenant_id,
                    PreschoolReport.deleted_at.is_(None),
                )
            )
        )
        report = report_result.scalar_one_or_none()

        if not report:
            raise ValueError("Report not found")

        if not report.is_published:
            raise ValueError("Only published reports can be downloaded as PDF")

        # Fetch student
        student_result = await db.execute(
            select(Student).where(Student.id == report.student_id)
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")

        # Fetch school
        school_result = await db.execute(
            select(School).where(School.tenant_id == tenant_id)
        )
        school = school_result.scalar_one_or_none()

        # Fetch academic year with terms
        academic_year_result = await db.execute(
            select(AcademicYear)
            .options(selectinload(AcademicYear.terms))
            .where(AcademicYear.id == report.academic_year_id)
        )
        academic_year = academic_year_result.scalar_one_or_none()

        # Fetch term
        term_result = await db.execute(
            select(Term).where(Term.id == report.term_id)
        )
        term = term_result.scalar_one_or_none()

        # Fetch class
        class_result = await db.execute(
            select(Class).where(Class.id == report.class_id)
        )
        student_class = class_result.scalar_one_or_none()

        # Fetch learning areas with skills
        learning_areas_result = await db.execute(
            select(LearningArea)
            .options(selectinload(LearningArea.skills))
            .where(
                and_(
                    LearningArea.tenant_id == tenant_id,
                    LearningArea.deleted_at.is_(None),
                )
            )
            .order_by(LearningArea.display_order, LearningArea.name)
        )
        learning_areas = learning_areas_result.scalars().all()

        # Fetch assessments for this student and term
        assessments_result = await db.execute(
            select(StudentSkillAssessment)
            .options(selectinload(StudentSkillAssessment.rating))
            .where(
                and_(
                    StudentSkillAssessment.student_id == student.id,
                    StudentSkillAssessment.term_id == report.term_id,
                    StudentSkillAssessment.tenant_id == tenant_id,
                )
            )
        )
        assessments_list = assessments_result.scalars().all()

        # Create assessments lookup by skill_id
        assessments = {a.skill_id: a for a in assessments_list}

        # Calculate attendance percentage
        attendance_percentage = 0
        if report.total_school_days and report.total_school_days > 0:
            attendance_percentage = round(
                ((report.days_present or 0) / report.total_school_days) * 100
            )

        # Prepare learning areas with their skills for template
        areas_with_skills = []
        for area in learning_areas:
            area_data = {
                "name": area.name,
                "skills": [
                    {"id": skill.id, "name": skill.name}
                    for skill in sorted(area.skills, key=lambda s: (s.display_order or 0, s.name))
                    if skill.deleted_at is None
                ]
            }
            if area_data["skills"]:  # Only include areas with skills
                areas_with_skills.append(area_data)

        # Prepare template context
        context = {
            "report": report,
            "student": student,
            "school": school or {},
            "academic_year": academic_year or {},
            "term": term or {},
            "class_name": student_class.name if student_class else "",
            "age": cls._calculate_age(student.date_of_birth),
            "learning_areas": areas_with_skills,
            "assessments": assessments,
            "attendance_percentage": attendance_percentage,
            "current_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

        # Render HTML template
        env = cls._get_jinja_env()
        template = env.get_template("preschool_report.html")
        html_content = template.render(**context)

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_bytes = pdf_buffer.getvalue()

        # Generate filename
        student_name = f"{student.first_name}_{student.last_name}".replace(" ", "_")
        term_name = term.name.replace(" ", "_") if term else "Term"
        filename = f"Progress_Report_{student_name}_{term_name}.pdf"

        return pdf_bytes, filename

    @classmethod
    async def generate_term_report_pdf(
        cls,
        db: AsyncSession,
        tenant_id: UUID,
        report_id: UUID,
    ) -> tuple[bytes, str]:
        """
        Generate a PDF for a term report card.

        Returns tuple of (pdf_bytes, filename).
        """
        from app.services.exam import TermReportService
        from sqlalchemy.orm import joinedload

        # Fetch the report with related data
        report_result = await db.execute(
            select(TermReport)
            .where(
                and_(
                    TermReport.id == report_id,
                    TermReport.tenant_id == tenant_id,
                )
            )
            .options(
                joinedload(TermReport.student),
                joinedload(TermReport.class_),
                joinedload(TermReport.section),
                joinedload(TermReport.term),
                joinedload(TermReport.academic_year),
            )
        )
        report = report_result.scalar_one_or_none()

        if not report:
            raise ValueError("Report not found")

        student = report.student
        if not student:
            raise ValueError("Student not found")

        # Fetch school
        school_result = await db.execute(
            select(School).where(School.tenant_id == tenant_id)
        )
        school = school_result.scalar_one_or_none()

        # Get section name
        section_name = report.section.name if report.section else None

        # Get assessment weights for display
        weights_result = await db.execute(
            select(AssessmentWeight).where(
                and_(
                    AssessmentWeight.tenant_id == tenant_id,
                )
            )
        )
        weights = weights_result.scalar_one_or_none()
        ca_weight = int(weights.ca_total_weight) if weights else 50
        exam_weight = int(weights.exam_total_weight) if weights else 50

        # Get grading scale
        grading_scale_result = await db.execute(
            select(GradingScale).where(
                and_(
                    GradingScale.tenant_id == tenant_id,
                    GradingScale.is_default == True,
                )
            )
        )
        grading_scale = grading_scale_result.scalar_one_or_none()

        grades = []
        if grading_scale:
            grades_result = await db.execute(
                select(Grade)
                .where(Grade.grading_scale_id == grading_scale.id)
                .order_by(Grade.min_score.desc())
            )
            grades = grades_result.scalars().all()

        # Get subject results using TermReportService
        term_report_service = TermReportService(db)
        subject_results = await term_report_service.get_student_subject_results(
            tenant_id=tenant_id,
            term_id=report.term_id,
            student_id=report.student_id,
            class_id=report.class_id,
            academic_year_id=report.academic_year_id,
            section_id=report.section_id,
        )

        # Resolve curriculum profile for this class (if multi-curriculum is active)
        curriculum_profile = None
        report_config = None
        components = []
        if report.class_ and hasattr(report.class_, "curriculum_profile_id") and report.class_.curriculum_profile_id:
            from app.models.curriculum import CurriculumProfile, ReportCardConfig, AssessmentStructure
            from sqlalchemy.orm import selectinload as _sel

            profile_result = await db.execute(
                select(CurriculumProfile).where(
                    and_(
                        CurriculumProfile.id == report.class_.curriculum_profile_id,
                        CurriculumProfile.tenant_id == tenant_id,
                        CurriculumProfile.deleted_at.is_(None),
                    )
                )
            )
            curriculum_profile = profile_result.scalar_one_or_none()

            # Fetch report card display config for the profile
            if curriculum_profile:
                rc_result = await db.execute(
                    select(ReportCardConfig).where(
                        and_(
                            ReportCardConfig.curriculum_profile_id == curriculum_profile.id,
                            ReportCardConfig.tenant_id == tenant_id,
                            ReportCardConfig.deleted_at.is_(None),
                        )
                    )
                )
                report_config = rc_result.scalar_one_or_none()

                # Fetch assessment structure components for column rendering
                from app.models.curriculum import AssessmentComponent
                struct_result = await db.execute(
                    select(AssessmentStructure).where(
                        and_(
                            AssessmentStructure.curriculum_profile_id == curriculum_profile.id,
                            AssessmentStructure.tenant_id == tenant_id,
                            AssessmentStructure.is_active == True,
                            AssessmentStructure.deleted_at.is_(None),
                        )
                    )
                )
                structure = struct_result.scalar_one_or_none()
                if structure:
                    comp_result = await db.execute(
                        select(AssessmentComponent)
                        .where(AssessmentComponent.assessment_structure_id == structure.id)
                        .order_by(AssessmentComponent.sequence)
                    )
                    components = comp_result.scalars().all()

        # Select the correct template based on curriculum type
        template_name = cls.get_report_template(curriculum_profile)

        # Prepare template context
        context = {
            "report": report,
            "student": student,
            "school": school or {},
            "academic_year": report.academic_year or {},
            "term": report.term or {},
            "class_name": report.class_.name if report.class_ else "",
            "section_name": section_name,
            "subject_results": subject_results,
            "ca_weight": ca_weight,
            "exam_weight": exam_weight,
            "grading_scale": grading_scale,
            "grades": grades,
            "next_term_begins": None,  # Can be added later if needed
            "current_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            # Curriculum-specific context (unused by GES template, consumed by others)
            "report_config": report_config,
            "components": components,
            "curriculum_profile": curriculum_profile,
            # Curriculum-specific values — populated by the calling service when available.
            # Templates degrade gracefully when these are absent (show dashes).
            "term_gpa": None,
            "cumulative_gpa": None,
            "total_credits_attempted": None,
            "total_credits_earned": None,
            "honor_roll": None,
            "ib_total_points": None,
            "ib_bonus_points": None,
            "learner_profile_traits": None,
            "atl_skills": None,
            "mention": None,
            "weighted_average": None,
            "total_coefficients": None,
            "total_weighted_score": None,
            "class_averages": None,
            "developmental_areas": None,
            "work_samples": None,
            "goals": None,
        }

        # Render HTML template
        env = cls._get_jinja_env()
        template = env.get_template(template_name)
        html_content = template.render(**context)

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_bytes = pdf_buffer.getvalue()

        # Generate filename
        student_name = f"{student.first_name}_{student.last_name}".replace(" ", "_")
        term_name = report.term.name.replace(" ", "_") if report.term else "Term"
        filename = f"Report_Card_{student_name}_{term_name}.pdf"

        return pdf_bytes, filename

    @classmethod
    async def generate_invoice_pdf(
        cls,
        db: AsyncSession,
        tenant_id: UUID,
        invoice_id: UUID,
    ) -> tuple[bytes, str]:
        """
        Generate a PDF for an invoice.

        Returns tuple of (pdf_bytes, filename).
        """
        from sqlalchemy.orm import joinedload

        # Fetch the invoice with related data
        invoice_result = await db.execute(
            select(Invoice)
            .where(
                and_(
                    Invoice.id == invoice_id,
                    Invoice.tenant_id == tenant_id,
                    Invoice.deleted_at.is_(None),
                )
            )
            .options(
                joinedload(Invoice.student),
                joinedload(Invoice.academic_year),
                joinedload(Invoice.term),
                selectinload(Invoice.items),
                selectinload(Invoice.payments),
            )
        )
        invoice = invoice_result.scalar_one_or_none()

        if not invoice:
            raise ValueError("Invoice not found")

        student = invoice.student
        if not student:
            raise ValueError("Student not found")

        # Fetch school
        school_result = await db.execute(
            select(School).where(School.tenant_id == tenant_id)
        )
        school = school_result.scalar_one_or_none()

        # Get class name if student has enrollment
        class_name = None
        section_name = None
        if student.class_id:
            class_result = await db.execute(
                select(Class).where(Class.id == student.class_id)
            )
            student_class = class_result.scalar_one_or_none()
            if student_class:
                class_name = student_class.name

        if student.section_id:
            section_result = await db.execute(
                select(ClassSection).where(ClassSection.id == student.section_id)
            )
            section = section_result.scalar_one_or_none()
            if section:
                section_name = section.name

        # Calculate balance
        balance = invoice.total_amount - invoice.amount_paid

        # Filter non-voided payments
        payments = [p for p in invoice.payments if not p.is_voided]

        # Prepare template context
        context = {
            "invoice": invoice,
            "student": student,
            "school": school or {},
            "academic_year": invoice.academic_year or {},
            "term": invoice.term or {},
            "class_name": class_name,
            "section_name": section_name,
            "items": invoice.items,
            "payments": payments,
            "currency": invoice.currency or "GHS",
            "balance": balance,
            "current_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

        # Render HTML template
        env = cls._get_jinja_env()
        template = env.get_template("invoice.html")
        html_content = template.render(**context)

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_bytes = pdf_buffer.getvalue()

        # Generate filename
        student_name = f"{student.first_name}_{student.last_name}".replace(" ", "_")
        filename = f"Invoice_{invoice.invoice_number}_{student_name}.pdf"

        return pdf_bytes, filename
