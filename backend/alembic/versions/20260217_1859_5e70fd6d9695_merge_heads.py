"""merge_heads

Revision ID: 5e70fd6d9695
Revises: add_attendance_soft_delete, add_tenant_to_preschool_ratings
Create Date: 2026-02-17 18:59:17.851652+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e70fd6d9695'
down_revision: Union[str, None] = ('add_attendance_soft_delete', 'add_tenant_to_preschool_ratings')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass
