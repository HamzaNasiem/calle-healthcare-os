-- ============================================================
-- Bytelytic Clinic OS - Phase 10 Clinic Profile Migrations
-- ============================================================

ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS address TEXT DEFAULT '100 Michigan Avenue',
  ADD COLUMN IF NOT EXISTS suite TEXT DEFAULT 'Suite 400',
  ADD COLUMN IF NOT EXISTS state TEXT DEFAULT 'IL',
  ADD COLUMN IF NOT EXISTS zip_code TEXT DEFAULT '60601',
  ADD COLUMN IF NOT EXISTS emergency_protocols TEXT DEFAULT 'If caller reports chest pain, severe shortness of breath, sudden numbness, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest emergency department.',
  ADD COLUMN IF NOT EXISTS transfer_phone_number TEXT,
  ADD COLUMN IF NOT EXISTS telnyx_number TEXT;

-- Populate existing rows with clean defaults if null
UPDATE public.clinics
SET 
  address = COALESCE(address, '100 Michigan Avenue'),
  suite = COALESCE(suite, 'Suite 400'),
  state = COALESCE(state, 'IL'),
  zip_code = COALESCE(zip_code, '60601'),
  emergency_protocols = COALESCE(emergency_protocols, 'If caller reports chest pain, severe shortness of breath, sudden numbness, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest emergency department.'),
  transfer_phone_number = COALESCE(transfer_phone_number, phone_number, '+15551234567'),
  telnyx_number = COALESCE(telnyx_number, '+15755734355')
WHERE address IS NULL OR suite IS NULL OR state IS NULL OR zip_code IS NULL OR emergency_protocols IS NULL OR transfer_phone_number IS NULL;
