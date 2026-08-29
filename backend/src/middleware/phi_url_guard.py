"""
PHI URL Guard Middleware
HIPAA Rule: No PHI in URLs.
This middleware intercepts requests and rejects them if they contain patterns resembling PHI in the URL.
"""
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Simple patterns to detect potential PHI in URL
# Note: UUIDs (like patient_id) are not considered PHI.
# These patterns detect things like raw phone numbers, SSNs, or dates of birth.
PHI_PATTERNS = [
    re.compile(r'\b\d{10,14}\b'),               # Raw Phone numbers (e.g. 1234567890)
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),         # DOB (YYYY-MM-DD)
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),         # SSN
]

class PHIUrlGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        url_path = request.url.path
        
        # Check URL path for raw phone numbers or SSNs (UUIDs/IDs are exempt)
        for pattern in PHI_PATTERNS[:1] + PHI_PATTERNS[2:]: # Phone & SSN
            if pattern.search(url_path):
                return JSONResponse(
                    {
                        "error": "PHI_DETECTED_IN_URL",
                        "message": "HIPAA Policy Violation: PHI detected in URL path. Use request body instead."
                    }, 
                    status_code=400
                )

        response = await call_next(request)
        return response
