"""Add scholarship-invoice improvements

Revision ID: 20260125_0100
Revises: 20260122_0300
Create Date: 2026-01-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260125_0100"
down_revision = "20260122_0300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reinstated_from column to student_scholarships for tracking reinstated awards
    op.add_column(
        "student_scholarships",
        sa.Column(
            "reinstated_from",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_scholarships.id", ondelete="SET NULL"),
            nullable=True,
            comment="Reference to previously revoked scholarship if this is a reinstatement",
        ),
    )

    # Create invoice_scholarship_items table for tracking scholarship discounts on invoices
    op.create_table(
        "invoice_scholarship_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_scholarship_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_scholarships.id", ondelete="SET NULL"),
            nullable=True,
            comment="Link to the student scholarship that provided this discount",
        ),
        sa.Column(
            "scholarship_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarships.id", ondelete="SET NULL"),
            nullable=True,
            comment="Direct link to scholarship for historical reference",
        ),
        sa.Column(
            "scholarship_name",
            sa.String(100),
            nullable=False,
            comment="Scholarship name at time of application (for historical record)",
        ),
        sa.Column(
            "scholarship_code",
            sa.String(20),
            nullable=True,
            comment="Scholarship code at time of application",
        ),
        sa.Column(
            "coverage_type",
            sa.String(20),
            nullable=False,
            comment="percentage or fixed_amount",
        ),
        sa.Column(
            "coverage_value",
            sa.Numeric(12, 2),
            nullable=False,
            comment="The coverage value used (percentage or amount)",
        ),
        sa.Column(
            "calculated_amount",
            sa.Numeric(12, 2),
            nullable=False,
            comment="The actual discount amount applied to the invoice",
        ),
        sa.Column(
            "applicable_subtotal",
            sa.Numeric(12, 2),
            nullable=False,
            comment="The subtotal this scholarship was applied to",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        comment="Tracks scholarship discounts applied to invoices with full audit trail",
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_invoice_scholarship_items_tenant_id",
        "invoice_scholarship_items",
        ["tenant_id"],
    )
    op.create_index(
        "ix_invoice_scholarship_items_invoice_id",
        "invoice_scholarship_items",
        ["invoice_id"],
    )
    op.create_index(
        "ix_invoice_scholarship_items_student_scholarship_id",
        "invoice_scholarship_items",
        ["student_scholarship_id"],
    )
    op.create_index(
        "ix_invoice_scholarship_items_scholarship_id",
        "invoice_scholarship_items",
        ["scholarship_id"],
    )

    # Add adjustment_for_invoice_id to invoices for tracking adjustment invoices
    op.add_column(
        "invoices",
        sa.Column(
            "adjustment_for_invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
            comment="If this is an adjustment invoice, reference to the original invoice",
        ),
    )

    # Add adjustment_type to invoices
    op.add_column(
        "invoices",
        sa.Column(
            "adjustment_type",
            sa.String(30),
            nullable=True,
            comment="Type of adjustment: scholarship_revoked, scholarship_reinstated, fee_correction, etc.",
        ),
    )

    # Add adjustment_reason to invoices
    op.add_column(
        "invoices",
        sa.Column(
            "adjustment_reason",
            sa.Text,
            nullable=True,
            comment="Reason for the adjustment",
        ),
    )


def downgrade() -> None:
    # Remove columns from invoices
    op.drop_column("invoices", "adjustment_reason")
    op.drop_column("invoices", "adjustment_type")
    op.drop_column("invoices", "adjustment_for_invoice_id")

    # Drop indexes
    op.drop_index(
        "ix_invoice_scholarship_items_scholarship_id",
        table_name="invoice_scholarship_items",
    )
    op.drop_index(
        "ix_invoice_scholarship_items_student_scholarship_id",
        table_name="invoice_scholarship_items",
    )
    op.drop_index(
        "ix_invoice_scholarship_items_invoice_id",
        table_name="invoice_scholarship_items",
    )
    op.drop_index(
        "ix_invoice_scholarship_items_tenant_id",
        table_name="invoice_scholarship_items",
    )

    # Drop invoice_scholarship_items table
    op.drop_table("invoice_scholarship_items")

    # Remove reinstated_from from student_scholarships
    op.drop_column("student_scholarships", "reinstated_from")
