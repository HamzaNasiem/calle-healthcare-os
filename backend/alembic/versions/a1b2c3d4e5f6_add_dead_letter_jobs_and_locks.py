"""Add dead_letter_jobs table for DLQ pattern

Revision ID: a1b2c3d4e5f6
Revises: 5858b05edf30
Create Date: 2026-06-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '5858b05edf30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dead_letter_jobs table for permanently failed background jobs
    op.create_table(
        'dead_letter_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('original_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('job_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('failed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed', sa.Boolean, server_default='false', nullable=False),
        sa.Column('reviewed_by', sa.String(255), nullable=True),
        sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Index for unreviewed DLQ items (admin dashboard queries)
    op.create_index(
        'idx_dead_letter_jobs_reviewed',
        'dead_letter_jobs',
        ['reviewed', 'failed_at'],
        postgresql_where=sa.text("reviewed = false")
    )

    # Index for clinic-specific DLQ queries
    op.create_index(
        'idx_dead_letter_jobs_clinic',
        'dead_letter_jobs',
        ['clinic_id', 'failed_at']
    )

    # Add distributed lock support functions (PostgreSQL advisory locks)
    # These are idempotent - safe to run multiple times
    op.execute("""
        CREATE OR REPLACE FUNCTION acquire_distributed_lock(lock_key TEXT, lease_seconds INT DEFAULT 60)
        RETURNS BOOLEAN AS $$
        DECLARE
            lock_hash BIGINT;
        BEGIN
            -- Convert text key to a stable bigint hash
            lock_hash := ('x' || substr(md5(lock_key), 1, 16))::bit(64)::bigint;
            -- Try to acquire an advisory lock (non-blocking)
            RETURN pg_try_advisory_lock(lock_hash);
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION release_distributed_lock(lock_key TEXT)
        RETURNS VOID AS $$
        DECLARE
            lock_hash BIGINT;
        BEGIN
            lock_hash := ('x' || substr(md5(lock_key), 1, 16))::bit(64)::bigint;
            PERFORM pg_advisory_unlock(lock_hash);
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.drop_index('idx_dead_letter_jobs_clinic', table_name='dead_letter_jobs')
    op.drop_index('idx_dead_letter_jobs_reviewed', table_name='dead_letter_jobs')
    op.drop_table('dead_letter_jobs')
    op.execute("DROP FUNCTION IF EXISTS acquire_distributed_lock(TEXT, INT);")
    op.execute("DROP FUNCTION IF EXISTS release_distributed_lock(TEXT);")
