import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request
from ..core.database import supabase
from ..core.logger import log, scrub_phi
from ..core.cache import local_cache


class AuditService:
    async def log(
        self,
        clinic_id: Optional[str],
        user_id: Optional[str],
        user_email: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        request: Optional[Request] = None
    ) -> None:
        """
        Structured logging for all sensitive user actions.
        Runs asynchronously to prevent blocking API responses.
        """
        ip_address = None
        user_agent = None

        if request:
            # Extract IP (considering reverse proxy like Railway/Cloudflare)
            for header in ["cf-connecting-ip", "x-real-ip", "x-forwarded-for", "true-client-ip"]:
                val = request.headers.get(header)
                if val:
                    ip_address = val.split(",")[0].strip()
                    break
            if not ip_address:
                ip_address = request.client.host if request.client else "127.0.0.1"

            # Extract User-Agent
            user_agent = request.headers.get("user-agent", "Web Browser")

        # Run database insert in background task to avoid blocking API
        asyncio.create_task(self._insert_log(
            clinic_id=clinic_id,
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        ))

    async def _insert_log(
        self,
        clinic_id: Optional[str],
        user_id: Optional[str],
        user_email: Optional[str],
        action: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        details: Optional[dict],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> None:
        try:
            # Clean clinic_id to handle empty strings
            c_id = clinic_id if clinic_id else "d3b07384-d113-46a6-a719-38cf89235d54"
            u_id = user_id if user_id else "demo-user-001"
            
            log_details = {}
            if details and isinstance(details, dict):
                for k, v in details.items():
                    log_details[k] = scrub_phi(v) if isinstance(v, str) else v

            if resource_type:
                log_details["resource_type"] = resource_type
            if resource_id:
                log_details["resource_id"] = resource_id

            entry_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()

            insert_data = {
                "id": entry_id,
                "clinic_id": c_id,
                "user_id": u_id,
                "user_email": user_email or "admin@sunriseclinic.com",
                "action": action,
                "details": log_details,
                "resource_type": resource_type or "audit",
                "resource_id": resource_id,
                "ip_address": ip_address or "127.0.0.1",
                "user_agent": user_agent or "Web Browser",
                "created_at": now_iso
            }
            
            # Immediately record in local_cache ring buffer for instantaneous reactivity
            cache_key = f"recent_audit_logs_{c_id}"
            recent = local_cache.get(cache_key) or []
            recent.insert(0, insert_data)
            local_cache.set(cache_key, recent[:200], ttl=3600)

            def _safe_uuid(val, default="d3b07384-d113-46a6-a719-38cf89235d54"):
                if not val:
                    return default
                try:
                    return str(uuid.UUID(str(val)))
                except Exception:
                    return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(val)))

            db_clinic_id = _safe_uuid(c_id)
            db_user_id = str(u_id) if u_id else "demo-user-001"

            db_insert_data = {
                "id": entry_id,
                "clinic_id": db_clinic_id,
                "user_id": db_user_id,
                "user_email": user_email or "admin@sunriseclinic.com",
                "action": action,
                "resource_type": resource_type or (log_details.get("resource_type") if log_details else None) or "audit",
                "resource_id": str(resource_id) if resource_id else None,
                "details": log_details,
                "ip_address": ip_address or "127.0.0.1",
                "user_agent": user_agent or "Web Browser",
                "created_at": now_iso
            }

            # Executed in a separate thread-pool since supabase-py is synchronous
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("audit_logs").insert(db_insert_data).execute()
            )
        except Exception as e:
            # Fail silently to prevent database errors from breaking the main flow
            log.warning(f"[AuditService] Failed to write audit log action='{action}': {str(e)}")

audit_service = AuditService()

