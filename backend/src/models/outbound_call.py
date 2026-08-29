import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class OutboundCall(Base, TenantMixin, UUIDMixin, TimestampMixin):
    __tablename__ = "outbound_calls"
    __table_args__ = (
        Index("idx_outbound_calls_tenant_id", "tenant_id"),
        Index("idx_outbound_calls_appointment_id", "appointment_id"),
        Index("idx_outbound_calls_calle_call_id", "calle_call_id"),
        Index("idx_outbound_calls_idempotency_key", "idempotency_key", unique=True),
    )

    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('patients.id', ondelete='SET NULL'), nullable=True)

    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    calle_call_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    task_completed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    structured_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    completion_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_confidence_label: Mapped[str | None] = mapped_column(String(20), nullable=True)

    evidence: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    direction: Mapped[str] = mapped_column(String(20), default="outbound", nullable=False)
    from_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    transcript_turns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String, nullable=True)
    recording_purge_scheduled: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_purged_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scheduled_for: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    placed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    appointment: Mapped["Appointment"] = relationship("Appointment", foreign_keys=[appointment_id], lazy="select")
    patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[patient_id], lazy="select")

