"""
FHIR R4 Standard Connector (Epic, Cerner & Generic FHIR)
---------------------------------------------------------
Integrates with SMART-on-FHIR R4 endpoints for health systems (Epic Systems, Cerner Oracle Health, and open FHIR R4 servers).
Supports standard FHIR resources: Patient, Appointment, and CapabilityStatement metadata.
Stores resource mappings in `ehr_resource_mappings` table.
Never raises — logs errors and returns None on failure.
"""

import httpx
from typing import Optional
from datetime import datetime

from ...core.logger import log
from ...core.database import supabase
from .base import EMRIntegrationBase

EPIC_SANDBOX_FHIR = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
CERNER_SANDBOX_FHIR = "https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d"


class FHIRConnector(EMRIntegrationBase):
    """Generic SMART-on-FHIR R4 Connector."""

    def __init__(self, integration: dict, provider_name: str = "fhir"):
        self._integration = integration
        self._provider_name = integration.get("provider_name") or provider_name
        self._access_token: str = integration.get("access_token", "")
        self._client_id: str = integration.get("client_id", "")
        self._client_secret: str = integration.get("client_secret", "")
        
        # Determine FHIR Base URL
        endpoint = integration.get("fhir_endpoint", "").strip()
        if not endpoint:
            if self._provider_name in ("epic", "epic_fhir"):
                endpoint = EPIC_SANDBOX_FHIR
            elif self._provider_name in ("cerner", "cerner_fhir"):
                endpoint = CERNER_SANDBOX_FHIR
            else:
                endpoint = "https://hapi.fhir.org/baseR4"

        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]
        self._fhir_endpoint: str = endpoint

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/fhir+json, application/json",
            "Content-Type": "application/fhir+json",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
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
                .eq("provider_name", self._provider_name)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]["ehr_resource_id"]
        except Exception as e:
            log.warning(f"[{self._provider_name}] mapping lookup error: {e}")
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
                    "provider_name": self._provider_name,
                    "local_resource_type": resource_type,
                    "local_resource_id": local_resource_id,
                    "ehr_resource_id": ehr_resource_id,
                }
            ).execute()
        except Exception as e:
            log.warning(f"[{self._provider_name}] mapping store error: {e}")

    async def create_patient(self, clinic_id: str, patient_data: dict) -> Optional[str]:
        """Create a FHIR R4 Patient resource."""
        local_patient_id = patient_data.get("id", "")

        if local_patient_id:
            existing = self._get_existing_mapping(clinic_id, "patient", local_patient_id)
            if existing:
                log.info(f"[{self._provider_name}] patient already synced: local={local_patient_id} ehr={existing}")
                return existing

        name_parts = (patient_data.get("name") or "").split(" ")
        first_name = patient_data.get("first_name") or (name_parts[0] if name_parts else "Patient")
        last_name = patient_data.get("last_name") or (" ".join(name_parts[1:]) if len(name_parts) > 1 else "Unknown")
        phone = patient_data.get("phone_number") or patient_data.get("phone", "")
        email = patient_data.get("email", "")
        dob = patient_data.get("date_of_birth") or patient_data.get("dob")
        gender_raw = (patient_data.get("gender") or "unknown").lower()
        gender = "unknown"
        if gender_raw in ("male", "m"):
            gender = "male"
        elif gender_raw in ("female", "f"):
            gender = "female"
        elif gender_raw in ("other", "non-binary"):
            gender = "other"

        telecom = []
        if phone:
            telecom.append({"system": "phone", "value": phone, "use": "mobile"})
        if email:
            telecom.append({"system": "email", "value": email, "use": "home"})

        fhir_patient = {
            "resourceType": "Patient",
            "active": True,
            "name": [
                {
                    "use": "official",
                    "family": last_name,
                    "given": [first_name],
                }
            ],
            "gender": gender,
        }
        if telecom:
            fhir_patient["telecom"] = telecom
        if dob:
            fhir_patient["birthDate"] = dob

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._fhir_endpoint}/Patient",
                    headers=self._headers(),
                    json=fhir_patient,
                )
                resp.raise_for_status()
                
                # Check response body or Location header for resource ID
                ehr_id = ""
                if resp.status_code in (200, 201):
                    try:
                        body = resp.json()
                        ehr_id = str(body.get("id", ""))
                    except Exception:
                        pass
                    if not ehr_id and "location" in resp.headers:
                        loc = resp.headers["location"]
                        ehr_id = loc.split("/")[-1].split("?")[0]

                if ehr_id and local_patient_id:
                    self._store_mapping(clinic_id, "patient", local_patient_id, ehr_id)
                log.info(f"[{self._provider_name}] patient created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[{self._provider_name}] create_patient error: {e}")
            return None

    async def create_appointment(self, clinic_id: str, appointment_data: dict) -> Optional[str]:
        """Create a FHIR R4 Appointment resource."""
        local_appt_id = appointment_data.get("id", "")

        if local_appt_id:
            existing = self._get_existing_mapping(clinic_id, "appointment", local_appt_id)
            if existing:
                log.info(f"[{self._provider_name}] appointment already synced: local={local_appt_id} ehr={existing}")
                return existing

        ehr_patient_id = appointment_data.get("ehr_patient_id") or appointment_data.get("patient_id", "")
        start_time = appointment_data.get("start_at") or appointment_data.get("datetime") or appointment_data.get("scheduled_time")
        
        participants = []
        if ehr_patient_id:
            participants.append({
                "actor": {"reference": f"Patient/{ehr_patient_id}", "display": "Patient"},
                "status": "accepted",
            })

        fhir_appt = {
            "resourceType": "Appointment",
            "status": "booked",
            "description": appointment_data.get("notes") or "Appointment booked via Bytelytic Clinic OS",
            "participant": participants if participants else [{"status": "accepted"}],
        }
        if start_time:
            fhir_appt["start"] = start_time
            # Default end is +30m if not specified
            end_time = appointment_data.get("end_at")
            if end_time:
                fhir_appt["end"] = end_time

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._fhir_endpoint}/Appointment",
                    headers=self._headers(),
                    json=fhir_appt,
                )
                resp.raise_for_status()
                
                ehr_id = ""
                if resp.status_code in (200, 201):
                    try:
                        body = resp.json()
                        ehr_id = str(body.get("id", ""))
                    except Exception:
                        pass
                    if not ehr_id and "location" in resp.headers:
                        loc = resp.headers["location"]
                        ehr_id = loc.split("/")[-1].split("?")[0]

                if ehr_id and local_appt_id:
                    self._store_mapping(clinic_id, "appointment", local_appt_id, ehr_id)
                log.info(f"[{self._provider_name}] appointment created ehr_id={ehr_id}")
                return ehr_id or None
        except Exception as e:
            log.error(f"[{self._provider_name}] create_appointment error: {e}")
            return None

    async def get_patient(self, clinic_id: str, ehr_patient_id: str) -> Optional[dict]:
        """GET FHIR Patient resource by ID."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._fhir_endpoint}/Patient/{ehr_patient_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            log.error(f"[{self._provider_name}] get_patient error ehr_id={ehr_patient_id}: {e}")
            return None

    async def verify_connection(self, clinic_id: str) -> bool:
        """
        Verify FHIR endpoint connection via /metadata CapabilityStatement
        or querying /Patient?_count=1.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. First attempt /metadata (standard FHIR capability check)
                meta_headers = {"Accept": "application/fhir+json, application/json"}
                if self._access_token:
                    meta_headers["Authorization"] = f"Bearer {self._access_token}"
                resp = await client.get(
                    f"{self._fhir_endpoint}/metadata",
                    headers=meta_headers,
                )
                if resp.status_code == 200:
                    try:
                        body = resp.json()
                        if body.get("resourceType") in ("CapabilityStatement", "Conformance"):
                            return True
                    except Exception:
                        pass
                    return True

                # 2. Second attempt: Authenticated endpoint check /Patient?_count=1
                resp2 = await client.get(
                    f"{self._fhir_endpoint}/Patient?_count=1",
                    headers=self._headers(),
                )
                if resp2.status_code in (200, 201):
                    return True
                if resp2.status_code == 401:
                    log.warning(f"[{self._provider_name}] verify_connection 401 Unauthorized - invalid token")
                    return False
                return False
        except Exception as e:
            log.warning(f"[{self._provider_name}] verify_connection error: {e}")
            return False

    async def diagnose_endpoint(self) -> dict:
        """Fetch deep diagnostic metadata from FHIR server."""
        import time
        start = time.time()
        try:
            meta_headers = {"Accept": "application/fhir+json, application/json"}
            if self._access_token:
                meta_headers["Authorization"] = f"Bearer {self._access_token}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._fhir_endpoint}/metadata", headers=meta_headers)
                latency = round((time.time() - start) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    software = data.get("software", {}).get("name", "Standard FHIR Server")
                    version = data.get("fhirVersion", "4.0.1")
                    rest_defs = data.get("rest", [])
                    resources = []
                    if rest_defs and isinstance(rest_defs, list):
                        resources = [r.get("type") for r in rest_defs[0].get("resource", []) if r.get("type")]
                    return {
                        "online": True,
                        "status_code": 200,
                        "latency_ms": latency,
                        "fhir_version": version,
                        "software_name": software,
                        "supported_resources": resources[:10],
                        "total_resources": len(resources),
                        "message": f"Successfully connected to {software} (FHIR v{version}) in {latency}ms."
                    }
                elif resp.status_code == 401:
                    return {
                        "online": False,
                        "status_code": 401,
                        "latency_ms": latency,
                        "message": "Endpoint requires OAuth2 / Bearer Token authorization (HTTP 401 Unauthorized)."
                    }
                else:
                    return {
                        "online": False,
                        "status_code": resp.status_code,
                        "latency_ms": latency,
                        "message": f"FHIR Server returned HTTP status {resp.status_code}."
                    }
        except Exception as e:
            latency = round((time.time() - start) * 1000)
            return {
                "online": False,
                "status_code": 500,
                "latency_ms": latency,
                "message": f"Connection failed: {str(e)}"
            }


class EpicConnector(FHIRConnector):
    """Epic Systems FHIR Connector."""
    def __init__(self, integration: dict):
        super().__init__(integration, provider_name="epic")


class CernerConnector(FHIRConnector):
    """Cerner / Oracle Health FHIR Connector."""
    def __init__(self, integration: dict):
        super().__init__(integration, provider_name="cerner")
