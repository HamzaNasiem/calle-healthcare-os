"""
Audit Database Engine
Dedicated connection for the append-only Audit Log database to comply with HIPAA.

This module provides:
1. audit_engine       — Separate SQLAlchemy async engine for audit DB
2. audit_session_maker — Session factory for audit DB
3. log_audit_event()  — Convenience wrapper used by voice tools to log PHI access
                        Delegates to AuditService to maintain the hash chain.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ssl

from src.config.settings import settings

audit_connect_args = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
    "prepared_statement_name_func": lambda: "",
}
if settings.AUDIT_DATABASE_SSL:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    audit_connect_args["ssl"] = ssl_ctx

audit_engine = create_async_engine(
    settings.audit_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
    connect_args=audit_connect_args,
)

audit_session_maker = async_sessionmaker(
    audit_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_audit_db() -> AsyncGenerator[AsyncSession, None]:
    async with audit_session_maker() as session:
        yield session


async def log_audit_event(
    db: AsyncSession,
    tenant_id: str,
    actor_type: str,
    actor_id: str,
    action: str,
    target_table: str,
    target_id: str | None,
    target_patient_id: str | None = None,
    fields_accessed: list[str] | None = None
) -> None:
    """
    Convenience wrapper for voice tools to log PHI access events.

    Delegates to AuditService which maintains the hash-chain per HIPAA requirements.
    The tenant context MUST be set via set_tenant_id() before calling this function.

    Args:
        db:                 Main app DB session (not used for write — audit writes to audit_db)
        tenant_id:          UUID str of the clinic tenant
        actor_type:         "ai_agent" | "user" | "system"
        actor_id:           call_id or user session_id as string
        action:             Uppercase action string, e.g. "CREATE", "UPDATE", "TOOL_INVOKE"
        target_table:       DB table name touched, e.g. "appointments", "patients"
        target_id:          UUID str of the row affected (None if not applicable)
        target_patient_id:  UUID str of the patient this action relates to
        fields_accessed:    List of field names accessed/modified
    """
    import uuid as _uuid

    from src.core.tenant_context import set_tenant_id
    from src.services.audit_service import audit_service

    # Ensure tenant context is set so audit_service can read it
    try:
        set_tenant_id(_uuid.UUID(str(tenant_id)))
    except (ValueError, AttributeError):
        pass  # Already set or invalid — audit_service will raise if truly missing

    # Convert string IDs to UUID objects where expected
    def _to_uuid(val: str | None) -> _uuid.UUID | None:
        if not val:
            return None
        try:
            return _uuid.UUID(str(val))
        except (ValueError, AttributeError):
            return None

    await audit_service.log(
        action=action,
        target_table=target_table,
        target_id=_to_uuid(target_id),
        target_patient_id=_to_uuid(target_patient_id),
        actor_id=_to_uuid(actor_id) if actor_id else None,
        actor_type=actor_type,
        session_id=actor_id,  # store call_id in session_id for AI agent calls
        fields_accessed=fields_accessed or [],
        outcome="SUCCESS"
    )
