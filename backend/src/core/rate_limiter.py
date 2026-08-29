import time

from fastapi import HTTPException, Request, status

from src.core.cache import local_cache


class RateLimiter:
    def __init__(self, requests: int, window_seconds: int):
        self.requests = requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request):
        # Use X-Forwarded-For if available (for load balancers), otherwise client host
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "127.0.0.1"

        route_path = request.url.path
        key = f"ratelimit:{route_path}:{ip}"
        
        # Simple token bucket / fixed window using the cache
        current_data = local_cache.get(key)
        now = time.time()
        
        if not current_data:
            # First request
            local_cache.set(key, {"count": 1, "reset": now + self.window_seconds}, ttl=self.window_seconds)
            remaining = self.requests - 1
            reset_time = int(now + self.window_seconds)
        else:
            count = current_data["count"]
            reset_time = current_data["reset"]
            
            if now > reset_time:
                # Window expired, reset
                local_cache.set(key, {"count": 1, "reset": now + self.window_seconds}, ttl=self.window_seconds)
                remaining = self.requests - 1
                reset_time = int(now + self.window_seconds)
            else:
                if count >= self.requests:
                    # Rate limit exceeded
                    headers = {
                        "X-RateLimit-Limit": str(self.requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(reset_time))
                    }
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded",
                        headers=headers
                    )
                # Increment count
                current_data["count"] += 1
                ttl = int(reset_time - now)
                if ttl > 0:
                    local_cache.set(key, current_data, ttl=ttl)
                remaining = self.requests - current_data["count"]

        # We can't easily inject headers into the final response from a Dependency without modifying the Response object.
        # But we can store them in request.state and add a middleware to append them.
        request.state.ratelimit_limit = self.requests
        request.state.ratelimit_remaining = remaining
        request.state.ratelimit_reset = int(reset_time)

# Pre-configured dependencies
login_limiter = RateLimiter(requests=5, window_seconds=900)  # 5 req / 15 min
mfa_limiter = RateLimiter(requests=10, window_seconds=900)   # 10 req / 15 min
api_limiter = RateLimiter(requests=1000, window_seconds=60)  # 1000 req / 1 min
