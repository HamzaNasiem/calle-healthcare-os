import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import TenantMixin, Base, TimestampMixin, UUIDMixin


class TrainingCompletion(Base, TenantMixin, UUIDMixin, TimestampMixin):
    __tablename__ = "training_completions"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
