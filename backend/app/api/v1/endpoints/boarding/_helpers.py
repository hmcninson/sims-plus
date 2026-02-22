"""
SIMS Plus - Boarding Endpoint Helpers

Shared helper functions used across boarding endpoint modules.
"""

from uuid import UUID

from fastapi import HTTPException, status

from app.services.boarding import BoardingServiceError


# Error code to HTTP status code mapping
_ERROR_CODE_STATUS_MAP: dict[str, int] = {
    "not_found": 404,
    "conflict": 409,
    "duplicate_house_name": 409,
    "duplicate_house_code": 409,
    "duplicate_dormitory_name": 409,
    "duplicate_bed_number": 409,
    "duplicate_roll_call": 409,
    "duplicate_entry": 409,
    "duplicate_meal": 409,
    "already_assigned": 409,
    "already_resolved": 409,
    "bed_occupied": 409,
    "invalid_status": 422,
    "invalid_status_transition": 422,
    "bed_maintenance": 422,
    "bed_dormitory_mismatch": 422,
    "dormitory_house_mismatch": 422,
    "not_a_boarder": 422,
    "students_not_in_house": 422,
}


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


def _handle_service_error(e: BoardingServiceError) -> HTTPException:
    """
    Map a BoardingServiceError to an appropriate HTTPException.

    Uses the error code to determine the HTTP status code. Falls back
    to 400 for unrecognized error codes.
    """
    http_status = _ERROR_CODE_STATUS_MAP.get(e.code, 400)
    return HTTPException(status_code=http_status, detail=e.message)
