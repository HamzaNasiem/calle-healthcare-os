"""
calle_router.py — CALL-E Outbound Campaign API Router

Endpoints:
  GET  /calle/status                          — CALL-E connection status
  GET  /calle/campaigns/estimates             — Live backlog queue counts & cost estimates for all 5 campaigns
  POST /calle/campaigns/confirmation          — Batch: confirm tomorrow's appointments
  POST /calle/campaigns/no-show              — Batch: no-show follow-ups for today
  POST /calle/campaigns/recall               — Batch: recall patients (30/60/90 days)
  POST /calle/campaigns/survey               — Batch: post-visit surveys for today
  POST /calle/campaigns/waitlist             — Batch: waitlist backfill for open slots
  POST /calle/calls/single                   — Trigger single test/live call (supports live wait)
  GET  /calle/calls                          — List all outbound calls + status
  GET  /calle/calls/{record_id}              — Get single call detail + live status update
  GET  /calle/calls/{calle_call_id}/events   — Developer-facing call event stream
  GET  /calle/goals                          — List published goals (CALL-E API 0.6.0)
  POST /calle/goals/{goal_id}/runs           — Execute Goal Run with variables
  GET  /calle/goals/{goal_id}/runs/{run_id}  — Fetch Goal Run execution result
  POST /calle/webhook                        — CALL-E terminal result webhook
  POST /calle/inbound                        — Inbound dynamic AI voice receptionist

HIPAA:
  - No PHI (patient name, phone, DOB) written to stdout logs.
  - All calls tracked in 'outbound_calls' Supabase table.
  - Every trigger action logged to audit_logs.
  - Only 'owner' and 'admin' roles can trigger campaigns.
"""

import uuid
import re
import hmac
import hashlib
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query, Header
from pydantic import BaseModel

from ...core.database import supabase, supabase_read
from ...core.security import require_permission, AuthenticatedUser, require_role, require_active_subscription
from ...services.calle_service import calle_service
from ...services.audit_service import audit_service
from ...config.settings import settings
from ...ws.manager import tenant_room_manager

log = logging.getLogger(__name__)

# Webhook ingestion endpoints (/webhook, /inbound) are public/signature-verified.
# Management and campaign routes enforce explicit auth & subscription dependencies.
router = APIRouter(
    prefix="/calle",
    tags=["CALL-E Outbound Campaigns"],
)


# ── Pydantic Models ────────────────────────────────────────────────────────────

class SingleCallRequest(BaseModel):
    appointment_id: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    phone: str
    campaign_type: str  # confirmation | no_show | recall | survey | waitlist
    clinic_name: Optional[str] = None
    time_str: Optional[str] = None
    days_since_last_visit: Optional[int] = 30
    recall_type: Optional[str] = "routine follow-up"
    slot_date: Optional[str] = None
    slot_time: Optional[str] = None
    region: str = "US"
    wait_for_completion: bool = False


class RecallCampaignRequest(BaseModel):
    days_threshold: int = 30  # 30, 60, or 90
    recall_type: str = "routine follow-up"
    limit: int = 20  # max patients to call in one batch


class WaitlistCampaignRequest(BaseModel):
    slot_date: Optional[str] = None
    slot_time: Optional[str] = None
    limit: int = 15


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalize_phone_e164(raw: Optional[str], default_country: str = "+1") -> str:
    """
    Normalizes any phone number format to standard E.164 (+1XXXXXXXXXX).
    Handles (555) 123-4567, 5551234567, 15551234567, +15551234567, and international numbers.
    """
    if not raw:
        return ""
    cleaned = str(raw).strip()
    has_plus = cleaned.startswith("+")
    digits = re.sub(r"[^\d]", "", cleaned)
    if not digits:
        return ""
    if has_plus:
        return f"+{digits}"
    if len(digits) == 10:
        return f"{default_country}{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


def _verify_calle_auth(request: Request, body_event_id: Optional[str] = None) -> bool:
    """
    Verifies CALL-E webhook authenticity per official docs (https://docs.heycall-e.com/webhooks).
    - Checks for CALL-E-Event-Id header matching body event ID.
    - Also accepts Authorization: Bearer or signature headers if configured.
    """
    event_id_header = request.headers.get("CALL-E-Event-Id") or request.headers.get("call-e-event-id")
    if event_id_header:
        if body_event_id and event_id_header != body_event_id:
            log.warning("[CalleWebhook] Event ID header mismatch: header=%s, body=%s", event_id_header, body_event_id)
            return False
        return True

    expected_secret = (
        getattr(settings, "calle_webhook_secret", None)
        or getattr(settings, "CALLE_API_KEY", None)
        or getattr(settings, "calle_api_key", None)
    )
    if not expected_secret:
        return True

    auth_header = request.headers.get("Authorization", "")
    sig_header = request.headers.get("X-Calle-Signature", "") or request.headers.get("X-Webhook-Secret", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if hmac.compare_digest(token, str(expected_secret)):
            return True

    if sig_header and hmac.compare_digest(sig_header, str(expected_secret)):
        return True

    # All signature checks failed — reject the request
    return False


def _build_idempotency_key(campaign_type: str, clinic_id: str, ref_id: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{campaign_type}_{clinic_id[:8]}_{ref_id[:8]}_{date_str}_{uuid.uuid4().hex[:4]}"


async def _save_outbound_call(
    clinic_id: str,
    campaign_type: str,
    result: dict,
    appointment_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    idempotency_key: str = "",
) -> str:
    """Insert outbound call record into Supabase. Returns record ID."""
    record_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    structured = result.get("structured_result") or {}
    status = result.get("status", "unknown")
    calle_id = result.get("id") or result.get("call_id")
    conf = result.get("completion_confidence") or {}

    record = {
        "id": record_id,
        "clinic_id": clinic_id,
        "campaign_type": campaign_type,
        "calle_call_id": str(calle_id) if calle_id else None,
        "idempotency_key": idempotency_key,
        "status": status,
        "task_completed": result.get("task_completed", False),
        "completion_score": conf.get("score") if isinstance(conf, dict) else None,
        "completion_label": conf.get("label") if isinstance(conf, dict) else None,
        "structured_result": structured,
        "summary": result.get("summary", ""),
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "created_at": now_iso,
        "completed_at": now_iso if status in ("completed", "failed") else None,
    }

    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("outbound_calls").insert(record).execute()
        )
        # Auto-update appointment status if confirmed or reschedule requested
        if campaign_type == "confirmation" and appointment_id and structured:
            will_attend = str(structured.get("will_attend", "")).lower()
            if will_attend in ("yes", "confirmed", "true"):
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("appointments")
                        .update({"status": "confirmed"})
                        .eq("id", appointment_id)
                        .execute()
                )
            elif will_attend in ("no", "rescheduled", "reschedule"):
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("appointments")
                        .update({"status": "rescheduled_requested"})
                        .eq("id", appointment_id)
                        .execute()
                )
    except Exception as exc:
        log.warning("[CalleRouter] DB save warning: %s", type(exc).__name__)

    return record_id


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_calle_status(
    auth: AuthenticatedUser = Depends(require_permission("settings:read")),
):
    """Check CALL-E connection and engine status."""
    return {
        "configured": settings.calle_configured,
        "live_mode": calle_service.is_live(),
        "dry_run": calle_service.is_dry_run(),
        "sdk_available": calle_service.client is not None,
        "mode": "live" if calle_service.is_live() else "dry_run",
        "api_version": "0.6.0",
        "campaigns_supported": [
            "confirmation",
            "no_show",
            "recall",
            "survey",
            "waitlist",
        ],
    }


@router.get("/campaigns/estimates")
async def get_campaign_estimates(
    auth: AuthenticatedUser = Depends(require_permission("calls:read")),
):
    """
    Computes real backlog queue counts and estimated dispatch costs for all 5 automated campaigns.
    """
    clinic_id = auth.clinic_id
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).date()
    today = now.date()

    counts = {
        "confirmation": 0,
        "no_show": 0,
        "recall_30": 0,
        "recall_60": 0,
        "recall_90": 0,
        "survey": 0,
        "waitlist": 0,
    }

    try:
        # 1. Tomorrow's appointments (confirmation)
        res_conf = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
                .select("id", count="exact")
                .eq("clinic_id", clinic_id)
                .gte("datetime", f"{tomorrow}T00:00:00")
                .lte("datetime", f"{tomorrow}T23:59:59")
                .in_("status", ["scheduled", "pending"])
                .execute()
        )
        counts["confirmation"] = res_conf.count or len(res_conf.data or [])
    except Exception:
        pass

    try:
        # 2. Today's no-shows
        res_ns = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
                .select("id", count="exact")
                .eq("clinic_id", clinic_id)
                .gte("datetime", f"{today}T00:00:00")
                .lte("datetime", f"{today}T23:59:59")
                .eq("status", "no_show")
                .execute()
        )
        counts["no_show"] = res_ns.count or len(res_ns.data or [])
    except Exception:
        pass

    try:
        # 3. Recall (30/60/90 days)
        for threshold, key in [(30, "recall_30"), (60, "recall_60"), (90, "recall_90")]:
            cutoff = (now - timedelta(days=threshold)).date()
            res_rec = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda c=cutoff: supabase_read.table("appointments")
                    .select("id", count="exact")
                    .eq("clinic_id", clinic_id)
                    .eq("status", "completed")
                    .gte("datetime", f"{c - timedelta(days=7)}T00:00:00")
                    .lte("datetime", f"{c}T23:59:59")
                    .execute()
            )
            counts[key] = res_rec.count or len(res_rec.data or [])
    except Exception:
        pass

    try:
        # 4. Today's completed (survey)
        res_surv = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
                .select("id", count="exact")
                .eq("clinic_id", clinic_id)
                .gte("datetime", f"{today}T00:00:00")
                .lte("datetime", f"{today}T23:59:59")
                .eq("status", "completed")
                .execute()
        )
        counts["survey"] = res_surv.count or len(res_surv.data or [])
    except Exception:
        pass

    try:
        # 5. Waitlist entries
        res_wl = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("waitlist")
                .select("id", count="exact")
                .eq("clinic_id", clinic_id)
                .in_("status", ["active", "pending", "waiting"])
                .execute()
        )
        counts["waitlist"] = res_wl.count or len(res_wl.data or [])
    except Exception:
        counts["waitlist"] = 0

    cost_per_call = 0.07  # ~$0.07 avg CALL-E rate per completed call
    total_queued = (
        counts["confirmation"]
        + counts["no_show"]
        + counts["recall_30"]
        + counts["survey"]
        + counts["waitlist"]
    )

    return {
        "counts": counts,
        "total_queued": total_queued,
        "cost_per_call": cost_per_call,
        "estimated_total_cost": round(total_queued * cost_per_call, 2),
        "campaigns": {
            "confirmation": {"queue_count": counts["confirmation"], "estimated_cost": round(counts["confirmation"] * cost_per_call, 2)},
            "no_show": {"queue_count": counts["no_show"], "estimated_cost": round(counts["no_show"] * cost_per_call, 2)},
            "recall": {"queue_count": counts["recall_30"], "estimated_cost": round(counts["recall_30"] * cost_per_call, 2)},
            "survey": {"queue_count": counts["survey"], "estimated_cost": round(counts["survey"] * cost_per_call, 2)},
            "waitlist": {"queue_count": counts["waitlist"], "estimated_cost": round(counts["waitlist"] * cost_per_call, 2)},
        }
    }


@router.get("/calls")
async def list_outbound_calls(
    auth: AuthenticatedUser = Depends(require_permission("calls:read")),
    campaign_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    page: int = Query(1, ge=1),
):
    """List all CALL-E outbound calls for this clinic with rich filters."""
    clinic_id = auth.clinic_id
    offset = (page - 1) * limit

    try:
        query = (
            supabase_read.table("outbound_calls")
            .select("*", count="exact")
            .eq("clinic_id", clinic_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if campaign_type and campaign_type != "all":
            query = query.eq("campaign_type", campaign_type)
        if status and status != "all":
            query = query.eq("status", status)

        res = await asyncio.get_event_loop().run_in_executor(None, query.execute)
        calls_data = res.data or []

        # Optional client-side search filter if query specified
        if search and search.strip():
            term = search.strip().lower()
            calls_data = [
                c for c in calls_data
                if term in str(c.get("summary", "")).lower()
                or term in str(c.get("calle_call_id", "")).lower()
                or term in str(c.get("structured_result", "")).lower()
                or term in str(c.get("campaign_type", "")).lower()
            ]

        return {
            "data": calls_data,
            "meta": {"total": res.count or len(calls_data), "page": page, "limit": limit},
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/calls/{record_id}")
async def get_outbound_call(
    record_id: str,
    auth: AuthenticatedUser = Depends(require_permission("calls:read")),
):
    """Get a single outbound call record with full structured details and live poll."""
    clinic_id = auth.clinic_id
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("outbound_calls")
                .select("*")
                .eq("id", record_id)
                .eq("clinic_id", clinic_id)
                .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Call record not found")

        record = res.data[0]

        # If CALL-E call ID exists and status is still running/queued, poll live status
        if record.get("calle_call_id") and record.get("status") in ("running", "queued"):
            live_status = await calle_service.get_call_status(record["calle_call_id"])
            if live_status and live_status.get("status") in ("completed", "failed"):
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("outbound_calls").update({
                        "status": live_status.get("status"),
                        "task_completed": live_status.get("task_completed"),
                        "structured_result": live_status.get("structured_result"),
                        "summary": live_status.get("summary", ""),
                        "completion_score": live_status.get("completion_confidence", {}).get("score"),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", record_id).execute()
                )
                record.update(live_status)

        return {"data": record}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/calls/{calle_call_id}/events")
async def get_call_events(
    calle_call_id: str,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    auth: AuthenticatedUser = Depends(require_permission("calls:read")),
):
    """List developer-facing call events from CALL-E per https://docs.heycall-e.com/calls."""
    return await calle_service.list_call_events(calle_call_id, limit=limit, cursor=cursor)


@router.get("/goals")
async def list_goals(
    limit: int = Query(50, ge=1, le=100),
    after: Optional[str] = Query(None),
    auth: AuthenticatedUser = Depends(require_permission("calls:read")),
):
    """List active published goals per https://docs.heycall-e.com/goal-runs."""
    return await calle_service.list_goals(limit=limit, after=after)


@router.post("/goals/{goal_id}/runs")
async def create_goal_run(
    goal_id: str,
    body: Dict[str, Any],
    auth: AuthenticatedUser = Depends(require_permission("calls:write")),
    request: Request = None,
):
    """Execute a Goal Run per https://docs.heycall-e.com/goal-runs."""
    phone = _normalize_phone_e164(body.get("phone"))
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    variables = body.get("variables", {})
    wait_for_completion = bool(body.get("wait_for_completion", False))
    idempotency_key = body.get("idempotency_key") or f"run_{goal_id}_{uuid.uuid4().hex[:8]}"

    res = await calle_service.create_goal_run(
        goal_id=goal_id,
        phone=phone,
        variables=variables,
        idempotency_key=idempotency_key,
        wait_for_completion=wait_for_completion,
    )

    # Save to outbound_calls table as goal run record
    record_id = await _save_outbound_call(
        clinic_id=auth.clinic_id,
        campaign_type="goal_run",
        result={
            "id": res.get("id"),
            "status": res.get("status", "running"),
            "task_completed": res.get("result", {}).get("task_completed", False) if isinstance(res.get("result"), dict) else False,
            "structured_result": res.get("result", {}).get("extracted_data") if isinstance(res.get("result"), dict) else res.get("result"),
            "summary": res.get("result", {}).get("summary", f"Goal Run for '{goal_id}'") if isinstance(res.get("result"), dict) else f"Goal Run '{goal_id}'",
        },
        idempotency_key=idempotency_key,
    )

    await audit_service.log(
        clinic_id=auth.clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="calle_goal_run_executed",
        resource_type="outbound_calls",
        resource_id=record_id,
        details={"goal_id": goal_id, "idempotency_key": idempotency_key},
        request=request,
    )

    return {"record_id": record_id, "goal_run": res}


@router.get("/goals/{goal_id}/runs/{goal_run_id}")
async def get_goal_run(
    goal_id: str,
    goal_run_id: str,
    auth: AuthenticatedUser = Depends(require_permission("calls:read")),
):
    """Get the status of a Goal Run per https://docs.heycall-e.com/goal-runs."""
    return await calle_service.get_goal_run(goal_id, goal_run_id)


@router.post("/calls/single")
async def trigger_single_call(
    body: SingleCallRequest,
    background_tasks: BackgroundTasks,
    auth: AuthenticatedUser = Depends(require_permission("calls:write")),
    request: Request = None,
):
    """
    Trigger a single test or live outbound CALL-E call for any campaign type.
    Ensures patient and appointment records are dynamically resolved and linked in PostgreSQL.
    Supports synchronous waiting (`wait_for_completion: true`) to return immediate structured results.
    """
    clinic_id = auth.clinic_id

    # 1. Get clinic name
    try:
        clinic_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics")
                .select("name")
                .eq("id", clinic_id)
                .execute()
        )
        clinic_name = body.clinic_name or (clinic_res.data[0]["name"] if clinic_res.data else "Your Clinic")
    except Exception:
        clinic_name = body.clinic_name or "Your Clinic"

    normalized_phone = _normalize_phone_e164(body.phone)
    if not normalized_phone:
        raise HTTPException(status_code=400, detail="Invalid phone number format. Provide valid E.164 phone number.")

    appointment_id = body.appointment_id
    patient_id = body.patient_id
    patient_name = body.patient_name
    time_str = body.time_str

    # 2. If appointment_id provided, fetch real appointment datetime and patient
    if appointment_id:
        try:
            appt_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase_read.table("appointments")
                    .select("id, patient_id, patient_name, patient_phone, datetime, status")
                    .eq("id", appointment_id)
                    .eq("clinic_id", clinic_id)
                    .execute()
            )
            if appt_res.data:
                appt_item = appt_res.data[0]
                patient_id = patient_id or appt_item.get("patient_id")
                patient_name = patient_name or appt_item.get("patient_name")
                if appt_item.get("datetime"):
                    try:
                        raw_dt = appt_item["datetime"].replace("Z", "+00:00")
                        parsed_dt = datetime.fromisoformat(raw_dt)
                        time_str = parsed_dt.strftime("%A, %B %d at %I:%M %p")
                    except Exception:
                        time_str = appt_item["datetime"][:16].replace("T", " ")
        except Exception as ex:
            log.warning("[SingleCall] Could not query appointment: %s", ex)

    # 3. If patient_id missing, find or create patient in patients table by phone
    if not patient_id:
        try:
            pat_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase_read.table("patients")
                    .select("id, name")
                    .eq("clinic_id", clinic_id)
                    .eq("phone", normalized_phone)
                    .execute()
            )
            if pat_res.data:
                patient_id = pat_res.data[0]["id"]
                patient_name = patient_name or pat_res.data[0].get("name") or "Patient"
            else:
                patient_id = str(uuid.uuid4())
                patient_name = patient_name or "Test Patient"
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("patients").insert({
                        "id": patient_id,
                        "clinic_id": clinic_id,
                        "name": patient_name,
                        "phone": normalized_phone,
                        "email": "patient@clinic.com",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }).execute()
                )
        except Exception as ex:
            log.warning("[SingleCall] Patient resolution warning: %s", ex)

    # 4. For confirmation campaign without appointment, auto-schedule a real pending appointment for tomorrow
    if body.campaign_type == "confirmation" and not appointment_id:
        try:
            tomorrow_dt = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=30, second=0, microsecond=0)
            appointment_id = str(uuid.uuid4())
            time_str = time_str or tomorrow_dt.strftime("%A, %B %d at %I:%M %p")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("appointments").insert({
                    "id": appointment_id,
                    "clinic_id": clinic_id,
                    "patient_id": patient_id,
                    "patient_name": patient_name or "Test Patient",
                    "patient_phone": normalized_phone,
                    "datetime": tomorrow_dt.isoformat(),
                    "status": "scheduled",
                    "appointment_type": "General Consultation",
                    "booked_by": "ai",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            )
            # Broadcast real-time booking event to Dashboard & Appointments page
            await tenant_room_manager.broadcast_to_tenant(str(clinic_id), {
                "event": "APPOINTMENT_ADDED",
                "data": {
                    "id": appointment_id,
                    "patient_name": patient_name or "Test Patient",
                    "datetime": tomorrow_dt.isoformat(),
                    "status": "scheduled",
                    "booked_by": "ai"
                }
            })
        except Exception as ex:
            log.warning("[SingleCall] Auto-appointment creation warning: %s", ex)

    idem_key = _build_idempotency_key(body.campaign_type, clinic_id, appointment_id or str(uuid.uuid4()))
    webhook_url = f"{settings.API_BASE_URL}/api/v1/calle/webhook" if settings.API_BASE_URL and not body.wait_for_completion else None

    # 5. Dispatch the right campaign
    result = None
    if body.campaign_type == "confirmation":
        result = await calle_service.confirmation_call(
            phone=normalized_phone,
            clinic_name=clinic_name,
            time_str=time_str or "tomorrow at 10:30 AM",
            idempotency_key=idem_key,
            webhook_url=webhook_url,
            region=body.region,
            wait_for_completion=body.wait_for_completion,
        )
    elif body.campaign_type == "no_show":
        result = await calle_service.no_show_recovery_call(
            phone=normalized_phone,
            clinic_name=clinic_name,
            patient_name=body.patient_name or "Valued Patient",
            time_str=time_str or "today's appointment time",
            idempotency_key=idem_key,
            webhook_url=webhook_url,
            region=body.region,
            wait_for_completion=body.wait_for_completion,
        )
    elif body.campaign_type == "recall":
        result = await calle_service.recall_call(
            phone=normalized_phone,
            clinic_name=clinic_name,
            days_since_last_visit=body.days_since_last_visit or 30,
            recall_type=body.recall_type or "routine follow-up",
            idempotency_key=idem_key,
            webhook_url=webhook_url,
            region=body.region,
            wait_for_completion=body.wait_for_completion,
        )
    elif body.campaign_type == "survey":
        result = await calle_service.post_visit_survey_call(
            phone=normalized_phone,
            clinic_name=clinic_name,
            idempotency_key=idem_key,
            webhook_url=webhook_url,
            region=body.region,
            wait_for_completion=body.wait_for_completion,
        )
    elif body.campaign_type == "waitlist":
        result = await calle_service.waitlist_fill_call(
            phone=normalized_phone,
            clinic_name=clinic_name,
            slot_date=body.slot_date or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%A, %B %d"),
            slot_time=body.slot_time or "10:30 AM",
            idempotency_key=idem_key,
            webhook_url=webhook_url,
            region=body.region,
            wait_for_completion=body.wait_for_completion,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown campaign_type: {body.campaign_type}")

    # 6. Save to DB with strict appointment_id and patient_id linkages
    record_id = await _save_outbound_call(
        clinic_id=clinic_id,
        campaign_type=body.campaign_type,
        result=result,
        appointment_id=appointment_id,
        patient_id=patient_id,
        idempotency_key=idem_key,
    )

    # 7. If wait_for_completion was true and call succeeded immediately, update downstream appointment status
    if body.wait_for_completion and result.get("status") == "completed" and appointment_id:
        struct_res = result.get("structured_result") or {}
        will_attend = str(struct_res.get("will_attend", "")).lower()
        new_status = None
        if will_attend in ("yes", "confirmed", "true"):
            new_status = "confirmed"
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("appointments").update({
                    "status": "confirmed",
                    "confirmed_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", appointment_id).execute()
            )
        elif will_attend in ("no", "rescheduled", "reschedule"):
            new_status = "rescheduled_requested"
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("appointments").update({"status": "rescheduled_requested"}).eq("id", appointment_id).execute()
            )

        if new_status:
            await tenant_room_manager.broadcast_to_tenant(str(clinic_id), {
                "event": "APPOINTMENT_UPDATED",
                "data": {
                    "id": str(appointment_id),
                    "status": new_status,
                    "patient_name": patient_name,
                    "confirmed_at": datetime.now(timezone.utc).isoformat() if new_status == "confirmed" else None
                }
            })

    if result.get("status") == "failed":
        err_detail = result.get("error") or result.get("summary") or "Call creation rejected by CALL-E API"
        raise HTTPException(status_code=400, detail=err_detail)

    # HIPAA Audit log (no PHI)
    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="calle_single_call_triggered",
        resource_type="outbound_calls",
        resource_id=record_id,
        details={"campaign_type": body.campaign_type, "status": result.get("status"), "wait_for_completion": body.wait_for_completion},
        request=request,
    )

    return {
        "record_id": record_id,
        "calle_call_id": result.get("id"),
        "status": result.get("status"),
        "task_completed": result.get("task_completed"),
        "structured_result": result.get("structured_result"),
        "summary": result.get("summary"),
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "completion_score": result.get("completion_confidence", {}).get("score") if isinstance(result.get("completion_confidence"), dict) else None,
        "completion_label": result.get("completion_confidence", {}).get("label") if isinstance(result.get("completion_confidence"), dict) else None,
        "dry_run": calle_service.is_dry_run(),
    }


async def _resolve_appt_phone_and_name(appt: Dict[str, Any], clinic_id: str) -> tuple[str, str]:
    """Reliably extracts patient phone and name with database fallback."""
    phone = appt.get("patient_phone") or ""
    name = appt.get("patient_name") or ""
    pat_id = appt.get("patient_id")
    
    if (not phone or not name) and pat_id:
        try:
            p_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase_read.table("patients").select("name, phone").eq("id", pat_id).single().execute()
            )
            if p_res.data:
                if not phone:
                    phone = p_res.data.get("phone") or ""
                if not name:
                    name = p_res.data.get("name") or ""
        except Exception:
            pass
    return phone, (name or "Patient")


@router.post("/campaigns/confirmation")
async def run_confirmation_campaign(
    background_tasks: BackgroundTasks,
    auth: AuthenticatedUser = Depends(require_permission("calls:write")),
    request: Request = None,
):
    """
    Batch Campaign: Call all patients with appointments tomorrow.
    Runs up to 20 calls. Returns immediately; calls happen in background.
    """
    clinic_id = auth.clinic_id

    try:
        clinic_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics").select("name").eq("id", clinic_id).execute()
        )
        clinic_name = clinic_res.data[0]["name"] if clinic_res.data else "Your Clinic"
    except Exception:
        clinic_name = "Your Clinic"

    # Get tomorrow's appointments
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    tomorrow_start = f"{tomorrow}T00:00:00"
    tomorrow_end = f"{tomorrow}T23:59:59"

    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
                .select("id, patient_id, patient_phone, patient_name, appointment_type, datetime, status")
                .eq("clinic_id", clinic_id)
                .gte("datetime", tomorrow_start)
                .lte("datetime", tomorrow_end)
                .in_("status", ["scheduled", "pending"])
                .limit(20)
                .execute()
        )
        appointments = res.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch appointments: {exc}")

    if not appointments:
        return {"message": "No scheduled appointments found for tomorrow.", "queued": 0}

    webhook_url = f"{settings.API_BASE_URL}/api/v1/calle/webhook" if settings.API_BASE_URL else None

    async def _run_batch():
        for appt in appointments:
            if appt.get("patient_id"):
                try:
                    p_res = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda pid=appt["patient_id"]: supabase_read.table("patients").select("recall_opted_out").eq("id", pid).execute()
                    )
                    if p_res.data and p_res.data[0].get("recall_opted_out"):
                        log.info(f"Skipping TCPA opted out patient: {appt['patient_id']}")
                        continue
                except Exception as ex:
                    log.warning(f"Failed to check recall_opted_out for patient {appt.get('patient_id')}: {ex}")

            phone, patient_name = await _resolve_appt_phone_and_name(appt, clinic_id)
            if not phone:
                continue
            time_str = appt.get("datetime", "")[:16].replace("T", " at ") if appt.get("datetime") else "scheduled time"
            appt_type = appt.get("appointment_type", "appointment")
            idem_key = _build_idempotency_key("confirmation", clinic_id, appt["id"])

            result = await calle_service.confirmation_call(
                phone=phone,
                clinic_name=clinic_name,
                patient_name=patient_name,
                time_str=f"{time_str} for your {appt_type}",
                idempotency_key=idem_key,
                webhook_url=webhook_url,
            )
            await _save_outbound_call(
                clinic_id=clinic_id,
                campaign_type="confirmation",
                result=result,
                appointment_id=appt["id"],
                patient_id=appt.get("patient_id"),
                idempotency_key=idem_key,
            )
            await asyncio.sleep(1.5)

    background_tasks.add_task(_run_batch)

    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="calle_confirmation_campaign_started",
        resource_type="outbound_campaigns",
        details={"appointments_queued": len(appointments), "dry_run": calle_service.is_dry_run()},
        request=request,
    )

    return {
        "message": f"Confirmation campaign started for {len(appointments)} appointments.",
        "queued": len(appointments),
        "dry_run": calle_service.is_dry_run(),
    }


@router.post("/campaigns/no-show")
async def run_no_show_campaign(
    background_tasks: BackgroundTasks,
    auth: AuthenticatedUser = Depends(require_permission("calls:write")),
    request: Request = None,
):
    """Batch: Call patients who missed their appointment today."""
    clinic_id = auth.clinic_id

    try:
        clinic_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics").select("name").eq("id", clinic_id).execute()
        )
        clinic_name = clinic_res.data[0]["name"] if clinic_res.data else "Your Clinic"
    except Exception:
        clinic_name = "Your Clinic"

    today = datetime.now(timezone.utc).date()
    today_start = f"{today}T00:00:00"
    today_end = f"{today}T23:59:59"

    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
                .select("id, patient_id, patient_phone, appointment_type, datetime")
                .eq("clinic_id", clinic_id)
                .gte("datetime", today_start)
                .lte("datetime", today_end)
                .eq("status", "no_show")
                .limit(15)
                .execute()
        )
        appointments = res.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch no-shows: {exc}")

    if not appointments:
        return {"message": "No missed appointments found for today.", "queued": 0}

    webhook_url = f"{settings.API_BASE_URL}/api/v1/calle/webhook" if settings.API_BASE_URL else None

    async def _run_batch():
        for appt in appointments:
            phone, patient_name = await _resolve_appt_phone_and_name(appt, clinic_id)
            if not phone:
                continue
            time_str = appt.get("datetime", "")[:16].replace("T", " at ") if appt.get("datetime") else "today"
            idem_key = _build_idempotency_key("no_show", clinic_id, appt["id"])

            result = await calle_service.no_show_recovery_call(
                phone=phone,
                clinic_name=clinic_name,
                patient_name=patient_name,
                time_str=time_str,
                idempotency_key=idem_key,
                webhook_url=webhook_url,
            )
            await _save_outbound_call(
                clinic_id=clinic_id,
                campaign_type="no_show",
                result=result,
                appointment_id=appt["id"],
                patient_id=appt.get("patient_id"),
                idempotency_key=idem_key,
            )
            await asyncio.sleep(1.5)

    background_tasks.add_task(_run_batch)

    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="calle_noshow_campaign_started",
        resource_type="outbound_campaigns",
        details={"no_shows_queued": len(appointments), "dry_run": calle_service.is_dry_run()},
        request=request,
    )

    return {
        "message": f"No-show recovery campaign started for {len(appointments)} patients.",
        "queued": len(appointments),
        "dry_run": calle_service.is_dry_run(),
    }


@router.post("/campaigns/recall")
async def run_recall_campaign(
    body: RecallCampaignRequest,
    background_tasks: BackgroundTasks,
    auth: AuthenticatedUser = Depends(require_permission("calls:write")),
    request: Request = None,
):
    """Batch: Call patients overdue for follow-up (30/60/90 days since last visit)."""
    clinic_id = auth.clinic_id

    try:
        clinic_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics").select("name").eq("id", clinic_id).execute()
        )
        clinic_name = clinic_res.data[0]["name"] if clinic_res.data else "Your Clinic"
    except Exception:
        clinic_name = "Your Clinic"

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=body.days_threshold)).date()
    # We want patients overdue by ~days_threshold. To allow a window, say last_visit_date <= cutoff_date
    cutoff_end_str = cutoff_date.strftime("%Y-%m-%d")

    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("patients")
                .select("id, name, phone")
                .eq("clinic_id", clinic_id)
                .lte("last_visit_date", cutoff_end_str)
                .eq("recall_opted_out", False)
                .limit(body.limit)
                .execute()
        )
        patients = res.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recall patients: {exc}")

    if not patients:
        return {"message": f"No patients found for {body.days_threshold}-day recall.", "queued": 0}

    webhook_url = f"{settings.API_BASE_URL}/api/v1/calle/webhook" if settings.API_BASE_URL else None

    async def _run_batch():
        for pat in patients:
            phone = pat.get("phone")
            patient_name = pat.get("name")
            if not phone:
                continue
            idem_key = _build_idempotency_key(f"recall_{body.days_threshold}d", clinic_id, pat["id"])

            # Assuming recall_call signature doesn't take patient_name anymore, or if it does, keep it.
            # wait, the signature in calle_service.py for recall_call doesn't take patient_name actually in the file we saw!
            # Let's pass what's needed. Wait, in `calle_service.py`, `recall_call` does NOT have `patient_name` parameter!
            result = await calle_service.recall_call(
                phone=phone,
                clinic_name=clinic_name,
                days_since_last_visit=body.days_threshold,
                recall_type=body.recall_type,
                idempotency_key=idem_key,
                webhook_url=webhook_url,
            )
            await _save_outbound_call(
                clinic_id=clinic_id,
                campaign_type="recall",
                result=result,
                appointment_id=None,
                patient_id=pat["id"],
                idempotency_key=idem_key,
            )
            await asyncio.sleep(1.5)

    background_tasks.add_task(_run_batch)

    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="calle_recall_campaign_started",
        resource_type="outbound_campaigns",
        details={
            "days_threshold": body.days_threshold,
            "patients_queued": len(appointments),
            "dry_run": calle_service.is_dry_run(),
        },
        request=request,
    )

    return {
        "message": f"Recall campaign started for {len(appointments)} patients ({body.days_threshold}-day threshold).",
        "queued": len(appointments),
        "dry_run": calle_service.is_dry_run(),
    }


@router.post("/campaigns/survey")
async def run_survey_campaign(
    background_tasks: BackgroundTasks,
    auth: AuthenticatedUser = Depends(require_permission("calls:write")),
    request: Request = None,
):
    """Batch: Post-visit satisfaction survey for today's completed appointments."""
    clinic_id = auth.clinic_id

    try:
        clinic_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics").select("name").eq("id", clinic_id).execute()
        )
        clinic_name = clinic_res.data[0]["name"] if clinic_res.data else "Your Clinic"
    except Exception:
        clinic_name = "Your Clinic"

    today = datetime.now(timezone.utc).date()
    today_start = f"{today}T00:00:00"
    today_end = f"{today}T23:59:59"

    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
                .select("id, patient_id, patient_phone, patient_name")
                .eq("clinic_id", clinic_id)
                .gte("datetime", today_start)
                .lte("datetime", today_end)
                .eq("status", "completed")
                .limit(20)
                .execute()
        )
        appointments = res.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch completed appointments: {exc}")

    if not appointments:
        return {"message": "No completed appointments found for today.", "queued": 0}

    webhook_url = f"{settings.API_BASE_URL}/api/v1/calle/webhook" if settings.API_BASE_URL else None

    async def _run_batch():
        for appt in appointments:
            phone, patient_name = await _resolve_appt_phone_and_name(appt, clinic_id)
            if not phone:
                continue
            idem_key = _build_idempotency_key("survey", clinic_id, appt["id"])

            result = await calle_service.post_visit_survey_call(
                phone=phone,
                clinic_name=clinic_name,
                idempotency_key=idem_key,
                webhook_url=webhook_url,
            )
            await _save_outbound_call(
                clinic_id=clinic_id,
                campaign_type="survey",
                result=result,
                appointment_id=appt["id"],
                patient_id=appt.get("patient_id"),
                idempotency_key=idem_key,
            )
            await asyncio.sleep(1.5)

    background_tasks.add_task(_run_batch)

    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="calle_survey_campaign_started",
        resource_type="outbound_campaigns",
        details={"appointments_queued": len(appointments), "dry_run": calle_service.is_dry_run()},
        request=request,
    )

    return {
        "message": f"Survey campaign started for {len(appointments)} patients.",
        "queued": len(appointments),
        "dry_run": calle_service.is_dry_run(),
    }


@router.post("/campaigns/waitlist")
async def run_waitlist_campaign(
    body: Optional[WaitlistCampaignRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    auth: AuthenticatedUser = Depends(require_permission("calls:write")),
    request: Request = None,
):
    """
    Batch Campaign 5: Call active waitlist patients to backfill an open schedule slot.
    """
    clinic_id = auth.clinic_id
    req_body = body or WaitlistCampaignRequest()

    try:
        clinic_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics").select("name").eq("id", clinic_id).execute()
        )
        clinic_name = clinic_res.data[0]["name"] if clinic_res.data else "Your Clinic"
    except Exception:
        clinic_name = "Your Clinic"

    slot_date = req_body.slot_date or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%A, %B %d")
    slot_time = req_body.slot_time or "10:30 AM"

    # Fetch waitlist entries
    waitlist_patients = []
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("waitlist")
                .select("id, patient_id, patient_phone, preferred_days, notes")
                .eq("clinic_id", clinic_id)
                .in_("status", ["active", "pending", "waiting"])
                .limit(req_body.limit)
                .execute()
        )
        waitlist_patients = res.data or []
    except Exception:
        pass

    if not waitlist_patients:
        try:
            res_c = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase_read.table("appointments")
                    .select("id, patient_id, patient_phone")
                    .eq("clinic_id", clinic_id)
                    .eq("status", "waitlisted")
                    .limit(req_body.limit)
                    .execute()
            )
            waitlist_patients = res_c.data or []
        except Exception:
            pass

    if not waitlist_patients:
        return {
            "message": "No active waitlist patients found to notify for this slot.",
            "queued": 0,
            "slot_date": slot_date,
            "slot_time": slot_time,
        }

    webhook_url = f"{settings.API_BASE_URL}/api/v1/calle/webhook" if settings.API_BASE_URL else None

    async def _run_batch():
        for wp in waitlist_patients:
            phone = wp.get("patient_phone") or wp.get("phone", "")
            if not phone:
                continue
            ref_id = wp.get("id") or str(uuid.uuid4())
            idem_key = _build_idempotency_key("waitlist", clinic_id, ref_id)

            result = await calle_service.waitlist_fill_call(
                phone=phone,
                clinic_name=clinic_name,
                slot_date=slot_date,
                slot_time=slot_time,
                idempotency_key=idem_key,
                webhook_url=webhook_url,
            )
            await _save_outbound_call(
                clinic_id=clinic_id,
                campaign_type="waitlist",
                result=result,
                appointment_id=None,
                patient_id=wp.get("patient_id"),
                idempotency_key=idem_key,
            )
            await asyncio.sleep(1.5)

    background_tasks.add_task(_run_batch)

    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="calle_waitlist_campaign_started",
        resource_type="outbound_campaigns",
        details={
            "slot_date": slot_date,
            "slot_time": slot_time,
            "patients_queued": len(waitlist_patients),
            "dry_run": calle_service.is_dry_run(),
        },
        request=request,
    )

    return {
        "message": f"Waitlist backfill campaign started for {len(waitlist_patients)} patients for slot on {slot_date} at {slot_time}.",
        "queued": len(waitlist_patients),
        "slot_date": slot_date,
        "slot_time": slot_time,
        "dry_run": calle_service.is_dry_run(),
    }


@router.post("/webhook")
async def handle_calle_webhook(request: Request):
    """
    CALL-E terminal result webhook per official docs (https://docs.heycall-e.com/webhooks).
    Handles call.completed, call.failed, call.result_validation_failed.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    body_event_id = payload.get("id") if payload.get("object") == "event" or payload.get("type") in ("call.completed", "call.failed", "call.result_validation_failed") else None
    if not _verify_calle_auth(request, body_event_id):
        log.warning("[CalleWebhook] Unauthorized webhook signature or secret")
        raise HTTPException(status_code=401, detail="Unauthorized webhook signature")

    call_data = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    calle_call_id = call_data.get("id") or call_data.get("call_id") or payload.get("id")
    status = call_data.get("status") or payload.get("status")
    task_completed = call_data.get("task_completed") or call_data.get("taskCompleted", False)
    structured_result = call_data.get("structured_result") or call_data.get("structuredResult") or {}
    summary = call_data.get("summary", "")
    confidence = call_data.get("completion_confidence") or call_data.get("completionConfidence") or {}

    transcript_turns = []
    recipients = call_data.get("recipients", [])
    if recipients and isinstance(recipients, list):
        attempts = recipients[0].get("attempts", [])
        if attempts and isinstance(attempts, list):
            transcript_turns = attempts[0].get("transcript_turns", [])

    if not calle_call_id:
        return {"status": "ignored", "reason": "no call_id"}

    log.info("[CalleWebhook] Received call_id=%s status=%s task_completed=%s", calle_call_id, status, task_completed)

    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("outbound_calls")
                .select("id, clinic_id, appointment_id, campaign_type")
                .eq("calle_call_id", str(calle_call_id))
                .execute()
        )
        if not res.data:
            return {"status": "accepted", "call_id": str(calle_call_id), "message": "untracked call recorded"}

        record = res.data[0]
        record_id = record["id"]
        clinic_id = record["clinic_id"]
        appointment_id = record.get("appointment_id")
        campaign_type = record.get("campaign_type")

        update_data = {
            "status": status,
            "task_completed": task_completed,
            "structured_result": structured_result,
            "summary": summary,
            "completion_score": confidence.get("score") if isinstance(confidence, dict) else None,
            "completion_label": confidence.get("label") if isinstance(confidence, dict) else None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if transcript_turns:
            update_data["transcript_turns"] = transcript_turns

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("outbound_calls").update(update_data).eq("id", record_id).execute()
        )

        # Downstream EHR status synchronization
        new_status = None
        if campaign_type == "confirmation" and appointment_id and structured_result:
            will_attend = str(structured_result.get("will_attend", "")).lower()
            if will_attend in ("yes", "confirmed", "true"):
                new_status = "confirmed"
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("appointments").update({
                        "status": "confirmed",
                        "confirmed_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", appointment_id).execute()
                )
            elif will_attend in ("no", "rescheduled", "reschedule"):
                new_status = "rescheduled_requested"
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("appointments").update({"status": "rescheduled_requested"}).eq("id", appointment_id).execute()
                )
            elif will_attend in ("cancelled", "canceled"):
                new_status = "cancelled"
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("appointments").update({"status": "cancelled"}).eq("id", appointment_id).execute()
                )

        elif campaign_type == "no_show" and appointment_id and structured_result:
            resp_type = str(structured_result.get("response_type", "")).lower()
            if resp_type in ("rescheduled", "yes", "true"):
                new_status = "rescheduled_requested"
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("appointments").update({"status": "rescheduled_requested"}).eq("id", appointment_id).execute()
                )

        # ── REAL-TIME WEBSOCKET BROADCASTS ──────────────────────────────────
        if appointment_id and new_status:
            await tenant_room_manager.broadcast_to_tenant(str(clinic_id), {
                "event": "APPOINTMENT_UPDATED",
                "data": {
                    "id": str(appointment_id),
                    "status": new_status,
                    "confirmed_at": datetime.now(timezone.utc).isoformat() if new_status == "confirmed" else None
                }
            })

        await tenant_room_manager.broadcast_to_tenant(str(clinic_id), {
            "event": "OUTBOUND_CALL_COMPLETED",
            "data": {
                "id": str(record_id),
                "calle_call_id": str(calle_call_id),
                "campaign_type": campaign_type,
                "status": status,
                "task_completed": task_completed,
                "structured_result": structured_result,
                "summary": summary,
                "appointment_id": str(appointment_id) if appointment_id else None
            }
        })

        await tenant_room_manager.broadcast_to_tenant(str(clinic_id), {
            "event": "DASHBOARD_STATS_UPDATED",
            "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
        })

        # Audit log (no PHI)
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=None,
            user_email="calle-webhook@system",
            action="calle_webhook_received",
            resource_type="outbound_calls",
            resource_id=record_id,
            details={
                "calle_call_id": str(calle_call_id),
                "status": status,
                "campaign_type": campaign_type,
                "task_completed": task_completed,
            },
            request=request,
        )

    except Exception as exc:
        log.error("[CalleWebhook] Processing error: %s", type(exc).__name__)
        return {"status": "error", "detail": str(exc)}

    return {"status": "ok", "id": str(calle_call_id)}


@router.post("/inbound")
async def handle_calle_inbound_call(request: Request):
    """
    CALL-E Inbound Voice Receptionist Router.
    Dynamic clinic knowledgebase, doctor credentials, business hours, emergency protocols.
    """
    if not _verify_calle_auth(request):
        log.warning("[CalleInbound] Unauthorized inbound voice request")
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    raw_from = payload.get("from_number") or payload.get("from") or payload.get("caller_phone") or payload.get("caller_id")
    raw_to = payload.get("to_number") or payload.get("to") or payload.get("called_number") or payload.get("did")
    
    from_normalized = _normalize_phone_e164(raw_from)
    to_normalized = _normalize_phone_e164(raw_to)

    clinic_id = payload.get("clinic_id") or payload.get("metadata", {}).get("clinic_id") or request.query_params.get("clinic_id")

    if not clinic_id and to_normalized:
        try:
            res_to = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase_read.table("clinics")
                    .select("id")
                    .or_(f"telnyx_number.eq.{to_normalized},twilio_number.eq.{to_normalized},phone_number.eq.{to_normalized}")
                    .limit(1)
                    .execute()
            )
            if res_to.data:
                clinic_id = res_to.data[0]["id"]
        except Exception as did_err:
            log.warning("[CalleInbound] DID lookup error: %s", did_err)

    if not clinic_id:
        clinic_id = getattr(settings, "DEFAULT_CLINIC_ID", "d3b07384-d113-46a6-a719-38cf89235d54")

    clinic_name = "Bytelytic Medical Clinic"
    doctor_name = "Dr. Smith, MD"
    specialty = "General Practice"
    hours = "Mon-Fri 8:00 AM - 5:00 PM"
    tz_str = "America/New_York"
    agent_name = "Monika"
    clinic_address = "123 Medical Center Way, Suite 400"
    emergency_phone = "911"
    transfer_phone = None
    custom_persona_prompt = None

    if clinic_id:
        try:
            res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase_read.table("clinics")
                    .select("name, primary_doctor_name, specialty, business_hours, timezone, address, city, state, phone_number, ai_receptionist_name, transfer_phone_number, emergency_phone, custom_system_prompt")
                    .eq("id", clinic_id)
                    .execute()
            )
            if res.data:
                c = res.data[0]
                clinic_name = c.get("name") or clinic_name
                doctor_name = c.get("primary_doctor_name") or doctor_name
                specialty = c.get("specialty") or specialty
                hours = c.get("business_hours") or hours
                tz_str = c.get("timezone") or tz_str
                agent_name = c.get("ai_receptionist_name") or agent_name
                if c.get("address"):
                    clinic_address = f"{c.get('address')}, {c.get('city', '')} {c.get('state', '')}".strip()
                emergency_phone = c.get("emergency_phone") or emergency_phone
                transfer_phone = c.get("transfer_phone_number")
                custom_persona_prompt = c.get("custom_system_prompt")
        except Exception as e:
            log.warning("[CalleInbound] Clinic profile lookup failed: %s", e)

    # Caller recognition
    recognized_patient = False
    patient_salutation = ""
    patient_id = None

    if from_normalized and clinic_id:
        try:
            from_hash = hashlib.sha256(from_normalized.encode("utf-8")).hexdigest()
            p_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase_read.table("patients")
                    .select("id, full_name, first_name")
                    .eq("clinic_id", clinic_id)
                    .or_(f"phone.eq.{from_normalized},phone_hash.eq.{from_hash}")
                    .limit(1)
                    .execute()
            )
            if p_res.data:
                p_data = p_res.data[0]
                recognized_patient = True
                patient_id = p_data.get("id")
                first_name = p_data.get("first_name")
                if not first_name and p_data.get("full_name"):
                    first_name = p_data.get("full_name").split()[0]
                if first_name:
                    patient_salutation = first_name.strip()
        except Exception as p_err:
            log.warning("[CalleInbound] Patient recognition check failed: %s", p_err)

    try:
        from zoneinfo import ZoneInfo
        clinic_tz = ZoneInfo(tz_str)
        now_local = datetime.now(clinic_tz)
    except Exception:
        now_local = datetime.now(timezone.utc)
    current_time_str = now_local.strftime("%A, %B %d at %I:%M %p")

    if recognized_patient and patient_salutation:
        greeting = (
            f"Thank you for calling {clinic_name}. Hello {patient_salutation}, this is {agent_name}, "
            f"your 24/7 AI Voice Receptionist. How can I help you today?"
        )
    else:
        greeting = (
            f"Thank you for calling {clinic_name}. My name is {agent_name}, "
            f"your 24/7 AI Voice Receptionist. How may I assist you with your appointment or inquiry today?"
        )

    base_prompt = (
        f"You are {agent_name}, the 24/7 AI Voice Receptionist for {clinic_name}. "
        f"Primary Physician: {doctor_name} ({specialty}). "
        f"Clinic Business Hours: {hours}. "
        f"Clinic Address: {clinic_address}. "
        f"Current Clinic Time: {current_time_str}. "
        f"{f'The caller is an existing patient: {patient_salutation}. ' if recognized_patient and patient_salutation else ''}"
        f"Your goal is to warmly greet the caller, identify their needs (appointment booking, reschedule, "
        f"cancellation, doctor credentials, business hours, or general clinic inquiries), verify open slots, "
        f"and confirm their requested details over the phone. "
        f"CRITICAL MEDICAL GUARDRAIL: If the patient describes emergency symptoms such as severe chest pain, "
        f"shortness of breath, uncontrolled bleeding, or sudden numbness, immediately instruct them to hang up and call 911 immediately. "
        f"{f'If the caller requests a human staff member, inform them you can route to {transfer_phone}. ' if transfer_phone else ''}"
        f"Be warm, polite, natural, concise, professional, and clear."
    )

    prompt = f"{base_prompt}\n\nAdditional Clinic Guidelines:\n{custom_persona_prompt}" if custom_persona_prompt else base_prompt

    inbound_schema = {
        "type": "object",
        "required": ["call_reason", "action_taken"],
        "properties": {
            "call_reason": {
                "type": "string",
                "enum": ["new_appointment", "reschedule", "cancellation", "doctor_info", "emergency", "general_inquiry"],
                "description": "Primary reason for the inbound patient call."
            },
            "action_taken": {
                "type": "string",
                "description": "Summary of appointment booked, rescheduled time, or instructions provided."
            },
            "booked_slot": {
                "type": "string",
                "description": "Requested or confirmed appointment date/time if booked."
            },
            "caller_name": {
                "type": "string",
                "description": "Patient's name as stated during the call."
            },
            "transfer_requested": {
                "type": "boolean",
                "description": "True if patient requested transfer to human staff."
            }
        },
        "additionalProperties": False
    }

    try:
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=None,
            user_email="calle-inbound@system",
            action="calle_inbound_call_routed",
            resource_type="inbound_calls",
            resource_id=None,
            details={
                "clinic_name": clinic_name,
                "recognized_patient": recognized_patient,
                "agent_name": agent_name,
            },
            request=request,
        )
    except Exception as audit_err:
        log.warning("[CalleInbound] Audit log warning: %s", audit_err)

    return {
        "status": "active",
        "agent_name": agent_name,
        "clinic_name": clinic_name,
        "clinic_id": clinic_id,
        "begin_message": greeting,
        "system_prompt": prompt,
        "result_schema": inbound_schema,
        "dynamic_variables": {
            "clinic_name": clinic_name,
            "doctor_name": doctor_name,
            "specialty": specialty,
            "business_hours": hours,
            "timezone": tz_str,
            "current_time": current_time_str,
            "patient_recognized": recognized_patient,
            "patient_id": patient_id,
        },
        "idempotency_key": f"inbound_{uuid.uuid4().hex[:8]}"
    }
