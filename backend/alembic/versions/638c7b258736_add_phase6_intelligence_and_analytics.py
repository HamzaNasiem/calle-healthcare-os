"""add_phase6_intelligence_and_analytics

Revision ID: 638c7b258736
Revises: b2c3d4e5f6a7
Create Date: 2026-06-11 06:25:08.439860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '638c7b258736'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ai_insights table
    op.create_table(
        'ai_insights',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False)
    )
    
    op.create_index(
        'idx_ai_insights_clinic_created',
        'ai_insights',
        ['clinic_id', 'created_at']
    )

    # 2. Add LTV & Churn columns to patients
    op.add_column('patients', sa.Column('total_revenue_generated', sa.Numeric(10, 2), server_default='0.00', nullable=False))
    op.add_column('patients', sa.Column('average_visit_value', sa.Numeric(10, 2), server_default='0.00', nullable=False))
    op.add_column('patients', sa.Column('visit_frequency_days', sa.Integer(), nullable=True))
    op.add_column('patients', sa.Column('churn_risk_score', sa.Numeric(3, 2), server_default='0.00', nullable=False))
    op.add_column('patients', sa.Column('is_vip', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('patients', sa.Column('last_visit_date', sa.Date(), nullable=True))

    op.create_index(
        'idx_patients_vip_churn',
        'patients',
        ['clinic_id', 'is_vip', 'churn_risk_score']
    )

    # 3. Add benchmark_opt_in to clinics
    op.add_column('clinics', sa.Column('benchmark_opt_in', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    # Remove benchmark_opt_in from clinics
    op.drop_column('clinics', 'benchmark_opt_in')

    # Remove LTV & Churn from patients
    op.drop_index('idx_patients_vip_churn', table_name='patients')
    op.drop_column('patients', 'last_visit_date')
    op.drop_column('patients', 'is_vip')
    op.drop_column('patients', 'churn_risk_score')
    op.drop_column('patients', 'visit_frequency_days')
    op.drop_column('patients', 'average_visit_value')
    op.drop_column('patients', 'total_revenue_generated')

    # Drop ai_insights
    op.drop_index('idx_ai_insights_clinic_created', table_name='ai_insights')
    op.drop_table('ai_insights')
