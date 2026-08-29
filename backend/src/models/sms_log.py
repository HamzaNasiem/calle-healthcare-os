import uuid

from sqlalchemy import Float, ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import TenantMixin, Base, TimestampMixin, UUIDMixin


class SmsLog(Base, TenantMixin, UUIDMixin, TimestampMixin):
    __tablename__ = "sms_logs"
    __table_args__ = (
        Index("idx_smslog_tenant_patient", "patient_id", "created_at"),
    )

    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('patients.id'), nullable=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('appointments.id'), nullable=True)

    # Relationship for selectinload in sms_logs.py API
    patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[patient_id], lazy="select")

    direction: Mapped[str] = mapped_column(String, nullable=False)
    telnyx_message_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    sms_type: Mapped[str | None] = mapped_column(String, nullable=True)

    message_body_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # In production this is None; the API exposes message_body_encrypted decrypted as content

    parsed_intent: Mapped[str | None] = mapped_column(String, nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
