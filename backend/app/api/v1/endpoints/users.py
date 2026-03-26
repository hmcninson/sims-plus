"""
SIMS Plus - User Management Endpoints

API endpoints for user CRUD operations.
"""

import csv
import io
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from starlette.responses import StreamingResponse

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
    UserImportResult,
    MySchoolRoleResponse,
)
from app.schemas.custom_role import CustomRoleAssign
import structlog

from app.services.user import UserService, UserServiceError
from app.services.mfa import MFAService, MFAError
from app.services.custom_role import CustomRoleError, CustomRoleService
from app.services.email import email_service
from app.services.audit import AuditService, AuditEventType
from app.services.token_blacklist import get_token_blacklist_service

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
        custom_role_id=user.custom_role_id,
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
    current_user: ValidatedUser,
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

    # Audit: log account creation by admin
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ACCOUNT_CREATED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="user",
        target_id=user.id,
        details={"role": data.role.value, "email": data.email},
    )

    return _user_to_response(user)


# =========================
# Bulk Import Endpoints
# =========================


@router.get(
    "/import/template",
    summary="Download user import CSV template",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def download_import_template():
    """
    Download a CSV template file for bulk user import.

    Returns a CSV with the required headers and two example rows.
    Requires `users.create` permission.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "first_name", "last_name", "role", "phone"])
    writer.writerow(["john.doe@example.com", "John", "Doe", "teacher", "+233241234567"])
    writer.writerow(["jane.smith@example.com", "Jane", "Smith", "finance_officer", ""])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=user_import_template.csv",
        },
    )


@router.post(
    "/import",
    response_model=UserImportResult,
    summary="Import users from CSV file",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def import_users(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    file: UploadFile = File(...),
    preview: bool = Form(default=False),
    school_id: Optional[UUID] = Form(default=None),
):
    """
    Import users from a CSV file.

    - **preview=true**: Validate only, return row-by-row preview without creating users
    - **preview=false** (default): Validate and create users with PENDING status

    CSV columns: email (required), first_name (required), last_name (required),
    role (required), phone (optional).

    Valid roles: school_admin, academic_head, finance_officer, hr_officer, teacher, house_parent.
    Max 200 rows per import. Max 1MB file size.

    Returns credentials (one-time) on actual import for admin to distribute as fallback.
    Requires `users.create` permission.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    # Validate file size (max 1MB)
    content = await file.read()
    if len(content) > 1_048_576:
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")

    service = UserService(db)
    try:
        result = await service.import_users_from_file(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            file_content=content,
            preview_only=preview,
            created_by_id=UUID(current_user["user_id"]),
        )
    except UserServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log on actual import (not preview)
    if not preview and result["created"] > 0:
        audit = AuditService(db)
        await audit.log(
            event_type=AuditEventType.ACCOUNT_CREATED,
            tenant_id=tenant.tenant_id,
            user_id=UUID(current_user["user_id"]),
            target_type="user",
            target_id=None,
            details={
                "action": "bulk_import",
                "total": result["total"],
                "created": result["created"],
                "errors": len(result["errors"]),
            },
        )

    return result


# =========================
# Self-Service Endpoints
# =========================


@router.get(
    "/me/schools",
    response_model=list[MySchoolRoleResponse],
    summary="Get current user's school roles",
    dependencies=[Depends(require_permissions("self.read"))],
)
async def get_my_schools(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[MySchoolRoleResponse]:
    service = UserService(db)
    user_id = UUID(current_user["user_id"])
    items = await service.get_user_school_roles(
        tenant_id=tenant.tenant_id,
        user_id=user_id,
    )
    return [MySchoolRoleResponse(**item) for item in items]


# =========================
# Single User Endpoints
# =========================


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
    current_user: ValidatedUser,
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

    # Token blacklisting: invalidate sessions when status or role changes via PUT,
    # so the user picks up new permissions / is logged out immediately.
    needs_blacklist = False
    if data.status in (UserStatus.SUSPENDED, UserStatus.DEACTIVATED):
        needs_blacklist = True
    if data.role is not None:
        # Role changed — JWT permissions claim is now stale
        needs_blacklist = True

    if needs_blacklist:
        try:
            blacklist_service = await get_token_blacklist_service()
            await blacklist_service.blacklist_user_tokens(str(user_id))
            logger.info("user_tokens_blacklisted_via_put", user_id=str(user_id))
        except Exception:
            logger.warning("token_blacklist_failed_via_put", user_id=str(user_id))

    # Audit: log user profile update
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.SETTINGS_CHANGED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="user",
        target_id=user_id,
        details={"updated_fields": [k for k, v in data.model_dump(exclude_unset=True).items()]},
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

    # Immediately invalidate all sessions for the deleted user
    try:
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_user_tokens(str(user_id))
    except Exception:
        logger.error("token_blacklist_failed_on_delete", user_id=str(user_id), exc_info=True)

    # Audit: log account deletion
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ACCOUNT_DEACTIVATED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user_id),
        target_type="user",
        target_id=user_id,
        details={"action": "deleted"},
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
    current_user: ValidatedUser,
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

    # Audit: log role change
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.USER_ROLE_CHANGED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="user",
        target_id=user_id,
        details={"new_role": data.role.value},
    )

    # Invalidate existing sessions so the user picks up new role permissions
    try:
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_user_tokens(str(user_id))
        logger.info("user_tokens_blacklisted_on_role_change", user_id=str(user_id), new_role=data.role.value)
    except Exception:
        logger.warning("token_blacklist_failed_on_role_change", user_id=str(user_id))

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

    # Immediately invalidate all sessions when user is suspended or deactivated
    if data.status in (UserStatus.SUSPENDED, UserStatus.DEACTIVATED):
        try:
            blacklist_service = await get_token_blacklist_service()
            await blacklist_service.blacklist_user_tokens(str(user_id))
        except Exception:
            logger.error(
                "token_blacklist_failed_on_status_change",
                user_id=str(user_id),
                new_status=data.status.value,
                exc_info=True,
            )

    # Audit: log status change with appropriate event type
    status_event_map = {
        UserStatus.ACTIVE: AuditEventType.ACCOUNT_ACTIVATED,
        UserStatus.SUSPENDED: AuditEventType.ACCOUNT_SUSPENDED,
        UserStatus.DEACTIVATED: AuditEventType.ACCOUNT_DEACTIVATED,
    }
    audit_event = status_event_map.get(data.status, AuditEventType.SETTINGS_CHANGED)

    audit = AuditService(db)
    await audit.log(
        event_type=audit_event,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user_id),
        target_type="user",
        target_id=user_id,
        details={"new_status": data.status.value},
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
    current_user: ValidatedUser,
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

    # Invalidate all existing sessions so old tokens can't be reused
    try:
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_user_tokens(str(user_id))
    except Exception:
        logger.error("token_blacklist_failed_on_password_reset", user_id=str(user_id), exc_info=True)

    # Send email with new password if requested
    if data.send_email:
        try:
            if settings.is_production:
                portal_url = f"https://{tenant.subdomain}.simsplus.io"
            else:
                portal_url = "http://localhost:3000"
            await email_service.send_user_credentials_email(
                to_email=user.email,
                user_name=f"{user.first_name} {user.last_name}",
                password=data.new_password,
                role=user.role.value.replace("_", " ").title(),
                school_name=tenant.name,
                portal_url=portal_url,
            )
            logger.info("password_reset_email_sent", to=user.email)
        except Exception:
            logger.error("password_reset_email_failed", to=user.email, exc_info=True)

    # Audit: log admin-initiated password reset
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.PASSWORD_RESET_COMPLETE,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="user",
        target_id=user_id,
        details={"send_email": data.send_email},
    )

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

    # Audit: log invited user account creation
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.ACCOUNT_CREATED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(user["user_id"]),
        target_type="user",
        target_id=new_user.id,
        details={"role": data.role.value, "email": data.email, "method": "invite"},
    )

    return UserInviteResponse(
        id=new_user.id,
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        role=new_user.role,
        status=new_user.status,
        created_at=new_user.created_at,
    )


# =========================
# MFA Admin Endpoints
# =========================


@router.delete(
    "/{user_id}/mfa",
    summary="Admin: force-disable MFA for a user",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("users.update"))],
)
async def admin_disable_user_mfa(
    user_id: UUID,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> None:
    """
    Force-disable MFA for a user (e.g., user lost their phone).

    Requires `users.update` permission. Audit logged.
    """
    mfa_service = MFAService(db)
    try:
        await mfa_service.admin_disable_mfa(
            target_user_id=user_id,
            tenant_id=UUID(tenant.tenant_id),
            admin_user_id=UUID(current_user["user_id"]),
        )
    except MFAError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.MFA_DISABLED,
        tenant_id=UUID(tenant.tenant_id),
        user_id=UUID(current_user["user_id"]),
        target_type="user",
        target_id=str(user_id),
        details={"action": "admin_force_disable"},
    )


# =========================
# Custom Role Assignment
# =========================


@router.post(
    "/{user_id}/custom-role",
    response_model=UserResponse,
    summary="Assign or clear a custom role for a user",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def assign_custom_role(
    user_id: UUID,
    data: CustomRoleAssign,
    tenant: RequestTenant,
    current_user: ValidatedUser,
    db: DatabaseSession,
):
    """
    Assign a custom role to a user, or clear it by passing null.

    When a custom role is assigned, the user's JWT permissions will be
    sourced from the custom role instead of the static ROLE_PERMISSIONS
    on their next token refresh or login.

    The custom role's base_role must match the user's role — a teacher
    cannot be assigned a role based on school_admin.

    Requires `users.update` permission.
    """
    service = CustomRoleService(db)
    try:
        user = await service.assign_role_to_user(
            user_id=user_id,
            custom_role_id=data.custom_role_id,
            tenant_id=tenant.tenant_id,
        )
    except CustomRoleError as e:
        status_map = {
            "not_found": 404,
            "base_role_mismatch": 400,
        }
        raise HTTPException(
            status_code=status_map.get(e.code, 400),
            detail=e.message,
        )

    # Audit trail
    audit = AuditService(db)
    await audit.log(
        event_type=AuditEventType.USER_ROLE_CHANGED,
        tenant_id=tenant.tenant_id,
        user_id=UUID(current_user["user_id"]),
        target_type="user",
        target_id=str(user_id),
        details={
            "action": "custom_role_assigned" if data.custom_role_id else "custom_role_cleared",
            "custom_role_id": str(data.custom_role_id) if data.custom_role_id else None,
        },
    )

    # Invalidate tokens so the user picks up the new custom role permissions
    try:
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_user_tokens(str(user_id))
        logger.info("user_tokens_blacklisted_on_custom_role_assign", user_id=str(user_id))
    except Exception:
        logger.warning("token_blacklist_failed_on_custom_role_assign", user_id=str(user_id))

    return _user_to_response(user)
