import datetime

from sqlalchemy import ARRAY, JSON, Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import TenantMixin, Base, UUIDMixin


class BaaRegistry(Base, TenantMixin, UUIDMixin):
    __tablename__ = "baa_registry"

    vendor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    baa_document_url: Mapped[str | None] = mapped_column(String, nullable=True)
    signed_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    
    phi_categories: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    subprocessors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    ai_training_prohibited: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
