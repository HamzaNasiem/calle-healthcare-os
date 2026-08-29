-- ============================================================
-- Phase 5b Database Migrations
-- Bytelytic Clinic OS — Demo Mode & Referral Bonus Schema
-- RUN THIS IN: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Add is_demo and bonus_calls columns to clinics table
ALTER TABLE clinics
  ADD COLUMN IF NOT EXISTS is_demo     BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS bonus_calls INTEGER DEFAULT 0;

-- 2. Index on is_demo for quick cleanups
CREATE INDEX IF NOT EXISTS idx_clinics_is_demo ON clinics(is_demo) WHERE is_demo = TRUE;
