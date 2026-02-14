"""Add critical finance fixes: unique constraints and sequences

Revision ID: 20260121_0400
Revises: 20260121_0300
Create Date: 2026-01-21

This migration addresses critical issues:
1. Adds unique constraint on student_scholarships to prevent duplicate awards
2. Adds database sequences for invoice/receipt number generation to prevent race conditions
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260121_0400"
down_revision: Union[str, None] = "20260121_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add unique constraint on student_scholarships (idempotent)
    # This prevents duplicate scholarship awards for the same student/scholarship/year
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_student_scholarship_unique'
            ) THEN
                ALTER TABLE student_scholarships
                ADD CONSTRAINT uq_student_scholarship_unique
                UNIQUE (tenant_id, scholarship_id, student_id, academic_year_id);
            END IF;
        END $$;
    """)

    # 2. Create sequence for invoice numbers (per-tenant)
    # Using a global sequence with tenant prefix in the invoice number
    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS invoice_number_seq
        START WITH 1
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1;
    """)

    # 3. Create sequence for receipt numbers (per-tenant)
    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS receipt_number_seq
        START WITH 1
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1;
    """)

    # 4. Add index for student_scholarships unique lookup (idempotent)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_student_scholarships_lookup
        ON student_scholarships (tenant_id, scholarship_id, student_id, academic_year_id);
    """)

    # 5. Add balance column to invoices (idempotent)
    # This is useful for direct queries without needing to compute in Python
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'invoices' AND column_name = 'balance'
            ) THEN
                ALTER TABLE invoices
                ADD COLUMN balance NUMERIC(12, 2) NOT NULL DEFAULT 0.00;
                COMMENT ON COLUMN invoices.balance IS 'Cached balance (total_amount - amount_paid)';
            END IF;
        END $$;
    """)

    # Update existing invoices to set their balance
    op.execute("""
        UPDATE invoices
        SET balance = total_amount - amount_paid
        WHERE balance = 0 AND total_amount > 0;
    """)


def downgrade() -> None:
    # Drop balance column
    op.drop_column("invoices", "balance")

    # Drop index
    op.drop_index("ix_student_scholarships_lookup", table_name="student_scholarships")

    # Drop sequences
    op.execute("DROP SEQUENCE IF EXISTS receipt_number_seq;")
    op.execute("DROP SEQUENCE IF EXISTS invoice_number_seq;")

    # Drop unique constraint
    op.drop_constraint(
        "uq_student_scholarship_unique",
        "student_scholarships",
        type_="unique",
    )
