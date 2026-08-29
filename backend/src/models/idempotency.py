import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base


class IdempotencyKey(Base):
    """
    Stores HTTP idempotency keys for critical mutation endpoints.
    Prevents double-charges or double-bookings on client retries.
    """
    __tablename__ = "idempotency_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    key = Column(String(255), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True) # Optional, depends on auth scope
    tenant_id = Column(String(50), nullable=True)
    
    # Cached HTTP response
    status_code = Column(String(10), nullable=False)
    response_body = Column(JSON, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index("ix_idempotency_key_tenant", "key", "tenant_id", unique=True),
    )
