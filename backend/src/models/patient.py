import datetime

from sqlalchemy import Boolean, Date, Float, Index, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.encryption import phi_crypto
from src.models.base import (
    TenantMixin,
    Base,
    IntegrityMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class Patient(Base, TenantMixin, UUIDMixin, TimestampMixin, SoftDeleteMixin, IntegrityMixin):
    __tablename__ = "patients"
    __table_args__ = (
        Index("idx_patient_phone", "phone_hash"),
        Index("idx_patient_last_visit", "last_visit_date"),
    )

    phone_hash: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    phone_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    full_name_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dob_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    
    is_existing_patient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_revenue_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    churn_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_visit_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Email — stored encrypted (HIPAA) for appointment confirmation emails
    email_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    
    # Insurance & Demographics — stored encrypted (HIPAA)
    insurance_provider_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    insurance_member_id_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    notes_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    preferred_time: Mapped[str | None] = mapped_column(String, default="morning", nullable=True)
    recall_opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    language_preference: Mapped[str | None] = mapped_column(String, default="en", nullable=True)
    
    data_access_level: Mapped[str] = mapped_column(String, default='standard', nullable=False)


    @property
    def phone(self) -> str | None:
        if self.phone_encrypted:
            return phi_crypto.decrypt(self.phone_encrypted)
        return None

    @phone.setter
    def phone(self, value: str | None):
        if value:
            self.phone_encrypted = phi_crypto.encrypt(value)
        else:
            self.phone_encrypted = None

    @property
    def full_name(self) -> str | None:
        if self.full_name_encrypted:
            return phi_crypto.decrypt(self.full_name_encrypted)
        return None

    @full_name.setter
    def full_name(self, value: str | None):
        if value:
            self.full_name_encrypted = phi_crypto.encrypt(value)
        else:
            self.full_name_encrypted = None

    @property
    def dob(self) -> str | None:
        if self.dob_encrypted:
            return phi_crypto.decrypt(self.dob_encrypted)
        return None

    @dob.setter
    def dob(self, value: str | None):
        if value:
            self.dob_encrypted = phi_crypto.encrypt(value)
        else:
            self.dob_encrypted = None

    @property
    def email(self) -> str | None:
        if self.email_encrypted:
            return phi_crypto.decrypt(self.email_encrypted)
        return None

    @email.setter
    def email(self, value: str | None):
        if value:
            self.email_encrypted = phi_crypto.encrypt(value)
        else:
            self.email_encrypted = None

    @property
    def insurance_provider(self) -> str | None:
        if self.insurance_provider_encrypted:
            return phi_crypto.decrypt(self.insurance_provider_encrypted)
        return None

    @insurance_provider.setter
    def insurance_provider(self, value: str | None):
        if value:
            self.insurance_provider_encrypted = phi_crypto.encrypt(value)
        else:
            self.insurance_provider_encrypted = None

    @property
    def insurance_member_id(self) -> str | None:
        if self.insurance_member_id_encrypted:
            return phi_crypto.decrypt(self.insurance_member_id_encrypted)
        return None

    @insurance_member_id.setter
    def insurance_member_id(self, value: str | None):
        if value:
            self.insurance_member_id_encrypted = phi_crypto.encrypt(value)
        else:
            self.insurance_member_id_encrypted = None

    @property
    def notes(self) -> str | None:
        if self.notes_encrypted:
            return phi_crypto.decrypt(self.notes_encrypted)
        return None

    @notes.setter
    def notes(self, value: str | None):
        if value:
            self.notes_encrypted = phi_crypto.encrypt(value)
        else:
            self.notes_encrypted = None

    @property
    def age(self) -> int | None:
        """Calculate patient age safely from encrypted DOB."""
        dob_str = self.dob
        if not dob_str:
            return None
        try:
            # Handle YYYY-MM-DD, MM/DD/YYYY or similar standard formats
            clean_dob = dob_str.split("T")[0]
            if "-" in clean_dob:
                parts = [int(p) for p in clean_dob.split("-")]
                if len(parts) == 3:
                    if parts[0] > 1000:
                        birth_date = datetime.date(parts[0], parts[1], parts[2])
                    else:
                        birth_date = datetime.date(parts[2], parts[0], parts[1])
                    today = datetime.date.today()
                    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except Exception:
            return None
        return None

    def calculate_recall_status(self) -> str:
        """
        Calculates recall status tag for UI and operational queuing.
        Returns one of: 'exempt', 'overdue_60d', 'due_for_recall', 'up_to_date'.
        """
        if self.recall_opted_out:
            return "exempt"
        if not self.last_visit_date:
            return "due_for_recall"
        
        today = datetime.date.today()
        days_since = (today - self.last_visit_date).days

        if days_since >= 150: # Standard 90d recall + 60d grace
            return "overdue_60d"
        elif days_since >= 90:
            return "due_for_recall"
        elif days_since >= 60 and self.churn_risk_score and self.churn_risk_score > 0.5:
            return "due_for_recall"
        else:
            return "up_to_date"
