"""
SIMS Plus - Fee Structure Service

Business logic for fee structure management.
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.finance import FeeStructure, FeeItem


class FeeStructureService:
    """Service for managing fee structures."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_fee_structure(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        description: Optional[str] = None,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
        level: Optional[str] = None,
        level_category: Optional[str] = None,
        student_type: str = "all",
        is_active: bool = True,
        items: list[dict] = None,
    ) -> FeeStructure:
        """Create a new fee structure with optional items."""
        fee_structure = FeeStructure(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name,
            description=description,
            academic_year_id=academic_year_id,
            term_id=term_id,
            class_id=class_id,
            level=level,
            level_category=level_category,
            student_type=student_type,
            is_active=is_active,
        )
        self.db.add(fee_structure)
        await self.db.flush()

        # Add items if provided
        if items:
            for i, item_data in enumerate(items):
                fee_item = FeeItem(
                    tenant_id=tenant_id,
                    fee_structure_id=fee_structure.id,
                    fee_type_id=item_data.get("fee_type_id"),
                    name=item_data["name"],
                    description=item_data.get("description"),
                    amount=Decimal(str(item_data["amount"])),
                    is_optional=item_data.get("is_optional", False),
                    sequence=item_data.get("sequence", i),
                )
                self.db.add(fee_item)

        await self.db.flush()
        # Reload with relationships
        return await self.get_fee_structure(tenant_id, fee_structure.id, include_items=True)

    async def get_fee_structure(
        self, tenant_id: UUID, fee_structure_id: UUID, include_items: bool = True
    ) -> Optional[FeeStructure]:
        """Get fee structure by ID."""
        query = select(FeeStructure).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                FeeStructure.tenant_id == tenant_id,
                FeeStructure.id == fee_structure_id,
                FeeStructure.deleted_at.is_(None),
            )
        )
        if include_items:
            query = query.options(
                # Chain fee_type loading so _get_eligible_subtotal can filter by fee type
                selectinload(FeeStructure.items).joinedload(FeeItem.fee_type),
                joinedload(FeeStructure.academic_year),
                joinedload(FeeStructure.term),
                joinedload(FeeStructure.class_),
            )
        # populate_existing ensures that an already-loaded identity-mapped
        # instance gets its attributes (including relationships) refreshed
        # from the database. This prevents stale items after add/delete.
        query = query.execution_options(populate_existing=True)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_fee_structures(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[FeeStructure], int]:
        """List fee structures with filters."""
        query = select(FeeStructure).where(
            and_(
                FeeStructure.tenant_id == tenant_id,
                FeeStructure.deleted_at.is_(None),
            )
        )

        if school_id:
            query = query.where(FeeStructure.school_id == school_id)
        if academic_year_id:
            query = query.where(FeeStructure.academic_year_id == academic_year_id)
        if term_id:
            query = query.where(FeeStructure.term_id == term_id)
        if is_active is not None:
            query = query.where(FeeStructure.is_active == is_active)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results with eager loading
        query = query.options(
            selectinload(FeeStructure.items).joinedload(FeeItem.fee_type),
            joinedload(FeeStructure.academic_year),
            joinedload(FeeStructure.term),
            joinedload(FeeStructure.class_),
        ).order_by(desc(FeeStructure.created_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_fee_structure(
        self, tenant_id: UUID, fee_structure_id: UUID, items: list[dict] = None, **kwargs
    ) -> Optional[FeeStructure]:
        """Update fee structure, optionally syncing items."""
        fee_structure = await self.get_fee_structure(tenant_id, fee_structure_id, include_items=True)
        if not fee_structure:
            return None

        # Update fee structure fields
        for key, value in kwargs.items():
            if value is not None and hasattr(fee_structure, key):
                setattr(fee_structure, key, value)

        # Sync items if provided
        if items is not None:
            # Get existing item IDs
            existing_item_ids = {str(item.id) for item in fee_structure.items}
            new_item_ids = {str(item.get("id")) for item in items if item.get("id")}

            # Delete items not in the new list
            for item in fee_structure.items:
                if str(item.id) not in new_item_ids:
                    await self.db.delete(item)

            # Update or create items
            for i, item_data in enumerate(items):
                item_id = item_data.get("id")
                if item_id and str(item_id) in existing_item_ids:
                    # Update existing item
                    for existing_item in fee_structure.items:
                        if str(existing_item.id) == str(item_id):
                            existing_item.fee_type_id = item_data.get("fee_type_id")
                            existing_item.name = item_data["name"]
                            existing_item.description = item_data.get("description")
                            existing_item.amount = Decimal(str(item_data["amount"]))
                            existing_item.is_optional = item_data.get("is_optional", False)
                            existing_item.sequence = item_data.get("sequence", i)
                            break
                else:
                    # Create new item
                    new_item = FeeItem(
                        tenant_id=fee_structure.tenant_id,
                        fee_structure_id=fee_structure.id,
                        fee_type_id=item_data.get("fee_type_id"),
                        name=item_data["name"],
                        description=item_data.get("description"),
                        amount=Decimal(str(item_data["amount"])),
                        is_optional=item_data.get("is_optional", False),
                        sequence=item_data.get("sequence", i),
                    )
                    self.db.add(new_item)

        await self.db.flush()
        # Reload with relationships (populate_existing ensures fresh data)
        return await self.get_fee_structure(tenant_id, fee_structure_id, include_items=True)

    async def delete_fee_structure(self, tenant_id: UUID, fee_structure_id: UUID) -> bool:
        """Soft delete fee structure."""
        fee_structure = await self.get_fee_structure(tenant_id, fee_structure_id, include_items=False)
        if not fee_structure:
            return False

        fee_structure.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def add_fee_item(
        self,
        tenant_id: UUID,
        fee_structure_id: UUID,
        name: str,
        amount: Decimal,
        description: Optional[str] = None,
        fee_type_id: Optional[UUID] = None,
        is_optional: bool = False,
        sequence: int = 0,
    ) -> FeeItem:
        """Add item to fee structure."""
        fee_item = FeeItem(
            tenant_id=tenant_id,
            fee_structure_id=fee_structure_id,
            fee_type_id=fee_type_id,
            name=name,
            description=description,
            amount=amount,
            is_optional=is_optional,
            sequence=sequence,
        )
        self.db.add(fee_item)
        await self.db.flush()
        # Reload with fee_type relationship
        result = await self.db.execute(
            select(FeeItem)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    FeeItem.tenant_id == tenant_id,
                    FeeItem.id == fee_item.id,
                )
            )
            .options(joinedload(FeeItem.fee_type))
        )
        return result.scalar_one_or_none()

    async def update_fee_item(self, tenant_id: UUID, fee_item_id: UUID, **kwargs) -> Optional[FeeItem]:
        """Update fee item."""
        result = await self.db.execute(
            select(FeeItem)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    FeeItem.tenant_id == tenant_id,
                    FeeItem.id == fee_item_id,
                )
            )
            .options(joinedload(FeeItem.fee_type))
        )
        fee_item = result.scalar_one_or_none()
        if not fee_item:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(fee_item, key):
                setattr(fee_item, key, value)

        await self.db.flush()
        # Reload with fee_type relationship
        result = await self.db.execute(
            select(FeeItem)
            .where(
                and_(
                    FeeItem.tenant_id == tenant_id,
                    FeeItem.id == fee_item_id,
                )
            )
            .options(joinedload(FeeItem.fee_type))
        )
        return result.scalar_one_or_none()

    async def delete_fee_item(self, tenant_id: UUID, fee_item_id: UUID) -> bool:
        """Delete fee item."""
        result = await self.db.execute(
            select(FeeItem).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    FeeItem.tenant_id == tenant_id,
                    FeeItem.id == fee_item_id,
                )
            )
        )
        fee_item = result.scalar_one_or_none()
        if not fee_item:
            return False

        await self.db.delete(fee_item)
        await self.db.flush()
        return True

    async def copy_fee_structure(
        self,
        tenant_id: UUID,
        fee_structure_id: UUID,
        new_name: str,
        new_academic_year_id: Optional[UUID] = None,
        new_term_id: Optional[UUID] = None,
    ) -> Optional[FeeStructure]:
        """Copy fee structure with items to a new one."""
        original = await self.get_fee_structure(tenant_id, fee_structure_id, include_items=True)
        if not original:
            return None

        new_structure = FeeStructure(
            tenant_id=original.tenant_id,
            school_id=original.school_id,
            name=new_name,
            description=original.description,
            academic_year_id=new_academic_year_id or original.academic_year_id,
            term_id=new_term_id or original.term_id,
            class_id=original.class_id,
            level=original.level,
            is_active=True,
        )
        self.db.add(new_structure)
        await self.db.flush()

        # Copy items
        for item in original.items:
            new_item = FeeItem(
                tenant_id=original.tenant_id,
                fee_structure_id=new_structure.id,
                name=item.name,
                description=item.description,
                amount=item.amount,
                is_optional=item.is_optional,
                sequence=item.sequence,
            )
            self.db.add(new_item)

        await self.db.flush()
        # Reload with relationships
        return await self.get_fee_structure(tenant_id, new_structure.id, include_items=True)
