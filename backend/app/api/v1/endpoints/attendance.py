"""
SIMS Plus - Attendance Endpoints

API endpoints for student and staff attendance management.
"""

from datetime import date, datetime
from io import BytesIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.attendance import (
    StudentAttendanceMark,
    BulkStudentAttendanceMark,
    StudentAttendanceResponse,
    StudentAttendanceListItem,
    StudentAttendanceSummary,
    SectionAttendanceSummary,
    DailyAttendanceReport,
    BulkAttendanceResult,
    StaffAttendanceMark,
    BulkStaffAttendanceMark,
    StaffAttendanceResponse,
    StaffAttendanceSummary,
)
from app.schemas.reports import AttendanceReportRequest
from app.services.attendance import AttendanceService

import structlog

logger = structlog.get_logger()

router = APIRouter()


# =========================
# Student Attendance Endpoints
# =========================


@router.post(
    "/students",
    response_model=StudentAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark student attendance",
    dependencies=[Depends(require_permissions("attendance.mark"))],
)
async def mark_student_attendance(
    data: StudentAttendanceMark,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentAttendanceResponse:
    """Mark or update attendance for a single student."""
    service = AttendanceService(db)

    attendance = await service.mark_student_attendance(
        tenant_id=tenant.tenant_id,
        student_id=data.student_id,
        section_id=data.section_id,
        attendance_date=data.date,
        status=data.status,
        term_id=data.term_id,
        check_in_time=data.check_in_time,
        check_out_time=data.check_out_time,
        remarks=data.remarks,
        excuse_reason=data.excuse_reason,
        marked_by=UUID(user["user_id"]),
    )

    return StudentAttendanceResponse(
        id=attendance.id,
        student_id=attendance.student_id,
        section_id=attendance.section_id,
        date=attendance.date,
        status=attendance.status.value,
        term_id=attendance.term_id,
        check_in_time=attendance.check_in_time,
        check_out_time=attendance.check_out_time,
        remarks=attendance.remarks,
        excuse_reason=attendance.excuse_reason,
        marked_by=attendance.marked_by,
        created_at=attendance.created_at,
        updated_at=attendance.updated_at,
        student_name=f"{attendance.student.first_name} {attendance.student.last_name}" if attendance.student else None,
        student_number=attendance.student.student_id if attendance.student else None,
        section_name=attendance.section.name if attendance.section else None,
    )


@router.post(
    "/students/bulk",
    response_model=BulkAttendanceResult,
    summary="Bulk mark student attendance",
    dependencies=[Depends(require_permissions("attendance.mark"))],
)
async def bulk_mark_student_attendance(
    data: BulkStudentAttendanceMark,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkAttendanceResult:
    """Bulk mark attendance for multiple students in a section."""
    service = AttendanceService(db)

    result = await service.bulk_mark_student_attendance(
        tenant_id=tenant.tenant_id,
        section_id=data.section_id,
        attendance_date=data.date,
        attendance_records=[
            {
                "student_id": str(r.student_id),
                "status": r.status,
                "check_in_time": r.check_in_time,
                "remarks": r.remarks,
                "excuse_reason": r.excuse_reason,
            }
            for r in data.records
        ],
        term_id=data.term_id,
        marked_by=UUID(user["user_id"]),
    )

    return BulkAttendanceResult(**result)


@router.get(
    "/students/section/{section_id}",
    response_model=list[StudentAttendanceListItem],
    summary="Get students for attendance marking",
    dependencies=[Depends(require_permissions("attendance.read"))],
)
async def get_students_for_attendance(
    section_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    attendance_date: date = Query(..., description="Date to get attendance for"),
) -> list[StudentAttendanceListItem]:
    """Get all students in a section with their attendance status for a date."""
    service = AttendanceService(db)

    students = await service.get_students_for_attendance(
        tenant_id=tenant.tenant_id,
        section_id=section_id,
        attendance_date=attendance_date,
    )

    return [StudentAttendanceListItem(**s) for s in students]


@router.get(
    "/students/section/{section_id}/summary",
    response_model=SectionAttendanceSummary,
    summary="Get section attendance summary",
    dependencies=[Depends(require_permissions("attendance.read"))],
)
async def get_section_attendance_summary(
    section_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    attendance_date: date = Query(..., description="Date to get summary for"),
) -> SectionAttendanceSummary:
    """Get attendance summary for a section on a specific date."""
    service = AttendanceService(db)

    summary = await service.get_section_attendance_summary(
        tenant_id=tenant.tenant_id,
        section_id=section_id,
        attendance_date=attendance_date,
    )

    return SectionAttendanceSummary(**summary)


@router.get(
    "/students/{student_id}/summary",
    response_model=StudentAttendanceSummary,
    summary="Get student attendance summary",
    dependencies=[Depends(require_permissions("attendance.read"))],
)
async def get_student_attendance_summary(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: Optional[UUID] = Query(None, description="Filter by term"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
) -> StudentAttendanceSummary:
    """Get attendance summary for a specific student."""
    service = AttendanceService(db)

    summary = await service.get_student_attendance_summary(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        term_id=term_id,
        start_date=start_date,
        end_date=end_date,
    )

    return StudentAttendanceSummary(**summary)


@router.get(
    "/students",
    response_model=dict,
    summary="List student attendance",
    dependencies=[Depends(require_permissions("attendance.read"))],
)
async def list_student_attendance(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    student_id: Optional[UUID] = Query(None, description="Filter by student"),
    section_id: Optional[UUID] = Query(None, description="Filter by section"),
    term_id: Optional[UUID] = Query(None, description="Filter by term"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> dict:
    """List student attendance records with filters."""
    service = AttendanceService(db)

    records, total = await service.list_student_attendance(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        section_id=section_id,
        term_id=term_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": [
            StudentAttendanceResponse(
                id=r.id,
                student_id=r.student_id,
                section_id=r.section_id,
                date=r.date,
                status=r.status.value,
                term_id=r.term_id,
                check_in_time=r.check_in_time,
                check_out_time=r.check_out_time,
                remarks=r.remarks,
                excuse_reason=r.excuse_reason,
                marked_by=r.marked_by,
                created_at=r.created_at,
                updated_at=r.updated_at,
                student_name=f"{r.student.first_name} {r.student.last_name}" if r.student else None,
                student_number=r.student.student_id if r.student else None,
                section_name=r.section.name if r.section else None,
            )
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.delete(
    "/students/{attendance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete student attendance",
    dependencies=[Depends(require_permissions("attendance.delete"))],
)
async def delete_student_attendance(
    attendance_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Delete a student attendance record."""
    service = AttendanceService(db)

    deleted = await service.delete_student_attendance(
        tenant_id=tenant.tenant_id,
        attendance_id=attendance_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found",
        )


# =========================
# Daily Reports
# =========================


@router.get(
    "/reports/daily",
    response_model=DailyAttendanceReport,
    summary="Get daily attendance report",
    dependencies=[Depends(require_permissions("attendance.read"))],
)
async def get_daily_attendance_report(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    attendance_date: date = Query(..., description="Date for report"),
    school_id: Optional[UUID] = Query(None, description="Filter by school"),
) -> DailyAttendanceReport:
    """Get school-wide attendance report for a date."""
    service = AttendanceService(db)

    report = await service.get_daily_attendance_report(
        tenant_id=tenant.tenant_id,
        attendance_date=attendance_date,
        school_id=school_id,
    )

    return DailyAttendanceReport(**report)


# =========================
# Attendance Report PDF
# =========================


@router.post(
    "/reports/pdf",
    summary="Generate attendance report PDF",
    dependencies=[Depends(require_permissions("attendance.reports"))],
    responses={200: {"content": {"application/pdf": {}}}},
)
async def generate_attendance_report_pdf(
    request: AttendanceReportRequest,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StreamingResponse:
    """
    Generate an attendance report as a downloadable PDF.

    Covers a date range for a specific class and optional section.
    Requires `attendance.reports` permission.

    NOTE: Depends on AttendanceService.get_attendance_report_data() which
    aggregates per-student attendance stats over the requested date range.
    If that method is not yet available, this endpoint will return 501.
    """
    from weasyprint import HTML

    service = AttendanceService(db)

    # Validate date range
    if request.date_from > request.date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be before or equal to date_to",
        )

    # Check if the service method exists; graceful fallback if not yet implemented
    if not hasattr(service, "get_attendance_report_data"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Attendance report data aggregation is not yet implemented",
        )

    report_data = await service.get_attendance_report_data(
        tenant_id=tenant.tenant_id,
        class_id=request.class_id,
        section_id=request.section_id,
        date_from=request.date_from,
        date_to=request.date_to,
    )

    # Build PDF from report data
    students = report_data.get("students", [])

    header_html = (
        "<th>Student ID</th><th>Name</th><th>Present</th>"
        "<th>Absent</th><th>Late</th><th>Excused</th><th>Rate</th>"
    )
    rows_html = ""
    for s in students:
        rows_html += (
            f"<tr>"
            f"<td>{s.get('student_number', 'N/A')}</td>"
            f"<td>{s.get('name', '')}</td>"
            f"<td>{s.get('present', 0)}</td>"
            f"<td>{s.get('absent', 0)}</td>"
            f"<td>{s.get('late', 0)}</td>"
            f"<td>{s.get('excused', 0)}</td>"
            f"<td>{s.get('attendance_rate', 0):.1f}%</td>"
            f"</tr>"
        )

    summary_data = report_data.get("summary", {})
    summary_html = ""
    if summary_data:
        for key, value in summary_data.items():
            label = key.replace("_", " ").title()
            summary_html += f"<p><strong>{label}:</strong> {value}</p>"

    date_range = f"{request.date_from.strftime('%d/%m/%Y')} - {request.date_to.strftime('%d/%m/%Y')}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            h1 {{ color: #1B4F72; border-bottom: 2px solid #1B4F72; padding-bottom: 10px; }}
            h2 {{ color: #555; font-size: 14px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background-color: #1B4F72; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; }}
            tr:nth-child(even) {{ background-color: #f9fafb; }}
            .summary {{ background-color: #f0f4f8; padding: 15px; border-radius: 8px; margin-top: 20px; }}
            .generated {{ color: #666; font-size: 12px; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <h1>Attendance Report</h1>
        <h2>Period: {date_range}</h2>
        <table>
            <thead><tr>{header_html}</tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <div class="summary">{summary_html}</div>
        <p class="generated">Generated by SIMS Plus on {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
    </body>
    </html>
    """

    pdf_bytes = HTML(string=html_content).write_pdf()

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=attendance-report.pdf",
        },
    )


# =========================
# Staff Attendance Endpoints
# =========================


@router.post(
    "/staff",
    response_model=StaffAttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark staff attendance",
    dependencies=[Depends(require_permissions("attendance.mark"))],
)
async def mark_staff_attendance(
    data: StaffAttendanceMark,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StaffAttendanceResponse:
    """Mark or update attendance for a staff member."""
    service = AttendanceService(db)

    attendance = await service.mark_staff_attendance(
        tenant_id=tenant.tenant_id,
        staff_id=data.staff_id,
        attendance_date=data.date,
        status=data.status,
        term_id=data.term_id,
        check_in_time=data.check_in_time,
        check_out_time=data.check_out_time,
        remarks=data.remarks,
        excuse_reason=data.excuse_reason,
        marked_by=UUID(user["user_id"]),
    )

    return StaffAttendanceResponse(
        id=attendance.id,
        staff_id=attendance.staff_id,
        date=attendance.date,
        status=attendance.status.value,
        term_id=attendance.term_id,
        check_in_time=attendance.check_in_time,
        check_out_time=attendance.check_out_time,
        remarks=attendance.remarks,
        excuse_reason=attendance.excuse_reason,
        marked_by=attendance.marked_by,
        created_at=attendance.created_at,
        updated_at=attendance.updated_at,
        staff_name=f"{attendance.staff.first_name} {attendance.staff.last_name}" if attendance.staff else None,
        staff_number=attendance.staff.staff_id if attendance.staff else None,
    )


@router.post(
    "/staff/bulk",
    response_model=BulkAttendanceResult,
    summary="Bulk mark staff attendance",
    dependencies=[Depends(require_permissions("attendance.mark"))],
)
async def bulk_mark_staff_attendance(
    data: BulkStaffAttendanceMark,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkAttendanceResult:
    """Bulk mark attendance for multiple staff members."""
    service = AttendanceService(db)

    result = await service.bulk_mark_staff_attendance(
        tenant_id=tenant.tenant_id,
        attendance_date=data.date,
        attendance_records=[
            {
                "staff_id": str(r.staff_id),
                "status": r.status,
                "check_in_time": r.check_in_time,
                "check_out_time": r.check_out_time,
                "remarks": r.remarks,
                "excuse_reason": r.excuse_reason,
            }
            for r in data.records
        ],
        term_id=data.term_id,
        marked_by=UUID(user["user_id"]),
    )

    return BulkAttendanceResult(**result)


@router.get(
    "/staff/{staff_id}/summary",
    response_model=StaffAttendanceSummary,
    summary="Get staff attendance summary",
    dependencies=[Depends(require_permissions("attendance.read"))],
)
async def get_staff_attendance_summary(
    staff_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: Optional[UUID] = Query(None, description="Filter by term"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
) -> StaffAttendanceSummary:
    """Get attendance summary for a specific staff member."""
    service = AttendanceService(db)

    summary = await service.get_staff_attendance_summary(
        tenant_id=tenant.tenant_id,
        staff_id=staff_id,
        term_id=term_id,
        start_date=start_date,
        end_date=end_date,
    )

    return StaffAttendanceSummary(**summary)


@router.get(
    "/staff",
    response_model=dict,
    summary="List staff attendance",
    dependencies=[Depends(require_permissions("attendance.read"))],
)
async def list_staff_attendance(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    staff_id: Optional[UUID] = Query(None, description="Filter by staff"),
    term_id: Optional[UUID] = Query(None, description="Filter by term"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> dict:
    """List staff attendance records with filters."""
    service = AttendanceService(db)

    records, total = await service.list_staff_attendance(
        tenant_id=tenant.tenant_id,
        staff_id=staff_id,
        term_id=term_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": [
            StaffAttendanceResponse(
                id=r.id,
                staff_id=r.staff_id,
                date=r.date,
                status=r.status.value,
                term_id=r.term_id,
                check_in_time=r.check_in_time,
                check_out_time=r.check_out_time,
                remarks=r.remarks,
                excuse_reason=r.excuse_reason,
                marked_by=r.marked_by,
                created_at=r.created_at,
                updated_at=r.updated_at,
                staff_name=f"{r.staff.first_name} {r.staff.last_name}" if r.staff else None,
                staff_number=r.staff.staff_id if r.staff else None,
            )
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.delete(
    "/staff/{attendance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete staff attendance",
    dependencies=[Depends(require_permissions("attendance.delete"))],
)
async def delete_staff_attendance(
    attendance_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Delete a staff attendance record."""
    service = AttendanceService(db)

    deleted = await service.delete_staff_attendance(
        tenant_id=tenant.tenant_id,
        attendance_id=attendance_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found",
        )
