from abc import ABC, abstractmethod
from typing import Optional


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
