"""
SIMS Plus - Parent Portal Admin Endpoints

Admin-only endpoints for managing parent invitations and viewing
parent engagement statistics. These are used by school admins and
teachers, not by parents themselves.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    BulkParentInviteRequest,
    BulkParentInviteResponse,
    ParentEngagementStats,
    ParentInviteWithStudent,
)
from app.services.parent import (
    ParentOnboardingService,
    ParentServiceError,
)

from ._helpers import _get_school_id, _get_user_id, _handle_parent_error

router = APIRouter()


@router.post(
    "/invitations",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a parent",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def invite_parent(
    data: ParentInviteWithStudent,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """
    Invite a single parent to the portal and link them to a student.

    Creates a user account with the PARENT role (status=PENDING) and
    sends an invitation email with temporary credentials. If a parent
    user with this email already exists in this tenant, the student is
    linked without creating a duplicate account.
    """
    user_id = _get_user_id(user)
    school_id = _get_school_id(user)
    service = ParentOnboardingService(db)

    try:
        parent_user = await service.create_parent_for_student(
            student_id=data.student_id,
            guardian_data=data.model_dump(),
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            invited_by=user_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return {
        "user_id": str(parent_user.id),
        "email": parent_user.email,
        "status": parent_user.status.value,
    }


@router.post(
    "/invitations/bulk",
    response_model=BulkParentInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk invite parents",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def bulk_invite_parents(
    data: BulkParentInviteRequest,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkParentInviteResponse:
    """
    Invite multiple parents in a single operation (max 200 per batch).

    Deduplicates by email: if the same email appears for multiple students,
    one user account is created and multiple student_guardian links are made.

    Returns counts of created accounts, linked children, and any errors.
    """
    user_id = _get_user_id(user)
    school_id = _get_school_id(user)
    service = ParentOnboardingService(db)

    try:
        result = await service.bulk_create_parents(
            invitations=[inv.model_dump() for inv in data.invitations],
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            invited_by=user_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return BulkParentInviteResponse(**result)


@router.get(
    "/engagement-stats",
    response_model=ParentEngagementStats,
    summary="Get parent engagement stats",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def get_engagement_stats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ParentEngagementStats:
    """
    Get aggregate parent engagement metrics for the school admin dashboard.

    Returns: total parents, registered parents, active this week,
    announcement read rate, note acknowledgement rate, and online
    payment statistics for the current month.

    This is an admin-only endpoint. Parents do not have access.
    """
    # Compose engagement stats from direct queries rather than a service
    # method, since this aggregation spans multiple tables and is specific
    # to the admin view.
    from datetime import date, datetime, timedelta, UTC
    from decimal import Decimal

    from sqlalchemy import select, and_, func

    from app.models.parent import (
        Announcement,
        ParentNotificationPreference,
        TeacherNote,
    )
    from app.models.finance import Payment, PaymentStatus
    from app.models.student import Guardian
    from app.models.user import User, UserRole, UserStatus

    tenant_id = tenant.tenant_id

    # Total guardians in the system (potential parents)
    guardians_q = select(func.count(func.distinct(Guardian.email))).where(
        and_(
            Guardian.tenant_id == tenant_id,
            Guardian.deleted_at.is_(None),
        )
    )
    total_parents = (await db.execute(guardians_q)).scalar() or 0

    # Registered parents (have a User account with role=PARENT)
    registered_q = select(func.count(User.id)).where(
        and_(
            User.tenant_id == tenant_id,
            User.role == UserRole.PARENT,
            User.deleted_at.is_(None),
        )
    )
    registered_parents = (await db.execute(registered_q)).scalar() or 0

    # Active this week (parents who logged in within last 7 days)
    week_ago = datetime.now(UTC) - timedelta(days=7)
    active_q = select(func.count(User.id)).where(
        and_(
            User.tenant_id == tenant_id,
            User.role == UserRole.PARENT,
            User.status == UserStatus.ACTIVE,
            User.deleted_at.is_(None),
            User.last_login_at >= week_ago,
        )
    )
    active_this_week = (await db.execute(active_q)).scalar() or 0

    # Announcement read rate: ratio of acknowledged notes to total visible notes
    # (using teacher notes as a proxy since announcements don't track reads)
    visible_notes_q = select(func.count(TeacherNote.id)).where(
        and_(
            TeacherNote.tenant_id == tenant_id,
            TeacherNote.deleted_at.is_(None),
            TeacherNote.is_visible_to_parent == True,
        )
    )
    visible_notes = (await db.execute(visible_notes_q)).scalar() or 0

    acknowledged_notes_q = select(func.count(TeacherNote.id)).where(
        and_(
            TeacherNote.tenant_id == tenant_id,
            TeacherNote.deleted_at.is_(None),
            TeacherNote.is_visible_to_parent == True,
            TeacherNote.parent_acknowledged == True,
        )
    )
    acknowledged_notes = (await db.execute(acknowledged_notes_q)).scalar() or 0

    notes_acknowledged_rate = 0.0
    if visible_notes > 0:
        notes_acknowledged_rate = round(
            (acknowledged_notes / visible_notes) * 100, 2
        )

    # Online payments this month
    today = date.today()
    month_start = datetime(today.year, today.month, 1, tzinfo=UTC)

    online_payments_q = select(
        func.count(Payment.id),
        func.coalesce(func.sum(Payment.amount), Decimal("0.00")),
    ).where(
        and_(
            Payment.tenant_id == tenant_id,
            Payment.status == PaymentStatus.COMPLETED,
            Payment.is_voided == False,
            Payment.payment_date >= month_start,
            # Online payments have a bank_reference starting with "SIMS-"
            Payment.bank_reference.like("SIMS-%"),
        )
    )
    payment_result = (await db.execute(online_payments_q)).one()
    online_payments_this_month = payment_result[0] or 0
    online_payments_amount = payment_result[1] or Decimal("0.00")

    return ParentEngagementStats(
        total_parents=total_parents,
        registered_parents=registered_parents,
        active_this_week=active_this_week,
        announcements_read_rate=0.0,  # Not tracked at announcement level yet
        notes_acknowledged_rate=notes_acknowledged_rate,
        online_payments_this_month=online_payments_this_month,
        online_payments_amount=online_payments_amount,
    )
