"""add_advanced_settings_to_clinics

Revision ID: g5b4c3d2e1f0
Revises: f4a3b2c1d0e9
Create Date: 2026-09-01 06:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g5b4c3d2e1f0'
down_revision: Union[str, Sequence[str], None] = 'f4a3b2c1d0e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TABLE public.clinics ADD COLUMN IF NOT EXISTS advanced_settings JSONB DEFAULT '{}'::jsonb;")

def downgrade() -> None:
    op.execute("ALTER TABLE public.clinics DROP COLUMN IF EXISTS advanced_settings;")
