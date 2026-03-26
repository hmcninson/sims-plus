"""
SIMS Plus - Preschool Report Endpoints

API routes for preschool reports.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.services.pdf import PDFService
from app.schemas.preschool import (
    PreschoolReportCreate,
    PreschoolReportUpdate,
    PreschoolReportResponse,
    PreschoolReportGenerateRequest,
    PreschoolReportPublishRequest,
    convert_uuid,
)

router = APIRouter()


# =========================
# Preschool Reports
# =========================


@router.get(
    "/reports",
    response_model=list[PreschoolReportResponse],
    summary="List reports",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_reports(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    term_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
    is_published: bool | None = Query(None),
):
    """List preschool reports with filters."""
    service = PreschoolService(db)
    return await service.list_reports(
        convert_uuid(tenant.tenant_id), student_id, term_id, class_id, is_published
    )


@router.post(
    "/reports",
    response_model=PreschoolReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create report",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_report(
    data: PreschoolReportCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a preschool report."""
    service = PreschoolService(db)
    try:
        return await service.create_report(convert_uuid(tenant.tenant_id), data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/reports/{report_id}",
    response_model=PreschoolReportResponse,
    summary="Get report",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_report(
    report_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a report by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_report(convert_uuid(tenant.tenant_id), report_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/reports/{report_id}",
    response_model=PreschoolReportResponse,
    summary="Update report",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_report(
    report_id: UUID,
    data: PreschoolReportUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update a report."""
    service = PreschoolService(db)
    try:
        report = await service.get_report(convert_uuid(tenant.tenant_id), report_id)
        return await service.update_report(report, data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/reports/generate",
    summary="Generate reports",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def generate_reports(
    data: PreschoolReportGenerateRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Generate reports for all students in a class for a given term."""
    service = PreschoolService(db)
    try:
        result = await service.generate_reports(
            convert_uuid(tenant.tenant_id),
            data.class_id,
            data.academic_year_id,
            data.term_id,
            report_type=data.report_type,
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return result


@router.post(
    "/reports/publish",
    response_model=list[PreschoolReportResponse],
    summary="Publish reports",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def publish_reports(
    data: PreschoolReportPublishRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Publish multiple reports."""
    service = PreschoolService(db)
    try:
        return await service.publish_reports(convert_uuid(tenant.tenant_id), data.report_ids)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/reports/{report_id}/pdf",
    summary="Download report PDF",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def download_report_pdf(
    report_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Download a preschool report as PDF. Only published reports can be downloaded."""
    try:
        pdf_bytes, filename = await PDFService.generate_preschool_report_pdf(
            db,
            convert_uuid(tenant.tenant_id),
            report_id,
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
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
