-- ============================================================
-- Phase 5 Database Migrations
-- Bytelytic Clinic OS — Billing & Referrals Schema Updates
-- ============================================================

-- 1. Alter clinics table to add Stripe SaaS columns
ALTER TABLE clinics
ADD COLUMN IF NOT EXISTS stripe_customer_id         TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS stripe_subscription_id     TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS stripe_subscription_status TEXT DEFAULT 'trailing'
  CHECK (stripe_subscription_status IN ('trailing', 'active', 'past_due', 'canceled', 'unpaid', 'incomplete')),
ADD COLUMN IF NOT EXISTS plan                       TEXT DEFAULT 'trial'
  CHECK (plan IN ('trial', 'starter', 'growth', 'pro')),
ADD COLUMN IF NOT EXISTS trial_ends_at              TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '14 days'),
ADD COLUMN IF NOT EXISTS billing_cycle_anchor       TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS referral_code              TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS trial_reminder_sent        BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS trial_ended_sent           BOOLEAN DEFAULT FALSE;

-- Create optimization indexes
CREATE INDEX IF NOT EXISTS idx_clinics_stripe_customer ON clinics(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_clinics_stripe_sub ON clinics(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_clinics_referral_code ON clinics(referral_code);

-- 2. Create referrals table for viral loops
CREATE TABLE IF NOT EXISTS referrals (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_code            TEXT        NOT NULL,
  referrer_clinic_id  UUID        NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
  referred_clinic_id  UUID        UNIQUE REFERENCES clinics(id) ON DELETE SET NULL,
  rewarded_at         TIMESTAMPTZ,
  status              TEXT        DEFAULT 'pending' CHECK (status IN ('pending', 'rewarded', 'expired')),
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Referral indexes
CREATE INDEX IF NOT EXISTS idx_referrals_lookup ON referrals(ref_code);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_clinic_id);

-- 3. Seed demo referral codes for existing clinic records
UPDATE clinics 
SET referral_code = UPPER(SUBSTRING(name FROM 1 FOR 3) || '-' || SUBSTRING(id::text FROM 1 FOR 4))
WHERE referral_code IS NULL;
