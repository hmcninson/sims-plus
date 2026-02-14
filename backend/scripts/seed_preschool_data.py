"""
Database-direct script to seed preschool data for a tenant.

Seeds:
- Default learning areas (8 areas)
- Default developmental skills (~70 skills)
- Default 5-point rating scale

Usage:
    python -m scripts.seed_preschool_data <subdomain>

Example:
    python -m scripts.seed_preschool_data brightfutureacademy
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
from app.models.preschool import (
    LearningArea,
    DevelopmentalSkill,
    PreschoolRatingScale,
    PreschoolRating,
)


# =========================
# Default Seed Data
# =========================

DEFAULT_LEARNING_AREAS = [
    {
        "name": "Social-Emotional Development",
        "code": "SED",
        "description": "Building relationships, understanding emotions, and developing social skills",
        "icon": "heart",
        "color": "#ef4444",
        "display_order": 1,
    },
    {
        "name": "Language & Literacy",
        "code": "LL",
        "description": "Communication, vocabulary, reading readiness, and early writing skills",
        "icon": "book",
        "color": "#3b82f6",
        "display_order": 2,
    },
    {
        "name": "Mathematical Thinking",
        "code": "MT",
        "description": "Numbers, counting, patterns, shapes, and early math concepts",
        "icon": "calculator",
        "color": "#8b5cf6",
        "display_order": 3,
    },
    {
        "name": "Scientific Exploration",
        "code": "SE",
        "description": "Curiosity, observation, exploration, and understanding of the natural world",
        "icon": "flask",
        "color": "#22c55e",
        "display_order": 4,
    },
    {
        "name": "Physical Development - Gross Motor",
        "code": "PD-GM",
        "description": "Large muscle movement, coordination, balance, and physical activity",
        "icon": "running",
        "color": "#f97316",
        "display_order": 5,
    },
    {
        "name": "Physical Development - Fine Motor",
        "code": "PD-FM",
        "description": "Small muscle control, hand-eye coordination, and manual dexterity",
        "icon": "hand",
        "color": "#eab308",
        "display_order": 6,
    },
    {
        "name": "Creative Arts & Expression",
        "code": "CA",
        "description": "Art, music, drama, creative expression, and imagination",
        "icon": "palette",
        "color": "#ec4899",
        "display_order": 7,
    },
    {
        "name": "Personal Hygiene & Self-Care",
        "code": "PH",
        "description": "Self-care routines, hygiene habits, and independence skills",
        "icon": "sparkles",
        "color": "#06b6d4",
        "display_order": 8,
    },
]

DEFAULT_SKILLS_BY_AREA = {
    "SED": [
        {"name": "Separates from caregiver with ease", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Plays alongside other children (parallel play)", "age_range_months_min": 24, "age_range_months_max": 36},
        {"name": "Plays cooperatively with peers", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Shares toys and materials when prompted", "age_range_months_min": 30, "age_range_months_max": 48},
        {"name": "Shares spontaneously without prompting", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Expresses emotions verbally", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Manages strong emotions appropriately", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Shows empathy towards others", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Follows classroom rules", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Takes turns in games and activities", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
    "LL": [
        {"name": "Recognizes own name in print", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Speaks in complete sentences", "age_range_months_min": 36, "age_range_months_max": 48},
        {"name": "Identifies letters of the alphabet", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Recognizes rhyming words", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Holds a book correctly", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Listens to stories with interest", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Retells a simple story in sequence", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Writes own name", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Makes marks that represent letters", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Follows two-step verbal instructions", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
    "MT": [
        {"name": "Counts to 10", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Counts to 20", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Recognizes numbers 1-10", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Identifies basic shapes (circle, square, triangle)", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Sorts objects by color", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Sorts objects by size", "age_range_months_min": 30, "age_range_months_max": 48},
        {"name": "Understands concepts of more/less", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Recognizes simple patterns", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Creates simple patterns", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Understands positional words (in, on, under)", "age_range_months_min": 30, "age_range_months_max": 48},
    ],
    "SE": [
        {"name": "Shows curiosity about surroundings", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Asks questions about the world", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Makes observations about nature", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Participates in simple experiments", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Identifies living vs non-living things", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Explores with senses (touch, smell, taste, sight, sound)", "age_range_months_min": 24, "age_range_months_max": 60},
        {"name": "Makes predictions about outcomes", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Cares for classroom plants/animals", "age_range_months_min": 48, "age_range_months_max": 72},
    ],
    "PD-GM": [
        {"name": "Walks steadily", "age_range_months_min": 12, "age_range_months_max": 24},
        {"name": "Runs with coordination", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Climbs playground equipment safely", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Jumps with both feet", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Hops on one foot", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Throws a ball overhand", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Catches a large ball", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Kicks a ball forward", "age_range_months_min": 30, "age_range_months_max": 48},
        {"name": "Balances on one foot for 5 seconds", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Pedals a tricycle", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
    "PD-FM": [
        {"name": "Holds crayon/pencil correctly", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Uses scissors to cut on a line", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Strings large beads", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Builds with blocks (stacks 6+ blocks)", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Draws recognizable pictures", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Colors within lines", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Buttons and unbuttons clothing", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Uses zippers", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Ties shoelaces", "age_range_months_min": 60, "age_range_months_max": 84},
        {"name": "Traces shapes and letters", "age_range_months_min": 48, "age_range_months_max": 72},
    ],
    "CA": [
        {"name": "Participates in music activities", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Sings simple songs", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Moves to music rhythmically", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Engages in pretend play", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Creates artwork using various materials", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Expresses ideas through art", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Participates in dramatic play", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Shows creativity in building/constructing", "age_range_months_min": 36, "age_range_months_max": 72},
    ],
    "PH": [
        {"name": "Washes hands properly", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Uses toilet independently", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Feeds self with utensils", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Drinks from a cup without spilling", "age_range_months_min": 24, "age_range_months_max": 36},
        {"name": "Puts on shoes (not necessarily tied)", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Puts on and removes coat", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Brushes teeth with assistance", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Blows nose into tissue", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Covers mouth when coughing", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
}

DEFAULT_RATING_SCALE = {
    "name": "5-Point Developmental Scale",
    "description": "Standard developmental assessment scale for preschool",
    "ratings": [
        {
            "name": "Not Yet Observed",
            "short_code": "NYO",
            "description": "Skill not yet observed or too early for developmental stage",
            "numeric_value": 0,
            "color": "#9ca3af",
            "icon": "circle-dashed",
            "display_order": 0,
        },
        {
            "name": "Emerging",
            "short_code": "E",
            "description": "Beginning to show awareness or initial attempts",
            "numeric_value": 1,
            "color": "#ef4444",
            "icon": "circle",
            "display_order": 1,
        },
        {
            "name": "Developing",
            "short_code": "D",
            "description": "Progressing, needs support or reminders",
            "numeric_value": 2,
            "color": "#eab308",
            "icon": "circle-half",
            "display_order": 2,
        },
        {
            "name": "Proficient",
            "short_code": "P",
            "description": "Consistently demonstrates skill independently",
            "numeric_value": 3,
            "color": "#22c55e",
            "icon": "check-circle",
            "display_order": 3,
        },
        {
            "name": "Advanced",
            "short_code": "A",
            "description": "Exceeds age-appropriate expectations",
            "numeric_value": 4,
            "color": "#3b82f6",
            "icon": "star",
            "display_order": 4,
        },
    ],
}


async def get_tenant_by_subdomain(db: AsyncSession, subdomain: str) -> Tenant | None:
    """Get tenant by subdomain."""
    result = await db.execute(
        select(Tenant).where(Tenant.subdomain == subdomain)
    )
    return result.scalar_one_or_none()


async def check_existing_data(db: AsyncSession, tenant_id: UUID) -> dict:
    """Check what preschool data already exists."""
    # Check learning areas
    areas_result = await db.execute(
        select(LearningArea).where(
            and_(
                LearningArea.tenant_id == tenant_id,
                LearningArea.deleted_at.is_(None),
            )
        )
    )
    areas = list(areas_result.scalars().all())

    # Check rating scales
    scales_result = await db.execute(
        select(PreschoolRatingScale).where(
            and_(
                PreschoolRatingScale.tenant_id == tenant_id,
                PreschoolRatingScale.deleted_at.is_(None),
            )
        )
    )
    scales = list(scales_result.scalars().all())

    return {
        "learning_areas": len(areas),
        "rating_scales": len(scales),
    }


async def seed_learning_areas(db: AsyncSession, tenant_id: UUID) -> list[LearningArea]:
    """Seed default learning areas and skills."""
    areas = []
    total_skills = 0

    for area_data in DEFAULT_LEARNING_AREAS:
        area = LearningArea(
            tenant_id=tenant_id,
            **area_data,
        )
        db.add(area)
        areas.append(area)

    await db.flush()  # Get IDs

    # Add skills for each area
    for area in areas:
        skills_data = DEFAULT_SKILLS_BY_AREA.get(area.code, [])
        for i, skill_data in enumerate(skills_data):
            skill = DevelopmentalSkill(
                tenant_id=tenant_id,
                learning_area_id=area.id,
                display_order=i,
                is_active=True,
                **skill_data,
            )
            db.add(skill)
            total_skills += 1

    print(f"  Created {len(areas)} learning areas")
    print(f"  Created {total_skills} developmental skills")

    return areas


async def seed_rating_scale(db: AsyncSession, tenant_id: UUID) -> PreschoolRatingScale:
    """Seed the default rating scale."""
    scale = PreschoolRatingScale(
        tenant_id=tenant_id,
        name=DEFAULT_RATING_SCALE["name"],
        description=DEFAULT_RATING_SCALE["description"],
        is_default=True,
    )
    db.add(scale)
    await db.flush()  # Get ID

    for rating_data in DEFAULT_RATING_SCALE["ratings"]:
        rating = PreschoolRating(
            scale_id=scale.id,
            **rating_data,
        )
        db.add(rating)

    print(f"  Created rating scale: {scale.name}")
    print(f"  Created {len(DEFAULT_RATING_SCALE['ratings'])} ratings")

    return scale


async def main(subdomain: str):
    """Main function to seed preschool data."""
    print(f"\n{'='*60}")
    print(f"PRESCHOOL DATA SEEDING")
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

        # 2. Check existing data
        print("\nChecking existing data...")
        existing = await check_existing_data(db, tenant.id)
        print(f"  Existing learning areas: {existing['learning_areas']}")
        print(f"  Existing rating scales: {existing['rating_scales']}")

        # 3. Seed learning areas if not exist
        if existing['learning_areas'] == 0:
            print("\nSeeding learning areas and skills...")
            await seed_learning_areas(db, tenant.id)
        else:
            print(f"\n  Skipping learning areas (already have {existing['learning_areas']})")

        # 4. Seed rating scale if not exist
        if existing['rating_scales'] == 0:
            print("\nSeeding rating scale...")
            await seed_rating_scale(db, tenant.id)
        else:
            print(f"\n  Skipping rating scale (already have {existing['rating_scales']})")

        # 5. Commit
        await db.commit()

        print(f"\n{'='*60}")
        print("DONE!")
        print(f"{'='*60}\n")

        # Summary
        final_data = await check_existing_data(db, tenant.id)
        print("Final state:")
        print(f"  Learning areas: {final_data['learning_areas']}")
        print(f"  Rating scales: {final_data['rating_scales']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.seed_preschool_data <subdomain>")
        print("Example: python -m scripts.seed_preschool_data brightfutureacademy")
        sys.exit(1)

    subdomain = sys.argv[1]
    asyncio.run(main(subdomain))
