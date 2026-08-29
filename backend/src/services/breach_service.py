import datetime
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.incident_log import IncidentLog
from src.models.audit_log import AuditLog
from src.services.slack_service import slack_service
from src.core.logger import log

class BreachService:
    async def log_security_incident(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_type: str,
        severity: str,
        description: str,
        affected_patient_count: int = 0,
        phi_encrypted_at_time: bool = True
    ) -> IncidentLog:
        """
        Logs a security incident to the database and alerts via Slack.
        If affected_patient_count >= 500, sets HHS notification due in 60 days.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        hhs_due = None
        if affected_patient_count >= 500:
            hhs_due = now + datetime.timedelta(days=60)
            
        incident = IncidentLog(
            tenant_id=tenant_id,
            severity=severity,
            incident_type=incident_type,
            description=description,
            detected_at=now,
            detected_by="BreachDetectionEngine",
            affected_patient_count=affected_patient_count,
            phi_encrypted_at_time=phi_encrypted_at_time,
            hhs_notification_due=hhs_due,
            status="open"
        )
        db.add(incident)
        await db.flush()
        
        if severity in ["high", "critical"]:
            try:
                alert_msg = f"🚨 *CRITICAL SECURITY INCIDENT DETECTED* 🚨\n*Type:* {incident_type}\n*Severity:* {severity}\n*Description:* {description}\n*Affected Patients:* {affected_patient_count}"
                await slack_service.alert(alert_msg, level=severity)
            except Exception as slack_err:
                log.error(f"[BreachService] Failed to send Slack alert: {str(slack_err)}")
                
        await db.commit()
        return incident

    async def detect_brute_force(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        email: str,
        ip_address: str
    ) -> bool:
        """
        Checks if there are 5 or more failed login attempts in the last 15 minutes.
        If so, logs a high-severity incident.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        fifteen_mins_ago = now - datetime.timedelta(minutes=15)
        
        from src.db.audit_engine import audit_session_maker
        
        async with audit_session_maker() as audit_db:
            stmt = select(func.count(AuditLog.id)).where(
                AuditLog.tenant_id == str(tenant_id),
                AuditLog.action == "FAILED_LOGIN",
                AuditLog.timestamp >= fifteen_mins_ago,
                AuditLog.ip_address == ip_address
            )
            res = await audit_db.execute(stmt)
            count = res.scalar() or 0
            
        if count >= 5:
            await self.log_security_incident(
                db=db,
                tenant_id=tenant_id,
                incident_type="brute_force_login",
                severity="high",
                description=f"Brute force login detected from IP {ip_address} targeting user {email} (failed attempts: {count} in 15m)"
            )
            return True
        return False

    async def detect_excessive_phi_reveals(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str
    ) -> bool:
        """
        Checks if a user has performed 10 or more PHI reveals in the last 60 minutes.
        If so, logs a critical incident.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        one_hour_ago = now - datetime.timedelta(hours=1)
        
        from src.db.audit_engine import audit_session_maker
        
        async with audit_session_maker() as audit_db:
            stmt = select(func.count(AuditLog.id)).where(
                AuditLog.tenant_id == str(tenant_id),
                AuditLog.action == "REVEAL_PHI",
                AuditLog.actor_id == actor_id,
                AuditLog.timestamp >= one_hour_ago
            )
            res = await audit_db.execute(stmt)
            count = res.scalar() or 0
            
        if count >= 10:
            await self.log_security_incident(
                db=db,
                tenant_id=tenant_id,
                incident_type="excessive_phi_access",
                severity="critical",
                description=f"User {actor_id} performed excessive PHI reveals from IP {ip_address} (reveals: {count} in 1h)",
                affected_patient_count=count
            )
            return True
        return False

breach_service = BreachService()
