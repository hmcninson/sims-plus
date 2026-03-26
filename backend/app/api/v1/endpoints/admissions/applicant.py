"""
SIMS Plus - Applicant Account Authenticated Endpoints

Protected endpoints for applicant profile management, application
dashboard, drafts, document upload, payment initiation, print view,
and application claiming.

Uses DatabaseSession (tenant-scoped via JWT) + ApplicantUser (role=applicant).

IMPORTANT: Do NOT use 'from __future__ import annotations' in this file.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    ApplicantUser,
    DatabaseSession,
    require_permissions,
)
from app.api.v1.endpoints.admissions.applicant_public import (
    _resolve_default_school_id,
)
from app.schemas.admissions import (
    AdmissionDecisionResponse,
    ApplicationDocumentResponse,
    ApplicationGuardianResponse,
    ApplicationPaymentResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    OfferDetailResponse,
    OfferResponseRequest,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    StatusHistoryResponse,
)
from app.schemas.applicant import (
    ApplicantPasswordChange,
    ApplicantProfileResponse,
    ApplicantProfileUpdate,
    ClaimApplicationRequest,
    ClaimApplicationResponse,
    DraftApplicationCreate,
    DraftApplicationUpdate,
    DraftSubmitResponse,
    GuardianPrefillResponse,
    MyApplicationDetailResponse,
    MyApplicationListItem,
    MyApplicationListResponse,
    PrintableApplicationResponse,
    PrintableDecisionInfo,
    PrintableDocumentInfo,
    PrintableGuardianInfo,
    PrintablePaymentInfo,
)
from app.services.admissions.applicant_service import (
    ApplicantAccountError,
    ApplicantAccountService,
)
from app.services.admissions.application_service import (
    ApplicationService,
    ApplicationServiceError,
)
from app.services.admissions.payment_service import (
    ApplicationPaymentError,
    ApplicationPaymentService,
)

router = APIRouter(prefix="/applicant")


def _error_status(code: str) -> int:
    """Map service error codes to HTTP status codes."""
    status_map = {
        "NOT_FOUND": 404,
        "NOT_DRAFT": 409,
        "ALREADY_CLAIMED": 409,
        "CLAIM_FAILED": 400,
        "EMAIL_MISMATCH": 403,
        "INVALID_PASSWORD": 400,
        "MISSING_TARGET_CLASS": 422,
        "MISSING_DOB": 422,
        "MISSING_GENDER": 422,
        "NO_GUARDIANS": 422,
        "INCOMPLETE_GUARDIAN": 422,
        "VALIDATION_ERROR": 422,
        "PERIOD_NOT_OPEN": 400,
        "PERIOD_FULL": 400,
        "DAILY_CAP_EXCEEDED": 429,
        # Phase 2: offer response codes
        "INVALID_STATUS": 422,
        "INVALID_RESPONSE": 422,
        "INVALID_TRANSITION": 422,
    }
    return status_map.get(code, 400)


# =========================
# Profile Endpoints
# =========================


@router.get(
    "/profile",
    response_model=ApplicantProfileResponse,
    summary="Get applicant profile",
    dependencies=[Depends(require_permissions("applicant.profile.read"))],
)
async def get_profile(
    user: ApplicantUser,
    db: DatabaseSession,
) -> ApplicantProfileResponse:
    """
    Get the current applicant's profile information.
    User ID is extracted from JWT -- never from request params.
    """
    service = ApplicantAccountService(db)
    try:
        profile = await service.get_profile(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
        )
        return ApplicantProfileResponse(
            id=profile.id,
            email=profile.email,
            first_name=profile.first_name,
            last_name=profile.last_name,
            phone=profile.phone,
            email_verified=profile.email_verified,
            created_at=profile.created_at,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.put(
    "/profile",
    response_model=ApplicantProfileResponse,
    summary="Update applicant profile",
    dependencies=[Depends(require_permissions("applicant.profile.update"))],
)
async def update_profile(
    data: ApplicantProfileUpdate,
    user: ApplicantUser,
    db: DatabaseSession,
) -> ApplicantProfileResponse:
    """
    Update the current applicant's profile (name, phone).
    Email changes are not supported to preserve claim flow integrity.
    """
    service = ApplicantAccountService(db)
    try:
        profile = await service.update_profile(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
        )
        return ApplicantProfileResponse(
            id=profile.id,
            email=profile.email,
            first_name=profile.first_name,
            last_name=profile.last_name,
            phone=profile.phone,
            email_verified=profile.email_verified,
            created_at=profile.created_at,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.put(
    "/profile/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change applicant password",
    dependencies=[Depends(require_permissions("applicant.profile.update"))],
)
async def change_password(
    data: ApplicantPasswordChange,
    user: ApplicantUser,
    db: DatabaseSession,
) -> None:
    """
    Change the current applicant's password.
    Requires current password for verification.
    After change, all existing tokens are revoked.
    """
    service = ApplicantAccountService(db)
    try:
        await service.change_password(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
            current_password=data.current_password,
            new_password=data.new_password,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


# =========================
# My Applications Endpoints
# =========================


@router.get(
    "/applications",
    response_model=MyApplicationListResponse,
    summary="List my applications",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def list_my_applications(
    user: ApplicantUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
) -> MyApplicationListResponse:
    """
    List all applications belonging to the current applicant.

    Returns applications sorted by most recently updated.
    Supports pagination and optional status filtering.

    IDOR safe: user_id comes from JWT, not request params.
    """
    service = ApplicationService(db)
    try:
        applications, total = await service.list_my_applications(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            status=status_filter,
            page=page,
            page_size=page_size,
        )

        items = [
            MyApplicationListItem(
                id=app.id,
                tracking_code=app.tracking_code,
                admission_period_id=app.admission_period_id,
                applicant_first_name=app.applicant_first_name,
                applicant_last_name=app.applicant_last_name,
                target_class_name=app.target_class.name if app.target_class else None,
                admission_period_name=app.admission_period.name if app.admission_period else None,
                status=app.status,
                submitted_at=app.submitted_at,
                created_at=app.created_at,
                updated_at=app.updated_at,
            )
            for app in applications
        ]

        return MyApplicationListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.get(
    "/applications/guardian-prefill",
    response_model=list[GuardianPrefillResponse],
    summary="Get guardian info for pre-fill",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def get_guardian_prefill(
    user: ApplicantUser,
    db: DatabaseSession,
):
    """
    Get guardian info from the most recent submitted application.
    Used for pre-filling the guardian section when creating a new application
    for another child. Returns empty list if no previous applications exist.
    """
    service = ApplicationService(db)
    guardians = await service.get_latest_guardian_info(
        tenant_id=UUID(user["tenant_id"]),
        applicant_user_id=UUID(user["user_id"]),
    )
    return guardians


@router.get(
    "/applications/{application_id}",
    response_model=MyApplicationDetailResponse,
    summary="Get my application detail",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def get_my_application(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> MyApplicationDetailResponse:
    """
    Get a single application owned by the current applicant.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    Returns application with guardians, documents, payments, status history,
    and decision.
    """
    service = ApplicationService(db)
    try:
        app = await service.get_my_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )
        return MyApplicationDetailResponse(
            id=app.id,
            tenant_id=app.tenant_id,
            tracking_code=app.tracking_code,
            admission_period_id=app.admission_period_id,
            admission_period_name=app.admission_period.name if app.admission_period else None,
            applicant_first_name=app.applicant_first_name,
            applicant_last_name=app.applicant_last_name,
            applicant_other_names=app.applicant_other_names,
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            nationality=app.nationality,
            target_class_id=app.target_class_id,
            target_class_name=app.target_class.name if app.target_class else None,
            status=app.status,
            custom_fields=app.custom_fields or {},
            fee_waived=app.fee_waived,
            exam_waived=app.exam_waived,
            applicant_photo_url=app.applicant_photo_url,
            previous_school=app.previous_school,
            medical_info=app.medical_info,
            submitted_at=app.submitted_at,
            created_at=app.created_at,
            updated_at=app.updated_at,
            guardians=[g for g in (app.guardians or []) if g.deleted_at is None],
            documents=[d for d in (app.documents or []) if d.deleted_at is None],
            payments=[p for p in (app.payments or []) if p.deleted_at is None],
            status_history=list(app.status_history or []),
            decision=app.decision if app.decision and getattr(app.decision, "deleted_at", None) is None else None,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications",
    response_model=DraftSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create draft application",
    dependencies=[Depends(require_permissions("applicant.applications.create"))],
)
async def create_draft(
    data: DraftApplicationCreate,
    request: Request,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DraftSubmitResponse:
    """
    Create a new draft application for a child.

    The application starts in DRAFT status and can be updated
    multiple times before submission. Only admission_period_id
    and child name are required to start.

    No Turnstile required (user is authenticated).
    """
    service = ApplicationService(db)
    try:
        tenant_id = UUID(user["tenant_id"])
        # Resolve default school for this tenant
        school_id = await _resolve_default_school_id(db, tenant_id)

        application = await service.create_draft(
            tenant_id=tenant_id,
            school_id=school_id,
            applicant_user_id=UUID(user["user_id"]),
            admission_period_id=data.admission_period_id,
            applicant_first_name=data.applicant_first_name,
            applicant_last_name=data.applicant_last_name,
            applicant_other_names=data.applicant_other_names,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            nationality=data.nationality,
            target_class_id=data.target_class_id,
            previous_school=data.previous_school,
            medical_info=data.medical_info,
            custom_fields=data.custom_fields,
            guardians=(
                [g.model_dump(exclude_none=True) for g in data.guardians]
                if data.guardians
                else None
            ),
        )

        return DraftSubmitResponse(
            id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
            payment_required=False,  # Draft -- payment only checked on submit
            application_fee_amount=None,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.put(
    "/applications/{application_id}",
    response_model=DraftSubmitResponse,
    summary="Update draft application",
    dependencies=[Depends(require_permissions("applicant.applications.update"))],
)
async def update_draft(
    application_id: UUID,
    data: DraftApplicationUpdate,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DraftSubmitResponse:
    """
    Update an existing draft application (auto-save on each wizard step).

    Only DRAFT applications can be updated.
    All fields are optional for partial save.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    """
    service = ApplicationService(db)
    try:
        application = await service.update_draft(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
            applicant_first_name=data.applicant_first_name,
            applicant_last_name=data.applicant_last_name,
            applicant_other_names=data.applicant_other_names,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            nationality=data.nationality,
            target_class_id=data.target_class_id,
            previous_school=data.previous_school,
            medical_info=data.medical_info,
            custom_fields=data.custom_fields,
            guardians=(
                [g.model_dump(exclude_none=True) for g in data.guardians]
                if data.guardians
                else None
            ),
        )

        return DraftSubmitResponse(
            id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
            payment_required=False,
            application_fee_amount=None,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications/{application_id}/submit",
    response_model=DraftSubmitResponse,
    summary="Submit draft application",
    dependencies=[Depends(require_permissions("applicant.applications.submit"))],
)
async def submit_draft(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DraftSubmitResponse:
    """
    Submit a draft application after filling all required fields.

    Full validation is performed:
    - target_class_id, date_of_birth, gender must be set
    - At least one guardian with complete info required
    - custom_fields validated against form_schema

    If fee is required and not paid/waived, status stays DRAFT.
    If fee is not required, status transitions to SUBMITTED.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    """
    service = ApplicationService(db)
    try:
        application = await service.submit_draft(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )

        # Determine if payment is still required
        payment_required = (
            application.status == "draft"
            and not application.fee_waived
        )

        return DraftSubmitResponse(
            id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
            payment_required=payment_required,
            application_fee_amount=None,  # Populated from period if needed
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document to application",
    dependencies=[Depends(require_permissions("applicant.applications.update"))],
)
async def upload_document(
    application_id: UUID,
    data: DocumentUploadRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> DocumentUploadResponse:
    """
    Request a presigned S3 URL for document upload on an application.

    IDOR protection: verifies application ownership before generating URL.

    Validation:
    - Application must be in DRAFT or SUBMITTED status
    - Max 5 documents per application
    - File size max 5MB
    - MIME: application/pdf, image/jpeg, image/png
    """
    # Verify ownership via public IDOR-safe query (eager-loads relations but
    # correctness over micro-optimization -- _get_my_application is private API)
    app_service = ApplicationService(db)
    try:
        my_app = await app_service.get_my_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)

    # Delegate to existing document upload logic using tracking_code
    try:
        result = await app_service.upload_document(
            tenant_id=UUID(user["tenant_id"]),
            tracking_code=my_app.tracking_code,
            document_type=data.document_type,
            file_name=data.file_name,
            mime_type=data.mime_type,
            file_size=data.file_size,
        )
        return DocumentUploadResponse(**result)
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.post(
    "/applications/{application_id}/pay",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate payment for application",
    dependencies=[Depends(require_permissions("applicant.applications.update"))],
)
async def initiate_payment(
    application_id: UUID,
    data: PaymentInitiateRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> PaymentInitiateResponse:
    """
    Initialize Paystack payment for application fee.

    IDOR protection: verifies application ownership before initiating.

    The payment flow is identical to the anonymous flow except:
    - User is identified (for receipt/history)
    - Application is already linked to the account
    """
    # Verify ownership via public IDOR-safe query
    app_service = ApplicationService(db)
    try:
        my_app = await app_service.get_my_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)

    # Delegate to existing payment service using the application's school_id
    payment_service = ApplicationPaymentService(db)
    try:
        result = await payment_service.initialize_payment(
            tenant_id=UUID(user["tenant_id"]),
            school_id=my_app.school_id,
            application_id=application_id,
            callback_url=data.callback_url,
            payment_method=data.payment_method,
        )
        return result
    except ApplicationPaymentError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


@router.get(
    "/applications/{application_id}/print",
    response_model=PrintableApplicationResponse,
    summary="Get printable application view",
    dependencies=[Depends(require_permissions("applicant.applications.read"))],
)
async def get_printable_application(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> PrintableApplicationResponse:
    """
    Get full application data formatted for server-rendered print view.

    Loads all relations: guardians, documents, payments, decision,
    admission period, target class, and school info.

    Does NOT include internal notes or status history.

    IDOR protection: verifies application.applicant_user_id == JWT user_id.
    """
    service = ApplicationService(db)
    try:
        app = await service.get_printable_application(
            tenant_id=UUID(user["tenant_id"]),
            applicant_user_id=UUID(user["user_id"]),
            application_id=application_id,
        )

        # Build response with nested relation data
        return PrintableApplicationResponse(
            id=app.id,
            tracking_code=app.tracking_code,
            school_name=app.school.name if app.school else "",
            school_logo_url=getattr(app.school, "logo_url", None) if app.school else None,
            admission_period_name=(
                app.admission_period.name if app.admission_period else ""
            ),
            applicant_first_name=app.applicant_first_name,
            applicant_last_name=app.applicant_last_name,
            applicant_other_names=app.applicant_other_names,
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            nationality=app.nationality,
            target_class_name=(
                app.target_class.name if app.target_class else None
            ),
            previous_school=app.previous_school,
            medical_info=app.medical_info,
            custom_fields=app.custom_fields,
            status=app.status,
            submitted_at=app.submitted_at,
            created_at=app.created_at,
            guardians=[
                PrintableGuardianInfo(
                    first_name=g.first_name,
                    last_name=g.last_name,
                    phone=g.phone,
                    email=g.email,
                    relationship=g.relationship,
                    is_primary=g.is_primary,
                    occupation=g.occupation,
                    address=g.address,
                )
                for g in (app.guardians or [])
                if g.deleted_at is None
            ],
            documents=[
                PrintableDocumentInfo(
                    document_type=d.document_type,
                    file_name=d.file_name,
                    created_at=d.created_at,
                )
                for d in (app.documents or [])
                if d.deleted_at is None
            ],
            payments=[
                PrintablePaymentInfo(
                    amount=p.amount,
                    currency=p.currency,
                    payment_method=p.payment_method,
                    status=p.status,
                    paid_at=p.paid_at,
                )
                for p in (app.payments or [])
                if p.deleted_at is None
            ],
            decision=(
                PrintableDecisionInfo(
                    decision_type=app.decision.decision_type,
                    offered_class_name=None,
                    conditions=app.decision.conditions,
                    decision_date=app.decision.decision_date,
                    response_deadline=app.decision.response_deadline,
                )
                if app.decision and getattr(app.decision, "deleted_at", None) is None
                else None
            ),
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


# =========================
# Claim Application
# =========================


@router.post(
    "/applications/claim",
    response_model=ClaimApplicationResponse,
    summary="Claim an anonymous application",
    dependencies=[Depends(require_permissions("applicant.applications.claim"))],
)
async def claim_application(
    data: ClaimApplicationRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> ClaimApplicationResponse:
    """
    Claim a previously anonymous application by tracking code.

    Requires:
    1. Valid tracking code for an application in this tenant
    2. Application must not already be linked to an account
    3. At least one guardian email on the application must match
       the applicant's account email

    After claiming, the application appears in the applicant's dashboard.
    """
    service = ApplicantAccountService(db)
    try:
        application = await service.claim_application(
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
            tracking_code=data.tracking_code,
        )
        return ClaimApplicationResponse(
            application_id=application.id,
            tracking_code=application.tracking_code,
            status=application.status,
        )
    except ApplicantAccountError as e:
        raise HTTPException(status_code=_error_status(e.code), detail=e.message)


# =========================
# Offer Response Endpoints (Enrollment Gap Closure Phase 2)
# =========================


@router.get(
    "/offers/{application_id}",
    response_model=OfferDetailResponse,
    summary="Get offer details",
)
async def get_offer_details(
    application_id: UUID,
    user: ApplicantUser,
    db: DatabaseSession,
) -> OfferDetailResponse:
    """
    Get full offer details for an application.

    IDOR check: only the owning applicant can view offer details.
    Returns decision info, conditions, deadline, letter URL, and response status.
    """
    service = ApplicantAccountService(db)
    try:
        details = await service.get_offer_details(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            user_id=UUID(user["user_id"]),
        )
        return OfferDetailResponse(**details)
    except ApplicantAccountError as e:
        raise HTTPException(
            status_code=_error_status(e.code),
            detail=e.message,
        )


@router.post(
    "/offers/{application_id}/respond",
    response_model=OfferDetailResponse,
    summary="Accept or decline admission offer",
)
async def respond_to_offer(
    application_id: UUID,
    data: OfferResponseRequest,
    user: ApplicantUser,
    db: DatabaseSession,
) -> OfferDetailResponse:
    """
    Accept or decline an admission offer.

    IDOR check: only the owning applicant (AD-5) can respond.
    - accepted: transitions application to ACCEPTED status
    - declined: transitions application to WITHDRAWN status
    """
    service = ApplicantAccountService(db)
    try:
        await service.respond_to_offer(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            user_id=UUID(user["user_id"]),
            response=data.response.value,
            notes=data.notes,
        )
        # Re-fetch full offer details for the response
        details = await service.get_offer_details(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            user_id=UUID(user["user_id"]),
        )
        return OfferDetailResponse(**details)
    except ApplicantAccountError as e:
        raise HTTPException(
            status_code=_error_status(e.code),
            detail=e.message,
        )
