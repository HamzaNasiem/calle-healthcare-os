import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import (
    TenantMixin,
    Base,
    IntegrityMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class Appointment(Base, TenantMixin, UUIDMixin, TimestampMixin, SoftDeleteMixin, IntegrityMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("idx_appt_tenant_slot_active", "slot_start", "status", postgresql_where=text("is_deleted = false")),
        Index("idx_appt_tenant_patient", "patient_id"),
        Index("idx_appt_tenant_provider_slot", "provider_id", "slot_start"),
        Index("idx_appt_tenant_code", "confirmation_code", unique=True),
    )

    # FK columns
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('patients.id'), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('providers.id'), nullable=False)

    # Relationships (required for selectinload in API)
    patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[patient_id], lazy="select")
    provider: Mapped["Provider"] = relationship("Provider", foreign_keys=[provider_id], lazy="select")

    slot_start: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    service_type: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String, default='scheduled')
    booked_by: Mapped[str] = mapped_column(String, nullable=False)
    booked_via_call_id: Mapped[str | None] = mapped_column(String, nullable=True)

    confirmation_code: Mapped[str | None] = mapped_column(String, nullable=True)
    sms_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    call_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmation_call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('outbound_calls.id', ondelete='SET NULL'), nullable=True)
    pre_appointment_call_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_24h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_2h_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    cancellation_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('appointments.id'), nullable=True)
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
