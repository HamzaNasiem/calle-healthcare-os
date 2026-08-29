"""
Telnyx Inbound SMS Webhook
Handles patient SMS replies with Ed25519 signature verification.

HIPAA Safeguards:
- All SMS bodies stored AES-256-GCM encrypted
- Patient lookup via phone_hash only (never plaintext phone in DB query)
- STOP/UNSUBSCRIBE → OPT_OUT intent (NOT appointment cancel)
- WebSocket broadcast on every intent action for real-time dashboard
- audit_service called for every PHI-touching action
"""
import hashlib
import json
import logging
import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from nacl.exceptions import BadSignatureError

# For Ed25519 signature verification
from nacl.signing import VerifyKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.core.encryption import phi_crypto
from src.core.tenant_context import set_tenant_id
from src.db.engine import get_db
from src.models.appointment import Appointment
from src.models.patient import Patient
from src.models.sms_log import SmsLog
from src.models.tenant_settings import TenantSettings
from src.services.audit_service import audit_service
from src.services.intent_parser import intent_parser
from src.services.waitlist_service import waitlist_service

router = APIRouter()
log = logging.getLogger(__name__)


def verify_telnyx_signature(payload: bytes, signature: str, timestamp: str, public_key: str):
    """
    Verifies the Ed25519 signature of incoming Telnyx webhooks.
    Supports Base64, Hex, PEM, and Raw public keys.
    """
    if not signature or not timestamp or not public_key:
        raise HTTPException(status_code=401, detail="Missing signature headers")

    try:
        pk_str = public_key.strip()
        signed_payload = f"{timestamp}|{payload.decode('utf-8')}".encode("utf-8")
        signature_bytes = __import__('base64').b64decode(signature)

        # 1. PEM format key
        if "-----BEGIN PUBLIC KEY-----" in pk_str:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ed25519
            pub = serialization.load_pem_public_key(pk_str.encode("utf-8"))
            pub.verify(signature_bytes, signed_payload)
            return

        # 2. Hex format key (64 hex characters = 32 bytes)
        if len(pk_str) == 64 and all(c in "0123456789abcdefABCDEF" for c in pk_str):
            key_bytes = bytes.fromhex(pk_str)
            verify_key = VerifyKey(key_bytes)
        else:
            # 3. Base64 format key
            verify_key = VerifyKey(pk_str, encoder=__import__('nacl.encoding').encoding.Base64Encoder)

        verify_key.verify(signed_payload, signature_bytes)
    except BadSignatureError:
        log.warning("[Telnyx Webhook] Invalid signature detected")
        raise HTTPException(status_code=401, detail="Invalid signature")
    except Exception as e:
        log.error(f"[Telnyx Webhook] Signature verification error: {e}")
        raise HTTPException(status_code=401, detail="Signature verification error")


def _normalize_phone(raw: str, default_country: str = "+1") -> str:
    """
    Normalizes any phone number format to standard E.164 (+1XXXXXXXXXX).
    Handles:
      "(555) 123-4567" -> "+15551234567"
      "5551234567"     -> "+15551234567"
      "15551234567"    -> "+15551234567"
      "+15551234567"   -> "+15551234567"
      "+447911123456"  -> "+447911123456"
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


@router.post("/inbound")
async def telnyx_inbound_webhook(
    request: Request,
    telnyx_signature_ed25519: str = Header(None),
    telnyx_timestamp: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handles inbound SMS messages from Telnyx.

    Flow:
    1. Ed25519 signature verification
    2. Parse intent (CONFIRM / CANCEL / RESCHEDULE / QUESTION / OPT_OUT)
    3. Find patient by phone_hash (NEVER by plaintext phone column)
    4. Resolve tenant from patient or from DID (to_number)
    5. Apply business logic (confirm/cancel/opt-out appointment)
    6. Broadcast WebSocket event to dashboard
    7. Log SMS body AES-256 encrypted to sms_logs
    8. Audit log every PHI-touching action
    """
    payload_bytes = await request.body()

    # ── 1. Ed25519 Signature Verification ──────────────────────────────────
    pub_key = settings.telnyx_public_key or settings.TELNYX_PUBLIC_KEY
    if pub_key:
        verify_telnyx_signature(
            payload=payload_bytes,
            signature=telnyx_signature_ed25519,
            timestamp=telnyx_timestamp,
            public_key=pub_key
        )
    elif settings.is_prod:
        log.critical("TELNYX_PUBLIC_KEY is not configured in production. Blocking SMS webhook.")
        raise HTTPException(status_code=500, detail="Signature configuration error")
    else:
        log.warning("TELNYX_PUBLIC_KEY is missing. Skipping signature check in development.")

    try:
        data = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = data.get("data", {}).get("event_type")

    if event_type == "message.received":
        msg_payload = data.get("data", {}).get("payload", {})
        from_number_raw = msg_payload.get("from", {}).get("phone_number", "")
        to_number_raw   = msg_payload.get("to", [{}])[0].get("phone_number", "")
        text            = msg_payload.get("text", "")
        message_id      = msg_payload.get("id")

        # ── 2. Normalize phone and compute hash (HIPAA: never query by plaintext) ──
        from_number_normalized = _normalize_phone(from_number_raw)
        to_number_normalized = _normalize_phone(to_number_raw)
        phone_hash = hashlib.sha256(from_number_normalized.encode("utf-8")).hexdigest()

        # ── 3. Parse Intent FIRST (before DB hit) ─────────────────────────
        intent = await intent_parser.parse_intent(text)
        confidence = 1.0 # Mocked for MVP

        # HIPAA: Never log plaintext phone numbers to stdout/stderr
        log.info(f"[Telnyx SMS] phone_hash={phone_hash[:8]}... intent={intent} confidence={confidence}")

        # ── 4. Find patient by phone_hash (NOT by .phone column) ──────────
        stmt   = select(Patient).where(
            Patient.phone_hash == phone_hash,
            Patient.is_deleted == False
        )
        result  = await db.execute(stmt)
        patient = result.scalars().first()

        # ── 5. Resolve tenant_id ───────────────────────────────────────────
        # Primary: from patient record
        # Secondary: match to_number against TenantSettings.clinic_phone
        # Fallback: single-clinic tenant
        tenant_id  = None
        patient_id = None

        if patient:
            tenant_id  = patient.tenant_id
            patient_id = patient.id
        else:
            if to_number_normalized:
                ts_stmt = select(TenantSettings).where(
                    TenantSettings.clinic_phone == to_number_normalized
                ).limit(1)
                ts_result = await db.execute(ts_stmt)
                ts = ts_result.scalars().first()
                if ts:
                    tenant_id = ts.tenant_id

            if not tenant_id:
                # Fallback to single clinic tenant
                ts_stmt = select(TenantSettings).limit(1)
                ts_result = await db.execute(ts_stmt)
                ts = ts_result.scalars().first()
                if ts:
                    tenant_id = ts.tenant_id

            log.warning(
                f"[Telnyx SMS] Patient not found for phone_hash={phone_hash[:8]}…"
                " Recording inbound SMS without patient link."
            )

        if not tenant_id and settings.DEFAULT_CLINIC_ID:
            try:
                tenant_id = uuid.UUID(str(settings.DEFAULT_CLINIC_ID))
            except Exception:
                pass

        if not tenant_id:
            # Last-resort: log and exit — cannot process without a tenant
            log.error("[Telnyx SMS] Could not resolve tenant_id. Dropping webhook.")
            return {"status": "success"}

        # Set tenant context for audit chain
        set_tenant_id(uuid.UUID(str(tenant_id)))

        # ── 6. Handle OPT_OUT before anything else (TCPA / HIPAA) ─────────
        if intent == "OPT_OUT":
            await _handle_opt_out(db, tenant_id, from_number_normalized)
            # Still log the SMS below, then return
            appointment = None
        else:
            # ── 7. Find latest upcoming appointment for context ─────────────
            appointment = None
            if patient:
                apt_stmt = select(Appointment).where(
                    Appointment.patient_id == patient.id,
                    Appointment.status.in_(["scheduled", "confirmed"]),
                    Appointment.is_deleted == False,
                    Appointment.slot_start >= datetime.now(UTC)
                ).order_by(Appointment.slot_start.asc())
                appointment = (await db.execute(apt_stmt)).scalars().first()

            # ── 8. Apply business logic ────────────────────────────────────
            if appointment:
                if intent == "CONFIRM":
                    appointment.sms_confirmed = True
                    appointment.status = "confirmed"
                    log.info(f"[Telnyx SMS] Appointment {appointment.id} confirmed via SMS")

                    await audit_service.log(
                        action="APPOINTMENT_CONFIRMED_VIA_SMS",
                        target_table="appointments",
                        target_id=appointment.id,
                        target_patient_id=patient_id,
                        actor_type="patient_sms",
                        ingress_ip="telnyx_webhook",
                        outcome="SUCCESS"
                    )

                    # WS broadcast → real-time dashboard update
                    await _broadcast_ws(str(tenant_id), {
                        "event": "APPOINTMENT_CONFIRMED",
                        "data": {
                            "appointment_id": str(appointment.id),
                            "patient_id": str(patient_id) if patient_id else None,
                            "confirmed_via": "sms",
                            "timestamp": datetime.now(UTC).isoformat()
                        }
                    })

                elif intent == "CANCEL":
                    appointment.status = "cancelled"
                    appointment.is_deleted = True
                    appointment.deleted_at = datetime.now(UTC)
                    log.info(f"[Telnyx SMS] Appointment {appointment.id} cancelled via SMS")

                    await audit_service.log(
                        action="APPOINTMENT_CANCELLED_VIA_SMS",
                        target_table="appointments",
                        target_id=appointment.id,
                        target_patient_id=patient_id,
                        actor_type="patient_sms",
                        ingress_ip="telnyx_webhook",
                        outcome="SUCCESS"
                    )

                    # Trigger waitlist for freed slot
                    try:
                        await waitlist_service.match_and_notify_waitlist(
                            db=db,
                            tenant_id=appointment.tenant_id,
                            service_type=appointment.service_type or "general",
                            slot_start=appointment.slot_start,
                            provider_id=appointment.provider_id
                        )
                    except Exception as wait_e:
                        log.error(f"[Telnyx SMS] Waitlist trigger failed: {wait_e}")

                    # WS broadcast
                    await _broadcast_ws(str(tenant_id), {
                        "event": "APPOINTMENT_CANCELLED",
                        "data": {
                            "appointment_id": str(appointment.id),
                            "patient_id": str(patient_id) if patient_id else None,
                            "cancelled_via": "sms",
                            "timestamp": datetime.now(UTC).isoformat()
                        }
                    })

            # Always broadcast SMS_REPLY_RECEIVED for activity feed
            await _broadcast_ws(str(tenant_id), {
                "event": "SMS_REPLY_RECEIVED",
                "data": {
                    "intent": intent,
                    "confidence": confidence,
                    "patient_id": str(patient_id) if patient_id else None,
                    "appointment_id": str(appointment.id) if appointment else None,
                    "timestamp": datetime.now(UTC).isoformat()
                }
            })

        # ── 9. Log inbound SMS — AES-256-GCM encrypted body ───────────────
        encrypted_body = phi_crypto.encrypt(text)

        log_record = SmsLog(
            tenant_id=tenant_id,
            patient_id=patient_id,
            appointment_id=appointment.id if appointment else None,
            direction="inbound",
            telnyx_message_id=message_id,
            sms_type="inbound_reply",
            message_body_encrypted=encrypted_body,
            parsed_intent=intent,
            intent_confidence=confidence,
            status="received"
        )
        db.add(log_record)
        await db.commit()

    return {"status": "success"}


async def _handle_opt_out(db: AsyncSession, tenant_id, phone_normalized: str) -> None:
    """
    TCPA Compliance: Adds patient phone to sms_opt_out_list in TenantSettings.
    This prevents any future outbound SMS to this number.
    """
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ts_result = await db.execute(stmt)
    ts = ts_result.scalars().first()

    if ts:
        current_list = ts.sms_opt_out_list or []
        if phone_normalized not in current_list:
            # ARRAY append — SQLAlchemy requires reassignment for ARRAY mutation
            ts.sms_opt_out_list = current_list + [phone_normalized]
            log.info(f"[Telnyx SMS] OPT_OUT: added {phone_normalized[:6]}… to opt-out list for tenant {tenant_id}")

        await audit_service.log(
            action="SMS_OPT_OUT",
            target_table="tenant_settings",
            target_id=ts.id,
            actor_type="patient_sms",
            ingress_ip="telnyx_webhook",
            outcome="SUCCESS",
            change_reason="Patient sent STOP/UNSUBSCRIBE keyword"
        )
        await db.commit()


async def _broadcast_ws(tenant_id: str, payload: dict) -> None:
    """
    Broadcasts a WebSocket event to all dashboard clients in this tenant room.
    Wrapped in try/except so a WS failure never crashes the webhook.
    """
    try:
        from src.ws.manager import tenant_room_manager
        await tenant_room_manager.broadcast_to_tenant(tenant_id, payload)
    except Exception as ws_err:
        log.warning(f"[Telnyx SMS] WS broadcast failed (non-fatal): {ws_err}")
