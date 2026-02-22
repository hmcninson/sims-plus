"""
SIMS Plus - Parent Portal Boarding & Transport Endpoints

Read-only endpoints for parents to view their children's boarding
and transport information. These are lightweight views that pull
from the boarding and transport modules.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

import structlog

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.parent import ParentService, ParentServiceError

from ._helpers import _get_user_id, _handle_parent_error

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/children/{student_id}/boarding",
    summary="Get child boarding info",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def get_child_boarding(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """
    Get boarding information for a child: house, dormitory, bed assignment.

    Returns an empty object if the child is not a boarder or the boarding
    module is not active. Gracefully degrades if boarding models are not
    available.
    """
    user_id = _get_user_id(user)
    parent_service = ParentService(db)

    try:
        await parent_service.require_parent_child_access(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    # Attempt to load boarding info; gracefully degrade if the module is unavailable
    try:
        from sqlalchemy import select, and_
        from sqlalchemy.orm import joinedload
        from app.models.boarding import StudentBoarding, BoardingStatus

        result = await db.execute(
            select(StudentBoarding)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentBoarding.tenant_id == tenant.tenant_id,
                    StudentBoarding.student_id == student_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
            .options(
                joinedload(StudentBoarding.house),
                joinedload(StudentBoarding.dormitory),
                joinedload(StudentBoarding.bed),
            )
        )
        assignment = result.scalar_one_or_none()

        if not assignment:
            return {"is_boarder": False}

        return {
            "is_boarder": True,
            "house_name": assignment.house.name if assignment.house else None,
            "dormitory_name": assignment.dormitory.name if assignment.dormitory else None,
            "bed_number": assignment.bed.bed_number if assignment.bed else None,
            "check_in_date": (
                assignment.check_in_date.isoformat()
                if assignment.check_in_date else None
            ),
        }

    except ImportError:
        # Boarding module is not available -- gracefully degrade
        logger.debug(
            "parent_boarding_module_not_available",
            student_id=str(student_id),
        )
        return {"is_boarder": False}
    except Exception:
        logger.exception(
            "parent_boarding_info_query_failed",
            student_id=str(student_id),
        )
        raise


@router.get(
    "/children/{student_id}/transport",
    summary="Get child transport info",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def get_child_transport(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """
    Get transport information for a child: route, stop, vehicle.

    Returns an empty object if the child is not assigned to a transport
    route or the transport module is not active.
    """
    user_id = _get_user_id(user)
    parent_service = ParentService(db)

    try:
        await parent_service.require_parent_child_access(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    # Attempt to load transport info; gracefully degrade if the module is unavailable
    try:
        from sqlalchemy import select, and_
        from sqlalchemy.orm import joinedload
        from app.models.transport import StudentTransport

        result = await db.execute(
            select(StudentTransport)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentTransport.tenant_id == tenant.tenant_id,
                    StudentTransport.student_id == student_id,
                    StudentTransport.is_active == True,
                    StudentTransport.deleted_at.is_(None),
                )
            )
            .options(
                joinedload(StudentTransport.route),
                joinedload(StudentTransport.stop),
            )
        )
        assignment = result.scalar_one_or_none()

        if not assignment:
            return {"uses_transport": False}

        return {
            "uses_transport": True,
            "route_name": assignment.route.name if assignment.route else None,
            "stop_name": assignment.stop.name if assignment.stop else None,
            "pickup_time": (
                assignment.stop.pickup_time.isoformat()
                if assignment.stop and assignment.stop.pickup_time else None
            ),
            "dropoff_time": (
                assignment.stop.dropoff_time.isoformat()
                if assignment.stop and assignment.stop.dropoff_time else None
            ),
        }

    except ImportError:
        # Transport module is not available -- gracefully degrade
        logger.debug(
            "parent_transport_module_not_available",
            student_id=str(student_id),
        )
        return {"uses_transport": False}
    except Exception:
        logger.exception(
            "parent_transport_info_query_failed",
            student_id=str(student_id),
        )
        raise
