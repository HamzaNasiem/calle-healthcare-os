from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.encryption import phi_crypto
from src.core.security import require_permission
from src.db.engine import get_db
from src.models.sms_log import SmsLog
from src.models.user import User
from src.schemas.sms import SmsListResponse, SmsListResponseData, SmsLogResponse

router = APIRouter(prefix="/sms-logs", tags=["sms_logs"])

@router.get("", response_model=SmsListResponse)
async def list_sms_logs(
    date_from: str | None = None,
    date_to: str | None = None,
    direction: str | None = None,
    sms_type: str | None = None,
    parsed_intent: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission(["owner", "clinician"])), # Explicitly restricts staff
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SmsLog).options(selectinload(SmsLog.patient)).where(SmsLog.tenant_id == user.tenant_id)
    
    if direction:
        stmt = stmt.where(SmsLog.direction == direction)
    if sms_type:
        stmt = stmt.where(SmsLog.sms_type == sms_type)
    if parsed_intent:
        stmt = stmt.where(SmsLog.parsed_intent == parsed_intent)
        
    if date_from:
        stmt = stmt.where(SmsLog.created_at >= datetime.fromisoformat(date_from.replace("Z", "+00:00")))
    if date_to:
        stmt = stmt.where(SmsLog.created_at <= datetime.fromisoformat(date_to.replace("Z", "+00:00")))
        
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt)
    
    stmt = stmt.order_by(SmsLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    
    out = []
    for log in logs:
        patient_name = "Unknown"
        if log.patient and log.patient.full_name_encrypted:
            patient_name = phi_crypto.decrypt(log.patient.full_name_encrypted)
            
        out.append(SmsLogResponse(
            id=log.id,
            direction=log.direction,
            sms_type=log.sms_type,
            patient_name=patient_name,
            status=log.status,
            created_at=log.created_at,
            content=phi_crypto.decrypt(log.message_body_encrypted) if log.message_body_encrypted else None
        ))
        
    return SmsListResponse(
        success=True,
        data=SmsListResponseData(
            sms_logs=out,
            meta={"page": page, "per_page": per_page, "total": total}
        )
    )
