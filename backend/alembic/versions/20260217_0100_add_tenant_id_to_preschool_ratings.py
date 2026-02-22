"""Add tenant_id and deleted_at to preschool_ratings table.

The preschool_ratings table was originally created as a lookup table without
tenant scoping. This is a data isolation failure -- ratings belong to a
specific tenant's rating scale and must be tenant-scoped for RLS enforcement.

This migration:
1. Adds tenant_id column (nullable initially for backfill)
2. Backfills tenant_id from parent preschool_rating_scales table
3. Makes tenant_id NOT NULL after backfill
4. Adds FK constraint to tenants.id
5. Adds deleted_at column for soft delete support
6. Creates tenant_id index
7. Drops old unique constraint and creates new one including tenant_id
8. Enables RLS with hardened tenant isolation policy
9. Grants CRUD permissions to sims_app_user

Revision ID: add_tenant_to_preschool_ratings
Revises: transaction_scoped_tenant_ctx
Create Date: 2026-02-17 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_tenant_to_preschool_ratings"
down_revision = "transaction_scoped_tenant_ctx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tenant_id and deleted_at to preschool_ratings, enable RLS."""
    connection = op.get_bind()

    # ---------------------------------------------------------------
    # Step 1: Add tenant_id column (nullable for backfill)
    # ---------------------------------------------------------------
    op.add_column(
        "preschool_ratings",
        sa.Column("tenant_id", sa.UUID(), nullable=True),
    )

    # ---------------------------------------------------------------
    # Step 2: Backfill tenant_id from parent preschool_rating_scales
    # ---------------------------------------------------------------
    connection.execute(
        sa.text("""
            UPDATE preschool_ratings pr
            SET tenant_id = prs.tenant_id
            FROM preschool_rating_scales prs
            WHERE pr.scale_id = prs.id
        """)
    )

    # Delete orphaned ratings that have no parent scale (defensive cleanup)
    connection.execute(
        sa.text("""
            DELETE FROM preschool_ratings
            WHERE tenant_id IS NULL
        """)
    )

    # ---------------------------------------------------------------
    # Step 3: Make tenant_id NOT NULL after backfill
    # ---------------------------------------------------------------
    op.alter_column(
        "preschool_ratings",
        "tenant_id",
        nullable=False,
    )

    # ---------------------------------------------------------------
    # Step 4: Add FK constraint to tenants.id with CASCADE delete
    # ---------------------------------------------------------------
    op.create_foreign_key(
        "fk_preschool_ratings_tenant_id",
        "preschool_ratings",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ---------------------------------------------------------------
    # Step 5: Add deleted_at column for SoftDeleteMixin
    # ---------------------------------------------------------------
    op.add_column(
        "preschool_ratings",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------
    # Step 6: Create index on tenant_id for RLS performance
    # ---------------------------------------------------------------
    op.create_index(
        "ix_preschool_ratings_tenant_id",
        "preschool_ratings",
        ["tenant_id"],
    )

    # ---------------------------------------------------------------
    # Step 7: Update unique constraint to include tenant_id
    # The old constraint was (scale_id, short_code). The new one is
    # (tenant_id, scale_id, short_code) for proper multi-tenant scoping.
    # ---------------------------------------------------------------
    op.drop_constraint("uq_rating_code", "preschool_ratings", type_="unique")
    op.create_unique_constraint(
        "uq_rating_code",
        "preschool_ratings",
        ["tenant_id", "scale_id", "short_code"],
    )

    # ---------------------------------------------------------------
    # Step 8: Enable RLS with hardened tenant isolation policy
    # Matches the pattern from rls_policy_rework migration.
    # ---------------------------------------------------------------
    connection.execute(
        sa.text("ALTER TABLE preschool_ratings ENABLE ROW LEVEL SECURITY")
    )
    connection.execute(
        sa.text("ALTER TABLE preschool_ratings FORCE ROW LEVEL SECURITY")
    )
    connection.execute(
        sa.text("""
            CREATE POLICY tenant_isolation_preschool_ratings
            ON preschool_ratings
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """)
    )

    # ---------------------------------------------------------------
    # Step 9: Grant CRUD permissions to sims_app_user
    # ---------------------------------------------------------------
    connection.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE, DELETE "
            "ON preschool_ratings TO sims_app_user"
        )
    )


def downgrade() -> None:
    """Remove tenant_id and deleted_at from preschool_ratings, disable RLS."""
    connection = op.get_bind()

    # Drop RLS policy and disable RLS
    connection.execute(
        sa.text(
            "DROP POLICY IF EXISTS tenant_isolation_preschool_ratings "
            "ON preschool_ratings"
        )
    )
    connection.execute(
        sa.text("ALTER TABLE preschool_ratings DISABLE ROW LEVEL SECURITY")
    )

    # Restore original unique constraint
    op.drop_constraint("uq_rating_code", "preschool_ratings", type_="unique")
    op.create_unique_constraint(
        "uq_rating_code",
        "preschool_ratings",
        ["scale_id", "short_code"],
    )

    # Drop index
    op.drop_index("ix_preschool_ratings_tenant_id", "preschool_ratings")

    # Drop deleted_at column
    op.drop_column("preschool_ratings", "deleted_at")

    # Drop FK constraint and column
    op.drop_constraint(
        "fk_preschool_ratings_tenant_id",
        "preschool_ratings",
        type_="foreignkey",
    )
    op.drop_column("preschool_ratings", "tenant_id")
