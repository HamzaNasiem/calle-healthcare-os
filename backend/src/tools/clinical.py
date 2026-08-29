import hashlib
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.encryption import phi_crypto
from src.db.audit_engine import log_audit_event
from src.models.clinical_note import ClinicalNote
from src.models.patient import Patient

from .base_tool import BaseTool


class LogPatientSymptomsArgs(BaseModel):
    phone: str = Field(..., description="The 10-digit phone number of the patient.")
    symptom_summary: str = Field(..., description="A concise summary of the patient's symptoms.")

class LogPatientSymptomsTool(BaseTool):
    @property
    def name(self) -> str:
        return "log_patient_symptoms"
        
    @property
    def description(self) -> str:
        return "Logs the patient's symptoms or clinical notes securely."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return LogPatientSymptomsArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        import hashlib
        phone = args.get("phone")
        symptom_summary = args.get("symptom_summary")
        normalized_phone = phone.strip().replace(" ", "").replace("-", "")
        if not normalized_phone.startswith("+"):
            normalized_phone = "+" + normalized_phone.lstrip("0")
            
        phone_hash = hashlib.sha256(normalized_phone.encode('utf-8')).hexdigest()
        
        stmt = select(Patient).where(Patient.tenant_id == tenant_id, Patient.phone_hash == phone_hash, Patient.is_deleted == False)
        patient = (await db.execute(stmt)).scalars().first()
        
        if not patient:
            patient = Patient(
                tenant_id=tenant_id,
                phone_hash=phone_hash,
                full_name_encrypted=phi_crypto.encrypt("Unknown Caller"),
                dob_encrypted=phi_crypto.encrypt("1900-01-01"),
                phone_encrypted=phi_crypto.encrypt(normalized_phone),
                is_existing_patient=False,
                visit_count=0,
                is_deleted=False
            )
            db.add(patient)
            await db.flush()
            
        note_encrypted = phi_crypto.encrypt(symptom_summary)
        note_hash = hashlib.sha256(symptom_summary.encode('utf-8')).hexdigest()
        # Resolve real CallLog UUID
        from src.models.call_log import CallLog
        stmt_c = select(CallLog).where(CallLog.retell_call_id == call_id)
        call_log_obj = (await db.execute(stmt_c)).scalars().first()
        db_call_log_id = str(call_log_obj.id) if call_log_obj else call_id
        
        # Using ORM for clinical_note
        new_note = ClinicalNote(
            tenant_id=tenant_id,
            patient_id=patient.id,
            call_log_id=db_call_log_id,
            note_encrypted=note_encrypted,
            note_hash=note_hash,
            authored_by='ai_agent'
        )
        db.add(new_note)
        await db.flush()
        note_id = new_note.id
        
        await log_audit_event(
            db=db,
            tenant_id=tenant_id,
            actor_type="ai_agent",
            actor_id=db_call_log_id,
            action="CREATE",
            target_table="clinical_notes",
            target_id=str(note_id),
            target_patient_id=str(patient.id),
            fields_accessed=["note_encrypted"]
        )
        
        return {"success": True, "note_id": str(note_id)}

class CheckExistingPatientArgs(BaseModel):
    phone: str = Field(..., description="The 10-digit phone number of the caller.")

class CheckExistingPatientTool(BaseTool):
    @property
    def name(self) -> str:
        return "check_existing_patient"

    @property
    def description(self) -> str:
        return "Checks if a patient already exists in the system using their phone number."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return CheckExistingPatientArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        phone = args.get("phone")
        # phone is guaranteed by pydantic validation
        normalized_phone = phone.strip().replace(" ", "").replace("-", "")
        if not normalized_phone.startswith("+"):
            normalized_phone = "+" + normalized_phone.lstrip("0")
            
        phone_hash = hashlib.sha256(normalized_phone.encode('utf-8')).hexdigest()
        
        stmt = select(Patient).where(Patient.tenant_id == tenant_id, Patient.phone_hash == phone_hash, Patient.is_deleted == False)
        patient = (await db.execute(stmt)).scalars().first()
        
        if patient and patient.is_existing_patient:
            return {
                "is_existing_patient": True,
                "visit_count": patient.visit_count,
                "is_vip": patient.is_vip,
                "patient_id": str(patient.id),
                "last_visit_date": patient.last_visit_date.isoformat() if patient.last_visit_date else None
            }
        return {"is_existing_patient": False}
