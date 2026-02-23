"""
SIMS Plus - Teacher Portal Endpoint Helpers

Shared helper functions used across teacher portal endpoint modules.
Maps service error codes to HTTP status codes and extracts user context.
"""

from uuid import UUID

from fastapi import HTTPException, status

from app.services.teacher import TeacherServiceError


# TeacherServiceError code -> HTTP status code mapping
_TEACHER_ERROR_CODE_STATUS_MAP: dict[str, int] = {
    "not_a_teacher": 403,
    "access_denied": 403,
    "not_found": 404,
    "no_academic_year": 422,
    "no_current_term": 422,
    "scores_locked": 409,
    "no_comment": 422,
    "student_not_in_section": 422,
    "teacher_error": 400,
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


def _get_school_id(user: dict) -> UUID:
    """
    Extract school_id from the ValidatedUser dict.

    Raises HTTPException if school_id is missing from the JWT claims.
    """
    school_id = user.get("school_id")
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no school association",
        )
    return UUID(school_id)


def _handle_teacher_error(e: TeacherServiceError) -> HTTPException:
    """
    Map a TeacherServiceError to an appropriate HTTPException.

    Uses the error code to determine the HTTP status code. Falls back
    to 400 for unrecognized error codes.
    """
    http_status = _TEACHER_ERROR_CODE_STATUS_MAP.get(e.code, 400)
    return HTTPException(status_code=http_status, detail=e.message)
