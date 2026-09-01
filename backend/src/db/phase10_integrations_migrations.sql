-- ============================================================
-- Bytelytic Clinic OS - Phase 10 Integrations & Telephony Migrations
-- ============================================================

-- 1. Ensure telnyx_number exists on clinics table
ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS telnyx_number TEXT;

-- 2. Populate telnyx_number from phone_number where null
UPDATE public.clinics
  SET telnyx_number = phone_number
  WHERE telnyx_number IS NULL AND phone_number IS NOT NULL;

-- 3. Ensure calle_api_key_enc and calle_enabled exist
ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS calle_api_key_enc TEXT,
  ADD COLUMN IF NOT EXISTS calle_enabled BOOLEAN DEFAULT TRUE;
