import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import require_permission
from src.db.audit_engine import get_audit_db  # STEP 7 FIX: import dedicated audit DB session
from src.db.engine import get_db
from src.models.audit_log import AuditLog
from src.models.baa_registry import BaaRegistry
from src.models.incident_log import IncidentLog
from src.models.user import User
from src.schemas.compliance import (
    AuditLogsData,
    AuditLogsResponse,
    AuditVerifyData,
    AuditVerifyResponse,
    BaaRegistryData,
    BaaRegistryResponse,
    IncidentsData,
    IncidentsResponse,
)
from src.services.audit_service import audit_service

router = APIRouter(prefix="/compliance", tags=["compliance"])

@router.get("/audit-logs", response_model=AuditLogsResponse)
async def list_audit_logs(
    date_from: str | None = None,
    date_to: str | None = None,
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
    target_table: str | None = None,
    target_patient_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db),
    audit_db: AsyncSession = Depends(get_audit_db),  # STEP 7 FIX: use audit DB, not main DB
):
    # STEP 7 FIX: AuditLog records are written to the AUDIT database (audit_session_maker).
    # Querying via main `db` always returned empty results. Now using `audit_db`.
    stmt = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if target_table:
        stmt = stmt.where(AuditLog.target_table == target_table)
    if target_patient_id:
        stmt = stmt.where(AuditLog.target_patient_id == target_patient_id)
        
    if date_from:
        stmt = stmt.where(AuditLog.timestamp >= datetime.fromisoformat(date_from.replace("Z", "+00:00")))
    if date_to:
        stmt = stmt.where(AuditLog.timestamp <= datetime.fromisoformat(date_to.replace("Z", "+00:00")))
        
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await audit_db.scalar(count_stmt)  # use audit_db
    
    stmt = stmt.order_by(AuditLog.sequence_number.desc()).offset((page - 1) * per_page).limit(per_page)
    res = await audit_db.execute(stmt)  # use audit_db
    logs = res.scalars().all()
    
    out = []
    for log in logs:
        out.append({
            "id": str(log.id),
            "sequence_number": log.sequence_number,
            "timestamp": log.timestamp.isoformat(),
            "action": log.action,
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "target_table": log.target_table,
            "target_id": str(log.target_id) if log.target_id else None,
            "target_patient_id": str(log.target_patient_id) if log.target_patient_id else None,
            "ip_address": log.ip_address,
            "change_reason": log.change_reason,
            "is_high_sensitivity": log.is_high_sensitivity
        })

    return AuditLogsResponse(
        success=True,
        data=AuditLogsData(
            audit_logs=out,
            meta={"page": page, "per_page": per_page, "total": total}
        )
    )

@router.get("/audit-chain/verify", response_model=AuditVerifyResponse)
async def verify_audit_chain(
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    start_time = datetime.now(UTC)
    
    # Run the full hash chain verification
    is_valid, records_checked, error_msg = await audit_service.verify_chain(user.tenant_id)
    
    duration = datetime.now(UTC) - start_time
    duration_ms = int(duration.total_seconds() * 1000)
    
    return AuditVerifyResponse(
        success=True,
        data=AuditVerifyData(
            status="VALID" if is_valid else "INTEGRITY_BREACH",
            total_records_verified=records_checked,
            verification_duration_ms=duration_ms,
            last_record_sequence=records_checked,
            last_verified_at=datetime.now(UTC)
        )
    )

@router.get("/audit-logs/export", response_class=Response)
async def export_audit_logs(
    request: Request,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id).order_by(AuditLog.sequence_number.asc())
    res = await db.execute(stmt)
    logs = res.scalars().all()
    
    csv_data = "sequence_number,timestamp,action,actor_id,target_table,target_id,target_patient_id,ip_address,change_reason\n"
    for log in logs:
        csv_data += f"{log.sequence_number},{log.timestamp.isoformat()},{log.action},{log.actor_id},{log.target_table},{log.target_id},{log.target_patient_id},{log.ip_address},\"{log.change_reason or ''}\"\n"
        
    await audit_service.log(
        action="EXPORT_AUDIT_LOGS",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="audit_logs",
        ip_address=request.client.host if request.client else "unknown",
        change_reason="Exported audit logs to CSV",
        is_high_sensitivity=True
    )
    
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit_log.csv"'})

@router.get("/baa-registry", response_model=BaaRegistryResponse)
async def get_baa_registry(
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(BaaRegistry).where(BaaRegistry.tenant_id == user.tenant_id).order_by(BaaRegistry.signed_date.desc())
    res = await db.execute(stmt)
    baas = res.scalars().all()
    
    out = []
    for b in baas:
        expiry_warning = False
        if b.expiry_date:
            expiry_warning = (b.expiry_date - datetime.now(UTC).date()).days < 30
            
        out.append({
            "id": b.id,
            "vendor_name": b.vendor_name or "Unknown Vendor",
            "signed_date": b.signed_date.strftime("%Y-%m-%d") if b.signed_date else "",
            "expiry_date": b.expiry_date.strftime("%Y-%m-%d") if b.expiry_date else None,
            "status": b.status or "active",
            "phi_categories": b.phi_categories or [],
            "ai_training_prohibited": b.ai_training_prohibited or False,
            "expiry_warning": expiry_warning
        })
        
    return BaaRegistryResponse(
        success=True,
        data=BaaRegistryData(baas=out)
    )

@router.get("/incidents", response_model=IncidentsResponse)
async def get_incidents(
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(IncidentLog).where(IncidentLog.tenant_id == user.tenant_id).order_by(IncidentLog.detected_at.desc())
    res = await db.execute(stmt)
    incidents = res.scalars().all()
    
    out = []
    for i in incidents:
        out.append({
            "id": i.id,
            "severity": i.severity,
            "incident_type": i.incident_type,
            "description": i.description,
            "detected_at": i.detected_at,
            "phi_encrypted_at_time": i.phi_encrypted_at_time,
            "hhs_notification_due": i.hhs_notification_due,
            "status": i.status,
            "resolved_at": i.resolved_at
        })
        
    return IncidentsResponse(
        success=True,
        data=IncidentsData(incidents=out)
    )


