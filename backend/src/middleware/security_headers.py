from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    Implements HSTS, CSP, X-Frame-Options, X-Content-Type-Options, and X-XSS-Protection.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Clickjacking, MIME Sniffing, XSS protection
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        path = request.url.path
        if path in ["/docs", "/redoc", "/openapi.json"] or path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
            
        if request.url.hostname not in ["localhost", "127.0.0.1"]:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
            
        # Prevent caching of PHI on API routes
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Vary"] = "*"
            
            # Force remove ETag if present so proxies can't revalidate
            if "etag" in response.headers:
                del response.headers["etag"]
            
        return response
