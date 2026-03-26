"""Preschool Phase 1: Incidents, Pickups, Allergies, Sessions

Creates:
- preschool_incidents table with RLS
- authorized_pickups table with RLS
- pickup_logs table with RLS
- enrollment_session column on students
- dietary_requirements JSONB column on students
- session_type column on fee_structures
- CHECK constraints for enum validation
- GIN index on students.dietary_requirements

Revision ID: 20260328_0100
Revises: 20260323_0100
Create Date: 2026-03-28 01:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "20260328_0100"
down_revision: Union[str, None] = "20260323_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # NOTE: No PG enum types created. All enum-like columns use String + CHECK constraints,
    # matching the existing preschool pattern (ObservationType, MoodType, etc. are all String(20)).
    # This avoids ALTER TYPE headaches when adding new values later.

    # ---------------------------------------------------------------
    # 1. Create preschool_incidents table
    # ---------------------------------------------------------------
    op.create_table(
        "preschool_incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="reported"),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("incident_time", sa.Time(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("first_aid_given", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("medical_attention_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("parent_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_notified_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("witnesses", JSONB(), nullable=True),
        sa.Column("attachments", JSONB(), nullable=True),
        sa.Column("follow_up_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reported_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------
    # 2. Create authorized_pickups table
    # ---------------------------------------------------------------
    op.create_table(
        "authorized_pickups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("relationship_to_student", sa.String(100), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("id_document_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial unique index to allow re-adding soft-deleted phone numbers
    op.execute("""
        CREATE UNIQUE INDEX uq_authorized_pickup_phone
        ON authorized_pickups (tenant_id, student_id, phone)
        WHERE deleted_at IS NULL
    """)

    # ---------------------------------------------------------------
    # 3. Create pickup_logs table
    # ---------------------------------------------------------------
    op.create_table(
        "pickup_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pickup_date", sa.Date(), nullable=False),
        sa.Column("pickup_time", sa.Time(), nullable=False),
        sa.Column("picked_up_by_type", sa.String(20), nullable=False),
        sa.Column("picked_up_by_guardian_id", UUID(as_uuid=True), sa.ForeignKey("guardians.id", ondelete="SET NULL"), nullable=True),
        sa.Column("picked_up_by_authorized_id", UUID(as_uuid=True), sa.ForeignKey("authorized_pickups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---------------------------------------------------------------
    # 4. Add columns to existing tables
    # ---------------------------------------------------------------
    # students: enrollment_session + dietary_requirements
    op.add_column("students", sa.Column(
        "enrollment_session", sa.String(20), nullable=True,
        comment="Preschool session type: half_day_morning, half_day_afternoon, full_day, extended",
    ))
    op.add_column("students", sa.Column(
        "dietary_requirements", JSONB(), nullable=True,
        comment="Structured dietary/allergy data for preschool students",
    ))

    # fee_structures: session_type
    op.add_column("fee_structures", sa.Column(
        "session_type", sa.String(20), nullable=True,
        comment="Preschool session type filter. NULL = applies to all sessions.",
    ))

    # ---------------------------------------------------------------
    # 5. Create indexes
    # ---------------------------------------------------------------
    # preschool_incidents
    op.create_index("ix_preschool_incidents_tenant", "preschool_incidents", ["tenant_id"])
    op.create_index("ix_preschool_incidents_school", "preschool_incidents", ["school_id"])
    op.create_index("ix_preschool_incidents_student_date", "preschool_incidents", ["tenant_id", "student_id", "incident_date"])
    op.create_index("ix_preschool_incidents_status", "preschool_incidents", ["tenant_id", "status"])

    # authorized_pickups
    op.create_index("ix_authorized_pickups_tenant", "authorized_pickups", ["tenant_id"])
    op.create_index("ix_authorized_pickups_school", "authorized_pickups", ["school_id"])
    op.create_index("ix_authorized_pickups_student", "authorized_pickups", ["tenant_id", "student_id"])

    # pickup_logs
    op.create_index("ix_pickup_logs_tenant", "pickup_logs", ["tenant_id"])
    op.create_index("ix_pickup_logs_school", "pickup_logs", ["school_id"])
    op.create_index("ix_pickup_logs_student_date", "pickup_logs", ["tenant_id", "student_id", "pickup_date"])

    # students: GIN index for dietary_requirements JSONB queries
    op.execute(
        "CREATE INDEX ix_students_dietary_requirements ON students "
        "USING GIN (dietary_requirements) WHERE dietary_requirements IS NOT NULL"
    )

    # ---------------------------------------------------------------
    # 6. CHECK constraints (enforce valid enum values at DB level)
    # ---------------------------------------------------------------
    op.execute("""
        ALTER TABLE preschool_incidents
        ADD CONSTRAINT ck_incident_type CHECK (incident_type IN ('accident', 'illness', 'behavioral', 'allergic_reaction', 'other')),
        ADD CONSTRAINT ck_incident_severity CHECK (severity IN ('minor', 'moderate', 'serious')),
        ADD CONSTRAINT ck_incident_status CHECK (status IN ('reported', 'reviewed', 'parent_notified', 'resolved'))
    """)
    op.execute("""
        ALTER TABLE pickup_logs
        ADD CONSTRAINT ck_pickup_type CHECK (picked_up_by_type IN ('guardian', 'authorized_person')),
        ADD CONSTRAINT ck_pickup_person CHECK (
            (picked_up_by_type = 'guardian' AND picked_up_by_guardian_id IS NOT NULL AND picked_up_by_authorized_id IS NULL)
            OR
            (picked_up_by_type = 'authorized_person' AND picked_up_by_authorized_id IS NOT NULL AND picked_up_by_guardian_id IS NULL)
        )
    """)

    # ---------------------------------------------------------------
    # 7. RLS policies (using project-standard rls_helpers)
    # ---------------------------------------------------------------
    from app.db.rls_helpers import enable_rls_for_table
    for table in ["preschool_incidents", "authorized_pickups", "pickup_logs"]:
        enable_rls_for_table(conn, table)


def downgrade() -> None:
    from app.db.rls_helpers import disable_rls_for_table
    conn = op.get_bind()

    # Disable RLS before dropping tables
    for table in ["pickup_logs", "authorized_pickups", "preschool_incidents"]:
        disable_rls_for_table(conn, table)

    # Drop tables (reverse order of creation)
    op.drop_table("pickup_logs")
    op.drop_table("authorized_pickups")
    op.drop_table("preschool_incidents")

    # Drop added columns (reverse order)
    op.drop_column("fee_structures", "session_type")
    op.drop_index("ix_students_dietary_requirements", "students")
    op.drop_column("students", "dietary_requirements")
    op.drop_column("students", "enrollment_session")
