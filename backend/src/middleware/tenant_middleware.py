"""
Tenant Middleware
Extracts the tenant ID from the JWT token and binds it to the ContextVar.
"""
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.settings import settings
from src.core.tenant_context import set_tenant_id


class TenantMiddleware(BaseHTTPMiddleware):
    # Endpoints that don't require tenant context (e.g. webhooks, login, health)
    # Endpoints that don't require tenant context (e.g. webhooks, login, health)
    EXACT_EXEMPT_PATHS = {
        "/",
        "/health",
        "/health/detailed",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/mfa/verify",
        "/api/v1/auth/mfa/setup",
    }
    
    PREFIX_EXEMPT_PATHS = {
        "/webhooks/retell/",
        "/webhooks/telnyx/",
    }

    async def dispatch(self, request: Request, call_next):
        # Allow preflight OPTIONS requests to pass through to CORSMiddleware
        if request.method == "OPTIONS":
            return await call_next(request)

        # Webhook paths use different auth (signature verification)
        if request.url.path in self.EXACT_EXEMPT_PATHS or any(request.url.path.startswith(p) for p in self.PREFIX_EXEMPT_PATHS):
            return await call_next(request)

        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            return JSONResponse({"error": "Unauthorized: Missing Token"}, status_code=401)

        try:
            public_key = settings.jwt_public_key.replace('\\n', '\n')
            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            tenant_id = UUID(payload["tenant_id"])
            
            # Dedicated Clinic Mode Lockdown check
            if settings.DEDICATED_CLINIC_MODE and settings.DEFAULT_CLINIC_ID:
                try:
                    default_id = UUID(settings.DEFAULT_CLINIC_ID)
                    if tenant_id != default_id:
                        return JSONResponse({"error": "Forbidden: Request does not match dedicated clinic context"}, status_code=403)
                except ValueError:
                    pass # Skip if settings DEFAULT_CLINIC_ID is not a valid UUID string
            
            # Bind to this coroutine
            set_tenant_id(tenant_id)
            
            # Attach to request state for other middlewares if needed
            request.state.tenant_id = tenant_id
            request.state.user_id = UUID(payload["sub"])
            request.state.role = payload["role"]
            
        except Exception as e:
            return JSONResponse({"error": f"Invalid token: {str(e)}"}, status_code=401)

        response = await call_next(request)
        return response
