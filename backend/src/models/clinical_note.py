import uuid

from sqlalchemy import ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import TenantMixin, Base, TimestampMixin, UUIDMixin


class ClinicalNote(Base, TenantMixin, UUIDMixin, TimestampMixin):
    __tablename__ = "clinical_notes"
    __table_args__ = (
        Index("idx_clinicalnote_tenant_patient", "patient_id", "created_at"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('patients.id'), nullable=False)
    call_log_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('call_logs.id'), nullable=True)
    
    authored_by: Mapped[str] = mapped_column(String, nullable=False)
    note_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    note_hash: Mapped[str] = mapped_column(String, nullable=False)
    access_level: Mapped[str] = mapped_column(String, default='clinician')
