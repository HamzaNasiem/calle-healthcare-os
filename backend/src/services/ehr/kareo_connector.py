"""
Kareo (Tebra) EHR Connector
---------------------------
Integrates with Kareo / Tebra clinical and billing API.
Supports bidirectional sync for Patients, Appointments, and CALL-E Clinical Notes.
Stores resource mappings in `ehr_resource_mappings` table.
"""

import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from ...core.logger import log
from ...core.database import supabase
from .base import EMRIntegrationBase

KAREO_BASE_URL = "https://api.kareo.com/v1"


class KareoConnector(EMRIntegrationBase):
    """Connector for Kareo / Tebra EHR API."""

    def __init__(self, integration: dict):
        self._integration = integration
        self._access_token: str = integration.get("access_token", "")
        self._client_id: str = integration.get("client_id", "")
        self._client_secret: str = integration.get("client_secret", "")
        self._practice_id: str = integration.get("provider_clinic_id", "")
        self._base_url: str = (integration.get("fhir_endpoint") or KAREO_BASE_URL).rstrip("/")

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
            headers["x-kareo-token"] = self._access_token
        if self._practice_id:
            headers["x-kareo-practice-id"] = self._practice_id
        return headers

    def _get_existing_mapping(
        self, clinic_id: str, resource_type: str, local_resource_id: str
    ) -> Optional[str]:
        """Return existing EHR resource ID if mapping exists."""
        try:
            res = (
                supabase.table("ehr_resource_mappings")
                .select("ehr_resource_id")
                .eq("clinic_id", clinic_id)
                .eq("local_resource_type", resource_type)
                .eq("local_resource_id", local_resource_id)
                .eq("provider_name", "kareo")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]["ehr_resource_id"]
        except Exception as e:
            log.warning(f"[kareo] mapping lookup error: {e}")
        return None

    def _store_mapping(
        self,
        clinic_id: str,
        resource_type: str,
        local_resource_id: str,
        ehr_resource_id: str,
    ) -> None:
        """Persist local->EHR resource mapping."""
        try:
            supabase.table("ehr_resource_mappings").insert(
                {
                    "clinic_id": clinic_id,
                    "provider_name": "kareo",
                    "local_resource_type": resource_type,
                    "local_resource_id": local_resource_id,
                    "ehr_resource_id": ehr_resource_id,
                }
            ).execute()
        except Exception as e:
            log.warning(f"[kareo] mapping store error: {e}")

    async def create_patient(self, clinic_id: str, patient_data: dict) -> Optional[str]:
        """Register patient in Kareo."""
        local_patient_id = patient_data.get("id", "")

        if local_patient_id:
            existing = self._get_existing_mapping(clinic_id, "patient", local_patient_id)
            if existing:
                log.info(f"[kareo] patient already synced: local={local_patient_id} ehr={existing}")
                return existing

        name_parts = (patient_data.get("name") or "").split(" ")
        first_name = patient_data.get("first_name") or (name_parts[0] if name_parts else "Patient")
        last_name = patient_data.get("last_name") or (" ".join(name_parts[1:]) if len(name_parts) > 1 else "Unknown")

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "dob": patient_data.get("date_of_birth") or patient_data.get("dob") or "1980-01-01",
            "mobile_phone": patient_data.get("phone_number") or patient_data.get("phone", ""),
            "email": patient_data.get("email", ""),
            "practice_id": self._practice_id or clinic_id,
            "insurance_plan": patient_data.get("insurance_provider"),
            "insurance_id": patient_data.get("insurance_member_id"),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/patients",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                ehr_id = str(data.get("id") or data.get("patient_id", ""))

                if ehr_id and local_patient_id:
                    self._store_mapping(clinic_id, "patient", local_patient_id, ehr_id)
                log.info(f"[kareo] patient created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[kareo] create_patient error: {e}")
            return None

    async def create_appointment(self, clinic_id: str, appointment_data: dict) -> Optional[str]:
        """Book appointment in Kareo."""
        local_appt_id = appointment_data.get("id", "")

        if local_appt_id:
            existing = self._get_existing_mapping(clinic_id, "appointment", local_appt_id)
            if existing:
                log.info(f"[kareo] appointment already synced: local={local_appt_id} ehr={existing}")
                return existing

        patient_id = appointment_data.get("ehr_patient_id") or appointment_data.get("patient_id", "")
        start_time = appointment_data.get("start_at") or appointment_data.get("datetime") or appointment_data.get("scheduled_time")

        payload = {
            "patient_id": str(patient_id),
            "start_time": start_time,
            "duration": appointment_data.get("duration_minutes", 30),
            "reason": appointment_data.get("notes", "Appointment via CALL-E Voice Receptionist"),
            "status": "scheduled",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/appointments",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                ehr_id = str(data.get("id") or data.get("appointment_id", ""))

                if ehr_id and local_appt_id:
                    self._store_mapping(clinic_id, "appointment", local_appt_id, ehr_id)
                log.info(f"[kareo] appointment created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[kareo] create_appointment error: {e}")
            return None

    async def create_clinical_note(self, clinic_id: str, note_data: dict) -> Optional[str]:
        """Push CALL-E telephone encounter note or call summary to Kareo."""
        ehr_patient_id = note_data.get("ehr_patient_id")
        if not ehr_patient_id and note_data.get("local_patient_id"):
            ehr_patient_id = self._get_existing_mapping(clinic_id, "patient", note_data["local_patient_id"])

        if not ehr_patient_id:
            log.warning(f"[kareo] cannot create note: patient not mapped to Kareo")
            return None

        payload = {
            "patient_id": ehr_patient_id,
            "title": note_data.get("title", "CALL-E Voice AI Clinical Note"),
            "date": note_data.get("date", datetime.now(timezone.utc).isoformat()),
            "content": note_data.get("content") or note_data.get("summary") or note_data.get("transcript", ""),
            "document_type": "Telephone Encounter",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/patients/{ehr_patient_id}/encounters",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                note_id = str(data.get("id") or data.get("encounter_id", ""))
                log.info(f"[kareo] clinical note synced to patient {ehr_patient_id}: note_id={note_id}")
                return note_id or None
        except Exception as e:
            log.error(f"[kareo] create_clinical_note error: {e}")
            return None

    async def fetch_appointments(self, clinic_id: str, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch appointments from Kareo for inbound sync."""
        try:
            params = {}
            if start_date:
                params["start_date"] = start_date

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/appointments",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("appointments", [])
        except Exception as e:
            log.error(f"[kareo] fetch_appointments error: {e}")
            return []

    async def get_patient(self, clinic_id: str, ehr_patient_id: str) -> Optional[dict]:
        """Fetch patient from Kareo."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/patients/{ehr_patient_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            log.error(f"[kareo] get_patient error ehr_id={ehr_patient_id}: {e}")
            return None

    async def verify_connection(self, clinic_id: str) -> bool:
        """Verify connection to Kareo API endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url}/ping", headers=self._headers())
                if resp.status_code in (200, 201):
                    return True
                resp2 = await client.get(f"{self._base_url}/patients?limit=1", headers=self._headers())
                return resp2.status_code in (200, 201)
        except Exception as e:
            log.warning(f"[kareo] verify_connection error: {e}")
            return False
