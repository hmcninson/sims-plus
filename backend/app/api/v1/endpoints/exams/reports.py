"""
SIMS Plus - Term Report Endpoints
"""

from typing import Optional
from uuid import UUID
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.exam import (
    MontessoriAssessmentCreate,
    MontessoriAssessmentResponse,
    SubjectResult,
    TermReportGenerate,
    TermReportRemarksUpdate,
    TermReportResponse,
    TermReportWithDetailsResponse,
    TermReportListResponse,
)
from app.services.curriculum._shared import CurriculumServiceError
from app.services.exam import TermReportService

router = APIRouter()


# =========================
# Term Report Endpoints
# =========================


@router.post(
    "/reports/term/generate",
    response_model=list[TermReportResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate term reports",
    dependencies=[Depends(require_permissions("reports.generate"))],
)
async def generate_term_reports(
    data: TermReportGenerate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[TermReportResponse]:
    """Generate term reports for a class."""
    # Get academic year from term
    from app.services.academic import AcademicService
    academic_service = AcademicService(db)
    term = await academic_service.get_term(tenant.tenant_id, data.term_id)
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = TermReportService(db)
    reports = await service.generate_term_reports(
        tenant_id=tenant.tenant_id,
        academic_year_id=term.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        section_id=data.section_id,
        generated_by=current_user.get("user_id"),
    )

    # Calculate rankings after generating reports
    await service.calculate_rankings(
        tenant_id=tenant.tenant_id,
        term_id=data.term_id,
        class_id=data.class_id,
    )

    # Refresh reports to get updated rankings
    refreshed_reports = []
    for r in reports:
        await db.refresh(r)
        refreshed_reports.append(r)

    return [
        TermReportResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            academic_year_id=r.academic_year_id,
            term_id=r.term_id,
            student_id=r.student_id,
            class_id=r.class_id,
            section_id=r.section_id,
            total_score=r.total_score,
            average_score=r.average_score,
            subjects_count=r.subjects_count,
            class_position=r.class_position,
            section_position=r.section_position,
            class_size=r.class_size,
            section_size=r.section_size,
            attendance_percentage=r.attendance_percentage,
            days_present=r.days_present,
            days_absent=r.days_absent,
            total_school_days=r.total_school_days,
            conduct_grade=r.conduct_grade,
            interest=r.interest,
            class_teacher_remark=r.class_teacher_remark,
            headmaster_remark=r.headmaster_remark,
            is_published=r.is_published,
            published_at=r.published_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in refreshed_reports
    ]


@router.get(
    "/reports/term",
    response_model=TermReportListResponse,
    summary="List term reports",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def list_term_reports(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: Optional[UUID] = Query(None),
    class_id: Optional[UUID] = Query(None),
    section_id: Optional[UUID] = Query(None),
    is_published: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> TermReportListResponse:
    """List term reports with filters."""
    service = TermReportService(db)
    reports, total = await service.list_term_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        is_published=is_published,
        page=page,
        page_size=page_size,
    )

    items = []
    for r in reports:
        items.append(TermReportWithDetailsResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            academic_year_id=r.academic_year_id,
            term_id=r.term_id,
            student_id=r.student_id,
            class_id=r.class_id,
            section_id=r.section_id,
            total_score=r.total_score,
            average_score=r.average_score,
            subjects_count=r.subjects_count,
            class_position=r.class_position,
            section_position=r.section_position,
            class_size=r.class_size,
            section_size=r.section_size,
            attendance_percentage=r.attendance_percentage,
            days_present=r.days_present,
            days_absent=r.days_absent,
            total_school_days=r.total_school_days,
            conduct_grade=r.conduct_grade,
            interest=r.interest,
            class_teacher_remark=r.class_teacher_remark,
            headmaster_remark=r.headmaster_remark,
            is_published=r.is_published,
            published_at=r.published_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
            student_name=f"{r.student.first_name} {r.student.last_name}" if r.student else "",
            student_id_number=r.student.student_id if r.student else "",
            class_name=r.class_.name if r.class_ else "",
            section_name=r.section.name if r.section else None,
            term_name=r.term.name if r.term else "",
            academic_year_name=r.academic_year.name if hasattr(r, "academic_year") and r.academic_year else "",
        ))

    return TermReportListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/reports/term/export",
    summary="Export term reports to CSV",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def export_term_reports_csv(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: Optional[UUID] = Query(None),
    section_id: Optional[UUID] = Query(None),
):
    """Export term reports for a class as CSV."""
    import csv
    from io import StringIO
    from fastapi.responses import Response

    service = TermReportService(db)
    reports, total = await service.list_term_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        page=1,
        page_size=1000,  # Get all
    )

    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found for the specified criteria",
        )

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Write header row
    headers = [
        "Rank", "Student ID", "Student Name", "Class", "Section",
        "Total Score", "Average (%)", "Subjects",
        "Days Present", "Days Absent", "Attendance (%)",
        "Conduct", "Class Teacher Remark", "Published"
    ]
    writer.writerow(headers)

    # Write data rows
    for report in reports:
        row = [
            report.class_position or "",
            report.student.student_id if report.student else "",
            f"{report.student.first_name} {report.student.last_name}" if report.student else "",
            report.class_.name if report.class_ else "",
            report.section.name if report.section else "",
            report.total_score or "",
            report.average_score or "",
            report.subjects_count or "",
            report.days_present or 0,
            report.days_absent or 0,
            report.attendance_percentage or "",
            report.conduct_grade or "",
            report.class_teacher_remark or "",
            "Yes" if report.is_published else "No",
        ]
        writer.writerow(row)

    # Create response
    csv_content = output.getvalue()
    term_name = reports[0].term.name if reports and reports[0].term else "Term"
    class_name = reports[0].class_.name if reports and reports[0].class_ else "Class"
    filename = f"Report_Cards_{class_name}_{term_name}.csv"
    filename = filename.replace(" ", "_")

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/reports/term/batch-pdf",
    summary="Download multiple term reports as ZIP",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def download_batch_term_reports_pdf(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: Optional[UUID] = Query(None),
    section_id: Optional[UUID] = Query(None),
):
    """Download multiple term reports as a ZIP file containing individual PDFs."""
    from fastapi.responses import Response
    from app.services.pdf import PDFService
    import zipfile
    from io import BytesIO

    service = TermReportService(db)
    reports, total = await service.list_term_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        page=1,
        page_size=500,  # Limit for safety
    )

    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found for the specified criteria",
        )

    # Create ZIP file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for report in reports:
            try:
                pdf_bytes, filename = await PDFService.generate_term_report_pdf(
                    db=db,
                    tenant_id=tenant.tenant_id,
                    report_id=report.id,
                )
                zip_file.writestr(filename, pdf_bytes)
            except Exception as e:
                # Skip failed PDFs but continue with others
                continue

    zip_buffer.seek(0)
    zip_content = zip_buffer.getvalue()

    # Create filename
    term_name = reports[0].term.name if reports and reports[0].term else "Term"
    class_name = reports[0].class_.name if reports and reports[0].class_ else "Class"
    zip_filename = f"Report_Cards_{class_name}_{term_name}.zip"
    zip_filename = zip_filename.replace(" ", "_")

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )


@router.get(
    "/reports/term/{report_id}",
    response_model=TermReportWithDetailsResponse,
    summary="Get term report",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def get_term_report(
    report_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> TermReportWithDetailsResponse:
    """Get term report by ID."""
    service = TermReportService(db)
    report = await service.get_term_report(tenant.tenant_id, report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Get subject results for this student's term report
    subject_results = await service.get_student_subject_results(
        tenant_id=tenant.tenant_id,
        term_id=report.term_id,
        student_id=report.student_id,
        class_id=report.class_id,
        academic_year_id=report.academic_year_id,
        section_id=report.section_id,
    )

    return TermReportWithDetailsResponse(
        id=report.id,
        tenant_id=report.tenant_id,
        academic_year_id=report.academic_year_id,
        term_id=report.term_id,
        student_id=report.student_id,
        class_id=report.class_id,
        section_id=report.section_id,
        total_score=report.total_score,
        average_score=report.average_score,
        subjects_count=report.subjects_count,
        class_position=report.class_position,
        section_position=report.section_position,
        class_size=report.class_size,
        section_size=report.section_size,
        attendance_percentage=report.attendance_percentage,
        days_present=report.days_present,
        days_absent=report.days_absent,
        total_school_days=report.total_school_days,
        conduct_grade=report.conduct_grade,
        interest=report.interest,
        class_teacher_remark=report.class_teacher_remark,
        headmaster_remark=report.headmaster_remark,
        is_published=report.is_published,
        published_at=report.published_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        student_name=f"{report.student.first_name} {report.student.last_name}" if report.student else "",
        student_id_number=report.student.student_id if report.student else "",
        class_name=report.class_.name if report.class_ else "",
        section_name=report.section.name if report.section else None,
        term_name=report.term.name if report.term else "",
        academic_year_name=report.academic_year.name if report.academic_year else "",
        subject_results=[
            SubjectResult(
                subject_id=s["subject_id"],
                subject_name=s["subject_name"],
                subject_code=s.get("subject_code"),
                # Raw scores
                ca_score=s.get("ca_score"),
                ca_max=s.get("ca_max"),
                end_term_score=s.get("end_term_score"),
                end_term_max=s.get("end_term_max"),
                # Normalized scores (Ghana 50/50 system)
                class_score=s.get("class_score"),
                exams_score=s.get("exams_score"),
                total_score=s.get("total_score"),
                grade=s.get("grade"),
                grade_remark=s.get("grade_remark"),
                subject_position=s.get("subject_position"),
            )
            for s in subject_results
        ],
    )


@router.get(
    "/reports/term/{report_id}/pdf",
    summary="Download term report PDF",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def download_term_report_pdf(
    report_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Download term report as PDF."""
    from fastapi.responses import Response
    from app.services.pdf import PDFService

    try:
        pdf_bytes, filename = await PDFService.generate_term_report_pdf(
            db=db,
            tenant_id=tenant.tenant_id,
            report_id=report_id,
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF",
        )


@router.put(
    "/reports/term/{report_id}/remarks",
    response_model=TermReportResponse,
    summary="Update report remarks",
    dependencies=[Depends(require_permissions("reports.remarks.update"))],
)
async def update_report_remarks(
    report_id: UUID,
    data: TermReportRemarksUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> TermReportResponse:
    """Update term report remarks."""
    service = TermReportService(db)
    report = await service.update_remarks(
        report_id=report_id,
        tenant_id=tenant.tenant_id,
        conduct_grade=data.conduct_grade,
        interest=data.interest,
        class_teacher_remark=data.class_teacher_remark,
        headmaster_remark=data.headmaster_remark,
    )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return TermReportResponse(
        id=report.id,
        tenant_id=report.tenant_id,
        academic_year_id=report.academic_year_id,
        term_id=report.term_id,
        student_id=report.student_id,
        class_id=report.class_id,
        section_id=report.section_id,
        total_score=report.total_score,
        average_score=report.average_score,
        subjects_count=report.subjects_count,
        class_position=report.class_position,
        section_position=report.section_position,
        class_size=report.class_size,
        section_size=report.section_size,
        attendance_percentage=report.attendance_percentage,
        days_present=report.days_present,
        days_absent=report.days_absent,
        total_school_days=report.total_school_days,
        conduct_grade=report.conduct_grade,
        interest=report.interest,
        class_teacher_remark=report.class_teacher_remark,
        headmaster_remark=report.headmaster_remark,
        is_published=report.is_published,
        published_at=report.published_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "/reports/term/publish",
    summary="Publish term reports",
    dependencies=[Depends(require_permissions("reports.publish"))],
)
async def publish_term_reports(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: Optional[UUID] = Query(None),
) -> dict:
    """Publish term reports (make visible to parents)."""
    service = TermReportService(db)
    count = await service.publish_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
    )

    return {"published": count, "message": f"Published {count} reports"}


# =========================
# Montessori Narrative Assessment Endpoints
# =========================


@router.post(
    "/reports/montessori-assessment/{academic_year_id}/{term_id}",
    response_model=MontessoriAssessmentResponse,
    summary="Save Montessori narrative assessment",
    dependencies=[Depends(require_permissions("exams.scores"))],
)
async def save_montessori_assessment(
    academic_year_id: UUID,
    term_id: UUID,
    data: MontessoriAssessmentCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    class_id: UUID = Query(..., description="Class ID for the student"),
    section_id: Optional[UUID] = Query(None, description="Section ID (optional)"),
):
    """Save or update a Montessori narrative assessment for a student.

    Montessori schools use qualitative, narrative-based assessment instead of
    numeric scores. This endpoint stores developmental area observations,
    work samples, goals, and general narrative in the TermReport JSONB.
    """
    service = TermReportService(db)
    try:
        report = await service.save_montessori_assessment(
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            class_id=class_id,
            section_id=section_id,
            data=data,
        )
    except CurriculumServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Build response from the saved TermReport.extra_data
    extra = report.extra_data or {}
    student_name = ""
    if report.student_id:
        from app.models.student import Student
        from sqlalchemy import select as sa_select

        student_result = await db.execute(
            sa_select(Student).where(Student.id == report.student_id)
        )
        student = student_result.scalar_one_or_none()
        if student:
            student_name = f"{student.first_name} {student.last_name}"

    return MontessoriAssessmentResponse(
        student_id=report.student_id,
        student_name=student_name,
        developmental_areas=extra.get("developmental_areas", []),
        work_samples=extra.get("work_samples", []),
        goals=extra.get("goals", []),
        general_narrative=extra.get("general_narrative", ""),
        updated_at=report.updated_at,
    )


@router.get(
    "/reports/montessori-assessment/{academic_year_id}/{term_id}/{student_id}",
    response_model=MontessoriAssessmentResponse,
    summary="Get Montessori narrative assessment",
    dependencies=[Depends(require_permissions("exams.scores"))],
)
async def get_montessori_assessment(
    academic_year_id: UUID,
    term_id: UUID,
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Get existing Montessori assessment for a student-term.

    Returns the narrative-based assessment data stored in TermReport.extra_data,
    or 404 if no Montessori assessment has been saved for this student-term.
    """
    service = TermReportService(db)
    report = await service.get_montessori_assessment(
        tenant_id=tenant.tenant_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        student_id=student_id,
    )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Montessori assessment found for this student-term",
        )

    extra = report.extra_data or {}
    student = report.student
    student_name = f"{student.first_name} {student.last_name}" if student else ""

    return MontessoriAssessmentResponse(
        student_id=report.student_id,
        student_name=student_name,
        developmental_areas=extra.get("developmental_areas", []),
        work_samples=extra.get("work_samples", []),
        goals=extra.get("goals", []),
        general_narrative=extra.get("general_narrative", ""),
        updated_at=report.updated_at,
    )
