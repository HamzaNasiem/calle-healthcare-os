import asyncio
import datetime
from .database import supabase

class DistributedLock:
    def __init__(self, key: str, lease_seconds: int = 30, timeout: float = 10.0, retry_interval: float = 0.5):
        """
        Distributed lock context manager using database-backed locks.
        
        Usage:
            async with DistributedLock("lock_name"):
                # critical write section
        """
        self.key = key
        self.lease_seconds = lease_seconds
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.acquired = False

    async def __aenter__(self):
        elapsed = 0.0
        while elapsed < self.timeout:
            try:
                # Call RPC in Supabase
                res = supabase.rpc("acquire_distributed_lock", {
                    "lock_key": self.key,
                    "lease_seconds": self.lease_seconds
                }).execute()
                
                # If Supabase RPC returns true, lock is successfully acquired
                if res.data is True:
                    self.acquired = True
                    return self
            except Exception as e:
                err_str = str(e).lower()
                # Resilient fallback: if the database migration hasn't been applied yet, 
                # log a warning and bypass the lock rather than crashing the application.
                if "does not exist" in err_str or "method not allowed" in err_str or "404" in err_str or "could not find the function" in err_str or "pgrst202" in err_str:
                    print(f"[lock.warning] acquire_distributed_lock RPC does not exist. "
                          f"Please apply the create_distributed_locks.sql migration in the Supabase SQL editor.")
                    self.acquired = True
                    return self
                print(f"[lock.error] Exception while acquiring lock for key {self.key}: {e}")
                
            await asyncio.sleep(self.retry_interval)
            elapsed += self.retry_interval
            
        raise TimeoutError(f"Could not acquire distributed lock for key: {self.key} within {self.timeout}s")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            try:
                # Call release RPC
                supabase.rpc("release_distributed_lock", {
                    "lock_key": self.key
                }).execute()
            except Exception as e:
                err_str = str(e).lower()
                # Ignore missing RPC errors during release fallback
                if "does not exist" in err_str or "method not allowed" in err_str or "404" in err_str or "could not find the function" in err_str or "pgrst202" in err_str:
                    pass
                else:
                    print(f"[lock.error] Exception while releasing lock for key {self.key}: {e}")
