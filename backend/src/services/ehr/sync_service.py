"""
EHR/EMR Automatic Sync Service
--------------------------------
Handles background orchestration of syncing:
1. Outbound: patients and appointments to active clinic integrations.
2. Inbound: EHR -> Bytelytic appointments.
3. CALL-E Clinical Notes: CALL-E call summaries and transcripts -> EHR patient notes/encounters.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from ...core.database import supabase
from ...core.logger import log
from .jane_connector import JaneConnector
from .simplepractice_connector import SimplePracticeConnector
from .zapier_connector import ZapierConnector
from .drchrono_connector import DrChronoConnector
from .athena_connector import AthenaHealthConnector
from .fhir_connector import FHIRConnector, EpicConnector, CernerConnector
from .webpt_connector import WebPTConnector
from .kareo_connector import KareoConnector

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
    elif provider_clean in ("webpt", "web_pt"):
        return WebPTConnector(integration)
    elif provider_clean in ("kareo", "tebra"):
        return KareoConnector(integration)
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

    async def sync_call_notes(
        self,
        clinic_id: str,
        patient_id: Optional[str],
        summary: str,
        transcript: Optional[str] = None,
        call_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bidirectional CALL-E -> EHR Notes Sync.
        Pushes AI conversation summary, structured findings, and call transcript
        directly into the patient's EHR clinical notes / encounter documents.
        """
        if not patient_id or not (summary or transcript):
            return {"synced": False, "reason": "Missing patient_id or note content"}

        loop = asyncio.get_event_loop()
        results = {}
        note_title = title or f"CALL-E AI Encounter Note ({datetime.now(timezone.utc).strftime('%b %d, %Y')})"
        note_content = f"SUMMARY:\n{summary}\n\n"
        if transcript:
            note_content += f"TRANSCRIPT:\n{transcript}"

        try:
            def _fetch_active():
                return (
                    supabase.table("ehr_integrations")
                    .select("*")
                    .eq("clinic_id", clinic_id)
                    .eq("is_active", True)
                    .execute()
                )
            integrations_res = await loop.run_in_executor(None, _fetch_active)
            integrations = integrations_res.data or []

            for integration in integrations:
                provider = integration.get("provider_name", "")
                try:
                    connector = get_connector(provider, integration)
                    note_payload = {
                        "local_patient_id": patient_id,
                        "title": note_title,
                        "summary": summary,
                        "content": note_content,
                        "call_id": call_id,
                        "date": datetime.now(timezone.utc).isoformat(),
                    }
                    note_id = await connector.create_clinical_note(clinic_id, note_payload)
                    results[provider] = {"success": note_id is not None, "note_id": note_id}
                    log.info(f"[ehr_sync] CALL-E note for patient {patient_id} synced to {provider}: note_id={note_id}")
                except Exception as e:
                    log.error(f"[ehr_sync] Error syncing CALL-E note to {provider}: {e}")
                    results[provider] = {"success": False, "error": str(e)}

            return {"synced": True, "results": results}
        except Exception as e:
            log.error(f"[ehr_sync] sync_call_notes error clinic={clinic_id} patient={patient_id}: {e}")
            return {"synced": False, "error": str(e)}

    async def sync_inbound_appointments(self, clinic_id: str) -> Dict[str, Any]:
        """
        Bidirectional EHR -> Bytelytic Inbound Sync.
        Pulls newly booked/updated appointments from connected EHR systems
        and upserts them into Bytelytic's `appointments` table with proper mappings.
        """
        loop = asyncio.get_event_loop()
        results = {}

        try:
            def _fetch_active():
                return (
                    supabase.table("ehr_integrations")
                    .select("*")
                    .eq("clinic_id", clinic_id)
                    .eq("is_active", True)
                    .eq("sync_enabled", True)
                    .execute()
                )
            integrations_res = await loop.run_in_executor(None, _fetch_active)
            integrations = integrations_res.data or []

            for integration in integrations:
                provider = integration.get("provider_name", "")
                try:
                    connector = get_connector(provider, integration)
                    raw_appts = await connector.fetch_appointments(clinic_id)
                    synced_count = 0

                    for appt in raw_appts:
                        # Extract external appointment ID & details
                        ext_id = str(appt.get("id") or appt.get("appointment_id") or appt.get("appointmentid", ""))
                        if not ext_id:
                            continue

                        # Check if already mapped
                        def _check_mapping(p=provider, e=ext_id):
                            return (
                                supabase.table("ehr_resource_mappings")
                                .select("local_resource_id")
                                .eq("clinic_id", clinic_id)
                                .eq("provider_name", p)
                                .eq("local_resource_type", "appointment")
                                .eq("ehr_resource_id", e)
                                .limit(1)
                                .execute()
                            )
                        map_res = await loop.run_in_executor(None, _check_mapping)

                        appt_time = appt.get("start") or appt.get("start_time") or appt.get("scheduled_time") or appt.get("date")
                        if not appt_time:
                            continue

                        if not map_res.data:
                            # Insert new appointment into local Bytelytic database
                            new_row = {
                                "clinic_id": clinic_id,
                                "appointment_type": appt.get("type") or appt.get("description") or "EHR Inbound Booking",
                                "datetime": appt_time,
                                "duration_minutes": appt.get("duration") or appt.get("duration_minutes") or 30,
                                "status": "confirmed" if str(appt.get("status", "")).lower() in ("booked", "confirmed") else "scheduled",
                                "booked_by": f"ehr_{provider}",
                                "notes": f"Synced from {provider.upper()} (EHR ID: {ext_id})",
                            }
                            def _insert(row=new_row):
                                return supabase.table("appointments").insert(row).execute()
                            ins_res = await loop.run_in_executor(None, _insert)
                            if ins_res.data:
                                local_id = ins_res.data[0]["id"]
                                # Store mapping
                                def _store_map(p=provider, l_id=local_id, e_id=ext_id):
                                    return supabase.table("ehr_resource_mappings").insert({
                                        "clinic_id": clinic_id,
                                        "provider_name": p,
                                        "local_resource_type": "appointment",
                                        "local_resource_id": l_id,
                                        "ehr_resource_id": e_id,
                                    }).execute()
                                await loop.run_in_executor(None, _store_map)
                                synced_count += 1

                    results[provider] = {"success": True, "appointments_synced": synced_count}
                except Exception as err:
                    log.error(f"[ehr_sync] Inbound appointment sync failed for {provider}: {err}")
                    results[provider] = {"success": False, "error": str(err)}

            return {"inbound_synced": True, "results": results}
        except Exception as e:
            log.error(f"[ehr_sync] sync_inbound_appointments error clinic={clinic_id}: {e}")
            return {"inbound_synced": False, "error": str(e)}

ehr_sync_service = EhrSyncService()
