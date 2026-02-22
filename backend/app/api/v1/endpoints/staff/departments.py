"""
SIMS Plus - Department Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.staff import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentListResponse,
)
from app.services.staff import DepartmentService, StaffServiceError

router = APIRouter()


# =========================
# Department Endpoints
# =========================
# NOTE: These must be defined BEFORE /{staff_id} routes to avoid route conflicts


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create department",
    dependencies=[Depends(require_permissions("staff.create"))],
)
async def create_department(
    data: DepartmentCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> DepartmentResponse:
    """Create a new department."""
    service = DepartmentService(db)

    try:
        department = await service.create_department(
            tenant_id=tenant.tenant_id,
            name=data.name,
            code=data.code,
            description=data.description,
            head_id=data.head_id,
        )

        # Get staff count
        staff_count = await service.get_department_staff_count(
            tenant.tenant_id, department.id
        )

        return DepartmentResponse(
            id=department.id,
            name=department.name,
            code=department.code,
            description=department.description,
            head_id=department.head_id,
            created_at=department.created_at,
            updated_at=department.updated_at,
            staff_count=staff_count,
        )
    except StaffServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/departments",
    response_model=list[DepartmentListResponse],
    summary="List departments",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def list_departments(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    search: Optional[str] = Query(None, description="Search by name or code"),
) -> list[DepartmentListResponse]:
    """List all departments."""
    service = DepartmentService(db)
    departments = await service.list_departments(tenant.tenant_id, search)

    result = []
    for dept in departments:
        staff_count = await service.get_department_staff_count(
            tenant.tenant_id, dept.id
        )
        result.append(
            DepartmentListResponse(
                id=dept.id,
                name=dept.name,
                code=dept.code,
                description=dept.description,
                staff_count=staff_count,
            )
        )
    return result


@router.get(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
    summary="Get department",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_department(
    department_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> DepartmentResponse:
    """Get a department by ID."""
    service = DepartmentService(db)
    department = await service.get_department(tenant.tenant_id, department_id)

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    staff_count = await service.get_department_staff_count(
        tenant.tenant_id, department.id
    )

    return DepartmentResponse(
        id=department.id,
        name=department.name,
        code=department.code,
        description=department.description,
        head_id=department.head_id,
        created_at=department.created_at,
        updated_at=department.updated_at,
        staff_count=staff_count,
    )


@router.put(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
    summary="Update department",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def update_department(
    department_id: UUID,
    data: DepartmentUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> DepartmentResponse:
    """Update a department."""
    service = DepartmentService(db)

    try:
        department = await service.update_department(
            tenant_id=tenant.tenant_id,
            department_id=department_id,
            name=data.name,
            code=data.code,
            description=data.description,
            head_id=data.head_id,
        )

        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found",
            )

        staff_count = await service.get_department_staff_count(
            tenant.tenant_id, department.id
        )

        return DepartmentResponse(
            id=department.id,
            name=department.name,
            code=department.code,
            description=department.description,
            head_id=department.head_id,
            created_at=department.created_at,
            updated_at=department.updated_at,
            staff_count=staff_count,
        )
    except StaffServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/departments/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete department",
    dependencies=[Depends(require_permissions("staff.delete"))],
)
async def delete_department(
    department_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a department."""
    service = DepartmentService(db)
    deleted = await service.delete_department(tenant.tenant_id, department_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
