"""Seed preschool learning areas, skills, and rating scales

Revision ID: 20260109_1800
Revises: 20260109_1700
Create Date: 2026-01-09 18:00:00.000000

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '20260109_1800'
down_revision: Union[str, None] = '20260109_0200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Standard preschool learning areas based on early childhood education frameworks
LEARNING_AREAS = [
    {
        "code": "SED",
        "name": "Social-Emotional Development",
        "description": "Developing self-awareness, self-regulation, and relationships with others",
        "icon": "heart",
        "color": "#ec4899",  # Pink
        "display_order": 1,
    },
    {
        "code": "LL",
        "name": "Language & Literacy",
        "description": "Developing listening, speaking, reading, and writing skills",
        "icon": "book-open",
        "color": "#3b82f6",  # Blue
        "display_order": 2,
    },
    {
        "code": "MT",
        "name": "Mathematical Thinking",
        "description": "Developing number sense, patterns, shapes, and problem-solving",
        "icon": "calculator",
        "color": "#22c55e",  # Green
        "display_order": 3,
    },
    {
        "code": "SE",
        "name": "Scientific Exploration",
        "description": "Exploring the natural world through observation and investigation",
        "icon": "flask",
        "color": "#8b5cf6",  # Purple
        "display_order": 4,
    },
    {
        "code": "PD-GM",
        "name": "Physical Development - Gross Motor",
        "description": "Developing large muscle skills like running, jumping, and climbing",
        "icon": "dumbbell",
        "color": "#f97316",  # Orange
        "display_order": 5,
    },
    {
        "code": "PD-FM",
        "name": "Physical Development - Fine Motor",
        "description": "Developing small muscle skills like writing, cutting, and manipulating objects",
        "icon": "hand",
        "color": "#eab308",  # Yellow
        "display_order": 6,
    },
    {
        "code": "CA",
        "name": "Creative Arts",
        "description": "Expressing creativity through art, music, drama, and movement",
        "icon": "palette",
        "color": "#06b6d4",  # Cyan
        "display_order": 7,
    },
    {
        "code": "PH",
        "name": "Personal Hygiene & Self-Help",
        "description": "Developing independence in daily routines and self-care",
        "icon": "sparkles",
        "color": "#14b8a6",  # Teal
        "display_order": 8,
    },
]

# Skills for each learning area
SKILLS_BY_AREA = {
    "SED": [
        "Recognizes and expresses own feelings",
        "Shows empathy towards others",
        "Follows classroom rules and routines",
        "Takes turns and shares with others",
        "Resolves conflicts with guidance",
        "Shows confidence in abilities",
        "Separates easily from caregivers",
        "Cooperates in group activities",
    ],
    "LL": [
        "Listens attentively to stories and instructions",
        "Speaks in complete sentences",
        "Recognizes own name in print",
        "Identifies letters of the alphabet",
        "Recognizes common sight words",
        "Attempts to write letters and words",
        "Retells familiar stories",
        "Uses books appropriately",
    ],
    "MT": [
        "Counts objects up to 20",
        "Recognizes numerals 0-10",
        "Compares quantities (more/less/same)",
        "Identifies basic shapes",
        "Creates and extends simple patterns",
        "Sorts objects by attributes",
        "Uses positional words correctly",
        "Understands concept of addition/subtraction",
    ],
    "SE": [
        "Shows curiosity and asks questions",
        "Makes predictions about outcomes",
        "Uses senses to explore materials",
        "Observes and describes changes",
        "Cares for living things",
        "Understands weather concepts",
        "Explores cause and effect",
        "Uses simple tools for investigation",
    ],
    "PD-GM": [
        "Runs, jumps, and hops with control",
        "Climbs playground equipment safely",
        "Catches and throws a ball",
        "Balances on one foot",
        "Pedals a tricycle",
        "Participates in group movement activities",
        "Navigates obstacle courses",
        "Demonstrates body awareness",
    ],
    "PD-FM": [
        "Holds pencil/crayon correctly",
        "Cuts with scissors along a line",
        "Strings beads",
        "Completes puzzles",
        "Uses glue appropriately",
        "Traces shapes and lines",
        "Buttons and zips clothing",
        "Manipulates playdough and clay",
    ],
    "CA": [
        "Explores various art materials",
        "Creates artwork with intention",
        "Participates in music and movement",
        "Engages in dramatic play",
        "Responds to different types of music",
        "Uses imagination in play",
        "Appreciates artwork of others",
        "Expresses ideas through art",
    ],
    "PH": [
        "Washes and dries hands properly",
        "Uses toilet independently",
        "Puts on and removes outerwear",
        "Feeds self with utensils",
        "Cleans up after activities",
        "Covers mouth when coughing/sneezing",
        "Manages personal belongings",
        "Follows hygiene routines",
    ],
}

# Standard 5-point developmental rating scale
RATING_SCALE = {
    "name": "Developmental Rating Scale",
    "description": "Standard 5-point scale for assessing preschool developmental skills",
}

RATINGS = [
    {
        "name": "Not Yet Observed",
        "short_code": "NYO",
        "description": "Skill has not been observed or child has not had opportunity to demonstrate",
        "numeric_value": 0,
        "color": "#9ca3af",  # Gray
        "display_order": 1,
    },
    {
        "name": "Emerging",
        "short_code": "E",
        "description": "Child is beginning to show awareness of the skill with significant support",
        "numeric_value": 1,
        "color": "#ef4444",  # Red
        "display_order": 2,
    },
    {
        "name": "Developing",
        "short_code": "D",
        "description": "Child demonstrates the skill inconsistently or with some support",
        "numeric_value": 2,
        "color": "#eab308",  # Yellow
        "display_order": 3,
    },
    {
        "name": "Proficient",
        "short_code": "P",
        "description": "Child consistently demonstrates the skill independently",
        "numeric_value": 3,
        "color": "#22c55e",  # Green
        "display_order": 4,
    },
    {
        "name": "Advanced",
        "short_code": "A",
        "description": "Child exceeds expectations and may help others with this skill",
        "numeric_value": 4,
        "color": "#3b82f6",  # Blue
        "display_order": 5,
    },
]


def upgrade() -> None:
    """Seed preschool data for all existing tenants."""
    conn = op.get_bind()

    # Get all tenant IDs
    result = conn.execute(sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL"))
    tenants = result.fetchall()

    for (tenant_id,) in tenants:
        # Create rating scale
        scale_id = uuid4()
        conn.execute(
            sa.text("""
                INSERT INTO preschool_rating_scales (id, tenant_id, name, description, is_default)
                VALUES (:id, :tenant_id, :name, :description, true)
                ON CONFLICT (tenant_id, name) DO NOTHING
            """),
            {
                "id": scale_id,
                "tenant_id": tenant_id,
                "name": RATING_SCALE["name"],
                "description": RATING_SCALE["description"],
            }
        )

        # Get the scale ID (in case it already existed)
        result = conn.execute(
            sa.text("SELECT id FROM preschool_rating_scales WHERE tenant_id = :tenant_id AND name = :name"),
            {"tenant_id": tenant_id, "name": RATING_SCALE["name"]}
        )
        row = result.fetchone()
        if row:
            scale_id = row[0]

        # Create ratings for the scale
        for rating in RATINGS:
            conn.execute(
                sa.text("""
                    INSERT INTO preschool_ratings (id, scale_id, name, short_code, description, numeric_value, color, display_order)
                    VALUES (:id, :scale_id, :name, :short_code, :description, :numeric_value, :color, :display_order)
                    ON CONFLICT (scale_id, short_code) DO NOTHING
                """),
                {
                    "id": uuid4(),
                    "scale_id": scale_id,
                    "name": rating["name"],
                    "short_code": rating["short_code"],
                    "description": rating["description"],
                    "numeric_value": rating["numeric_value"],
                    "color": rating["color"],
                    "display_order": rating["display_order"],
                }
            )

        # Create learning areas and skills
        for area in LEARNING_AREAS:
            area_id = uuid4()
            conn.execute(
                sa.text("""
                    INSERT INTO learning_areas (id, tenant_id, code, name, description, icon, color, display_order, is_active)
                    VALUES (:id, :tenant_id, :code, :name, :description, :icon, :color, :display_order, true)
                    ON CONFLICT (tenant_id, code) DO NOTHING
                """),
                {
                    "id": area_id,
                    "tenant_id": tenant_id,
                    "code": area["code"],
                    "name": area["name"],
                    "description": area["description"],
                    "icon": area["icon"],
                    "color": area["color"],
                    "display_order": area["display_order"],
                }
            )

            # Get the area ID (in case it already existed)
            result = conn.execute(
                sa.text("SELECT id FROM learning_areas WHERE tenant_id = :tenant_id AND code = :code"),
                {"tenant_id": tenant_id, "code": area["code"]}
            )
            row = result.fetchone()
            if row:
                area_id = row[0]

            # Create skills for this learning area
            skills = SKILLS_BY_AREA.get(area["code"], [])
            for order, skill_name in enumerate(skills, 1):
                conn.execute(
                    sa.text("""
                        INSERT INTO developmental_skills (id, tenant_id, learning_area_id, name, display_order, is_active)
                        VALUES (:id, :tenant_id, :learning_area_id, :name, :display_order, true)
                        ON CONFLICT (tenant_id, learning_area_id, name) DO NOTHING
                    """),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "learning_area_id": area_id,
                        "name": skill_name,
                        "display_order": order,
                    }
                )


def downgrade() -> None:
    """Remove seeded preschool data."""
    conn = op.get_bind()

    # Delete skills
    conn.execute(sa.text("DELETE FROM developmental_skills"))

    # Delete learning areas
    conn.execute(sa.text("DELETE FROM learning_areas"))

    # Delete ratings
    conn.execute(sa.text("DELETE FROM preschool_ratings"))

    # Delete rating scales
    conn.execute(sa.text("DELETE FROM preschool_rating_scales"))
