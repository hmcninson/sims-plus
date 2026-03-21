"""
Service to initialize subjects from GES curriculum templates.

Idempotent: skips subjects that already exist (by code) for the tenant/school.
"""

import structlog
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ges_subjects import (
    GES_SUBJECTS,
    SHS_ELECTIVE_PROGRAMMES,
    SCHOOL_TYPE_SUBJECT_MAP,
    LEVEL_MAPPING,
)
from app.models.academic.subject_models import Subject, SubjectCategory

logger = structlog.get_logger()


class SubjectTemplateService:
    """Service for initializing subjects from GES curriculum templates."""

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_from_template(
        self,
        tenant_id: UUID,
        school_type: str,
        school_id: UUID | None = None,
        programmes: list[str] | None = None,
    ) -> dict:
        """
        Create standard GES subjects for a given school type.

        Idempotent: subjects that already exist (by code within the tenant)
        are skipped. Uses flush() so the caller's middleware handles commit.

        Args:
            tenant_id: Tenant UUID
            school_type: SchoolType value (e.g., "primary", "jhs", "shs", "basic")
            school_id: Optional school UUID (for chain tenants)
            programmes: SHS elective programme names (required for SHS schools)
                       e.g., ["General Science", "Business"]

        Returns:
            {"created": int, "skipped": int, "subjects": list[dict]}
        """
        subject_keys = SCHOOL_TYPE_SUBJECT_MAP.get(school_type)
        if not subject_keys:
            raise self.Error(f"Unknown school type: {school_type}", 422)

        # Collect all subjects to create, deduplicating by code
        subjects_to_create: list[dict] = []
        seen_codes: set[str] = set()

        for key in subject_keys:
            template_subjects = GES_SUBJECTS.get(key, [])
            applicable_levels = LEVEL_MAPPING.get(key, [])

            for subj in template_subjects:
                if subj["code"] not in seen_codes:
                    subjects_to_create.append({
                        **subj,
                        "applicable_levels": applicable_levels,
                    })
                    seen_codes.add(subj["code"])

        # Add SHS elective programme subjects if applicable
        if school_type in ("shs", "basic_shs", "international", "technical") and programmes:
            shs_levels = LEVEL_MAPPING["shs_core"]
            for programme_name in programmes:
                programme_subjects = SHS_ELECTIVE_PROGRAMMES.get(programme_name, [])
                for subj in programme_subjects:
                    if subj["code"] not in seen_codes:
                        subjects_to_create.append({
                            **subj,
                            "applicable_levels": shs_levels,
                        })
                        seen_codes.add(subj["code"])

        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        existing_codes_query = select(Subject.code).where(
            and_(
                Subject.tenant_id == tenant_id,
                Subject.deleted_at.is_(None),
            )
        )
        if school_id:
            existing_codes_query = existing_codes_query.where(
                Subject.school_id == school_id
            )

        result = await self.db.execute(existing_codes_query)
        existing_codes = {row[0] for row in result.all()}

        created = 0
        skipped = 0
        created_subjects: list[dict] = []

        for subj_data in subjects_to_create:
            if subj_data["code"] in existing_codes:
                skipped += 1
                continue

            subject = Subject(
                tenant_id=tenant_id,
                school_id=school_id,
                name=subj_data["name"],
                code=subj_data["code"],
                category=SubjectCategory(subj_data["category"]),
                applicable_levels=subj_data["applicable_levels"],
                is_active=True,
            )
            self.db.add(subject)
            created += 1
            created_subjects.append({
                "name": subj_data["name"],
                "code": subj_data["code"],
                "category": subj_data["category"],
            })

        # Flush to assign IDs but let the endpoint middleware handle commit
        await self.db.flush()

        logger.info(
            "subjects_initialized_from_template",
            tenant_id=str(tenant_id),
            school_type=school_type,
            created=created,
            skipped=skipped,
            programmes=programmes,
        )

        return {
            "created": created,
            "skipped": skipped,
            "subjects": created_subjects,
        }

    @staticmethod
    def get_available_programmes() -> list[str]:
        """Return list of available SHS elective programme names."""
        return list(SHS_ELECTIVE_PROGRAMMES.keys())

    @staticmethod
    def list_templates(school_type: str) -> list[dict]:
        """
        Return the available subject templates for a school type.

        Includes core subjects from GES_SUBJECTS and, for SHS-capable types,
        notes that elective programmes are available separately.

        Args:
            school_type: SchoolType value

        Returns:
            List of subject dicts with name, code, category, applicable_levels
        """
        subject_keys = SCHOOL_TYPE_SUBJECT_MAP.get(school_type)
        if not subject_keys:
            return []

        subjects: list[dict] = []
        seen_codes: set[str] = set()

        for key in subject_keys:
            template_subjects = GES_SUBJECTS.get(key, [])
            applicable_levels = LEVEL_MAPPING.get(key, [])

            for subj in template_subjects:
                if subj["code"] not in seen_codes:
                    subjects.append({
                        **subj,
                        "applicable_levels": applicable_levels,
                    })
                    seen_codes.add(subj["code"])

        return subjects
