import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.encryption import phi_crypto
from src.models.base import TenantMixin, Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class User(Base, TenantMixin, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_user_tenant_email", "email"),
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    mfa_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_backup_codes_encrypted: Mapped[str | None] = mapped_column("mfa_backup_codes", Text, nullable=True)

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # Store as String, NOT INET — handles "unknown"

    @property
    def mfa_secret(self) -> str | None:
        if self.mfa_secret_encrypted:
            return phi_crypto.decrypt(self.mfa_secret_encrypted)
        return None

    @mfa_secret.setter
    def mfa_secret(self, value: str):
        if value:
            self.mfa_secret_encrypted = phi_crypto.encrypt(value)
        else:
            self.mfa_secret_encrypted = None

    @property
    def mfa_backup_codes(self) -> str | None:
        """Decrypts and returns JSON string, or falls back to plaintext if stored unencrypted."""
        if self.mfa_backup_codes_encrypted:
            try:
                import base64
                encrypted_bytes = base64.b64decode(self.mfa_backup_codes_encrypted)
                decrypted = phi_crypto.decrypt(encrypted_bytes)
                if decrypted is not None:
                    return decrypted
            except Exception:
                pass
            # Fallback if stored as plaintext initially
            return self.mfa_backup_codes_encrypted
        return None

    @mfa_backup_codes.setter
    def mfa_backup_codes(self, value: str):
        """Encrypts JSON string of backup codes using AES-256-GCM and encodes as base64."""
        if value:
            import base64
            encrypted_bytes = phi_crypto.encrypt(value)
            self.mfa_backup_codes_encrypted = base64.b64encode(encrypted_bytes).decode('utf-8')
        else:
            self.mfa_backup_codes_encrypted = None
