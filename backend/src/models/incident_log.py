import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import TenantMixin, Base, UUIDMixin


class IncidentLog(Base, TenantMixin, UUIDMixin):
    __tablename__ = "incident_logs"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True)
    
    severity: Mapped[str] = mapped_column(String, nullable=False)
    incident_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    
    detected_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    detected_by: Mapped[str | None] = mapped_column(String, nullable=True)
    
    affected_patient_count: Mapped[int] = mapped_column(Integer, default=0)
    phi_encrypted_at_time: Mapped[bool] = mapped_column(Boolean, default=True)
    
    hhs_notification_due: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hhs_notified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patient_notification_due: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patients_notified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    
    status: Mapped[str] = mapped_column(String, default='open')
