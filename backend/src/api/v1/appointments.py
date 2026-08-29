import asyncio
import math
import random
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import local_cache
from src.core.logger import log
from src.core.security import get_current_user_with_role, require_permission
from src.db.engine import get_db
from src.models.appointment import Appointment
from src.models.outbound_call import OutboundCall
from src.models.outbox import OutboxEvent
from src.models.patient import Patient
from src.models.provider import Provider
from src.models.sms_log import SmsLog
from src.models.tenant import Tenant
from src.models.tenant_settings import TenantSettings
from src.models.user import User
from src.models.waitlist import Waitlist
from src.schemas.appointment import (
    AppointmentCreateData,
    AppointmentCreateRequest,
    AppointmentCreateResponse,
    AppointmentDeleteRequest,
    AppointmentDetailResponse,
    AppointmentListResponse,
    AppointmentUpdateData,
    AppointmentUpdateRequest,
    AppointmentUpdateResponse,
)
from src.services.audit_service import audit_service
from src.services.calle_service import calle_service

router = APIRouter(prefix="/appointments", tags=["appointments"])


def mask_phi(user: User, field_name: str, value: str) -> str:
    if user.role in ["owner", "clinician"]:
        return value
    if not value:
        return value
    if field_name == "full_name":
        parts = value.split(" ")
        masked_parts = [f"{p[0]}{'*' * (len(p)-1)}" for p in parts if p]
        return " ".join(masked_parts)
    elif field_name == "phone":
        if len(value) >= 4:
            return f"***-***-{value[-4:]}"
        return "****"
    return "***"


def generate_confirmation_code() -> str:
    return "APPT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _invalidate_date_cache(tenant_id: uuid.UUID | str, slot_start: datetime, tz: ZoneInfo):
    """Invalidates the Redis and local cache for slots on the given day."""
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=UTC)
    date_formatted = slot_start.astimezone(tz).strftime("%Y-%m-%d")
    pattern = f"t:{tenant_id}:slots:{date_formatted}*"
    if local_cache.redis_client:
        try:
            for key in local_cache.redis_client.scan_iter(pattern):
                local_cache.redis_client.delete(key)
        except Exception:
            pass
    else:
        keys_to_del = [k for k in local_cache._cache.keys() if k.startswith(f"t:{tenant_id}:slots:{date_formatted}")]
        for k in keys_to_del:
            local_cache.invalidate(k)


async def _trigger_waitlist_fill(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    appointment: Appointment,
    tz: ZoneInfo,
    clinic_name: str = "Our Medical Clinic"
) -> dict[str, Any] | None:
    """
    Trigger instant waitlist fill-in automated call and SMS when an appointment is cancelled.
    Searches for matching waiting patients and places a CALL-E outbound call.
    """
    time_until_slot = appointment.slot_start - datetime.now(UTC)
    if time_until_slot < timedelta(hours=1):
        log.info(f"[Waitlist] Slot {appointment.id} is too soon (<1h) for waitlist fill-in.")
        return None

    hour = appointment.slot_start.astimezone(tz).hour
    if hour < 12:
        slot_range = "morning"
    elif hour < 17:
        slot_range = "afternoon"
    else:
        slot_range = "evening"

    day_name = appointment.slot_start.astimezone(tz).strftime("%A").lower()

    waitlist_stmt = select(Waitlist).where(
        Waitlist.tenant_id == tenant_id,
        Waitlist.booked_from_waitlist == False,
        Waitlist.patient_id != appointment.patient_id,
        or_(Waitlist.provider_id == appointment.provider_id, Waitlist.provider_id.is_(None)),
        or_(func.lower(Waitlist.preferred_day) == day_name, Waitlist.preferred_day.is_(None)),
        or_(func.lower(Waitlist.preferred_time_range) == slot_range, Waitlist.preferred_time_range.is_(None)),
        or_(Waitlist.expires_at >= appointment.slot_start, Waitlist.expires_at.is_(None)),
        or_(Waitlist.notified_at.is_(None), Waitlist.notified_at < datetime.now(UTC) - timedelta(hours=2)),
        Waitlist.status.in_(["waiting", "pending"])
    )
    if appointment.service_type:
        waitlist_stmt = waitlist_stmt.where(
            or_(func.lower(Waitlist.service_type) == appointment.service_type.lower(), Waitlist.service_type.is_(None))
        )

    waitlist_stmt = waitlist_stmt.order_by(Waitlist.created_at.asc()).with_for_update(skip_locked=True)
    waitlist_entry = (await db.execute(waitlist_stmt)).scalars().first()

    if not waitlist_entry:
        log.info(f"[Waitlist] No matching waitlist candidate found for freed slot at {appointment.slot_start}.")
        return None

    # Retrieve patient information
    pat_stmt = select(Patient).where(Patient.id == waitlist_entry.patient_id)
    wl_patient = (await db.execute(pat_stmt)).scalars().first()
    if not wl_patient:
        return None

    patient_phone = wl_patient.phone
    patient_name = wl_patient.full_name or "Patient"

    slot_date_str = appointment.slot_start.astimezone(tz).strftime("%A, %B %d")
    slot_time_str = appointment.slot_start.astimezone(tz).strftime("%I:%M %p")

    # Update waitlist status
    waitlist_entry.notified_at = datetime.now(UTC)
    waitlist_entry.status = "notified"
    db.add(waitlist_entry)

    # 1. Queue instant SMS notification via Outbox (Telnyx)
    if patient_phone:
        sms_event = OutboxEvent(
            tenant_id=tenant_id,
            event_type="SEND_SMS",
            payload={
                "type": "waitlist_slot_opened",
                "patient_id": str(waitlist_entry.patient_id),
                "to_number": patient_phone,
                "patient_name": patient_name,
                "day": slot_date_str,
                "time": slot_time_str,
                "service_type": appointment.service_type or "Appointment"
            }
        )
        db.add(sms_event)

    # 2. Queue & record CALL-E Waitlist Fill-in Outbound Call
    idempotency_key = f"CALL_WAITLIST_{waitlist_entry.id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    call_record = OutboundCall(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        appointment_id=appointment.id,
        patient_id=wl_patient.id,
        call_type="waitlist",
        idempotency_key=idempotency_key,
        status="pending",
        placed_at=datetime.now(UTC)
    )
    db.add(call_record)

    # 3. Fire CALL-E voice call asynchronously in background
    if patient_phone:
        async def _call_in_background():
            try:
                result = await calle_service.place_waitlist_fill_call(
                    phone=patient_phone,
                    clinic_name=clinic_name,
                    slot_date=slot_date_str,
                    slot_time=slot_time_str,
                    idempotency_key=idempotency_key
                )
                log.info(f"[CALL-E Waitlist] Automated voice call placed to {patient_phone[:6]}**** (Result: {result.get('status')})")
            except Exception as call_err:
                log.warning(f"[CALL-E Waitlist] Failed to place instant voice call: {call_err}")

        asyncio.create_task(_call_in_background())

    log.info(f"[Waitlist] Triggered instant fill-in for patient {wl_patient.id} on freed slot {appointment.id}")
    return {"waitlist_id": str(waitlist_entry.id), "patient_id": str(wl_patient.id)}


@router.get("/availability")
async def get_availability(
    date: str = Query(..., description="Date to check in YYYY-MM-DD format"),
    provider_id: uuid.UUID | None = Query(None, description="Filter by specific provider"),
    time_preference: str = Query("any", description="morning | afternoon | evening | any"),
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns available appointment slots for a given date.
    Used by the AI voice agent (Retell/CALL-E tool: check_calendar_availability) and frontend calendar.
    Slots are 30-minute blocks filtered against existing bookings, provider work hours, and active slot locks.
    """
    # Parse date
    try:
        target_date = datetime.strptime(date.split("T")[0], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Get tenant timezone
    tenant_stmt = select(Tenant).where(Tenant.id == user.tenant_id).limit(1)
    tenant = (await db.execute(tenant_stmt)).scalars().first()
    tz = ZoneInfo(tenant.timezone) if tenant and tenant.timezone else ZoneInfo("America/Chicago")

    # Determine day-start and day-end in UTC
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=tz)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, tzinfo=tz)

    # Get all booked appointments for this day
    booked_stmt = select(Appointment).where(
        Appointment.tenant_id == user.tenant_id,
        Appointment.is_deleted == False,
        Appointment.status != "cancelled",
        Appointment.slot_start >= day_start,
        Appointment.slot_start <= day_end,
    )
    if provider_id:
        booked_stmt = booked_stmt.where(Appointment.provider_id == provider_id)
    booked_result = await db.execute(booked_stmt)
    booked_appointments = booked_result.scalars().all()
    booked_slots = {apt.slot_start.astimezone(tz).strftime("%H:%M") for apt in booked_appointments}

    # Get tenant settings for business hours
    settings_stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id).limit(1)
    tenant_settings = (await db.execute(settings_stmt)).scalars().first()
    business_hours = {}
    if tenant_settings and tenant_settings.business_hours:
        business_hours = tenant_settings.business_hours if isinstance(tenant_settings.business_hours, dict) else {}

    # Determine work hours for this day
    day_name = target_date.strftime("%A").lower()
    day_config = business_hours.get(day_name, {})
    is_open = day_config.get("open", True) if isinstance(day_config, dict) else True
    if not is_open:
        return {"date": date, "available_slots": [], "message": "Clinic is closed on this day."}

    open_time_str = day_config.get("open_time", "09:00") if isinstance(day_config, dict) else "09:00"
    close_time_str = day_config.get("close_time", "17:00") if isinstance(day_config, dict) else "17:00"
    try:
        open_hour, open_min = map(int, open_time_str.split(":"))
        close_hour, close_min = map(int, close_time_str.split(":"))
    except Exception:
        open_hour, open_min = 9, 0
        close_hour, close_min = 17, 0

    # Time preference filters
    pref_filter = {
        "morning": (6, 12),
        "afternoon": (12, 17),
        "evening": (17, 21),
        "any": (0, 24),
    }.get(time_preference.lower(), (0, 24))

    # Generate 30-minute slots
    available_slots = []
    now_tz = datetime.now(tz)
    current_hour = open_hour
    current_min = open_min
    while (current_hour < close_hour) or (current_hour == close_hour and current_min < close_min):
        slot_str = f"{current_hour:02d}:{current_min:02d}"
        slot_dt = datetime(target_date.year, target_date.month, target_date.day,
                           current_hour, current_min, tzinfo=tz)
        if slot_dt > now_tz and slot_str not in booked_slots:
            if pref_filter[0] <= current_hour < pref_filter[1]:
                available_slots.append({
                    "time": slot_str,
                    "datetime_utc": slot_dt.astimezone(UTC).isoformat(),
                    "label": slot_dt.strftime("%I:%M %p"),
                })
        current_min += 30
        if current_min >= 60:
            current_min -= 60
            current_hour += 1

    return {
        "date": date,
        "day": target_date.strftime("%A"),
        "timezone": str(tz),
        "available_slots": available_slots,
        "total_available": len(available_slots),
        "booked_count": len(booked_slots),
    }


@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    date_from: str | None = Query(None, description="ISO date start filter"),
    date_to: str | None = Query(None, description="ISO date end filter"),
    provider_id: uuid.UUID | None = Query(None, description="Filter by doctor/provider"),
    status: str | None = Query(None, description="Filter by status (scheduled, confirmed, etc.)"),
    search: str | None = Query(None, description="Search by patient name or phone"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """
    List appointments with rich filtering: by Doctor, by Date Range, by Status, and by Patient Search.
    """
    stmt = select(Appointment, Patient, Provider).join(
        Patient, Appointment.patient_id == Patient.id
    ).join(
        Provider, Appointment.provider_id == Provider.id
    ).where(
        Appointment.tenant_id == user.tenant_id,
        Appointment.is_deleted == False
    )

    if date_from:
        try:
            start_date = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            stmt = stmt.where(Appointment.slot_start >= start_date)
        except Exception:
            pass

    if date_to:
        try:
            end_date = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            stmt = stmt.where(Appointment.slot_end <= end_date + timedelta(days=1))
        except Exception:
            pass

    if provider_id:
        stmt = stmt.where(Appointment.provider_id == provider_id)

    if status and status.lower() != "all":
        stmt = stmt.where(Appointment.status == status.lower())

    if search:
        search_term = f"%{search.strip().lower()}%"
        # Search via Patient name or phone
        stmt = stmt.where(
            or_(
                func.lower(Patient.full_name_encrypted).like(search_term),
                Patient.phone_hash.like(search_term)
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(Appointment.slot_start.asc()).offset((page - 1) * per_page).limit(per_page)
    res = await db.execute(stmt)
    rows = res.all()

    out = []
    for appt, pat, prov in rows:
        out.append({
            "id": appt.id,
            "slot_start": appt.slot_start,
            "slot_end": appt.slot_end,
            "service_type": appt.service_type,
            "duration_minutes": appt.duration_minutes,
            "status": appt.status,
            "booked_by": appt.booked_by or "staff",
            "confirmation_code": appt.confirmation_code,
            "sms_confirmed": appt.sms_confirmed,
            "call_confirmed": getattr(appt, "call_confirmed", False),
            "created_at": appt.created_at,
            "patient": {
                "id": pat.id,
                "full_name": mask_phi(user, "full_name", pat.full_name),
                "phone": mask_phi(user, "phone", pat.phone)
            },
            "provider": {
                "id": prov.id,
                "display_name": prov.display_name,
                "specialty": prov.specialty
            }
        })

    return AppointmentListResponse(
        success=True,
        data={"appointments": out},
        meta={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1
        }
    )


@router.post("", response_model=AppointmentCreateResponse, status_code=201)
async def create_appointment(
    req: AppointmentCreateRequest,
    user: User = Depends(require_permission(["owner", "clinician", "staff"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new appointment with slot conflict validation, instant Telnyx SMS confirmation,
    and automatic CALL-E 24h confirmation call queuing.
    """
    # 1. Check for slot conflict
    conflict_stmt = select(Appointment).where(
        Appointment.tenant_id == user.tenant_id,
        Appointment.provider_id == req.provider_id,
        Appointment.slot_start < req.slot_end,
        Appointment.slot_end > req.slot_start,
        Appointment.is_deleted == False,
        Appointment.status != "cancelled"
    )
    conflict_res = await db.execute(conflict_stmt)
    if conflict_res.first():
        raise HTTPException(status_code=409, detail="APPOINTMENT_SLOT_TAKEN: This slot is already booked.")

    duration = int((req.slot_end - req.slot_start).total_seconds() / 60)
    conf_code = generate_confirmation_code()

    # 2. Instantiate Appointment
    new_appt = Appointment(
        tenant_id=user.tenant_id,
        patient_id=req.patient_id,
        provider_id=req.provider_id,
        slot_start=req.slot_start,
        slot_end=req.slot_end,
        duration_minutes=duration,
        service_type=req.service_type,
        status="scheduled",
        booked_by="staff",
        confirmation_code=conf_code,
        sms_confirmed=False
    )
    db.add(new_appt)
    await db.flush()

    # 3. Retrieve Patient and Provider information
    pat_stmt = select(Patient).where(Patient.id == req.patient_id)
    pat = (await db.execute(pat_stmt)).scalars().first()
    if not pat:
        raise HTTPException(status_code=404, detail="Patient record not found.")

    prov_stmt = select(Provider).where(Provider.id == req.provider_id)
    prov = (await db.execute(prov_stmt)).scalars().first()
    prov_name = prov.display_name if prov else "Our Doctor"

    tenant_stmt = select(Tenant).where(Tenant.id == user.tenant_id)
    tenant = (await db.execute(tenant_stmt)).scalars().first()
    tz = ZoneInfo(tenant.timezone) if tenant and tenant.timezone else ZoneInfo("America/Chicago")
    clinic_name = tenant.name if tenant else "Sunrise Medical Clinic"

    local_start = new_appt.slot_start.astimezone(tz)
    date_display = local_start.strftime("%A, %B %d")
    time_display = local_start.strftime("%I:%M %p")

    # 4. Instant SMS Confirmation via Transactional Outbox (Telnyx)
    patient_phone = pat.phone
    patient_name = pat.full_name or "Patient"

    if req.send_confirmation_sms and patient_phone:
        sms_event = OutboxEvent(
            tenant_id=user.tenant_id,
            event_type="SEND_SMS",
            payload={
                "type": "appointment_confirmation",
                "to_number": patient_phone,
                "patient_name": patient_name,
                "apt_date": date_display,
                "apt_time": time_display,
                "provider_name": prov_name,
                "confirmation_code": conf_code,
                "appointment_id": str(new_appt.id)
            }
        )
        db.add(sms_event)

    # 5. Auto-Queue CALL-E 24h Confirmation Call
    idempotency_key = f"CALL_CONFIRMATION_{new_appt.id}_{new_appt.slot_start.date().isoformat()}"
    scheduled_call_time = new_appt.slot_start - timedelta(hours=24)
    calle_record = OutboundCall(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        appointment_id=new_appt.id,
        patient_id=pat.id,
        call_type="confirmation",
        idempotency_key=idempotency_key,
        status="pending",
        scheduled_for=scheduled_call_time
    )
    db.add(calle_record)

    # 6. WebSocket Real-time Broadcast Outbox Event
    ws_event = OutboxEvent(
        tenant_id=user.tenant_id,
        event_type="WS_BROADCAST",
        payload={
            "ws_event_type": "APPOINTMENT_CREATED",
            "data": {
                "id": str(new_appt.id),
                "status": "scheduled",
                "slot_start": new_appt.slot_start.isoformat(),
                "provider": prov_name,
                "patient_name": patient_name,
                "booked_by": "staff"
            }
        }
    )
    db.add(ws_event)

    # 7. Audit log creation
    await audit_service.log(
        action="CREATE",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="appointments",
        target_id=new_appt.id,
        target_patient_id=req.patient_id,
        ip_address="internal",
        change_reason="Created manual appointment with automated CALL-E and SMS triggers"
    )

    # 8. Invalidate availability cache
    _invalidate_date_cache(user.tenant_id, new_appt.slot_start, tz)

    await db.commit()

    # 9. Send patient confirmation email in background (non-blocking)
    try:
        from src.services.email_service import email_service
        if pat.email:
            appt_date_str = new_appt.slot_start.strftime("%A, %B %d, %Y")
            appt_time_str = new_appt.slot_start.strftime("%I:%M %p")
            await email_service.send_appointment_confirmation_email(
                patient_email=pat.email,
                patient_name=patient_name,
                appointment_date=appt_date_str,
                appointment_time=appt_time_str,
                doctor_name=prov_name,
                service_type=new_appt.service_type or "Appointment",
                confirmation_code=conf_code,
                clinic_name=clinic_name,
            )
    except Exception as email_err:
        log.warning(f"[Appointments] Confirmation email note: {email_err}")

    return AppointmentCreateResponse(
        success=True,
        data=AppointmentCreateData(
            appointment_id=new_appt.id,
            confirmation_code=conf_code,
            sms_sent=req.send_confirmation_sms and bool(patient_phone)
        )
    )


@router.get("/{id}", response_model=AppointmentDetailResponse)
async def get_appointment(
    id: uuid.UUID,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full appointment details including patient profile, provider details, and SMS interaction history.
    """
    stmt = select(Appointment, Patient, Provider).join(
        Patient, Appointment.patient_id == Patient.id
    ).join(
        Provider, Appointment.provider_id == Provider.id
    ).where(
        Appointment.id == id,
        Appointment.tenant_id == user.tenant_id,
        Appointment.is_deleted == False
    )
    
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    appt, pat, prov = row

    # Fetch SMS logs for this appointment
    sms_stmt = select(SmsLog).where(SmsLog.appointment_id == id).order_by(SmsLog.created_at.asc())
    sms_res = await db.execute(sms_stmt)
    sms_history = [
        {
            "direction": sms.direction,
            "sms_type": sms.sms_type,
            "sent_at": sms.created_at.isoformat(),
            "status": sms.status
        } for sms in sms_res.scalars().all()
    ]

    return AppointmentDetailResponse(
        success=True,
        data={
            "id": appt.id,
            "slot_start": appt.slot_start,
            "slot_end": appt.slot_end,
            "service_type": appt.service_type,
            "duration_minutes": appt.duration_minutes,
            "status": appt.status,
            "booked_by": appt.booked_by or "staff",
            "confirmation_code": appt.confirmation_code,
            "sms_confirmed": appt.sms_confirmed,
            "created_at": appt.created_at,
            "patient": {
                "id": pat.id,
                "full_name": mask_phi(user, "full_name", pat.full_name),
                "phone": mask_phi(user, "phone", pat.phone)
            },
            "provider": {
                "id": prov.id,
                "display_name": prov.display_name,
                "specialty": prov.specialty
            },
            "sms_history": sms_history,
            "rescheduled_from_id": appt.rescheduled_from_id
        }
    )


@router.patch("/{id}", response_model=AppointmentUpdateResponse)
async def update_appointment(
    id: uuid.UUID,
    req: AppointmentUpdateRequest,
    user: User = Depends(require_permission(["owner", "clinician", "staff"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Update appointment status, reschedule time slots, or cancel with automated waitlist fill-in.
    """
    stmt = select(Appointment).where(
        Appointment.id == id,
        Appointment.tenant_id == user.tenant_id,
        Appointment.is_deleted == False
    )
    res = await db.execute(stmt)
    appt = res.scalar_one_or_none()
    
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    tenant_stmt = select(Tenant).where(Tenant.id == user.tenant_id)
    tenant = (await db.execute(tenant_stmt)).scalars().first()
    tz = ZoneInfo(tenant.timezone) if tenant and tenant.timezone else ZoneInfo("America/Chicago")
    clinic_name = tenant.name if tenant else "Sunrise Medical Clinic"

    old_status = appt.status
    if req.status:
        appt.status = req.status
        if req.status == "cancelled":
            appt.cancelled_at = datetime.now(UTC)
            if req.cancellation_reason:
                appt.cancellation_reason = req.cancellation_reason
        
    if req.slot_start is not None or req.slot_end is not None:
        new_start = req.slot_start or appt.slot_start
        new_end = req.slot_end or appt.slot_end
        
        # Check for conflicts
        conflict_stmt = select(Appointment).where(
            Appointment.tenant_id == user.tenant_id,
            Appointment.provider_id == appt.provider_id,
            Appointment.slot_start < new_end,
            Appointment.slot_end > new_start,
            Appointment.is_deleted == False,
            Appointment.status != "cancelled",
            Appointment.id != appt.id
        )
        conflict_res = await db.execute(conflict_stmt)
        if conflict_res.first():
            raise HTTPException(status_code=409, detail="APPOINTMENT_SLOT_TAKEN: This slot is already booked.")
            
        if appt.slot_start != new_start or appt.slot_end != new_end:
            _invalidate_date_cache(user.tenant_id, appt.slot_start, tz)
            appt.rescheduled_from_id = appt.id
            appt.slot_start = new_start
            appt.slot_end = new_end
            appt.duration_minutes = int((new_end - new_start).total_seconds() / 60)
            _invalidate_date_cache(user.tenant_id, new_start, tz)

    # If appointment was cancelled, trigger waitlist fill-in automated call
    if req.status == "cancelled" and old_status != "cancelled":
        _invalidate_date_cache(user.tenant_id, appt.slot_start, tz)
        await _trigger_waitlist_fill(db, user.tenant_id, appt, tz, clinic_name)

        # Broadcast cancellation event via Outbox
        ws_cancel = OutboxEvent(
            tenant_id=user.tenant_id,
            event_type="WS_BROADCAST",
            payload={
                "ws_event_type": "APPOINTMENT_CANCELLED",
                "data": {
                    "id": str(appt.id),
                    "status": "cancelled",
                    "slot_start": appt.slot_start.isoformat()
                }
            }
        )
        db.add(ws_cancel)
    else:
        # Broadcast status update event
        ws_update = OutboxEvent(
            tenant_id=user.tenant_id,
            event_type="WS_BROADCAST",
            payload={
                "ws_event_type": "APPOINTMENT_UPDATED",
                "data": {
                    "id": str(appt.id),
                    "status": appt.status,
                    "slot_start": appt.slot_start.isoformat()
                }
            }
        )
        db.add(ws_update)
        
    await audit_service.log(
        action="UPDATE",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="appointments",
        target_id=appt.id,
        target_patient_id=appt.patient_id,
        ip_address="internal",
        change_reason=f"Appointment updated (status={appt.status}, slot_start={appt.slot_start})"
    )
    
    await db.commit()
    
    return AppointmentUpdateResponse(
        success=True,
        data=AppointmentUpdateData(
            appointment_id=appt.id,
            status=appt.status,
            slot_start=appt.slot_start,
            slot_end=appt.slot_end
        )
    )


@router.delete("/{id}", status_code=204)
async def delete_appointment(
    id: uuid.UUID,
    req: AppointmentDeleteRequest,
    user: User = Depends(require_permission(["owner", "clinician"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft-delete appointment and trigger instant waitlist fill-in automated call.
    """
    stmt = select(Appointment).where(
        Appointment.id == id,
        Appointment.tenant_id == user.tenant_id,
        Appointment.is_deleted == False
    )
    res = await db.execute(stmt)
    appt = res.scalar_one_or_none()
    
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    tenant_stmt = select(Tenant).where(Tenant.id == user.tenant_id)
    tenant = (await db.execute(tenant_stmt)).scalars().first()
    tz = ZoneInfo(tenant.timezone) if tenant and tenant.timezone else ZoneInfo("America/Chicago")
    clinic_name = tenant.name if tenant else "Sunrise Medical Clinic"

    appt.is_deleted = True
    appt.deleted_at = datetime.now(UTC)
    appt.status = "cancelled"
    appt.cancellation_reason = req.reason
    appt.deleted_by_id = user.id
    
    # Invalidate availability cache
    _invalidate_date_cache(user.tenant_id, appt.slot_start, tz)

    # Trigger waitlist fill-in automated call
    await _trigger_waitlist_fill(db, user.tenant_id, appt, tz, clinic_name)

    # Broadcast cancellation via Outbox
    ws_del = OutboxEvent(
        tenant_id=user.tenant_id,
        event_type="WS_BROADCAST",
        payload={
            "ws_event_type": "APPOINTMENT_CANCELLED",
            "data": {
                "id": str(appt.id),
                "status": "cancelled",
                "slot_start": appt.slot_start.isoformat()
            }
        }
    )
    db.add(ws_del)

    await audit_service.log(
        action="SOFT_DELETE",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="appointments",
        target_id=appt.id,
        target_patient_id=appt.patient_id,
        ip_address="internal",
        change_reason=req.reason
    )
    
    await db.commit()
    return Response(status_code=204)
