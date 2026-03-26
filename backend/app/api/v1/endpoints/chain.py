"""
SIMS Plus - School Chain Endpoints

Endpoints for managing school chains: list/add/update schools,
assign users to schools, get chain overview and dashboard,
list accessible schools for the switcher, and list chain users.

IMPORTANT: Do NOT add `from __future__ import annotations` to this file.
It breaks 204 No Content responses in FastAPI.

These endpoints require chain_admin or platform_admin permissions.

Route ordering note: static paths (/accessible, /overview, /dashboard,
/users) are registered BEFORE parameterised paths (/schools/{school_id})
so FastAPI does not try to parse path literals as UUID parameters.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    DatabaseSession,
    ValidatedUser,
    require_permissions,
)
from app.services.token_blacklist import get_token_blacklist_service
from app.schemas.chain import (
    AccessibleSchoolResponse,
    ChainDashboardResponse,
    ChainOverview,
    ChainSchoolCreate,
    ChainSchoolListResponse,
    ChainSchoolMetrics,
    ChainSchoolResponse,
    ChainSchoolUpdate,
    ChainUserListResponse,
    ChainUserResponse,
    ChainUserSchoolAccess,
    UserSchoolAssign,
    UserSchoolListResponse,
    UserSchoolResponse,
)
from app.services.cache import CacheService
from app.services.chain import ChainService
from app.utils.cache_keys import CacheKeys

logger = structlog.get_logger()

router = APIRouter()


# =========================
# Accessible Schools (Switcher)
# =========================


@router.get(
    "/accessible",
    response_model=list[AccessibleSchoolResponse],
    summary="List accessible schools for current user",
    dependencies=[Depends(require_permissions("schools.read"))],
)
async def list_accessible_schools(
    request: Request,
    db: DatabaseSession,
    user: ValidatedUser,
) -> list[AccessibleSchoolResponse]:
    """Get schools the current user can access (for switcher dropdown).

    Results are cached in Redis for 5 minutes to reduce DB load since the
    school switcher fires on every page load for chain admins.  Cache is
    invalidated when user-school assignments change (assign / remove).
    """
    tenant_id = UUID(user["tenant_id"])
    user_id = UUID(user["user_id"])

    redis_client = getattr(request.app.state, "redis", None)
    cache = CacheService(redis_client)
    cache_key = CacheKeys.chain_accessible_schools(
        str(tenant_id), str(user_id)
    )

    # Try cache first (graceful degradation -- CacheService handles errors)
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return [AccessibleSchoolResponse(**item) for item in cached]

    # Cache miss -- query DB
    service = ChainService(db)
    schools = await service.get_accessible_schools(user_id, tenant_id)
    response_data = [
        AccessibleSchoolResponse(
            id=s.id, name=s.name, code=s.code, logo_url=s.logo_url
        )
        for s in schools
    ]

    # Populate cache for subsequent requests
    await cache.set_json(
        cache_key,
        [r.model_dump(mode="json") for r in response_data],
        CacheKeys.CHAIN_ACCESSIBLE_TTL,
    )

    return response_data


# =========================
# Chain Overview
# =========================


@router.get(
    "/overview",
    response_model=ChainOverview,
    summary="Get chain overview",
    dependencies=[Depends(require_permissions("schools.read"))],
)
async def get_chain_overview(
    db: DatabaseSession,
    user: ValidatedUser,
) -> ChainOverview:
    """Get high-level overview of the school chain."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    try:
        overview = await service.get_chain_overview(tenant_id)
    except ChainService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    # Build school responses with counts
    school_responses = [
        ChainSchoolResponse(
            id=sd["school"].id,
            tenant_id=sd["school"].tenant_id,
            name=sd["school"].name,
            code=sd["school"].code,
            address=sd["school"].address,
            phone=sd["school"].phone,
            email=sd["school"].email,
            logo_url=sd["school"].logo_url,
            student_id_prefix=sd["school"].student_id_prefix,
            student_count=sd["student_count"],
            staff_count=sd["staff_count"],
            created_at=sd["school"].created_at,
            updated_at=sd["school"].updated_at,
        )
        for sd in overview["schools_data"]
    ]

    return ChainOverview(
        tenant_id=overview["tenant_id"],
        tenant_name=overview["tenant_name"],
        total_schools=overview["total_schools"],
        total_students=overview["total_students"],
        total_staff=overview["total_staff"],
        schools=school_responses,
    )


# =========================
# Chain Dashboard
# =========================


@router.get(
    "/dashboard",
    response_model=ChainDashboardResponse,
    summary="Get chain dashboard with metrics",
    dependencies=[Depends(require_permissions("schools.read"))],
)
async def get_chain_dashboard(
    db: DatabaseSession,
    user: ValidatedUser,
) -> ChainDashboardResponse:
    """Get chain dashboard with financial and attendance metrics per school."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    try:
        data = await service.get_chain_dashboard(tenant_id)
    except ChainService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return ChainDashboardResponse(
        total_schools=data["total_schools"],
        total_students=data["total_students"],
        total_staff=data["total_staff"],
        overall_attendance_rate=data["overall_attendance_rate"],
        total_revenue=data["total_revenue"],
        total_outstanding=data["total_outstanding"],
        schools=[ChainSchoolMetrics(**s) for s in data["schools"]],
    )


# =========================
# Chain Users
# =========================


@router.get(
    "/users",
    response_model=ChainUserListResponse,
    summary="List chain users",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def list_chain_users(
    db: DatabaseSession,
    user: ValidatedUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    school_id: UUID | None = None,
) -> ChainUserListResponse:
    """List users in the chain with their school assignments."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    data = await service.list_chain_users(
        tenant_id,
        page=page,
        page_size=page_size,
        search=search,
        school_id=school_id,
    )

    items = []
    for u in data["users"]:
        accesses = data["accesses_by_user"].get(u.id, [])
        items.append(
            ChainUserResponse(
                id=u.id,
                email=u.email,
                first_name=u.first_name,
                last_name=u.last_name,
                role=u.role.value,
                status=u.status.value,
                school_accesses=[
                    ChainUserSchoolAccess(
                        id=a.id,
                        school_id=a.school_id,
                        school_name=a.school.name if a.school else "Unknown",
                        school_code=a.school.code if a.school else None,
                        role_at_school=a.role_at_school,
                        is_primary=a.is_primary,
                    )
                    for a in accesses
                ],
                created_at=u.created_at,
                updated_at=u.updated_at,
            )
        )

    return ChainUserListResponse(
        items=items,
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
        total_pages=data["total_pages"],
    )


# =========================
# School Management
# =========================


@router.get(
    "/schools",
    response_model=ChainSchoolListResponse,
    summary="List chain schools",
    dependencies=[Depends(require_permissions("schools.read"))],
)
async def list_chain_schools(
    db: DatabaseSession,
    user: ValidatedUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
) -> ChainSchoolListResponse:
    """List all schools in the chain with pagination and optional search."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    schools_result = await service.list_schools(
        tenant_id, page=page, page_size=page_size, search=search
    )

    items = [
        ChainSchoolResponse(
            id=sd["school"].id,
            tenant_id=sd["school"].tenant_id,
            name=sd["school"].name,
            code=sd["school"].code,
            address=sd["school"].address,
            phone=sd["school"].phone,
            email=sd["school"].email,
            logo_url=sd["school"].logo_url,
            student_id_prefix=sd["school"].student_id_prefix,
            student_count=sd["student_count"],
            staff_count=sd["staff_count"],
            created_at=sd["school"].created_at,
            updated_at=sd["school"].updated_at,
        )
        for sd in schools_result["items"]
    ]

    return ChainSchoolListResponse(items=items, total=schools_result["total"])


@router.post(
    "/schools",
    response_model=ChainSchoolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add school to chain",
    dependencies=[Depends(require_permissions("schools.create"))],
)
async def add_chain_school(
    data: ChainSchoolCreate,
    db: DatabaseSession,
    user: ValidatedUser,
) -> ChainSchoolResponse:
    """Add a new school to the chain."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    try:
        school = await service.add_school(
            tenant_id=tenant_id,
            name=data.name,
            code=data.code,
            address=data.address,
            phone=data.phone,
            email=data.email,
            student_id_prefix=data.student_id_prefix,
        )
    except ChainService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    return ChainSchoolResponse(
        id=school.id,
        tenant_id=school.tenant_id,
        name=school.name,
        code=school.code,
        address=school.address,
        phone=school.phone,
        email=school.email,
        logo_url=school.logo_url,
        student_id_prefix=school.student_id_prefix,
        student_count=0,
        staff_count=0,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )


@router.get(
    "/schools/{school_id}",
    response_model=ChainSchoolResponse,
    summary="Get chain school details",
    dependencies=[Depends(require_permissions("schools.read"))],
)
async def get_chain_school(
    school_id: UUID,
    db: DatabaseSession,
    user: ValidatedUser,
) -> ChainSchoolResponse:
    """Get details for a single school in the chain."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    try:
        school = await service.get_school(tenant_id, school_id)
        student_count, staff_count = await service.get_school_counts(school_id, tenant_id)
    except ChainService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return ChainSchoolResponse(
        id=school.id,
        tenant_id=school.tenant_id,
        name=school.name,
        code=school.code,
        address=school.address,
        phone=school.phone,
        email=school.email,
        logo_url=school.logo_url,
        student_id_prefix=school.student_id_prefix,
        student_count=student_count,
        staff_count=staff_count,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )


@router.put(
    "/schools/{school_id}",
    response_model=ChainSchoolResponse,
    summary="Update chain school",
    dependencies=[Depends(require_permissions("schools.update"))],
)
async def update_chain_school(
    school_id: UUID,
    data: ChainSchoolUpdate,
    db: DatabaseSession,
    user: ValidatedUser,
) -> ChainSchoolResponse:
    """Update a school in the chain."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    try:
        school = await service.update_school(
            tenant_id=tenant_id,
            school_id=school_id,
            name=data.name,
            address=data.address,
            phone=data.phone,
            email=data.email,
            student_id_prefix=data.student_id_prefix,
        )
        student_count, staff_count = await service.get_school_counts(school_id, tenant_id)
    except ChainService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    return ChainSchoolResponse(
        id=school.id,
        tenant_id=school.tenant_id,
        name=school.name,
        code=school.code,
        address=school.address,
        phone=school.phone,
        email=school.email,
        logo_url=school.logo_url,
        student_id_prefix=school.student_id_prefix,
        student_count=student_count,
        staff_count=staff_count,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )


# =========================
# User-School Assignment
# =========================


@router.post(
    "/user-schools",
    response_model=UserSchoolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign user to school",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def assign_user_to_school(
    data: UserSchoolAssign,
    request: Request,
    db: DatabaseSession,
    user: ValidatedUser,
) -> UserSchoolResponse:
    """Grant a user access to a school in the chain."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    try:
        user_school = await service.assign_user_to_school(
            tenant_id=tenant_id,
            user_id=data.user_id,
            school_id=data.school_id,
            role_at_school=data.role_at_school,
            is_primary=data.is_primary,
        )
    except ChainService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    # Invalidate the affected user's accessible-schools cache so the
    # switcher dropdown reflects the new assignment immediately.
    redis_client = getattr(request.app.state, "redis", None)
    cache = CacheService(redis_client)
    await cache.invalidate_key(
        CacheKeys.chain_accessible_schools(str(tenant_id), str(data.user_id))
    )

    # Invalidate tokens so the user's accessible_school_ids JWT claim is refreshed
    try:
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_user_tokens(str(data.user_id))
        logger.info("user_tokens_blacklisted_on_school_assign", user_id=str(data.user_id), school_id=str(data.school_id))
    except Exception:
        logger.warning("token_blacklist_failed_on_school_assign", user_id=str(data.user_id))

    return UserSchoolResponse(
        id=user_school.id,
        tenant_id=user_school.tenant_id,
        user_id=user_school.user_id,
        school_id=user_school.school_id,
        role_at_school=user_school.role_at_school,
        is_primary=user_school.is_primary,
        is_active=user_school.is_active,
        created_at=user_school.created_at,
        updated_at=user_school.updated_at,
    )


@router.delete(
    "/user-schools/{user_id}/{school_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove user from school",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def remove_user_from_school(
    user_id: UUID,
    school_id: UUID,
    request: Request,
    db: DatabaseSession,
    user: ValidatedUser,
) -> None:
    """Remove a user's access to a school (soft-disable)."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    try:
        await service.remove_user_from_school(
            tenant_id=tenant_id,
            user_id=user_id,
            school_id=school_id,
        )
    except ChainService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    # Invalidate the affected user's accessible-schools cache so the
    # switcher dropdown reflects the removal immediately.
    redis_client = getattr(request.app.state, "redis", None)
    cache = CacheService(redis_client)
    await cache.invalidate_key(
        CacheKeys.chain_accessible_schools(str(tenant_id), str(user_id))
    )

    # Invalidate tokens so the user's accessible_school_ids JWT claim is refreshed
    try:
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_user_tokens(str(user_id))
        logger.info("user_tokens_blacklisted_on_school_remove", user_id=str(user_id), school_id=str(school_id))
    except Exception:
        logger.warning("token_blacklist_failed_on_school_remove", user_id=str(user_id))


@router.get(
    "/user-schools/{user_id}",
    response_model=UserSchoolListResponse,
    summary="List user's schools",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def list_user_schools(
    user_id: UUID,
    db: DatabaseSession,
    user: ValidatedUser,
) -> UserSchoolListResponse:
    """List all schools a user has access to."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    user_schools = await service.list_user_schools(tenant_id, user_id)

    items = [
        UserSchoolResponse(
            id=us.id,
            tenant_id=us.tenant_id,
            user_id=us.user_id,
            school_id=us.school_id,
            role_at_school=us.role_at_school,
            is_primary=us.is_primary,
            is_active=us.is_active,
            school_name=us.school.name if us.school else None,
            created_at=us.created_at,
            updated_at=us.updated_at,
        )
        for us in user_schools
    ]

    return UserSchoolListResponse(items=items, total=len(items))


@router.get(
    "/schools/{school_id}/users",
    response_model=UserSchoolListResponse,
    summary="List school's users",
    dependencies=[Depends(require_permissions("users.read"))],
)
async def list_school_users(
    school_id: UUID,
    db: DatabaseSession,
    user: ValidatedUser,
) -> UserSchoolListResponse:
    """List all users assigned to a specific school."""
    tenant_id = UUID(user["tenant_id"])
    service = ChainService(db)
    user_schools = await service.list_school_users(tenant_id, school_id)

    items = [
        UserSchoolResponse(
            id=us.id,
            tenant_id=us.tenant_id,
            user_id=us.user_id,
            school_id=us.school_id,
            role_at_school=us.role_at_school,
            is_primary=us.is_primary,
            is_active=us.is_active,
            user_email=us.user.email if us.user else None,
            created_at=us.created_at,
            updated_at=us.updated_at,
        )
        for us in user_schools
    ]

    return UserSchoolListResponse(items=items, total=len(items))
