-- Bytelytic Clinic OS - Phase 7 Production Hardening & Scalability Migrations
-- Run this SQL in your Supabase SQL Editor to enable RLS, indexes, and Materialized Views.

-- 1. Create materialized view covering yesterday, today, and tomorrow for timezone safety
CREATE MATERIALIZED VIEW IF NOT EXISTS public.today_appointments_mv AS
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
FROM public.appointments
WHERE datetime >= (CURRENT_DATE - INTERVAL '1 day')
  AND datetime < (CURRENT_DATE + INTERVAL '2 days');

-- 2. Unique index on materialized view for concurrent refreshes
CREATE UNIQUE INDEX IF NOT EXISTS idx_today_appts_mv_id ON public.today_appointments_mv(id);

-- 3. Add high-frequency index on patients (clinic_id, phone)
CREATE INDEX IF NOT EXISTS idx_patients_clinic_phone ON public.patients(clinic_id, phone);

-- 4. Add index on appointments (clinic_id, datetime)
CREATE INDEX IF NOT EXISTS idx_appointments_clinic_datetime ON public.appointments(clinic_id, datetime);

-- 5. Create secure RPC function to refresh materialized views
CREATE OR REPLACE FUNCTION public.refresh_materialized_view(view_name text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || quote_ident(view_name);
END;
$$;

-- 6. Create secure RLS verification function
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

-- 7. Enable RLS and add tenant_isolation_policy to tables
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policy ON public.patients;
CREATE POLICY tenant_isolation_policy ON public.patients
    USING (public.check_user_belongs_to_clinic(clinic_id))
    WITH CHECK (public.check_user_belongs_to_clinic(clinic_id));

ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policy ON public.appointments;
CREATE POLICY tenant_isolation_policy ON public.appointments
    USING (public.check_user_belongs_to_clinic(clinic_id))
    WITH CHECK (public.check_user_belongs_to_clinic(clinic_id));

ALTER TABLE public.calls ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policy ON public.calls;
CREATE POLICY tenant_isolation_policy ON public.calls
    USING (public.check_user_belongs_to_clinic(clinic_id))
    WITH CHECK (public.check_user_belongs_to_clinic(clinic_id));

ALTER TABLE public.sms_messages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policy ON public.sms_messages;
CREATE POLICY tenant_isolation_policy ON public.sms_messages
    USING (public.check_user_belongs_to_clinic(clinic_id))
    WITH CHECK (public.check_user_belongs_to_clinic(clinic_id));

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policy ON public.jobs;
CREATE POLICY tenant_isolation_policy ON public.jobs
    USING (public.check_user_belongs_to_clinic(clinic_id))
    WITH CHECK (public.check_user_belongs_to_clinic(clinic_id));

ALTER TABLE public.revenue_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policy ON public.revenue_events;
CREATE POLICY tenant_isolation_policy ON public.revenue_events
    USING (public.check_user_belongs_to_clinic(clinic_id))
    WITH CHECK (public.check_user_belongs_to_clinic(clinic_id));
