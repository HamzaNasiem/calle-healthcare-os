from pydantic import BaseModel
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from ...core.database import supabase, supabase_read
from ...core.security import require_permission, AuthenticatedUser, require_active_subscription
from ...services.notification_service import notification_service

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    dependencies=[Depends(require_active_subscription)]
)


class TestAlertRequest(BaseModel):
    alert_type: str = "staff.alert"
    title: Optional[str] = "Test Staff Notification Alert"
    body: Optional[str] = "This is a simulated verification test from your Bytelytic OS Notification Settings."
    metadata: Optional[Dict[str, Any]] = None


class NotificationConfigUpdate(BaseModel):
    notifications_config: Dict[str, Any]


DEFAULT_NOTIFICATIONS_CONFIG = {
    "booking_confirmation_enabled": True,
    "cancellation_confirmation_enabled": True,
    "reminders_enabled": True,
    "recall_enabled": True,
    "followup_enabled": True,
    "insurance_enabled": True,
    "email_daily_report_enabled": True,
    "email_quota_alerts_enabled": True,
    "email_staff_alerts_enabled": True,
    "staff_alert_email": "",
    "staff_alert_phone": "",
    "alert_on_negative_sentiment": True,
    "alert_on_missed_calls": True,
    "alert_on_noshow": True,
    "sound_alerts_enabled": True,
    "browser_notifications_enabled": False,
    "reminder_lead_time_hours": 24,
    "reminder_sms_template": "Hi {patient_name}, your appointment at {clinic_name} is confirmed for {datetime}. Reply CONFIRM or CANCEL.",
    "quiet_hours_enabled": True,
    "quiet_hours_start": "21:00",
    "quiet_hours_end": "08:00",
}


@router.get("")
async def get_notifications(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
    limit: int = Query(20, ge=1, le=50),
    unread_only: bool = Query(False),
):
    """Fetch latest notifications for the clinic."""
    clinic_id = auth.clinic_id
    try:
        query = (
            supabase_read.table("notifications")
            .select("id, type, title, body, metadata, resource_type, resource_id, is_read, created_at")
            .eq("clinic_id", clinic_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if unread_only:
            query = query.eq("is_read", False)

        res = query.execute()
        unread_count_res = (
            supabase_read.table("notifications")
            .select("id", count="exact")
            .eq("clinic_id", clinic_id)
            .eq("is_read", False)
            .execute()
        )
        return {
            "data": res.data or [],
            "unread_count": unread_count_res.count or 0,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/test-alert")
async def send_test_alert(
    payload: TestAlertRequest,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:write")),
):
    """Trigger a live simulated test alert through staff notification routing channels."""
    clinic_id = auth.clinic_id
    try:
        routing_outcome = await notification_service.trigger_test_alert(
            clinic_id=clinic_id,
            alert_type=payload.alert_type,
            title=payload.title or "Staff Notification Test",
            body=payload.body or "Verification alert from Bytelytic OS settings.",
            metadata=payload.metadata or {},
        )
        return {
            "success": True,
            "message": "Test alert created and routed through notification channels.",
            "routed": routing_outcome.get("routed", False),
            "routed_to_email": routing_outcome.get("routed_to_email"),
            "routed_to_phone": routing_outcome.get("routed_to_phone"),
            "reason": routing_outcome.get("reason"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/config")
async def get_notification_config(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
):
    """Fetch current clinic notification preferences configuration."""
    clinic_id = auth.clinic_id
    try:
        res = supabase_read.table("clinics").select("notifications_config, business_hours, owner_email, primary_doctor_phone, timezone").eq("id", clinic_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Clinic not found")
        
        c = res.data
        conf = c.get("notifications_config")
        if not isinstance(conf, dict):
            b_hrs = c.get("business_hours") or {}
            conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
        if not isinstance(conf, dict):
            conf = {}

        merged = {**DEFAULT_NOTIFICATIONS_CONFIG, **conf}
        
        return {
            "data": {
                **merged,
                "_defaults": {
                    "owner_email": c.get("owner_email"),
                    "doctor_phone": c.get("primary_doctor_phone"),
                    "timezone": c.get("timezone") or "America/New_York",
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/config")
async def update_notification_config(
    payload: NotificationConfigUpdate,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:write")),
):
    """Update clinic notification preferences configuration."""
    clinic_id = auth.clinic_id
    try:
        merged = {**DEFAULT_NOTIFICATIONS_CONFIG, **payload.notifications_config}
        res = supabase.table("clinics").update({
            "notifications_config": merged
        }).eq("id", clinic_id).execute()
        return {"success": True, "data": merged}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
):
    """Mark a single notification as read."""
    success = await notification_service.mark_read(auth.clinic_id, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.post("/read-all")
async def mark_all_notifications_read(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
):
    """Mark all notifications as read for the clinic."""
    await notification_service.mark_all_read(auth.clinic_id)
    return {"success": True}

