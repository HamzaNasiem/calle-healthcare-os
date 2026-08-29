import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base


class OutboxEvent(Base):
    """
    Transactional Outbox Pattern.
    Events that must be published to external services (like Retell or Telnyx).
    Written in the same database transaction as business logic to prevent split-brain.
    """
    __tablename__ = "outbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    
    tenant_id = Column(String(50), nullable=True, index=True)
    
    status = Column(String(20), default="PENDING", nullable=False, index=True) # PENDING, PROCESSING, FAILED, COMPLETED
    retries = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    last_error = Column(String(500), nullable=True)
