import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import TenantMixin, Base, TimestampMixin, UUIDMixin


class Waitlist(Base, TenantMixin, UUIDMixin, TimestampMixin):
    """
    Waitlist model. Uses TimestampMixin (gives created_at + updated_at)
    which is required by waitlist_service.py (accesses entry.updated_at).
    """
    __tablename__ = "waitlist"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('patients.id'), nullable=False)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('providers.id'), nullable=True)

    # Relationship for selectinload in waitlist.py API
    patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[patient_id], lazy="select")

    service_type: Mapped[str | None] = mapped_column(String, nullable=True)

    # preferred_days: list of day strings, e.g. ["Monday", "Wednesday"]
    preferred_days: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    # Backward compat alias — older code may use preferred_day (singular)
    preferred_day: Mapped[str | None] = mapped_column(String, nullable=True)

    preferred_time_range: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: waiting | notified | claimed | booked | removed | cancelled
    status: Mapped[str] = mapped_column(String, nullable=False, default="waiting")

    notified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    booked_from_waitlist: Mapped[bool] = mapped_column(Boolean, default=False)

    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
