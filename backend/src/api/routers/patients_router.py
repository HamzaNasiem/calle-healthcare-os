from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from typing import Optional
import datetime

from ...core.database import supabase, supabase_read
from ...core.security import require_permission, AuthenticatedUser, require_active_subscription, validate_phone_format
from ...services.recall_service import recall_service
from ...services.sms_service import sms_service
from ...services.audit_service import audit_service

router = APIRouter(prefix="/patients", tags=["Patients"], dependencies=[Depends(require_active_subscription)])

class PatientCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_time: Optional[str] = "morning"
    is_vip: Optional[bool] = False
    notes: Optional[str] = None
    language_preference: Optional[str] = "en"

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        validate_phone_format(v)
        return v

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_time: Optional[str] = None
    is_vip: Optional[bool] = None
    notes: Optional[str] = None
    recall_opted_out: Optional[bool] = None
    language_preference: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v:
            validate_phone_format(v)
        return v

class PatientMessage(BaseModel):
    message: str

class PhiRevealResponse(BaseModel):
    id: str
    phone: str
    date_of_birth: Optional[str] = None
    insurance_member_id: Optional[str] = None
    email: Optional[str] = None

@router.get("")
async def get_patients(
    auth: AuthenticatedUser = Depends(require_permission("patients:read")),
    page: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=500),
    cursor: Optional[str] = None,
    search: Optional[str] = None
):
    clinic_id = auth.clinic_id
    
    query = supabase_read.table("patients").select(
        "id, name, phone, email, date_of_birth, insurance_provider, insurance_member_id, last_visit_date, total_visits, no_show_count, recall_opted_out, is_vip, created_at",
        count="exact"
    ).eq("clinic_id", clinic_id).order("created_at", desc=True)
    
    if search:
        search_term = search.strip()
        query = query.or_(f"name.ilike.%{search_term}%,phone.ilike.%{search_term}%,insurance_member_id.ilike.%{search_term}%")
        
    if cursor:
        query = query.lt("created_at", cursor).limit(limit)
    elif page is not None:
        offset = (page - 1) * limit
        query = query.range(offset, offset + limit - 1)
    else:
        query = query.limit(limit)
        
    try:
        res = query.execute()
        next_cursor = res.data[-1]["created_at"] if len(res.data) == limit else None
        
        meta = {
            "limit": limit,
            "total": res.count
        }
        if page is not None:
            meta["page"] = page
        if next_cursor:
            meta["next_cursor"] = next_cursor
            
        return {"data": res.data, "meta": meta}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/recall-candidates")
async def get_recall_candidates(auth: AuthenticatedUser = Depends(require_permission("patients:read"))):
    clinic_id = auth.clinic_id
    try:
        res = await recall_service.get_recall_candidates(clinic_id)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error"))
        return {"data": res.get("data")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/recall/{id}")
@router.post("/{id}/trigger-recall")
async def trigger_recall(id: str, request: Request, auth: AuthenticatedUser = Depends(require_permission("patients:write"))):
    clinic_id = auth.clinic_id
    try:
        res = await recall_service.initiate_recall(clinic_id, id)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error"))
            
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="patient.trigger_recall",
            resource_type="patient",
            resource_id=id,
            request=request
        )
        return {"data": res.get("data")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id}/reveal-phi", response_model=PhiRevealResponse)
async def reveal_patient_phi(
    id: str,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("patients:read"))
):
    """HIPAA Audit-logged PHI Reveal Endpoint."""
    clinic_id = auth.clinic_id
    pat_res = supabase_read.table("patients").select("*").eq("id", id).eq("clinic_id", clinic_id).execute()
    if not pat_res.data:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = pat_res.data[0]

    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="patient.reveal_phi",
        resource_type="patient",
        resource_id=id,
        details={"revealed_fields": ["phone", "date_of_birth", "insurance_member_id", "email"]},
        request=request
    )

    return PhiRevealResponse(
        id=patient["id"],
        phone=patient.get("phone", ""),
        date_of_birth=patient.get("date_of_birth"),
        insurance_member_id=patient.get("insurance_member_id"),
        email=patient.get("email")
    )

@router.get("/{id}")
async def get_patient(id: str, auth: AuthenticatedUser = Depends(require_permission("patients:read"))):
    clinic_id = auth.clinic_id
    try:
        pat_res = supabase_read.table("patients").select("*").eq("id", id).eq("clinic_id", clinic_id).execute()
        if not pat_res.data:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        patient = pat_res.data[0]
        
        appt_res = supabase_read.table("appointments").select("id, appointment_type, datetime, status, booked_by, revenue_amount, notes").eq("clinic_id", clinic_id).eq("patient_id", id).order("datetime", desc=True).limit(50).execute()
        call_res = supabase_read.table("calls").select("id, direction, call_type, duration_seconds, outcome, started_at, transcript").eq("clinic_id", clinic_id).eq("patient_id", id).order("started_at", desc=True).limit(50).execute()
        sms_res = supabase_read.table("sms_messages").select("id, direction, sms_type, body, status, created_at, reply_sentiment").eq("clinic_id", clinic_id).eq("patient_id", id).order("created_at", desc=True).limit(50).execute()
        
        try:
            # Query prior auth requests by tenant_id (or clinic_id)
            pa_res = supabase_read.table("prior_auth_requests").select("id, cpt_code, cpt_description, urgency, auth_status, call_status, denial_reason, requested_service_date, created_at").eq("tenant_id", clinic_id).eq("patient_id", id).order("created_at", desc=True).limit(50).execute()
            prior_auths = pa_res.data or []
        except Exception:
            prior_auths = []
        
        return {
            "data": {
                "patient": patient,
                "appointments": appt_res.data or [],
                "calls": call_res.data or [],
                "smsMessages": sms_res.data or [],
                "priorAuths": prior_auths
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("", status_code=201)
async def create_patient(pat: PatientCreate, request: Request, auth: AuthenticatedUser = Depends(require_permission("patients:write"))):
    clinic_id = auth.clinic_id
    try:
        insert_data = pat.model_dump(exclude_none=True)
        insert_data["clinic_id"] = clinic_id
        res = supabase.table("patients").insert(insert_data).execute()
        created_patient = res.data[0]
        
        # Trigger automatic background EHR sync
        from ...services.ehr.sync_service import ehr_sync_service
        import asyncio
        asyncio.create_task(ehr_sync_service.sync_patient(clinic_id, created_patient.get("id")))
        
        # Audit log creation
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="patient.create",
            resource_type="patient",
            resource_id=created_patient.get("id"),
            details=insert_data,
            request=request
        )
        return {"data": created_patient}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{id}")
async def update_patient(id: str, updates: PatientUpdate, request: Request, auth: AuthenticatedUser = Depends(require_permission("patients:write"))):
    clinic_id = auth.clinic_id
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
        
    try:
        # Fetch current record before updating for audit diff tracking
        existing_res = supabase_read.table("patients").select("*").eq("id", id).eq("clinic_id", clinic_id).execute()
        existing_data = existing_res.data[0] if existing_res.data else {}
        
        res = supabase.table("patients").update(update_data).eq("id", id).eq("clinic_id", clinic_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        data = res.data[0]
        
        # Audit log update with before and after diff payload
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="patient.update",
            resource_type="patient",
            resource_id=id,
            details={
                "before": {k: existing_data.get(k) for k in update_data.keys() if k in existing_data},
                "after": update_data
            },
            request=request
        )
        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{id}/language")
async def update_patient_language(
    id: str,
    body: dict,
    auth: AuthenticatedUser = Depends(require_permission("patients:write"))
):
    """
    Update patient language preference.
    Body: {"language": "en" | "es"}
    """
    language = body.get("language", "en")
    if language not in ["en", "es"]:
        raise HTTPException(status_code=400, detail="Language must be 'en' or 'es'")
    clinic_id = auth.clinic_id
    try:
        import asyncio
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("patients")
                .update({"language_preference": language})
                .eq("id", id)
                .eq("clinic_id", clinic_id)
                .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Patient not found")
        return {"data": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id}/message", status_code=201)
async def send_manual_message(id: str, msg: PatientMessage, request: Request, auth: AuthenticatedUser = Depends(require_permission("patients:write"))):
    clinic_id = auth.clinic_id
    msg_text = msg.message.strip()
    if not msg_text:
        raise HTTPException(status_code=400, detail="message is required")
        
    try:
        pat_res = supabase_read.table("patients").select("id, name, phone").eq("id", id).eq("clinic_id", clinic_id).execute()
        if not pat_res.data:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        patient = pat_res.data[0]
        
        sms_res = await sms_service.send(
            clinic_id=clinic_id,
            to=patient["phone"],
            body=msg_text,
            sms_type="manual",
            patient_id=patient["id"]
        )
        
        if not sms_res.get("success"):
            raise HTTPException(status_code=500, detail="Failed to send SMS")
            
        # Audit log manual message
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="patient.send_message",
            resource_type="patient",
            resource_id=id,
            details={"message_length": len(msg_text)},
            request=request
        )
        
        return {"data": sms_res}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
async def export_patients_csv(
    auth: AuthenticatedUser = Depends(require_permission("patients:read"))
):
    """
    Export patient data as CSV — GET /api/v1/patients/export
    """
    import io
    import csv
    import asyncio
    from fastapi.responses import StreamingResponse
    clinic_id = auth.clinic_id
    try:
        # Fetch patients from database
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("patients")
            .select("id, name, email, phone, created_at, total_revenue_generated, is_vip, churn_risk_score")
            .eq("clinic_id", clinic_id)
            .execute()
        )
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Patient ID", "Name", "Email", "Phone", "Created At", "LTV Revenue", "VIP", "Churn Risk"])
        
        for row in (res.data or []):
            writer.writerow([
                row.get("id"), row.get("name"), row.get("email"), row.get("phone"), 
                row.get("created_at"), row.get("total_revenue_generated"), row.get("is_vip"), row.get("churn_risk_score")
            ])
            
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=patients.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id}")
async def delete_patient(
    id: str,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("patients:delete"))
):
    """
    HIPAA-compliant Patient Deletion.
    Cascades and securely deletes all associated calls, SMS messages, appointments, waitlist offers, and the patient profile.
    """
    clinic_id = auth.clinic_id
    try:
        # Check if patient exists
        pat_res = supabase_read.table("patients").select("id, name").eq("id", id).eq("clinic_id", clinic_id).execute()
        if not pat_res.data:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        # 1. Delete SMS messages
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("sms_messages").delete().eq("patient_id", id).eq("clinic_id", clinic_id).execute()
        )
        
        # 2. Delete calls
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("calls").delete().eq("patient_id", id).eq("clinic_id", clinic_id).execute()
        )
        
        # 3. Delete appointments
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("appointments").delete().eq("patient_id", id).eq("clinic_id", clinic_id).execute()
        )
        
        # 4. Delete waitlist entries
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("waitlist").delete().eq("patient_id", id).eq("clinic_id", clinic_id).execute()
        )
        
        # 5. Delete patient profile itself
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("patients").delete().eq("id", id).eq("clinic_id", clinic_id).execute()
        )
        
        # Log audit entry
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="patient.delete",
            resource_type="patient",
            resource_id=id,
            details={"patient_name": pat_res.data[0]["name"]},
            request=request
        )
        
        return {"success": True, "message": "Patient and all related HIPAA records deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

