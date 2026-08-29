import datetime
import uuid

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SlotLock(Base):
    __tablename__ = "slot_locks"

    slot_key: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    locked_by_call_id: Mapped[str] = mapped_column(String, nullable=False)
    locked_by_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    locked_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
