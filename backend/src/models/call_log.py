import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import TenantMixin, Base, TimestampMixin, UUIDMixin


class CallLog(Base, TenantMixin, UUIDMixin, TimestampMixin):
    __tablename__ = "call_logs"
    __table_args__ = (
        Index("idx_calllog_tenant_date", "created_at"),
        Index("idx_calllog_tenant_patient", "patient_id"),
        Index("idx_calllog_purge_pending", "recording_purge_scheduled", postgresql_where=text("recording_url IS NOT NULL")),
    )

    retell_call_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('patients.id'), nullable=True)
    caller_phone_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    call_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # When call happened

    # Relationship for selectinload in calls.py and patients.py APIs
    patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[patient_id], lazy="select")

    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True)
    appointment: Mapped["Appointment"] = relationship("Appointment", foreign_keys=[appointment_id], lazy="select")

    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String, default='inbound')
    call_type: Mapped[str | None] = mapped_column(String(50), default='general', nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), default='completed', nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)

    from_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    tools_invoked: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    tools_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    structured_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    evidence: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    transcript_turns: Mapped[list | None] = mapped_column(JSON, nullable=True)

    transcript_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String, nullable=True)
    
    recording_purged_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_purge_scheduled: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transfer_reason: Mapped[str | None] = mapped_column(String, nullable=True)

