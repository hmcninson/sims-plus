"""
SIMS Plus - Parent Communication Service

Announcements, teacher notes, and acknowledgement handling for parents.
All methods enforce parent-child access verification where applicable.
"""

from datetime import datetime, UTC
from uuid import UUID

import structlog
from sqlalchemy import select, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.academic import AcademicYear
from app.models.parent import (
    Announcement,
    AnnouncementTarget,
    TeacherNote,
)
from app.models.student import Student

from app.services.parent._shared import ParentServiceError
from app.services.parent.parent_service import ParentService

logger = structlog.get_logger()


class ParentCommunicationService:
    """
    Service for parent access to communication data: announcements and teacher notes.

    Announcements are filtered by targeting rules based on the parent's children.
    Teacher notes require parent-child access verification per student.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._parent = ParentService(db)

    async def get_announcements_for_parent(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> list[dict]:
        """
        Get announcements visible to this parent based on targeting rules.

        Targeting logic:
        - all_parents: always included
        - specific_class: include if any of the parent's children is in that class
        - specific_house: include if any child has a boarding assignment in that house
        - boarding_parents: include if any child is a boarder (is_boarder=True)
        - transport_parents: not yet implemented (no transport column on Student)

        Only returns published (published_at IS NOT NULL), non-expired,
        non-deleted announcements, ordered by pinned status then publish date.

        Args:
            user_id: The authenticated parent's user ID
            tenant_id: Tenant ID (defense-in-depth with RLS)

        Returns:
            List of dicts matching AnnouncementResponse schema
        """
        # Get all children for this parent to determine which announcements apply
        children = await self._parent.get_my_children(user_id, tenant_id)

        if not children:
            # No children linked: only show all_parents announcements
            return await self._fetch_announcements(
                tenant_id,
                class_ids=[],
                has_boarder=False,
                house_ids=[],
            )

        # Collect targeting criteria from children
        class_ids = [
            child.class_id for child in children if child.class_id is not None
        ]
        has_boarder = any(child.is_boarder for child in children)

        # Collect house IDs from boarding assignments (if boarding module is active)
        house_ids = await self._get_children_house_ids(
            tenant_id, [child.id for child in children]
        )

        return await self._fetch_announcements(
            tenant_id,
            class_ids=class_ids,
            has_boarder=has_boarder,
            house_ids=house_ids,
        )

    async def _get_children_house_ids(
        self, tenant_id: UUID, student_ids: list[UUID]
    ) -> list[UUID]:
        """
        Get house IDs for children who have boarding assignments.

        Queries the student_boarding table to find active house assignments
        for the current academic year.
        """
        if not student_ids:
            return []

        try:
            # Import boarding model here to avoid hard dependency
            from app.models.boarding.models import StudentBoarding

            # Get current academic year for boarding context
            year_result = await self.db.execute(
                select(AcademicYear.id)
                .where(
                    and_(
                        AcademicYear.tenant_id == tenant_id,
                        AcademicYear.is_current == True,
                        AcademicYear.deleted_at.is_(None),
                    )
                )
            )
            current_year_id = year_result.scalar_one_or_none()
            if not current_year_id:
                return []

            result = await self.db.execute(
                select(StudentBoarding.house_id)
                .where(
                    and_(
                        StudentBoarding.tenant_id == tenant_id,
                        StudentBoarding.student_id.in_(student_ids),
                        StudentBoarding.academic_year_id == current_year_id,
                        StudentBoarding.deleted_at.is_(None),
                    )
                )
                .distinct()
            )
            return [row[0] for row in result.all()]
        except Exception:
            # Boarding module may not be fully set up; gracefully degrade
            logger.debug(
                "boarding_house_lookup_skipped",
                reason="boarding module not available or no assignments",
            )
            return []

    async def _fetch_announcements(
        self,
        tenant_id: UUID,
        class_ids: list[UUID],
        has_boarder: bool,
        house_ids: list[UUID],
    ) -> list[dict]:
        """
        Fetch announcements matching the targeting criteria.

        Builds an OR clause that matches:
        - all_parents announcements (always)
        - specific_class where target_class_id in parent's children's class IDs
        - specific_house where target_house_id in parent's children's house IDs
        - boarding_parents if any child is a boarder
        """
        now = datetime.now(UTC)

        # Base conditions: published, not expired, not deleted
        base_conditions = [
            Announcement.tenant_id == tenant_id,
            Announcement.deleted_at.is_(None),
            Announcement.published_at.isnot(None),
        ]

        # Build targeting filter
        target_filters = [
            # All parents announcements are always visible
            Announcement.target_audience == AnnouncementTarget.ALL_PARENTS,
        ]

        # Class-specific announcements
        if class_ids:
            target_filters.append(
                and_(
                    Announcement.target_audience == AnnouncementTarget.SPECIFIC_CLASS,
                    Announcement.target_class_id.in_(class_ids),
                )
            )

        # House-specific announcements
        if house_ids:
            target_filters.append(
                and_(
                    Announcement.target_audience == AnnouncementTarget.SPECIFIC_HOUSE,
                    Announcement.target_house_id.in_(house_ids),
                )
            )

        # Boarding parents announcements
        if has_boarder:
            target_filters.append(
                Announcement.target_audience == AnnouncementTarget.BOARDING_PARENTS,
            )

        # Combine: must match base conditions AND at least one targeting filter
        query = (
            select(Announcement)
            .where(
                and_(
                    *base_conditions,
                    or_(*target_filters),
                    # Exclude expired announcements
                    or_(
                        Announcement.expires_at.is_(None),
                        Announcement.expires_at > now,
                    ),
                )
            )
            .options(joinedload(Announcement.author))
            .order_by(
                # Pinned announcements first, then by publish date
                Announcement.is_pinned.desc(),
                Announcement.published_at.desc(),
            )
        )

        result = await self.db.execute(query)
        announcements = result.scalars().unique().all()

        return [
            {
                "id": ann.id,
                "title": ann.title,
                "content": ann.content,
                "author_name": (
                    f"{ann.author.first_name} {ann.author.last_name}"
                    if ann.author else None
                ),
                "priority": ann.priority.value,
                "target_audience": ann.target_audience.value,
                "published_at": ann.published_at,
                "expires_at": ann.expires_at,
                "is_pinned": ann.is_pinned,
                "attachment_url": ann.attachment_url,
                "created_at": ann.created_at,
            }
            for ann in announcements
        ]

    async def get_child_teacher_notes(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
    ) -> list[dict]:
        """
        Get teacher notes for a child that are visible to parents.

        Only returns notes where is_visible_to_parent=True.
        Ordered by creation date, most recent first.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)

        Returns:
            List of dicts matching TeacherNoteResponse schema

        Raises:
            ParentServiceError: If access denied
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        result = await self.db.execute(
            select(TeacherNote)
            .where(
                and_(
                    TeacherNote.student_id == student_id,
                    TeacherNote.tenant_id == tenant_id,
                    TeacherNote.deleted_at.is_(None),
                    # Only show notes marked visible to parents
                    TeacherNote.is_visible_to_parent == True,
                )
            )
            .options(
                joinedload(TeacherNote.teacher),
                joinedload(TeacherNote.student),
            )
            .order_by(desc(TeacherNote.created_at))
        )
        notes = result.scalars().unique().all()

        return [
            {
                "id": note.id,
                "student_id": note.student_id,
                "student_name": (
                    f"{note.student.first_name} {note.student.last_name}"
                    if note.student else None
                ),
                "teacher_name": (
                    f"{note.teacher.first_name} {note.teacher.last_name}"
                    if note.teacher else None
                ),
                "subject_name": None,  # Subject loaded separately if needed
                "note_type": note.note_type.value,
                "content": note.content,
                "is_visible_to_parent": note.is_visible_to_parent,
                "parent_acknowledged": note.parent_acknowledged,
                "parent_acknowledged_at": note.parent_acknowledged_at,
                "created_at": note.created_at,
            }
            for note in notes
        ]

    async def acknowledge_teacher_note(
        self,
        user_id: UUID,
        student_id: UUID,
        note_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """
        Mark a teacher note as acknowledged by parent.

        Verifies parent-child access AND that the note belongs to the
        specified student (IDOR prevention).

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            note_id: The teacher note to acknowledge
            tenant_id: Tenant ID (defense-in-depth with RLS)

        Raises:
            ParentServiceError: If access denied, note not found, or already acknowledged
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        result = await self.db.execute(
            select(TeacherNote)
            .where(
                and_(
                    TeacherNote.id == note_id,
                    TeacherNote.tenant_id == tenant_id,
                    # IDOR check: note must belong to the specified student
                    TeacherNote.student_id == student_id,
                    TeacherNote.deleted_at.is_(None),
                    TeacherNote.is_visible_to_parent == True,
                )
            )
        )
        note = result.scalar_one_or_none()

        if not note:
            raise ParentServiceError(
                "Teacher note not found", code="note_not_found"
            )

        if note.parent_acknowledged:
            # Idempotent: acknowledging an already-acknowledged note is a no-op
            return

        note.parent_acknowledged = True
        note.parent_acknowledged_at = datetime.now(UTC)

        await self.db.flush()
