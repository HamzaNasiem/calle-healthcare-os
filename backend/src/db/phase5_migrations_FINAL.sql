-- ============================================================
-- Phase 5 FINAL Database Migrations
-- Bytelytic Clinic OS — Billing & Referrals Schema
-- RUN THIS IN: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Add all billing columns to clinics table
--    Using IF NOT EXISTS so it is safe to run multiple times

ALTER TABLE clinics
  ADD COLUMN IF NOT EXISTS stripe_customer_id         TEXT,
  ADD COLUMN IF NOT EXISTS stripe_subscription_id     TEXT,
  ADD COLUMN IF NOT EXISTS stripe_subscription_status TEXT DEFAULT 'trialing',
  ADD COLUMN IF NOT EXISTS plan                       TEXT DEFAULT 'trial',
  ADD COLUMN IF NOT EXISTS trial_ends_at              TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '14 days'),
  ADD COLUMN IF NOT EXISTS billing_cycle_anchor       TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS referral_code              TEXT,
  ADD COLUMN IF NOT EXISTS quota_warning_sent         BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS sms_warning_sent           BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS trial_reminder_sent        BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS trial_ended_sent           BOOLEAN DEFAULT FALSE;

-- 2. Add CHECK constraints (run separately if above already ran)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'clinics_stripe_subscription_status_check'
  ) THEN
    ALTER TABLE clinics
      ADD CONSTRAINT clinics_stripe_subscription_status_check
      CHECK (stripe_subscription_status IN ('trialing', 'active', 'past_due', 'canceled', 'unpaid', 'incomplete'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'clinics_plan_check'
  ) THEN
    ALTER TABLE clinics
      ADD CONSTRAINT clinics_plan_check
      CHECK (plan IN ('trial', 'starter', 'growth', 'pro'));
  END IF;
END $$;

-- 3. Create performance indexes
CREATE INDEX IF NOT EXISTS idx_clinics_stripe_customer ON clinics(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clinics_stripe_sub      ON clinics(stripe_subscription_id) WHERE stripe_subscription_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clinics_referral_code   ON clinics(referral_code) WHERE referral_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clinics_plan            ON clinics(plan);

-- 4. Back-fill existing rows with trial defaults
UPDATE clinics
SET
  stripe_subscription_status = 'trialing',
  plan                       = 'trial',
  trial_ends_at              = created_at + INTERVAL '14 days',
  billing_cycle_anchor       = created_at,
  quota_warning_sent         = FALSE,
  sms_warning_sent           = FALSE,
  trial_reminder_sent        = FALSE,
  trial_ended_sent           = FALSE
WHERE plan IS NULL;

-- 5. Generate referral codes for all existing clinics that don't have one
UPDATE clinics
SET referral_code = UPPER(
  SUBSTRING(REGEXP_REPLACE(name, '[^a-zA-Z0-9]', '', 'g') FROM 1 FOR 3)
  || '-' ||
  SUBSTRING(id::text FROM 1 FOR 6)
)
WHERE referral_code IS NULL;

-- 6. Create the referrals table for viral growth tracking
CREATE TABLE IF NOT EXISTS referrals (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_code            TEXT        NOT NULL,
  referrer_clinic_id  UUID        NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
  referred_clinic_id  UUID        REFERENCES clinics(id) ON DELETE SET NULL,
  rewarded_at         TIMESTAMPTZ,
  status              TEXT        DEFAULT 'pending' CHECK (status IN ('pending', 'rewarded', 'expired')),
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referrals_ref_code  ON referrals(ref_code);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer  ON referrals(referrer_clinic_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred  ON referrals(referred_clinic_id) WHERE referred_clinic_id IS NOT NULL;

-- ============================================================
-- VERIFY: Run this SELECT to confirm all columns now exist
-- ============================================================
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'clinics'
--   AND column_name IN (
--     'stripe_customer_id', 'stripe_subscription_id', 'stripe_subscription_status',
--     'plan', 'trial_ends_at', 'billing_cycle_anchor', 'referral_code',
--     'quota_warning_sent', 'sms_warning_sent', 'trial_reminder_sent', 'trial_ended_sent'
--   )
-- ORDER BY column_name;
