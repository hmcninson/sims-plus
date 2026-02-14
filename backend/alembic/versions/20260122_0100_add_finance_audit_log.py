"""Add finance audit log for comprehensive audit trail

Revision ID: 20260122_0100
Revises: 20260121_0400
Create Date: 2026-01-22

This migration creates the finance_audit_log table for tracking all changes
to financial entities (invoices, payments, scholarships, etc.).
Also adds justification field to student_scholarships for award tracking.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260122_0100"
down_revision: Union[str, None] = "20260121_0400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create finance_audit_log table
    op.create_table(
        "finance_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "entity_type",
            sa.String(50),
            nullable=False,
            comment="Type of entity: invoice, payment, scholarship, fee_structure, etc.",
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="ID of the entity being audited",
        ),
        sa.Column(
            "action",
            sa.String(20),
            nullable=False,
            comment="Action type: create, update, delete, void, issue, cancel, award, revoke",
        ),
        sa.Column(
            "field_name",
            sa.String(100),
            nullable=True,
            comment="Field that was changed (for updates)",
        ),
        sa.Column(
            "old_value",
            sa.Text(),
            nullable=True,
            comment="Previous value (JSON string for complex values)",
        ),
        sa.Column(
            "new_value",
            sa.Text(),
            nullable=True,
            comment="New value (JSON string for complex values)",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Reason for the change (e.g., void reason, cancel reason)",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional metadata about the change",
        ),
        sa.Column(
            "performed_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User who made the change",
        ),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
            comment="IP address of the user",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Browser/client user agent",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_finance_audit_log_tenant_id",
        "finance_audit_log",
        ["tenant_id"],
    )
    op.create_index(
        "ix_finance_audit_log_entity",
        "finance_audit_log",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_finance_audit_log_performed_at",
        "finance_audit_log",
        ["tenant_id", "performed_at"],
    )
    op.create_index(
        "ix_finance_audit_log_performed_by",
        "finance_audit_log",
        ["performed_by"],
    )

    # 2. Add justification field to student_scholarships
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'student_scholarships' AND column_name = 'justification'
            ) THEN
                ALTER TABLE student_scholarships
                ADD COLUMN justification TEXT;
                COMMENT ON COLUMN student_scholarships.justification IS 'Required justification/reason for awarding the scholarship';
            END IF;
        END $$;
    """)

    # 3. Add renewal_type field to student_scholarships
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'student_scholarships' AND column_name = 'renewal_type'
            ) THEN
                ALTER TABLE student_scholarships
                ADD COLUMN renewal_type VARCHAR(20) DEFAULT 'one_time';
                COMMENT ON COLUMN student_scholarships.renewal_type IS 'Renewal type: one_time, annual, until_graduation';
            END IF;
        END $$;
    """)

    # 4. Add is_provisional flag to student_scholarships
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'student_scholarships' AND column_name = 'is_provisional'
            ) THEN
                ALTER TABLE student_scholarships
                ADD COLUMN is_provisional BOOLEAN DEFAULT FALSE;
                COMMENT ON COLUMN student_scholarships.is_provisional IS 'Whether this is a provisional/conditional award';
            END IF;
        END $$;
    """)

    # 5. Add provisional_conditions field
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'student_scholarships' AND column_name = 'provisional_conditions'
            ) THEN
                ALTER TABLE student_scholarships
                ADD COLUMN provisional_conditions TEXT;
                COMMENT ON COLUMN student_scholarships.provisional_conditions IS 'Conditions that must be met for provisional awards';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Drop new columns from student_scholarships
    op.drop_column("student_scholarships", "provisional_conditions")
    op.drop_column("student_scholarships", "is_provisional")
    op.drop_column("student_scholarships", "renewal_type")
    op.drop_column("student_scholarships", "justification")

    # Drop indexes
    op.drop_index("ix_finance_audit_log_performed_by", table_name="finance_audit_log")
    op.drop_index("ix_finance_audit_log_performed_at", table_name="finance_audit_log")
    op.drop_index("ix_finance_audit_log_entity", table_name="finance_audit_log")
    op.drop_index("ix_finance_audit_log_tenant_id", table_name="finance_audit_log")

    # Drop table
    op.drop_table("finance_audit_log")
