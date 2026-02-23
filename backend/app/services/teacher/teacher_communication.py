"""
SIMS Plus - Teacher Communication Service

Allows teachers to send class-wide announcements (broadcasts) to parents
of students in their assigned classes. Uses the existing Announcement model
with target_audience=SPECIFIC_CLASS.
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parent import Announcement, AnnouncementPriority, AnnouncementTarget
from app.models.school import School
from app.models.user import User

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherCommunicationService:
    """
    Class broadcast communication for teachers.

    Teachers can send announcements targeted at a specific class
    (target_audience=specific_class) through the existing Announcement
    model, reusing the parent portal's announcement infrastructure.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_class_broadcast(
        self,
        user_id: UUID,
        tenant_id: UUID,
        school_id: UUID,
        class_id: UUID,
        title: str,
        content: str,
        priority: str = "normal",
    ) -> dict:
        """
        Send a broadcast message to all parents in a class.

        Creates an Announcement with target_audience=SPECIFIC_CLASS and
        publishes it immediately (published_at set to now).
        """
        # Validate priority
        try:
            priority_enum = AnnouncementPriority(priority)
        except ValueError:
            priority_enum = AnnouncementPriority.NORMAL

        # Verify school exists
        school_result = await self.db.execute(
            select(School)
            .where(
                and_(
                    School.id == school_id,
                    School.tenant_id == tenant_id,
                )
            )
        )
        school = school_result.scalar_one_or_none()
        if not school:
            raise TeacherServiceError("School not found", code="not_found")

        announcement = Announcement(
            tenant_id=tenant_id,
            school_id=school_id,
            title=title,
            content=content,
            author_id=user_id,
            target_audience=AnnouncementTarget.SPECIFIC_CLASS,
            target_class_id=class_id,
            priority=priority_enum,
            published_at=datetime.now(UTC),
        )
        self.db.add(announcement)
        await self.db.flush()
        await self.db.refresh(announcement)

        logger.info(
            "class_broadcast_sent",
            announcement_id=str(announcement.id),
            class_id=str(class_id),
            teacher_user_id=str(user_id),
        )

        return {
            "announcement_id": announcement.id,
            "message": "Broadcast sent successfully",
        }
