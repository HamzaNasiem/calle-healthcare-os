"""initial_schema

Revision ID: 3ec0823a4d01
Revises: 
Create Date: 2026-06-11 04:12:42.807473

"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ec0823a4d01'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema by applying SQL scripts in order."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    files = [
        "src/db/schema.sql",
        "src/db/migrations/create_clinic_users.sql",
        "src/db/migrations/create_security_tables.sql",
        "src/db/migrations/create_distributed_locks.sql",
        "src/db/phase5b_migrations.sql"
    ]
    
    for relative_path in files:
        full_path = os.path.join(base_dir, relative_path)
        if os.path.exists(full_path):
            print(f"[Alembic] Reading migration file: {full_path}")
            with open(full_path, 'r', encoding='utf-8') as f:
                sql = f.read()
                if sql.strip():
                    op.execute(sql)
        else:
            print(f"[Alembic] WARNING: migration file not found: {full_path}")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order of foreign key dependencies
    tables = [
        "revenue_events",
        "jobs",
        "sms_messages",
        "calls",
        "appointments",
        "patients",
        "user_sessions",
        "audit_logs",
        "clinic_users",
        "distributed_locks",
        "clinics"
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    
    op.execute("DROP FUNCTION IF EXISTS public.acquire_distributed_lock(text, int);")
    op.execute("DROP FUNCTION IF EXISTS public.release_distributed_lock(text);")

