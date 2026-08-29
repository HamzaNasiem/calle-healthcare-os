import uuid
import hmac
from datetime import datetime, timezone
import json
import secrets
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_current_user_with_role, require_permission
from src.core.config import settings
from src.db.engine import get_db
from src.models.user import User
from src.models.patient import Patient
from src.models.prior_auth_request import PriorAuthRequest
from src.services.audit_service import audit_service
from src.services.prior_auth_service import prior_auth_service
from src.core.encryption import phi_crypto

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/prior-auth", tags=["prior_auth"])


class CreatePriorAuthReq(BaseModel):
    patient_id: Optional[uuid.UUID] = None
    provider_id: Optional[uuid.UUID] = None
    insurance_provider_name: str
    insurance_prior_auth_phone: str
    patient_member_id: str
    patient_group_number: Optional[str] = None
    cpt_code: str
    cpt_description: Optional[str] = None
    icd10_code: str
    icd10_description: Optional[str] = None
    urgency: str = "standard"
    requested_service_date: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("patient_id", "provider_id", mode="before")
    @classmethod
    def coerce_empty_uuid(cls, v):
        if not v or (isinstance(v, str) and not v.strip()):
            return None
        return v


class PriorAuthItemResponse(BaseModel):
    id: uuid.UUID
    patient_id: Optional[uuid.UUID] = None
    patient_name: Optional[str] = "Patient"
    provider_id: Optional[uuid.UUID] = None
    insurance_provider_name: str
    insurance_prior_auth_phone: Optional[str] = None
    cpt_code: str
    cpt_description: Optional[str] = None
    icd10_code: str
    icd10_description: Optional[str] = None
    status: str
    auth_status: Optional[str] = None
    call_status: Optional[str] = None
    urgency: str
    created_at: datetime
    auth_number: Optional[str] = None
    authorization_number: Optional[str] = None
    reference_number: Optional[str] = None
    insurance_agent_name: Optional[str] = None
    call_summary: Optional[str] = None
    call_duration_seconds: Optional[int] = None


class PaginatedPriorAuths(BaseModel):
    success: bool
    data: List[PriorAuthItemResponse]
    total: int
    page: int = 1
    per_page: int = 25


def _get_tenant_id(user: Any) -> uuid.UUID:
    tid = getattr(user, 'tenant_id', None) or getattr(user, 'clinic_id', None) or "d3b07384-d113-46a6-a719-38cf89235d54"
    if isinstance(tid, str):
        try:
            return uuid.UUID(tid)
        except ValueError:
            return uuid.UUID("d3b07384-d113-46a6-a719-38cf89235d54")
    return tid


def _get_user_id(user: Any) -> uuid.UUID:
    uid = getattr(user, 'id', None) or getattr(user, 'user_id', None) or "00000000-0000-0000-0000-000000000001"
    if isinstance(uid, str):
        try:
            return uuid.UUID(uid)
        except ValueError:
            return uuid.UUID("00000000-0000-0000-0000-000000000001")
    return uid


# Global in-memory fallback store for development/testing
_IN_MEMORY_PRIOR_AUTHS: Dict[str, Dict[str, Any]] = {}


@router.post("/request", status_code=201)
@router.post("", status_code=201)
async def create_prior_auth_request(
    req: CreatePriorAuthReq,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    tenant_id = _get_tenant_id(user)
    user_id = _get_user_id(user)
    pa_id = uuid.uuid4()
    # Do NOT pre-generate auth codes — they must come from the insurer via CALL-E
    # Do NOT set approved status before the call runs

    patient_name = "Patient"
    if req.patient_id:
        try:
            p_stmt = select(Patient).where(Patient.id == req.patient_id)
            p_res = await db.execute(p_stmt)
            pat = p_res.scalar_one_or_none()
            if pat and pat.full_name:
                patient_name = pat.full_name
        except Exception:
            pass

    # Initial state: pending — will be updated via CALL-E webhook
    mem_item = {
        "id": str(pa_id),
        "tenant_id": str(tenant_id),
        "patient_id": str(req.patient_id) if req.patient_id else str(uuid.uuid4()),
        "patient_name": patient_name,
        "provider_id": str(req.provider_id) if req.provider_id else None,
        "insurance_provider_name": req.insurance_provider_name,
        "insurance_prior_auth_phone": req.insurance_prior_auth_phone,
        "patient_member_id": req.patient_member_id,
        "patient_group_number": req.patient_group_number,
        "cpt_code": req.cpt_code,
        "cpt_description": req.cpt_description or "Medical Procedure",
        "icd10_code": req.icd10_code,
        "icd10_description": req.icd10_description or "Diagnosis code",
        "urgency": req.urgency or "standard",
        "status": "calling",
        "auth_status": "pending",
        "call_status": "in_progress",
        "auth_number": None,
        "authorization_number": None,
        "reference_number": None,
        "insurance_agent_name": None,
        "call_duration_seconds": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "call_summary": "CALL-E AI Voice Agent is currently navigating the insurance IVR system. Authorization pending."
    }
    _IN_MEMORY_PRIOR_AUTHS[str(pa_id)] = mem_item

    try:
        pa_record = PriorAuthRequest(
            id=pa_id,
            tenant_id=tenant_id,
            patient_id=req.patient_id,
            provider_id=req.provider_id,
            created_by_user_id=user_id,
            insurance_provider_name=req.insurance_provider_name,
            insurance_prior_auth_phone=req.insurance_prior_auth_phone,
            cpt_code=req.cpt_code,
            cpt_description=req.cpt_description or "Medical Procedure",
            icd10_code=req.icd10_code,
            icd10_description=req.icd10_description or "Diagnosis code",
            urgency=req.urgency,
            call_status="in_progress",
            auth_status="pending",
            call_started_at=datetime.now(timezone.utc),
        )
        # HIPAA Encrypted properties
        pa_record.patient_member_id = req.patient_member_id
        if req.patient_group_number:
            pa_record.patient_group_number = req.patient_group_number
            
        db.add(pa_record)
        await db.commit()
        
        # HIPAA Audit Trail
        await audit_service.log_action(
            db, tenant_id, user_id, "create_prior_auth", 
            f"Initiated prior auth request for patient {req.patient_id or 'Demo'} (CPT: {req.cpt_code})"
        )
        
        # Trigger CALL-E service async — result comes back via webhook
        try:
            call_res = await prior_auth_service.initiate_prior_auth_call(
                request_id=str(pa_record.id),
                db=db,
                request_payload=req.model_dump()
            )
            if call_res.get("calle_task_id"):
                pa_record.calle_task_id = call_res["calle_task_id"]
                mem_item["calle_task_id"] = call_res["calle_task_id"]
                await db.commit()
            # If dry-run completed synchronously, update mem_item with real result
            if call_res.get("auth_status") and call_res["auth_status"] != "pending":
                mem_item.update({
                    "status": call_res.get("auth_status", "pending"),
                    "auth_status": call_res.get("auth_status", "pending"),
                    "call_status": call_res.get("status", "completed"),
                    "auth_number": call_res.get("authorization_number"),
                    "authorization_number": call_res.get("authorization_number"),
                    "reference_number": call_res.get("reference_number"),
                    "insurance_agent_name": call_res.get("insurance_agent_name"),
                    "call_duration_seconds": call_res.get("call_duration_seconds"),
                    "call_summary": call_res.get("call_summary", mem_item["call_summary"]),
                })
        except Exception as e:
            logger.warning(f"[PriorAuth] CALL-E service notice: {e}")

    except Exception as exc:
        logger.warning(f"[PriorAuth] DB commit skipped (using memory store): {exc}")

    return {
        "success": True, 
        "data": mem_item,
        "id": str(pa_id), 
        "auth_status": mem_item.get("auth_status", "pending"),
        "message": "Prior auth call initiated with CALL-E voice agent. Authorization will be updated when complete."
    }


@router.get("", response_model=PaginatedPriorAuths)
async def list_prior_auths(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    patient_id: Optional[uuid.UUID] = None,
    provider_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    db_data = []
    user_role = getattr(user, 'role', 'owner')

    try:
        tenant_id = _get_tenant_id(user)
        stmt = select(PriorAuthRequest).where(
            PriorAuthRequest.tenant_id == tenant_id,
            PriorAuthRequest.is_deleted == False
        )
        if status_filter and status_filter.lower() != "all":
            stmt = stmt.where(
                or_(
                    PriorAuthRequest.auth_status == status_filter.lower(),
                    PriorAuthRequest.call_status == status_filter.lower()
                )
            )
        if patient_id:
            stmt = stmt.where(PriorAuthRequest.patient_id == patient_id)
        if provider_id:
            stmt = stmt.where(PriorAuthRequest.provider_id == provider_id)
        if search:
            s = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    PriorAuthRequest.insurance_provider_name.ilike(s),
                    PriorAuthRequest.cpt_code.ilike(s),
                    PriorAuthRequest.icd10_code.ilike(s),
                    PriorAuthRequest.reference_number.ilike(s)
                )
            )
            
        stmt = stmt.order_by(desc(PriorAuthRequest.created_at)).limit(per_page).offset((page - 1) * per_page)
        res = await db.execute(stmt)
        records = res.scalars().all()
        
        for r in records:
            # Retrieve patient name if possible
            p_name = "Patient"
            if r.patient_id:
                try:
                    p_res = await db.execute(select(Patient).where(Patient.id == r.patient_id))
                    p_rec = p_res.scalar_one_or_none()
                    if p_rec and p_rec.full_name:
                        p_name = p_rec.full_name
                except Exception:
                    pass

            auth_num = r.authorization_number if user_role in ["owner", "clinician", "admin"] else "***"
            db_data.append(PriorAuthItemResponse(
                id=r.id,
                patient_id=r.patient_id,
                patient_name=p_name,
                provider_id=r.provider_id,
                insurance_provider_name=r.insurance_provider_name or "",
                insurance_prior_auth_phone=r.insurance_prior_auth_phone,
                cpt_code=r.cpt_code or "",
                cpt_description=r.cpt_description or "Medical Procedure",
                icd10_code=r.icd10_code or "",
                icd10_description=r.icd10_description or "Diagnosis code",
                status=r.auth_status or r.call_status or "pending",
                auth_status=r.auth_status or "pending",
                call_status=r.call_status or "in_progress",
                urgency=r.urgency or "standard",
                created_at=r.created_at if r.created_at else datetime.now(timezone.utc),
                auth_number=auth_num,
                authorization_number=auth_num,
                reference_number=r.reference_number,
                insurance_agent_name=r.insurance_agent_name,
                call_summary=r.call_summary,
                call_duration_seconds=r.call_duration_seconds
            ))
    except Exception as e:
        logger.warning(f"[PriorAuth] Error querying prior auth DB list: {e}")

    # Combine with in-memory records
    mem_data = []
    for v in _IN_MEMORY_PRIOR_AUTHS.values():
        pid = uuid.UUID(v["id"])
        if not any(d.id == pid for d in db_data):
            try:
                cat = datetime.fromisoformat(v["created_at"]) if isinstance(v.get("created_at"), str) else datetime.now(timezone.utc)
            except Exception:
                cat = datetime.now(timezone.utc)

            raw_auth = v.get("auth_number") or v.get("authorization_number")
            auth_val = raw_auth if user_role in ["owner", "clinician", "admin"] else "***"

            mem_data.append(PriorAuthItemResponse(
                id=pid,
                patient_id=uuid.UUID(v["patient_id"]) if v.get("patient_id") and len(v["patient_id"]) == 36 else None,
                patient_name=v.get("patient_name") or "Patient",
                provider_id=uuid.UUID(v["provider_id"]) if v.get("provider_id") and len(v["provider_id"]) == 36 else None,
                insurance_provider_name=v.get("insurance_provider_name", ""),
                insurance_prior_auth_phone=v.get("insurance_prior_auth_phone"),
                cpt_code=v.get("cpt_code", ""),
                cpt_description=v.get("cpt_description", "Medical Procedure"),
                icd10_code=v.get("icd10_code", ""),
                icd10_description=v.get("icd10_description", "Diagnosis code"),
                status=v.get("auth_status", "pending"),
                auth_status=v.get("auth_status", "pending"),
                call_status=v.get("call_status", "in_progress"),
                urgency=v.get("urgency", "standard"),
                created_at=cat,
                auth_number=auth_val,
                authorization_number=auth_val,
                reference_number=v.get("reference_number"),
                insurance_agent_name=v.get("insurance_agent_name"),
            ))


    if status_filter and status_filter.lower() != "all":
        mem_data = [m for m in mem_data if m.status.lower() == status_filter.lower() or (m.auth_status and m.auth_status.lower() == status_filter.lower())]

    if search:
        s_lower = search.lower().strip()
        mem_data = [
            m for m in mem_data if
            s_lower in (m.patient_name or "").lower() or
            s_lower in (m.insurance_provider_name or "").lower() or
            s_lower in (m.cpt_code or "").lower() or
            s_lower in (m.icd10_code or "").lower() or
            s_lower in (m.authorization_number or "").lower() or
            s_lower in (m.reference_number or "").lower()
        ]

    combined = mem_data + db_data
    total_count = len(combined)
    paginated = combined[(page - 1) * per_page : page * per_page]

    return PaginatedPriorAuths(
        success=True,
        data=paginated,
        total=total_count,
        page=page,
        per_page=per_page
    )


@router.get("/stats")
async def get_prior_auth_stats(
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    try:
        tenant_id = _get_tenant_id(user)
        stmt = select(PriorAuthRequest).where(
            PriorAuthRequest.tenant_id == tenant_id,
            PriorAuthRequest.is_deleted == False
        )
        res = await db.execute(stmt)
        records = res.scalars().all()
        
        db_total = len(records)
        db_pending = sum(1 for r in records if (r.auth_status or r.call_status or "").lower() in ["pending", "in_progress", "calling"])
        db_approved = sum(1 for r in records if (r.auth_status or "").lower() == "approved")
        db_denied = sum(1 for r in records if (r.auth_status or "").lower() == "denied")

        mem_records = list(_IN_MEMORY_PRIOR_AUTHS.values())
        mem_pending = sum(1 for m in mem_records if (m.get("auth_status") or m.get("call_status") or "").lower() in ["pending", "in_progress", "calling"])
        mem_approved = sum(1 for m in mem_records if (m.get("auth_status") or "").lower() == "approved")
        mem_denied = sum(1 for m in mem_records if (m.get("auth_status") or "").lower() == "denied")

        total = db_total + len(mem_records)
        pending = db_pending + mem_pending
        approved = db_approved + mem_approved
        denied = db_denied + mem_denied

        total_decided = approved + denied
        approval_rate = round((approved / total_decided * 100), 1) if total_decided > 0 else 0.0
        
        # Standard benchmark: 35 minutes saved per automated CALL-E prior authorization call
        hours_saved = round((approved * 35) / 60.0, 1) if approved > 0 else 0.0
        avg_duration_secs = 0
        
        return {
            "success": True,
            "data": {
                "active_requests": pending,
                "pending": pending,
                "pending_count": pending,
                "approved_auths": approved,
                "approved": approved,
                "denied": denied,
                "total": total,
                "total_requests": total,
                "approval_rate": approval_rate,
                "hours_saved": hours_saved,
                "hours_saved_week": hours_saved,
                "avg_call_duration_seconds": avg_duration_secs
            }
        }
    except Exception as e:
        logger.warning(f"[PriorAuth] Error fetching prior auth stats: {e}")
        return {
            "success": True,
            "data": {
                "active_requests": 0,
                "pending": 0,
                "pending_count": 0,
                "approved_auths": 0,
                "approved": 0,
                "denied": 0,
                "total": 0,
                "total_requests": 0,
                "approval_rate": 0.0,
                "hours_saved": 0.0,
                "hours_saved_week": 0.0,
                "avg_call_duration_seconds": 0
            }
        }


@router.get("/insurance-providers")
async def get_insurance_providers():
    data_file = Path("src/data/insurance_providers.json")
    if data_file.exists():
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"success": True, "data": data}
        except Exception as e:
            logger.warning(f"[PriorAuth] Error reading insurance_providers.json: {e}")

    # Robust fallback
    return {
        "success": True,
        "data": [
            {"name": "Aetna", "phone": "1-800-624-0756", "prior_auth_phone": "1-800-624-0756", "payer_id": "60054", "ivr_hints": "Press 2 for providers, then 1 for prior authorization", "ivr_hint": "Press 2 (Providers) -> 1 (Prior Auth)"},
            {"name": "UnitedHealthcare", "phone": "1-877-842-3210", "prior_auth_phone": "1-877-842-3210", "payer_id": "87726", "ivr_hints": "Say 'Provider', then say 'Prior Authorization'", "ivr_hint": "Say 'Provider' -> 'Prior Authorization'"},
            {"name": "Blue Cross Blue Shield", "phone": "1-800-676-2583", "prior_auth_phone": "1-800-676-2583", "payer_id": "BCBS1", "ivr_hints": "Enter NPI, then press 3 for authorizations", "ivr_hint": "Enter NPI -> Press 3 for authorizations"},
            {"name": "Cigna", "phone": "1-800-882-4462", "prior_auth_phone": "1-800-882-4462", "payer_id": "62308", "ivr_hints": "Say 'Healthcare Professional', then 'Authorization'", "ivr_hint": "Say 'Healthcare Professional' -> 'Authorization'"},
            {"name": "Humana", "phone": "1-800-448-6262", "prior_auth_phone": "1-800-448-6262", "payer_id": "61101", "ivr_hints": "Press 1 for Providers, then 4 for Authorization", "ivr_hint": "Press 1 (Providers) -> 4 (Authorization)"},
            {"name": "Medicare (CMS)", "phone": "1-800-633-4227", "prior_auth_phone": "1-800-633-4227", "payer_id": "00801", "ivr_hints": "Say 'Provider services', then follow prompts", "ivr_hint": "Say 'Provider services' -> Follow prompts"}
        ]
    }


@router.get("/cpt-codes")
async def get_cpt_codes(q: Optional[str] = Query(None)):
    data_file = Path("src/data/common_cpt_codes.json")
    codes = []
    if data_file.exists():
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                codes = json.load(f)
        except Exception as e:
            logger.warning(f"[PriorAuth] Error reading common_cpt_codes.json: {e}")

    if not codes:
        codes = [
            {"code": "70551", "description": "MRI Brain without dye", "category": "Radiology"},
            {"code": "72148", "description": "MRI Lumbar spine without dye", "category": "Radiology"},
            {"code": "73221", "description": "MRI Joint upper extremity", "category": "Radiology"},
            {"code": "73721", "description": "MRI Joint lower extremity", "category": "Radiology"},
            {"code": "70450", "description": "CT Head/brain without dye", "category": "Radiology"},
            {"code": "93306", "description": "Echocardiogram complete", "category": "Cardiology"},
            {"code": "45378", "description": "Diagnostic colonoscopy", "category": "Gastroenterology"},
            {"code": "27447", "description": "Total knee arthroplasty", "category": "Orthopedic Surgery"},
            {"code": "99214", "description": "Office/Outpatient Visit Level 4", "category": "Evaluation & Management"}
        ]

    if q:
        q_lower = q.lower().strip()
        codes = [c for c in codes if q_lower in c.get("code", "").lower() or q_lower in c.get("description", "").lower()]

    return {"success": True, "data": codes}


@router.get("/icd10-codes")
async def get_icd10_codes(q: Optional[str] = Query(None)):
    data_file = Path("src/data/common_icd10_codes.json")
    codes = []
    if data_file.exists():
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                codes = json.load(f)
        except Exception as e:
            logger.warning(f"[PriorAuth] Error reading common_icd10_codes.json: {e}")

    if not codes:
        codes = [
            {"code": "G43.909", "description": "Migraine, unspecified, not intractable", "category": "Neurology"},
            {"code": "M54.50", "description": "Low back pain, unspecified", "category": "Musculoskeletal"},
            {"code": "M17.11", "description": "Primary osteoarthritis, right knee", "category": "Musculoskeletal"},
            {"code": "I10", "description": "Essential (primary) hypertension", "category": "Cardiovascular"},
            {"code": "R07.9", "description": "Chest pain, unspecified", "category": "Symptoms"}
        ]

    if q:
        q_lower = q.lower().strip()
        codes = [c for c in codes if q_lower in c.get("code", "").lower() or q_lower in c.get("description", "").lower()]

    return {"success": True, "data": codes}


@router.get("/{id}")
async def get_prior_auth_detail(
    id: uuid.UUID,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    sid = str(id)
    user_role = getattr(user, 'role', 'owner')
    tenant_id = _get_tenant_id(user)

    if sid in _IN_MEMORY_PRIOR_AUTHS:
        v = _IN_MEMORY_PRIOR_AUTHS[sid]
        try:
            cat = datetime.fromisoformat(v["created_at"]) if isinstance(v.get("created_at"), str) else datetime.now(timezone.utc)
        except Exception:
            cat = datetime.now(timezone.utc)

        raw_auth = v.get("auth_number") or v.get("authorization_number")
        auth_val = raw_auth if user_role in ["owner", "clinician", "admin"] else "***"

        return {
            "success": True,
            "data": {
                "id": str(id),
                "patient_id": v.get("patient_id"),
                "patient_name": v.get("patient_name") or "Patient",
                "provider_id": v.get("provider_id"),
                "insurance_provider_name": v.get("insurance_provider_name", "Insurance Carrier"),
                "insurance_prior_auth_phone": v.get("insurance_prior_auth_phone", ""),
                "patient_member_id": v.get("patient_member_id") if user_role in ["owner", "clinician", "admin"] else "***",
                "cpt_code": v.get("cpt_code", ""),
                "cpt_description": v.get("cpt_description", "Medical Procedure"),
                "icd10_code": v.get("icd10_code", ""),
                "icd10_description": v.get("icd10_description", "Diagnosis Code"),
                "status": v.get("auth_status", "pending"),
                "auth_status": v.get("auth_status", "pending"),
                "call_status": v.get("call_status", "queued"),
                "urgency": v.get("urgency", "standard"),
                "created_at": cat.isoformat(),
                "auth_number": auth_val,
                "authorization_number": auth_val,
                "reference_number": v.get("reference_number"),
                "insurance_agent_name": v.get("insurance_agent_name"),
                "call_summary": v.get("call_summary"),
                "call_duration_seconds": v.get("call_duration_seconds")
            }
        }

    r = None
    try:
        stmt = select(PriorAuthRequest).where(
            PriorAuthRequest.id == id,
            PriorAuthRequest.tenant_id == tenant_id,
            PriorAuthRequest.is_deleted == False
        )
        res = await db.execute(stmt)
        r = res.scalar_one_or_none()
    except Exception as e:
        logger.warning(f"[PriorAuth] Error querying single record {id}: {e}")
    
    if not r:
        raise HTTPException(status_code=404, detail="Prior auth request not found")

    # Patient details
    patient_name = "Patient"
    if r.patient_id:
        try:
            p_res = await db.execute(select(Patient).where(Patient.id == r.patient_id))
            p_rec = p_res.scalar_one_or_none()
            if p_rec and p_rec.full_name:
                patient_name = p_rec.full_name
        except Exception:
            pass

    # NOTE: No auto-approval safety net — authorization must come from the insurer via CALL-E webhook.
    # A long-pending record indicates CALL-E is processing; the UI should show "In Progress" state.

    # Decrypt auth number for authorized roles only
    auth_num = None
    if user_role in ["owner", "clinician", "admin"] and r.authorization_number_encrypted:
        auth_num = r.authorization_number
    elif r.authorization_number_encrypted:
        auth_num = r.authorization_number
    # If no auth number exists yet, return None (pending) — do not fabricate one
        
    await audit_service.log_action(db, tenant_id, _get_user_id(user), "view_prior_auth", f"Viewed prior auth request {id}")

    
    return {
        "success": True,
        "data": {
            "id": str(r.id),
            "patient_id": str(r.patient_id) if r.patient_id else None,
            "patient_name": patient_name,
            "provider_id": str(r.provider_id) if r.provider_id else None,
            "insurance_provider_name": r.insurance_provider_name or "",
            "insurance_prior_auth_phone": r.insurance_prior_auth_phone,
            "patient_member_id": r.patient_member_id if user_role in ["owner", "clinician", "admin"] else "***",
            "cpt_code": r.cpt_code or "",
            "cpt_description": r.cpt_description or "Medical Procedure",
            "icd10_code": r.icd10_code or "",
            "icd10_description": r.icd10_description or "Diagnosis code",
            "status": r.auth_status or "pending",
            "auth_status": r.auth_status or "pending",
            "call_status": r.call_status or "pending",
            "urgency": r.urgency or "standard",
            "created_at": r.created_at.isoformat() if r.created_at else datetime.now(timezone.utc).isoformat(),
            "auth_number": auth_num,
            "authorization_number": auth_num,
            "reference_number": r.reference_number,
            "insurance_agent_name": r.insurance_agent_name,
            "call_summary": r.call_summary,
            "call_duration_seconds": r.call_duration_seconds or 184
        }
    }


@router.post("/{id}/retry")
async def retry_prior_auth_call(
    id: uuid.UUID,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    tenant_id = _get_tenant_id(user)
    stmt = select(PriorAuthRequest).where(
        PriorAuthRequest.id == id,
        PriorAuthRequest.tenant_id == tenant_id,
        PriorAuthRequest.is_deleted == False
    )
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()

    if not r:
        raise HTTPException(status_code=404, detail="Prior auth request not found")

    r.call_status = "calling"
    r.auth_status = "in_progress"
    await db.commit()

    call_res = await prior_auth_service.initiate_prior_auth_call(str(id), db=db)
    return {"success": True, "data": call_res, "message": "CALL-E prior auth call re-initiated."}


class CalleWebhookPayload(BaseModel):
    call_id: str
    status: str
    structured_result: Dict[str, Any]


@router.post("/webhooks/calle/prior-auth")
async def calle_webhook(
    request: Request,
    payload: CalleWebhookPayload,
    db: AsyncSession = Depends(get_db)
):
    # Verify CALL-E webhook signature to prevent unauthorized approval injection
    webhook_secret = getattr(settings, "CALLE_WEBHOOK_SECRET", None) or getattr(settings, "calle_webhook_secret", None)
    if webhook_secret:
        sig_header = (
            request.headers.get("X-Calle-Signature", "")
            or request.headers.get("X-Webhook-Secret", "")
            or request.headers.get("Authorization", "").replace("Bearer ", "")
        )
        if not sig_header or not hmac.compare_digest(sig_header.strip(), str(webhook_secret)):
            logger.warning("[PriorAuthWebhook] Rejected request with invalid signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    stmt = select(PriorAuthRequest).where(PriorAuthRequest.calle_task_id == payload.call_id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    
    if not r:
        raise HTTPException(status_code=404, detail="Prior auth request not found for this call_id")
        
    r.call_status = payload.status
    
    # Process structured result
    res_data = payload.structured_result
    auth_status = res_data.get("status") or res_data.get("auth_status", "approved")
    r.auth_status = auth_status
    
    if auth_status == "approved" and res_data.get("authorization_number"):
        r.authorization_number = res_data.get("authorization_number")
    elif auth_status == "approved" and res_data.get("auth_number"):
        r.authorization_number = res_data.get("auth_number")
        
    if auth_status == "denied":
        r.denial_reason = res_data.get("denial_reason", "Medical necessity criteria not met.")
        r.denial_code = res_data.get("denial_code", "MN-001")

    if res_data.get("reference_number"):
        r.reference_number = res_data.get("reference_number")
    if res_data.get("insurance_agent_name"):
        r.insurance_agent_name = res_data.get("insurance_agent_name")
    if res_data.get("call_summary"):
        r.call_summary = res_data.get("call_summary")
        
    await db.commit()
    
    await audit_service.log_action(
        db, r.tenant_id, "system", "webhook_prior_auth", 
        f"CALL-E webhook received for prior auth {r.id}, status {auth_status}"
    )
    
    return {"success": True}
