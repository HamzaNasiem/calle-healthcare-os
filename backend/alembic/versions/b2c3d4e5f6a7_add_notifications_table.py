"""Add notifications table with Supabase Realtime support

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(64), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('resource_type', sa.String(64), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_read', sa.Boolean, server_default='false', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Index: unread notifications per clinic (most common query pattern)
    op.create_index(
        'idx_notifications_clinic_unread',
        'notifications',
        ['clinic_id', 'created_at'],
        postgresql_where=sa.text("is_read = false")
    )

    # Index: all notifications for a clinic ordered by time
    op.create_index(
        'idx_notifications_clinic_created',
        'notifications',
        ['clinic_id', 'created_at']
    )

    # Auto-delete notifications older than 30 days (prevent table bloat)
    # This is a scheduled Postgres job — run via pg_cron or a daily cron task
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_notifications()
        RETURNS void AS $$
        BEGIN
            DELETE FROM notifications
            WHERE created_at < NOW() - INTERVAL '30 days'
              AND is_read = true;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # NOTE: To enable Supabase Realtime on this table, run in Supabase SQL editor:
    # ALTER PUBLICATION supabase_realtime ADD TABLE notifications;


def downgrade() -> None:
    op.drop_index('idx_notifications_clinic_created', table_name='notifications')
    op.drop_index('idx_notifications_clinic_unread', table_name='notifications')
    op.drop_table('notifications')
    op.execute("DROP FUNCTION IF EXISTS cleanup_old_notifications();")
