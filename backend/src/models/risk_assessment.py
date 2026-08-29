import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import TenantMixin, Base, TimestampMixin, UUIDMixin


class RiskAssessment(Base, TenantMixin, UUIDMixin, TimestampMixin):
    __tablename__ = "risk_assessments"
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)
    assessment_notes: Mapped[str | None] = mapped_column(String, nullable=True)
