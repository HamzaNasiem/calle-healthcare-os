import time
import threading
import json
import redis
from typing import Any, Dict, Optional, Tuple
from .config import settings
from .logger import log

class LocalCache:
    def __init__(self, default_ttl: int = 60):
        self.default_ttl = default_ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                val, expiry = self._cache[key]
                if time.time() < expiry:
                    return val
                else:
                    del self._cache[key]  # Expired
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl_val = ttl if ttl is not None else self.default_ttl
        with self._lock:
            self._cache[key] = (value, time.time() + ttl_val)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys_to_del = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in keys_to_del:
                self._cache.pop(k, None)

    def delete(self, key: str) -> None:
        self.invalidate(key)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class RedisOrLocalCache:
    def __init__(self):
        self.redis_client = None
        self.local = LocalCache(default_ttl=300)
        
        redis_url = getattr(settings, "REDIS_URL", None)
        if redis_url:
            try:
                self.redis_client = redis.Redis.from_url(redis_url, socket_timeout=2.0)
                # Test connection
                self.redis_client.ping()
                log.info("Successfully connected to Redis cache.")
            except Exception as e:
                log.warning(f"Failed to connect to Redis at {redis_url}: {e}. Falling back to local cache.")
                self.redis_client = None

    def get(self, key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                val = self.redis_client.get(key)
                if val:
                    return json.loads(val.decode('utf-8'))
            except Exception as e:
                log.warning(f"Redis get failed: {e}. Falling back to local cache.")
        return self.local.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl_val = ttl if ttl is not None else 300 # Default 5 mins
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl_val, json.dumps(value))
                return
            except Exception as e:
                log.warning(f"Redis set failed: {e}. Falling back to local cache.")
        self.local.set(key, value, ttl=ttl_val)

    def invalidate(self, key: str) -> None:
        if self.redis_client:
            try:
                self.redis_client.delete(key)
                return
            except Exception as e:
                log.warning(f"Redis delete failed: {e}.")
        self.local.invalidate(key)

    def invalidate_prefix(self, prefix: str) -> None:
        if self.redis_client:
            try:
                keys = self.redis_client.keys(f"{prefix}*")
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                log.warning(f"Redis delete prefix failed: {e}.")
        self.local.invalidate_prefix(prefix)

    def delete(self, key: str) -> None:
        self.invalidate(key)

    def clear(self) -> None:
        if self.redis_client:
            try:
                self.redis_client.flushdb()
                return
            except Exception as e:
                log.warning(f"Redis flushdb failed: {e}.")
        self.local.clear()

# Instantiate globally as local_cache to remain fully backwards compatible
local_cache = RedisOrLocalCache()

def invalidate_dashboard_stats(clinic_id: str) -> None:
    local_cache.invalidate_prefix(f"dashboard_stats_{clinic_id}")
