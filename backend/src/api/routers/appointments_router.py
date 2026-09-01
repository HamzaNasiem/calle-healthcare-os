from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
import datetime

from ...core.database import supabase, supabase_read
from ...core.security import require_permission, AuthenticatedUser, require_active_subscription, validate_phone_format
from ...services.calendar_service import calendar_service
from ...services.audit_service import audit_service
from ...services.notification_service import notification_service

router = APIRouter(prefix="/appointments", tags=["Appointments"], dependencies=[Depends(require_active_subscription)])

class AppointmentCreate(BaseModel):
    patient_name: str
    patient_phone: str
    patient_id: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_id: Optional[str] = None
    provider_id: Optional[str] = None
    appointment_type: Optional[str] = "Follow-up"
    datetime: str
    duration_minutes: Optional[int] = 30
    notes: Optional[str] = None
    send_confirmation_sms: Optional[bool] = True

    @field_validator("patient_phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        validate_phone_format(v)
        return v

class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    doctor_name: Optional[str] = None
    notes: Optional[str] = None
    insurance_verified: Optional[bool] = None
    eligibility_status: Optional[str] = None
    prior_auth_required: Optional[bool] = None
    revenue_amount: Optional[int] = None

@router.get("")
async def get_appointments(
    auth: AuthenticatedUser = Depends(require_permission("appointments:read")),
    status: Optional[str] = None,
    doctor_name: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500)
):
    clinic_id = auth.clinic_id
    offset = (page - 1) * limit
    
    query = supabase_read.table("appointments").select(
        "id, patient_id, patient_name, patient_phone, appointment_type, datetime, duration_minutes, status, booked_by, reminder_sent, insurance_verified, revenue_amount, noshow_risk, notes, created_at",
        count="exact"
    ).eq("clinic_id", clinic_id).order("datetime", desc=False).range(offset, offset + limit - 1)
    
    if status and status.lower() != "all":
        query = query.eq("status", status.lower())
    if date_from:
        query = query.gte("datetime", date_from)
    if date_to:
        query = query.lte("datetime", date_to)
    if search:
        s = search.strip()
        query = query.or_(f"patient_name.ilike.%{s}%,patient_phone.ilike.%{s}%")
        
    try:
        res = query.execute()
        return {"data": res.data, "meta": {"page": page, "limit": limit, "total": res.count}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/today")
async def get_today_appointments(auth: AuthenticatedUser = Depends(require_permission("appointments:read"))):
    clinic_id = auth.clinic_id
    now = datetime.datetime.now()
    today_start = datetime.datetime(now.year, now.month, now.day).isoformat()
    today_end = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(days=1)
    
    try:
        res = supabase_read.table("appointments").select(
            "id, patient_id, patient_name, patient_phone, appointment_type, datetime, duration_minutes, status, booked_by, reminder_sent, noshow_risk, notes"
        ).eq("clinic_id", clinic_id).gte("datetime", today_start).lt("datetime", today_end.isoformat()).order("datetime", desc=False).execute()
        
        return {"data": res.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("", status_code=201)
async def create_appointment(appt: AppointmentCreate, request: Request, auth: AuthenticatedUser = Depends(require_permission("appointments:write"))):
    clinic_id = auth.clinic_id
    try:
        # Create Google Calendar Event
        cal_res = await calendar_service.create_event(clinic_id, appt.model_dump(exclude_none=True))
        google_event_id = cal_res["data"]["googleEventId"] if cal_res.get("success") else None
        
        # Resolve or create patient in patients table to guarantee patient_id foreign key
        patient_id = appt.patient_id
        if not patient_id and appt.patient_phone:
            try:
                pat_check = supabase_read.table("patients").select("id").eq("clinic_id", clinic_id).eq("phone", appt.patient_phone).execute()
                if pat_check.data:
                    patient_id = pat_check.data[0]["id"]
                else:
                    import uuid
                    new_pat_id = str(uuid.uuid4())
                    supabase.table("patients").insert({
                        "id": new_pat_id,
                        "clinic_id": clinic_id,
                        "name": appt.patient_name,
                        "phone": appt.patient_phone,
                        "email": "patient@clinic.com"
                    }).execute()
                    patient_id = new_pat_id
            except Exception as pat_err:
                print(f"[AppointmentsRouter] Patient resolution note: {pat_err}")

        # Resolve duration, fee, and CPT code from clinic appointment_types if available
        fee_cents = None
        cpt_code = None
        try:
            clinic_res = supabase_read.table("clinics").select("appointment_types").eq("id", clinic_id).single().execute()
            if clinic_res.data and clinic_res.data.get("appointment_types"):
                req_t = (appt.appointment_type or "").strip().lower()
                for at in clinic_res.data["appointment_types"]:
                    if isinstance(at, dict):
                        at_name = str(at.get("name", "")).strip().lower()
                        if at_name == req_t or req_t in at_name or at_name in req_t:
                            fee = at.get("fee") if at.get("fee") is not None else at.get("price")
                            if fee is not None:
                                fee_cents = int(float(fee) * 100)
                            if at.get("duration_minutes") and (not appt.duration_minutes or appt.duration_minutes == 30):
                                appt.duration_minutes = int(at.get("duration_minutes"))
                            if at.get("cpt_code"):
                                cpt_code = at.get("cpt_code")
                            break
        except Exception as e:
            print(f"[AppointmentsRouter] Appointment type resolution note: {e}")

        final_notes = appt.notes or ""
        if cpt_code and f"CPT: {cpt_code}" not in final_notes:
            final_notes = f"{final_notes} [CPT: {cpt_code}]".strip()

        insert_data = {
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "patient_name": appt.patient_name,
            "patient_phone": appt.patient_phone,
            "doctor_name": appt.doctor_name or "Dr. Sarah Jenkins",
            "provider_id": appt.provider_id or appt.doctor_id,
            "appointment_type": appt.appointment_type,
            "datetime": appt.datetime,
            "duration_minutes": appt.duration_minutes,
            "google_event_id": google_event_id,
            "status": "scheduled",
            "booked_by": "staff",
            "notes": final_notes or None
        }
        if fee_cents is not None:
            insert_data["revenue_amount"] = fee_cents
        
        res = supabase.table("appointments").insert(insert_data).execute()
        created_appt = res.data[0]
        
        # Trigger automatic background EHR sync
        from ...services.ehr.sync_service import ehr_sync_service
        import asyncio
        asyncio.create_task(ehr_sync_service.sync_appointment(clinic_id, created_appt.get("id")))

        # Instant SMS Confirmation via Telnyx / Outbox
        from ...services.sms_service import sms_service
        if appt.send_confirmation_sms and appt.patient_phone:
            async def _send_sms_async():
                try:
                    await sms_service.send_booking_confirmation(
                        clinic_id=clinic_id,
                        phone=appt.patient_phone,
                        time_str=appt.datetime,
                        patient_name=appt.patient_name,
                        appointment_id=created_appt.get("id")
                    )
                except Exception as sms_err:
                    pass
            asyncio.create_task(_send_sms_async())
        
        # Audit log creation
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="appointment.create",
            resource_type="appointment",
            resource_id=created_appt.get("id"),
            details=insert_data,
            request=request
        )

        # Real-time notification
        await notification_service.create(
            clinic_id=clinic_id,
            notification_type="appointment.booked",
            title="New Appointment Booked",
            body=f"{appt.patient_name} — {appt.appointment_type} on {appt.datetime[:10]}",
            metadata={"booked_by": "staff", "patient_name": appt.patient_name},
            resource_type="appointment",
            resource_id=created_appt.get("id"),
        )

        # Invalidate dashboard stats cache
        from ...core.cache import invalidate_dashboard_stats
        invalidate_dashboard_stats(clinic_id)

        # Broadcast WebSocket APPOINTMENT_ADDED event to live dashboard and calendar
        try:
            from src.ws.manager import tenant_room_manager, WebSocketEvent
            import asyncio
            asyncio.create_task(tenant_room_manager.broadcast_event(
                str(clinic_id),
                WebSocketEvent.APPOINTMENT_ADDED,
                created_appt
            ))
        except Exception as ws_err:
            pass

        return {"data": created_appt}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{id}")
async def update_appointment(id: str, updates: AppointmentUpdate, request: Request, auth: AuthenticatedUser = Depends(require_permission("appointments:write"))):
    clinic_id = auth.clinic_id
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
        
    if update_data.get("status") == "confirmed":
        update_data["confirmed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
    try:
        # Fetch current record before updating for audit diff tracking
        existing_res = supabase_read.table("appointments").select("*").eq("id", id).eq("clinic_id", clinic_id).execute()
        existing_data = existing_res.data[0] if existing_res.data else {}
        
        res = supabase.table("appointments").update(update_data).eq("id", id).eq("clinic_id", clinic_id).execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail="Appointment not found")
            
        data = res.data[0]
        
        # Audit log update with before and after diff payload
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="appointment.update",
            resource_type="appointment",
            resource_id=id,
            details={
                "before": {k: existing_data.get(k) for k in update_data.keys() if k in existing_data},
                "after": update_data
            },
            request=request
        )
        
        # If completed, update patient stats
        if update_data.get("status") == "completed" and data.get("patient_id"):
            pat_res = supabase_read.table("patients").select("total_visits").eq("id", data["patient_id"]).execute()
            current_visits = pat_res.data[0].get("total_visits", 0) if pat_res.data else 0
            visit_date = data["datetime"][:10]
            
            supabase.table("patients").update({
                "last_visit_date": visit_date,
                "total_visits": current_visits + 1
            }).eq("id", data["patient_id"]).eq("clinic_id", clinic_id).execute()
            
        # If cancelled, fire notification & trigger instant waitlist fill-in & cancel Google Calendar event
        if update_data.get("status") == "cancelled":
            if existing_data.get("google_event_id"):
                import asyncio
                asyncio.create_task(calendar_service.cancel_event(clinic_id, existing_data["google_event_id"]))

            await notification_service.create(
                clinic_id=clinic_id,
                notification_type="appointment.cancelled",
                title="Appointment Cancelled",
                body=f"{existing_data.get('patient_name', 'Patient')} — {existing_data.get('appointment_type', '')} on {existing_data.get('datetime', '')[:10]}",
                resource_type="appointment",
                resource_id=id,
            )

            # Trigger automated waitlist fill-in
            from ...services.waitlist_service import waitlist_service
            import asyncio
            async def _fill_waitlist():
                try:
                    candidates = await waitlist_service.get_waitlist_candidates(clinic_id, page=1, limit=1)
                    if candidates.get("success") and candidates.get("data"):
                        top_wl = candidates["data"][0]
                        await waitlist_service.offer_slot(clinic_id, top_wl["id"], existing_data.get("datetime", ""))
                except Exception as wl_err:
                    pass
            asyncio.create_task(_fill_waitlist())

        # If no-show detected
        if update_data.get("status") == "no_show":
            await notification_service.create(
                clinic_id=clinic_id,
                notification_type="noshow.detected",
                title="No-Show Detected",
                body=f"{existing_data.get('patient_name', 'Patient')} did not show for their {existing_data.get('appointment_type', 'appointment')}.",
                resource_type="appointment",
                resource_id=id,
            )

        # Invalidate dashboard stats cache
        from ...core.cache import invalidate_dashboard_stats
        invalidate_dashboard_stats(clinic_id)

        # Broadcast WebSocket APPOINTMENT_CANCELLED or APPOINTMENT_UPDATED event
        try:
            from src.ws.manager import tenant_room_manager, WebSocketEvent
            import asyncio
            event_type = WebSocketEvent.APPOINTMENT_CANCELLED if update_data.get("status") == "cancelled" else WebSocketEvent.APPOINTMENT_UPDATED
            asyncio.create_task(tenant_room_manager.broadcast_event(
                str(clinic_id),
                event_type,
                data
            ))
        except Exception as ws_err:
            pass

        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
async def export_appointments_csv(
    auth: AuthenticatedUser = Depends(require_permission("appointments:read"))
):
    """
    Export appointments as CSV — GET /api/v1/appointments/export
    """
    import io
    import csv
    import asyncio
    from fastapi.responses import StreamingResponse
    clinic_id = auth.clinic_id
    try:
        # Fetch appointments from database
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
            .select("id, patient_name, patient_phone, appointment_type, datetime, status, booked_by, revenue_amount, created_at")
            .eq("clinic_id", clinic_id)
            .execute()
        )
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Appointment ID", "Patient Name", "Patient Phone", "Type", "Date/Time", "Status", "Booked By", "Revenue Cents", "Created At"])
        
        for row in (res.data or []):
            writer.writerow([
                row.get("id"), row.get("patient_name"), row.get("patient_phone"), 
                row.get("appointment_type"), row.get("datetime"), row.get("status"), 
                row.get("booked_by"), row.get("revenue_amount"), row.get("created_at")
            ])
            
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=appointments.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

