"""
AthenaHealth EHR Connector
---------------------------
Integrates with AthenaHealth API (REST & FHIR Preview/Production).
Stores resource mappings in `ehr_resource_mappings` table.
Never raises — logs errors and returns None on failure.
"""

import httpx
from typing import Optional

from ...core.logger import log
from ...core.database import supabase
from .base import EMRIntegrationBase

ATHENA_BASE_URL = "https://api.preview.platform.athenahealth.com/v1"


class AthenaHealthConnector(EMRIntegrationBase):
    """Connector for AthenaHealth EHR API."""

    def __init__(self, integration: dict):
        self._integration = integration
        self._access_token: str = integration.get("access_token", "")
        self._client_id: str = integration.get("client_id", "")
        self._client_secret: str = integration.get("client_secret", "")
        self._practice_id: str = integration.get("provider_clinic_id", "") or "195900"  # default preview sandbox
        self._base_url: str = integration.get("fhir_endpoint") or ATHENA_BASE_URL
        if self._base_url.endswith("/"):
            self._base_url = self._base_url[:-1]

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
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
                .eq("provider_name", "athenahealth")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]["ehr_resource_id"]
        except Exception as e:
            log.warning(f"[athenahealth] mapping lookup error: {e}")
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
                    "provider_name": "athenahealth",
                    "local_resource_type": resource_type,
                    "local_resource_id": local_resource_id,
                    "ehr_resource_id": ehr_resource_id,
                }
            ).execute()
        except Exception as e:
            log.warning(f"[athenahealth] mapping store error: {e}")

    async def create_patient(self, clinic_id: str, patient_data: dict) -> Optional[str]:
        """Create/register patient in AthenaHealth."""
        local_patient_id = patient_data.get("id", "")

        if local_patient_id:
            existing = self._get_existing_mapping(clinic_id, "patient", local_patient_id)
            if existing:
                log.info(f"[athenahealth] patient already synced: local={local_patient_id} ehr={existing}")
                return existing

        name_parts = (patient_data.get("name") or "").split(" ")
        first_name = patient_data.get("first_name") or (name_parts[0] if name_parts else "Patient")
        last_name = patient_data.get("last_name") or (" ".join(name_parts[1:]) if len(name_parts) > 1 else "Unknown")
        dob = patient_data.get("date_of_birth") or patient_data.get("dob") or "01/01/1980"
        # Convert YYYY-MM-DD to MM/DD/YYYY if needed
        if "-" in dob and len(dob) == 10:
            parts = dob.split("-")
            dob = f"{parts[1]}/{parts[2]}/{parts[0]}"

        payload = {
            "firstname": first_name,
            "lastname": last_name,
            "dob": dob,
            "mobilephone": patient_data.get("phone_number") or patient_data.get("phone", ""),
            "email": patient_data.get("email", ""),
            "departmentid": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/{self._practice_id}/patients",
                    headers=self._headers(),
                    data=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                ehr_id = ""
                if isinstance(data, list) and len(data) > 0:
                    ehr_id = str(data[0].get("patientid", ""))
                elif isinstance(data, dict):
                    ehr_id = str(data.get("patientid") or data.get("id", ""))

                if ehr_id and local_patient_id:
                    self._store_mapping(clinic_id, "patient", local_patient_id, ehr_id)
                log.info(f"[athenahealth] patient created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[athenahealth] create_patient error: {e}")
            return None

    async def create_appointment(self, clinic_id: str, appointment_data: dict) -> Optional[str]:
        """Book/create appointment in AthenaHealth."""
        local_appt_id = appointment_data.get("id", "")

        if local_appt_id:
            existing = self._get_existing_mapping(clinic_id, "appointment", local_appt_id)
            if existing:
                log.info(f"[athenahealth] appointment already synced: local={local_appt_id} ehr={existing}")
                return existing

        patient_id = appointment_data.get("ehr_patient_id") or appointment_data.get("patient_id", "")
        payload = {
            "patientid": str(patient_id),
            "appointmenttypeid": "1",
            "departmentid": "1",
            "reason": appointment_data.get("notes", "Bytelytic Clinic OS Booking"),
        }
        appointment_id = appointment_data.get("provider_appointment_id") or "1"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/{self._practice_id}/appointments/{appointment_id}",
                    headers=self._headers(),
                    data=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                ehr_id = ""
                if isinstance(data, list) and len(data) > 0:
                    ehr_id = str(data[0].get("appointmentid", ""))
                elif isinstance(data, dict):
                    ehr_id = str(data.get("appointmentid") or data.get("id", ""))

                if not ehr_id:
                    ehr_id = str(appointment_id)

                if ehr_id and local_appt_id:
                    self._store_mapping(clinic_id, "appointment", local_appt_id, ehr_id)
                log.info(f"[athenahealth] appointment created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[athenahealth] create_appointment error: {e}")
            return None

    async def get_patient(self, clinic_id: str, ehr_patient_id: str) -> Optional[dict]:
        """Fetch patient from AthenaHealth."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/{self._practice_id}/patients/{ehr_patient_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data[0] if isinstance(data, list) and len(data) > 0 else data
        except Exception as e:
            log.error(f"[athenahealth] get_patient error ehr_id={ehr_patient_id}: {e}")
            return None

    async def verify_connection(self, clinic_id: str) -> bool:
        """Verify connection to AthenaHealth via departments or ping endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url}/{self._practice_id}/departments",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code in (200, 201):
                    return True
                # Fallback check ping endpoint
                resp2 = await client.get(
                    f"{self._base_url}/ping",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                )
                return resp2.status_code == 200
        except Exception as e:
            log.warning(f"[athenahealth] verify_connection error: {e}")
            return False
