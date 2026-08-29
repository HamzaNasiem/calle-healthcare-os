"""
AuditLog Model
HIPAA-compliant hash-chained audit log.
Stored in a SEPARATE audit database (audit_engine).
CRITICAL: Uses AuditBase, NOT Base — so it maps to the audit DB schema.
"""
import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from .base import AuditBase


class AuditLog(AuditBase):
    __tablename__ = "audit_logs"

    # Primary key — UUID v4
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Hash chain fields
    sequence_number = Column(BigInteger, nullable=False, index=True)
    previous_hash = Column(String(64), nullable=True)    # NULL for genesis row
    row_hash = Column(String(64), nullable=False)         # SHA-256 of this row

    # Tenant isolation
    tenant_id = Column(String(36), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # alias

    # Actor info
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    actor_type = Column(String(50), nullable=False, default="system")   # user | ai_agent | system
    actor_email = Column(String(255), nullable=True)
    actor_role = Column(String(50), nullable=True)

    # Action
    action = Column(String(100), nullable=False)

    # Target info
    target_table = Column(String(100), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    target_patient_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Request metadata (NEVER store raw PHI here)
    ingress_ip = Column(String(45), nullable=True)          # IPv4 or IPv6
    ip_address = Column(String(45), nullable=True)           # alias for convenience
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(255), nullable=True)

    # Payload diffs (for change tracking)
    fields_accessed = Column(JSON, nullable=True)
    before_snapshot = Column(JSON, nullable=True)
    after_snapshot = Column(JSON, nullable=True)

    # Outcome and notes
    outcome = Column(String(20), nullable=False, default="SUCCESS")   # SUCCESS | FAILURE | DENIED
    change_reason = Column(String(500), nullable=True)
    denial_reason = Column(String(500), nullable=True)
    is_high_sensitivity = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_tenant_patient", "target_patient_id"),
        Index("ix_audit_logs_tenant_seq", "sequence_number"),
        Index("ix_audit_logs_action", "action"),
    )
