"""
Database-direct script to bulk assign subjects to all classes for a tenant.

This script runs directly against the database without requiring API authentication.

Usage:
    python -m scripts.assign_subjects_to_classes_db <subdomain>

Example:
    python -m scripts.assign_subjects_to_classes_db brightfutureacademy
"""
import asyncio
import sys
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, "/app")

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.tenant import Tenant
from app.models.academic import Class, Subject, ClassSubject


async def get_tenant_by_subdomain(db: AsyncSession, subdomain: str) -> Tenant | None:
    """Get tenant by subdomain."""
    result = await db.execute(
        select(Tenant).where(Tenant.subdomain == subdomain)
    )
    return result.scalar_one_or_none()


async def get_all_classes(db: AsyncSession, tenant_id: UUID) -> list[Class]:
    """Get all classes for a tenant."""
    result = await db.execute(
        select(Class).where(
            and_(
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None)
            )
        )
    )
    return list(result.scalars().all())


async def get_all_subjects(db: AsyncSession, tenant_id: UUID) -> list[Subject]:
    """Get all subjects for a tenant."""
    result = await db.execute(
        select(Subject).where(
            and_(
                Subject.tenant_id == tenant_id,
                Subject.deleted_at.is_(None),
                Subject.is_active == True
            )
        )
    )
    return list(result.scalars().all())


async def get_existing_class_subjects(
    db: AsyncSession, tenant_id: UUID, class_id: UUID
) -> set[UUID]:
    """Get existing subject IDs assigned to a class."""
    result = await db.execute(
        select(ClassSubject.subject_id).where(
            and_(
                ClassSubject.tenant_id == tenant_id,
                ClassSubject.class_id == class_id,
            )
        )
    )
    return set(result.scalars().all())


def get_level_category(class_obj: Class) -> str:
    """
    Get the level category from the class level enum.

    Maps specific levels (nursery_1, kg_1, jhs_1, etc.) to categories.
    """
    if not class_obj.level:
        return "unknown"

    level_value = class_obj.level.value if hasattr(class_obj.level, 'value') else str(class_obj.level)

    # Direct category levels
    if level_value in ["preschool", "primary", "jhs", "shs"]:
        return level_value

    # Specific grade level mappings
    if level_value in ["creche", "nursery_1", "nursery_2", "kg_1", "kg_2"]:
        return "preschool"
    elif level_value.startswith("primary_"):
        return "primary"
    elif level_value.startswith("jhs_"):
        return "jhs"
    elif level_value.startswith("shs_"):
        return "shs"

    return "unknown"


def should_assign_subject_to_class(
    subject: Subject, class_obj: Class
) -> bool:
    """
    Determine if a subject should be assigned to a class based on level category.

    Preschool classes get a limited set of foundational subjects.
    Other levels (primary, jhs, shs) get all subjects.
    """
    level_category = get_level_category(class_obj)
    subject_name_lower = subject.name.lower()

    if level_category == "preschool":
        # Preschool typically has simplified subjects
        preschool_subjects = [
            "english", "mathematics", "math", "numeracy",
            "reading", "writing", "phonics", "creative arts",
            "physical education", "pe", "science", "social studies",
            "art", "music", "rhymes", "nature"
        ]
        return any(ps in subject_name_lower for ps in preschool_subjects)
    else:
        # For other levels, assign all subjects
        return True


async def assign_subjects_to_class(
    db: AsyncSession,
    tenant_id: UUID,
    class_obj: Class,
    subjects: list[Subject],
    existing_subject_ids: set[UUID]
) -> int:
    """Assign subjects to a class. Returns count of newly assigned subjects."""
    assigned_count = 0

    for subject in subjects:
        # Skip if already assigned
        if subject.id in existing_subject_ids:
            continue

        # Check if subject should be assigned based on class level
        if not should_assign_subject_to_class(subject, class_obj):
            continue

        # Create class subject assignment
        class_subject = ClassSubject(
            tenant_id=tenant_id,
            class_id=class_obj.id,
            subject_id=subject.id,
            is_compulsory=True,
            periods_per_week=5,
        )
        db.add(class_subject)
        assigned_count += 1

    return assigned_count


async def main(subdomain: str):
    """Main function to assign subjects to all classes."""
    print(f"\n{'='*60}")
    print(f"BULK SUBJECT ASSIGNMENT")
    print(f"Subdomain: {subdomain}")
    print(f"{'='*60}\n")

    async with async_session_maker() as db:
        # 1. Get tenant
        print("Looking up tenant...")
        tenant = await get_tenant_by_subdomain(db, subdomain)

        if not tenant:
            print(f"ERROR: Tenant with subdomain '{subdomain}' not found!")
            return

        print(f"  Found: {tenant.name} (ID: {tenant.id})")

        # 2. Get all classes
        print("\nFetching classes...")
        classes = await get_all_classes(db, tenant.id)
        print(f"  Found {len(classes)} classes")

        if not classes:
            print("  No classes found. Please create classes first.")
            return

        # 3. Get all subjects
        print("\nFetching subjects...")
        subjects = await get_all_subjects(db, tenant.id)
        print(f"  Found {len(subjects)} subjects")

        if not subjects:
            print("  No subjects found. Please create subjects first.")
            return

        # 4. Assign subjects to each class
        print(f"\n{'='*60}")
        print("ASSIGNING SUBJECTS TO CLASSES")
        print(f"{'='*60}")

        total_assigned = 0

        for class_obj in classes:
            level_category = get_level_category(class_obj)
            print(f"\n{class_obj.name} (Category: {level_category})")

            # Get existing assignments
            existing_subject_ids = await get_existing_class_subjects(
                db, tenant.id, class_obj.id
            )
            print(f"  Already has {len(existing_subject_ids)} subjects assigned")

            # Assign new subjects
            assigned_count = await assign_subjects_to_class(
                db, tenant.id, class_obj, subjects, existing_subject_ids
            )

            if assigned_count > 0:
                print(f"  + Assigned {assigned_count} new subjects")
                total_assigned += assigned_count
            else:
                print(f"  - No new subjects to assign")

        # Commit all changes
        if total_assigned > 0:
            await db.commit()
            print(f"\n{'='*60}")
            print(f"DONE! Assigned {total_assigned} total subject-class mappings")
            print(f"{'='*60}")
        else:
            print(f"\n{'='*60}")
            print("DONE! All subjects were already assigned to classes.")
            print(f"{'='*60}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.assign_subjects_to_classes_db <subdomain>")
        print("Example: python -m scripts.assign_subjects_to_classes_db brightfutureacademy")
        sys.exit(1)

    subdomain = sys.argv[1]
    asyncio.run(main(subdomain))
