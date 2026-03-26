"""Staff HR Gap Closure Phase 1: Staff Documents

New table:
  - staff_documents: Uploaded documents (contracts, certificates, CVs, etc.)
    with SoftDeleteMixin (deleted_at). Standard grants (SELECT, INSERT, UPDATE, DELETE).

New enum:
  - staffdocumenttype: contract, certificate, cv_resume, id_document,
    reference_letter, disciplinary, training, medical, other

Revision ID: 20260426_0200
Revises: 20260426_0100
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260426_0200"
down_revision: Union[str, None] = "20260426_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum: staffdocumenttype
    # ------------------------------------------------------------------
    staffdocumenttype = sa.Enum(
        "contract",
        "certificate",
        "cv_resume",
        "id_document",
        "reference_letter",
        "disciplinary",
        "training",
        "medical",
        "other",
        name="staffdocumenttype",
    )
    staffdocumenttype.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # Table: staff_documents (SoftDeleteMixin — has deleted_at)
    # ------------------------------------------------------------------
    op.create_table(
        "staff_documents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_type",
            postgresql.ENUM(
                "contract", "certificate", "cv_resume", "id_document",
                "reference_letter", "disciplinary", "training", "medical", "other",
                name="staffdocumenttype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
    )

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------
    op.create_index("ix_staff_documents_tenant_staff", "staff_documents", ["tenant_id", "staff_id"])
    op.create_index("ix_staff_documents_type", "staff_documents", ["tenant_id", "document_type"])

    # ------------------------------------------------------------------
    # RLS
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE staff_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE staff_documents FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_staff_documents "
        "ON staff_documents FOR ALL TO sims_app_user "
        "USING (tenant_id = get_current_tenant_id()) "
        "WITH CHECK (tenant_id = get_current_tenant_id())"
    )

    # Standard grants
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON staff_documents TO sims_app_user"
    )


def downgrade() -> None:
    # Drop RLS policy
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_staff_documents "
        "ON staff_documents"
    )

    # Drop indexes
    op.drop_index("ix_staff_documents_type", table_name="staff_documents")
    op.drop_index("ix_staff_documents_tenant_staff", table_name="staff_documents")

    # Drop table
    op.drop_table("staff_documents")

    # Drop enum
    sa.Enum(name="staffdocumenttype").drop(op.get_bind(), checkfirst=True)
