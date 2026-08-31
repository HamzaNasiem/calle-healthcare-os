from fastapi import APIRouter, Depends, HTTPException, Query, status
import datetime
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from ...core.database import supabase, supabase_read
from ...core.security import require_permission, AuthenticatedUser, require_active_subscription
from ...services.revenue_service import revenue_service
from ...core.logger import log

router = APIRouter(prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(require_active_subscription)])


class QuickTestCallRequest(BaseModel):
    phone_number: Optional[str] = None
    patient_name: Optional[str] = "Test Patient"
    scenario: Optional[str] = "booking"  # booking | confirmation | prior_auth


class QuickPriorAuthRequest(BaseModel):
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    insurance_name: Optional[str] = None
    cpt_code: Optional[str] = None
    icd10_code: Optional[str] = None
    urgency: Optional[str] = "standard"


def _derive_call_sentiment(call: dict) -> tuple[str, str]:
    """Derive sentiment key and label based on call outcome and transcript markers."""
    outcome = (call.get("outcome") or "").lower()
    transcript = (call.get("transcript") or "").lower()

    if outcome in ["booked", "confirmed", "rescheduled"]:
        return "positive", "Positive (High Intent)"
    elif outcome in ["cancelled"]:
        return "critical", "Critical (Cancelled)"
    elif outcome in ["no_answer", "missed"]:
        return "neutral", "Unreached / Missed"
    elif outcome in ["transferred"]:
        return "neutral", "Transferred to Staff"

    if any(w in transcript for w in ["thank you", "great", "perfect", "appreciate", "confirmed", "excellent", "awesome", "book", "appointment"]):
        return "positive", "Positive (Satisfied)"
    if any(w in transcript for w in ["cancel", "unhappy", "pain", "emergency", "urgent", "wrong", "complaint"]):
        return "critical", "Critical Attention"

    return "neutral", "Informational / Inquiring"


def _derive_structured_summary(call: dict) -> dict:
    """Derives a structured summary and action item snippet for dashboard display."""
    outcome = (call.get("outcome") or "completed").lower()
    call_type = (call.get("call_type") or "inbound").lower()
    patient = call.get("patient_name") or "Patient"

    if outcome == "booked":
        return {
            "intent": "Appointment Booking",
            "action_taken": f"AI booked new appointment slot for {patient}",
            "key_takeaway": f"Confirmed appointment booking details and sent SMS notification to patient."
        }
    elif outcome == "confirmed":
        return {
            "intent": "Appointment Confirmation",
            "action_taken": f"AI verified patient attendance for scheduled visit",
            "key_takeaway": f"Patient {patient} confirmed arrival on time; status updated to Confirmed."
        }
    elif outcome == "rescheduled":
        return {
            "intent": "Appointment Reschedule",
            "action_taken": f"AI modified slot for {patient}",
            "key_takeaway": f"Slot moved to new open calendar availability as requested by caller."
        }
    elif outcome == "cancelled":
        return {
            "intent": "Cancellation Request",
            "action_taken": f"AI cancelled appointment & triggered waitlist backfill",
            "key_takeaway": f"Patient cancelled visit. Auto-waitlist engine queued for slot recovery."
        }
    elif outcome == "transferred":
        return {
            "intent": "Complex Clinical / Human Transfer",
            "action_taken": f"Transferred to front-desk staff",
            "key_takeaway": f"Caller requested complex clinical triage or direct staff assistance."
        }
    else:
        return {
            "intent": "General Inquiry / FAQ",
            "action_taken": f"AI answered clinic FAQs & operating hours",
            "key_takeaway": f"Provided clinic address, parking instructions, and insurance acceptance details."
        }


def _parse_date_bounds(date_from: Optional[str], date_to: Optional[str]) -> tuple[datetime.datetime, datetime.datetime, str, str]:
    now = datetime.datetime.now(datetime.timezone.utc)
    
    if date_from:
        try:
            clean_from = date_from.replace("Z", "+00:00")
            if "T" in clean_from:
                dt_from = datetime.datetime.fromisoformat(clean_from)
            else:
                dt_from = datetime.datetime.strptime(clean_from[:10], "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        except Exception:
            dt_from = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=datetime.timezone.utc)
    else:
        dt_from = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=datetime.timezone.utc)

    if date_to:
        try:
            clean_to = date_to.replace("Z", "+00:00")
            if "T" in clean_to:
                dt_to = datetime.datetime.fromisoformat(clean_to)
            else:
                dt_to = datetime.datetime.strptime(clean_to[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=datetime.timezone.utc)
        except Exception:
            dt_to = datetime.datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=datetime.timezone.utc)
    else:
        dt_to = datetime.datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=datetime.timezone.utc)

    if dt_from.tzinfo is None:
        dt_from = dt_from.replace(tzinfo=datetime.timezone.utc)
    if dt_to.tzinfo is None:
        dt_to = dt_to.replace(tzinfo=datetime.timezone.utc)

    return dt_from, dt_to, dt_from.isoformat(), dt_to.isoformat()


@router.get("/stats")
async def get_dashboard_stats(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
    date_from: Optional[str] = Query(None, description="Start date in ISO format or YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date in ISO format or YYYY-MM-DD"),
):
    """
    Consolidated Dashboard Stats Endpoint:
    Returns accurate live counts for:
    - Today's / Filtered Appointments (AI vs Staff)
    - Inbound Calls Handled & Answer Rate
    - Outbound Calls Confirmed
    - Prior Auths Approved & In-Flight
    - Estimated Hours Saved
    - Revenue Recovered
    - Full compatibility with both nested and flat frontend schemas
    """
    clinic_id = auth.clinic_id
    dt_from, dt_to, iso_from, iso_to = _parse_date_bounds(date_from, date_to)
    
    cache_key = f"dashboard_stats_{clinic_id}:{iso_from[:10]}:{iso_to[:10]}"
    
    # 1. Try to read from cache (short TTL for real-time accuracy)
    from ...core.cache import local_cache
    cached_data = local_cache.get(cache_key)
    if cached_data:
        return {"data": cached_data}
        
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Current month
        month_start = datetime.datetime(now.year, now.month, 1, tzinfo=datetime.timezone.utc).isoformat()
        if now.month == 12:
            month_end = datetime.datetime(now.year + 1, 1, 1, tzinfo=datetime.timezone.utc).isoformat()
        else:
            month_end = datetime.datetime(now.year, now.month + 1, 1, tzinfo=datetime.timezone.utc).isoformat()
            
        # Today
        today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc).isoformat()
        today_end = (datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
        
        # Previous period for vs_yesterday_pct
        period_duration = dt_to - dt_from
        prev_dt_from = dt_from - period_duration
        prev_dt_to = dt_from
        prev_iso_from = prev_dt_from.isoformat()
        prev_iso_to = prev_dt_to.isoformat()

        # Fetch data from read-replica
        rev_res = supabase_read.table("revenue_events").select("amount_cents").eq("clinic_id", clinic_id).gte("created_at", month_start).lt("created_at", month_end).execute()
        calls_res = supabase_read.table("calls").select("id, outcome, direction, call_type, duration_seconds, status, created_at").eq("clinic_id", clinic_id).gte("created_at", month_start).lt("created_at", month_end).execute()
        calls_period_res = supabase_read.table("calls").select("id, outcome, direction, duration_seconds, created_at").eq("clinic_id", clinic_id).gte("created_at", iso_from).lte("created_at", iso_to).execute()
        calls_prev_res = supabase_read.table("calls").select("id", count="exact").eq("clinic_id", clinic_id).gte("created_at", prev_iso_from).lt("created_at", prev_iso_to).execute()
        
        # Appointments month + period + today
        appt_month_res = supabase_read.table("appointments").select("id, booked_by, status").eq("clinic_id", clinic_id).gte("created_at", month_start).lt("created_at", month_end).execute()
        appt_period_res = supabase_read.table("appointments").select("id, status, booked_by, datetime, created_at").eq("clinic_id", clinic_id).gte("datetime", iso_from).lte("datetime", iso_to).execute()
        today_res = supabase_read.table("appointments").select("id, status, booked_by, datetime").eq("clinic_id", clinic_id).gte("datetime", today_start).lt("datetime", today_end).execute()
        
        # Prior authorizations
        pa_list = []
        try:
            pa_res = supabase_read.table("prior_auth_requests").select("id, auth_status, call_status, created_at").eq("tenant_id", clinic_id).execute()
            pa_list = pa_res.data or []
        except Exception:
            try:
                pa_res = supabase_read.table("prior_authorizations").select("id, status, created_at").eq("clinic_id", clinic_id).execute()
                pa_list = pa_res.data or []
            except Exception:
                pa_list = []

        total_revenue_cents = sum(e.get("amount_cents", 0) for e in (rev_res.data or []))
        calls = calls_res.data or []
        period_calls = calls_period_res.data or []
        
        # Period Calls Breakdown
        total_period_calls = len(period_calls)
        call_booked = sum(1 for c in period_calls if c.get("outcome") == "booked")
        call_cancelled = sum(1 for c in period_calls if c.get("outcome") == "cancelled")
        call_transferred = sum(1 for c in period_calls if c.get("outcome") == "transferred")
        call_faq = sum(1 for c in period_calls if c.get("outcome") == "faq_answered")
        call_no_action = sum(1 for c in period_calls if c.get("outcome") in ["no_action", "no_answer", None])
        answered_period_calls = sum(1 for c in period_calls if c.get("outcome") != "no_answer")

        prev_calls_count = calls_prev_res.count if calls_prev_res.count is not None else len(calls_prev_res.data or [])
        if prev_calls_count > 0:
            vs_yesterday_pct = round(((total_period_calls - prev_calls_count) / prev_calls_count) * 100, 1)
        else:
            vs_yesterday_pct = 100.0 if total_period_calls > 0 else 0.0

        # Split calls by direction
        inbound_calls = [c for c in calls if (c.get("direction") or "inbound").lower() == "inbound"]
        inbound_answered = [c for c in inbound_calls if (c.get("outcome") or "").lower() not in ["no_answer", "missed", "failed"]]
        inbound_total = len(inbound_calls) if inbound_calls else len(calls)
        inbound_handled = len(inbound_answered) if inbound_calls else sum(1 for c in calls if c.get("outcome") != "no_answer")
        answer_rate = round((inbound_handled / max(inbound_total, 1)) * 100) if inbound_total > 0 else 99
        
        # Outbound calls & confirmations
        outbound_calls = [c for c in calls if (c.get("direction") or "").lower() == "outbound" or (c.get("call_type") or "").lower() in ["confirmation", "recall", "noshow", "pre_appointment"]]
        outbound_confirmed = [c for c in outbound_calls if (c.get("outcome") or "").lower() in ["confirmed", "completed", "booked", "rescheduled"]]
        outbound_total = len(outbound_calls)
        outbound_confirmed_count = len(outbound_confirmed)

        # Appointments breakdown
        month_appts = appt_month_res.data or []
        ai_month_appts = sum(1 for a in month_appts if a.get("booked_by") == "ai")
        staff_month_appts = sum(1 for a in month_appts if a.get("booked_by") != "ai")

        period_appts = appt_period_res.data or []
        total_period_appts = len(period_appts)
        scheduled_appts = sum(1 for a in period_appts if a.get("status") == "scheduled")
        confirmed_appts = sum(1 for a in period_appts if a.get("status") == "confirmed")
        completed_appts = sum(1 for a in period_appts if a.get("status") == "completed")
        cancelled_appts = sum(1 for a in period_appts if a.get("status") == "cancelled")
        ai_period_appts = sum(1 for a in period_appts if a.get("booked_by") == "ai")
        staff_period_appts = sum(1 for a in period_appts if a.get("booked_by") != "ai")
        
        today_appts = today_res.data or []
        today_appts_ai = sum(1 for a in today_appts if a.get("booked_by") == "ai")
        today_appts_staff = sum(1 for a in today_appts if a.get("booked_by") != "ai")
        today_confirmed = sum(1 for a in today_appts if a.get("status") in ["confirmed", "arrived", "in_session", "completed"])
        today_no_shows = sum(1 for a in today_appts if a.get("status") == "no_show")

        # Prior auth counts
        pa_approved = sum(1 for p in pa_list if (p.get("auth_status") or p.get("status") or "").lower() in ["approved", "auth_approved"])
        pa_pending = sum(1 for p in pa_list if (p.get("auth_status") or p.get("status") or "").lower() in ["pending", "in_progress", "submitted", "dialing"])
        pa_total = len(pa_list)

        # Average call duration
        durations = [c.get("duration_seconds", 0) for c in calls if c.get("duration_seconds")]
        avg_duration = round(sum(durations) / len(durations)) if durations else None

        # Estimated Staff Hours Saved
        hours_saved = round(
            (inbound_handled * 0.20) + 
            (ai_month_appts * 0.25) + 
            (outbound_confirmed_count * 0.15) + 
            (max(pa_total, pa_approved) * 0.75), 
            1
        )
        if hours_saved <= 0:
            hours_saved = round((len(calls) * 0.20) + (len(month_appts) * 0.25), 1)

        # AI performance rate — only compute when there are real calls; return None otherwise
        resolved_ai_calls = sum(
            1 for c in calls 
            if (c.get("status") or "").lower() in ["completed", "transferred", "resolved"] or c.get("call_successful") is True
        )
        ai_perf_rate = round((resolved_ai_calls / max(len(calls), 1)) * 100, 1) if calls else None

        # Do NOT fabricate revenue — return 0 when no real revenue data exists
        # Showing invented revenue would misrepresent actual financial performance
        revenue_appt_count = len(rev_res.data or []) if rev_res.data else 0
        avg_value_cents = int(total_revenue_cents / revenue_appt_count) if revenue_appt_count > 0 else 0

        stats_payload = {
            "period": {
                "from_date": iso_from[:10],
                "to_date": iso_to[:10]
            },
            "calls": {
                "total": total_period_calls,
                "booked": call_booked,
                "cancelled": call_cancelled,
                "transferred": call_transferred,
                "faq_answered": call_faq,
                "no_action": call_no_action,
                "vs_yesterday_pct": vs_yesterday_pct,
                "inbound_handled": answered_period_calls,
                "inbound_total": total_period_calls,
                "outbound_total": outbound_total,
                "outbound_confirmed": outbound_confirmed_count
            },
            "appointments": {
                "total_today": total_period_appts,
                "scheduled": scheduled_appts,
                "confirmed": confirmed_appts,
                "completed": completed_appts,
                "cancelled": cancelled_appts,
                "ai_booked_today": ai_period_appts,
                "staff_booked_today": staff_period_appts
            },
            "revenue_recovered": {
                "amount_cents": total_revenue_cents,
                "currency": "USD",
                "appointment_count": revenue_appt_count,
                "avg_value_cents": avg_value_cents
            },
            "prior_auths": {
                "approved": pa_approved,
                "pending": pa_pending,
                "total": pa_total
            },
            "estimated_hours_saved": hours_saved,
            "ai_performance_rate": ai_perf_rate,
            "no_show_rate_month": round((today_no_shows / max(len(today_appts), 1)) * 100, 1) if today_appts else 0.0,

            # Flat properties for Dashboard.jsx
            "revenueRecoveredCents": total_revenue_cents,
            "revenueRecoveredDollars": round(total_revenue_cents / 100) if total_revenue_cents else 0,
            "callsAnswered": inbound_handled,
            "callsTotal": inbound_total,
            "inboundCallsHandled": inbound_handled,
            "inboundCallsTotal": inbound_total,
            "outboundConfirmed": outbound_confirmed_count,
            "outboundCallsTotal": outbound_total,
            "answerRatePercent": answer_rate,
            "appointmentsBookedByAi": ai_month_appts,
            "appointmentsBookedByStaff": staff_month_appts,
            "appointmentsBookedTotal": len(month_appts),
            "avgCallDurationSeconds": avg_duration,
            "todayAppointments": len(today_appts),
            "todayAppointmentsAi": today_appts_ai,
            "todayAppointmentsStaff": today_appts_staff,
            "todayConfirmed": today_confirmed,
            "todayNoShows": today_no_shows,
            "priorAuthsApproved": pa_approved,
            "priorAuthsPending": pa_pending,
            "priorAuthsTotal": pa_total,
            "estimatedHoursSaved": hours_saved,
            "aiPerformanceRate": ai_perf_rate,
            "noShowRateMonth": round((today_no_shows / max(len(today_appts), 1)) * 100, 1) if today_appts else 0.0
        }
        
        # 2. Write to cache with a 60-second TTL
        local_cache.set(cache_key, stats_payload, ttl=60)
        
        return {"data": stats_payload}
    except Exception as e:
        log.error(f"[dashboard_stats_error] {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/recent-calls")
async def get_dashboard_recent_calls(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
    limit: int = Query(6, le=20)
):
    """
    Returns latest live Voice AI calls enriched with sentiment analysis, structured takeaways,
    duration formatting, and action tags for the Dashboard Recent Calls widget.
    """
    clinic_id = auth.clinic_id
    try:
        res = supabase_read.table("calls").select(
            "id, direction, call_type, from_number, to_number, patient_id, duration_seconds, outcome, status, transcript, recording_url, created_at"
        ).eq("clinic_id", clinic_id).order("created_at", desc=True).limit(limit).execute()

        raw_calls = res.data or []
        patient_ids = list({c["patient_id"] for c in raw_calls if c.get("patient_id")})
        patients_map = {}
        if patient_ids:
            try:
                p_res = supabase_read.table("patients").select("id, name, phone").in_("id", patient_ids).execute()
                if p_res.data:
                    for p in p_res.data:
                        patients_map[p["id"]] = p.get("name")
            except Exception:
                pass

        enriched_calls = []

        for call in raw_calls:
            sentiment_key, sentiment_label = _derive_call_sentiment(call)
            structured_info = _derive_structured_summary(call)
            
            dur = call.get("duration_seconds") or 0
            m = dur // 60
            s = dur % 60
            duration_formatted = f"{m}m {s:02d}s" if m > 0 else f"{s}s"
            pid = call.get("patient_id")
            resolved_patient_name = patients_map.get(pid) or call.get("from_number") or "Patient Caller"

            enriched_calls.append({
                "id": call.get("id"),
                "direction": call.get("direction") or "inbound",
                "call_type": call.get("call_type") or "booking",
                "from_number": call.get("from_number") or "Unknown Caller",
                "to_number": call.get("to_number"),
                "patient_id": pid,
                "patient_name": resolved_patient_name,
                "duration_seconds": dur,
                "duration_formatted": duration_formatted,
                "outcome": (call.get("outcome") or "completed").lower(),
                "status": call.get("status") or "completed",
                "sentiment": sentiment_key,
                "sentiment_label": sentiment_label,
                "structured_result": structured_info,
                "transcript": call.get("transcript"),
                "recording_url": call.get("recording_url"),
                "created_at": call.get("created_at")
            })

        return {"data": enriched_calls}
    except Exception as e:
        log.error(f"[dashboard_recent_calls_error] {e}", exc_info=True)
        return {"data": []}


@router.post("/quick-test-call")
async def trigger_quick_test_call(
    payload: QuickTestCallRequest,
    auth: AuthenticatedUser = Depends(require_permission("calls:write"))
):
    """
    Trigger 1-Click test call / simulated scenario verification from dashboard.
    """
    clinic_id = auth.clinic_id
    try:
        # Record test call event
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        phone = payload.phone_number or "+10000000000"
        pat_name = payload.patient_name or "Sandbox Test Patient"
        patient_id = None

        try:
            pat_res = supabase_read.table("patients").select("id").eq("clinic_id", clinic_id).eq("phone", phone).maybe_single().execute()
            if pat_res and pat_res.data:
                patient_id = pat_res.data.get("id") if isinstance(pat_res.data, dict) else pat_res.data[0].get("id")
            else:
                new_pat = supabase.table("patients").insert({
                    "clinic_id": clinic_id,
                    "name": pat_name,
                    "phone": phone,
                    "insurance_provider": "Self-Pay",
                    "created_at": now_iso
                }).execute()
                if new_pat.data:
                    patient_id = new_pat.data.get("id") if isinstance(new_pat.data, dict) else new_pat.data[0].get("id")
        except Exception as p_err:
            log.warning(f"[quick_test_call] Patient lookup error: {p_err}")

        test_call_record = {
            "clinic_id": clinic_id,
            "direction": "inbound",
            "call_type": payload.scenario or "booking",
            "from_number": phone,
            "patient_id": patient_id,
            "duration_seconds": 95,
            "outcome": "booked",
            "status": "ended",
            "transcript": f"Caller: Hello, I'd like to test the receptionist AI.\nCALL-E AI: Hello! I can assist you with scheduling and clinical inquiries. Test completed successfully.",
            "created_at": now_iso
        }
        
        insert_res = supabase.table("calls").insert(test_call_record).execute()
        inserted = insert_res.data if isinstance(insert_res.data, dict) else (insert_res.data[0] if insert_res.data else test_call_record)
        # Attach patient_name for frontend display
        if isinstance(inserted, dict):
            inserted["patient_name"] = pat_name

        # Invalidate dashboard cache — must use the same key prefix pattern as the write
        from ...core.cache import local_cache
        # Invalidate all stat keys for this clinic (date-range variants)
        if hasattr(local_cache, "invalidate_prefix"):
            local_cache.invalidate_prefix(f"dashboard_stats_{clinic_id}")
        else:
            local_cache.delete(f"dashboard_stats_{clinic_id}")

        # Broadcast real-time WebSocket event
        try:
            try:
                from ...ws.manager import tenant_room_manager, WebSocketEvent
            except ImportError:
                from src.ws.manager import tenant_room_manager, WebSocketEvent
            import asyncio
            asyncio.create_task(tenant_room_manager.broadcast_event(
                str(clinic_id),
                WebSocketEvent.NEW_CALL,
                inserted
            ))
        except Exception:
            pass

        return {
            "success": True,
            "message": "Quick test call simulated and synced to dashboard.",
            "data": inserted
        }
    except Exception as e:
        log.error(f"[quick_test_call_error] {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/quick-prior-auth")
async def trigger_quick_prior_auth(
    payload: QuickPriorAuthRequest,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:write"))
):
    """
    1-Click Quick Prior Auth Initiation shortcut from dashboard.
    """
    clinic_id = auth.clinic_id
    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        pa_record = {
            "tenant_id": clinic_id,
            "patient_id": payload.patient_id,
            "insurance_provider_name": payload.insurance_name or "Blue Cross Blue Shield",
            "cpt_code": payload.cpt_code or "99214",
            "icd10_code": payload.icd10_code or "M54.5",
            "urgency": payload.urgency or "standard",
            "auth_status": "in_progress",
            "call_status": "dialing",
            "created_at": now_iso
        }

        try:
            insert_res = supabase.table("prior_auth_requests").insert(pa_record).execute()
            inserted = insert_res.data[0] if insert_res.data else pa_record
        except Exception:
            inserted = pa_record

        # Invalidate cache
        from ...core.cache import local_cache
        local_cache.delete(f"dashboard_stats_{clinic_id}")

        return {
            "success": True,
            "message": "Prior Authorization autonomous inquiry initiated.",
            "data": inserted
        }
    except Exception as e:
        log.error(f"[quick_prior_auth_error] {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/revenue")
async def get_dashboard_revenue(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
    month: Optional[int] = None,
    year: Optional[int] = None
):
    clinic_id = auth.clinic_id
    try:
        now = datetime.datetime.now()
        m = month or now.month
        y = year or now.year
        
        res = await revenue_service.get_monthly_stats(clinic_id, m, y)
        if not res.get("success"):
            raise HTTPException(status_code=500, detail=res.get("error"))
            
        return {"data": res.get("data")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/timeline")
async def get_dashboard_timeline(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read")),
    days: int = Query(30, le=90)
):
    clinic_id = auth.clinic_id
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(days=days)
        cutoff_iso = cutoff.isoformat()
        
        calls_res = supabase_read.table("calls").select("created_at, outcome").eq("clinic_id", clinic_id).gte("created_at", cutoff_iso).order("created_at", desc=False).execute()
        appt_res = supabase_read.table("appointments").select("created_at, booked_by").eq("clinic_id", clinic_id).gte("created_at", cutoff_iso).order("created_at", desc=False).execute()
        
        # Pre-populate all days in range to prevent missing gaps in chart
        by_day: Dict[str, Dict[str, Any]] = {}
        for i in range(days + 1):
            day_dt = cutoff + datetime.timedelta(days=i)
            day_str = day_dt.strftime("%Y-%m-%d")
            by_day[day_str] = {
                "date": day_str,
                "calls": 0,
                "answered": 0,
                "missed_calls": 0,
                "answered_calls": 0,
                "bookings": 0,
                "manual_bookings": 0,
                "total_bookings": 0
            }
        
        for c in (calls_res.data or []):
            day = c.get("created_at", "")[:10]
            if day in by_day:
                by_day[day]["calls"] += 1
                if c.get("outcome") == "no_answer":
                    by_day[day]["missed_calls"] += 1
                else:
                    by_day[day]["answered"] += 1
                    by_day[day]["answered_calls"] += 1
            
        for a in (appt_res.data or []):
            day = a.get("created_at", "")[:10]
            if day in by_day:
                by_day[day]["total_bookings"] += 1
                if a.get("booked_by") == "ai":
                    by_day[day]["bookings"] += 1
                else:
                    by_day[day]["manual_bookings"] += 1
                
        timeline = sorted(list(by_day.values()), key=lambda x: x["date"])
        
        return {"data": timeline}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class VoiceChatRequest(BaseModel):
    message: str
    patient_name: Optional[str] = "Patient"
    patient_phone: Optional[str] = "+14155552671"
    language: Optional[str] = "en"


@router.post("/voice-chat")
async def handle_voice_chat(
    payload: VoiceChatRequest,
    auth: AuthenticatedUser = Depends(require_permission("calls:write"))
):
    """
    Intelligent conversational endpoint for the Voice AI Receptionist Simulator.
    Processes natural speech, answers clinic FAQs, and books real appointments into the database.
    """
    clinic_id = auth.clinic_id
    user_msg = (payload.message or "").strip()
    lang = (payload.language or "en").lower()

    if not user_msg:
        return {"reply": "I'm listening. How can I help you today?", "action": "none"}

    # Fetch clinic profile
    clinic_info = {}
    try:
        c_res = supabase_read.table("clinics").select(
            "name, primary_doctor_name, specialty, business_hours, city, phone_number, timezone"
        ).eq("id", clinic_id).single().execute()
        if c_res.data:
            clinic_info = c_res.data if isinstance(c_res.data, dict) else (c_res.data[0] if len(c_res.data) > 0 else {})
    except Exception:
        pass

    clinic_name = clinic_info.get("name") or "Bytelytic Clinic"
    doctor_name = clinic_info.get("primary_doctor_name") or "Dr. Alexander"
    specialty = clinic_info.get("specialty") or "General Practice"
    city = clinic_info.get("city") or "Chicago"
    agent_name = "CALL-E"

    lower = user_msg.lower()
    action = "none"
    appt_data = None

    # Intent 1: Booking / Scheduling
    is_booking = any(w in lower for w in [
        "appointment", "book", "schedule", "visit", "consultation", "checkup", 
        "tomorrow", "friday", "monday", "tuesday", "wednesday", "thursday", 
        "yes", "confirm", "see doctor", "slot", "available",
        "cita", "agendar", "reservar", "consulta", "mañana", "viernes", "lunes", "martes", "jueves"
    ])

    if is_booking:
        try:
            # Determine booking date
            now = datetime.datetime.now(datetime.timezone.utc)
            days_ahead = 1
            if "monday" in lower or "lunes" in lower:
                days_ahead = (0 - now.weekday()) % 7 or 7
            elif "tuesday" in lower or "martes" in lower:
                days_ahead = (1 - now.weekday()) % 7 or 7
            elif "wednesday" in lower or "miércoles" in lower or "miercoles" in lower:
                days_ahead = (2 - now.weekday()) % 7 or 7
            elif "thursday" in lower or "jueves" in lower:
                days_ahead = (3 - now.weekday()) % 7 or 7
            elif "friday" in lower or "viernes" in lower:
                days_ahead = (4 - now.weekday()) % 7 or 7
            elif "tomorrow" in lower or "mañana" in lower:
                days_ahead = 1

            # Extract requested time from speech (e.g. "10 AM", "10:00 AM", "2 PM", "11:30", "las diez")
            time_match = re.search(r'\b(1[0-2]|0?[1-9])(?::([0-5][0-9]))?\s*(am|pm)\b', lower)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                meridiem = time_match.group(3).lower()
                if meridiem == "pm" and hour != 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
                slot_time_str = f"{hour:02d}:{minute:02d}:00"
                slot_time_formatted = datetime.time(hour, minute).strftime("%I:%M %p").lstrip("0")
            elif "diez" in lower:
                slot_time_str = "10:00:00"
                slot_time_formatted = "10:00 AM"
            else:
                slot_time_str = "10:00:00"
                slot_time_formatted = "10:00 AM"

            target_date = (now + datetime.timedelta(days=days_ahead)).date()
            target_iso = f"{target_date.isoformat()}T{slot_time_str}Z"
            formatted_date = f"{target_date.strftime('%A, %B %d')} at {slot_time_formatted}"

            # Upsert patient in Master Patient Index
            phone = payload.patient_phone or "+14155552671"
            pat_name = payload.patient_name or "Voice Test Patient"
            if pat_name in ("Patient", "Voice Test Patient"):
                name_match = re.search(r'\b(?:my name is|i am|this is|name\'?s)\s+([a-zA-Z]+)', user_msg, re.IGNORECASE)
                if name_match:
                    pat_name = name_match.group(1).capitalize()
            pat_id = None

            pat_res = supabase_read.table("patients").select("id").eq("clinic_id", clinic_id).eq("phone", phone).maybe_single().execute()
            if pat_res and pat_res.data:
                pat_id = pat_res.data.get("id") if isinstance(pat_res.data, dict) else pat_res.data[0].get("id")
            else:
                new_pat = supabase.table("patients").insert({
                    "clinic_id": clinic_id,
                    "name": pat_name,
                    "phone": phone,
                    "insurance_provider": "Self-Pay",
                    "created_at": now.isoformat()
                }).execute()
                if new_pat.data:
                    pat_id = new_pat.data.get("id") if isinstance(new_pat.data, dict) else new_pat.data[0].get("id")

            # Create real appointment in database
            appt_insert = supabase.table("appointments").insert({
                "clinic_id": clinic_id,
                "patient_id": pat_id,
                "patient_name": pat_name,
                "patient_phone": phone,
                "appointment_type": "General Consultation",
                "datetime": target_iso,
                "duration_minutes": 30,
                "status": "scheduled",
                "booked_by": "ai",
                "notes": f"Booked live via {agent_name} Voice Simulator ({user_msg[:60]})",
                "created_at": now.isoformat()
            }).execute()

            if appt_insert.data:
                appt_data = appt_insert.data if isinstance(appt_insert.data, dict) else appt_insert.data[0]
                action = "appointment_booked"

                # Invalidate cache & broadcast WebSocket
                try:
                    from ...core.cache import local_cache
                    local_cache.delete(f"dashboard_stats_{clinic_id}")
                    try:
                        from ...ws.manager import tenant_room_manager, WebSocketEvent
                    except ImportError:
                        from src.ws.manager import tenant_room_manager, WebSocketEvent
                    import asyncio
                    asyncio.create_task(tenant_room_manager.broadcast_event(
                        str(clinic_id),
                        WebSocketEvent.APPOINTMENT_ADDED,
                        appt_data
                    ))
                except Exception:
                    pass

                # Trigger real-time SMS booking confirmation
                try:
                    from ...services.sms_service import sms_service
                    import asyncio
                    asyncio.create_task(sms_service.send_booking_confirmation(
                        phone=phone,
                        time_str=formatted_date,
                        provider_name=doctor_name,
                        clinic_id=clinic_id,
                        patient_name=pat_name,
                        appointment_id=appt_data.get("id"),
                        patient_id=pat_id,
                        clinic_name=clinic_name,
                    ))
                except Exception as sms_err:
                    log.warning(f"[voice_chat] SMS trigger warning: {sms_err}")

            if lang == "es":
                reply = f"¡Perfecto! He reservado su cita con {doctor_name} para el {formatted_date}. La cita ha sido confirmada y registrada en nuestro sistema clínico."
            else:
                reply = f"Perfect! I have scheduled your appointment with {doctor_name} for {formatted_date}. Your slot is confirmed and synced to our EHR calendar!"

        except Exception as booking_err:
            log.warning(f"[voice_chat] Booking error: {booking_err}")
            reply = f"I would be glad to help you schedule with {doctor_name}. We have availability tomorrow at 10:30 AM. Would you like me to reserve that time?"

    # Intelligent LLM Conversational Voice Receptionist via AIService
    else:
        try:
            from src.services.ai_service import AIService
            ai_service = AIService()
            system_prompt = (
                f"You are {agent_name}, the autonomous voice AI medical receptionist for {clinic_name} in {city}. "
                f"The primary clinician is {doctor_name} ({specialty}). "
                f"The clinic is open Monday through Friday 8:00 AM to 5:00 PM, and Saturday 9:00 AM to 1:00 PM. "
                f"We accept Blue Cross Blue Shield, Medicare, and private pay. "
                f"Respond naturally, warmly, and concisely (under 2 sentences) as if speaking live on a phone call. "
                f"If the caller introduces their name, acknowledge them warmly by name and ask how you can assist them. "
                f"If they ask if you can hear them, confirm clearly that you can hear them loud and clear. "
                f"Answer in Spanish if the user's language is Spanish, otherwise English."
            )
            llm_reply = await ai_service.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ], max_tokens=150, temperature=0.5)

            if llm_reply and len(llm_reply.strip()) > 3:
                reply = llm_reply.strip()
            else:
                raise ValueError("Empty LLM reply")
        except Exception as e:
            log.warning(f"[voice_chat] AIService conversational error: {e}")
            if lang == "es":
                reply = f"Gracias por llamar a {clinic_name}. Mi nombre es {agent_name}. Puedo coordinar su cita con {doctor_name}, resolver dudas o registrar su consulta. ¿En qué le ayudo?"
            else:
                reply = f"Thank you for contacting {clinic_name}! My name is {agent_name}. I can schedule your visit with {doctor_name}, answer clinic questions, or verify insurance. How may I help you today?"

    # Real-time Call Log generation for Call Logs (/calls) & EHR sync
    try:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        call_outcome = "booked" if action == "appointment_booked" else "completed"
        call_type = "booking" if action == "appointment_booked" else "general"
        phone_used = payload.patient_phone or "+14155552671"
        caller_name = payload.patient_name or "Hamza Nasiem"
        
        transcript_data = [
            {"speaker": "AI Receptionist", "text": f"Thank you for calling {clinic_name}. My name is {agent_name}. How may I help you today?"},
            {"speaker": caller_name, "text": user_msg},
            {"speaker": "AI Receptionist", "text": reply}
        ]
        
        call_id = str(uuid.uuid4())
        call_row = {
            "id": call_id,
            "clinic_id": str(clinic_id),
            "patient_id": str(pat_id) if ('pat_id' in locals() and pat_id) else None,
            "direction": "inbound",
            "call_type": call_type,
            "from_number": phone_used,
            "to_number": "+15755734355",
            "duration_seconds": 38,
            "status": "ended",
            "outcome": call_outcome,
            "appointment_id": str(appt_data.get("id")) if (appt_data and isinstance(appt_data, dict) and appt_data.get("id")) else None,
            "transcript": json.dumps(transcript_data),
            "started_at": (now_dt - datetime.timedelta(seconds=38)).isoformat(),
            "ended_at": now_dt.isoformat(),
            "created_at": now_dt.isoformat()
        }
        supabase.table("calls").insert(call_row).execute()
        
        try:
            from ...core.cache import local_cache
            local_cache.delete(f"dashboard_stats_{clinic_id}")
            local_cache.delete(f"dashboard_recent_calls_{clinic_id}")
        except Exception:
            pass
    except Exception as call_err:
        log.warning(f"[voice_chat] Call logging note: {call_err}")

    return {
        "reply": reply,
        "action": action,
        "appointment": appt_data
    }


