import uuid
from typing import Optional, Dict, Any
from datetime import date, datetime, timezone
from sqlalchemy import String, Integer, Text, Date, DateTime, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base, TenantMixin, UUIDMixin, TimestampMixin, SoftDeleteMixin
from src.core.encryption import phi_crypto


class PriorAuthRequest(Base, TenantMixin, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Prior Authorization Request model with HIPAA-compliant AES-256-GCM encryption
    for patient member ID, insurance group number, and authorization codes.
    """
    __tablename__ = 'prior_auth_requests'

    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Insurance Info
    insurance_provider_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    insurance_prior_auth_phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Encrypted PHI Fields (AES-256-GCM)
    patient_member_id_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    patient_group_number_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    authorization_number_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    
    # Clinical Codes
    cpt_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cpt_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icd10_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    icd10_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Request Metadata
    urgency: Mapped[Optional[str]] = mapped_column(String, default='standard', nullable=True)
    requested_service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # CALL-E Telephony & AI Voice State
    calle_task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    call_status: Mapped[Optional[str]] = mapped_column(String, default='pending', index=True, nullable=True)
    call_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    call_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    call_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    call_recording_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Result & Outcome
    auth_status: Mapped[Optional[str]] = mapped_column(String, default='pending', nullable=True)
    denial_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    denial_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    insurance_agent_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expected_decision_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    additional_info_required: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    call_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── PHI Encrypted Properties ──────────────────────────────────────────────

    @property
    def patient_member_id(self) -> Optional[str]:
        if self.patient_member_id_encrypted:
            try:
                return phi_crypto.decrypt(self.patient_member_id_encrypted)
            except Exception:
                return None
        return None
        
    @patient_member_id.setter
    def patient_member_id(self, value: Optional[str]):
        if value is not None and value != "":
            self.patient_member_id_encrypted = phi_crypto.encrypt(str(value))
        else:
            self.patient_member_id_encrypted = None
            
    @property
    def patient_group_number(self) -> Optional[str]:
        if self.patient_group_number_encrypted:
            try:
                return phi_crypto.decrypt(self.patient_group_number_encrypted)
            except Exception:
                return None
        return None
        
    @patient_group_number.setter
    def patient_group_number(self, value: Optional[str]):
        if value is not None and value != "":
            self.patient_group_number_encrypted = phi_crypto.encrypt(str(value))
        else:
            self.patient_group_number_encrypted = None

    @property
    def authorization_number(self) -> Optional[str]:
        if self.authorization_number_encrypted:
            try:
                return phi_crypto.decrypt(self.authorization_number_encrypted)
            except Exception:
                return None
        return None
        
    @authorization_number.setter
    def authorization_number(self, value: Optional[str]):
        if value is not None and value != "":
            self.authorization_number_encrypted = phi_crypto.encrypt(str(value))
        else:
            self.authorization_number_encrypted = None

    def to_dict(self, user_role: str = "clinician") -> Dict[str, Any]:
        """Serialize model into dict with role-based access control on PHI."""
        auth_num = None
        if self.authorization_number_encrypted:
            auth_num = self.authorization_number if user_role in ["owner", "clinician", "admin"] else "***"

        member_id_val = None
        if self.patient_member_id_encrypted:
            raw_mem = self.patient_member_id
            if user_role in ["owner", "clinician", "admin"]:
                member_id_val = raw_mem
            elif raw_mem and len(raw_mem) > 4:
                member_id_val = f"***{raw_mem[-4:]}"
            else:
                member_id_val = "***"

        return {
            "id": str(self.id) if self.id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "patient_id": str(self.patient_id) if self.patient_id else None,
            "provider_id": str(self.provider_id) if self.provider_id else None,
            "appointment_id": str(self.appointment_id) if self.appointment_id else None,
            "insurance_provider_name": self.insurance_provider_name,
            "insurance_prior_auth_phone": self.insurance_prior_auth_phone,
            "patient_member_id": member_id_val,
            "cpt_code": self.cpt_code,
            "cpt_description": self.cpt_description,
            "icd10_code": self.icd10_code,
            "icd10_description": self.icd10_description,
            "urgency": self.urgency or "standard",
            "requested_service_date": self.requested_service_date.isoformat() if self.requested_service_date else None,
            "calle_task_id": self.calle_task_id,
            "call_status": self.call_status,
            "auth_status": self.auth_status,
            "status": self.auth_status,
            "authorization_number": auth_num,
            "auth_number": auth_num,
            "denial_reason": self.denial_reason,
            "denial_code": self.denial_code,
            "reference_number": self.reference_number,
            "insurance_agent_name": self.insurance_agent_name,
            "call_duration_seconds": self.call_duration_seconds,
            "call_summary": self.call_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
