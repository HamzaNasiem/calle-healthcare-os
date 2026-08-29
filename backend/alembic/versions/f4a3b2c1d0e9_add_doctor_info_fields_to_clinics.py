"""add_doctor_info_fields_to_clinics

Revision ID: f4a3b2c1d0e9
Revises: 13abc5fb58f2
Create Date: 2026-08-15 09:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a3b2c1d0e9'
down_revision: Union[str, Sequence[str], None] = '13abc5fb58f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TABLE public.clinics ADD COLUMN IF NOT EXISTS npi_number TEXT;")
    op.execute("ALTER TABLE public.clinics ADD COLUMN IF NOT EXISTS medical_license TEXT;")

def downgrade() -> None:
    op.execute("ALTER TABLE public.clinics DROP COLUMN IF EXISTS npi_number;")
    op.execute("ALTER TABLE public.clinics DROP COLUMN IF EXISTS medical_license;")
