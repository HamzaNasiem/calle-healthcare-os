-- ============================================================
-- Bytelytic Clinic OS - Phase 10 Doctor Info & Provider Sync Migrations
-- ============================================================

-- 1. Add doctor info columns to clinics table
ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS doctor_title TEXT,
  ADD COLUMN IF NOT EXISTS dea_number TEXT,
  ADD COLUMN IF NOT EXISTS bio TEXT;

-- 2. Enhance providers table with UUID default and doctor clinical identifiers
ALTER TABLE public.providers
  ALTER COLUMN id SET DEFAULT gen_random_uuid();

ALTER TABLE public.providers
  ADD COLUMN IF NOT EXISTS title TEXT,
  ADD COLUMN IF NOT EXISTS npi_number TEXT,
  ADD COLUMN IF NOT EXISTS dea_number TEXT,
  ADD COLUMN IF NOT EXISTS bio TEXT;

CREATE INDEX IF NOT EXISTS idx_providers_tenant_deleted ON public.providers(tenant_id, is_deleted);
CREATE INDEX IF NOT EXISTS idx_clinics_npi ON public.clinics(npi_number);
CREATE INDEX IF NOT EXISTS idx_providers_npi ON public.providers(npi_number);
