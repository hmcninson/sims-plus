"""
SIMS Plus - Transport Endpoint Helpers

Shared helper functions used across transport endpoint modules.
"""

from uuid import UUID

from fastapi import HTTPException, status

from app.services.transport import TransportServiceError


# Error code to HTTP status code mapping
_ERROR_CODE_STATUS_MAP: dict[str, int] = {
    # 404 Not Found
    "not_found": 404,
    "vehicle_not_found": 404,
    "driver_not_found": 404,
    "route_not_found": 404,
    "student_not_found": 404,
    "academic_year_not_found": 404,
    # 409 Conflict
    "conflict": 409,
    "duplicate": 409,
    "duplicate_registration": 409,
    "duplicate_license": 409,
    "duplicate_route_code": 409,
    "duplicate_stop_order": 409,
    "duplicate_assignment": 409,
    "duplicate_trip": 409,
    "already_cancelled": 409,
    # 422 Unprocessable Entity
    "capacity": 422,
    "route_full": 422,
    "route_inactive": 422,
    "stop_not_on_route": 422,
    "incomplete_stop_list": 422,
    "invalid_status_transition": 422,
    "invalid_odometer": 422,
    "vehicle_in_use": 422,
    "driver_in_use": 422,
    "route_in_use": 422,
    "stop_in_use": 422,
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


def _handle_service_error(e: TransportServiceError) -> HTTPException:
    """
    Map a TransportServiceError to an appropriate HTTPException.

    Uses the error code to determine the HTTP status code. Falls back
    to 400 for unrecognized error codes.
    """
    http_status = _ERROR_CODE_STATUS_MAP.get(e.code, 400)
    return HTTPException(status_code=http_status, detail=e.message)
