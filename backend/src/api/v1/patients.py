import math
import uuid
import re
import hashlib
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_current_user_with_role, require_permission
from src.db.engine import get_db
from src.models.appointment import Appointment
from src.models.call_log import CallLog
from src.models.clinical_note import ClinicalNote
from src.models.patient import Patient
from src.models.prior_auth_request import PriorAuthRequest
from src.models.user import User
from src.schemas.patient import (
    PaginationMeta,
    PatientAppointmentItem,
    PatientAppointmentsData,
    PatientAppointmentsResponse,
    PatientCallLogItem,
    PatientCallLogsData,
    PatientCallLogsResponse,
    PatientClinicalNoteItem,
    PatientClinicalNotesData,
    PatientClinicalNotesResponse,
    PatientDetailData,
    PatientDetailResponse,
    PatientListResponse,
    PatientListResponseData,
    PatientPriorAuthItem,
    PatientPriorAuthsData,
    PatientPriorAuthsResponse,
    PatientCreateRequest,
    PatientCreateResponse,
    PatientCreateResponseData,
    PatientUpdateRequest,
    PhiRevealRequest,
    PhiRevealResponse,
    PhiRevealData,
)
from src.services.audit_service import audit_service
from src.services.recall_service import recall_service
from src.services.sms_service import sms_service

router = APIRouter(prefix="/patients", tags=["patients"])


def mask_phi(user: User, field_name: str, value: Optional[str]) -> Optional[str]:
    """Mask sensitive PHI for unprivileged staff while preserving data for clinicians/owners."""
    if not value:
        return value

    if user.role in ["owner", "clinician", "admin"]:
        return value

    if field_name == "full_name":
        parts = value.split(" ")
        masked_parts = [f"{p[0]}{'*' * (len(p)-1)}" if len(p) > 1 else p for p in parts if p]
        return " ".join(masked_parts)
    elif field_name == "phone":
        clean = re.sub(r"\D", "", value)
        if len(clean) >= 4:
            return f"***-***-{clean[-4:]}"
        return "****"
    elif field_name == "dob":
        parts = value.split("-")
        if len(parts) == 3:
            return f"****-**-{parts[2]}"
        return "****-**-**"
    elif field_name == "email":
        if "@" in value:
            name, domain = value.split("@", 1)
            masked_name = name[0] + "***" if len(name) > 0 else "***"
            return f"{masked_name}@{domain}"
        return "***@***"
    elif field_name == "insurance_member_id":
        if len(value) >= 4:
            return f"***{value[-4:]}"
        return "****"
    return "***"


@router.get("", response_model=PatientListResponse)
async def list_patients(
    search: Optional[str] = None,
    recall_status: Optional[str] = Query(None, description="Filter by recall status tag: all, up_to_date, due_for_recall, overdue_60d, exempt"),
    is_existing: Optional[bool] = None,
    is_vip: Optional[bool] = None,
    sort_by: str = Query("created_at", pattern="^(last_visit_date|visit_count|created_at|full_name)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """
    List patients with search over encrypted attributes (Name, Phone, Member ID),
    recall status calculation, and strict HIPAA access control.
    """
    base_stmt = select(Patient).where(
        Patient.is_deleted == False,
        Patient.tenant_id == user.tenant_id
    )
    
    if is_existing is not None:
        base_stmt = base_stmt.where(Patient.is_existing_patient == is_existing)
    if is_vip is not None:
        base_stmt = base_stmt.where(Patient.is_vip == is_vip)

    # Search & dynamic recall status filtering require decrypting patient records
    # Fetch bounded candidate set (max 2000) for fast Python filtering
    if search or (recall_status and recall_status != "all"):
        res = await db.execute(base_stmt.limit(2000))
        all_patients = list(res.scalars().all())
        
        filtered = []
        search_lower = search.strip().lower() if search else None

        for p in all_patients:
            p_name = p.full_name or ""
            p_phone = p.phone or ""
            p_member_id = p.insurance_member_id or ""
            p_recall = p.calculate_recall_status()

            # Search filter (name, phone, member ID)
            if search_lower:
                phone_clean = re.sub(r"\D", "", p_phone)
                search_digits = re.sub(r"\D", "", search_lower)
                matches_search = (
                    search_lower in p_name.lower() or
                    (search_digits and search_digits in phone_clean) or
                    search_lower in p_member_id.lower()
                )
                if not matches_search:
                    continue

            # Recall status filter
            if recall_status and recall_status != "all":
                if recall_status == "overdue_60d" and p_recall != "overdue_60d":
                    continue
                elif recall_status == "due_for_recall" and p_recall not in ["due_for_recall", "overdue_60d"]:
                    continue
                elif recall_status == "up_to_date" and p_recall != "up_to_date":
                    continue
                elif recall_status == "exempt" and p_recall != "exempt":
                    continue

            filtered.append(p)

        total = len(filtered)
        
        # Sort in Python
        reverse = (sort_dir == "desc")
        if sort_by == "last_visit_date":
            filtered.sort(key=lambda x: x.last_visit_date or datetime.date.min, reverse=reverse)
        elif sort_by == "visit_count":
            filtered.sort(key=lambda x: x.visit_count or 0, reverse=reverse)
        elif sort_by == "full_name":
            filtered.sort(key=lambda x: (x.full_name or "").lower(), reverse=reverse)
        else:
            min_dt = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            filtered.sort(key=lambda x: x.created_at or min_dt, reverse=reverse)
        
        start_idx = (page - 1) * per_page
        paginated_patients = filtered[start_idx:start_idx + per_page]

    else:
        # No text search / recall filter — DB-level pagination
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        if sort_by == "last_visit_date":
            order_col = Patient.last_visit_date
        elif sort_by == "visit_count":
            order_col = Patient.visit_count
        else:
            order_col = Patient.created_at

        from sqlalchemy import desc as sql_desc, asc as sql_asc
        order_func = sql_desc if sort_dir == "desc" else sql_asc

        data_stmt = base_stmt.order_by(order_func(order_col)).limit(per_page).offset((page - 1) * per_page)
        res = await db.execute(data_stmt)
        paginated_patients = list(res.scalars().all())

    out_patients = [
        PatientListResponseData(
            id=p.id,
            full_name=mask_phi(user, "full_name", p.full_name) or "Unknown Patient",
            phone=mask_phi(user, "phone", p.phone) or "—",
            dob=mask_phi(user, "dob", p.dob),
            age=p.age,
            insurance_provider=p.insurance_provider or None,
            insurance_member_id=mask_phi(user, "insurance_member_id", p.insurance_member_id),
            is_existing_patient=p.is_existing_patient,
            visit_count=p.visit_count,
            last_visit_date=p.last_visit_date,
            recall_status=p.calculate_recall_status(),
            recall_opted_out=p.recall_opted_out,
            is_vip=p.is_vip,
            created_at=p.created_at
        )
        for p in paginated_patients
    ]

    return PatientListResponse(
        success=True,
        data={"patients": out_patients},
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=math.ceil(total / per_page) if total > 0 else 1
        )
    )


@router.get("/{id}", response_model=PatientDetailResponse)
async def get_patient_detail(
    id: uuid.UUID,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """Get full profile details for a patient."""
    stmt = select(Patient).where(Patient.id == id, Patient.is_deleted == False)
    res = await db.execute(stmt)
    p = res.scalar_one_or_none()

    if not p or p.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Calculate patient lifetime revenue dynamically
    pat_appts_stmt = select(Appointment).where(
        Appointment.patient_id == p.id,
        Appointment.is_deleted == False,
        Appointment.status == "completed"
    )
    pat_appts_res = await db.execute(pat_appts_stmt)
    pat_appts = pat_appts_res.scalars().all()

    total_rev_cents = sum(15000 for _ in pat_appts)
    if p.total_revenue_cents != total_rev_cents and total_rev_cents > 0:
        p.total_revenue_cents = total_rev_cents
        await db.commit()

    # Audit log read access
    await audit_service.log(
        action="READ",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="patients",
        target_id=p.id,
        target_patient_id=p.id,
        ingress_ip="internal",
        change_reason="Viewed patient profile"
    )

    return PatientDetailResponse(
        success=True,
        data=PatientDetailData(
            id=p.id,
            full_name=mask_phi(user, "full_name", p.full_name) or "Unknown Patient",
            phone=mask_phi(user, "phone", p.phone) or "—",
            email=mask_phi(user, "email", p.email),
            dob=mask_phi(user, "dob", p.dob),
            age=p.age,
            insurance_provider=p.insurance_provider or None,
            insurance_member_id=mask_phi(user, "insurance_member_id", p.insurance_member_id),
            preferred_time=p.preferred_time or "morning",
            recall_opted_out=p.recall_opted_out,
            recall_status=p.calculate_recall_status(),
            notes=p.notes if user.role in ["owner", "clinician", "admin"] else None,
            is_existing_patient=p.is_existing_patient,
            visit_count=p.visit_count,
            last_visit_date=p.last_visit_date,
            total_revenue_cents=p.total_revenue_cents,
            is_vip=p.is_vip,
            data_access_level="full" if user.role in ["owner", "clinician", "admin"] else "masked",
            created_at=p.created_at
        )
    )


@router.get("/{id}/appointments", response_model=PatientAppointmentsResponse)
async def get_patient_appointments(
    id: uuid.UUID,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve appointment history for the specified patient."""
    patient_stmt = select(Patient).where(Patient.id == id, Patient.is_deleted == False)
    p_res = await db.execute(patient_stmt)
    patient = p_res.scalar_one_or_none()
    if not patient or patient.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Patient not found")

    stmt = select(Appointment).where(
        Appointment.patient_id == id,
        Appointment.is_deleted == False
    ).order_by(Appointment.slot_start.desc())

    res = await db.execute(stmt)
    appts = res.scalars().all()

    out = [
        PatientAppointmentItem(
            id=a.id,
            slot_start=a.slot_start,
            slot_end=a.slot_end,
            status=a.status,
            service_type=a.service_type or "General Evaluation"
        )
        for a in appts
    ]

    return PatientAppointmentsResponse(
        success=True,
        data=PatientAppointmentsData(appointments=out)
    )


@router.get("/{id}/call-logs", response_model=PatientCallLogsResponse)
async def get_patient_call_logs(
    id: uuid.UUID,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve communication and voice AI call logs for the patient."""
    patient_stmt = select(Patient).where(Patient.id == id, Patient.is_deleted == False)
    p_res = await db.execute(patient_stmt)
    patient = p_res.scalar_one_or_none()
    if not patient or patient.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Patient not found")

    stmt = select(CallLog).where(
        CallLog.patient_id == id
    ).order_by(CallLog.created_at.desc())

    res = await db.execute(stmt)
    calls = res.scalars().all()

    out = [
        PatientCallLogItem(
            id=c.id,
            created_at=c.created_at,
            duration_seconds=c.duration_seconds or 0,
            outcome=c.outcome or "completed",
            has_transcript=bool(c.transcript),
            call_type=getattr(c, "call_type", "recall"),
            direction=getattr(c, "direction", "outbound")
        )
        for c in calls
    ]

    return PatientCallLogsResponse(
        success=True,
        data=PatientCallLogsData(call_logs=out)
    )


@router.get("/{id}/prior-auths", response_model=PatientPriorAuthsResponse)
async def get_patient_prior_auths(
    id: uuid.UUID,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve prior authorization history for the patient."""
    patient_stmt = select(Patient).where(Patient.id == id, Patient.is_deleted == False)
    p_res = await db.execute(patient_stmt)
    patient = p_res.scalar_one_or_none()
    if not patient or patient.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Patient not found")

    stmt = select(PriorAuthRequest).where(
        PriorAuthRequest.patient_id == id,
        PriorAuthRequest.is_deleted == False
    ).order_by(PriorAuthRequest.created_at.desc())

    res = await db.execute(stmt)
    auths = res.scalars().all()

    out = [
        PatientPriorAuthItem(
            id=a.id,
            cpt_code=a.cpt_code,
            cpt_description=a.cpt_description,
            urgency=a.urgency or "standard",
            auth_status=a.auth_status or "pending",
            calle_task_id=a.calle_task_id,
            call_status=a.call_status or "pending",
            requested_service_date=a.requested_service_date,
            denial_reason=a.denial_reason,
            authorization_number=a.authorization_number if user.role in ["owner", "clinician", "admin"] else mask_phi(user, "insurance_member_id", a.authorization_number),
            created_at=a.created_at
        )
        for a in auths
    ]

    return PatientPriorAuthsResponse(
        success=True,
        data=PatientPriorAuthsData(prior_auths=out)
    )


@router.get("/{id}/clinical-notes", response_model=PatientClinicalNotesResponse)
async def get_patient_clinical_notes(
    id: uuid.UUID,
    user: User = Depends(require_permission(["owner", "clinician", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve confidential clinical notes for the patient."""
    patient_stmt = select(Patient).where(Patient.id == id, Patient.is_deleted == False)
    p_res = await db.execute(patient_stmt)
    patient = p_res.scalar_one_or_none()
    if not patient or patient.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Patient not found")

    stmt = select(ClinicalNote).where(
        ClinicalNote.patient_id == id,
        ClinicalNote.is_deleted == False
    ).order_by(ClinicalNote.created_at.desc())

    res = await db.execute(stmt)
    notes = res.scalars().all()

    out = [
        PatientClinicalNoteItem(
            id=n.id,
            created_at=n.created_at,
            authored_by=n.authored_by or "Care Specialist",
            note=n.note
        )
        for n in notes
    ]

    return PatientClinicalNotesResponse(
        success=True,
        data=PatientClinicalNotesData(notes=out)
    )


@router.post("", response_model=PatientCreateResponse, status_code=201)
async def create_patient(
    req: PatientCreateRequest,
    request: Request,
    user: User = Depends(require_permission(["owner", "clinician", "staff", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Register a new patient profile with AES-256 encrypted PHI."""
    # Normalize phone
    phone_clean = re.sub(r"\D", "", req.phone)
    if len(phone_clean) == 10:
        normalized_phone = "+1" + phone_clean
    else:
        normalized_phone = "+" + phone_clean

    phone_hash = hashlib.sha256(normalized_phone.encode("utf-8")).hexdigest()

    # Check for existing patient in tenant
    dup_stmt = select(Patient).where(
        Patient.tenant_id == user.tenant_id,
        Patient.phone_hash == phone_hash,
        Patient.is_deleted == False
    )
    dup_res = await db.execute(dup_stmt)
    if dup_res.scalars().first():
        raise HTTPException(status_code=409, detail="PATIENT_ALREADY_EXISTS: A patient with this phone number already exists.")

    new_patient = Patient(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        phone_hash=phone_hash,
        is_existing_patient=True,
        visit_count=0,
        total_revenue_cents=0,
        is_vip=req.is_vip or False,
        preferred_time=req.preferred_time or "morning",
        recall_opted_out=req.recall_opted_out or False,
        data_access_level=req.data_access_level or "standard"
    )

    # Set encrypted properties
    new_patient.full_name = req.full_name
    new_patient.phone = normalized_phone
    new_patient.dob = req.dob
    new_patient.email = req.email
    new_patient.insurance_provider = req.insurance_provider
    new_patient.insurance_member_id = req.insurance_member_id
    new_patient.notes = req.notes

    db.add(new_patient)
    await db.flush()

    await audit_service.log(
        action="CREATE_PATIENT",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="patients",
        target_id=new_patient.id,
        target_patient_id=new_patient.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason="Registered new patient record",
        outcome="SUCCESS"
    )

    await db.commit()

    return PatientCreateResponse(
        success=True,
        data=PatientCreateResponseData(patient_id=new_patient.id)
    )


@router.put("/{id}", response_model=PatientDetailResponse)
async def update_patient(
    id: uuid.UUID,
    req: PatientUpdateRequest,
    request: Request,
    user: User = Depends(require_permission(["owner", "clinician", "staff", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Update patient demographic and clinical record with audit log."""
    stmt = select(Patient).where(Patient.id == id, Patient.tenant_id == user.tenant_id, Patient.is_deleted == False)
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Update fields
    if req.full_name is not None:
        patient.full_name = req.full_name
    if req.phone is not None:
        phone_clean = re.sub(r"\D", "", req.phone)
        normalized_phone = "+1" + phone_clean if len(phone_clean) == 10 else "+" + phone_clean
        patient.phone = normalized_phone
        patient.phone_hash = hashlib.sha256(normalized_phone.encode("utf-8")).hexdigest()
    if req.email is not None:
        patient.email = req.email
    if req.dob is not None:
        patient.dob = req.dob
    if req.insurance_provider is not None:
        patient.insurance_provider = req.insurance_provider
    if req.insurance_member_id is not None:
        patient.insurance_member_id = req.insurance_member_id
    if req.preferred_time is not None:
        patient.preferred_time = req.preferred_time
    if req.notes is not None:
        patient.notes = req.notes
    if req.recall_opted_out is not None:
        patient.recall_opted_out = req.recall_opted_out
    if req.is_vip is not None:
        patient.is_vip = req.is_vip

    await audit_service.log(
        action="UPDATE_PATIENT",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="patients",
        target_id=patient.id,
        target_patient_id=patient.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason="Updated patient profile details",
        outcome="SUCCESS"
    )

    await db.commit()

    return PatientDetailResponse(
        success=True,
        data=PatientDetailData(
            id=patient.id,
            full_name=mask_phi(user, "full_name", patient.full_name) or "Unknown Patient",
            phone=mask_phi(user, "phone", patient.phone) or "—",
            email=mask_phi(user, "email", patient.email),
            dob=mask_phi(user, "dob", patient.dob),
            age=patient.age,
            insurance_provider=patient.insurance_provider or None,
            insurance_member_id=mask_phi(user, "insurance_member_id", patient.insurance_member_id),
            preferred_time=patient.preferred_time or "morning",
            recall_opted_out=patient.recall_opted_out,
            recall_status=patient.calculate_recall_status(),
            notes=patient.notes if user.role in ["owner", "clinician", "admin"] else None,
            is_existing_patient=patient.is_existing_patient,
            visit_count=patient.visit_count,
            last_visit_date=patient.last_visit_date,
            total_revenue_cents=patient.total_revenue_cents,
            is_vip=patient.is_vip,
            data_access_level="full" if user.role in ["owner", "clinician", "admin"] else "masked",
            created_at=patient.created_at
        )
    )


@router.post("/{id}/trigger-recall")
async def trigger_recall_call(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission(["owner", "clinician", "staff", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Quick Action: Trigger automated recall call via CALL-E Voice AI.
    """
    stmt = select(Patient).where(Patient.id == id, Patient.tenant_id == user.tenant_id, Patient.is_deleted == False)
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if patient.recall_opted_out:
        raise HTTPException(status_code=400, detail="Patient has opted out of automated recall outreach.")

    call_res = await recall_service.initiate_recall(str(user.tenant_id), str(patient.id))

    await audit_service.log(
        action="TRIGGER_RECALL_CALL",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="patients",
        target_id=patient.id,
        target_patient_id=patient.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason="Triggered CALL-E recall voice outreach",
        outcome="SUCCESS" if call_res.get("success") else "FAILED"
    )

    if not call_res.get("success"):
        raise HTTPException(status_code=500, detail=call_res.get("error") or "Failed to initiate CALL-E voice call")

    return {
        "success": True,
        "message": "CALL-E recall voice AI initiated successfully.",
        "data": call_res.get("data")
    }


@router.post("/{id}/message")
async def send_patient_message(
    id: uuid.UUID,
    body: dict,
    request: Request,
    user: User = Depends(require_permission(["owner", "clinician", "staff", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Quick Action: Send SMS link or communication message to patient.
    """
    msg_text = body.get("message", "").strip()
    if not msg_text:
        raise HTTPException(status_code=400, detail="Message text cannot be empty.")

    stmt = select(Patient).where(Patient.id == id, Patient.tenant_id == user.tenant_id, Patient.is_deleted == False)
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    sms_res = await sms_service.send(
        clinic_id=str(user.tenant_id),
        to=patient.phone or "",
        body=msg_text,
        sms_type="manual",
        patient_id=str(patient.id)
    )

    await audit_service.log(
        action="SEND_PATIENT_SMS",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="patients",
        target_id=patient.id,
        target_patient_id=patient.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason=f"Sent patient SMS: {len(msg_text)} chars",
        outcome="SUCCESS" if sms_res.get("success") else "FAILED"
    )

    return {"success": True, "data": sms_res}


@router.post("/{id}/reveal-phi", response_model=PhiRevealResponse)
async def reveal_phi(
    id: uuid.UUID,
    req: PhiRevealRequest,
    request: Request,
    user: User = Depends(require_permission(["owner", "clinician", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Reveal decrypted PHI under strict audit logging and temporary 60-second window.
    """
    stmt = select(Patient).where(Patient.id == id, Patient.tenant_id == user.tenant_id, Patient.is_deleted == False)
    res = await db.execute(stmt)
    patient = res.scalars().first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    audit_log = await audit_service.log(
        action="REVEAL_PHI",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="patients",
        target_id=patient.id,
        target_patient_id=patient.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason=req.reveal_reason,
        is_high_sensitivity=True,
        outcome="SUCCESS"
    )

    reveal_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)

    await db.commit()

    return PhiRevealResponse(
        success=True,
        data=PhiRevealData(
            full_name=patient.full_name or "",
            phone=patient.phone or "",
            dob=patient.dob or "",
            reveal_expires_at=reveal_expires_at,
            audit_log_id=audit_log
        )
    )


@router.delete("/{id}")
async def delete_patient(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission(["owner", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete patient profile and log audit record."""
    stmt = select(Patient).where(Patient.id == id, Patient.tenant_id == user.tenant_id, Patient.is_deleted == False)
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient.is_deleted = True

    await audit_service.log(
        action="DELETE_PATIENT",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="patients",
        target_id=patient.id,
        target_patient_id=patient.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason="Soft deleted patient record under HIPAA retention guidelines",
        outcome="SUCCESS"
    )

    await db.commit()

    return {"success": True, "message": "Patient record deleted successfully."}

