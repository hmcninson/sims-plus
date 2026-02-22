"""Fix unique constraints for soft delete

This migration updates unique constraints to use partial indexes
that exclude soft-deleted records, allowing names to be reused
after deletion.

Revision ID: 20260105_0200
Revises: 20260105_0100_add_school_metadata
Create Date: 2026-01-05

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260105_0200"
down_revision: Union[str, None] = "20260105_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing unique constraints
    op.drop_constraint("uq_academic_year_name", "academic_years", type_="unique")
    op.drop_constraint("uq_class_name", "classes", type_="unique")
    op.drop_constraint("uq_subject_code", "subjects", type_="unique")
    op.drop_constraint("uq_grading_scale_name", "grading_scales", type_="unique")

    # Create partial unique indexes that exclude soft-deleted records
    op.execute("""
        CREATE UNIQUE INDEX uq_academic_year_name_active
        ON academic_years (tenant_id, name)
        WHERE deleted_at IS NULL
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_class_name_active
        ON classes (tenant_id, name)
        WHERE deleted_at IS NULL
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_subject_code_active
        ON subjects (tenant_id, code)
        WHERE deleted_at IS NULL
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_grading_scale_name_active
        ON grading_scales (tenant_id, name)
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    # Drop partial unique indexes
    op.drop_index("uq_academic_year_name_active", table_name="academic_years")
    op.drop_index("uq_class_name_active", table_name="classes")
    op.drop_index("uq_subject_code_active", table_name="subjects")
    op.drop_index("uq_grading_scale_name_active", table_name="grading_scales")

    # Recreate original unique constraints
    op.create_unique_constraint("uq_academic_year_name", "academic_years", ["tenant_id", "name"])
    op.create_unique_constraint("uq_class_name", "classes", ["tenant_id", "name"])
    op.create_unique_constraint("uq_subject_code", "subjects", ["tenant_id", "code"])
    op.create_unique_constraint("uq_grading_scale_name", "grading_scales", ["tenant_id", "name"])
