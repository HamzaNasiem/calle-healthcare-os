-- ============================================================
-- Bytelytic Clinic OS - Phase 6 Database Migrations
-- ============================================================

-- 1. Create a table to cache weekly AI Insights
CREATE TABLE IF NOT EXISTS public.ai_insights (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     UUID        NOT NULL REFERENCES public.clinics(id) ON DELETE CASCADE,
    period_start  DATE        NOT NULL,
    period_end    DATE        NOT NULL,
    summary       TEXT        NOT NULL, -- Natural language summary markdown
    metadata      JSONB       NOT NULL DEFAULT '{}', -- Raw metrics used for generation
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast retrieval of latest insights per clinic
CREATE INDEX IF NOT EXISTS idx_ai_insights_clinic_created 
    ON public.ai_insights(clinic_id, created_at DESC);

-- 2. Add Patient Lifetime Value (LTV) & Churn risk metrics to patients table
ALTER TABLE public.patients
    ADD COLUMN IF NOT EXISTS total_revenue_generated  NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS average_visit_value      NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS visit_frequency_days     INTEGER,        -- Avg days between consecutive appointments
    ADD COLUMN IF NOT EXISTS churn_risk_score         NUMERIC(3, 2)  NOT NULL DEFAULT 0.00, -- 0.00 to 1.00 scale
    ADD COLUMN IF NOT EXISTS is_vip                   BOOLEAN        NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_visit_date          DATE;

-- Index for querying VIPs and high churn risk patients efficiently
CREATE INDEX IF NOT EXISTS idx_patients_vip_churn 
    ON public.patients(clinic_id, is_vip, churn_risk_score DESC);

-- 3. Add Competitor Benchmarking opt-in state to clinics table
ALTER TABLE public.clinics
    ADD COLUMN IF NOT EXISTS benchmark_opt_in         BOOLEAN NOT NULL DEFAULT FALSE;
