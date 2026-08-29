"""
CALL-E Database Migration Script
--------------------------------
Applies schema migrations for CALL-E integration:
- Creates/updates `outbound_calls` table and indexes
- Creates `calle_campaigns` table and indexes
- Adds `calle_api_key_enc`, `calle_enabled`, `calle_webhook_secret` to `clinics` table
- Writes the SQL migration file for manual Supabase SQL Editor execution
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor

SUPABASE_URL = "https://aabbhuzlzjkosqmvhysm.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFhYmJodXpsemprb3NxbXZoeXNtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjEwNDY5NCwiZXhwIjoyMDkxNjgwNjk0fQ.b-rgkvqEaPfxz96G1XkpsNN02Y39osqAORu1FHntrbk"
LOCAL_DB_URL = os.getenv("SUPABASE_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/bytelytic_clinic_db")
MIGRATION_SQL_PATH = r"D:\projects\bytelytic-os-single\backend\migrations\add_calle_tables.sql"

SQL_CONTENT = """-- Migration: Add CALL-E tables and clinic columns
-- Run in Supabase SQL Editor or against PostgreSQL directly

-- 1. Ensure required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Create outbound_calls table if not exists
CREATE TABLE IF NOT EXISTS outbound_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    campaign_type VARCHAR(50) NOT NULL CHECK (campaign_type IN ('confirmation', 'recall', 'no_show', 'survey')),
    calle_call_id VARCHAR(255) UNIQUE,
    idempotency_key VARCHAR(500) UNIQUE,
    phone_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'no_answer')),
    task_completed BOOLEAN DEFAULT FALSE,
    completion_score FLOAT,
    completion_label VARCHAR(100),
    structured_result JSONB DEFAULT '{}',
    summary TEXT DEFAULT '',
    appointment_id UUID,
    patient_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT outbound_calls_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
);

-- Ensure all outbound_calls columns exist if table was already present
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS phone_hash VARCHAR(64);
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS completion_score FLOAT;
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS completion_label VARCHAR(100);
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS structured_result JSONB DEFAULT '{}';
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS summary TEXT DEFAULT '';
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS task_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- Outbound calls indexes
CREATE INDEX IF NOT EXISTS idx_outbound_calls_clinic ON outbound_calls(clinic_id);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_status ON outbound_calls(status);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_calle_id ON outbound_calls(calle_call_id);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_idempotency ON outbound_calls(idempotency_key);

-- 3. Create calle_campaigns table
CREATE TABLE IF NOT EXISTS calle_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    campaign_type VARCHAR(50) NOT NULL CHECK (campaign_type IN ('confirmation', 'recall', 'no_show', 'survey')),
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'running', 'completed', 'paused', 'failed')),
    patient_filter JSONB DEFAULT '{}',
    task_template TEXT NOT NULL,
    result_schema JSONB NOT NULL DEFAULT '{}',
    total_patients INTEGER DEFAULT 0,
    calls_completed INTEGER DEFAULT 0,
    calls_confirmed INTEGER DEFAULT 0,
    calls_rescheduled INTEGER DEFAULT 0,
    calls_failed INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID,
    CONSTRAINT calle_campaigns_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
);

-- Calle campaigns indexes
CREATE INDEX IF NOT EXISTS idx_calle_campaigns_clinic ON calle_campaigns(clinic_id);
CREATE INDEX IF NOT EXISTS idx_calle_campaigns_status ON calle_campaigns(status);

-- 4. Add CALL-E columns to clinics table
ALTER TABLE clinics ADD COLUMN IF NOT EXISTS calle_api_key_enc TEXT;
ALTER TABLE clinics ADD COLUMN IF NOT EXISTS calle_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE clinics ADD COLUMN IF NOT EXISTS calle_webhook_secret TEXT;
"""


def test_supabase_direct():
    print("[1/4] Checking remote Supabase API / RPC / Direct DDL capability...")
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        # Check basic connectivity
        res = sb.table("clinics").select("id").limit(1).execute()
        print(f"  -> Supabase REST query succeeded. Found records: {len(res.data)}")
    except Exception as e:
        print(f"  -> Supabase direct/REST connection skipped/failed: {e}")
        print("  -> Note: PostgREST API does not support raw DDL execution (CREATE TABLE/ALTER TABLE). Direct SQL editor or Postgres connection is required.")


def save_sql_file():
    print("[2/4] Saving SQL migration script...")
    os.makedirs(os.path.dirname(MIGRATION_SQL_PATH), exist_ok=True)
    with open(MIGRATION_SQL_PATH, "w", encoding="utf-8") as f:
        f.write(SQL_CONTENT.strip() + "\n")
    print(f"  -> Saved migration to: {MIGRATION_SQL_PATH}")


def run_local_migrations():
    print(f"[3/4] Connecting to local PostgreSQL at: {LOCAL_DB_URL}...")
    try:
        conn = psycopg2.connect(LOCAL_DB_URL)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("  -> Connected successfully.")

        print("  -> Executing DDL migrations...")
        cur.execute(SQL_CONTENT)
        print("  -> DDL statements executed successfully.")

        print("[4/4] Verifying schema...")
        # Verify outbound_calls columns
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'outbound_calls'
            ORDER BY ordinal_position;
        """)
        outbound_cols = [r["column_name"] for r in cur.fetchall()]
        print(f"  -> outbound_calls columns ({len(outbound_cols)}): {', '.join(outbound_cols)}")

        # Verify calle_campaigns columns
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'calle_campaigns'
            ORDER BY ordinal_position;
        """)
        campaign_cols = [r["column_name"] for r in cur.fetchall()]
        print(f"  -> calle_campaigns columns ({len(campaign_cols)}): {', '.join(campaign_cols)}")

        # Verify clinics columns
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'clinics' AND column_name IN ('calle_api_key_enc', 'calle_enabled', 'calle_webhook_secret')
            ORDER BY column_name;
        """)
        clinic_calle_cols = [f"{r['column_name']} ({r['data_type']})" for r in cur.fetchall()]
        print(f"  -> clinics CALL-E columns: {', '.join(clinic_calle_cols)}")

        # Verify indexes
        cur.execute("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE tablename IN ('outbound_calls', 'calle_campaigns')
            ORDER BY tablename, indexname;
        """)
        indexes = [f"{r['tablename']}.{r['indexname']}" for r in cur.fetchall()]
        print(f"  -> Created Indexes ({len(indexes)}): {', '.join(indexes)}")

        cur.close()
        conn.close()
        return True, {
            "outbound_calls_cols": outbound_cols,
            "calle_campaigns_cols": campaign_cols,
            "clinics_calle_cols": clinic_calle_cols,
            "indexes": indexes,
        }
    except Exception as e:
        print(f"  -> ERROR running local migrations: {e}")
        return False, str(e)


if __name__ == "__main__":
    test_supabase_direct()
    save_sql_file()
    success, result = run_local_migrations()
    if success:
        print("\n=== MIGRATION COMPLETED SUCCESSFULLY ===")
    else:
        print(f"\n=== MIGRATION FAILED: {result} ===")
        sys.exit(1)
