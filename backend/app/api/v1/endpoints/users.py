"""
SIMS Plus - User Management Endpoints

API endpoints for user CRUD operations.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.config import settings
from app.models.user import UserRole, UserStatus
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserRoleUpdate,
    UserStatusUpdate,
    ResetUserPasswordRequest,
    UserInviteRequest,
    UserInviteResponse,
)
import structlog

from app.services.user import UserService, UserServiceError
from app.services.email import email_service

logger = structlog.get_logger()

router = APIRouter()


def _user_to_response(user) -> UserResponse:
    """Convert User model to UserResponse schema."""
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        role=user.role,
        status=user.status,
        school_id=user.school_id,
        email_verified=user.email_verified,
        mfa_enabled=user.mfa_enabled,
        last_login=user.last_login,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# =========================
# User CRUD Endpoints
# =========================


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def list_users(
    tenant: RequestTenant,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    status: Optional[UserStatus] = Query(None, description="Filter by status"),
    school_id: Optional[UUID] = Query(None, description="Filter by school"),
) -> UserListResponse:
    """
    List all users with pagination and filters.

    Requires `users.read` permission.
    """
    service = UserService(db)
    users, total = await service.list_users(
        tenant_id=tenant.tenant_id,
        page=page,
        page_size=page_size,
        search=search,
        role=role,
        status=status,
        school_id=school_id,
    )

    total_pages = (total + page_size - 1) // page_size

    return UserListResponse(
        items=[_user_to_response(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def create_user(
    data: UserCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> UserResponse:
    """
    Create a new user.

    Requires `users.create` permission.
    Sends login credentials email to the new user.
    """
    service = UserService(db)

    try:
        user = await service.create_user(
            tenant_id=tenant.tenant_id,
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            role=data.role,
            school_id=data.school_id,
            status=UserStatus.ACTIVE,  # Admin-created users are active by default
            email_verified=True,  # Admin-created users are verified
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except IntegrityError as e:
        # Handle duplicate email constraint violation
        if "uq_users_email_tenant" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create user due to a database constraint",
        )

    # Send login credentials email to the new user
    try:
        # Build portal URL
        if settings.is_production:
            portal_url = f"https://{tenant.subdomain}.simsplus.io"
        else:
            portal_url = "http://localhost:3000"

        # Get role display name
        role_display = data.role.value.replace("_", " ").title()

        await email_service.send_user_credentials_email(
            to_email=data.email,
            user_name=f"{data.first_name} {data.last_name}",
            password=data.password,
            role=role_display,
            school_name=tenant.name,
            portal_url=portal_url,
        )
        logger.info("credentials_email_sent", to=data.email)
    except Exception:
        # Log error but don't fail the request -- user is already created
        logger.error("credentials_email_failed", to=data.email, exc_info=True)

    return _user_to_response(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def get_user(
    user_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> UserResponse:
    """
    Get a single user by ID.

    Requires `users.read` permission.
    """
    service = UserService(db)
    user = await service.get_user(user_id, tenant.tenant_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> UserResponse:
    """
    Update a user.

    Requires `users.update` permission.
    """
    service = UserService(db)

    user = await service.update_user(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        role=data.role,
        status=data.status,
        school_id=data.school_id,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    dependencies=[Depends(require_permissions("users.delete"))],
)
async def delete_user(
    user_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user_id: CurrentUserId,
) -> None:
    """
    Delete a user (soft delete).

    Requires `users.delete` permission.
    Cannot delete yourself.
    """
    # Prevent self-deletion
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    service = UserService(db)
    deleted = await service.delete_user(user_id, tenant.tenant_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


# =========================
# Role & Status Endpoints
# =========================


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
    summary="Update user role",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def update_user_role(
    user_id: UUID,
    data: UserRoleUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> UserResponse:
    """
    Update a user's role.

    Requires `users.update` permission.
    """
    service = UserService(db)
    user = await service.update_user_role(user_id, tenant.tenant_id, data.role)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(user)


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    summary="Update user status",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def update_user_status(
    user_id: UUID,
    data: UserStatusUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user_id: CurrentUserId,
) -> UserResponse:
    """
    Update a user's status (activate, suspend, deactivate).

    Requires `users.update` permission.
    Cannot change your own status.
    """
    # Prevent self-status-change
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own status",
        )

    service = UserService(db)
    user = await service.update_user_status(user_id, tenant.tenant_id, data.status)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=UserResponse,
    summary="Reset user password",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def reset_user_password(
    user_id: UUID,
    data: ResetUserPasswordRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> UserResponse:
    """
    Reset a user's password (admin action).

    Requires `users.update` permission.
    Optionally sends email notification.
    """
    service = UserService(db)
    user = await service.reset_user_password(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
        new_password=data.new_password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # TODO: Send email notification if data.send_email is True

    return _user_to_response(user)


# =========================
# Stats Endpoint
# =========================


@router.get(
    "/stats/by-role",
    summary="Get user counts by role",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def get_user_stats_by_role(
    tenant: RequestTenant,
    db: DatabaseSession,
) -> dict[str, int]:
    """
    Get count of users grouped by role.

    Requires `users.read` permission.
    """
    service = UserService(db)
    return await service.count_users_by_role(tenant.tenant_id)


# =========================
# Invite Endpoint
# =========================


@router.post(
    "/invite",
    response_model=UserInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new user",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def invite_user(
    data: UserInviteRequest,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> UserInviteResponse:
    """
    Invite a new user by email.

    Creates a user account with PENDING status and a temporary password,
    then sends an invitation email with login credentials.
    Requires `users.create` permission.
    """
    import secrets

    service = UserService(db)

    # Generate a secure temporary password that meets policy requirements
    temp_password = secrets.token_urlsafe(12) + "!A1"

    try:
        new_user = await service.create_user(
            tenant_id=tenant.tenant_id,
            email=data.email,
            password=temp_password,
            first_name=data.first_name,
            last_name=data.last_name,
            role=data.role,
            status=UserStatus.PENDING,
            email_verified=False,
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except IntegrityError as e:
        if "uq_users_email_tenant" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to invite user due to a database constraint",
        )

    # Send invitation email with temporary credentials
    try:
        if settings.is_production:
            portal_url = f"https://{tenant.subdomain}.simsplus.io"
        else:
            portal_url = "http://localhost:3000"

        role_display = data.role.value.replace("_", " ").title()

        # Build inviter display name from the current user's email as fallback
        inviter_name = user.get("email", "An administrator")

        await email_service.send_user_invite(
            to_email=data.email,
            inviter_name=inviter_name,
            school_name=tenant.name,
            temp_password=temp_password,
            role=role_display,
            portal_url=portal_url,
        )
        logger.info("invite_email_sent", to=data.email)
    except Exception:
        # Log error but don't fail -- the user account was already created
        logger.error("invite_email_failed", to=data.email, exc_info=True)

    return UserInviteResponse(
        id=new_user.id,
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        role=new_user.role,
        status=new_user.status,
        created_at=new_user.created_at,
    )
