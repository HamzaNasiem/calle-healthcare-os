import datetime
import hashlib
import hmac
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.core.cache import local_cache
from src.core.logger import log
from src.db.engine import get_db
from src.models.call_log import CallLog
from src.models.patient import Patient
from src.models.tenant_settings import TenantSettings
from src.schemas.webhook import RetellInboundRequest, RetellPostCallRequest, RetellToolRequest
from src.tools import get_tool

router = APIRouter(tags=["Webhooks", "Retell"])


def _normalize_phone(raw: str, default_country: str = "+1") -> str:
    """
    Normalizes any phone number format to standard E.164 (+1XXXXXXXXXX).
    Handles (555) 123-4567, 5551234567, 15551234567, +15551234567, and international.
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


async def verify_retell_signature(request: Request) -> bytes:
    """
    Verifies the cryptographic signature of incoming Retell webhooks.
    Supports Retell SDK verify, HMAC-SHA256 hex and Base64 signatures.
    """
    body = await request.body()
    secret_key = (
        settings.retell_webhook_secret
        or settings.RETELL_WEBHOOK_SECRET
        or settings.retell_api_key
        or settings.RETELL_API_KEY
    )

    if not secret_key:
        if settings.is_prod:
            log.critical("[Retell Webhook] Secret key missing in production. Rejecting webhook.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook configuration error")
        return body

    signature = request.headers.get("X-Retell-Signature") or request.headers.get("x-retell-signature")
    if not signature:
        if not settings.is_prod:
            log.warning("[Retell Webhook] Missing signature header in development mode — proceeding.")
            return body
        log.warning("[Retell Webhook] Missing signature header in production.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")

    # 1. Try Retell official SDK verification if available
    try:
        from retell.lib import verify as retell_sdk_verify
        if retell_sdk_verify(body.decode("utf-8"), secret_key, signature):
            return body
    except Exception:
        pass

    # 2. Try HMAC-SHA256 hex digest comparison
    try:
        secret_bytes = secret_key.encode("utf-8")
        expected_hex = hmac.new(secret_bytes, body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_hex, signature):
            return body

        # Try Base64 digest comparison if signature was base64-encoded
        import base64
        expected_b64 = base64.b64encode(hmac.new(secret_bytes, body, hashlib.sha256).digest()).decode("utf-8")
        if hmac.compare_digest(expected_b64, signature):
            return body
    except Exception as e:
        log.error(f"[Retell Webhook] Signature comparison error: {e}")

    log.warning("[Retell Webhook] Invalid signature detected — potential replay or forgery attempt.")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")


async def get_tenant_id(db: AsyncSession) -> str:
    """Helper to get default tenant_id in single-clinic mode."""
    stmt = select(TenantSettings.tenant_id).limit(1)
    result = await db.execute(stmt)
    tenant_id = result.scalar_one_or_none()
    if not tenant_id:
        if settings.DEFAULT_CLINIC_ID:
            return str(settings.DEFAULT_CLINIC_ID)
        raise HTTPException(status_code=500, detail="No tenant configured.")
    return str(tenant_id)


@router.post("/inbound")
async def handle_inbound(req: RetellInboundRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handles dynamic inbound call persona and greeting configuration for Retell AI.
    Fetches real-time clinic business hours, timezone, doctor credentials,
    and patient recognition for personalized receptionist greeting.
    """
    await verify_retell_signature(request)
    call_id = req.call.call_id
    log.info(f"[Retell Webhook] Inbound call received: {call_id}")

    from_num_norm = _normalize_phone(req.call.from_number or "")
    to_num_norm = _normalize_phone(req.call.to_number or "")

    # 1. Resolve Tenant ID:
    # Check by DID (to_number) in TenantSettings, or fallback to single-clinic tenant
    tenant_id = None
    if to_num_norm:
        ts_match_stmt = select(TenantSettings.tenant_id).where(
            TenantSettings.clinic_phone == to_num_norm
        ).limit(1)
        ts_match_res = await db.execute(ts_match_stmt)
        tenant_id = ts_match_res.scalar_one_or_none()

    if not tenant_id and from_num_norm:
        phone_hash = hashlib.sha256(from_num_norm.encode("utf-8")).hexdigest()
        p_stmt = select(Patient.tenant_id).where(
            Patient.phone_hash == phone_hash,
            Patient.is_deleted == False
        ).limit(1)
        p_res = await db.execute(p_stmt)
        tenant_id = p_res.scalar_one_or_none()

    if not tenant_id:
        tenant_id = await get_tenant_id(db)

    from src.core.tenant_context import set_tenant_id
    set_tenant_id(uuid.UUID(str(tenant_id)))

    # 2. Retrieve Clinic & AI Persona Settings (with local cache)
    cache_key = f"t:{tenant_id}:settings"
    settings_data = local_cache.get(cache_key)

    if not settings_data:
        stmt = select(TenantSettings).where(TenantSettings.tenant_id == uuid.UUID(str(tenant_id)))
        settings_obj = (await db.execute(stmt)).scalars().first()
        if settings_obj:
            settings_data = {
                "ai_persona": settings_obj.ai_persona,
                "ai_persona_prompt": settings_obj.ai_persona_prompt,
                "business_hours": settings_obj.business_hours,
                "timezone": settings_obj.timezone or "America/New_York",
                "clinic_name": settings_obj.clinic_name or "Our Clinic",
                "clinic_address": settings_obj.clinic_address or "Medical Plaza",
                "transfer_number": settings_obj.transfer_number,
                "providers": settings_obj.providers,
            }
            local_cache.set(cache_key, settings_data, ttl=300)

    clinic_name = settings_data.get("clinic_name", "Our Clinic") if settings_data else "Our Clinic"
    ai_name = settings_data.get("ai_persona", {}).get("name", "Alex") if settings_data else "Alex"
    tz_str = settings_data.get("timezone", "America/New_York") if settings_data else "America/New_York"
    clinic_address = settings_data.get("clinic_address", "Medical Plaza") if settings_data else "Medical Plaza"
    transfer_number = settings_data.get("transfer_number") if settings_data else None

    # 3. Check for Returning Patient (HIPAA compliant - no plaintext phone in logs)
    patient_name = None
    if from_num_norm:
        try:
            phone_hash = hashlib.sha256(from_num_norm.encode("utf-8")).hexdigest()
            stmt_p = select(Patient).where(
                Patient.tenant_id == uuid.UUID(str(tenant_id)),
                Patient.phone_hash == phone_hash,
                Patient.is_deleted == False
            ).limit(1)
            p_obj = (await db.execute(stmt_p)).scalars().first()
            if p_obj and p_obj.full_name:
                patient_name = p_obj.full_name.split()[0]
        except Exception as p_err:
            log.warning(f"[Retell Webhook] Patient lookup warning: {p_err}")

    # 4. Compute Localized Time
    try:
        from zoneinfo import ZoneInfo
        local_tz = ZoneInfo(tz_str)
        now_local = datetime.datetime.now(local_tz)
    except Exception:
        now_local = datetime.datetime.now(datetime.UTC)
    current_time_str = now_local.strftime("%A, %B %d, %I:%M %p")

    # 5. Dynamic Greeting Generation
    if patient_name:
        default_greeting = f"Thank you for calling {clinic_name}. Hello {patient_name}, this is {ai_name}, your AI receptionist. How can I help you today?"
    else:
        default_greeting = f"Thank you for calling {clinic_name}. This is {ai_name}, your AI receptionist. How can I help you today?"

    custom_greeting = settings_data.get("ai_persona", {}).get("greeting") if settings_data else None
    if custom_greeting:
        greeting = custom_greeting.replace("{clinic_name}", clinic_name).replace("{ai_name}", ai_name)
    else:
        greeting = default_greeting

    # Format business hours string if dict
    bh_raw = settings_data.get("business_hours") if settings_data else None
    if isinstance(bh_raw, dict):
        hours_parts = []
        for k, v in bh_raw.items():
            if str(k).startswith("_"):
                continue
            hours_parts.append(f"{k}: {v}")
        if "_lunch_break" in bh_raw and isinstance(bh_raw["_lunch_break"], dict):
            lb = bh_raw["_lunch_break"]
            if lb.get("enabled"):
                hours_parts.append(f"lunch break: {lb.get('start', '12:00')}–{lb.get('end', '13:00')}")
        hours_display = ", ".join(hours_parts) if hours_parts else "Monday to Friday 8:00 AM - 5:00 PM"
    elif isinstance(bh_raw, str):
        hours_display = bh_raw
    else:
        hours_display = "Monday to Friday 8:00 AM - 5:00 PM"

    agent_override = settings.retell_agent_id or settings.RETELL_AGENT_ID or None

    return {
        "llm_websocket_url": None,
        "override_agent_id": agent_override,
        "dynamic_variables": {
            "clinic_name": clinic_name,
            "ai_persona_name": ai_name,
            "business_hours": hours_display,
            "timezone": tz_str,
            "current_time": current_time_str,
            "clinic_address": clinic_address,
            "transfer_number": transfer_number or "",
            "is_returning_patient": bool(patient_name),
            "patient_first_name": patient_name or "",
        },
        "begin_message": greeting
    }


@router.post("/post_call")
async def handle_post_call(req: RetellPostCallRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Processes post-call terminal webhook from Retell AI.
    HIPAA Safeguards:
      - Transcripts stored AES-256-GCM encrypted
      - Patient phone stored as SHA-256 hash
      - 24-hour recording purge scheduled for data minimization
      - Patient names masked in real-time WebSocket broadcasts
    """
    await verify_retell_signature(request)
    log.info(f"[Retell Webhook] Post call received: {req.data.call_id}")

    tenant_id = await get_tenant_id(db)
    from src.core.tenant_context import set_tenant_id
    set_tenant_id(uuid.UUID(str(tenant_id)))

    # 1. Encrypt Transcript (AES-256-GCM)
    from src.core.encryption import phi_crypto
    encrypted_transcript = phi_crypto.encrypt(req.data.transcript or "")

    # 2. Extract call summary and tool metadata
    call_summary = "completed"
    if req.data.call_analysis and isinstance(req.data.call_analysis, dict):
        call_summary = req.data.call_analysis.get("call_summary", "completed")

    tools_called = []
    if req.data.metadata and isinstance(req.data.metadata, dict):
        tools_called = req.data.metadata.get("tools_called", [])
    tools_str = ",".join(tools_called) if isinstance(tools_called, list) else str(tools_called)

    # 3. Patient Resolution via phone hash or metadata
    patient_id = req.data.metadata.get("patient_id") if req.data.metadata and isinstance(req.data.metadata, dict) else None
    customer_phone_hash = None

    if req.data.customer_number:
        norm_cust = _normalize_phone(req.data.customer_number)
        customer_phone_hash = hashlib.sha256(norm_cust.encode("utf-8")).hexdigest()
        if not patient_id:
            stmt = select(Patient).where(
                Patient.phone_hash == customer_phone_hash,
                Patient.is_deleted == False
            )
            patient_obj = (await db.execute(stmt)).scalars().first()
            if patient_obj:
                patient_id = patient_obj.id

    # HIPAA Data Minimization: Schedule recording purge 24 hours from call completion
    now_utc = datetime.datetime.now(datetime.UTC)
    purge_time = now_utc + datetime.timedelta(hours=24)

    new_call_log = CallLog(
        tenant_id=uuid.UUID(str(tenant_id)),
        retell_call_id=req.data.call_id,
        patient_id=uuid.UUID(str(patient_id)) if patient_id else None,
        caller_phone_hash=customer_phone_hash,
        call_date=now_utc,
        duration_seconds=req.data.duration_ms // 1000 if req.data.duration_ms else 0,
        outcome=call_summary,
        transcript_encrypted=encrypted_transcript,
        recording_url=req.data.recording_url,
        recording_purge_scheduled=purge_time,
        tools_invoked=tools_called if isinstance(tools_called, list) else [],
    )

    try:
        db.add(new_call_log)
        await db.commit()
    except Exception as e:
        log.warning(f"[Retell Webhook] Could not save call log directly: {e}")
        await db.rollback()

    # 4. Masked Patient Name for Realtime Broadcast
    masked_name = "Unknown Caller"
    active_patient = None
    if patient_id:
        try:
            stmt = select(Patient).where(Patient.id == uuid.UUID(str(patient_id)))
            active_patient = (await db.execute(stmt)).scalars().first()
        except Exception:
            pass
    elif customer_phone_hash:
        try:
            stmt = select(Patient).where(Patient.phone_hash == customer_phone_hash, Patient.is_deleted == False)
            active_patient = (await db.execute(stmt)).scalars().first()
        except Exception:
            pass

    if active_patient and active_patient.full_name:
        parts = active_patient.full_name.split()
        if len(parts) == 1:
            masked_name = f"{parts[0][0]}{'*' * max(1, len(parts[0]) - 1)}"
        else:
            first = f"{parts[0][0]}{'*' * max(1, len(parts[0]) - 1)}"
            last = f"{parts[-1][0]}{'*' * max(1, len(parts[-1]) - 1)}"
            masked_name = f"{first} {last}"

    # 5. Broadcast WebSocket Event for Dashboard
    try:
        from src.ws.manager import tenant_room_manager
        await tenant_room_manager.broadcast_to_tenant(str(tenant_id), {
            "event": "NEW_CALL",
            "data": {
                "call_log_id": req.data.call_id,
                "duration_seconds": req.data.duration_ms // 1000 if req.data.duration_ms else 0,
                "outcome": call_summary,
                "patient_name_masked": masked_name,
                "tools_invoked": tools_str,
                "timestamp": now_utc.isoformat(),
            }
        })
    except Exception as ws_err:
        log.warning(f"[Retell Webhook] WS broadcast warning: {ws_err}")

    return {"success": True, "data": {"call_log_id": req.data.call_id}}


@router.post("/tool/{tool_name}")
async def handle_tool(tool_name: str, req: RetellToolRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Executes real-time Retell tool calls (appointment booking, rescheduling, cancellations, live SMS links, transfers).
    """
    await verify_retell_signature(request)
    log.info(f"[Retell Webhook] Tool execution requested: {tool_name}")

    tenant_id = await get_tenant_id(db)
    from src.core.tenant_context import set_tenant_id
    set_tenant_id(uuid.UUID(str(tenant_id)))

    try:
        tool = get_tool(tool_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tool {tool_name} not found")

    call_id = req.call_id
    result = await tool.run(db, tenant_id, call_id, req.args)

    # Commit any database modifications performed by the tool
    await db.commit()

    # Broadcast WebSocket Event for real-time calendar and dashboard sync
    try:
        from src.ws.manager import tenant_room_manager, WebSocketEvent
        event_data = result.get("result") or result.get("appointment") or result
        if isinstance(event_data, dict):
            event_payload = {**event_data, "tool_name": tool_name, "call_id": call_id, "timestamp": datetime.datetime.now(datetime.UTC).isoformat()}
        else:
            event_payload = {"tool_name": tool_name, "call_id": call_id, "result": event_data, "timestamp": datetime.datetime.now(datetime.UTC).isoformat()}

        if result.get("success") and tool_name in ["book_new_appointment", "book_appointment"]:
            await tenant_room_manager.broadcast_event(tenant_id, WebSocketEvent.APPOINTMENT_ADDED, event_payload)
        elif result.get("success") and tool_name in ["cancel_existing_appointment", "cancel_appointment"]:
            await tenant_room_manager.broadcast_event(tenant_id, WebSocketEvent.APPOINTMENT_CANCELLED, event_payload)
        elif result.get("success") and tool_name in ["reschedule_appointment"]:
            await tenant_room_manager.broadcast_event(tenant_id, WebSocketEvent.APPOINTMENT_UPDATED, event_payload)
            await tenant_room_manager.broadcast_event(tenant_id, WebSocketEvent.APPOINTMENT_ADDED, event_payload)
    except Exception as ws_e:
        log.warning(f"[Retell Webhook] Tool WS broadcast warning: {ws_e}")

    return result
