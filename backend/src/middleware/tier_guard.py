from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.config.settings import settings

class TierGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # We only protect API routes
        if not request.url.path.startswith('/api/v1/'):
            return await call_next(request)

        tier = settings.CLINIC_TIER

        # Define tier restrictions
        # Tier 1 = Basic (No bulk SMS, no advanced analytics)
        # Tier 2 = Pro (Includes bulk SMS)
        # Tier 3 = Enterprise (Everything)
        
        path = request.url.path

        if tier < 2:
            # Block bulk SMS endpoints or campaigns
            if '/campaigns' in path or '/bulk' in path:
                return JSONResponse({"error": "Forbidden: Requires Tier 2 or higher"}, status_code=403)
        
        if tier < 3:
            # Block advanced analytics/exports
            if '/export' in path or '/advanced-stats' in path:
                return JSONResponse({"error": "Forbidden: Requires Tier 3 (Enterprise)"}, status_code=403)

        response = await call_next(request)
        return response
