"""
PHI Audit Middleware
Logs every read access to PHI endpoints.
"""
import traceback

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.services.audit_service import audit_service


class PHIAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # We log after the response is generated to record the outcome
        # In a real app, this logic can be moved to specific dependencies to be more precise about fields accessed.
        # This is a global fallback.
        
        # Only log reads (GET) here. Writes (POST/PATCH/DELETE) should be logged directly in the endpoint
        # or via SQLAlchemy session events to ensure they only log if the transaction commits.
        if request.method == "GET" and any(route in request.url.path for route in ["/api/patients", "/api/appointments", "/api/call-logs"]):
            
            # Determine target table based on route
            target_table = "patients"
            if "/api/appointments" in request.url.path:
                target_table = "appointments"
            elif "/api/call-logs" in request.url.path:
                target_table = "call_logs"
                
            try:
                user_id = getattr(request.state, "user_id", None)
                role = getattr(request.state, "role", None)
                
                await audit_service.log(
                    action="READ",
                    target_table=target_table,
                    actor_id=user_id,
                    actor_type="staff_user" if user_id else "unknown",
                    actor_role=role,
                    ingress_ip=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent"),
                    fields_accessed=["*"], # Since it's a GET, we assume all exposed fields were read
                    outcome="SUCCESS" if response.status_code < 400 else "ERROR"
                )
            except Exception:
                # We don't fail the request if audit logging fails (or maybe we should? HIPAA might require it)
                print(f"CRITICAL: Failed to write audit log: {traceback.format_exc()}")
                
        return response
