import hashlib
import hmac
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ws.manager import tenant_room_manager as ws_manager
from src.config.settings import settings
from src.core.security import get_current_user_with_role, require_permission
from src.db.engine import get_db
from src.models.appointment import Appointment
from src.models.outbound_call import OutboundCall
from src.models.outbox import OutboxEvent
from src.models.patient import Patient
from src.models.tenant import Tenant
from src.models.user import User
from src.models.waitlist import Waitlist
from src.services.audit_service import audit_service
from src.services.calle_service import calle_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/outbound-calls", tags=["outbound-calls"])


class TriggerCallRequest(BaseModel):
    appointment_id: uuid.UUID
    call_type: str  # confirmation | no_show_recovery | waitlist_fill | pre_appointment


async def _trigger_waitlist_fill_workflow(db: AsyncSession, cancelled_appt: Appointment):
    """
    FR-016 / FR-017 / FR-018: Trigger waitlist workflow within 60s of cancellation.
    Searches for waiting patients on waitlist and attempts to fill the open slot.
    """
    try:
        stmt = select(Waitlist).where(
            Waitlist.tenant_id == cancelled_appt.tenant_id,
            Waitlist.status == "waiting"
        ).order_by(Waitlist.created_at.asc())
        res = await db.execute(stmt)
        wait_entry = res.scalars().first()

        if not wait_entry:
            log.info(f"No waiting patients on waitlist for tenant {cancelled_appt.tenant_id}")
            return

        # Fetch waitlisted patient details
        pat_stmt = select(Patient).where(Patient.id == wait_entry.patient_id)
        pat_res = await db.execute(pat_stmt)
        wait_patient = pat_res.scalars().first()
        if not wait_patient:
            return

        patient_phone = wait_patient.phone or "+15551234567"
        tenant = await db.get(Tenant, cancelled_appt.tenant_id)
        clinic_name = tenant.name if tenant else "Sunrise Medical Clinic"
        slot_date = cancelled_appt.slot_start.strftime("%B %d, %Y")
        slot_time = cancelled_appt.slot_start.strftime("%I:%M %p")
        idempotency_key = f"waitlist_fill:{cancelled_appt.id}:{wait_entry.id}:{datetime.now(UTC).strftime('%Y%m%d%H%M')}"

        call_record = OutboundCall(
            id=uuid.uuid4(),
            tenant_id=cancelled_appt.tenant_id,
            appointment_id=cancelled_appt.id,
            patient_id=wait_patient.id,
            call_type="waitlist_fill",
            idempotency_key=idempotency_key,
            status="in_progress",
            placed_at=datetime.now(UTC)
        )
        db.add(call_record)
        await db.commit()

        result = await calle_service.place_waitlist_fill_call(patient_phone, clinic_name, slot_date, slot_time, idempotency_key)
        call_record.calle_call_id = result.get("id") or result.get("call_id")
        call_record.status = result.get("status", "completed")
        call_record.task_completed = result.get("task_completed", True)
        call_record.structured_result = result.get("structured_result")
        call_record.summary = result.get("summary")
        call_record.completed_at = datetime.now(UTC)

        struct_res = result.get("structured_result", {})
        if struct_res.get("accepts_slot"):
            # Book slot for waitlisted patient
            wait_entry.status = "booked"
            new_appt = Appointment(
                id=uuid.uuid4(),
                tenant_id=cancelled_appt.tenant_id,
                patient_id=wait_patient.id,
                provider_id=cancelled_appt.provider_id,
                slot_start=cancelled_appt.slot_start,
                slot_end=cancelled_appt.slot_end,
                service_type=cancelled_appt.service_type,
                duration_minutes=cancelled_appt.duration_minutes,
                status="scheduled",
                booked_by="ai_waitlist_agent",
                confirmation_code=f"WL-{uuid.uuid4().hex[:6].upper()}",
                call_confirmed=True,
                row_hash=hashlib.sha256(f"wl_appt_{datetime.now(UTC)}".encode()).hexdigest(),
                is_deleted=False
            )
            db.add(new_appt)
            log.info(f"[Waitlist Auto-Fill] Successfully booked open slot for patient {wait_patient.id}")

        await db.commit()
    except Exception as e:
        log.error(f"Error in _trigger_waitlist_fill_workflow: {e}")


async def _trigger_sms_fallback_if_needed(db: AsyncSession, call_record: OutboundCall, appt: Appointment):
    """
    FR-015 / US-008: Telnyx SMS Fallback if CALL-E call results in `no_answer` or `voicemail`.
    """
    struct_res = call_record.structured_result or {}
    call_outcome = struct_res.get("will_attend") or struct_res.get("response_type") or call_record.status

    if call_outcome in ["no_answer", "voicemail", "failed"]:
        try:
            pat_stmt = select(Patient).where(Patient.id == appt.patient_id)
            pat_res = await db.execute(pat_stmt)
            patient = pat_res.scalars().first()
            if not patient:
                return

            phone = patient.phone or "+15551234567"
            time_str = appt.slot_start.strftime("%I:%M %p")

            sms_event = OutboxEvent(
                event_type="SEND_SMS",
                tenant_id=appt.tenant_id,
                payload={
                    "type": "fallback_reminder",
                    "patient_id": str(patient.id),
                    "appointment_id": str(appt.id),
                    "to_number": phone,
                    "patient_name": patient.full_name or "Patient",
                    "apt_time": time_str,
                    "message": f"Reminder: Your appointment is scheduled for tomorrow at {time_str}. Please reply YES to confirm or call us to reschedule."
                }
            )
            db.add(sms_event)
            await db.commit()
            log.info(f"[SMS Fallback] Queued Telnyx SMS fallback for unanswered call {call_record.id}")
        except Exception as sms_err:
            log.error(f"Error queuing SMS fallback: {sms_err}")


async def _apply_call_result_logic(db: AsyncSession, call_record: OutboundCall):
    """
    Applies business logic based on structured CALL-E results:
    - Update appointment status (cancelled/rescheduled/confirmed)
    - Trigger waitlist matching if appointment cancelled (FR-016)
    - Queue Telnyx SMS fallback if no answer (FR-015)
    - Send real-time WebSocket notification to clinic staff (FR-009)
    """
    if not call_record.appointment_id:
        return

    stmt = select(Appointment).where(Appointment.id == call_record.appointment_id)
    res = await db.execute(stmt)
    appt = res.scalars().first()
    if not appt:
        return

    struct_res = call_record.structured_result or {}

    # 1. Confirmation Call Logic
    if call_record.call_type == "confirmation":
        will_attend = struct_res.get("will_attend")
        if will_attend == "yes":
            appt.call_confirmed = True
            appt.confirmation_call_id = call_record.id
        elif will_attend == "no":
            appt.status = "cancelled"
            appt.cancellation_reason = "Cancelled via automated CALL-E confirmation call"
            appt.cancelled_at = datetime.now(UTC)
            await _trigger_waitlist_fill_workflow(db, appt)
        elif will_attend == "rescheduled" or struct_res.get("reschedule_request"):
            appt.status = "rescheduled"

    # 2. No-Show Recovery Logic
    elif call_record.call_type == "no_show_recovery":
        resp_type = struct_res.get("response_type")
        if resp_type == "rescheduled":
            appt.status = "rescheduled"

    # 3. Pre-Appointment Logic
    elif call_record.call_type == "pre_appointment":
        if struct_res.get("acknowledged"):
            appt.pre_appointment_call_sent = True

    await db.commit()

    # 4. Check for SMS Fallback
    await _trigger_sms_fallback_if_needed(db, call_record, appt)

    # 5. Broadcast real-time WebSocket event to clinic frontend dashboard
    try:
        ws_event = {
            "event": "outbound_call_completed",
            "data": {
                "outbound_call_id": str(call_record.id),
                "appointment_id": str(call_record.appointment_id),
                "call_type": call_record.call_type,
                "status": call_record.status,
                "task_completed": call_record.task_completed,
                "structured_result": call_record.structured_result,
                "confidence_score": call_record.completion_confidence_score,
                "summary": call_record.summary,
                "reschedule_request": struct_res.get("reschedule_request", False),
                "has_question": struct_res.get("has_question", False),
                "question_text": struct_res.get("question_text", "")
            }
        }
        await ws_manager.broadcast_to_tenant(str(call_record.tenant_id), ws_event)
    except Exception as ws_err:
        log.warning(f"WebSocket broadcast error: {ws_err}")


@router.post("/trigger")
async def trigger_outbound_call(
    req: TriggerCallRequest,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger an outbound CALL-E patient call.
    """
    stmt = select(Appointment).where(
        Appointment.id == req.appointment_id,
        Appointment.tenant_id == user.tenant_id,
        Appointment.is_deleted == False
    )
    res = await db.execute(stmt)
    appt = res.scalars().first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    pat_stmt = select(Patient).where(Patient.id == appt.patient_id)
    pat_res = await db.execute(pat_stmt)
    patient = pat_res.scalars().first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    tenant = await db.get(Tenant, user.tenant_id)
    clinic_name = tenant.name if tenant else "Sunrise Medical Clinic"
    time_str = appt.slot_start.strftime("%I:%M %p")
    date_str = appt.slot_start.strftime("%B %d, %Y")

    idempotency_key = f"CALL_{req.call_type.upper()}_{appt.id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    patient_phone = patient.phone or "+15551234567"

    call_record = OutboundCall(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        appointment_id=appt.id,
        patient_id=patient.id,
        call_type=req.call_type,
        idempotency_key=idempotency_key,
        status="in_progress",
        placed_at=datetime.now(UTC)
    )
    db.add(call_record)
    await db.commit()
    await db.refresh(call_record)

    try:
        if req.call_type == "confirmation":
            result = await calle_service.place_confirmation_call(patient_phone, clinic_name, time_str, idempotency_key)
        elif req.call_type == "no_show_recovery":
            result = await calle_service.place_no_show_recovery_call(patient_phone, clinic_name, time_str, idempotency_key)
        elif req.call_type == "waitlist_fill":
            result = await calle_service.place_waitlist_fill_call(patient_phone, clinic_name, date_str, time_str, idempotency_key)
        elif req.call_type == "pre_appointment":
            result = await calle_service.place_pre_appointment_call(patient_phone, clinic_name, time_str, idempotency_key)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid call_type: {req.call_type}")

        call_record.calle_call_id = result.get("id") or result.get("call_id")
        call_record.status = result.get("status", "completed")
        call_record.task_completed = result.get("task_completed", True)
        call_record.structured_result = result.get("structured_result")
        call_record.summary = result.get("summary")
        call_record.evidence = result.get("evidence")
        
        conf = result.get("completion_confidence", {})
        call_record.completion_confidence_score = conf.get("score")
        call_record.completion_confidence_label = conf.get("label")
        call_record.completed_at = datetime.now(UTC)

        await db.commit()
        await _apply_call_result_logic(db, call_record)

        await audit_service.log(
            action="OUTBOUND_CALL_PLACED",
            actor_id=user.id,
            target_table="outbound_calls",
            target_id=call_record.id,
            actor_type="user",
            actor_role=user.role,
            change_reason=f"Manually triggered {req.call_type} call",
            outcome="SUCCESS"
        )

        return {
            "success": True,
            "data": {
                "outbound_call_id": str(call_record.id),
                "calle_call_id": call_record.calle_call_id,
                "call_type": call_record.call_type,
                "status": call_record.status,
                "task_completed": call_record.task_completed,
                "structured_result": call_record.structured_result,
                "completion_confidence": conf,
                "summary": call_record.summary
            }
        }
    except Exception as e:
        log.error(f"Call placement failed: {e}")
        call_record.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to place call: {str(e)}")


@router.get("")
async def list_outbound_calls(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """
    List outbound CALL-E calls for the clinic.
    """
    stmt = select(OutboundCall).where(OutboundCall.tenant_id == user.tenant_id)
    
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt)

    stmt = stmt.order_by(OutboundCall.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    res = await db.execute(stmt)
    calls = res.scalars().all()

    out = []
    for c in calls:
        sr = c.structured_result or {}
        out.append({
            "id": str(c.id),
            "appointment_id": str(c.appointment_id) if c.appointment_id else None,
            "patient_id": str(c.patient_id) if c.patient_id else None,
            "call_type": c.call_type,
            "calle_call_id": c.calle_call_id,
            "status": c.status,
            "task_completed": c.task_completed,
            "structured_result": c.structured_result,
            "completion_confidence_score": c.completion_confidence_score,
            "completion_confidence_label": c.completion_confidence_label,
            "summary": c.summary,
            "reschedule_request": sr.get("reschedule_request", False),
            "has_question": sr.get("has_question", False),
            "question_text": sr.get("question_text", ""),
            "placed_at": c.placed_at.isoformat() if c.placed_at else None,
            "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None
        })

    return {
        "success": True,
        "data": {
            "calls": out,
            "meta": {"page": page, "per_page": per_page, "total": total}
        }
    }


@router.get("/stats")
async def get_outbound_call_stats(
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated dashboard statistics for outbound calls (FR-010).
    """
    stmt = select(OutboundCall).where(OutboundCall.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    calls = res.scalars().all()

    total_sent = len(calls)
    confirmed = 0
    no_answer = 0
    recovered = 0
    rescheduled = 0
    reschedule_requests_count = 0
    questions_count = 0

    for c in calls:
        sr = c.structured_result or {}
        if sr.get("will_attend") == "yes" or c.status == "completed":
            confirmed += 1
        if sr.get("will_attend") == "no_answer" or c.status == "no_answer":
            no_answer += 1
        if sr.get("response_type") == "rescheduled" or sr.get("will_attend") == "rescheduled":
            recovered += 1
            rescheduled += 1
        if sr.get("reschedule_request"):
            reschedule_requests_count += 1
        if sr.get("has_question"):
            questions_count += 1

    return {
        "success": True,
        "data": {
            "total_sent": total_sent,
            "confirmed": confirmed,
            "no_answer": no_answer,
            "recovered": recovered,
            "rescheduled": rescheduled,
            "reschedule_requests_count": reschedule_requests_count,
            "questions_count": questions_count,
            "confirmation_rate_pct": round((confirmed / max(total_sent, 1)) * 100, 1)
        }
    }


# ── Webhook Receiver ──────────────────────────────────────────────────
webhook_router = APIRouter(tags=["Webhooks"])


@webhook_router.post("/webhooks/calle")
async def calle_webhook_handler(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receives terminal call results from CALL-E platform. (FR-007 / FR-008)
    """
    if settings.calle_webhook_secret:
        body = await request.body()
        sig = request.headers.get("X-Calle-Signature", "")
        expected = "sha256=" + hmac.new(
            settings.calle_webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    call_id = payload.get("call_id")
    if not call_id:
        return {"received": True, "status": "no_call_id"}

    stmt = select(OutboundCall).where(OutboundCall.calle_call_id == call_id)
    res = await db.execute(stmt)
    call_record = res.scalars().first()

    if call_record:
        call_record.status = payload.get("status", "completed")
        call_record.task_completed = payload.get("task_completed")
        call_record.structured_result = payload.get("structured_result")
        call_record.summary = payload.get("summary")
        call_record.evidence = payload.get("evidence")
        call_record.completed_at = datetime.now(UTC)

        conf = payload.get("completion_confidence", {})
        call_record.completion_confidence_score = conf.get("score")
        call_record.completion_confidence_label = conf.get("label")

        await db.commit()
        await _apply_call_result_logic(db, call_record)
        
        await audit_service.log(
            action="OUTBOUND_CALL_COMPLETED",
            actor_id=None,
            target_table="outbound_calls",
            target_id=call_record.id,
            actor_type="system",
            actor_role="system",
            change_reason="Received webhook update from CALL-E",
            outcome="SUCCESS"
        )
        log.info(f"[Webhook CALLE] Outbound call {call_id} updated & business logic applied")

    return {"received": True, "call_id": call_id}
