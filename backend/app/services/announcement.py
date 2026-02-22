"""
SIMS Plus - Announcement Service

Business logic for managing school announcements.
Used by admin/teacher endpoints to create/publish/manage announcements,
and by the parent portal to read targeted announcements.
"""

import math
from datetime import UTC, datetime
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.parent import (
    Announcement,
    AnnouncementPriority,
    AnnouncementTarget,
)
from app.models.user import User
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


class AnnouncementServiceError(Exception):
    """Base exception for announcement service errors."""

    def __init__(self, message: str, code: str = "announcement_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class AnnouncementService:
    """Service for managing school announcements.

    Used by admin/teacher endpoints to create/publish,
    and by parent portal to read targeted announcements.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_announcement(
        self,
        tenant_id: UUID,
        school_id: UUID,
        author_id: UUID,
        data: "AnnouncementCreate",
    ) -> Announcement:
        """Create a new announcement.

        Announcements start as drafts (published_at=NULL) unless the caller
        explicitly sets published_at later via publish_announcement().
        """
        # Validate targeting constraints before persisting
        self._validate_targeting(
            target_audience=data.target_audience,
            target_class_id=data.target_class_id,
            target_house_id=data.target_house_id,
        )

        announcement = Announcement(
            tenant_id=tenant_id,
            school_id=school_id,
            author_id=author_id,
            title=data.title,
            content=data.content,
            target_audience=AnnouncementTarget(data.target_audience.value),
            target_class_id=data.target_class_id,
            target_house_id=data.target_house_id,
            priority=AnnouncementPriority(data.priority.value),
            expires_at=data.expires_at,
            is_pinned=data.is_pinned,
            attachment_url=data.attachment_url,
        )
        self.db.add(announcement)
        await self.db.flush()
        await self.db.refresh(announcement)

        logger.info(
            "announcement_created",
            announcement_id=str(announcement.id),
            tenant_id=str(tenant_id),
            target_audience=announcement.target_audience.value,
        )
        return announcement

    async def update_announcement(
        self,
        tenant_id: UUID,
        announcement_id: UUID,
        data: "AnnouncementUpdate",
    ) -> Announcement:
        """Update an announcement. Only drafts (unpublished) can be edited."""
        announcement = await self._get_announcement_or_raise(tenant_id, announcement_id)

        # Only allow editing unpublished (draft) announcements
        if announcement.published_at is not None:
            raise AnnouncementServiceError(
                "Published announcements cannot be edited. "
                "Create a new announcement instead.",
                code="already_published",
            )

        # If audience targeting is changing, validate the new combination
        new_audience = data.target_audience or announcement.target_audience
        new_class_id = data.target_class_id if data.target_class_id is not None else announcement.target_class_id
        new_house_id = data.target_house_id if data.target_house_id is not None else announcement.target_house_id

        # Need to convert schema enum to model enum if the audience is from the update payload
        if data.target_audience is not None:
            new_audience = AnnouncementTarget(data.target_audience.value)

        self._validate_targeting(
            target_audience=new_audience,
            target_class_id=new_class_id,
            target_house_id=new_house_id,
        )

        # Apply only the fields that were provided
        if data.title is not None:
            announcement.title = data.title
        if data.content is not None:
            announcement.content = data.content
        if data.target_audience is not None:
            announcement.target_audience = AnnouncementTarget(data.target_audience.value)
        if data.target_class_id is not None:
            announcement.target_class_id = data.target_class_id
        if data.target_house_id is not None:
            announcement.target_house_id = data.target_house_id
        if data.priority is not None:
            announcement.priority = AnnouncementPriority(data.priority.value)
        if data.expires_at is not None:
            announcement.expires_at = data.expires_at
        if data.is_pinned is not None:
            announcement.is_pinned = data.is_pinned
        if data.attachment_url is not None:
            announcement.attachment_url = data.attachment_url

        await self.db.flush()
        await self.db.refresh(announcement)

        logger.info(
            "announcement_updated",
            announcement_id=str(announcement.id),
            tenant_id=str(tenant_id),
        )
        return announcement

    async def publish_announcement(
        self,
        tenant_id: UUID,
        announcement_id: UUID,
    ) -> Announcement:
        """Publish an announcement by setting published_at to now.

        Only unpublished (draft) announcements can be published.
        After publishing, the announcement becomes visible to the targeted audience.
        """
        announcement = await self._get_announcement_or_raise(tenant_id, announcement_id)

        if announcement.published_at is not None:
            raise AnnouncementServiceError(
                "Announcement is already published",
                code="already_published",
            )

        announcement.published_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(announcement)

        logger.info(
            "announcement_published",
            announcement_id=str(announcement.id),
            tenant_id=str(tenant_id),
            target_audience=announcement.target_audience.value,
        )

        # Best-effort: trigger parent notifications asynchronously
        # This is a hook point for NotificationService integration.
        # Actual notification dispatch is handled by the caller or a background task
        # to avoid coupling announcement publishing to notification delivery.

        return announcement

    async def get_announcement(
        self,
        tenant_id: UUID,
        announcement_id: UUID,
    ) -> Announcement:
        """Get a single announcement by ID with author loaded."""
        # Defense-in-depth: always filter by tenant_id even though RLS handles isolation
        stmt = (
            select(Announcement)
            .where(
                and_(
                    Announcement.tenant_id == tenant_id,
                    Announcement.id == announcement_id,
                    Announcement.deleted_at.is_(None),
                )
            )
            .options(joinedload(Announcement.author))
        )
        result = await self.db.execute(stmt)
        announcement = result.scalar_one_or_none()
        if not announcement:
            raise AnnouncementServiceError(
                "Announcement not found",
                code="not_found",
            )
        return announcement

    async def list_announcements(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        include_drafts: bool = False,
        search: Optional[str] = None,
        priority: Optional[str] = None,
        target_audience: Optional[str] = None,
    ) -> dict:
        """List announcements with pagination (admin/staff view).

        Args:
            tenant_id: Tenant scope for defense-in-depth
            page: Current page (1-indexed)
            page_size: Items per page
            include_drafts: If True, include unpublished announcements
            search: Optional text search across title and content
            priority: Optional filter by priority level
            target_audience: Optional filter by target audience
        """
        conditions = [
            Announcement.tenant_id == tenant_id,
            Announcement.deleted_at.is_(None),
        ]

        if not include_drafts:
            conditions.append(Announcement.published_at.isnot(None))

        if priority:
            conditions.append(
                Announcement.priority == AnnouncementPriority(priority)
            )

        if target_audience:
            conditions.append(
                Announcement.target_audience == AnnouncementTarget(target_audience)
            )

        if search:
            safe_search = escape_ilike(search)
            search_pattern = f"%{safe_search}%"
            conditions.append(
                or_(
                    Announcement.title.ilike(search_pattern),
                    Announcement.content.ilike(search_pattern),
                )
            )

        # Count total matching records
        count_stmt = select(func.count()).select_from(
            select(Announcement.id).where(and_(*conditions)).subquery()
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        # Get paginated results: pinned first, then by created_at desc
        stmt = (
            select(Announcement)
            .where(and_(*conditions))
            .options(joinedload(Announcement.author))
            .order_by(
                Announcement.is_pinned.desc(),
                Announcement.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().unique().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def delete_announcement(
        self,
        tenant_id: UUID,
        announcement_id: UUID,
    ) -> None:
        """Soft delete an announcement."""
        announcement = await self._get_announcement_or_raise(tenant_id, announcement_id)

        announcement.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "announcement_deleted",
            announcement_id=str(announcement.id),
            tenant_id=str(tenant_id),
        )

    async def get_announcements_for_parent(
        self,
        tenant_id: UUID,
        user_id: UUID,
        children_class_ids: list[UUID],
        children_house_ids: list[UUID],
        has_boarder: bool,
        has_transport: bool,
    ) -> list[Announcement]:
        """Get announcements visible to a specific parent based on targeting.

        Targeting logic:
        - all_parents: always included
        - specific_class: included if target_class_id matches one of the parent's children's classes
        - specific_house: included if target_house_id matches one of the parent's children's houses
        - boarding_parents: included if the parent has at least one child who is a boarder
        - transport_parents: included if the parent has at least one child using transport

        Results are sorted with pinned announcements first, then by published_at descending.
        Only published, non-expired, non-deleted announcements are returned.
        """
        now = datetime.now(UTC)

        # Base conditions: published, not soft-deleted, and not expired
        base_conditions = [
            Announcement.tenant_id == tenant_id,
            Announcement.deleted_at.is_(None),
            Announcement.published_at.isnot(None),
            Announcement.published_at <= now,
        ]

        # Build audience filter as OR conditions
        audience_filters = [
            # All parents always see "all_parents" announcements
            Announcement.target_audience == AnnouncementTarget.ALL_PARENTS,
        ]

        # Class-targeted announcements: include if child is in that class
        if children_class_ids:
            audience_filters.append(
                and_(
                    Announcement.target_audience == AnnouncementTarget.SPECIFIC_CLASS,
                    Announcement.target_class_id.in_(children_class_ids),
                )
            )

        # House-targeted announcements: include if child is in that house
        if children_house_ids:
            audience_filters.append(
                and_(
                    Announcement.target_audience == AnnouncementTarget.SPECIFIC_HOUSE,
                    Announcement.target_house_id.in_(children_house_ids),
                )
            )

        # Boarding-specific announcements
        if has_boarder:
            audience_filters.append(
                Announcement.target_audience == AnnouncementTarget.BOARDING_PARENTS,
            )

        # Transport-specific announcements
        if has_transport:
            audience_filters.append(
                Announcement.target_audience == AnnouncementTarget.TRANSPORT_PARENTS,
            )

        # Exclude expired announcements (NULL expires_at means never expires)
        expiry_condition = or_(
            Announcement.expires_at.is_(None),
            Announcement.expires_at > now,
        )

        stmt = (
            select(Announcement)
            .where(
                and_(
                    *base_conditions,
                    expiry_condition,
                    or_(*audience_filters),
                )
            )
            .options(joinedload(Announcement.author))
            .order_by(
                # Pinned announcements always appear first
                Announcement.is_pinned.desc(),
                Announcement.published_at.desc(),
            )
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    # ==========================
    # Private helpers
    # ==========================

    async def _get_announcement_or_raise(
        self,
        tenant_id: UUID,
        announcement_id: UUID,
    ) -> Announcement:
        """Fetch an announcement by ID or raise AnnouncementServiceError.

        Uses tenant_id filter for defense-in-depth on top of RLS.
        """
        stmt = select(Announcement).where(
            and_(
                Announcement.tenant_id == tenant_id,
                Announcement.id == announcement_id,
                Announcement.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        announcement = result.scalar_one_or_none()
        if not announcement:
            raise AnnouncementServiceError(
                "Announcement not found",
                code="not_found",
            )
        return announcement

    @staticmethod
    def _validate_targeting(
        target_audience,
        target_class_id: Optional[UUID],
        target_house_id: Optional[UUID],
    ) -> None:
        """Validate that targeting fields are consistent with the audience type.

        Raises AnnouncementServiceError if targeting is invalid.
        """
        # Convert schema enum to model enum value string for comparison
        audience_value = (
            target_audience.value
            if hasattr(target_audience, "value")
            else str(target_audience)
        )

        if audience_value == AnnouncementTarget.SPECIFIC_CLASS.value and target_class_id is None:
            raise AnnouncementServiceError(
                "target_class_id is required when target_audience is 'specific_class'",
                code="missing_target_class",
            )

        if audience_value == AnnouncementTarget.SPECIFIC_HOUSE.value and target_house_id is None:
            raise AnnouncementServiceError(
                "target_house_id is required when target_audience is 'specific_house'",
                code="missing_target_house",
            )
