"""Add fee_types table

Revision ID: 20260120_0300
Revises: 20260120_0200
Create Date: 2026-01-20 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "20260120_0300"
down_revision: Union[str, None] = "20260120_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create fee_types table
    op.create_table(
        "fee_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, comment="Fee type name, e.g., Tuition, Examination, PTA"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=True, comment="Category: tuition, examination, facilities, activities, other"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create unique index on tenant_id + name (case insensitive)
    op.create_index(
        "idx_fee_types_tenant_name_unique",
        "fee_types",
        ["tenant_id", sa.text("lower(name)")],
        unique=True,
    )

    # Create index for searching
    op.create_index("idx_fee_types_school", "fee_types", ["school_id"])
    op.create_index("idx_fee_types_active", "fee_types", ["tenant_id", "is_active"])

    # Add fee_type_id to fee_items table (optional reference)
    op.add_column(
        "fee_items",
        sa.Column(
            "fee_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fee_types.id", ondelete="SET NULL"),
            nullable=True,
            comment="Reference to fee type for consistent naming",
        ),
    )

    # Seed common fee types for existing tenants
    op.execute("""
        INSERT INTO fee_types (tenant_id, school_id, name, category, description)
        SELECT DISTINCT t.id, s.id, ft.name, ft.category, ft.description
        FROM tenants t
        JOIN schools s ON s.tenant_id = t.id
        CROSS JOIN (VALUES
            ('Tuition Fee', 'tuition', 'Regular tuition fees'),
            ('Examination Fee', 'examination', 'Fees for examinations'),
            ('PTA Dues', 'activities', 'Parent Teacher Association dues'),
            ('Sports Fee', 'activities', 'Sports and games activities'),
            ('ICT Fee', 'facilities', 'Computer and technology fees'),
            ('Library Fee', 'facilities', 'Library usage fees'),
            ('Laboratory Fee', 'facilities', 'Science laboratory fees'),
            ('Maintenance Fee', 'facilities', 'School maintenance and repairs'),
            ('Boarding Fee', 'tuition', 'Accommodation for boarding students'),
            ('Feeding Fee', 'tuition', 'Meal fees for boarding students'),
            ('Uniform Fee', 'other', 'School uniform costs'),
            ('Books Fee', 'other', 'Textbooks and learning materials'),
            ('Transport Fee', 'other', 'School bus/transport fees'),
            ('Registration Fee', 'other', 'New student registration'),
            ('Development Levy', 'other', 'School development fund')
        ) AS ft(name, category, description)
        WHERE t.is_active = true;
    """)


def downgrade() -> None:
    op.drop_column("fee_items", "fee_type_id")
    op.drop_index("idx_fee_types_active")
    op.drop_index("idx_fee_types_school")
    op.drop_index("idx_fee_types_tenant_name_unique")
    op.drop_table("fee_types")
