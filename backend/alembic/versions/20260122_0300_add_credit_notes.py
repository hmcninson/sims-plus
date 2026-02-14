"""Add credit notes table for handling refunds and credits

Revision ID: 20260122_0300
Revises: 20260122_0200
Create Date: 2026-01-22

This migration creates the credit_notes table for managing fee reductions,
overpayments, and refunds.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260122_0300"
down_revision: Union[str, None] = "20260122_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create credit note status enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'creditnotestatus') THEN
                CREATE TYPE creditnotestatus AS ENUM ('draft', 'issued', 'applied', 'refunded', 'cancelled');
            END IF;
        END $$;
    """)

    # Create credit note type enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'creditnotetype') THEN
                CREATE TYPE creditnotetype AS ENUM ('overpayment', 'fee_reduction', 'error_correction', 'scholarship_adjustment', 'other');
            END IF;
        END $$;
    """)

    # Create credit_notes table
    op.create_table(
        "credit_notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "credit_note_number",
            sa.String(50),
            nullable=False,
            comment="Unique credit note number (e.g., CN-2026-00001)",
        ),
        sa.Column(
            "credit_note_type",
            postgresql.ENUM("overpayment", "fee_reduction", "error_correction", "scholarship_adjustment", "other", name="creditnotetype", create_type=False),
            nullable=False,
            comment="Type of credit note",
        ),
        sa.Column(
            "original_invoice_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Invoice this credit note is issued against (optional)",
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Student receiving the credit",
        ),
        sa.Column(
            "amount",
            sa.Numeric(12, 2),
            nullable=False,
            comment="Credit amount",
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="GHS",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
            comment="Reason for issuing the credit note",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("draft", "issued", "applied", "refunded", "cancelled", name="creditnotestatus", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        # Issuance info
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        # Application info (when applied to another invoice)
        sa.Column(
            "applied_to_invoice_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Invoice this credit was applied to",
        ),
        sa.Column("applied_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("applied_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        # Refund info (when refunded to student/guardian)
        sa.Column(
            "refund_method",
            sa.String(50),
            nullable=True,
            comment="How the refund was made: cash, momo, bank_transfer, etc.",
        ),
        sa.Column("refund_reference", sa.String(100), nullable=True),
        sa.Column("refunded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        # Cancellation info
        sa.Column("cancelled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        # Notes
        sa.Column("notes", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["applied_to_invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["refunded_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_credit_notes_tenant_id",
        "credit_notes",
        ["tenant_id"],
    )
    op.create_index(
        "ix_credit_notes_student_id",
        "credit_notes",
        ["student_id"],
    )
    op.create_index(
        "ix_credit_notes_status",
        "credit_notes",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_credit_notes_number",
        "credit_notes",
        ["tenant_id", "credit_note_number"],
        unique=True,
    )

    # Create sequence for credit note numbers
    op.execute("CREATE SEQUENCE IF NOT EXISTS credit_note_number_seq START WITH 1")

    # Add credit_balance column to students table for tracking available credits
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'students' AND column_name = 'credit_balance'
            ) THEN
                ALTER TABLE students
                ADD COLUMN credit_balance NUMERIC(12, 2) DEFAULT 0.00;
                COMMENT ON COLUMN students.credit_balance IS 'Available credit balance from credit notes';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Drop credit_balance column from students
    op.drop_column("students", "credit_balance")

    # Drop sequence
    op.execute("DROP SEQUENCE IF EXISTS credit_note_number_seq")

    # Drop indexes
    op.drop_index("ix_credit_notes_number", table_name="credit_notes")
    op.drop_index("ix_credit_notes_status", table_name="credit_notes")
    op.drop_index("ix_credit_notes_student_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_tenant_id", table_name="credit_notes")

    # Drop table
    op.drop_table("credit_notes")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS creditnotestatus")
    op.execute("DROP TYPE IF EXISTS creditnotetype")
