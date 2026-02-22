"""
SIMS Plus - Fee Type Service

Business logic for fee type management.
"""

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import FeeType
from app.services.finance._shared import FinanceServiceError
from app.utils.sanitize import escape_ilike


class FeeTypeService:
    """Service for managing fee types."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_fee_type(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_active: bool = True,
    ) -> FeeType:
        """Create a new fee type."""
        # Check for duplicate name (case insensitive)
        existing = await self.db.execute(
            select(FeeType).where(
                and_(
                    FeeType.tenant_id == tenant_id,
                    func.lower(FeeType.name) == name.lower(),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise FinanceServiceError(
                f"Fee type '{name}' already exists",
                "duplicate_fee_type",
            )

        fee_type = FeeType(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name,
            description=description,
            category=category,
            is_active=is_active,
        )
        self.db.add(fee_type)
        await self.db.flush()
        await self.db.refresh(fee_type)
        return fee_type

    async def get_fee_type(self, tenant_id: UUID, fee_type_id: UUID) -> Optional[FeeType]:
        """Get a fee type by ID."""
        result = await self.db.execute(
            select(FeeType).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    FeeType.tenant_id == tenant_id,
                    FeeType.id == fee_type_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_fee_type(
        self,
        tenant_id: UUID,
        fee_type_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[FeeType]:
        """Update a fee type."""
        fee_type = await self.get_fee_type(tenant_id, fee_type_id)
        if not fee_type:
            return None

        if name is not None:
            # Check for duplicate name
            existing = await self.db.execute(
                select(FeeType).where(
                    and_(
                        FeeType.tenant_id == fee_type.tenant_id,
                        func.lower(FeeType.name) == name.lower(),
                        FeeType.id != fee_type_id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise FinanceServiceError(
                    f"Fee type '{name}' already exists",
                    "duplicate_fee_type",
                )
            fee_type.name = name

        if description is not None:
            fee_type.description = description
        if category is not None:
            fee_type.category = category
        if is_active is not None:
            fee_type.is_active = is_active

        await self.db.flush()
        await self.db.refresh(fee_type)
        return fee_type

    async def delete_fee_type(self, tenant_id: UUID, fee_type_id: UUID) -> bool:
        """Delete a fee type."""
        fee_type = await self.get_fee_type(tenant_id, fee_type_id)
        if not fee_type:
            return False

        await self.db.delete(fee_type)
        await self.db.flush()
        return True

    async def list_fee_types(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[FeeType], int]:
        """List fee types with optional filtering."""
        query = select(FeeType).where(FeeType.tenant_id == tenant_id)

        if search:
            # Escape ILIKE wildcards to prevent wildcard injection
            safe_search = f"%{escape_ilike(search)}%"
            query = query.where(
                or_(
                    FeeType.name.ilike(safe_search),
                    FeeType.description.ilike(safe_search),
                )
            )
        if category:
            query = query.where(FeeType.category == category)
        if is_active is not None:
            query = query.where(FeeType.is_active == is_active)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(FeeType.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def search_fee_types(
        self,
        tenant_id: UUID,
        query: str,
        limit: int = 10,
    ) -> Sequence[FeeType]:
        """Quick search for fee types (for autocomplete)."""
        stmt = (
            select(FeeType)
            .where(
                and_(
                    FeeType.tenant_id == tenant_id,
                    FeeType.is_active == True,
                    FeeType.name.ilike(f"%{escape_ilike(query)}%"),
                )
            )
            .order_by(FeeType.name)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
