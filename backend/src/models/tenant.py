from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    business_type: Mapped[str | None] = mapped_column(String, nullable=True)
    telnyx_did: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    retell_agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plan: Mapped[str] = mapped_column(String, default='tier1')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    security_officer_email: Mapped[str] = mapped_column(String, nullable=False)
    owner_email: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, default='America/Chicago')
