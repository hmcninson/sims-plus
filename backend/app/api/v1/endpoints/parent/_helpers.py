"""
SIMS Plus - Parent Portal Endpoint Helpers

Shared helper functions used across parent portal endpoint modules.
Maps service error codes to HTTP status codes and extracts user context.
"""

from uuid import UUID

from fastapi import HTTPException, status

from app.services.parent import ParentServiceError
from app.services.payment import OnlinePaymentError
from app.services.announcement import AnnouncementServiceError
from app.services.teacher_note import TeacherNoteServiceError


# ParentServiceError code -> HTTP status code mapping
_PARENT_ERROR_CODE_STATUS_MAP: dict[str, int] = {
    "access_denied": 403,
    "not_found": 404,
    "student_not_found": 404,
    "term_not_found": 404,
    "report_not_found": 404,
    "report_not_published": 403,
    "note_not_found": 404,
    "invoice_not_found": 404,
    "user_not_found": 404,
    "not_a_parent": 403,
    "email_required": 422,
    "email_role_conflict": 409,
    "invalid_month": 422,
    "invalid_quiet_hours": 422,
    "invalid_time_format": 422,
    "parent_error": 400,
}

# OnlinePaymentError code -> HTTP status code mapping
_PAYMENT_ERROR_CODE_STATUS_MAP: dict[str, int] = {
    "INVOICE_NOT_FOUND": 404,
    "INVOICE_NOT_PAYABLE": 409,
    "INVOICE_FULLY_PAID": 409,
    "AMOUNT_EXCEEDS_BALANCE": 422,
    "INVALID_AMOUNT": 422,
    "INVALID_METHOD": 422,
    "PHONE_REQUIRED": 422,
    "GATEWAY_ERROR": 502,
    "GATEWAY_TIMEOUT": 504,
    "GATEWAY_UNREACHABLE": 502,
    "INVALID_SIGNATURE": 401,
    "INVALID_PAYLOAD": 400,
    "MISSING_REFERENCE": 400,
    "INVALID_METADATA": 400,
    "CONFIG_ERROR": 500,
    "STUDENT_NOT_FOUND": 404,
    "RECORD_FAILED": 500,
    "PAYMENT_ERROR": 400,
}

# Announcement/TeacherNote error code -> HTTP status code mapping
_COMM_ERROR_CODE_STATUS_MAP: dict[str, int] = {
    "not_found": 404,
    "student_not_found": 404,
    "subject_not_found": 404,
    "already_published": 409,
    "missing_target_class": 422,
    "missing_target_house": 422,
    "forbidden": 403,
    "not_visible": 403,
    "announcement_error": 400,
    "teacher_note_error": 400,
}


def _get_user_id(user: dict) -> UUID:
    """
    Extract user_id from the ValidatedUser dict.

    Raises HTTPException if user_id is missing from the JWT claims.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )
    return UUID(user_id)


def _get_tenant_id(user: dict) -> UUID:
    """
    Extract tenant_id from the ValidatedUser dict.

    Raises HTTPException if tenant_id is missing from the JWT claims.
    """
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context not found in token",
        )
    return UUID(tenant_id)


def _get_school_id(user: dict) -> UUID:
    """
    Extract school_id from the ValidatedUser dict.

    Raises HTTPException if school_id is missing from the JWT claims,
    which would indicate the user has no school association.
    """
    school_id = user.get("school_id")
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no school association",
        )
    return UUID(school_id)


def _handle_parent_error(e: ParentServiceError) -> HTTPException:
    """
    Map a ParentServiceError to an appropriate HTTPException.

    Uses the error code to determine the HTTP status code. Falls back
    to 400 for unrecognized error codes.
    """
    http_status = _PARENT_ERROR_CODE_STATUS_MAP.get(e.code, 400)
    return HTTPException(status_code=http_status, detail=e.message)


def _handle_payment_error(e: OnlinePaymentError) -> HTTPException:
    """
    Map an OnlinePaymentError to an appropriate HTTPException.

    Uses the error code to determine the HTTP status code. Falls back
    to 400 for unrecognized error codes.
    """
    http_status = _PAYMENT_ERROR_CODE_STATUS_MAP.get(e.code, 400)
    return HTTPException(status_code=http_status, detail=e.message)


def _handle_comm_error(
    e: AnnouncementServiceError | TeacherNoteServiceError,
) -> HTTPException:
    """
    Map an AnnouncementServiceError or TeacherNoteServiceError to HTTPException.

    Uses the error code to determine the HTTP status code. Falls back
    to 400 for unrecognized error codes.
    """
    http_status = _COMM_ERROR_CODE_STATUS_MAP.get(e.code, 400)
    return HTTPException(status_code=http_status, detail=e.message)
