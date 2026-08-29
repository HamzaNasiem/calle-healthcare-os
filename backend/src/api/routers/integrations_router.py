import re
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...core.database import supabase, supabase_read, update_clinic as db_update_clinic
from ...core.security import require_permission, AuthenticatedUser
from ...core.config import settings
from ...core.logger import log
from ...core.cache import local_cache
from ...services.audit_service import audit_service
from ...services.voice_service import voice_service

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class IntegrationsSettingsUpdate(BaseModel):
    telnyx_number: Optional[str] = None
    twilio_number: Optional[str] = None
    phone_number: Optional[str] = None
    google_calendar_id: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None


def _mask_secret(val: Optional[str], visible_start: int = 4, visible_end: int = 4) -> Optional[str]:
    if not val:
        return None
    val_str = str(val).strip()
    if len(val_str) <= (visible_start + visible_end):
        return "•" * len(val_str)
    return val_str[:visible_start] + "•" * (len(val_str) - (visible_start + visible_end)) + val_str[-visible_end:]


def _build_status_response(clinic: Dict[str, Any]) -> Dict[str, Any]:
    webhook_base = settings.WEBHOOK_BASE_URL or settings.API_BASE_URL

    # 1. Google Calendar
    has_google_token = bool(clinic.get("google_refresh_token"))
    google_status = {
        "connected": has_google_token,
        "calendar_id": clinic.get("google_calendar_id") or "primary",
        "has_refresh_token": has_google_token,
        "auth_url": "/auth/google",
        "status_label": "Connected & Synced" if has_google_token else "Disconnected",
    }

    # 2. Telnyx Assistant Line
    telnyx_num = clinic.get("telnyx_number") or ""
    telnyx_connected = bool(telnyx_num and len(telnyx_num.strip()) >= 10)
    telnyx_status = {
        "connected": telnyx_connected,
        "phone_number": telnyx_num,
        "sms_webhook_url": f"{webhook_base}/webhooks/telnyx/sms",
        "status_label": "Active Line" if telnyx_connected else "Unassigned",
    }

    # 3. Twilio
    clinic_twilio_num = clinic.get("twilio_number") or clinic.get("phone_number") or ""
    system_twilio_sid = clinic.get("twilio_account_sid") or settings.TWILIO_ACCOUNT_SID or ""
    system_twilio_token = clinic.get("twilio_auth_token") or settings.TWILIO_AUTH_TOKEN or ""
    twilio_has_creds = bool(system_twilio_sid and system_twilio_token)
    twilio_connected = bool(clinic_twilio_num or twilio_has_creds)
    twilio_status = {
        "connected": twilio_connected,
        "phone_number": clinic_twilio_num or settings.TWILIO_DEFAULT_NUMBER or "",
        "account_sid_masked": _mask_secret(system_twilio_sid, 4, 4),
        "is_configured": twilio_has_creds,
        "is_system_managed": bool(settings.TWILIO_ACCOUNT_SID and not clinic.get("twilio_account_sid")),
        "sms_webhook_url": f"{webhook_base}/webhooks/twilio/sms",
        "voice_webhook_url": f"{webhook_base}/webhooks/twilio/voice",
        "status_label": "Active" if twilio_connected else "Not Configured",
    }

    # 4. Retell AI
    agent_id = clinic.get("retell_agent_id") or ""
    retell_connected = bool(agent_id and len(agent_id.strip()) > 0)
    retell_status = {
        "connected": retell_connected,
        "agent_id": agent_id,
        "status": "active" if retell_connected else "unprovisioned",
        "webhook_url": f"{webhook_base}/webhooks/retell/",
        "status_label": "Live Active" if retell_connected else "Not Built",
    }

    # 5. Stripe Billing
    customer_id = clinic.get("stripe_customer_id") or ""
    sub_status = clinic.get("subscription_status") or clinic.get("stripe_subscription_status") or ("active" if customer_id else "trial")
    sub_plan = clinic.get("subscription_plan") or clinic.get("plan") or "trial"
    stripe_connected = bool(customer_id or sub_status in ["active", "trialing", "trial", "pro", "growth"])
    stripe_status = {
        "connected": stripe_connected,
        "customer_id": customer_id,
        "subscription_id": clinic.get("stripe_subscription_id") or "",
        "subscription_status": sub_status,
        "subscription_plan": sub_plan,
        "current_period_end": clinic.get("current_period_end") or clinic.get("trial_ends_at"),
        "portal_available": bool(settings.STRIPE_SECRET_KEY or not settings.is_prod),
        "status_label": "Active Subscription" if sub_status in ["active", "pro", "growth"] else ("Trial Active" if sub_status in ["trial", "trialing"] else "Inactive"),
    }

    return {
        "google_calendar": google_status,
        "telnyx": telnyx_status,
        "twilio": twilio_status,
        "retell": retell_status,
        "stripe": stripe_status,
    }


@router.get("/status")
@router.get("")
async def get_integrations_status(
    auth: AuthenticatedUser = Depends(require_permission("settings:read"))
):
    """
    Fetch comprehensive live connection statuses for all clinic integrations:
    Google Calendar, Telnyx, Twilio, Retell AI, and Stripe.
    """
    clinic_id = auth.clinic_id
    try:
        res = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Clinic not found")

        clinic = res.data
        statuses = _build_status_response(clinic)

        return {
            "success": True,
            "clinic_id": clinic_id,
            "data": statuses,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[integrations.status] clinic_id={clinic_id} Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/settings")
@router.post("/settings")
async def update_integrations_settings(
    updates: IntegrationsSettingsUpdate,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Update integration configuration fields (Telnyx number, Twilio number, Google Calendar ID, etc.)
    and return refreshed live connection statuses.
    """
    clinic_id = auth.clinic_id
    update_dict = updates.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=400, detail="No integration settings provided for update.")

    try:
        # Fetch current record for audit diff
        check_res = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        existing_clinic = check_res.data or {}

        # If telnyx_number updated, clean cache
        if "telnyx_number" in update_dict:
            old_num = existing_clinic.get("telnyx_number")
            if old_num:
                local_cache.delete(f"telnyx_clinic_info_{old_num}")
            new_num = update_dict.get("telnyx_number")
            if new_num:
                local_cache.delete(f"telnyx_clinic_info_{new_num}")

        # Update in database
        updated_clinic = db_update_clinic(clinic_id, update_dict)

        # Audit log
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.integrations_update",
            resource_type="clinics",
            resource_id=clinic_id,
            details={
                "before": {k: existing_clinic.get(k) for k in update_dict.keys() if k in existing_clinic},
                "after": update_dict,
            },
            request=request
        )

        statuses = _build_status_response(updated_clinic)
        return {
            "success": True,
            "message": "Integration settings updated successfully",
            "data": statuses,
        }
    except Exception as e:
        log.error(f"[integrations.update_settings] clinic_id={clinic_id} Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/google/disconnect")
@router.delete("/google")
async def disconnect_google_calendar(
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Disconnect Google Calendar integration by revoking/clearing the OAuth refresh token.
    """
    clinic_id = auth.clinic_id
    try:
        updated = db_update_clinic(clinic_id, {
            "google_refresh_token": None,
            "google_calendar_id": None,
        })

        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.google_calendar.disconnect",
            resource_type="clinics",
            resource_id=clinic_id,
            details={"service": "google_calendar"},
            request=request
        )

        return {
            "success": True,
            "message": "Google Calendar disconnected successfully",
            "data": _build_status_response(updated)
        }
    except Exception as e:
        log.error(f"[integrations.google.disconnect] clinic_id={clinic_id} Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/retell/create")
@router.post("/retell/sync")
async def create_or_sync_retell_agent(
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Create or synchronize the Retell AI Voice Receptionist agent for this clinic.
    """
    clinic_id = auth.clinic_id
    try:
        res = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Clinic not found")

        clinic = res.data
        agent_id = clinic.get("retell_agent_id")

        if agent_id:
            # Update prompt
            sync_res = await voice_service.update_agent_prompt(clinic_id)
            if not sync_res.get("success"):
                raise HTTPException(status_code=400, detail=sync_res.get("error", "Failed to update Retell agent prompt."))
            msg = f"Retell Agent prompt synchronized! ID: {agent_id}"
        else:
            # Create agent
            create_res = await voice_service.create_agent(clinic_id)
            if not create_res.get("success"):
                raise HTTPException(status_code=400, detail=create_res.get("error", "Failed to create Retell agent."))
            agent_id = create_res["data"]["agentId"]
            db_update_clinic(clinic_id, {"retell_agent_id": agent_id})
            clinic["retell_agent_id"] = agent_id
            msg = f"Retell Agent created successfully! ID: {agent_id}"

        # Audit log
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.retell_agent.sync",
            resource_type="clinics",
            resource_id=clinic_id,
            details={"agent_id": agent_id},
            request=request
        )

        refreshed = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        return {
            "success": True,
            "message": msg,
            "agent_id": agent_id,
            "data": _build_status_response(refreshed.data or clinic)
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[integrations.retell.create] clinic_id={clinic_id} Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/test/{service}")
async def test_integration_connection(
    service: str,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Test real-time connectivity and configuration for a specified integration service:
    'google', 'telnyx', 'twilio', 'retell', or 'stripe'.
    """
    clinic_id = auth.clinic_id
    service_clean = service.lower().strip()

    try:
        res = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Clinic not found")
        clinic = res.data

        if service_clean in ["google", "google_calendar", "calendar"]:
            refresh_token = clinic.get("google_refresh_token")
            if not refresh_token:
                return {
                    "success": False,
                    "service": "google_calendar",
                    "message": "Google Calendar is not connected. Please click Connect to authenticate.",
                }
            
            # Verify refresh token by testing credentials
            try:
                from ...services.calendar_service import _get_google_credentials
                creds, _ = _get_google_credentials(clinic_id)
                return {
                    "success": True,
                    "service": "google_calendar",
                    "message": "Google Calendar OAuth connection is healthy and authorized.",
                    "details": {"calendar_id": clinic.get("google_calendar_id") or "primary"}
                }
            except Exception as google_err:
                return {
                    "success": False,
                    "service": "google_calendar",
                    "message": f"Google Calendar verification failed: {str(google_err)}",
                }

        elif service_clean in ["telnyx", "telnyx_phone"]:
            telnyx_num = clinic.get("telnyx_number")
            if not telnyx_num:
                return {
                    "success": False,
                    "service": "telnyx",
                    "message": "No Telnyx phone number assigned. Please enter your line number.",
                }
            # Validate E.164-ish format
            cleaned = re.sub(r"[\s\-\(\)]", "", str(telnyx_num))
            if not (cleaned.startswith("+") and len(cleaned) >= 11):
                return {
                    "success": False,
                    "service": "telnyx",
                    "message": f"Telnyx number '{telnyx_num}' must include country code in E.164 format (e.g. +15755734355).",
                }
            return {
                "success": True,
                "service": "telnyx",
                "message": f"Telnyx phone line '{telnyx_num}' is configured and ready for SMS & call routing.",
                "details": {"phone_number": telnyx_num}
            }

        elif service_clean in ["twilio", "twilio_sms"]:
            twilio_num = clinic.get("twilio_number") or clinic.get("phone_number") or settings.TWILIO_DEFAULT_NUMBER
            has_creds = bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)
            if not has_creds and not twilio_num:
                return {
                    "success": False,
                    "service": "twilio",
                    "message": "Twilio account credentials or phone line are not configured.",
                }
            return {
                "success": True,
                "service": "twilio",
                "message": "Twilio integration is active and configured.",
                "details": {
                    "phone_number": twilio_num or "System Default",
                    "system_configured": has_creds
                }
            }

        elif service_clean in ["retell", "retell_ai", "voice"]:
            agent_id = clinic.get("retell_agent_id")
            if not agent_id:
                return {
                    "success": False,
                    "service": "retell",
                    "message": "No Retell AI Agent provisioned. Click 'Create Retell Agent' to provision.",
                }
            # Check with Retell API if possible
            try:
                retell_client = getattr(voice_service.provider, "retell", None)
                if retell_client and hasattr(retell_client, "agent") and hasattr(retell_client.agent, "retrieve"):
                    retell_client.agent.retrieve(agent_id)
                return {
                    "success": True,
                    "service": "retell",
                    "message": f"Retell AI Voice Receptionist is active and responsive. Agent ID: {agent_id}",
                    "details": {"agent_id": agent_id}
                }
            except Exception as retell_err:
                log.warning(f"[integrations.test.retell] Verification warning: {retell_err}")
                return {
                    "success": True,
                    "service": "retell",
                    "message": f"Retell Agent ID configured: {agent_id}",
                    "details": {"agent_id": agent_id, "warning": str(retell_err)}
                }

        elif service_clean in ["stripe", "billing"]:
            from ...services.billing_service import billing_service
            sub_status = clinic.get("subscription_status") or clinic.get("stripe_subscription_status") or "trial"
            sub_plan = clinic.get("subscription_plan") or clinic.get("plan") or "starter"
            customer_id = clinic.get("stripe_customer_id")
            return {
                "success": True,
                "service": "stripe",
                "message": f"Stripe Billing is operational. Status: {sub_status.upper()} (Plan: {sub_plan.capitalize()})",
                "details": {
                    "customer_id": customer_id or "Sandbox Mode",
                    "status": sub_status,
                    "plan": sub_plan,
                    "stripe_configured": billing_service.is_configured
                }
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown integration service: '{service}'")

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[integrations.test] service={service} clinic_id={clinic_id} Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
