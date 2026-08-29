import json
import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_current_user_with_role, require_permission
from src.db.engine import get_db
from src.models.call_log import CallLog
from src.models.patient import Patient
from src.models.user import User
from src.schemas.call import (
    CallListResponse,
    CallListResponseData,
    CallLogResponse,
    TranscriptMessage,
    TranscriptResponse,
    TranscriptResponseData,
)
from src.services.audit_service import audit_service

router = APIRouter(prefix="/calls", tags=["calls"])

def mask_phi(user: User, value: str | None) -> str | None:
    if not value:
        return value
    if user.role in ["owner", "clinician", "admin"]:
        return value
    parts = value.split(" ")
    masked_parts = [f"{p[0]}{'*' * max(len(p)-1, 1)}" for p in parts if p]
    return " ".join(masked_parts)

@router.get("", response_model=CallListResponse)
async def list_calls(
    date_from: str | None = None,
    date_to: str | None = None,
    campaign_type: str | None = None,
    call_type: str | None = None,
    status: str | None = None,
    outcome: str | None = None,
    direction: str | None = None,
    search: str | None = None,
    patient_id: uuid.UUID | None = None,
    min_duration: int | None = None,
    max_duration: int | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(CallLog, Patient).outerjoin(
        Patient, CallLog.patient_id == Patient.id
    )

    # Multi-tenant scoping if user has tenant_id
    if hasattr(user, "tenant_id") and user.tenant_id:
        stmt = stmt.where(CallLog.tenant_id == user.tenant_id)

    # Date range filters
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            stmt = stmt.where(CallLog.created_at >= dt_from)
        except Exception:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            stmt = stmt.where(CallLog.created_at <= dt_to)
        except Exception:
            pass

    # Type / Campaign filters
    target_type = campaign_type or call_type
    if target_type and target_type != "all":
        stmt = stmt.where(CallLog.call_type == target_type)

    if status and status != "all":
        stmt = stmt.where(CallLog.status == status)

    if outcome and outcome != "all":
        stmt = stmt.where(CallLog.outcome == outcome)

    if direction and direction != "all":
        stmt = stmt.where(CallLog.direction == direction)

    if patient_id:
        stmt = stmt.where(CallLog.patient_id == patient_id)

    if min_duration is not None:
        stmt = stmt.where(CallLog.duration_seconds >= min_duration)

    if max_duration is not None:
        stmt = stmt.where(CallLog.duration_seconds <= max_duration)

    # Search filter (patient name, phone, or caller numbers)
    if search:
        search_term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.full_name.ilike(search_term),
                Patient.phone.ilike(search_term),
                CallLog.from_number.ilike(search_term),
                CallLog.to_number.ilike(search_term),
                CallLog.summary.ilike(search_term)
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.scalar(count_stmt)) or 0

    stmt = stmt.order_by(CallLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    res = await db.execute(stmt)
    rows = res.all()

    out = []
    for c, p in rows:
        # Check if recording has passed 24h auto-purge window for HIPAA
        recording_url = c.recording_url
        purge_scheduled = c.recording_purge_scheduled
        if recording_url and purge_scheduled and purge_scheduled <= datetime.now(timezone.utc):
            recording_url = None

        has_t = bool(c.transcript_encrypted or c.transcript_turns)
        is_clinician = user.role in ["owner", "clinician", "admin"]

        out.append(CallLogResponse(
            id=c.id,
            retell_call_id=c.retell_call_id,
            call_date=c.call_date or c.created_at,
            duration_seconds=c.duration_seconds or 0,
            direction=c.direction or "inbound",
            call_type=c.call_type or "general",
            status=c.status or "completed",
            outcome=c.outcome or "completed",
            from_number=c.from_number,
            to_number=c.to_number,
            tools_invoked=c.tools_invoked or [],
            patient_id=p.id if p else c.patient_id,
            patient_name=mask_phi(user, p.full_name if p else None),
            appointment_id=c.appointment_id,
            has_transcript=has_t,
            transcript_accessible=is_clinician,
            transcript_turns=c.transcript_turns if is_clinician else None,
            structured_result=c.structured_result,
            completion_score=c.completion_score,
            completion_label=c.completion_label,
            evidence=c.evidence,
            summary=c.summary,
            recording_url=recording_url if is_clinician else None,
            recording_purge_scheduled=purge_scheduled,
            recording_purged_at=c.recording_purged_at,
        ))

    return CallListResponse(
        success=True,
        data=CallListResponseData(
            calls=out,
            meta={
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": math.ceil(total / per_page) if total > 0 else 1
            }
        )
    )

@router.get("/{id}", response_model=TranscriptResponse)
async def get_call_detail(
    id: uuid.UUID,
    user: User = Depends(require_permission(["owner", "clinician", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(CallLog, Patient).outerjoin(Patient, CallLog.patient_id == Patient.id).where(CallLog.id == id)
    res = await db.execute(stmt)
    row = res.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Call log not found")
        
    call_log, patient = row
    
    audit_id = await audit_service.log(
        action="READ",
        actor_id=user.id,
        tenant_id=user.tenant_id if hasattr(user, "tenant_id") else None,
        target_table="call_logs",
        target_id=call_log.id,
        target_patient_id=call_log.patient_id,
        ip_address="internal",
        change_reason="Viewed call detail and transcript turns"
    )
    
    transcript_messages = []
    
    # 1. First check structured transcript_turns
    if call_log.transcript_turns and isinstance(call_log.transcript_turns, list):
        for turn in call_log.transcript_turns:
            if isinstance(turn, dict):
                speaker = turn.get("speaker") or turn.get("role") or "unknown"
                text_content = turn.get("message") or turn.get("text") or turn.get("content") or ""
                time_str = turn.get("timestamp") or turn.get("time")
                sentiment = turn.get("sentiment")
                transcript_messages.append(TranscriptMessage(
                    speaker=speaker,
                    text=text_content,
                    timestamp=time_str,
                    role=turn.get("role", speaker),
                    sentiment=sentiment
                ))
    
    # 2. Check encrypted transcript fallback
    elif call_log.transcript_encrypted:
        try:
            from src.core.encryption import phi_crypto
            raw_json = phi_crypto.decrypt(call_log.transcript_encrypted)
            raw_transcript = json.loads(raw_json)
            for i, msg in enumerate(raw_transcript):
                role = msg.get("role", "unknown")
                speaker = "AI Receptionist" if role in ("agent", "bot", "assistant", "system") else (patient.full_name if patient else "Patient")
                transcript_messages.append(TranscriptMessage(
                    speaker=speaker,
                    text=msg.get("content") or msg.get("text", ""),
                    timestamp=msg.get("timestamp", f"00:{i*12:02d}"),
                    role=role
                ))
        except Exception:
            pass

    # Check 24-hour HIPAA auto-purge
    recording_url = call_log.recording_url
    purge_scheduled = call_log.recording_purge_scheduled
    if recording_url and purge_scheduled and purge_scheduled <= datetime.now(timezone.utc):
        recording_url = None

    return TranscriptResponse(
        success=True,
        data=TranscriptResponseData(
            call_id=call_log.id,
            transcript=transcript_messages,
            transcript_turns=call_log.transcript_turns,
            duration_seconds=call_log.duration_seconds or 0,
            direction=call_log.direction or "inbound",
            call_type=call_log.call_type or "general",
            status=call_log.status or "completed",
            outcome=call_log.outcome or "completed",
            structured_result=call_log.structured_result,
            summary=call_log.summary,
            completion_score=call_log.completion_score,
            completion_label=call_log.completion_label,
            evidence=call_log.evidence,
            recording_url=recording_url,
            recording_purge_scheduled=purge_scheduled,
            recording_purged_at=call_log.recording_purged_at,
            audit_log_id=audit_id
        )
    )

@router.get("/{id}/transcript", response_model=TranscriptResponse)
async def get_call_transcript(
    id: uuid.UUID,
    user: User = Depends(require_permission(["owner", "clinician", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    return await get_call_detail(id=id, user=user, db=db)

