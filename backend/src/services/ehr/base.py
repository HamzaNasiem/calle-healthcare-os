from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class EMRIntegrationBase(ABC):
    """Abstract base class for all EHR/EMR integrations."""

    @abstractmethod
    async def create_patient(self, clinic_id: str, patient_data: dict) -> Optional[str]:
        """Create patient in EHR. Returns EHR patient ID or None."""

    @abstractmethod
    async def create_appointment(self, clinic_id: str, appointment_data: dict) -> Optional[str]:
        """Create appointment in EHR. Returns EHR appointment ID or None."""

    @abstractmethod
    async def get_patient(self, clinic_id: str, ehr_patient_id: str) -> Optional[dict]:
        """Fetch patient from EHR by their EHR ID."""

    @abstractmethod
    async def verify_connection(self, clinic_id: str) -> bool:
        """Ping EHR to verify credentials are valid."""

    async def create_clinical_note(self, clinic_id: str, note_data: dict) -> Optional[str]:
        """Push CALL-E clinical note or call summary to EHR. Returns note/encounter ID or None."""
        return None

    async def fetch_appointments(self, clinic_id: str, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch recent appointments from EHR for inbound sync. Returns list of appointment dicts."""
        return []
