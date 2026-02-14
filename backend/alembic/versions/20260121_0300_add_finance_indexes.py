"""Add performance indexes for finance tables

Revision ID: 20260121_0300
Revises: 20260121_0200
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260121_0300"
down_revision: Union[str, None] = "20260121_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Indexes for invoices table (critical for performance)
    # Index for filtering by status (most common filter)
    op.create_index(
        "ix_invoices_tenant_status",
        "invoices",
        ["tenant_id", "status"],
    )

    # Index for filtering by academic year
    op.create_index(
        "ix_invoices_tenant_academic_year",
        "invoices",
        ["tenant_id", "academic_year_id"],
    )

    # Index for filtering by term
    op.create_index(
        "ix_invoices_tenant_term",
        "invoices",
        ["tenant_id", "term_id"],
    )

    # Composite index for common filter combination (year + status)
    op.create_index(
        "ix_invoices_tenant_year_status",
        "invoices",
        ["tenant_id", "academic_year_id", "status"],
    )

    # Index for student lookups
    op.create_index(
        "ix_invoices_tenant_student",
        "invoices",
        ["tenant_id", "student_id"],
    )

    # Index for created_at (used for ordering)
    op.create_index(
        "ix_invoices_tenant_created_at",
        "invoices",
        ["tenant_id", "created_at"],
    )

    # Indexes for payments table
    op.create_index(
        "ix_payments_tenant_status",
        "payments",
        ["tenant_id", "status"],
    )

    op.create_index(
        "ix_payments_tenant_payment_method",
        "payments",
        ["tenant_id", "payment_method"],
    )

    op.create_index(
        "ix_payments_tenant_student",
        "payments",
        ["tenant_id", "student_id"],
    )

    op.create_index(
        "ix_payments_tenant_invoice",
        "payments",
        ["tenant_id", "invoice_id"],
    )

    op.create_index(
        "ix_payments_tenant_payment_date",
        "payments",
        ["tenant_id", "payment_date"],
    )

    # Indexes for fee_structures table
    op.create_index(
        "ix_fee_structures_tenant_academic_year",
        "fee_structures",
        ["tenant_id", "academic_year_id"],
    )

    op.create_index(
        "ix_fee_structures_tenant_is_active",
        "fee_structures",
        ["tenant_id", "is_active"],
    )

    # Indexes for scholarships table
    op.create_index(
        "ix_scholarships_tenant_is_active",
        "scholarships",
        ["tenant_id", "is_active"],
    )

    # Indexes for student_scholarships table
    op.create_index(
        "ix_student_scholarships_tenant_student",
        "student_scholarships",
        ["tenant_id", "student_id"],
    )

    op.create_index(
        "ix_student_scholarships_tenant_scholarship",
        "student_scholarships",
        ["tenant_id", "scholarship_id"],
    )

    op.create_index(
        "ix_student_scholarships_tenant_status",
        "student_scholarships",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    # Drop indexes in reverse order
    op.drop_index("ix_student_scholarships_tenant_status", table_name="student_scholarships")
    op.drop_index("ix_student_scholarships_tenant_scholarship", table_name="student_scholarships")
    op.drop_index("ix_student_scholarships_tenant_student", table_name="student_scholarships")
    op.drop_index("ix_scholarships_tenant_is_active", table_name="scholarships")
    op.drop_index("ix_fee_structures_tenant_is_active", table_name="fee_structures")
    op.drop_index("ix_fee_structures_tenant_academic_year", table_name="fee_structures")
    op.drop_index("ix_payments_tenant_payment_date", table_name="payments")
    op.drop_index("ix_payments_tenant_invoice", table_name="payments")
    op.drop_index("ix_payments_tenant_student", table_name="payments")
    op.drop_index("ix_payments_tenant_payment_method", table_name="payments")
    op.drop_index("ix_payments_tenant_status", table_name="payments")
    op.drop_index("ix_invoices_tenant_created_at", table_name="invoices")
    op.drop_index("ix_invoices_tenant_student", table_name="invoices")
    op.drop_index("ix_invoices_tenant_year_status", table_name="invoices")
    op.drop_index("ix_invoices_tenant_term", table_name="invoices")
    op.drop_index("ix_invoices_tenant_academic_year", table_name="invoices")
    op.drop_index("ix_invoices_tenant_status", table_name="invoices")
