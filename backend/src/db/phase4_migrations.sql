-- ============================================================
-- Phase 4 Database Migrations
-- Run these in Supabase SQL Editor (one section at a time)
-- ============================================================

-- ============================================================
-- MIGRATION 1: notifications_config column in clinics
-- (SaaS standard: JSONB config stored per-tenant)
-- ============================================================
ALTER TABLE clinics
ADD COLUMN IF NOT EXISTS notifications_config JSONB DEFAULT '{
  "reminders_enabled": true,
  "recall_enabled": true,
  "followup_enabled": true,
  "insurance_enabled": true
}'::jsonb;


-- ============================================================
-- MIGRATION 2: clinic_users table (role-based access control)
-- Referenced by auth_router but missing from schema
-- ============================================================
CREATE TABLE IF NOT EXISTS clinic_users (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id         UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  supabase_user_id  UUID        NOT NULL,
  role              TEXT        DEFAULT 'owner'
    CHECK (role IN ('owner', 'doctor', 'front_desk', 'read_only')),
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(clinic_id, supabase_user_id)
);

CREATE INDEX IF NOT EXISTS idx_clinic_users_user ON clinic_users(supabase_user_id);
CREATE INDEX IF NOT EXISTS idx_clinic_users_clinic ON clinic_users(clinic_id);


-- ============================================================
-- MIGRATION 3: audit_logs table
-- Referenced by audit_service but missing from schema
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id     UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  user_id       TEXT,
  user_email    TEXT,
  action        TEXT        NOT NULL,
  ip_address    TEXT,
  user_agent    TEXT,
  details       JSONB       DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_clinic ON audit_logs(clinic_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action  ON audit_logs(action, created_at DESC);


-- ============================================================
-- MIGRATION 4: sessions table
-- Referenced by session_service but missing from schema
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       TEXT        NOT NULL,
  user_email    TEXT,
  clinic_id     UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  ip_address    TEXT,
  user_agent    TEXT,
  is_active     BOOLEAN     DEFAULT true,
  last_seen_at  TIMESTAMPTZ DEFAULT NOW(),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user   ON sessions(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_clinic ON sessions(clinic_id, is_active);


-- ============================================================
-- MIGRATION 5: Seed phone_pool with the existing Twilio number
-- This makes +15755734355 available for assignment
-- ============================================================
INSERT INTO phone_pool (phone_number, is_assigned, assigned_to, assigned_at)
VALUES ('+15755734355', false, NULL, NULL)
ON CONFLICT (phone_number) DO NOTHING;


-- ============================================================
-- VERIFY: Check all tables exist
-- ============================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
  'clinics', 'patients', 'appointments', 'calls',
  'sms_messages', 'jobs', 'revenue_events', 'waitlist',
  'phone_pool', 'clinic_users', 'audit_logs', 'sessions'
)
ORDER BY table_name;

-- Expected: 12 rows
