"""Student Management Gap Closure Phase 3: Documents & Profile Extensions

New tables:
  - student_documents: Uploaded documents (birth cert, medical, transfer letter, etc.)
    with SoftDeleteMixin (deleted_at). Standard grants (SELECT, INSERT, UPDATE, DELETE).
  - previous_schools: Academic history at prior institutions. No SoftDeleteMixin.
    Standard grants (SELECT, INSERT, UPDATE, DELETE).

New enum:
  - studentdocumenttype: birth_certificate, medical_record, transfer_letter,
    report_card, id_card, leaving_certificate, photo, other

Column additions on students:
  - birth_certificate_number VARCHAR(50)
  - structured_medical JSONB

Revision ID: 20260425_0300
Revises: 20260425_0200
Create Date: 2026-04-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "20260425_0300"
down_revision: Union[str, None] = "20260425_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum: studentdocumenttype
    # ------------------------------------------------------------------
    studentdocumenttype = sa.Enum(
        "birth_certificate",
        "medical_record",
        "transfer_letter",
        "report_card",
        "id_card",
        "leaving_certificate",
        "photo",
        "other",
        name="studentdocumenttype",
    )
    studentdocumenttype.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # Table: student_documents (SoftDeleteMixin — has deleted_at)
    # ------------------------------------------------------------------
    op.create_table(
        "student_documents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_type",
            postgresql.ENUM(
                "birth_certificate", "medical_record", "transfer_letter",
                "report_card", "id_card", "leaving_certificate",
                "photo", "other",
                name="studentdocumenttype",
                create_type=False,  # Already created above; dialect ENUM reliably respects this
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
    )

    # Indexes
    op.execute(
        "CREATE INDEX ix_sdoc_student "
        "ON student_documents(student_id, document_type) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_sdoc_tenant "
        "ON student_documents(tenant_id) "
        "WHERE deleted_at IS NULL"
    )

    # RLS
    op.execute("ALTER TABLE student_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE student_documents FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_student_documents "
        "ON student_documents FOR ALL TO sims_app_user "
        "USING (tenant_id = get_current_tenant_id()) "
        "WITH CHECK (tenant_id = get_current_tenant_id())"
    )

    # Standard grants (includes DELETE — soft delete updates deleted_at, but
    # hard delete may be needed for orphaned/corrupted uploads)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON student_documents TO sims_app_user"
    )

    # ------------------------------------------------------------------
    # Table: previous_schools (NO SoftDeleteMixin)
    # ------------------------------------------------------------------
    op.create_table(
        "previous_schools",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_name", sa.String(255), nullable=False),
        sa.Column("school_address", sa.Text(), nullable=True),
        sa.Column("last_class", sa.String(100), nullable=True),
        sa.Column("years_attended", sa.String(50), nullable=True),
        sa.Column("transfer_reason", sa.Text(), nullable=True),
        sa.Column("leaving_certificate_ref", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
    )

    # Indexes
    op.create_index("ix_prev_school_student", "previous_schools", ["student_id"])
    op.create_index("ix_prev_school_tenant", "previous_schools", ["tenant_id"])

    # RLS
    op.execute("ALTER TABLE previous_schools ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE previous_schools FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_previous_schools "
        "ON previous_schools FOR ALL TO sims_app_user "
        "USING (tenant_id = get_current_tenant_id()) "
        "WITH CHECK (tenant_id = get_current_tenant_id())"
    )

    # Standard grants
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON previous_schools TO sims_app_user"
    )

    # ------------------------------------------------------------------
    # Column additions on students
    # ------------------------------------------------------------------
    op.add_column("students", sa.Column("birth_certificate_number", sa.String(50), nullable=True))
    op.add_column("students", sa.Column("structured_medical", JSONB, nullable=True))


def downgrade() -> None:
    # Drop columns from students
    op.drop_column("students", "structured_medical")
    op.drop_column("students", "birth_certificate_number")

    # Drop previous_schools
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_previous_schools "
        "ON previous_schools"
    )
    op.drop_index("ix_prev_school_tenant", table_name="previous_schools")
    op.drop_index("ix_prev_school_student", table_name="previous_schools")
    op.drop_table("previous_schools")

    # Drop student_documents
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_student_documents "
        "ON student_documents"
    )
    op.execute("DROP INDEX IF EXISTS ix_sdoc_tenant")
    op.execute("DROP INDEX IF EXISTS ix_sdoc_student")
    op.drop_table("student_documents")

    # Drop enum
    sa.Enum(name="studentdocumenttype").drop(op.get_bind(), checkfirst=True)
