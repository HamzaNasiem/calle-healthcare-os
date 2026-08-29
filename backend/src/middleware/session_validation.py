from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.settings import settings
from src.core.cache import local_cache


class SessionValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce strict 3-minute idle timeout using Redis/LocalCache TTL.
    Validates that the session ID has not expired or been revoked.
    """
    EXEMPT_PATHS = {
        "/health", "/health/detailed", "/", "/metrics",
        "/docs", "/openapi.json", "/redoc",
        "/webhooks/retell/", "/webhooks/telnyx/",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/mfa/verify",
        "/api/v1/auth/mfa/setup",
    }

    async def dispatch(self, request: Request, call_next):
        # Allow preflight OPTIONS requests to pass through to CORSMiddleware
        if request.method == "OPTIONS":
            return await call_next(request)

        # Webhook and health paths don't require session validation
        if any(request.url.path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)

        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            return await call_next(request) # Let TenantMiddleware handle missing token

        # Check token blacklist (logout)
        if local_cache.get(f"blacklist_{token}"):
            return JSONResponse({"error": "Session revoked. Please log in again."}, status_code=401)

        try:
            public_key = settings.jwt_public_key.replace('\\n', '\n')
            # Don't fail here on decode, let TenantMiddleware handle normal validation
            # We just want to extract sid for idle timeout enforcement
            payload = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_exp": False})
            session_id = payload.get("sid")
            
            if not session_id:
                return JSONResponse({"error": "Invalid token payload: missing session ID"}, status_code=401)
                
            # Check idle timeout in cache
            session_key = f"sess_active:{session_id}"
            
            is_active = local_cache.get(session_key)
            if not is_active:
                # Idle timeout reached
                return JSONResponse({"error": "Session expired due to inactivity. Please log in again."}, status_code=401)
            
            # Refresh idle timeout (3 mins = 180 seconds)
            local_cache.set(session_key, "active", ttl=180)

        except Exception:
            # Let TenantMiddleware handle actual verification errors
            pass
            
        return await call_next(request)
