"""Fix userrole and userstatus enum values: UPPERCASE -> lowercase

Same issue as tenanttype/subscriptiontier: initial migration used enum
member NAMES (UPPERCASE) but models use values_callable which sends
lowercase VALUES.

Revision ID: 20260221_0400
Revises: 20260221_0300
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260221_0400"
down_revision: Union[str, None] = "20260221_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix userrole enum values
    op.execute("ALTER TYPE userrole RENAME VALUE 'PLATFORM_ADMIN' TO 'platform_admin'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'CHAIN_ADMIN' TO 'chain_admin'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'SCHOOL_ADMIN' TO 'school_admin'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'ACADEMIC_HEAD' TO 'academic_head'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'FINANCE_OFFICER' TO 'finance_officer'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'TEACHER' TO 'teacher'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'HOUSE_PARENT' TO 'house_parent'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'PARENT' TO 'parent'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'STUDENT' TO 'student'")

    # Fix userstatus enum values
    op.execute("ALTER TYPE userstatus RENAME VALUE 'PENDING' TO 'pending'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'ACTIVE' TO 'active'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'SUSPENDED' TO 'suspended'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'DEACTIVATED' TO 'deactivated'")


def downgrade() -> None:
    # Revert userrole to UPPERCASE
    op.execute("ALTER TYPE userrole RENAME VALUE 'platform_admin' TO 'PLATFORM_ADMIN'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'chain_admin' TO 'CHAIN_ADMIN'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'school_admin' TO 'SCHOOL_ADMIN'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'academic_head' TO 'ACADEMIC_HEAD'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'finance_officer' TO 'FINANCE_OFFICER'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'teacher' TO 'TEACHER'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'house_parent' TO 'HOUSE_PARENT'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'parent' TO 'PARENT'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'student' TO 'STUDENT'")

    # Revert userstatus to UPPERCASE
    op.execute("ALTER TYPE userstatus RENAME VALUE 'pending' TO 'PENDING'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'active' TO 'ACTIVE'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'suspended' TO 'SUSPENDED'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'deactivated' TO 'DEACTIVATED'")
