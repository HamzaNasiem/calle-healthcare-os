-- ============================================================
-- Bytelytic Clinic OS — Distributed Locks Schema
-- Supabase SQL Editor mein yeh SQL run karo
-- ============================================================

-- 1. Create the distributed_locks table
CREATE TABLE IF NOT EXISTS public.distributed_locks (
    lock_key    TEXT        PRIMARY KEY,
    locked_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);

-- 2. Index for scanning expired locks
CREATE INDEX IF NOT EXISTS idx_distributed_locks_expiry
    ON public.distributed_locks (expires_at);

-- 3. Function to atomically acquire a lock with a lease expiry
CREATE OR REPLACE FUNCTION public.acquire_distributed_lock(lock_key text, lease_seconds int)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  -- Cleanup any locks that have already expired
  DELETE FROM public.distributed_locks WHERE expires_at < now();
  
  -- Try to insert the new lock
  BEGIN
    INSERT INTO public.distributed_locks (lock_key, expires_at)
    VALUES (lock_key, now() + (lease_seconds || ' seconds')::interval);
    RETURN true;
  EXCEPTION WHEN unique_violation THEN
    -- Lock is already held and has not expired
    RETURN false;
  END;
END;
$$;

-- 4. Function to release a lock
CREATE OR REPLACE FUNCTION public.release_distributed_lock(lock_key text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  DELETE FROM public.distributed_locks WHERE distributed_locks.lock_key = release_distributed_lock.lock_key;
END;
$$;
