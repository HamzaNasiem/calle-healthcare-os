-- ============================================================
-- Bytelytic Clinic OS - Phase 9 Advanced Settings & API Keys Migrations
-- ============================================================

-- 1. Add Webhook and advanced configuration columns to clinics table
ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS webhook_url TEXT,
  ADD COLUMN IF NOT EXISTS webhook_secret TEXT,
  ADD COLUMN IF NOT EXISTS benchmark_opt_in BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS monthly_revenue_per_visit INTEGER DEFAULT 150,
  ADD COLUMN IF NOT EXISTS recall_days INTEGER[] DEFAULT '{30,60,90}';

-- Ensure webhook_events is TEXT[]
ALTER TABLE public.clinics DROP COLUMN IF EXISTS webhook_events;
ALTER TABLE public.clinics ADD COLUMN webhook_events TEXT[] DEFAULT '{"call.completed", "appointment.booked", "appointment.cancelled", "patient.created"}';

-- 2. Create api_keys table for secure API key management
CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL REFERENCES public.clinics(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Default API Key',
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    masked_key TEXT NOT NULL,
    scopes TEXT[] DEFAULT '{"read", "write"}',
    is_active BOOLEAN DEFAULT TRUE,
    created_by TEXT,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_clinic ON public.api_keys(clinic_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON public.api_keys(key_hash);
