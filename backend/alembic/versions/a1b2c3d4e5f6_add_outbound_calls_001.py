"""Add outbound_calls table and appointment CALL-E columns

Revision ID: a1b2c3d4e5f6
Revises: d0eab12a5c8b
Create Date: 2026-08-03 00:00:00.000000

CALL-E Integration: Step 10 - Database Migration
Adds outbound_calls table and confirmation-related columns on appointments.
Uses IF NOT EXISTS / existence checks for idempotent execution.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd0eab12a5c8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=:tname)"
    ), {"tname": table_name})
    return result.scalar()


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name=:tname AND column_name=:cname)"
    ), {"tname": table_name, "cname": column_name})
    return result.scalar()


def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname=:iname)"
    ), {"iname": index_name})
    return result.scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create outbound_calls table (IF NOT EXISTS) ──────────────────────
    if not _table_exists(conn, 'outbound_calls'):
        op.create_table(
            'outbound_calls',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('appointment_id', UUID(as_uuid=True), sa.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True),
            sa.Column('call_type', sa.String(50), nullable=False),
            sa.Column('calle_call_id', sa.String(255), unique=True, nullable=True),
            sa.Column('idempotency_key', sa.String(255), unique=True, nullable=False),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('task_completed', sa.Boolean(), nullable=True),
            sa.Column('structured_result', JSONB, nullable=True),
            sa.Column('completion_confidence_score', sa.Float(), nullable=True),
            sa.Column('completion_confidence_label', sa.String(20), nullable=True),
            sa.Column('evidence', JSONB, nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
            sa.Column('placed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # ── 2. Indexes for fast lookups (IF NOT EXISTS) ─────────────────────────
    index_map = {
        'idx_outbound_calls_tenant_id': ('outbound_calls', ['tenant_id']),
        'idx_outbound_calls_appointment_id': ('outbound_calls', ['appointment_id']),
        'idx_outbound_calls_calle_call_id': ('outbound_calls', ['calle_call_id']),
        'idx_outbound_calls_idempotency_key': ('outbound_calls', ['idempotency_key']),
        'idx_outbound_calls_status': ('outbound_calls', ['status']),
        'idx_outbound_calls_created_at': ('outbound_calls', ['created_at']),
    }
    for idx_name, (tbl, cols) in index_map.items():
        if not _index_exists(conn, idx_name):
            unique = idx_name == 'idx_outbound_calls_idempotency_key'
            op.create_index(idx_name, tbl, cols, unique=unique)

    # ── 3. Add CALL-E columns to appointments table (IF NOT EXISTS) ──────────
    columns_to_add = [
        ('call_confirmed', sa.Boolean(), {'server_default': 'false', 'nullable': True}),
        ('confirmation_call_id', UUID(as_uuid=True), {'nullable': True}),
        ('pre_appointment_call_sent', sa.Boolean(), {'server_default': 'false', 'nullable': True}),
        ('cancellation_reason', sa.Text(), {'nullable': True}),
        ('cancelled_at', sa.DateTime(timezone=True), {'nullable': True}),
    ]
    for col_name, col_type, col_kwargs in columns_to_add:
        if not _column_exists(conn, 'appointments', col_name):
            op.add_column('appointments', sa.Column(col_name, col_type, **col_kwargs))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove CALL-E columns from appointments
    cols_to_remove = ['cancelled_at', 'cancellation_reason', 'pre_appointment_call_sent',
                      'confirmation_call_id', 'call_confirmed']
    for col in cols_to_remove:
        if _column_exists(conn, 'appointments', col):
            op.drop_column('appointments', col)

    # Drop outbound_calls indexes
    for idx_name in ['idx_outbound_calls_created_at', 'idx_outbound_calls_status',
                     'idx_outbound_calls_idempotency_key', 'idx_outbound_calls_calle_call_id',
                     'idx_outbound_calls_appointment_id', 'idx_outbound_calls_tenant_id']:
        if _index_exists(conn, idx_name):
            op.drop_index(idx_name, table_name='outbound_calls')

    # Drop table
    if _table_exists(conn, 'outbound_calls'):
        op.drop_table('outbound_calls')
