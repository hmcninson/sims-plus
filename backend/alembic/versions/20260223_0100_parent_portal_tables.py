"""Add parent portal tables: announcements, teacher_notes, parent_notification_preferences

Three new tenant-scoped tables for the parent portal (Sprint 13-14).
All tables have RLS enabled and forced with hardened tenant isolation.

- announcements: school-wide or targeted announcements for parents
- teacher_notes: per-student notes from teachers, with parent acknowledgement
- parent_notification_preferences: per-user notification channel/category settings

Three new enum types: announcementtarget, announcementpriority, notetype

Revision ID: 20260223_0100
Revises: 20260222_0200
Create Date: 2026-02-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM


revision: str = "20260223_0100"
down_revision: Union[str, None] = "20260222_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# -----------------------------------------------------------------------
# All 3 new tenant-scoped tables (must be added to conftest.py too)
# -----------------------------------------------------------------------
NEW_TENANT_SCOPED_TABLES = [
    "announcements",
    "teacher_notes",
    "parent_notification_preferences",
]

# -----------------------------------------------------------------------
# All 3 new enum types (all lowercase values per Sprint 3-4+ convention)
# -----------------------------------------------------------------------
ENUM_DEFINITIONS = {
    "announcementtarget": (
        "all_parents", "specific_class", "specific_house",
        "boarding_parents", "transport_parents",
    ),
    "announcementpriority": ("normal", "important", "urgent"),
    "notetype": ("positive", "concern", "information", "action_required"),
}


def _enable_rls(table_name: str) -> None:
    """Enable and force RLS with hardened tenant isolation policy."""
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            FOR ALL TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")


def _disable_rls(table_name: str) -> None:
    """Drop RLS policy and disable RLS."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Phase 1: Create all enum types
    # ------------------------------------------------------------------
    for enum_name, values in ENUM_DEFINITIONS.items():
        values_str = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")

    # ------------------------------------------------------------------
    # Phase 2: Create tables
    # ------------------------------------------------------------------

    # 1. announcements
    op.create_table(
        "announcements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_audience", ENUM(
            "all_parents", "specific_class", "specific_house",
            "boarding_parents", "transport_parents",
            name="announcementtarget", create_type=False,
        ), nullable=False, server_default="all_parents"),
        sa.Column("target_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_house_id", UUID(as_uuid=True), sa.ForeignKey("houses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority", ENUM(
            "normal", "important", "urgent",
            name="announcementpriority", create_type=False,
        ), nullable=False, server_default="normal"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attachment_url", sa.String(500), nullable=True),
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. teacher_notes
    op.create_table(
        "teacher_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note_type", ENUM(
            "positive", "concern", "information", "action_required",
            name="notetype", create_type=False,
        ), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_visible_to_parent", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("parent_acknowledged", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("parent_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. parent_notification_preferences (no SoftDeleteMixin -- hard delete with user)
    op.create_table(
        "parent_notification_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # Channel preferences
        sa.Column("email_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sms_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("push_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        # Category preferences
        sa.Column("notify_attendance", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notify_grades", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notify_finance", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notify_announcements", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notify_transport", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notify_boarding", sa.Boolean, nullable=False, server_default=sa.text("true")),
        # Quiet hours
        sa.Column("quiet_hours_start", sa.Time, nullable=True),
        sa.Column("quiet_hours_end", sa.Time, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Unique: one preference record per user per tenant
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_parent_notification_preferences_tenant_user"),
    )

    # ------------------------------------------------------------------
    # Phase 3: Create composite indexes
    # ------------------------------------------------------------------

    # announcements indexes
    op.create_index("idx_announcements_tenant_id", "announcements", ["tenant_id"])
    op.create_index("idx_announcements_tenant_school", "announcements", ["tenant_id", "school_id"])
    op.create_index("idx_announcements_tenant_author", "announcements", ["tenant_id", "author_id"])
    op.create_index("idx_announcements_tenant_target", "announcements", ["tenant_id", "target_audience"])
    op.create_index("idx_announcements_tenant_published", "announcements", ["tenant_id", "published_at"])
    op.create_index("idx_announcements_tenant_priority", "announcements", ["tenant_id", "priority"])
    op.create_index("idx_announcements_tenant_pinned", "announcements", ["tenant_id", "is_pinned"])

    # teacher_notes indexes
    op.create_index("idx_teacher_notes_tenant_id", "teacher_notes", ["tenant_id"])
    op.create_index("idx_teacher_notes_tenant_student", "teacher_notes", ["tenant_id", "student_id"])
    op.create_index("idx_teacher_notes_tenant_teacher", "teacher_notes", ["tenant_id", "teacher_id"])
    op.create_index("idx_teacher_notes_tenant_school", "teacher_notes", ["tenant_id", "school_id"])
    op.create_index("idx_teacher_notes_tenant_type", "teacher_notes", ["tenant_id", "note_type"])
    op.create_index("idx_teacher_notes_tenant_visible", "teacher_notes", ["tenant_id", "is_visible_to_parent"])

    # parent_notification_preferences indexes
    op.create_index("idx_parent_notification_preferences_tenant_id", "parent_notification_preferences", ["tenant_id"])
    op.create_index("idx_parent_notification_preferences_tenant_user", "parent_notification_preferences", ["tenant_id", "user_id"])

    # ------------------------------------------------------------------
    # Phase 4: Enable RLS on all 3 tables
    # ------------------------------------------------------------------
    for table in NEW_TENANT_SCOPED_TABLES:
        _enable_rls(table)

    # Grant sequence usage for new tables
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user")


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Phase 1: Disable RLS on all 3 tables (reverse order)
    # ------------------------------------------------------------------
    for table in reversed(NEW_TENANT_SCOPED_TABLES):
        _disable_rls(table)

    # ------------------------------------------------------------------
    # Phase 2: Drop tables in reverse dependency order
    # ------------------------------------------------------------------
    op.drop_table("parent_notification_preferences")
    op.drop_table("teacher_notes")
    op.drop_table("announcements")

    # ------------------------------------------------------------------
    # Phase 3: Drop enum types
    # ------------------------------------------------------------------
    for enum_name in reversed(list(ENUM_DEFINITIONS.keys())):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
