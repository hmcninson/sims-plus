"""add section to exam subjects

Revision ID: 20260110_1700
Revises: 20260109_1800_seed_preschool_data
Create Date: 2026-01-10 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260110_1700"
down_revision: Union[str, None] = "20260110_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add section_id column to exam_subjects
    op.add_column(
        "exam_subjects",
        sa.Column(
            "section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("class_sections.id", ondelete="CASCADE"),
            nullable=True,
            comment="Optional section - if NULL, applies to whole class",
        ),
    )

    # Drop the old unique constraint
    op.drop_constraint("uq_exam_subject_class", "exam_subjects", type_="unique")

    # Create new unique index that handles NULL section_id
    op.execute("""
        CREATE UNIQUE INDEX uq_exam_subject_class_section
        ON exam_subjects (tenant_id, exam_id, subject_id, class_id, COALESCE(section_id, '00000000-0000-0000-0000-000000000000'))
    """)


def downgrade() -> None:
    # Drop the new unique index
    op.drop_index("uq_exam_subject_class_section", table_name="exam_subjects")

    # Recreate old unique constraint (after removing duplicates if any)
    # First, delete any rows that would violate the old constraint
    op.execute("""
        DELETE FROM exam_subjects es1
        USING exam_subjects es2
        WHERE es1.id > es2.id
        AND es1.tenant_id = es2.tenant_id
        AND es1.exam_id = es2.exam_id
        AND es1.subject_id = es2.subject_id
        AND es1.class_id = es2.class_id
    """)

    op.create_unique_constraint(
        "uq_exam_subject_class",
        "exam_subjects",
        ["tenant_id", "exam_id", "subject_id", "class_id"],
    )

    # Drop section_id column
    op.drop_column("exam_subjects", "section_id")
