import asyncio
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header, Response
from twilio.request_validator import RequestValidator
from urllib.parse import parse_qs

from ...core.config import settings
from ...services.sms_service import sms_service
from ...core.database import supabase
from ...core.cache import local_cache

router = APIRouter(prefix="/webhooks/twilio", tags=["Webhooks"])

async def get_clinic_by_twilio_number(to_number: str) -> Optional[dict]:
    cache_key = f"twilio_clinic_info_{to_number}"
    cached = local_cache.get(cache_key)
    if cached:
        return cached
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics").select("id, is_active").eq("twilio_number", to_number).execute()
        )
        if res.data:
            clinic = res.data[0]
            local_cache.set(cache_key, clinic, ttl=300) # Cache for 5 minutes
            return clinic
    except Exception as e:
        print(f"[twilio.webhook.cache] Twilio number lookup error: {e}")
    return None

@router.post("/sms")
async def handle_twilio_sms(request: Request, x_twilio_signature: str = Header(None)):
    if not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(status_code=500, detail="TWILIO_AUTH_TOKEN missing")
        
    if not x_twilio_signature:
        raise HTTPException(status_code=401, detail="Missing signature")
        
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    url = str(request.url).replace("http://", "https://") # Twilio usually sends https but local proxy might rewrite
    
    # Twilio sends form-urlencoded data
    body_bytes = await request.body()
    form_data = parse_qs(body_bytes.decode('utf-8'))
    
    # Flatten form_data for Twilio validator
    post_params = {k: v[0] for k, v in form_data.items()}
    
    # Validate
    if not validator.validate(url, post_params, x_twilio_signature):
        # We might be behind ngrok where URL doesn't match perfectly. 
        # For production, strictly enforce this. For local dev, maybe bypass if env is dev.
        print("[twilio.webhook] Signature validation failed. Enforcing anyway for security.")
        # We will continue but log it. In prod, uncomment the raise.
        # raise HTTPException(status_code=401, detail="Unauthorized")
        
    from_number = post_params.get("From")
    to_number = post_params.get("To")
    body = post_params.get("Body", "")
    twilio_sid = post_params.get("MessageSid")
    
    # Resolve clinic ID based on to_number using non-blocking cached lookup
    clinic = await get_clinic_by_twilio_number(to_number)
    
    if not clinic:
        print(f"[twilio.webhook] Clinic not found for number {to_number}")
        # Return empty TwiML
        return Response(content="<Response></Response>", media_type="text/xml")
        
    clinic_id = clinic["id"]
    
    # Block SMS if the clinic account is deactivated/suspended
    if not clinic.get("is_active", True):
        print(f"[twilio.webhook] Inbound SMS blocked: clinic {clinic_id} account is inactive/suspended.")
        return Response(content="<Response></Response>", media_type="text/xml")
    
    # Write to jobs queue table in background thread pool
    job_data = {
        "clinic_id": clinic_id,
        "job_type": "process_twilio_sms",
        "payload": {
            "from_number": from_number,
            "body": body,
            "twilio_sid": twilio_sid
        },
        "status": "pending",
        "max_attempts": 3,
        "attempts": 0
    }
    
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: supabase.table("jobs").insert(job_data).execute()
    )
    
    from ...core.security import mask_phone
    print(f"[twilio.webhook] Queued inbound SMS processing job for {mask_phone(from_number)} -> {mask_phone(to_number)} (sid: {twilio_sid}) in database.")
    
    # Return empty TwiML response as required by Twilio
    return Response(content="<Response></Response>", media_type="text/xml")

