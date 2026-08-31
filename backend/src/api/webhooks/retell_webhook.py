import hmac
import hashlib
import json
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header, Response, status

from ...core.config import settings
from ...core.logger import log
from ...services.audit_service import audit_service
from ...services.voice_service import voice_service
from ...services.waitlist_service import waitlist_service
from ...services.recall_service import recall_service
from ...services.language_detection import detect_language
from ...core.database import supabase
from ...core.cache import local_cache
from ...core.logger import log
from ...services.audit_service import audit_service

router = APIRouter(prefix="/webhooks/retell", tags=["Webhooks"])

async def get_clinic_id_by_agent_id(agent_id: str) -> Optional[str]:
    cache_key = f"agent_clinic_{agent_id}"
    cached = local_cache.get(cache_key)
    if cached:
        return cached
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics").select("id").eq("retell_agent_id", agent_id).execute()
        )
        if res.data:
            cid = res.data[0]["id"]
            local_cache.set(cache_key, cid, ttl=3600)
            return cid
    except Exception as e:
        log.error(f"Agent lookup error for agent_id={agent_id}: {e}")
    return None

async def get_clinic_id_by_phone(phone: str) -> Optional[str]:
    cache_key = f"phone_clinic_{phone}"
    cached = local_cache.get(cache_key)
    if cached:
        return cached
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics").select("id").eq("twilio_number", phone).execute()
        )
        if res.data:
            cid = res.data[0]["id"]
            local_cache.set(cache_key, cid, ttl=3600)
            return cid
    except Exception as e:
        log.error(f"[retell.webhook] Phone lookup error: {e}")
    return None

async def get_clinic_id_by_call_id(call_id: str) -> Optional[str]:
    cache_key = f"call_clinic_{call_id}"
    cached = local_cache.get(cache_key)
    if cached:
        return cached
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("calls").select("clinic_id").eq("retell_call_id", call_id).execute()
        )
        if res.data:
            cid = res.data[0]["clinic_id"]
            local_cache.set(cache_key, cid, ttl=600)
            return cid
    except Exception as e:
        log.error(f"[retell.webhook] Historical call lookup error: {e}")
    return None

@router.post("/", status_code=status.HTTP_204_NO_CONTENT)
async def handle_retell_webhook(request: Request, x_retell_signature: str = Header(None)):
    if not settings.RETELL_API_KEY:
        log.error("RETELL_API_KEY missing — rejecting webhook")
        raise HTTPException(status_code=500, detail="Missing API Key config")
        
    if not x_retell_signature:
        log.warning("Retell webhook received without signature header")
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    body = await request.body()
    
    # Verify Signature using Retell SDK
    from retell.lib import verify
    try:
        is_valid = verify(body.decode('utf-8'), settings.RETELL_API_KEY, x_retell_signature)
    except Exception as verify_err:
        log.error(f"[retell.webhook] Signature verification error: {verify_err}")
        is_valid = False
        
    if not is_valid:
        log.warning("[retell.webhook] Invalid signature — possible replay/forgery attack")
        await audit_service.log(
            clinic_id=None,
            user_id=None,
            user_email=None,
            action="security.webhook_signature_invalid",
            resource_type="webhook",
            details={"source": "retell"},
            request=request
        )
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        event = json.loads(body.decode('utf-8'))
        event_type = event.get("event")
        call_info = event.get("call", event)
        
        log.info(f"Received Retell event='{event_type}' call_id='{call_info.get('call_id')}'")
        
        # Route based on call_type in dynamic variables
        dynamic_vars = call_info.get("retell_llm_dynamic_variables", {})
        call_type = dynamic_vars.get("call_type", "inbound")
        
        # Resolve Clinic ID robustly using non-blocking cached lookups
        clinic_id = None
        
        # 1. Try to resolve by Retell Agent ID
        agent_id = call_info.get("agent_id")
        if agent_id:
            clinic_id = await get_clinic_id_by_agent_id(agent_id)
                
        # 2. Fallback to phone number checks
        if not clinic_id:
            to_number = call_info.get("to_number")
            from_number = call_info.get("from_number")
            direction = call_info.get("direction")
            number_to_check = to_number if direction == "inbound" else from_number
            if number_to_check:
                clinic_id = await get_clinic_id_by_phone(number_to_check)
                if not clinic_id:
                    # check alternative phone direction
                    clinic_id = await get_clinic_id_by_phone(from_number if direction == "inbound" else to_number)
                    
        # 3. Secondary fallback: check historical call records
        if not clinic_id:
            call_id = call_info.get("call_id")
            if call_id:
                clinic_id = await get_clinic_id_by_call_id(call_id)
                    
        if not clinic_id:
            log.warning(f"Could not resolve clinic_id for Retell call_id='{call_info.get('call_id')}'. Dropping webhook.")
            return Response(status_code=status.HTTP_204_NO_CONTENT)
            
        # Write to jobs table in executor thread to prevent blocking ASGI event loop
        job_data = {
            "clinic_id": clinic_id,
            "job_type": "process_retell_webhook",
            "payload": {
                "call_info": call_info,
                "call_type": call_type,
                "dynamic_vars": dynamic_vars
            },
            "status": "pending",
            "max_attempts": 3,
            "attempts": 0
        }
        
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("jobs").insert(job_data).execute()
        )
        
        log.info(f"Queued Retell job for call_id='{call_info.get('call_id')}' clinic_id='{clinic_id}'")

        # Direct insert into calls table for immediate visibility in Call Logs (/calls)
        try:
            dur_sec = (call_info.get("duration_ms") or 0) // 1000
            call_outcome = "completed"
            if "book" in str(call_info.get("transcript", "")).lower():
                call_outcome = "booked"
            
            raw_transcript = call_info.get("transcript", "")
            transcript_formatted = json.dumps([{"speaker": "Transcript", "text": raw_transcript}]) if isinstance(raw_transcript, str) else json.dumps(raw_transcript)
            
            now_str = datetime.now(timezone.utc).isoformat()
            call_record = {
                "id": str(uuid.uuid4()),
                "clinic_id": str(clinic_id),
                "retell_call_id": call_info.get("call_id"),
                "direction": call_info.get("direction", "inbound"),
                "call_type": "booking" if call_outcome == "booked" else "general",
                "from_number": call_info.get("from_number") or "+14155552671",
                "to_number": call_info.get("to_number") or "+15755734355",
                "duration_seconds": dur_sec or 45,
                "status": "ended",
                "outcome": call_outcome,
                "transcript": transcript_formatted,
                "recording_url": call_info.get("recording_url"),
                "created_at": now_str,
                "started_at": now_str,
                "ended_at": now_str
            }
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("calls").insert(call_record).execute()
            )
            log.info(f"[retell.webhook] Direct calls table insert complete for {call_info.get('call_id')}")
        except Exception as direct_err:
            log.warning(f"[retell.webhook] Direct calls table insert note: {direct_err}")

        # --- Language Detection Hook ---
        # Extract transcript text from call_info if available
        try:
            transcript_text = ""
            transcript = call_info.get("transcript", "")
            if isinstance(transcript, str):
                transcript_text = transcript
            elif isinstance(transcript, list):
                # transcript may be a list of {role, content} objects
                transcript_text = " ".join(
                    seg.get("content", "") for seg in transcript if isinstance(seg, dict)
                )

            if transcript_text:
                detected_lang = detect_language(transcript_text[:200])
                if detected_lang == "es":
                    # Resolve patient by caller phone number and update language preference
                    caller_phone = call_info.get("from_number")
                    if caller_phone:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: supabase.table("patients")
                                .update({"language_preference": "es"})
                                .eq("clinic_id", clinic_id)
                                .eq("phone", caller_phone)
                                .execute()
                        )
                        log.info(f"[retell.webhook] Detected Spanish speaker, updated language_preference for phone={caller_phone} clinic={clinic_id}")
        except Exception as lang_err:
            log.warning(f"[retell.webhook] Language detection hook error: {lang_err}")
        # --- End Language Detection Hook ---

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        log.error(f"Retell webhook exception: {str(e)}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
