"""
SIMS Plus - Department Service

Department CRUD operations.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import Department, Staff
from app.utils.sanitize import escape_ilike

from app.services.staff._shared import StaffServiceError


class DepartmentService:
    """Service for managing departments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_department(
        self,
        tenant_id: UUID,
        name: str,
        code: Optional[str] = None,
        description: Optional[str] = None,
        head_id: Optional[UUID] = None,
    ) -> Department:
        """Create a new department."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(Department).where(
                and_(
                    Department.tenant_id == tenant_id,
                    Department.name == name,
                    Department.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StaffServiceError(
                f"Department '{name}' already exists",
                code="duplicate_department",
            )

        department = Department(
            tenant_id=tenant_id,
            name=name,
            code=code,
            description=description,
            head_id=head_id,
        )
        self.db.add(department)
        await self.db.flush()
        await self.db.refresh(department)
        return department

    async def get_department(
        self, tenant_id: UUID, department_id: UUID
    ) -> Optional[Department]:
        """Get a department by ID."""
        result = await self.db.execute(
            select(Department).where(
                and_(
                    Department.tenant_id == tenant_id,
                    Department.id == department_id,
                    Department.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_departments(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
    ) -> Sequence[Department]:
        """List all departments."""
        conditions = [
            Department.tenant_id == tenant_id,
            Department.deleted_at.is_(None),
        ]

        if search:
            # Escape ILIKE wildcards to prevent wildcard injection
            safe_search = f"%{escape_ilike(search)}%"
            conditions.append(
                or_(
                    Department.name.ilike(safe_search),
                    Department.code.ilike(safe_search),
                )
            )

        result = await self.db.execute(
            select(Department)
            .where(and_(*conditions))
            .order_by(Department.name)
        )
        return result.scalars().all()

    async def update_department(
        self,
        tenant_id: UUID,
        department_id: UUID,
        name: Optional[str] = None,
        code: Optional[str] = None,
        description: Optional[str] = None,
        head_id: Optional[UUID] = None,
    ) -> Optional[Department]:
        """Update a department."""
        department = await self.get_department(tenant_id, department_id)
        if not department:
            return None

        if name is not None:
            # Check for duplicate name
            existing = await self.db.execute(
                select(Department).where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Department.name == name,
                        Department.id != department_id,
                        Department.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise StaffServiceError(
                    f"Department '{name}' already exists",
                    code="duplicate_department",
                )
            department.name = name

        if code is not None:
            department.code = code
        if description is not None:
            department.description = description
        if head_id is not None:
            department.head_id = head_id

        department.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(department)
        return department

    async def delete_department(
        self, tenant_id: UUID, department_id: UUID
    ) -> bool:
        """Soft delete a department."""
        department = await self.get_department(tenant_id, department_id)
        if not department:
            return False

        department.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def get_department_staff_count(
        self, tenant_id: UUID, department_id: UUID
    ) -> int:
        """Get the count of staff in a department."""
        result = await self.db.execute(
            select(func.count(Staff.id)).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.department_id == department_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        return result.scalar() or 0
