"""
DrChrono EHR Connector
-----------------------
Integrates with DrChrono REST API v4 to create/fetch patients and appointments.
Stores resource mappings in `ehr_resource_mappings` table.
Never raises — logs errors and returns None on failure.
"""

import httpx
from typing import Optional
from datetime import datetime, timedelta

from ...core.logger import log
from ...core.database import supabase
from .base import EMRIntegrationBase

DRCHRONO_BASE_URL = "https://drchrono.com/api"


class DrChronoConnector(EMRIntegrationBase):
    """Connector for DrChrono EHR API."""

    def __init__(self, integration: dict):
        self._integration = integration
        self._access_token: str = integration.get("access_token", "")
        self._refresh_token: str = integration.get("refresh_token", "")
        self._client_id: str = integration.get("client_id", "")
        self._client_secret: str = integration.get("client_secret", "")
        self._doctor_id: str = integration.get("provider_clinic_id", "")
        self._base_url: str = integration.get("fhir_endpoint") or DRCHRONO_BASE_URL
        if self._base_url.endswith("/"):
            self._base_url = self._base_url[:-1]

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

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
                .eq("provider_name", "drchrono")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]["ehr_resource_id"]
        except Exception as e:
            log.warning(f"[drchrono] mapping lookup error: {e}")
        return None

    def _store_mapping(
        self,
        clinic_id: str,
        resource_type: str,
        local_resource_id: str,
        ehr_resource_id: str,
    ) -> None:
        """Persist local→EHR resource mapping."""
        try:
            supabase.table("ehr_resource_mappings").insert(
                {
                    "clinic_id": clinic_id,
                    "provider_name": "drchrono",
                    "local_resource_type": resource_type,
                    "local_resource_id": local_resource_id,
                    "ehr_resource_id": ehr_resource_id,
                }
            ).execute()
        except Exception as e:
            log.warning(f"[drchrono] mapping store error: {e}")

    async def create_patient(self, clinic_id: str, patient_data: dict) -> Optional[str]:
        """Create patient in DrChrono."""
        local_patient_id = patient_data.get("id", "")

        if local_patient_id:
            existing = self._get_existing_mapping(clinic_id, "patient", local_patient_id)
            if existing:
                log.info(f"[drchrono] patient already synced: local={local_patient_id} ehr={existing}")
                return existing

        name_parts = (patient_data.get("name") or "").split(" ")
        first_name = patient_data.get("first_name") or (name_parts[0] if name_parts else "Patient")
        last_name = patient_data.get("last_name") or (" ".join(name_parts[1:]) if len(name_parts) > 1 else "Unknown")
        gender = patient_data.get("gender") or "Other"
        if gender.upper() in ("M", "MALE"):
            gender = "Male"
        elif gender.upper() in ("F", "FEMALE"):
            gender = "Female"
        else:
            gender = "Other"

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "date_of_birth": patient_data.get("date_of_birth") or patient_data.get("dob") or "1980-01-01",
            "cell_phone": patient_data.get("phone_number") or patient_data.get("phone", ""),
            "email": patient_data.get("email", ""),
        }
        if self._doctor_id:
            try:
                payload["doctor"] = int(self._doctor_id)
            except ValueError:
                payload["doctor"] = self._doctor_id

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/patients",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                ehr_id = str(data.get("id", ""))
                if ehr_id and local_patient_id:
                    self._store_mapping(clinic_id, "patient", local_patient_id, ehr_id)
                log.info(f"[drchrono] patient created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[drchrono] create_patient error: {e}")
            return None

    async def create_appointment(self, clinic_id: str, appointment_data: dict) -> Optional[str]:
        """Create appointment in DrChrono."""
        local_appt_id = appointment_data.get("id", "")

        if local_appt_id:
            existing = self._get_existing_mapping(clinic_id, "appointment", local_appt_id)
            if existing:
                log.info(f"[drchrono] appointment already synced: local={local_appt_id} ehr={existing}")
                return existing

        patient_id = appointment_data.get("ehr_patient_id") or appointment_data.get("patient_id")
        scheduled_time = appointment_data.get("scheduled_time") or appointment_data.get("datetime") or appointment_data.get("start_at", "")
        duration = appointment_data.get("duration") or appointment_data.get("duration_in_minutes", 30)

        payload = {
            "patient": int(patient_id) if str(patient_id).isdigit() else patient_id,
            "scheduled_time": scheduled_time,
            "duration": int(duration),
            "status": "Confirmed",
            "notes": appointment_data.get("notes", "Booked via Bytelytic Clinic OS"),
        }
        if self._doctor_id:
            try:
                payload["doctor"] = int(self._doctor_id)
            except ValueError:
                payload["doctor"] = self._doctor_id

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/appointments",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                ehr_id = str(data.get("id", ""))
                if ehr_id and local_appt_id:
                    self._store_mapping(clinic_id, "appointment", local_appt_id, ehr_id)
                log.info(f"[drchrono] appointment created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[drchrono] create_appointment error: {e}")
            return None

    async def get_patient(self, clinic_id: str, ehr_patient_id: str) -> Optional[dict]:
        """Fetch patient from DrChrono."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/patients/{ehr_patient_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            log.error(f"[drchrono] get_patient error ehr_id={ehr_patient_id}: {e}")
            return None

    async def create_clinical_note(self, clinic_id: str, note_data: dict) -> Optional[str]:
        """Push CALL-E encounter note to DrChrono clinical notes."""
        ehr_patient_id = note_data.get("ehr_patient_id")
        if not ehr_patient_id and note_data.get("local_patient_id"):
            ehr_patient_id = self._get_existing_mapping(clinic_id, "patient", note_data["local_patient_id"])

        if not ehr_patient_id:
            log.warning(f"[drchrono] cannot create note: patient not mapped to DrChrono")
            return None

        payload = {
            "patient": int(ehr_patient_id) if str(ehr_patient_id).isdigit() else ehr_patient_id,
            "appointment": note_data.get("ehr_appointment_id"),
            "clinical_note_sections": [
                {
                    "title": note_data.get("title", "CALL-E Voice AI Call Summary"),
                    "value": note_data.get("content") or note_data.get("summary") or note_data.get("transcript", "")
                }
            ]
        }
        if self._doctor_id:
            try:
                payload["doctor"] = int(self._doctor_id)
            except ValueError:
                payload["doctor"] = self._doctor_id

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/clinical_notes",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                note_id = str(data.get("id", ""))
                log.info(f"[drchrono] clinical note created: id={note_id}")
                return note_id or None
        except Exception as e:
            log.error(f"[drchrono] create_clinical_note error: {e}")
            return None

    async def fetch_appointments(self, clinic_id: str, start_date: Optional[str] = None) -> list:
        """Fetch appointments from DrChrono for inbound sync."""
        try:
            params = {}
            if start_date:
                params["date"] = start_date
            if self._doctor_id:
                params["doctor"] = self._doctor_id
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/appointments",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("results", []) if isinstance(data, dict) else (data or [])
        except Exception as e:
            log.error(f"[drchrono] fetch_appointments error: {e}")
            return []

    async def verify_connection(self, clinic_id: str) -> bool:
        """Verify DrChrono connection via users/current or doctors endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url}/users/current",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return True
                # Fallback check
                resp2 = await client.get(
                    f"{self._base_url}/doctors",
                    headers=self._headers(),
                )
                return resp2.status_code == 200
        except Exception as e:
            log.warning(f"[drchrono] verify_connection error: {e}")
            return False
