from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Any, List
from pydantic import BaseModel

from ...core.database import supabase, supabase_read, update_clinic, invalidate_clinic_cache
from ...core.security import get_current_user
from ...core.config import settings
from ...services.audit_service import audit_service

router = APIRouter(prefix="/admin", tags=["Admin"])

async def require_admin(request: Request) -> Any:
    """
    Dependency that ensures the caller is a Bytelytic admin.
    Supports either:
    1. A valid X-Admin-Key API key header.
    2. A valid Bearer JWT session belonging to an email in ADMIN_EMAILS.
    Optionally restricts access to an IP whitelist defined in ADMIN_IP_WHITELIST_STR.
    """
    # 1. IP Whitelist check first if configured
    whitelist_str = getattr(settings, "ADMIN_IP_WHITELIST_STR", None)
    if whitelist_str:
        allowed_ips = [ip.strip() for ip in whitelist_str.split(",") if ip.strip()]
        if allowed_ips:
            x_forwarded_for = request.headers.get("x-forwarded-for")
            ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else (request.client.host if request.client else "unknown")
            if ip not in allowed_ips:
                raise HTTPException(status_code=403, detail=f"IP address {ip} is not authorized for admin access.")

    # 2. Check X-Admin-Key API key header
    admin_key = request.headers.get("X-Admin-Key")
    if admin_key and getattr(settings, "ADMIN_API_KEY", None):
        if admin_key == settings.ADMIN_API_KEY:
            return {"email": "system_admin_api_key", "role": "admin"}

    # 3. Fallback to standard Bearer JWT validation
    from ...core.security import get_current_user
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authentication credentials not found.")
        
    from fastapi.security.utils import get_authorization_scheme_param
    scheme, token = get_authorization_scheme_param(auth_header)
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme. Bearer required.")
        
    try:
        user = await get_current_user(type("Credentials", (), {"credentials": token})())
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")

    email = user.get("email", "") if isinstance(user, dict) else getattr(user, "email", "")
    if email not in settings.ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    return user


@router.get("/clinics")
async def list_all_clinics(user: Any = Depends(require_admin)):
    """List all clinics with usage stats — admin only."""
    try:
        clinics_res = supabase_read.table("clinics").select(
            "id, name, owner_email, specialty, city, timezone, is_active, "
            "phone_number, retell_agent_id, google_refresh_token, created_at"
        ).order("created_at", desc=True).execute()
        
        raw_clinics = clinics_res.data or []
        
        # Filter out clinics owned by super admins
        admin_emails_lower = [email.lower().strip() for email in settings.ADMIN_EMAILS]
        clinics = [c for c in raw_clinics if c.get("owner_email", "").lower().strip() not in admin_emails_lower]
        
        # Enrich each clinic with call count and revenue
        enriched = []
        for clinic in clinics:
            cid = clinic["id"]
            
            # Calls this month using read replica
            from datetime import datetime, timezone
            month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
            calls_res = supabase_read.table("calls").select("id", count="exact").eq("clinic_id", cid).gte("created_at", month_start).execute()
            
            # Revenue total using read replica
            rev_res = supabase_read.table("revenue_events").select("amount_cents").eq("clinic_id", cid).execute()
            total_cents = sum(r.get("amount_cents", 0) for r in (rev_res.data or []))
            
            # Patient count using read replica
            patients_res = supabase_read.table("patients").select("id", count="exact").eq("clinic_id", cid).execute()
            
            enriched.append({
                **clinic,
                "calls_this_month": calls_res.count or 0,
                "total_revenue_dollars": total_cents // 100,
                "patient_count": patients_res.count or 0,
                "google_connected": bool(clinic.get("google_refresh_token")),
                "agent_configured": bool(clinic.get("retell_agent_id")),
            })
        
        return {"data": enriched, "total": len(enriched)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def global_stats(user: Any = Depends(require_admin)):
    """Global platform stats — admin only."""
    try:
        from datetime import datetime, timezone
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
        
        # Fetch all clinics to filter out super admin clinics (using read replica)
        clinics_res = supabase_read.table("clinics").select("id, is_active, owner_email").execute()
        clinics = clinics_res.data or []
        
        admin_emails_lower = [email.lower().strip() for email in settings.ADMIN_EMAILS]
        filtered_clinics = [c for c in clinics if c.get("owner_email", "").lower().strip() not in admin_emails_lower]
        
        total_count = len(filtered_clinics)
        active_count = sum(1 for c in filtered_clinics if c.get("is_active", True))
        
        # Filter calls & revenue to only non-admin clinics
        filtered_cids = [c["id"] for c in filtered_clinics]
        
        calls_count = 0
        total_cents = 0
        
        if filtered_cids:
            calls_month = supabase_read.table("calls").select("id", count="exact").in_("clinic_id", filtered_cids).gte("created_at", month_start).execute()
            calls_count = calls_month.count or 0
            
            revenue = supabase_read.table("revenue_events").select("amount_cents").in_("clinic_id", filtered_cids).execute()
            total_cents = sum(r.get("amount_cents", 0) for r in (revenue.data or []))
        
        return {
            "data": {
                "totalClinics": total_count,
                "activeClinics": active_count,
                "callsThisMonth": calls_count,
                "totalRevenueDollars": total_cents // 100,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clinics/{id}/suspend")
async def suspend_clinic(id: str, request: Request, user: Any = Depends(require_admin)):
    """Suspend a clinic — stops all AI features."""
    try:
        # Check if the clinic belongs to a Super Admin (using read replica)
        c_res = supabase_read.table("clinics").select("owner_email").eq("id", id).single().execute()
        if c_res.data:
            owner_email = c_res.data.get("owner_email", "")
            if owner_email.strip().lower() in [email.lower().strip() for email in settings.ADMIN_EMAILS]:
                raise HTTPException(status_code=400, detail="Cannot suspend a Super Admin's testing clinic")
                
        update_clinic(id, {"is_active": False})
        
        # Audit log clinic suspension
        admin_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        await audit_service.log(
            clinic_id=id,
            user_id=None,
            user_email=admin_email,
            action="admin.suspend_clinic",
            resource_type="clinics",
            resource_id=id,
            details={"suspended": True},
            request=request
        )
        return {"success": True, "message": f"Clinic {id} suspended"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clinics/{id}/activate")
async def activate_clinic(id: str, request: Request, user: Any = Depends(require_admin)):
    """Activate a suspended clinic."""
    try:
        # Check if the clinic belongs to a Super Admin (using read replica)
        c_res = supabase_read.table("clinics").select("owner_email").eq("id", id).single().execute()
        if c_res.data:
            owner_email = c_res.data.get("owner_email", "")
            if owner_email.strip().lower() in [email.lower().strip() for email in settings.ADMIN_EMAILS]:
                raise HTTPException(status_code=400, detail="Cannot modify a Super Admin's testing clinic")
                
        update_clinic(id, {"is_active": True})
        
        # Audit log clinic activation
        admin_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        await audit_service.log(
            clinic_id=id,
            user_id=None,
            user_email=admin_email,
            action="admin.activate_clinic",
            resource_type="clinics",
            resource_id=id,
            details={"activated": True},
            request=request
        )
        return {"success": True, "message": f"Clinic {id} activated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/phone-pool")
async def get_phone_pool(user: Any = Depends(require_admin)):
    """View all numbers in the phone pool."""
    try:
        res = supabase_read.table("phone_pool").select("*").order("created_at").execute()
        numbers = res.data or []
        available = sum(1 for n in numbers if not n.get("is_assigned"))
        return {
            "data": numbers,
            "total": len(numbers),
            "available": available,
            "low_pool": available < 3,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/phone-pool")
async def add_to_phone_pool(body: dict, request: Request, user: Any = Depends(require_admin)):
    """Add a Twilio number to the phone pool."""
    phone_number = body.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="phone_number is required")
    try:
        res = supabase.table("phone_pool").insert({"phone_number": phone_number}).execute()
        added_record = res.data[0]
        
        # Audit log phone addition
        admin_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        await audit_service.log(
            clinic_id=None,
            user_id=None,
            user_email=admin_email,
            action="admin.add_to_phone_pool",
            resource_type="phone_pool",
            resource_id=None,
            details={"phone_number": phone_number},
            request=request
        )
        return {"success": True, "data": added_record}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clinics/{id}/staff")
async def get_clinic_staff(id: str, user: Any = Depends(require_admin)):
    """Get all staff members of a specific clinic — admin only."""
    try:
        res = supabase_read.table("clinic_users").select("*").eq("clinic_id", id).execute()
        staff_records = res.data or []
        
        enriched_staff = []
        try:
            users_res = supabase.auth.admin.list_users()
            all_users = {str(u.id): u for u in users_res}
        except Exception:
            all_users = {}

        for record in staff_records:
            uid = str(record["supabase_user_id"])
            u = all_users.get(uid)
            email = u.email if u else f"User {uid[:8]}..."
            name = u.user_metadata.get("name", "Staff Member") if u and getattr(u, 'user_metadata', None) else "Staff Member"
            
            enriched_staff.append({
                "id": record["id"],
                "user_id": uid,
                "role": record["role"],
                "email": email,
                "name": name,
                "created_at": record["created_at"]
            })
        return {"data": enriched_staff}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clinics/{id}")
async def delete_clinic(id: str, request: Request, user: Any = Depends(require_admin)):
    """Delete a clinic permanently — admin only."""
    try:
        # Check if the clinic belongs to a Super Admin (using read replica)
        c_res = supabase_read.table("clinics").select("owner_email").eq("id", id).single().execute()
        owner_email = None
        if c_res.data:
            owner_email = c_res.data.get("owner_email", "")
            if owner_email.strip().lower() in [email.lower().strip() for email in settings.ADMIN_EMAILS]:
                raise HTTPException(status_code=400, detail="Cannot delete a Super Admin's testing clinic")
        
        supabase.table("clinics").delete().eq("id", id).execute()
        invalidate_clinic_cache(id, owner_email)
        
        # Audit log clinic deletion
        admin_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        await audit_service.log(
            clinic_id=id,
            user_id=None,
            user_email=admin_email,
            action="admin.delete_clinic",
            resource_type="clinics",
            resource_id=id,
            details={"owner_email": owner_email},
            request=request
        )
        return {"success": True, "message": f"Clinic {id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs")
async def get_audit_logs(user: Any = Depends(require_admin)):
    """Get all platform-wide audit logs — admin only."""
    try:
        res = supabase_read.table("audit_logs").select(
            "id, clinic_id, user_id, user_email, action, ip_address, user_agent, details, created_at"
        ).order("created_at", desc=True).limit(100).execute()
        
        logs = res.data or []
        
        # Get clinic names to enrich logs (using read replica)
        if logs:
            clinic_ids = list(set(log["clinic_id"] for log in logs if log.get("clinic_id")))
            if clinic_ids:
                clinics_res = supabase_read.table("clinics").select("id, name").in_("id", clinic_ids).execute()
                clinics_map = {c["id"]: c["name"] for c in (clinics_res.data or [])}
                for log in logs:
                    log["clinic_name"] = clinics_map.get(log.get("clinic_id"), "System/Unknown")
            else:
                for log in logs:
                    log["clinic_name"] = "System/Unknown"
        return {"data": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


