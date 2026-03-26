"""
SIMS Plus - Admissions Portal Public Endpoints

Unauthenticated endpoints for the public application form.
Tenant resolved from subdomain via TenantMiddleware -> request.state.tenant_id.
Uses get_public_tenant_db() for tenant-scoped DB without JWT.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import PublicTenantSession
from app.models.academic import Class
from app.schemas.admissions import (
    ApplicationStatusCheckResponse,
    ApplicationSubmitRequest,
    ApplicationSubmitResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PublicFormConfigResponse,
    PublicPeriodListResponse,
    PublicPeriodResponse,
    PublicSchoolInfoResponse,
)
from app.services.admissions import (
    AdmissionPeriodError,
    AdmissionPeriodService,
    ApplicationPaymentError,
    ApplicationPaymentService,
    ApplicationService,
    ApplicationServiceError,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/public")


def _handle_app_error(e: ApplicationServiceError) -> HTTPException:
    """Map application service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "VALIDATION_ERROR": 422,
        "INVALID_STATUS_TRANSITION": 422,
        "MAX_DOCUMENTS": 409,
        "CAPTCHA_FAILED": 403,
        "ACCOUNT_REQUIRED": 403,
        "DAILY_CAP_EXCEEDED": 429,
        "PERIOD_FULL": 409,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


def _handle_period_error(e: AdmissionPeriodError) -> HTTPException:
    """Map period service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "VALIDATION_ERROR": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


def _handle_payment_error(e: ApplicationPaymentError) -> HTTPException:
    """Map payment service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "ALREADY_PAID": 409,
        "PROVIDER_UNAVAILABLE": 502,
        "INIT_FAILED": 502,
        "VALIDATION_ERROR": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.get(
    "/school-info",
    response_model=PublicSchoolInfoResponse,
    summary="Get school branding for application form",
)
async def get_school_info(
    request: Request,
    db: PublicTenantSession,
) -> PublicSchoolInfoResponse:
    """
    Returns school name, logo, colors, and contact info.
    Used by the public application form to render school branding.
    No authentication required -- tenant resolved from subdomain.
    """
    service = ApplicationService(db)
    try:
        result = await service.get_school_info(
            tenant_id=request.state.tenant_id,
        )
        return PublicSchoolInfoResponse(**result)
    except ApplicationServiceError as e:
        raise _handle_app_error(e)


@router.get(
    "/periods",
    response_model=PublicPeriodListResponse,
    summary="List open admission periods",
)
async def list_open_periods(
    request: Request,
    db: PublicTenantSession,
) -> PublicPeriodListResponse:
    """
    Returns all admission periods with status='open' for this school,
    including target class info (id, name, level) and fee details.
    """
    service = AdmissionPeriodService(db)
    try:
        periods = await service.get_open_periods(
            tenant_id=request.state.tenant_id,
        )

        # Get school info for the response
        app_service = ApplicationService(db)
        school_info = await app_service.get_school_info(
            tenant_id=request.state.tenant_id,
        )

        # Enrich target_classes from UUID strings to {id, name, level} dicts.
        # The AdmissionPeriod model stores target_classes as a JSONB array of
        # class UUID strings, but the public response schema expects enriched
        # dicts so the frontend can display class names to prospective parents.
        all_class_ids: set[str] = set()
        for period in periods:
            all_class_ids.update(period.target_classes or [])

        class_lookup: dict[str, dict] = {}
        if all_class_ids:
            class_uuids = [UUID(cid) for cid in all_class_ids]
            result = await db.execute(
                select(Class)
                .where(
                    Class.tenant_id == request.state.tenant_id,
                    Class.id.in_(class_uuids),
                    Class.deleted_at.is_(None),
                )
            )
            for cls in result.scalars().all():
                class_lookup[str(cls.id)] = {
                    "id": str(cls.id),
                    "name": cls.name,
                    "level": cls.level.value if cls.level else None,
                }

        enriched_periods = []
        for period in periods:
            enriched_classes = [
                class_lookup[cid]
                for cid in (period.target_classes or [])
                if cid in class_lookup
            ]
            enriched_periods.append(
                PublicPeriodResponse(
                    id=period.id,
                    name=period.name,
                    description=period.description,
                    start_date=period.start_date,
                    end_date=period.end_date,
                    application_fee_amount=period.application_fee_amount,
                    application_fee_required=period.application_fee_required,
                    entrance_exam_required=period.entrance_exam_required,
                    require_applicant_account=period.require_applicant_account,
                    target_classes=enriched_classes,
                )
            )

        return PublicPeriodListResponse(
            items=enriched_periods,
            school=PublicSchoolInfoResponse(**school_info),
        )
    except (AdmissionPeriodError, ApplicationServiceError) as e:
        raise HTTPException(
            status_code=404 if getattr(e, "code", "") == "NOT_FOUND" else 400,
            detail=e.message,
        )


@router.get(
    "/periods/{period_id}/form",
    response_model=PublicFormConfigResponse,
    summary="Get form configuration for a period",
)
async def get_period_form(
    period_id: UUID,
    request: Request,
    db: PublicTenantSession,
) -> PublicFormConfigResponse:
    """
    Returns the custom form schema, required documents, fee info,
    and target classes for a specific admission period.
    Used to render the multi-step application form.
    """
    service = AdmissionPeriodService(db)
    try:
        # Always fetch the period (needed for fee info and target classes)
        period = await service.get_period(
            tenant_id=request.state.tenant_id,
            period_id=period_id,
        )

        config = await service.get_form_config(
            tenant_id=request.state.tenant_id,
            period_id=period_id,
        )

        # Enrich target_classes from UUID strings to {id, name, level} dicts
        enriched_classes: list[dict] = []
        if period.target_classes:
            class_uuids = [UUID(cid) for cid in period.target_classes]
            result = await db.execute(
                select(Class)
                .where(
                    Class.tenant_id == request.state.tenant_id,
                    Class.id.in_(class_uuids),
                    Class.deleted_at.is_(None),
                )
            )
            class_lookup = {
                str(cls.id): {
                    "id": str(cls.id),
                    "name": cls.name,
                    "level": cls.level.value if cls.level else None,
                }
                for cls in result.scalars().all()
            }
            enriched_classes = [
                class_lookup[cid]
                for cid in period.target_classes
                if cid in class_lookup
            ]

        return PublicFormConfigResponse(
            admission_period_id=period.id,
            period_name=period.name,
            form_schema=config.form_schema if config else {},
            required_documents=config.required_documents if config else [],
            application_fee_amount=period.application_fee_amount,
            application_fee_required=period.application_fee_required,
            require_applicant_account=period.require_applicant_account,
            target_classes=enriched_classes,
        )
    except AdmissionPeriodError as e:
        raise _handle_period_error(e)


@router.post(
    "/applications",
    response_model=ApplicationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit application",
)
async def submit_application(
    data: ApplicationSubmitRequest,
    request: Request,
    db: PublicTenantSession,
) -> ApplicationSubmitResponse:
    """
    Submit a new application. Requires Cloudflare Turnstile token.

    Flow:
    1. Verify Turnstile token
    2. Validate admission period is open
    3. Validate target_class_id is in period's target_classes
    4. Validate custom_fields against form_schema (jsonschema)
    5. Check max_applications cap not exceeded
    6. Create application + guardians
    7. Log status history (NULL -> SUBMITTED or DRAFT -> SUBMITTED)
    8. Send confirmation SMS/email to primary guardian

    Returns tracking_code for status checking and document upload.
    If payment is required and fee_waived=false, status starts as DRAFT
    until payment is confirmed.
    """
    service = ApplicationService(db)

    # Resolve school_id from tenant (public forms have no school context header)
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(
            School.tenant_id == request.state.tenant_id,
            School.is_active.is_(True),
        ).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    try:
        # Unpack Pydantic model fields into individual kwargs
        application = await service.submit(
            tenant_id=request.state.tenant_id,
            school_id=school.id,
            turnstile_token=data.turnstile_token,
            admission_period_id=data.admission_period_id,
            applicant_first_name=data.applicant_first_name,
            applicant_last_name=data.applicant_last_name,
            applicant_other_names=data.applicant_other_names,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            nationality=data.nationality,
            target_class_id=data.target_class_id,
            custom_fields=data.custom_fields,
            previous_school=data.previous_school,
            medical_info=data.medical_info,
            guardians=[g.model_dump() for g in data.guardians],
            remote_ip=request.client.host if request.client else None,
        )

        # Determine if payment is required
        payment_required = application.status == "draft"

        # Get fee amount if payment required
        fee_amount = None
        if payment_required:
            period_service = AdmissionPeriodService(db)
            try:
                period = await period_service.get_period(
                    tenant_id=request.state.tenant_id,
                    period_id=data.admission_period_id,
                )
                fee_amount = period.application_fee_amount
            except AdmissionPeriodError:
                pass

        return ApplicationSubmitResponse(
            tracking_code=application.tracking_code,
            application_id=application.id,
            status=application.status,
            message="Application submitted successfully",
            payment_required=payment_required,
            application_fee_amount=fee_amount,
        )
    except ApplicationServiceError as e:
        raise _handle_app_error(e)


@router.get(
    "/applications/{tracking_code}/status",
    response_model=ApplicationStatusCheckResponse,
    summary="Check application status",
)
async def check_application_status(
    tracking_code: str,
    request: Request,
    db: PublicTenantSession,
) -> ApplicationStatusCheckResponse:
    """
    Check the status of an application using the tracking code.

    SECURITY: Returns ONLY minimal data:
    - status (e.g., "submitted", "offered")
    - applicant_first_name (already known to the person who applied)
    - submitted_at
    - last_updated_at

    No guardian info, no PII, no documents, no decision details.
    """
    service = ApplicationService(db)
    try:
        result = await service.get_by_tracking_code(
            tenant_id=request.state.tenant_id,
            tracking_code=tracking_code,
        )
        return ApplicationStatusCheckResponse(**result)
    except ApplicationServiceError as e:
        raise _handle_app_error(e)


@router.post(
    "/applications/{tracking_code}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document for application",
)
async def upload_document(
    tracking_code: str,
    data: DocumentUploadRequest,
    request: Request,
    db: PublicTenantSession,
) -> DocumentUploadResponse:
    """
    Request a presigned S3 URL for document upload.

    Validation:
    - Application must exist and be in DRAFT or SUBMITTED status
    - Max 5 documents per application
    - File size max 5MB
    - MIME types: application/pdf, image/jpeg, image/png
    - Document type must be in required_documents or 'other'

    S3 path format: admissions/{tenant_id}/{application_id}/{uuid}.{ext}

    Returns a presigned PUT URL. Frontend uploads directly to S3.
    After successful upload, the document record is created.
    """
    service = ApplicationService(db)
    try:
        result = await service.upload_document(
            tenant_id=request.state.tenant_id,
            tracking_code=tracking_code,
            document_type=data.document_type,
            file_name=data.file_name,
            mime_type=data.mime_type,
            file_size=data.file_size,
        )
        return DocumentUploadResponse(**result)
    except ApplicationServiceError as e:
        raise _handle_app_error(e)


@router.post(
    "/applications/{tracking_code}/pay",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate application fee payment",
)
async def initiate_payment(
    tracking_code: str,
    data: PaymentInitiateRequest,
    request: Request,
    db: PublicTenantSession,
) -> PaymentInitiateResponse:
    """
    Initialize Paystack payment for application fee.

    Validates:
    - Application exists and fee is not waived
    - No completed payment already exists for this application
    - Admission period has application_fee_amount set

    Creates application_payments record with status='pending',
    then calls Paystack to create a transaction.

    Paystack metadata includes: application_id, tenant_id, school_id,
    context="application_fee"

    Returns authorization_url for redirect or access_code for inline popup.
    """
    # Look up application by tracking code to get application_id and school_id
    from app.models.admissions import Application

    result = await db.execute(
        select(Application).where(
            Application.tenant_id == request.state.tenant_id,
            Application.tracking_code == tracking_code,
            Application.deleted_at.is_(None),
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    service = ApplicationPaymentService(db)
    try:
        payment_result = await service.initialize_payment(
            tenant_id=request.state.tenant_id,
            school_id=app.school_id,
            application_id=app.id,
            tracking_code=tracking_code,
        )
        return payment_result
    except ApplicationPaymentError as e:
        raise _handle_payment_error(e)
