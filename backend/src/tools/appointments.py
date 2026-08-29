import datetime
import hashlib
import random
import string
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import local_cache
from src.core.encryption import phi_crypto
from src.core.tenant_context import set_tenant_id
from src.models.appointment import Appointment
from src.models.patient import Patient
from src.models.waitlist import Waitlist
from src.services.audit_service import audit_service

from .base_tool import BaseTool


def _safe_uuid(val: Any) -> uuid.UUID | None:
    if not val:
        return None
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return None


async def log_audit_event(db: AsyncSession, tenant_id: str, actor_type: str, actor_id: str, action: str, target_table: str, target_id: str, target_patient_id: str = None, fields_accessed: list = None):
    t_uuid = _safe_uuid(tenant_id)
    if t_uuid:
        try:
            set_tenant_id(t_uuid)
        except Exception:
            pass
    await audit_service.log(
        action=action,
        target_table=target_table,
        target_id=_safe_uuid(target_id),
        target_patient_id=_safe_uuid(target_patient_id),
        actor_id=_safe_uuid(actor_id) if actor_id else None,
        actor_type=actor_type,
        session_id=str(actor_id) if actor_id else None,
        fields_accessed=fields_accessed or [],
        outcome="SUCCESS"
    )


from pydantic import BaseModel, Field


def _safe_zone_info(tz_name: Any, default_tz: str = "America/Chicago"):
    from zoneinfo import ZoneInfo
    if not tz_name or not isinstance(tz_name, str):
        return ZoneInfo(default_tz)
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(default_tz)


class CheckCalendarAvailabilityArgs(BaseModel):
    date: str | None = Field(None, description="The date to check in YYYY-MM-DD format. If not provided, defaults to today.")
    time_preference: str = Field("any", description="Time preference: 'morning', 'afternoon', 'evening', or 'any'")
    provider_id: str | None = Field(None, description="The specific provider ID to check availability for. If not provided, checks any provider.")
    service_type: str | None = Field(None, description="The type of service requested, e.g. 'consult', 'cleaning', 'surgery'")

class CheckCalendarAvailabilityTool(BaseTool):
    @property
    def name(self) -> str:
        return "check_calendar_availability"
        
    @property
    def description(self) -> str:
        return "Checks the clinic's calendar for available appointment slots based on patient preferences."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return CheckCalendarAvailabilityArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        import json

        from src.models.provider import Provider
        from src.models.tenant import Tenant
        from src.models.tenant_settings import TenantSettings
        
        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(tenant_stmt)).scalars().first()
        tz = _safe_zone_info(tenant.timezone if tenant and tenant.timezone else None)
        
        date_str = args.get("date")
        if not date_str:
            date_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")
        else:
            date_str = date_str.split("T")[0]
            
        time_pref = args.get("time_preference", "any").lower()
        requested_provider_id = args.get("provider_id")
        service_type = args.get("service_type")
        
        # PRD Step 1: Check Redis cache
        cache_key = f"t:{tenant_id}:slots:{date_str}_{time_pref}"
        if requested_provider_id:
            cache_key += f"_{requested_provider_id}"
        if service_type:
            cache_key += f"_{service_type.replace(' ', '')}"
            
        if local_cache.redis_client:
            cached_val = local_cache.redis_client.get(cache_key)
            if cached_val:
                return json.loads(cached_val)
        else:
            cached_val = local_cache.get(cache_key)
            if cached_val:
                return json.loads(cached_val)
                
        try:
            base_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return {"available": False, "reason": "invalid_date_format", "message": "Please provide the date in YYYY-MM-DD format."}
            
        settings_stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        settings = (await db.execute(settings_stmt)).scalars().first()
        
        from src.models.slot_lock import SlotLock
        locked_stmt = select(SlotLock.slot_key).where(
            SlotLock.tenant_id == tenant_id,
            SlotLock.expires_at > datetime.datetime.now(datetime.UTC)
        )
        pg_locked_slots = set((await db.execute(locked_stmt)).scalars().all())
        
        duration_minutes = 30
        if service_type and settings and settings.services:
            for s in settings.services:
                if service_type.lower() in s.get("name", "").lower():
                    duration_minutes = s.get("duration_minutes", 30)
                    break
        
        if requested_provider_id:
            provider_stmt = select(Provider).where(Provider.tenant_id == tenant_id, Provider.id == requested_provider_id, Provider.is_accepting_patients == True, Provider.is_deleted == False)
        else:
            provider_stmt = select(Provider).where(Provider.tenant_id == tenant_id, Provider.is_accepting_patients == True, Provider.is_deleted == False)
        providers = (await db.execute(provider_stmt)).scalars().all()
        
        if not providers:
            return {"available": False, "reason": "no_providers_available", "message": "We currently do not have any doctors available for new appointments."}
            
        provider = providers[0]
        provider_name = provider.display_name
        
        async def scan_day(scan_date: datetime.datetime, target_providers: list):
            day_name = scan_date.strftime("%A").lower()
            day_key = scan_date.strftime("%a").lower()
            day_start_hour, day_end_hour = 9, 17
            
            if settings and settings.business_hours:
                biz = settings.business_hours
                if isinstance(biz, str):
                    try:
                        biz = json.loads(biz)
                    except Exception:
                        biz = {}
                        
                day_hours = biz.get(day_name) if isinstance(biz, dict) else None
                if day_hours is None and isinstance(biz, dict):
                    day_hours = biz.get(day_key)
                    
                if not day_hours:
                    return []
                    
                if isinstance(day_hours, str):
                    val_str = day_hours.strip().lower()
                    if val_str == "closed" or not val_str:
                        return []
                    if "-" in val_str:
                        try:
                            parts = val_str.split("-")
                            day_start_hour = int(parts[0].strip().split(":")[0])
                            day_end_hour = int(parts[1].strip().split(":")[0])
                        except Exception:
                            pass
                elif isinstance(day_hours, dict):
                    is_open = day_hours.get("enabled", True) if "enabled" in day_hours else day_hours.get("open", True)
                    if day_hours.get("closed") is True or not is_open:
                        return []
                    try:
                        s_str = str(day_hours.get("start") or "09:00").strip()
                        e_str = str(day_hours.get("end") or "17:00").strip()
                        day_start_hour = int(s_str.split(":")[0])
                        day_end_hour = int(e_str.split(":")[0])
                    except Exception:
                        pass
                    
            pref_start, pref_end = day_start_hour, day_end_hour
            if time_pref == "morning":
                pref_end = min(12, day_end_hour)
            elif time_pref == "afternoon":
                pref_start = max(12, day_start_hour)
                pref_end = min(17, day_end_hour)
            elif time_pref == "evening":
                pref_start = max(17, day_start_hour)
                
            if pref_start >= pref_end:
                return []
                
            local_day_start = scan_date.replace(tzinfo=tz)
            local_day_end = local_day_start + datetime.timedelta(days=1)
            utc_day_start = local_day_start.astimezone(datetime.UTC)
            utc_day_end = local_day_end.astimezone(datetime.UTC)
            
            stmt = select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.slot_start >= utc_day_start,
                Appointment.slot_start < utc_day_end,
                Appointment.is_deleted == False,
                Appointment.status.in_(["scheduled", "confirmed"])
            )
            existing_apts = (await db.execute(stmt)).scalars().all()
            
            day_slots = []
            for hour in range(pref_start, pref_end):
                if len(day_slots) >= 3: break
                for minute in [0, 30]:
                    if len(day_slots) >= 3: break
                    
                    slot_start_time = local_day_start.replace(hour=hour, minute=minute)
                    if slot_start_time < datetime.datetime.now(tz):
                        continue
                        
                    pref_end_time = local_day_start.replace(hour=pref_end, minute=0)
                    slot_end_time = slot_start_time + datetime.timedelta(minutes=duration_minutes)
                    if slot_end_time > pref_end_time:
                        continue
                        
                    utc_slot_start = slot_start_time.astimezone(datetime.UTC)
                    utc_slot_end = utc_slot_start + datetime.timedelta(minutes=duration_minutes)
                    
                    # PROPER RANGE OVERLAP CHECK ACROSS ALL PROVIDERS
                    for provider in target_providers:
                        has_overlap = False
                        for apt in existing_apts:
                            if apt.provider_id == provider.id and apt.slot_start < utc_slot_end and apt.slot_end > utc_slot_start:
                                has_overlap = True
                                break
                                
                        if has_overlap:
                            continue
                        
                        # Encode provider_id into the slot_id to guarantee multi-provider routing
                        slot_id_str = f"slot_{provider.id}_{slot_start_time.strftime('%Y%m%d_%H%M')}"
                        
                        # Check PostgreSQL locks
                        if slot_id_str in pg_locked_slots:
                            continue
                            
                        lock_key = f"lock:slot:{tenant_id}:{slot_id_str}"
                        
                        is_locked = False
                        if local_cache.redis_client:
                            if local_cache.redis_client.get(lock_key):
                                is_locked = True
                        else:
                            if lock_key in local_cache._cache:
                                is_locked = True
                                
                        if not is_locked:
                            day_slots.append({
                                "slot_id": slot_id_str,
                                "slot_start": slot_start_time.isoformat(),
                                "provider_name": provider.display_name,
                                "duration_minutes": duration_minutes
                            })
                            # Once we find one available provider for this exact time, we break 
                            # to offer diverse times instead of filling all 3 options with the same 9:00 AM slot.
                            break
            
            return day_slots

        slots = await scan_day(base_date, providers)
        
        # PRD: If specific provider requested but unavailable: offer other providers TODAY
        if not slots and requested_provider_id:
            provider_stmt_all = select(Provider).where(
                Provider.tenant_id == tenant_id, 
                Provider.id != requested_provider_id, 
                Provider.is_accepting_patients == True, 
                Provider.is_deleted == False
            )
            other_providers = (await db.execute(provider_stmt_all)).scalars().all()
            if other_providers:
                slots = await scan_day(base_date, other_providers)
        
        result = {}
        if slots:
            result = {"available": True, "slots": slots}
        else:
            # PRD Step 5: Check next 7 days if entire date is full
            next_available_date = None
            for offset in range(1, 8):
                future_date = base_date + datetime.timedelta(days=offset)
                future_slots = await scan_day(future_date, providers) # Look for the originally requested provider(s) again
                if future_slots:
                    next_available_date = future_date.strftime("%Y-%m-%d")
                    break
            
            result = {
                "available": False, 
                "reason": "no_slots_on_date", 
                "next_available_date": next_available_date,
                "message": "We are fully booked during that time. Let me check the next available day." if next_available_date else "We are fully booked for the next week."
            }
            
        # PRD Step 4: Cache result in Redis
        if local_cache.redis_client:
            local_cache.redis_client.set(cache_key, json.dumps(result), ex=120)
        else:
            local_cache.set(cache_key, json.dumps(result), ttl=120)
            
        await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="TOOL_INVOKE", target_table="appointments", target_id=None, fields_accessed=["slot_start", "provider_id"])
            
        return result

class BookNewAppointmentArgs(BaseModel):
    patient_name: str = Field("Unknown Patient", description="The full name of the patient.")
    phone: str = Field(..., description="The 10-digit phone number of the patient.")
    dob: str | None = Field(None, description="The date of birth in YYYY-MM-DD format.")
    slot_id: str = Field(..., description="The specific slot ID provided by the check_calendar_availability tool.")
    reason: str = Field("", description="The reason for the visit or any additional notes.")
    service_type: str | None = Field(None, description="The type of service requested, e.g. 'consult', 'cleaning', 'checkup', 'surgery'")

class BookNewAppointmentTool(BaseTool):
    @property
    def name(self) -> str:
        return "book_new_appointment"
        
    @property
    def description(self) -> str:
        return "Books a new appointment for the patient and securely logs their details."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return BookNewAppointmentArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        patient_name = args.get("patient_name", "Unknown Patient")
        phone = args.get("phone")
        dob = args.get("dob")
        slot_id = args.get("slot_id")
        reason = args.get("reason", "")
        
        # PRD Violation Fix: Do not crash webhook, return graceful error
        if not phone or not slot_id:
            return {"success": False, "reason": "missing_parameters", "message": "I need your phone number and the exact time slot to book an appointment."}

        import re
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        if not cleaned_phone.startswith('+'):
            if len(cleaned_phone) == 10:
                cleaned_phone = '+1' + cleaned_phone
            else:
                cleaned_phone = '+' + cleaned_phone
        normalized_phone = cleaned_phone
            
        phone_hash = hashlib.sha256(normalized_phone.encode('utf-8')).hexdigest()
        lock_key = f"lock:slot:{tenant_id}:{slot_id}"
        
        # PRD Violation Fix: Idempotent Redis lock checking
        if local_cache.redis_client:
            # PRD Step 4: ATOMIC ACQUIRE (NX)
            acquired = local_cache.redis_client.set(lock_key, call_id, ex=120, nx=True)
            if not acquired:
                current_lock = local_cache.redis_client.get(lock_key)
                current_lock_str = current_lock.decode('utf-8') if isinstance(current_lock, bytes) else str(current_lock) if current_lock else ""
                if current_lock_str and current_lock_str != call_id:
                    return {"success": False, "reason": "slot_no_longer_available", "message": "That slot was just taken. Let me check the next available."}
        else:
            cached_call_id = local_cache.get(lock_key)
            if cached_call_id and cached_call_id != call_id:
                return {"success": False, "reason": "slot_no_longer_available", "message": "That slot was just taken. Let me check the next available."}
            local_cache.set(lock_key, call_id, ttl=120)

        # Database-level SlotLock defense-in-depth against race conditions
        from src.models.slot_lock import SlotLock
        slot_lock_entry = await db.get(SlotLock, lock_key)
        if slot_lock_entry:
            if slot_lock_entry.expires_at and slot_lock_entry.expires_at > datetime.datetime.now(datetime.UTC):
                if slot_lock_entry.locked_by_call_id != call_id:
                    return {"success": False, "reason": "slot_no_longer_available", "message": "That slot was just taken. Let me check the next available."}
            slot_lock_entry.locked_by_call_id = call_id
            slot_lock_entry.locked_at = datetime.datetime.now(datetime.UTC)
            slot_lock_entry.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=120)
        else:
            slot_lock_entry = SlotLock(
                slot_key=lock_key,
                tenant_id=uuid.UUID(str(tenant_id)),
                locked_by_call_id=call_id,
                locked_at=datetime.datetime.now(datetime.UTC),
                expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=120)
            )
            db.add(slot_lock_entry)

        try:
            from sqlalchemy import select
            stmt = select(Patient).where(Patient.tenant_id == tenant_id, Patient.phone_hash == phone_hash)
            result = await db.execute(stmt)
            patient = result.scalars().first()
            
            if not patient:
                patient = Patient(
                    tenant_id=tenant_id,
                    phone_hash=phone_hash,
                    full_name_encrypted=phi_crypto.encrypt(patient_name),
                    phone_encrypted=phi_crypto.encrypt(normalized_phone),
                    dob_encrypted=phi_crypto.encrypt(dob) if dob else None,
                    is_existing_patient=False
                )
                db.add(patient)
                await db.flush()
                await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="CREATE", target_table="patients", target_id=str(patient.id), target_patient_id=str(patient.id), fields_accessed=["full_name", "phone", "dob"])
            else:
                if patient.is_deleted:
                    patient.is_deleted = False
                    patient.deleted_at = None
                    db.add(patient)
                    await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="RESTORE", target_table="patients", target_id=str(patient.id), target_patient_id=str(patient.id), fields_accessed=["is_deleted"])

                # Update name if they previously booked anonymously
                if patient_name and patient_name.lower() != "unknown patient":
                    current_name = patient.full_name
                    if not current_name or current_name.lower() == "unknown patient":
                        patient.full_name_encrypted = phi_crypto.encrypt(patient_name)
                        db.add(patient)
                        await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="UPDATE", target_table="patients", target_id=str(patient.id), target_patient_id=str(patient.id), fields_accessed=["full_name"])

                if dob and not patient.dob_encrypted:
                    patient.dob_encrypted = phi_crypto.encrypt(dob)
                    db.add(patient)
                    await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="UPDATE", target_table="patients", target_id=str(patient.id), target_patient_id=str(patient.id), fields_accessed=["dob_encrypted"])
                    
            max_retries = 3
            confirmation_code = None
            
            for _ in range(max_retries):
                candidate_code = "APPT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                code_stmt = select(Appointment).where(Appointment.confirmation_code == candidate_code)
                existing = (await db.execute(code_stmt)).scalars().first()
                if not existing:
                    confirmation_code = candidate_code
                    break
                    
            if not confirmation_code:
                raise ValueError("Could not generate a unique confirmation code")
            
            from zoneinfo import ZoneInfo

            from src.models.tenant import Tenant
            from src.models.tenant_settings import TenantSettings
            
            tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
            tenant = (await db.execute(tenant_stmt)).scalars().first()
            tz = _safe_zone_info(tenant.timezone if tenant and hasattr(tenant, "timezone") else None)
            
            settings_stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
            settings = (await db.execute(settings_stmt)).scalars().first()
            
            service_type = args.get("service_type")
            duration_minutes = 30
            if service_type and settings and settings.services:
                for s in settings.services:
                    if service_type.lower() in s.get("name", "").lower():
                        duration_minutes = s.get("duration_minutes", 30)
                        break
            
            try:
                # Expecting format: slot_<provider_id>_<YYYYMMDD>_<HHMM>
                parts = slot_id.split("_")
                if len(parts) == 4:
                    prov_id_str = parts[1]
                    date_str = parts[2]
                    time_str = parts[3]
                elif len(parts) == 3: # Backwards compatible
                    prov_id_str = None
                    date_str = parts[1]
                    time_str = parts[2]
                else:
                    raise Exception("Invalid slot format")
                    
                local_slot_start = datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M").replace(tzinfo=tz)
                utc_slot_start = local_slot_start.astimezone(datetime.UTC)
            except Exception:
                return {"success": False, "reason": "invalid_slot_id", "message": "I couldn't understand that time slot."}
                
            utc_slot_end = utc_slot_start + datetime.timedelta(minutes=duration_minutes)
            
            from src.models.provider import Provider
            provider = None
            if prov_id_str:
                provider_stmt = select(Provider).where(Provider.tenant_id == tenant_id, Provider.id == prov_id_str)
                provider = (await db.execute(provider_stmt)).scalars().first()
                
            if not provider:
                provider_stmt = select(Provider).where(Provider.tenant_id == tenant_id, Provider.is_accepting_patients == True, Provider.is_deleted == False)
                provider = (await db.execute(provider_stmt)).scalars().first()
                
            if not provider:
                return {"success": False, "reason": "no_providers_available", "message": "I'm sorry, but we currently don't have any providers available to book."}
                
            provider_name_display = provider.display_name
            
            # PROPER RANGE OVERLAP DB CHECK
            conflict_stmt = select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.provider_id == provider.id if provider else None,
                Appointment.is_deleted == False,
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.slot_start < utc_slot_end,
                Appointment.slot_end > utc_slot_start
            ).with_for_update()
            conflict = (await db.execute(conflict_stmt)).scalars().first()
            
            if conflict:
                return {"success": False, "reason": "slot_no_longer_available", "message": "I apologize, but that exact time slot was just booked by someone else. Let me check the next available."}
            
            appointment = Appointment(
                tenant_id=tenant_id,
                patient_id=patient.id,
                provider_id=provider.id if provider else None,
                slot_start=utc_slot_start,
                slot_end=utc_slot_end,
                service_type=service_type,
                duration_minutes=duration_minutes,
                status="scheduled",
                booked_by="ai_agent",
                booked_via_call_id=call_id,
                confirmation_code=confirmation_code
            )
            db.add(appointment)
            await db.flush()
            
            if reason:
                from src.models.clinical_note import ClinicalNote
                note_text = f"Appointment Reason: {reason}"
                note_enc = phi_crypto.encrypt(note_text)
                note_hash = hashlib.sha256(note_text.encode('utf-8')).hexdigest()
                clinical_note = ClinicalNote(
                    tenant_id=tenant_id,
                    patient_id=patient.id,
                    authored_by="ai_agent",
                    note_encrypted=note_enc,
                    note_hash=note_hash,
                    access_level="clinician"
                )
                db.add(clinical_note)
                
            from src.models.waitlist import Waitlist
            waitlist_stmt = select(Waitlist).where(Waitlist.patient_id == patient.id, Waitlist.booked_from_waitlist == False)
            wl_entry = (await db.execute(waitlist_stmt)).scalars().first()
            if wl_entry:
                wl_entry.booked_from_waitlist = True
                db.add(wl_entry)
            
            await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="CREATE", target_table="appointments", target_id=str(appointment.id), target_patient_id=str(patient.id), fields_accessed=["patient_id", "status", "slot_start"])
            
            # STALE CACHE INVALIDATION
            # Booking a slot must instantly invalidate the availability cache for that day!
            date_formatted = local_slot_start.strftime("%Y-%m-%d")
            pattern = f"t:{tenant_id}:slots:{date_formatted}*"
            if local_cache.redis_client:
                for key in local_cache.redis_client.scan_iter(pattern):
                    local_cache.redis_client.delete(key)
            else:
                keys_to_del = [k for k in local_cache._cache.keys() if k.startswith(f"t:{tenant_id}:slots:{date_formatted}")]
                for k in keys_to_del:
                    local_cache.invalidate(k)
            
            from src.models.outbox import OutboxEvent
            
            date_display = local_slot_start.strftime("%A, %B %d")
            time_display = local_slot_start.strftime("%I:%M %p")
            
            # TRANSACTIONAL OUTBOX PATTERN: Do not fire async task before commit!
            sms_event = OutboxEvent(
                tenant_id=tenant_id,
                event_type="SEND_SMS",
                payload={
                    "type": "appointment_confirmation",
                    "to_number": normalized_phone,
                    "patient_name": patient_name,
                    "apt_date": date_display,
                    "apt_time": time_display,
                    "provider_name": provider_name_display,
                    "confirmation_code": confirmation_code
                }
            )
            db.add(sms_event)

            # Auto-queue CALL-E 24h Confirmation Call
            from src.models.outbound_call import OutboundCall
            call_idempotency = f"CALL_CONFIRMATION_{appointment.id}_{local_slot_start.date().isoformat()}"
            calle_record = OutboundCall(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(str(tenant_id)),
                appointment_id=appointment.id,
                patient_id=patient.id,
                call_type="confirmation",
                idempotency_key=call_idempotency,
                status="pending",
                scheduled_for=appointment.slot_start - datetime.timedelta(hours=24)
            )
            db.add(calle_record)

            ws_event = OutboxEvent(
                tenant_id=tenant_id,
                event_type="WS_BROADCAST",
                payload={
                    "ws_event_type": "APPOINTMENT_CREATED",
                    "data": {
                        "id": str(appointment.id),
                        "status": "scheduled",
                        "slot_start": appointment.slot_start.isoformat(),
                        "provider": provider_name_display,
                        "patient_name_masked": "A**** K***" # Dashboard handles real masking, just an indicator
                    }
                }
            )
            db.add(ws_event)
            
            return {
                "success": True,
                "confirmation_code": confirmation_code,
                "appointment": {"date": date_display, "time": time_display, "provider": provider_name_display, "duration_minutes": duration_minutes},
                "patient_id": str(patient.id)
            }
        except Exception as e:
            if local_cache.redis_client:
                local_cache.redis_client.delete(lock_key)
            else:
                local_cache.invalidate(lock_key)
            raise e

def _invalidate_date_cache(tenant_id: str, slot_start: datetime.datetime, tz):
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=datetime.timezone.utc)
    date_formatted = slot_start.astimezone(tz).strftime("%Y-%m-%d")
    pattern = f"t:{tenant_id}:slots:{date_formatted}*"
    if local_cache.redis_client:
        for key in local_cache.redis_client.scan_iter(pattern):
            local_cache.redis_client.delete(key)
    else:
        keys_to_del = [k for k in local_cache._cache.keys() if k.startswith(f"t:{tenant_id}:slots:{date_formatted}")]
        for k in keys_to_del:
            local_cache.invalidate(k)

def _release_slot_lock(tenant_id: str, provider_id: str, slot_start: datetime.datetime, tz):
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=datetime.timezone.utc)
    if provider_id:
        slot_id_str = f"slot_{provider_id}_{slot_start.astimezone(tz).strftime('%Y%m%d_%H%M')}"
    else:
        slot_id_str = f"slot_{slot_start.astimezone(tz).strftime('%Y%m%d_%H%M')}"
    lock_key = f"lock:slot:{tenant_id}:{slot_id_str}"
    if local_cache.redis_client:
        local_cache.redis_client.delete(lock_key)
    else:
        local_cache.invalidate(lock_key)

async def _trigger_waitlist(db: AsyncSession, tenant_id: str, appointment: Appointment, tz):
    # PRD: Waitlist notification works for all tiers
    time_until_slot = appointment.slot_start - datetime.datetime.now(datetime.UTC)
    if time_until_slot < datetime.timedelta(hours=2):
        return  # Too soon to notify waitlist (slot already passed or imminent)

    hour = appointment.slot_start.astimezone(tz).hour
    if hour < 12: slot_range = "morning"
    elif hour < 17: slot_range = "afternoon"
    else: slot_range = "evening"

    day_name = appointment.slot_start.astimezone(tz).strftime("%A").lower()
    from sqlalchemy import func, or_

    from src.models.patient import Patient
    from src.models.waitlist import Waitlist
    from src.models.outbound_call import OutboundCall
    from src.services.calle_service import calle_service
    import asyncio

    waitlist_stmt = select(Waitlist).where(
        Waitlist.tenant_id == tenant_id, 
        Waitlist.booked_from_waitlist == False, 
        Waitlist.patient_id != appointment.patient_id,
        or_(Waitlist.provider_id == appointment.provider_id, Waitlist.provider_id.is_(None)),
        or_(func.lower(Waitlist.preferred_day) == day_name, Waitlist.preferred_day.is_(None)),
        or_(func.lower(Waitlist.preferred_time_range) == slot_range, Waitlist.preferred_time_range.is_(None)),
        or_(Waitlist.expires_at >= appointment.slot_start, Waitlist.expires_at.is_(None)),
        or_(Waitlist.notified_at.is_(None), Waitlist.notified_at < datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2))
    )
    if appointment.service_type:
        waitlist_stmt = waitlist_stmt.where(or_(func.lower(Waitlist.service_type) == appointment.service_type.lower(), Waitlist.service_type.is_(None)))
        
    waitlist_stmt = waitlist_stmt.order_by(Waitlist.created_at.asc()).with_for_update(skip_locked=True)
    waitlist_entry = (await db.execute(waitlist_stmt)).scalars().first()
    
    if waitlist_entry:
        wl_patient = (await db.execute(select(Patient).where(Patient.id == waitlist_entry.patient_id))).scalars().first()
        to_number = phi_crypto.decrypt(wl_patient.phone_encrypted) if wl_patient and wl_patient.phone_encrypted else ""
        
        waitlist_entry.notified_at = datetime.datetime.now(datetime.UTC)
        waitlist_entry.status = "notified"
        db.add(waitlist_entry)

        # 1. Queue instant Waitlist opening SMS
        from src.models.outbox import OutboxEvent
        slot_date_str = appointment.slot_start.astimezone(tz).strftime("%A, %B %d")
        slot_time_str = appointment.slot_start.astimezone(tz).strftime("%I:%M %p")
        sms_event = OutboxEvent(
            tenant_id=tenant_id,
            event_type="SEND_SMS",
            payload={
                "type": "waitlist_slot_opened",
                "patient_id": str(waitlist_entry.patient_id),
                "to_number": to_number,
                "day": slot_date_str,
                "time": slot_time_str,
                "service_type": appointment.service_type
            }
        )
        db.add(sms_event)

        # 2. Queue CALL-E automated waitlist fill voice call
        wl_idempotency_key = f"CALL_WAITLIST_{waitlist_entry.id}_{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d%H%M%S')}"
        wl_call_record = OutboundCall(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(str(tenant_id)),
            appointment_id=appointment.id,
            patient_id=wl_patient.id,
            call_type="waitlist",
            idempotency_key=wl_idempotency_key,
            status="pending",
            placed_at=datetime.datetime.now(datetime.UTC)
        )
        db.add(wl_call_record)

        # 3. Fire automated CALL-E voice call in background
        if to_number:
            async def _place_calle_voice_call():
                try:
                    await calle_service.place_waitlist_fill_call(
                        phone=to_number,
                        clinic_name="Our Medical Clinic",
                        slot_date=slot_date_str,
                        slot_time=slot_time_str,
                        idempotency_key=wl_idempotency_key
                    )
                except Exception:
                    pass
            asyncio.create_task(_place_calle_voice_call())

class CancelExistingAppointmentArgs(BaseModel):
    phone: str = Field(..., description="The patient's phone number for verification.")
    dob: str = Field(..., description="The patient's date of birth in YYYY-MM-DD format for verification.")
    appointment_date: str = Field(..., description="The date of the appointment they wish to cancel, in YYYY-MM-DD format.")
    reason: str = Field("", description="The reason for cancelling the appointment.")

class CancelExistingAppointmentTool(BaseTool):
    @property
    def name(self) -> str:
        return "cancel_existing_appointment"
        
    @property
    def description(self) -> str:
        return "Cancels an existing appointment after verifying the patient's identity."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return CancelExistingAppointmentArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        phone = args.get("phone")
        dob = args.get("dob")
        appointment_date = args.get("appointment_date")
        reason = args.get("reason", "")
        
        if not phone or not dob or not appointment_date:
            return {"success": False, "reason": "missing_parameters", "message": "I need your phone number, date of birth, and appointment date to cancel."}

        # Normalize phone
        import hashlib
        import re
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        if not cleaned_phone.startswith('+'):
            if len(cleaned_phone) == 10:
                cleaned_phone = '+1' + cleaned_phone
            else:
                cleaned_phone = '+' + cleaned_phone
        normalized_phone = cleaned_phone
        phone_hash = hashlib.sha256(normalized_phone.encode('utf-8')).hexdigest()
        
        # Verify Patient
        stmt = select(Patient).where(Patient.tenant_id == tenant_id, Patient.phone_hash == phone_hash, Patient.is_deleted == False)
        patients = (await db.execute(stmt)).scalars().all()
        
        if not patients:
            return {"success": False, "reason": "identity_not_found", "message": "I could not find any records with that phone number."}
            
        # Verify DOB across family
        cache_key_failures = f"failed_dob:{call_id}"
        dob_str = str(dob).split("T")[0]
        
        matched_patients = []
        for p in patients:
            if p.dob_encrypted:
                actual_dob = phi_crypto.decrypt(p.dob_encrypted)
                if actual_dob == dob_str:
                    matched_patients.append(p)
                    
        if not matched_patients:
            attempts = 1
            if local_cache.redis_client:
                attempts = local_cache.redis_client.incr(cache_key_failures)
                local_cache.redis_client.expire(cache_key_failures, 3600)
            else:
                curr = local_cache.get(cache_key_failures)
                attempts = int(curr) + 1 if curr else 1
                local_cache.set(cache_key_failures, str(attempts), ttl=3600)
                
            if attempts >= 3:
                return {"success": False, "reason": "transfer_call_to_human", "message": "I'm having trouble verifying your identity. Let me transfer you to a human agent."}
            else:
                return {"success": False, "reason": "identity_verification_failed", "message": "I couldn't verify your identity. Can you confirm your date of birth again?"}

        # Find appointment using Local Timezone to avoid UTC Date Mismatch
        import zoneinfo

        settings = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))).scalars().first()
        tz = _safe_zone_info(settings.timezone if settings and hasattr(settings, "timezone") else None, default_tz="UTC")

        apt_date_str = str(appointment_date).split("T")[0].strip()
        try:
            apt_date = datetime.datetime.strptime(apt_date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "reason": "invalid_date_format", "message": "Please provide the appointment date in YYYY-MM-DD format."}
        old_apt_stmt = select(Appointment).where(
            Appointment.tenant_id == tenant_id, 
            Appointment.patient_id.in_([p.id for p in matched_patients]), 
            Appointment.is_deleted == False, 
            Appointment.status.in_(["scheduled", "confirmed"])
        )
        all_apts = (await db.execute(old_apt_stmt)).scalars().all()
        matched_apts = []
        for apt in all_apts:
            if apt.slot_start.astimezone(tz).date() == apt_date:
                matched_apts.append(apt)
                
        if not matched_apts:
            return {"success": False, "reason": "no_appointment_found", "message": "I couldn't find any active appointments for you on that date."}
            
        if len(matched_apts) > 1:
            return {"success": False, "reason": "multiple_appointments_found", "message": "You have multiple appointments on this date. Let me transfer you to our staff to ensure we cancel the correct one."}
            
        appointment = matched_apts[0]                
            
        if appointment.slot_start <= datetime.datetime.now(datetime.UTC):
            return {"success": False, "reason": "appointment_in_past", "message": "You cannot cancel an appointment that has already passed."}
            
        time_until_apt = appointment.slot_start - datetime.datetime.now(datetime.UTC)
        if time_until_apt < datetime.timedelta(hours=24):
            return {"success": False, "reason": "transfer_call_to_human", "message": "This appointment is within 24 hours. Let me transfer you to our staff to process this late cancellation."}
            
        # Soft Delete
        appointment.is_deleted = True
        appointment.status = "cancelled"
        appointment.cancellation_reason = reason
        appointment.cancelled_at = datetime.datetime.now(datetime.UTC)
        db.add(appointment)
        await db.flush()
        
        # Audit Log
        await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="SOFT_DELETE", target_table="appointments", target_id=str(appointment.id), target_patient_id=str(appointment.patient_id), fields_accessed=["status", "is_deleted"])
        
        # Free Redis locks and cache
        _invalidate_date_cache(tenant_id, appointment.slot_start, tz)
        _release_slot_lock(tenant_id, appointment.provider_id, appointment.slot_start, tz)
            
        # Trigger Waitlist
        await _trigger_waitlist(db, tenant_id, appointment, tz)
            
        time_display = appointment.slot_start.astimezone(tz).strftime("%I:%M %p")
        date_display = appointment.slot_start.astimezone(tz).strftime("%B %d")
            
        return {"success": True, "message": f"Your appointment on {date_display} at {time_display} has been cancelled.", "cancellation_confirmed": True}

class RescheduleAppointmentArgs(BaseModel):
    phone: str = Field(..., description="The patient's phone number for verification.")
    dob: str = Field(..., description="The patient's date of birth in YYYY-MM-DD format for verification.")
    old_appointment_date: str = Field(..., description="The date of the current appointment they wish to change, in YYYY-MM-DD format.")
    new_slot_id: str = Field(..., description="The new slot ID to move the appointment to.")

class RescheduleAppointmentTool(BaseTool):
    @property
    def name(self) -> str:
        return "reschedule_appointment"
        
    @property
    def description(self) -> str:
        return "Reschedules an existing appointment to a new slot."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return RescheduleAppointmentArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        phone = args.get("phone")
        dob = args.get("dob")
        old_appointment_date = args.get("old_appointment_date")
        new_slot_id = args.get("new_slot_id")
        
        if not phone or not dob or not old_appointment_date or not new_slot_id:
            return {"success": False, "reason": "missing_parameters", "message": "I need your phone number, date of birth, old appointment date, and the new slot to reschedule."}

        # Identity Verification
        import hashlib
        import random
        import re
        import string
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        if not cleaned_phone.startswith('+'):
            if len(cleaned_phone) == 10:
                cleaned_phone = '+1' + cleaned_phone
            else:
                cleaned_phone = '+' + cleaned_phone
        normalized_phone = cleaned_phone
        phone_hash = hashlib.sha256(normalized_phone.encode('utf-8')).hexdigest()
        
        stmt = select(Patient).where(Patient.tenant_id == tenant_id, Patient.phone_hash == phone_hash, Patient.is_deleted == False)
        patients = (await db.execute(stmt)).scalars().all()
        
        if not patients:
            return {"success": False, "reason": "identity_not_found", "message": "I could not find a patient with that phone number."}
            
        cache_key_failures = f"failed_dob:{call_id}"
        dob_str = str(dob).split("T")[0]
        
        matched_patients = []
        for p in patients:
            if p.dob_encrypted:
                actual_dob = phi_crypto.decrypt(p.dob_encrypted)
                if actual_dob == dob_str:
                    matched_patients.append(p)
                    
        if not matched_patients:
            attempts = 1
            if local_cache.redis_client:
                attempts = local_cache.redis_client.incr(cache_key_failures)
                local_cache.redis_client.expire(cache_key_failures, 3600)
            else:
                curr = local_cache.get(cache_key_failures)
                attempts = int(curr) + 1 if curr else 1
                local_cache.set(cache_key_failures, str(attempts), ttl=3600)
            if attempts >= 3:
                return {"success": False, "reason": "transfer_call_to_human", "message": "I'm having trouble verifying your identity. Let me transfer you to a human agent."}
            return {"success": False, "reason": "identity_verification_failed", "message": "I couldn't verify your identity. Can you confirm your date of birth again?"}

        # Find Old Appointment
        apt_date_str = old_appointment_date.split("T")[0]
        from zoneinfo import ZoneInfo

        from src.models.tenant import Tenant
        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(tenant_stmt)).scalars().first()
        tz = _safe_zone_info(tenant.timezone if tenant and hasattr(tenant, "timezone") else None)
        
        try:
            local_old_date = datetime.datetime.strptime(apt_date_str, "%Y-%m-%d").replace(tzinfo=tz)
            utc_old_start = local_old_date.astimezone(datetime.UTC)
            utc_old_end = (local_old_date + datetime.timedelta(days=1)).astimezone(datetime.UTC)
        except Exception:
            return {"success": False, "reason": "invalid_date_format", "message": "I couldn't understand the old appointment date."}
            
        old_apt_stmt = select(Appointment).where(
            Appointment.tenant_id == tenant_id, 
            Appointment.patient_id.in_([p.id for p in matched_patients]), 
            Appointment.is_deleted == False, 
            Appointment.status.in_(["scheduled", "confirmed"]),
            Appointment.slot_start >= utc_old_start,
            Appointment.slot_start < utc_old_end
        ).order_by(Appointment.slot_start.asc())
        old_appointments_list = (await db.execute(old_apt_stmt)).scalars().all()
        
        if not old_appointments_list:
            return {"success": False, "reason": "no_appointment_found", "message": "I could not find an existing appointment for you on that date."}
            
        if len(old_appointments_list) > 1:
            return {"success": False, "reason": "multiple_appointments_found", "message": "You have multiple appointments on this date. Please transfer to human."}
            
        old_appointment = old_appointments_list[0]
        patient = next((p for p in matched_patients if p.id == getattr(old_appointment, "patient_id", None)), matched_patients[0])

        if old_appointment.slot_start <= datetime.datetime.now(datetime.UTC):
            return {"success": False, "reason": "appointment_in_past", "message": "You cannot reschedule an appointment that has already passed."}
            
        time_until_apt = old_appointment.slot_start - datetime.datetime.now(datetime.UTC)
        if time_until_apt < datetime.timedelta(hours=24):
            return {"success": False, "reason": "transfer_call_to_human", "message": "This appointment is within 24 hours. Let me transfer you to our staff to process this late reschedule."}

        # Parse New Slot
        try:
            parts = new_slot_id.split("_")
            if len(parts) == 4:
                prov_id_str = parts[1]
                date_str = parts[2]
                time_str = parts[3]
            elif len(parts) == 3:
                prov_id_str = None
                date_str = parts[1]
                time_str = parts[2]
            else:
                raise Exception("Invalid slot format")
            local_slot_start = datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M").replace(tzinfo=tz)
            utc_new_start = local_slot_start.astimezone(datetime.UTC)
        except Exception:
            return {"success": False, "reason": "invalid_slot_id", "message": "I couldn't understand the new time slot."}
            
        if utc_new_start <= datetime.datetime.now(datetime.UTC):
            return {"success": False, "reason": "slot_in_past", "message": "You cannot reschedule into a time slot that has already passed."}

        # Lock New Slot: Redis SET NX EX distributed lock
        lock_key = f"lock:slot:{tenant_id}:{new_slot_id}"
        if local_cache.redis_client:
            is_set = local_cache.redis_client.set(lock_key, call_id, nx=True, ex=120)
            if not is_set:
                current_lock = local_cache.redis_client.get(lock_key)
                current_lock_str = current_lock.decode('utf-8') if isinstance(current_lock, bytes) else str(current_lock) if current_lock else ""
                if current_lock_str and current_lock_str != call_id:
                    return {"success": False, "reason": "slot_no_longer_available", "message": "That slot was just taken. Let me check the next available."}
        else:
            cached_call_id = local_cache.get(lock_key)
            if cached_call_id and cached_call_id != call_id:
                return {"success": False, "reason": "slot_no_longer_available", "message": "That slot was just taken. Let me check the next available."}
            local_cache.set(lock_key, call_id, ttl=120)

        # Database-level SlotLock defense-in-depth against race conditions
        from src.models.slot_lock import SlotLock
        slot_lock_entry = await db.get(SlotLock, lock_key)
        if slot_lock_entry:
            if slot_lock_entry.expires_at and slot_lock_entry.expires_at > datetime.datetime.now(datetime.UTC):
                if slot_lock_entry.locked_by_call_id != call_id:
                    return {"success": False, "reason": "slot_no_longer_available", "message": "That slot was just taken. Let me check the next available."}
            slot_lock_entry.locked_by_call_id = call_id
            slot_lock_entry.locked_at = datetime.datetime.now(datetime.UTC)
            slot_lock_entry.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=120)
        else:
            slot_lock_entry = SlotLock(
                slot_key=lock_key,
                tenant_id=uuid.UUID(str(tenant_id)),
                locked_by_call_id=call_id,
                locked_at=datetime.datetime.now(datetime.UTC),
                expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=120)
            )
            db.add(slot_lock_entry)

        # Atomic Reschedule Transaction
        try:
            # Soft Delete Old
            old_appointment.is_deleted = True
            old_appointment.status = "rescheduled"
            old_appointment.cancellation_reason = "Rescheduled via AI"
            old_appointment.cancelled_at = datetime.datetime.now(datetime.UTC)
            db.add(old_appointment)
            await db.flush()
            
            # Provider Check
            from src.models.provider import Provider
            provider = None
            if prov_id_str:
                provider_stmt = select(Provider).where(Provider.tenant_id == tenant_id, Provider.id == prov_id_str)
                provider = (await db.execute(provider_stmt)).scalars().first()
            if not provider and old_appointment.provider_id:
                provider_stmt = select(Provider).where(Provider.tenant_id == tenant_id, Provider.id == old_appointment.provider_id)
                provider = (await db.execute(provider_stmt)).scalars().first()
            if not provider:
                provider_stmt = select(Provider).where(Provider.tenant_id == tenant_id, Provider.is_accepting_patients == True, Provider.is_deleted == False)
                provider = (await db.execute(provider_stmt)).scalars().first()
            if not provider:
                raise Exception("no_providers_available")
                
            # Clinic Business Hours Check (Midnight Booking Fix)
            from src.models.tenant_settings import TenantSettings
            settings_stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
            settings = (await db.execute(settings_stmt)).scalars().first()
            if settings and settings.business_hours:
                biz = settings.business_hours
                if isinstance(biz, str):
                    try:
                        import json
                        biz = json.loads(biz)
                    except Exception:
                        biz = {}
                day_name = local_slot_start.strftime("%A").lower()
                day_key = local_slot_start.strftime("%a").lower()
                day_hours = biz.get(day_name) if isinstance(biz, dict) else None
                if day_hours is None and isinstance(biz, dict):
                    day_hours = biz.get(day_key)
                if day_hours:
                    if isinstance(day_hours, str):
                        val_str = day_hours.strip().lower()
                        if val_str == "closed" or not val_str:
                            raise Exception("clinic_closed")
                        if "-" in val_str:
                            try:
                                parts = val_str.split("-")
                                start_h = int(parts[0].strip().split(":")[0])
                                end_h = int(parts[1].strip().split(":")[0])
                                if local_slot_start.hour < start_h or local_slot_start.hour >= end_h:
                                    raise Exception("outside_working_hours")
                            except Exception as ex:
                                if str(ex) in ["clinic_closed", "outside_working_hours"]:
                                    raise ex
                    elif isinstance(day_hours, dict):
                        is_open = day_hours.get("enabled", True) if "enabled" in day_hours else day_hours.get("open", True)
                        if day_hours.get("closed") is True or not is_open:
                            raise Exception("clinic_closed")
                        try:
                            s_str = str(day_hours.get("start") or "09:00").strip()
                            e_str = str(day_hours.get("end") or "17:00").strip()
                            start_h = int(s_str.split(":")[0])
                            end_h = int(e_str.split(":")[0])
                            if local_slot_start.hour < start_h or local_slot_start.hour >= end_h:
                                raise Exception("outside_working_hours")
                        except Exception as ex:
                            if str(ex) in ["clinic_closed", "outside_working_hours"]:
                                raise ex

            # Doctor Conflict Check: Doctor
            duration_minutes = old_appointment.duration_minutes or 30
            utc_new_end = utc_new_start + datetime.timedelta(minutes=duration_minutes)
            conflict_stmt = select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.provider_id == provider.id if provider else None,
                Appointment.is_deleted == False,
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.slot_start < utc_new_end,
                Appointment.slot_end > utc_new_start
            ).with_for_update()
            conflict = (await db.execute(conflict_stmt)).scalars().first()
            if conflict:
                raise Exception("slot_no_longer_available")
                
            # Conflict Check: Patient double-booking
            patient_conflict_stmt = select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.patient_id == patient.id,
                Appointment.is_deleted == False,
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.slot_start < utc_new_end,
                Appointment.slot_end > utc_new_start
            ).with_for_update()
            patient_conflict = (await db.execute(patient_conflict_stmt)).scalars().first()
            if patient_conflict:
                raise Exception("patient_already_booked")
                
            # Generate Code safely
            confirmation_code = None
            for _ in range(3):
                code = "APPT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not (await db.execute(select(Appointment).where(Appointment.confirmation_code == code))).scalars().first():
                    confirmation_code = code
                    break
            if not confirmation_code:
                import uuid
                confirmation_code = "APPT-" + uuid.uuid4().hex[:6].upper()

            new_appointment = Appointment(
                tenant_id=tenant_id,
                patient_id=patient.id,
                provider_id=provider.id,
                slot_start=utc_new_start,
                slot_end=utc_new_end,
                service_type=old_appointment.service_type,
                duration_minutes=duration_minutes,
                status="scheduled",
                booked_by="ai_agent",
                booked_via_call_id=call_id,
                confirmation_code=confirmation_code,
                rescheduled_from_id=old_appointment.id
            )
            new_appointment.service_type = old_appointment.service_type
            db.add(new_appointment)
            await db.flush()
            
            # Auto-clear Ghost Waitlists
            from sqlalchemy import or_

            from src.models.waitlist import Waitlist
            clear_wl_stmt = select(Waitlist).where(
                Waitlist.tenant_id == tenant_id,
                Waitlist.patient_id == patient.id,
                Waitlist.booked_from_waitlist == False
            )
            if new_appointment.service_type:
                clear_wl_stmt = clear_wl_stmt.where(or_(Waitlist.service_type == new_appointment.service_type, Waitlist.service_type.is_(None)))
                
            pending_waitlists = (await db.execute(clear_wl_stmt.with_for_update())).scalars().all()
            for wl in pending_waitlists:
                wl.booked_from_waitlist = True
                db.add(wl)
            
            await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="UPDATE", target_table="appointments", target_id=str(new_appointment.id), target_patient_id=str(patient.id), fields_accessed=["rescheduled_from_id", "slot_start"])
            
            # Audit Log for Soft-Delete
            await log_audit_event(db=db, tenant_id=tenant_id, actor_type="ai_agent", actor_id=call_id, action="SOFT_DELETE", target_table="appointments", target_id=str(old_appointment.id), target_patient_id=str(patient.id), fields_accessed=["status", "is_deleted"])
            
            # Cache Invalidation for New Slot
            _invalidate_date_cache(tenant_id, local_slot_start, tz)
            
            # Cache Invalidation for Old Slot
            _invalidate_date_cache(tenant_id, old_appointment.slot_start, tz)
            
            # Release Redis Lock for Old Slot
            _release_slot_lock(tenant_id, old_appointment.provider_id, old_appointment.slot_start, tz)
            
            # Trigger Waitlist for Old Slot
            await _trigger_waitlist(db, tenant_id, old_appointment, tz)
                    
            return {
                "success": True,
                "message": "Successfully rescheduled.",
                "confirmation_code": confirmation_code,
                "appointment": {
                    "date": local_slot_start.strftime("%A, %B %d"),
                    "time": local_slot_start.strftime("%I:%M %p"),
                    "provider": provider.display_name,
                    "duration_minutes": duration_minutes
                }
            }
        except Exception as e:
            await db.rollback()
            if local_cache.redis_client:
                local_cache.redis_client.delete(lock_key)
            else:
                local_cache.invalidate(lock_key)
            
            if str(e) == "slot_no_longer_available":
                return {"success": False, "reason": "slot_no_longer_available", "message": "That slot was just taken. Let me check the next available."}
            elif str(e) == "patient_already_booked":
                return {"success": False, "reason": "patient_already_booked", "message": "You already have another appointment at this time."}
            elif str(e) in ["clinic_closed", "outside_working_hours"]:
                return {"success": False, "reason": "outside_working_hours", "message": "The selected time is outside the doctor's working hours."}
            elif str(e) == "no_providers_available":
                return {"success": False, "reason": "no_providers_available", "message": "No doctors are available right now."}
                
            return {"success": False, "reason": "reschedule_failed", "message": "An error occurred while rescheduling your appointment."}

class AddToWaitlistArgs(BaseModel):
    phone: str = Field(..., description="The patient's 10-digit phone number.")
    patient_name: str = Field("Unknown Patient", description="The patient's full name.")
    preferred_day: str = Field("any", description="The preferred day of the week, e.g. 'Monday', 'Friday', or 'any'.")
    preferred_time_range: str = Field("any", description="The preferred time of day: 'morning', 'afternoon', 'evening', or 'any'.")
    service_type: str = Field("", description="The type of service requested.")

class AddToWaitlistTool(BaseTool):
    @property
    def name(self) -> str:
        return "add_to_waitlist"
        
    @property
    def description(self) -> str:
        return "Adds a patient to the clinic's waitlist if their desired time slot is unavailable."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return AddToWaitlistArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        phone = args.get("phone")
        patient_name = args.get("patient_name", "Unknown Patient")
        
        import re
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        if not cleaned_phone.startswith('+'):
            if len(cleaned_phone) == 10:
                cleaned_phone = '+1' + cleaned_phone
            else:
                cleaned_phone = '+' + cleaned_phone
        normalized_phone = cleaned_phone
            
        phone_hash = hashlib.sha256(normalized_phone.encode('utf-8')).hexdigest()
        
        stmt = select(Patient).where(Patient.tenant_id == tenant_id, Patient.phone_hash == phone_hash, Patient.is_deleted == False)
        patient = (await db.execute(stmt)).scalars().first()
        
        if not patient:
            patient = Patient(tenant_id=tenant_id, phone_hash=phone_hash, full_name_encrypted=phi_crypto.encrypt(patient_name), phone_encrypted=phi_crypto.encrypt(normalized_phone), is_existing_patient=False)
            db.add(patient)
            await db.flush()
            
        entry = Waitlist(
            tenant_id=tenant_id,
            patient_id=patient.id,
            preferred_day=args.get("preferred_day", "any"),
            preferred_time_range=args.get("preferred_time_range", "any"),
            service_type=args.get("service_type", ""),
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)
        )
        db.add(entry)
        
        return {"success": True, "message": "Added to waitlist.", "position": 1, "eta_days": "3-5"}


# ─────────────────────────────────────────────────────────────────────────────
# Aliases for Standard Retell AI & CALL-E Tool Calling Schemes
# ─────────────────────────────────────────────────────────────────────────────

class GetAvailableSlotsArgs(CheckCalendarAvailabilityArgs):
    pass


class GetAvailableSlotsTool(CheckCalendarAvailabilityTool):
    @property
    def name(self) -> str:
        return "get_available_slots"

    @property
    def description(self) -> str:
        return "Checks the clinic's calendar for available appointment slots based on patient preferences."

    @property
    def args_schema(self) -> type[BaseModel]:
        return GetAvailableSlotsArgs


class CancelAppointmentArgs(CancelExistingAppointmentArgs):
    pass


class CancelAppointmentTool(CancelExistingAppointmentTool):
    @property
    def name(self) -> str:
        return "cancel_appointment"

    @property
    def description(self) -> str:
        return "Cancels an existing appointment after verifying the patient's identity."

    @property
    def args_schema(self) -> type[BaseModel]:
        return CancelAppointmentArgs


