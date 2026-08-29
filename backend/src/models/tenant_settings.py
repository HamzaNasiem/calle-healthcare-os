import datetime
import uuid

from sqlalchemy import ARRAY, JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base, UUIDMixin


class TenantSettings(Base, UUIDMixin):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('tenants.id'), unique=True, nullable=False)

    # Clinic identity
    clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default="Our Clinic")
    clinic_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    clinic_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="America/New_York")

    # Scheduling & services config (JSON)
    business_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    providers: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    services: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    faq_entries: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # AI persona (used by Retell inbound webhook + API settings GET)
    ai_persona: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # e.g. {"name": "Alex", "tone": "friendly", "greeting": "..."}
    ai_persona_prompt: Mapped[str | None] = mapped_column(String, nullable=True)  # raw LLM system prompt override

    # Telephony
    transfer_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # SMS
    sms_opt_out_list: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
