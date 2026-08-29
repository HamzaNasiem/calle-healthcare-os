"""
EHR/EMR Automatic Sync Service
--------------------------------
Handles background orchestration of syncing patients and appointments
to active clinic integrations (Jane App, SimplePractice, Zapier).
"""

import asyncio
from ...core.database import supabase
from ...core.logger import log
from .jane_connector import JaneConnector
from .simplepractice_connector import SimplePracticeConnector
from .zapier_connector import ZapierConnector
from .drchrono_connector import DrChronoConnector
from .athena_connector import AthenaHealthConnector
from .fhir_connector import FHIRConnector, EpicConnector, CernerConnector

def get_connector(provider_name: str, integration: dict):
    provider_clean = (provider_name or "").lower().strip()
    if provider_clean == "jane":
        return JaneConnector(integration)
    elif provider_clean == "simplepractice":
        return SimplePracticeConnector(integration)
    elif provider_clean == "zapier":
        return ZapierConnector(integration)
    elif provider_clean in ("drchrono", "dr_chrono"):
        return DrChronoConnector(integration)
    elif provider_clean in ("athenahealth", "athena", "athena_health"):
        return AthenaHealthConnector(integration)
    elif provider_clean in ("epic", "epic_fhir"):
        return EpicConnector(integration)
    elif provider_clean in ("cerner", "cerner_fhir"):
        return CernerConnector(integration)
    elif provider_clean in ("fhir", "fhir_r4", "smart_fhir"):
        return FHIRConnector(integration)
    raise ValueError(f"Unknown provider: {provider_name}")

class EhrSyncService:
    async def sync_patient(self, clinic_id: str, patient_id: str):
        """Sync patient to all active EHR integrations in the background."""
        try:
            loop = asyncio.get_event_loop()
            
            # Fetch patient details
            def _fetch_pat():
                return supabase.table("patients").select("*").eq("id", patient_id).eq("clinic_id", clinic_id).limit(1).execute()
            
            patient_res = await loop.run_in_executor(None, _fetch_pat)
            if not patient_res.data:
                log.warning(f"[ehr_sync] Patient {patient_id} not found for clinic {clinic_id}")
                return
            patient_data = patient_res.data[0]
            
            # Fetch active integrations for the clinic
            def _fetch_integrations():
                return supabase.table("ehr_integrations").select("*").eq("clinic_id", clinic_id).eq("is_active", True).execute()
            
            integrations_res = await loop.run_in_executor(None, _fetch_integrations)
            integrations = integrations_res.data or []
            
            for integration in integrations:
                provider = integration.get("provider_name", "")
                try:
                    connector = get_connector(provider, integration)
                    ehr_id = await connector.create_patient(clinic_id, patient_data)
                    log.info(f"[ehr_sync] Patient {patient_id} synced to {provider}: ehr_id={ehr_id}")
                except Exception as e:
                    log.error(f"[ehr_sync] Error syncing patient {patient_id} to {provider}: {e}")
        except Exception as e:
            log.error(f"[ehr_sync] sync_patient global error clinic={clinic_id} patient={patient_id}: {e}")

    async def sync_appointment(self, clinic_id: str, appointment_id: str):
        """Sync appointment to all active EHR integrations in the background."""
        try:
            loop = asyncio.get_event_loop()
            
            # Fetch appointment details
            def _fetch_appt():
                return supabase.table("appointments").select("*").eq("id", appointment_id).eq("clinic_id", clinic_id).limit(1).execute()
            
            appt_res = await loop.run_in_executor(None, _fetch_appt)
            if not appt_res.data:
                log.warning(f"[ehr_sync] Appointment {appointment_id} not found for clinic {clinic_id}")
                return
            appointment_data = appt_res.data[0]
            local_patient_id = appointment_data.get("patient_id")
            
            # Fetch active integrations for the clinic
            def _fetch_integrations():
                return supabase.table("ehr_integrations").select("*").eq("clinic_id", clinic_id).eq("is_active", True).execute()
            
            integrations_res = await loop.run_in_executor(None, _fetch_integrations)
            integrations = integrations_res.data or []
            
            for integration in integrations:
                provider = integration.get("provider_name", "")
                try:
                    connector = get_connector(provider, integration)
                    
                    # 1. Resolve patient mapping: Ensure patient is synced first
                    ehr_patient_id = None
                    if local_patient_id:
                        if hasattr(connector, "_get_existing_mapping"):
                            ehr_patient_id = connector._get_existing_mapping(clinic_id, "patient", local_patient_id)
                        
                        # If patient is not mapped, sync patient now
                        if not ehr_patient_id and provider != "zapier":
                            def _fetch_pat_sync():
                                return supabase.table("patients").select("*").eq("id", local_patient_id).execute()
                            pat_res = await loop.run_in_executor(None, _fetch_pat_sync)
                            if pat_res.data:
                                ehr_patient_id = await connector.create_patient(clinic_id, pat_res.data[0])
                    
                    # 2. Enrich appointment data with mapped EHR patient ID
                    appt_payload = dict(appointment_data)
                    if ehr_patient_id:
                        appt_payload["ehr_patient_id"] = ehr_patient_id
                    
                    # 3. Create appointment
                    ehr_id = await connector.create_appointment(clinic_id, appt_payload)
                    log.info(f"[ehr_sync] Appointment {appointment_id} synced to {provider}: ehr_id={ehr_id}")
                except Exception as e:
                    log.error(f"[ehr_sync] Error syncing appointment {appointment_id} to {provider}: {e}")
        except Exception as e:
            log.error(f"[ehr_sync] sync_appointment global error clinic={clinic_id} appt={appointment_id}: {e}")

ehr_sync_service = EhrSyncService()
