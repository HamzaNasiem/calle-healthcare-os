"""
agency_router.py — Phase 8: White Label Agency Management

Allows Bytelytic admins to create, manage and brand agency accounts.
Clinics can be assigned to agencies which then customise the UI/branding
via their custom_domain.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ...core.cache import local_cache
from ...core.config import settings
from ...core.database import supabase, supabase_read

from ...core.security import get_current_user_with_role, AuthenticatedUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agencies", tags=["Agencies"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class AgencyCreate(BaseModel):
    name: str
    support_email: Optional[str] = None
    custom_domain: Optional[str] = None
    logo_url: Optional[str] = None
    brand_color_primary: Optional[str] = "#1e3a8a"
    brand_color_secondary: Optional[str] = "#10b981"


class AgencyUpdate(BaseModel):
    name: Optional[str] = None
    support_email: Optional[str] = None
    custom_domain: Optional[str] = None
    logo_url: Optional[str] = None
    brand_color_primary: Optional[str] = None
    brand_color_secondary: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Admin Auth Dependency (reused from admin_router pattern)
# ─────────────────────────────────────────────────────────────────────────────

async def require_admin(request: Request) -> Any:
    """
    Validates the caller is a Bytelytic super-admin.
    Accepts either an X-Admin-Key header or a Bearer JWT belonging to
    an email listed in settings.ADMIN_EMAILS.
    """
    # Check X-Admin-Key header first
    admin_key = request.headers.get("X-Admin-Key")
    if admin_key and getattr(settings, "ADMIN_API_KEY", None):
        if admin_key == settings.ADMIN_API_KEY:
            return {"email": "system_admin_api_key", "role": "admin"}

    # Fallback: Bearer JWT
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authentication credentials not found.")

    from fastapi.security.utils import get_authorization_scheme_param
    from ...core.security import get_current_user

    scheme, token = get_authorization_scheme_param(auth_header)
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme. Bearer required.")

    try:
        user = await get_current_user(type("Credentials", (), {"credentials": token})())
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(exc)}")

    email = user.get("email", "") if isinstance(user, dict) else getattr(user, "email", "")
    if email not in settings.ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")

    return user


# ─────────────────────────────────────────────────────────────────────────────
# Helper — run sync DB calls in executor
# ─────────────────────────────────────────────────────────────────────────────

async def _run(fn):
    """Execute a synchronous callable in a thread-pool executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("")
async def create_agency(body: AgencyCreate, _: Any = Depends(require_admin)):
    """Create a new agency (admin only)."""
    try:
        payload = body.model_dump(exclude_none=False)
        res = await _run(lambda: supabase.table("agencies").insert(payload).execute())
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create agency")
        return {"data": res.data[0]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("")
async def list_agencies(_: Any = Depends(require_admin)):
    """List all agencies (admin only)."""
    try:
        res = await _run(
            lambda: supabase_read.table("agencies").select("*").order("created_at", desc=True).execute()
        )
        return {"data": res.data or []}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/resolve-branding")
async def resolve_branding(domain: str = Query(..., description="Custom domain to look up")):
    """
    PUBLIC endpoint — resolve branding info for a custom domain.
    Used by white-labelled frontends to load their colour scheme / logo.
    Results are cached for 30 minutes.
    """
    cache_key = f"agency_domain_{domain}"
    cached = local_cache.get(cache_key)
    if cached is not None:
        return {"data": cached}

    try:
        res = await _run(
            lambda: supabase_read.table("agencies")
            .select("id, name, logo_url, brand_color_primary, brand_color_secondary, support_email, custom_domain")
            .eq("custom_domain", domain)
            .execute()
        )
        if res.data:
            branding = res.data[0]
            local_cache.set(cache_key, branding, ttl=1800)
            return {"data": branding}
        else:
            local_cache.set(cache_key, None, ttl=1800)
            return {"data": None}
    except Exception as exc:
        logger.warning("resolve_branding error for domain %s: %s", domain, exc)
        return {"data": None}


@router.get("/{agency_id}")
async def get_agency(
    agency_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_with_role)
):
    """
    Get agency details.
    Accessible to admins, or clinic owners/doctors/front desk if their clinic is assigned to this agency.
    """
    try:
        is_admin = auth.email in settings.ADMIN_EMAILS
        
        # If not admin, verify clinic is assigned to this agency
        if not is_admin:
            clinic_res = await _run(
                lambda: supabase_read.table("clinics")
                .select("agency_id")
                .eq("id", auth.clinic_id)
                .single()
                .execute()
            )
            if not clinic_res.data or clinic_res.data.get("agency_id") != agency_id:
                raise HTTPException(status_code=403, detail="Access denied: clinic is not assigned to this agency")
        
        res = await _run(
            lambda: supabase_read.table("agencies").select("*").eq("id", agency_id).execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Agency not found")
        return {"data": res.data[0]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/{agency_id}")
async def update_agency(
    agency_id: str,
    body: AgencyUpdate,
    auth: AuthenticatedUser = Depends(get_current_user_with_role)
):
    """
    Update agency details.
    Accessible to admins, or clinic owners if their clinic is assigned to this agency.
    """
    try:
        is_admin = auth.email in settings.ADMIN_EMAILS
        
        if not is_admin:
            if auth.role != "owner":
                raise HTTPException(status_code=403, detail="Access denied: owner role required")
            clinic_res = await _run(
                lambda: supabase_read.table("clinics")
                .select("agency_id")
                .eq("id", auth.clinic_id)
                .single()
                .execute()
            )
            if not clinic_res.data or clinic_res.data.get("agency_id") != agency_id:
                raise HTTPException(status_code=403, detail="Access denied: clinic is not assigned to this agency")

        payload = {k: v for k, v in body.model_dump().items() if v is not None}
        if not payload:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        res = await _run(
            lambda: supabase.table("agencies").update(payload).eq("id", agency_id).execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Agency not found")

        # Bust any cached domain entries for this agency
        updated = res.data[0]
        if updated.get("custom_domain"):
            local_cache.invalidate(f"agency_domain_{updated['custom_domain']}")

        return {"data": updated}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{agency_id}")
async def delete_agency(agency_id: str, _: Any = Depends(require_admin)):
    """Delete an agency (admin only)."""
    try:
        # Fetch domain before deletion so we can bust the cache
        fetch_res = await _run(
            lambda: supabase_read.table("agencies").select("custom_domain").eq("id", agency_id).execute()
        )
        custom_domain = None
        if fetch_res.data:
            custom_domain = fetch_res.data[0].get("custom_domain")

        await _run(lambda: supabase.table("agencies").delete().eq("id", agency_id).execute())

        if custom_domain:
            local_cache.invalidate(f"agency_domain_{custom_domain}")

        return {"data": {"deleted": True, "agency_id": agency_id}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{agency_id}/assign-clinic/{clinic_id}")
async def assign_clinic_to_agency(
    agency_id: str,
    clinic_id: str,
    _: Any = Depends(require_admin),
):
    """Assign a clinic to an agency by setting agency_id on the clinic row (admin only)."""
    try:
        res = await _run(
            lambda: supabase.table("clinics").update({"agency_id": agency_id}).eq("id", clinic_id).execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Clinic not found")
        return {"data": {"clinic_id": clinic_id, "agency_id": agency_id, "assigned": True}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
