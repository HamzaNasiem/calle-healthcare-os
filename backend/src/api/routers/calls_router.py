import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.database import supabase, supabase_read
from ...core.security import require_permission, AuthenticatedUser, require_active_subscription
from ...services.audit_service import audit_service

router = APIRouter(prefix="/calls", tags=["Calls"], dependencies=[Depends(require_active_subscription)])

@router.get("")
async def get_calls(
    auth: AuthenticatedUser = Depends(require_permission("calls:read")),
    page: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, le=200),
    cursor: Optional[str] = None,
    direction: Optional[str] = None,
    call_type: Optional[str] = None,
    campaign_type: Optional[str] = None,
    status: Optional[str] = None,
    outcome: Optional[str] = None,
    patient_id: Optional[str] = None,
    from_number: Optional[str] = None,
    appointment_id: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    clinic_id = auth.clinic_id
    
    # 1. Query calls table (patient_name is not a column — joined via patients table)
    query = supabase_read.table("calls").select(
        "id, direction, call_type, from_number, to_number, patient_id, duration_seconds, outcome, status, transcript, recording_url, started_at, ended_at, appointment_id, created_at",
        count="exact"
    ).eq("clinic_id", clinic_id).order("created_at", desc=True)
    
    if direction and direction != "all":
        query = query.eq("direction", direction)
    target_type = campaign_type or call_type
    if target_type and target_type != "all":
        query = query.eq("call_type", target_type)
    if status and status != "all":
        query = query.eq("status", status)
    if outcome and outcome != "all":
        query = query.eq("outcome", outcome)
    if patient_id:
        query = query.eq("patient_id", patient_id)
    if from_number:
        query = query.eq("from_number", from_number)
    if appointment_id:
        query = query.eq("appointment_id", appointment_id)
    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        query = query.lte("created_at", date_to)
    if search:
        query = query.or_(f"from_number.ilike.%{search}%,to_number.ilike.%{search}%")
    
    if cursor:
        query = query.lt("created_at", cursor).limit(limit)
    elif page is not None:
        offset = (page - 1) * limit
        query = query.range(offset, offset + limit - 1)
    else:
        query = query.limit(limit)
        
    try:
        res = await asyncio.get_event_loop().run_in_executor(None, query.execute)
        calls_data = res.data or []
        total_count = res.count or len(calls_data)

        # 2. Also fetch any outbound_calls if calls table is small/empty or if outbound campaign calls exist
        try:
            outbound_q = supabase_read.table("outbound_calls").select(
                "id, clinic_id, campaign_type, calle_call_id, status, task_completed, structured_result, summary, transcript, transcript_turns, recording_url, duration_seconds, completion_score, completion_label, evidence, appointment_id, patient_id, created_at, completed_at, patients(id, name, phone)",
                count="exact"
            ).eq("clinic_id", clinic_id).order("created_at", desc=True).limit(limit)
            
            if target_type and target_type != "all":
                outbound_q = outbound_q.eq("campaign_type", target_type)
            if status and status != "all":
                outbound_q = outbound_q.eq("status", status)
                
            outbound_res = await asyncio.get_event_loop().run_in_executor(None, outbound_q.execute)
            if outbound_res.data:
                # Merge outbound records if not already represented in calls_data
                existing_ids = {c.get("id") for c in calls_data}
                for oc in outbound_res.data:
                    if oc["id"] not in existing_ids:
                        sr = oc.get("structured_result") or {}
                        outcome_val = "completed"
                        if sr.get("will_attend") == "yes":
                            outcome_val = "booked"
                        elif sr.get("will_attend") in ("no", "cancelled"):
                            outcome_val = "cancelled"
                        elif sr.get("will_attend") == "rescheduled" or sr.get("reschedule_request"):
                            outcome_val = "rescheduled"
                        elif oc.get("status") in ("failed", "no_answer", "voicemail"):
                            outcome_val = oc.get("status")

                        pat_obj = oc.get("patients") or {}
                        pat_name = pat_obj.get("name") if isinstance(pat_obj, dict) else None
                        pat_phone = pat_obj.get("phone") if isinstance(pat_obj, dict) else None

                        calls_data.append({
                            "id": oc["id"],
                            "direction": "outbound",
                            "call_type": oc.get("campaign_type", "confirmation"),
                            "status": oc.get("status", "completed"),
                            "outcome": outcome_val,
                            "patient_id": oc.get("patient_id"),
                            "patient_name": pat_name,
                            "from_number": "Clinic AI",
                            "to_number": pat_phone or "Patient",
                            "appointment_id": oc.get("appointment_id"),
                            "summary": oc.get("summary"),
                            "transcript": oc.get("transcript"),
                            "transcript_turns": oc.get("transcript_turns"),
                            "recording_url": oc.get("recording_url"),
                            "structured_result": oc.get("structured_result"),
                            "completion_score": oc.get("completion_score"),
                            "completion_label": oc.get("completion_label"),
                            "evidence": oc.get("evidence"),
                            "duration_seconds": oc.get("duration_seconds") or 0,
                            "created_at": oc.get("created_at"),
                            "started_at": oc.get("created_at"),
                            "ended_at": oc.get("completed_at"),
                            "patients": pat_obj if pat_obj else None,
                        })
                # Re-sort descending by created_at
                calls_data.sort(key=lambda x: x.get("created_at") or "", reverse=True)
                calls_data = calls_data[:limit]
        except Exception:
            pass

        # Resolve patient names for all call records using flat patients table
        patient_ids = list({str(c["patient_id"]) for c in calls_data if c.get("patient_id")})
        if patient_ids:
            try:
                from ...core.database import LocalPostgresClient
                _db = LocalPostgresClient()
                placeholders = ",".join(["%s"] * len(patient_ids))
                p_rows = _db.execute(
                    f"SELECT id::text, name, phone FROM patients WHERE id::text IN ({placeholders})",
                    tuple(patient_ids)
                )
                p_map = {r["id"]: r for r in p_rows}
                for c in calls_data:
                    pid = str(c.get("patient_id") or "")
                    if pid in p_map:
                        c["patient_name"] = p_map[pid].get("name") or c.get("patient_name")
                        if not c.get("patients"):
                            c["patients"] = {"name": p_map[pid].get("name"), "phone": p_map[pid].get("phone")}
            except Exception as pe:
                log.warning(f"[calls] Patient name resolution note: {pe}")

        # Check 24-hour HIPAA auto-purge on recording_url
        now_dt = datetime.now(timezone.utc)
        for c in calls_data:
            created_at_str = c.get("created_at")
            if created_at_str and c.get("recording_url"):
                try:
                    c_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if now_dt - c_dt > timedelta(hours=24):
                        c["recording_url"] = None
                        c["recording_purged"] = True
                    else:
                        c["recording_purge_scheduled"] = (c_dt + timedelta(hours=24)).isoformat()
                except Exception:
                    pass

        next_cursor = calls_data[-1]["created_at"] if len(calls_data) == limit and calls_data else None
        
        meta = {
            "limit": limit,
            "total": total_count
        }
        if page is not None:
            meta["page"] = page
        if next_cursor:
            meta["next_cursor"] = next_cursor
            
        return {"data": calls_data, "meta": meta}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{id}")
async def get_call(id: str, auth: AuthenticatedUser = Depends(require_permission("calls:read"))):
    clinic_id = auth.clinic_id
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("calls").select(
                "*, appointments(id, appointment_type, datetime, status), patients(id, name, phone)"
            ).eq("id", id).eq("clinic_id", clinic_id).execute()
        )
        
        if res.data:
            call_obj = res.data[0]
            # HIPAA recording purge calculation
            created_at_str = call_obj.get("created_at")
            if created_at_str and call_obj.get("recording_url"):
                try:
                    c_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    if now_dt - c_dt > timedelta(hours=24):
                        call_obj["recording_url"] = None
                        call_obj["recording_purged"] = True
                    else:
                        call_obj["recording_purge_scheduled"] = (c_dt + timedelta(hours=24)).isoformat()
                except Exception:
                    pass
            return {"data": call_obj}

        # Fallback check outbound_calls table
        outbound_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("outbound_calls").select(
                "*, appointments(id, appointment_type, datetime, status), patients(id, name, phone)"
            ).eq("id", id).eq("clinic_id", clinic_id).execute()
        )
        if outbound_res.data:
            return {"data": outbound_res.data[0]}

        raise HTTPException(status_code=404, detail="Call not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


