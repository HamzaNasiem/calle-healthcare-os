import asyncio
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header, Response
import telnyx
from ...core.config import settings
from ...services.sms_service import sms_service
from ...core.database import supabase
from ...core.cache import local_cache
from ...core.security import mask_phone
from ...core.logger import log

router = APIRouter(prefix="/webhooks/telnyx", tags=["Webhooks"])

async def get_clinic_by_telnyx_number(to_number: str) -> Optional[dict]:
    cache_key = f"telnyx_clinic_info_{to_number}"
    cached = local_cache.get(cache_key)
    if cached:
        return cached
    try:
        # Look up by telnyx_number in clinics table
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics").select("id, is_active").eq("telnyx_number", to_number).execute()
        )
        if res.data:
            clinic = res.data[0]
            local_cache.set(cache_key, clinic, ttl=300)
            return clinic
    except Exception as e:
        log.error(f"[telnyx.webhook.cache] Telnyx number lookup error: {e}")
    return None

def load_ed25519_public_key(pub_key: str):
    # Try decoding as PEM first if it has PEM headers
    if "-----BEGIN PUBLIC KEY-----" in pub_key:
        from cryptography.hazmat.primitives import serialization
        return serialization.load_pem_public_key(pub_key.encode("utf-8"))
    
    # Try decoding as hex if it contains only hex chars and is 64 chars long (32 bytes)
    if len(pub_key) == 64 and all(c in "0123456789abcdefABCDEF" for c in pub_key):
        key_bytes = bytes.fromhex(pub_key)
    else:
        # Otherwise assume it is base64 encoded
        import base64
        key_bytes = base64.b64decode(pub_key)
        
    from cryptography.hazmat.primitives.asymmetric import ed25519
    return ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)

@router.post("/sms")
async def handle_telnyx_sms(request: Request, telnyx_signature_ed25519: str = Header(None), telnyx_timestamp: str = Header(None)):
    if not settings.TELNYX_PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="TELNYX_PUBLIC_KEY missing")
        
    if not telnyx_signature_ed25519 or not telnyx_timestamp:
        raise HTTPException(status_code=401, detail="Missing signature headers")
        
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    # Telnyx Signature Validation
    try:
        verify_key = load_ed25519_public_key(settings.TELNYX_PUBLIC_KEY)
        signed_data = f"{telnyx_timestamp}|{body_str}".encode("utf-8")
        import base64
        signature_bytes = base64.b64decode(telnyx_signature_ed25519)
        verify_key.verify(signature_bytes, signed_data)
    except Exception as e:
        log.warning(f"[telnyx.webhook] Signature validation failed: {e}. Enforcing strict drop.")
        raise HTTPException(status_code=401, detail="Unauthorized")

    import json
    event = json.loads(body_str)
    
    if event.get("data", {}).get("event_type") != "message.received":
        return Response(status_code=204)
        
    payload = event.get("data", {}).get("payload", {})
    from_number = payload.get("from", {}).get("phone_number")
    to_number = payload.get("to", [{}])[0].get("phone_number")
    text_body = payload.get("text", "")
    message_id = payload.get("id")
    
    if not from_number or not to_number:
        return Response(status_code=204)
    
    # Resolve clinic ID based on to_number
    clinic = await get_clinic_by_telnyx_number(to_number)
    if not clinic:
        log.warning(f"[telnyx.webhook] Clinic not found for number {to_number}")
        return Response(status_code=204)
        
    clinic_id = clinic["id"]
    if not clinic.get("is_active", True):
        log.warning(f"[telnyx.webhook] Inbound SMS blocked: clinic {clinic_id} account is inactive.")
        return Response(status_code=204)
    
    # Queue for async processing
    job_data = {
        "clinic_id": clinic_id,
        "job_type": "process_telnyx_sms",
        "payload": {
            "from_number": from_number,
            "body": text_body,
            "message_sid": message_id
        },
        "status": "pending",
        "max_attempts": 3,
        "attempts": 0
    }
    
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: supabase.table("jobs").insert(job_data).execute()
    )
    
    log.info(f"[telnyx.webhook] Queued inbound SMS processing job for {mask_phone(from_number)} -> {mask_phone(to_number)} in DB.")
    return Response(status_code=204)
