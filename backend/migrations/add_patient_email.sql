-- Migration: Add email_encrypted column to patients table
-- Date: 2026-08-16
-- Purpose: Enable HIPAA-compliant encrypted email storage for appointment confirmation emails

ALTER TABLE patients
ADD COLUMN IF NOT EXISTS email_encrypted BYTEA;

COMMENT ON COLUMN patients.email_encrypted IS 'AES-256-GCM encrypted patient email. Decrypt via phi_crypto.decrypt()';
