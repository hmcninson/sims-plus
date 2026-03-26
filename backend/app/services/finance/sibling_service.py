"""
SIMS Plus - Sibling Detection Service

Business logic for detecting sibling groups within a tenant.
Used by the preschool sibling discount feature and potentially
by other discount/scholarship workflows.
"""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.student import Guardian, Student, StudentGuardian
from app.services.finance._shared import FinanceServiceError


class SiblingService:
    """Service for detecting sibling groups based on shared guardians."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_sibling_groups(
        self,
        tenant_id: UUID,
        school_id: UUID | None = None,
    ) -> list[dict]:
        """Detect sibling groups by finding students who share guardians.

        A sibling group is defined as 2+ active students linked to the same
        guardian within the same tenant (and optionally school).

        Returns: [
            {
                "guardian_id": UUID,
                "guardian_name": "Mr. Mensah",
                "students": [
                    {"id": UUID, "name": "Kofi Mensah", "class": "KG1"},
                    {"id": UUID, "name": "Ama Mensah", "class": "Nursery 2"},
                ]
            },
            ...
        ]
        """
        # Find guardians with more than one active student
        # Subquery: guardian_ids that link to >1 student
        sibling_guardian_subq = (
            select(StudentGuardian.guardian_id)
            .join(
                Student,
                and_(
                    Student.id == StudentGuardian.student_id,
                    Student.tenant_id == tenant_id,
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                ),
            )
            .where(
                # Defense-in-depth: filter by tenant_id
                StudentGuardian.tenant_id == tenant_id,
            )
        )

        if school_id:
            sibling_guardian_subq = sibling_guardian_subq.where(
                Student.school_id == school_id,
            )

        sibling_guardian_subq = (
            sibling_guardian_subq
            .group_by(StudentGuardian.guardian_id)
            .having(func.count(StudentGuardian.student_id) > 1)
            .subquery()
        )

        # Get full guardian + student details for those guardians
        result = await self.db.execute(
            select(
                Guardian.id.label("guardian_id"),
                Guardian.first_name.label("guardian_first"),
                Guardian.last_name.label("guardian_last"),
                Student.id.label("student_id"),
                Student.first_name.label("student_first"),
                Student.last_name.label("student_last"),
            )
            .select_from(StudentGuardian)
            .join(
                Guardian,
                and_(
                    Guardian.id == StudentGuardian.guardian_id,
                    Guardian.tenant_id == tenant_id,
                    Guardian.deleted_at.is_(None),
                ),
            )
            .join(
                Student,
                and_(
                    Student.id == StudentGuardian.student_id,
                    Student.tenant_id == tenant_id,
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                ),
            )
            .where(
                StudentGuardian.guardian_id.in_(
                    select(sibling_guardian_subq.c.guardian_id)
                ),
            )
            .order_by(Guardian.last_name, Guardian.first_name, Student.first_name)
        )
        rows = result.all()

        # Group by guardian
        groups: dict[UUID, dict] = {}
        for row in rows:
            gid = row.guardian_id
            if gid not in groups:
                groups[gid] = {
                    "guardian_id": gid,
                    "guardian_name": f"{row.guardian_first} {row.guardian_last}",
                    "students": [],
                }
            groups[gid]["students"].append({
                "id": row.student_id,
                "name": f"{row.student_first} {row.student_last}",
            })

        return list(groups.values())
