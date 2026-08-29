"""
SimplePractice EHR Connector
-----------------------------
Integrates with SimplePractice's REST API v1 using OAuth2 bearer tokens.
Stores resource mappings in `ehr_resource_mappings` after successful creates.
Never raises — logs errors and returns None on failure.
"""

import httpx
from typing import Optional

from ...core.logger import log
from ...core.database import supabase
from .base import EMRIntegrationBase

SP_BASE_URL = "https://api.simplepractice.com/api/v1"


class SimplePracticeConnector(EMRIntegrationBase):
    """Connector for SimplePractice EHR."""

    def __init__(self, integration: dict):
        """
        Args:
            integration: Row from `ehr_integrations` table for this clinic/provider.
        """
        self._integration = integration
        self._access_token: str = integration.get("access_token", "")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_existing_mapping(
        self, clinic_id: str, resource_type: str, local_resource_id: str
    ) -> Optional[str]:
        """Return existing EHR resource ID if mapping already exists."""
        try:
            res = (
                supabase.table("ehr_resource_mappings")
                .select("ehr_resource_id")
                .eq("clinic_id", clinic_id)
                .eq("local_resource_type", resource_type)
                .eq("local_resource_id", local_resource_id)
                .eq("provider_name", "simplepractice")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]["ehr_resource_id"]
        except Exception as e:
            log.warning(f"[simplepractice] mapping lookup error: {e}")
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
                    "provider_name": "simplepractice",
                    "local_resource_type": resource_type,
                    "local_resource_id": local_resource_id,
                    "ehr_resource_id": ehr_resource_id,
                }
            ).execute()
        except Exception as e:
            log.warning(f"[simplepractice] mapping store error: {e}")

    # ------------------------------------------------------------------
    # EMRIntegrationBase implementation
    # ------------------------------------------------------------------

    async def create_patient(self, clinic_id: str, patient_data: dict) -> Optional[str]:
        """POST client to SimplePractice. Returns SP client ID or None."""
        local_patient_id = patient_data.get("id", "")

        # Deduplicate
        if local_patient_id:
            existing = self._get_existing_mapping(clinic_id, "patient", local_patient_id)
            if existing:
                log.info(
                    f"[simplepractice] patient already synced: local={local_patient_id} ehr={existing}"
                )
                return existing

        payload = {
            "first_name": patient_data.get("first_name") or patient_data.get("name", "").split(" ")[0],
            "last_name": patient_data.get("last_name")
            or (" ".join(patient_data.get("name", "").split(" ")[1:]) or ""),
            "email": patient_data.get("email", ""),
            "phone_number": patient_data.get("phone_number") or patient_data.get("phone", ""),
            "date_of_birth": patient_data.get("date_of_birth") or patient_data.get("dob", ""),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{SP_BASE_URL}/clients",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                sp_client = resp.json()
                ehr_id = str(sp_client.get("id", ""))
                if ehr_id and local_patient_id:
                    self._store_mapping(clinic_id, "patient", local_patient_id, ehr_id)
                log.info(f"[simplepractice] patient created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[simplepractice] create_patient error: {e}")
            return None

    async def create_appointment(self, clinic_id: str, appointment_data: dict) -> Optional[str]:
        """POST appointment to SimplePractice. Returns SP appointment ID or None."""
        local_appt_id = appointment_data.get("id", "")

        if local_appt_id:
            existing = self._get_existing_mapping(clinic_id, "appointment", local_appt_id)
            if existing:
                log.info(
                    f"[simplepractice] appointment already synced: local={local_appt_id} ehr={existing}"
                )
                return existing

        payload = {
            "starts_at": appointment_data.get("starts_at") or appointment_data.get("datetime", ""),
            "ends_at": appointment_data.get("ends_at", ""),
            "client_id": appointment_data.get("ehr_patient_id") or appointment_data.get("patient_id", ""),
            "clinician_id": appointment_data.get("clinician_id", ""),
            "appointment_type_id": appointment_data.get("appointment_type_id", ""),
            "notes": appointment_data.get("notes", ""),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{SP_BASE_URL}/appointments",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                sp_appt = resp.json()
                ehr_id = str(sp_appt.get("id", ""))
                if ehr_id and local_appt_id:
                    self._store_mapping(clinic_id, "appointment", local_appt_id, ehr_id)
                log.info(f"[simplepractice] appointment created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[simplepractice] create_appointment error: {e}")
            return None

    async def get_patient(self, clinic_id: str, ehr_patient_id: str) -> Optional[dict]:
        """GET client from SimplePractice by EHR client ID."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{SP_BASE_URL}/clients/{ehr_patient_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            log.error(f"[simplepractice] get_patient error ehr_id={ehr_patient_id}: {e}")
            return None

    async def verify_connection(self, clinic_id: str) -> bool:
        """Verify SimplePractice OAuth2 token is valid via /current_user."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{SP_BASE_URL}/current_user",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception as e:
            log.warning(f"[simplepractice] verify_connection error: {e}")
            return False
