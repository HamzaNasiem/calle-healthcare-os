-- ============================================================
-- CALL-E Hackathon: DB Migration
-- File: add_calle_tables.sql
-- Run in: Supabase SQL Editor OR psql
-- ============================================================

-- Create clinics table or view if missing (mapping to tenants if exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'clinics') THEN
        IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'tenants') THEN
            CREATE OR REPLACE VIEW clinics AS SELECT * FROM tenants;
        ELSE
            CREATE TABLE clinics (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                owner_email VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        END IF;
    END IF;
END $$;

-- 1. outbound_calls: tracks every individual CALL-E call
CREATE TABLE IF NOT EXISTS outbound_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    campaign_type VARCHAR(50) NOT NULL CHECK (
        campaign_type IN ('confirmation', 'recall', 'no_show', 'survey')
    ),
    calle_call_id VARCHAR(255) UNIQUE,
    idempotency_key VARCHAR(500) UNIQUE,
    phone_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'no_answer', 'voicemail', 'dry_run')
    ),
    task_completed BOOLEAN DEFAULT FALSE,
    completion_score FLOAT,
    completion_label VARCHAR(100),
    structured_result JSONB DEFAULT '{}',
    summary TEXT DEFAULT '',
    evidence TEXT[] DEFAULT ARRAY[]::TEXT[],
    appointment_id UUID,
    patient_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outbound_calls_clinic ON outbound_calls(clinic_id);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_status ON outbound_calls(status);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_calle_id ON outbound_calls(calle_call_id);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_idempotency ON outbound_calls(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_created ON outbound_calls(created_at DESC);

-- 2. calle_campaigns: tracks batch campaign runs
CREATE TABLE IF NOT EXISTS calle_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    campaign_type VARCHAR(50) NOT NULL CHECK (
        campaign_type IN ('confirmation', 'recall', 'no_show', 'survey')
    ),
    status VARCHAR(50) DEFAULT 'draft' CHECK (
        status IN ('draft', 'running', 'completed', 'paused', 'failed')
    ),
    patient_filter JSONB DEFAULT '{}',
    task_template TEXT NOT NULL DEFAULT '',
    result_schema JSONB NOT NULL DEFAULT '{}',
    total_patients INTEGER DEFAULT 0,
    calls_completed INTEGER DEFAULT 0,
    calls_confirmed INTEGER DEFAULT 0,
    calls_rescheduled INTEGER DEFAULT 0,
    calls_failed INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_calle_campaigns_clinic ON calle_campaigns(clinic_id);
CREATE INDEX IF NOT EXISTS idx_calle_campaigns_status ON calle_campaigns(status);

-- Enable RLS & permissive policy for Service Role / API
ALTER TABLE outbound_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE calle_campaigns ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for authenticated/service" ON outbound_calls;
CREATE POLICY "Allow all for authenticated/service" ON outbound_calls FOR ALL USING (true);

DROP POLICY IF EXISTS "Allow all for authenticated/service" ON calle_campaigns;
CREATE POLICY "Allow all for authenticated/service" ON calle_campaigns FOR ALL USING (true);
