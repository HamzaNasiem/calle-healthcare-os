"""add_phase7_hardening_and_scalability

Revision ID: ebfd6d5685a5
Revises: 638c7b258736
Create Date: 2026-06-11 22:13:13.783569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebfd6d5685a5'
down_revision: Union[str, Sequence[str], None] = '638c7b258736'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create materialized view covering yesterday, today, and tomorrow for timezone safety
    op.execute("""
        CREATE MATERIALIZED VIEW today_appointments_mv AS
        SELECT 
            id,
            clinic_id,
            patient_id,
            patient_name,
            patient_phone,
            appointment_type,
            datetime,
            duration_minutes,
            google_event_id,
            status,
            confirmed_at,
            reminder_sent,
            insurance_verified,
            revenue_amount,
            booked_by,
            notes,
            noshow_risk,
            followup_sent,
            created_at
        FROM appointments
        WHERE datetime >= (CURRENT_DATE - INTERVAL '1 day')
          AND datetime < (CURRENT_DATE + INTERVAL '2 days');
    """)
    
    # 2. Unique index on materialized view for concurrent refreshes
    op.execute("CREATE UNIQUE INDEX idx_today_appts_mv_id ON today_appointments_mv(id);")
    
    # 3. Add high-frequency index on patients (clinic_id, phone)
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_clinic_phone ON patients(clinic_id, phone);")
    
    # 4. Add index on appointments (clinic_id, datetime)
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_clinic_datetime ON appointments(clinic_id, datetime);")

    # 5. Create secure RPC function to refresh materialized views
    op.execute("""
        CREATE OR REPLACE FUNCTION public.refresh_materialized_view(view_name text)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || quote_ident(view_name);
        END;
        $$;
    """)

    # 6. Create secure RLS verification function
    op.execute("""
        CREATE OR REPLACE FUNCTION public.check_user_belongs_to_clinic(cid uuid)
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            RETURN (
                EXISTS (
                    SELECT 1 FROM public.clinics
                    WHERE id = cid AND owner_email = auth.jwt() ->> 'email'
                )
                OR EXISTS (
                    SELECT 1 FROM public.clinic_users
                    WHERE clinic_id = cid AND supabase_user_id = auth.uid()::text
                )
            );
        END;
        $$;
    """)

    # 7. Enable RLS and add tenant_isolation_policy to tables
    tables = ["patients", "appointments", "calls", "sms_messages", "jobs", "revenue_events"]
    for t in tables:
        op.execute(f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON public.{t}
            USING (public.check_user_belongs_to_clinic(clinic_id))
            WITH CHECK (public.check_user_belongs_to_clinic(clinic_id));
        """)


def downgrade() -> None:
    # Drop RLS policies
    tables = ["patients", "appointments", "calls", "sms_messages", "jobs", "revenue_events"]
    for t in tables:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON public.{t};")
        op.execute(f"ALTER TABLE public.{t} DISABLE ROW LEVEL SECURITY;")

    # Drop verification function
    op.execute("DROP FUNCTION IF EXISTS public.check_user_belongs_to_clinic(uuid);")

    # Drop RPC function
    op.execute("DROP FUNCTION IF EXISTS public.refresh_materialized_view(text);")

    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS today_appointments_mv CASCADE;")
    
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_patients_clinic_phone;")
    op.execute("DROP INDEX IF EXISTS idx_appointments_clinic_datetime;")
