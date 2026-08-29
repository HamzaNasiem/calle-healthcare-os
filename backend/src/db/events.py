import asyncio

from sqlalchemy import event
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog
from src.models.user import User
from src.services.audit_service import audit_service


# Setup audit events to buffer logs during session lifecycle, and only dispatch on commit
def setup_audit_events(Base):
    for mapper in Base.registry.mappers:
        model_class = mapper.class_
        # Skip auditing the AuditLog itself
        if model_class == AuditLog or model_class == User:
            continue
            
        @event.listens_for(model_class, 'after_insert')
        def after_insert(mapper, connection, target):
            table_name = target.__tablename__
            target_id = getattr(target, "id", None)
            tenant_id = getattr(target, "tenant_id", None)
            
            session = Session.object_session(target)
            if session:
                session.info.setdefault('pending_audits', []).append({
                    "action": f"AUTO_INSERT_{table_name.upper()}",
                    "actor_id": None,
                    "actor_type": "system",
                    "target_table": table_name,
                    "target_id": target_id,
                    "ingress_ip": "internal",
                    "change_reason": "Automated ORM Insert",
                    "tenant_id": tenant_id
                })

        @event.listens_for(model_class, 'after_update')
        def after_update(mapper, connection, target):
            table_name = target.__tablename__
            target_id = getattr(target, "id", None)
            tenant_id = getattr(target, "tenant_id", None)
            
            session = Session.object_session(target)
            if session:
                session.info.setdefault('pending_audits', []).append({
                    "action": f"AUTO_UPDATE_{table_name.upper()}",
                    "actor_id": None,
                    "actor_type": "system",
                    "target_table": table_name,
                    "target_id": target_id,
                    "ingress_ip": "internal",
                    "change_reason": "Automated ORM Update",
                    "tenant_id": tenant_id
                })
                
        @event.listens_for(model_class, 'after_delete')
        def after_delete(mapper, connection, target):
            table_name = target.__tablename__
            target_id = getattr(target, "id", None)
            tenant_id = getattr(target, "tenant_id", None)
            
            session = Session.object_session(target)
            if session:
                session.info.setdefault('pending_audits', []).append({
                    "action": f"AUTO_DELETE_{table_name.upper()}",
                    "actor_id": None,
                    "actor_type": "system",
                    "target_table": table_name,
                    "target_id": target_id,
                    "ingress_ip": "internal",
                    "change_reason": "Automated ORM Delete",
                    "tenant_id": tenant_id
                })

    # Register Session Commit Events
    @event.listens_for(Session, "after_commit")
    def after_commit(session):
        pending = session.info.pop("pending_audits", [])
        if not pending:
            return
        try:
            loop = asyncio.get_running_loop()
            for audit in pending:
                loop.create_task(
                    audit_service.log(
                        action=audit["action"],
                        actor_id=audit["actor_id"],
                        actor_type=audit["actor_type"],
                        target_table=audit["target_table"],
                        target_id=audit["target_id"],
                        ingress_ip=audit["ingress_ip"],
                        change_reason=audit["change_reason"],
                        tenant_id=audit["tenant_id"]
                    )
                )
        except RuntimeError:
            pass  # Occurs during migrations or sync test runs

    @event.listens_for(Session, "after_rollback")
    def after_rollback(session):
        session.info.pop("pending_audits", None)
