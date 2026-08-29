"""add_role_permissions_to_clinics

Revision ID: 5858b05edf30
Revises: 3ec0823a4d01
Create Date: 2026-06-11 04:13:02.541361

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5858b05edf30'
down_revision: Union[str, Sequence[str], None] = '3ec0823a4d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add role_permissions column to clinics."""
    op.execute("ALTER TABLE clinics ADD COLUMN IF NOT EXISTS role_permissions JSONB DEFAULT '{}'::jsonb;")


def downgrade() -> None:
    """Downgrade schema: remove role_permissions column from clinics."""
    op.execute("ALTER TABLE clinics DROP COLUMN IF EXISTS role_permissions;")

