"""
EHR Integration Router
-----------------------
Endpoints for managing EHR/EMR integrations per clinic (DrChrono, AthenaHealth, Epic, Cerner, FHIR R4, Jane App, SimplePractice, Zapier).
All endpoints require owner role. DB calls wrapped in run_in_executor.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from ...core.database import supabase
from ...core.security import require_role, AuthenticatedUser
from ...services.ehr.jane_connector import JaneConnector
from ...services.ehr.simplepractice_connector import SimplePracticeConnector
from ...services.ehr.zapier_connector import ZapierConnector
from ...services.ehr.drchrono_connector import DrChronoConnector
from ...services.ehr.athena_connector import AthenaHealthConnector
from ...services.ehr.fhir_connector import FHIRConnector, EpicConnector, CernerConnector
from ...core.logger import log

router = APIRouter(prefix="/ehr", tags=["EHR Integration"])

SUPPORTED_PROVIDERS = {
    "drchrono": {
        "id": "drchrono",
        "name": "DrChrono EHR",
        "category": "General & Specialty EHR",
        "description": "Full REST API synchronization for patient demographics, clinical records, and appointments.",
        "auth_type": "oauth2",
        "fields": ["access_token", "refresh_token", "client_id", "client_secret", "provider_clinic_id", "fhir_endpoint"],
        "default_endpoint": "https://drchrono.com/api",
        "docs_url": "https://drchrono.com/api-docs/",
    },
    "athenahealth": {
        "id": "athenahealth",
        "name": "AthenaHealth",
        "category": "Enterprise Practice Management",
        "description": "Bi-directional patient registration and scheduling integration with AthenaNet / AthenaOne platform.",
        "auth_type": "oauth2_preview",
        "fields": ["access_token", "client_id", "client_secret", "provider_clinic_id", "fhir_endpoint"],
        "default_endpoint": "https://api.preview.platform.athenahealth.com/v1",
        "docs_url": "https://developer.athenahealth.com/",
    },
    "epic": {
        "id": "epic",
        "name": "Epic Systems (FHIR R4)",
        "category": "Hospital & Health System EHR",
        "description": "SMART-on-FHIR R4 standard bridge for hospital and clinical practice integrations with Epic Interconnect.",
        "auth_type": "fhir_oauth2",
        "fields": ["fhir_endpoint", "access_token", "client_id", "client_secret"],
        "default_endpoint": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        "docs_url": "https://open.epic.com/Interface/FHIR",
    },
    "cerner": {
        "id": "cerner",
        "name": "Cerner / Oracle Health (FHIR R4)",
        "category": "Hospital & Health System EHR",
        "description": "SMART-on-FHIR R4 connector for Millennium & Oracle Health clinical workflows.",
        "auth_type": "fhir_oauth2",
        "fields": ["fhir_endpoint", "access_token", "client_id", "client_secret"],
        "default_endpoint": "https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d",
        "docs_url": "https://fhir.cerner.com/",
    },
    "fhir": {
        "id": "fhir",
        "name": "Custom SMART on FHIR R4",
        "category": "Standard FHIR Server",
        "description": "Connect any ONC-certified FHIR R4 repository (Allscripts, NextGen, eClinicalWorks, HAPI FHIR).",
        "auth_type": "fhir_token",
        "fields": ["fhir_endpoint", "access_token", "client_id", "client_secret"],
        "default_endpoint": "https://hapi.fhir.org/baseR4",
        "docs_url": "https://hl7.org/fhir/R4/",
    },
    "jane": {
        "id": "jane",
        "name": "Jane App",
        "category": "Allied Health & Therapy",
        "description": "Integrated clinic management and booking for Canadian and US allied health practices.",
        "auth_type": "bearer_token",
        "fields": ["provider_clinic_id", "access_token"],
        "default_endpoint": "https://jane.app/api/v2",
        "docs_url": "https://jane.app/guide",
    },
    "simplepractice": {
        "id": "simplepractice",
        "name": "SimplePractice",
        "category": "Mental & Behavioral Health",
        "description": "Practice management system for mental health practitioners, social workers, and therapists.",
        "auth_type": "bearer_token",
        "fields": ["access_token"],
        "default_endpoint": "https://api.simplepractice.com/api/v1",
        "docs_url": "https://api.simplepractice.com/",
    },
    "zapier": {
        "id": "zapier",
        "name": "Zapier Webhook Bridge",
        "category": "Workflow Automation",
        "description": "Real-time webhook events for patient creations and appointment schedules to 5,000+ apps.",
        "auth_type": "webhook",
        "fields": ["webhook_secret"],
        "default_endpoint": "",
        "docs_url": "https://zapier.com/apps/webhook",
    },
}


def normalize_provider(name: str) -> str:
    """Normalize provider name to canonical identifier."""
    p = (name or "").lower().strip()
    if p in ("athena", "athena_health"):
        return "athenahealth"
    if p == "dr_chrono":
        return "drchrono"
    if p in ("epic_fhir", "epic_systems"):
        return "epic"
    if p in ("cerner_fhir", "oracle_health"):
        return "cerner"
    if p in ("smart_fhir", "fhir_r4"):
        return "fhir"
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class EHRIntegrationCreate(BaseModel):
    provider_name: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    fhir_endpoint: Optional[str] = None
    webhook_secret: Optional[str] = None
    provider_clinic_id: Optional[str] = None
    sync_frequency: Optional[str] = "realtime"  # realtime, 15m, 1h, daily, manual
    sync_enabled: Optional[bool] = True
    is_active: Optional[bool] = True
    settings: Optional[Dict[str, Any]] = None


class EHRIntegrationUpdate(BaseModel):
    sync_frequency: Optional[str] = None
    sync_enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    fhir_endpoint: Optional[str] = None
    webhook_secret: Optional[str] = None
    provider_clinic_id: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class EHRVerifyRequest(BaseModel):
    provider_name: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    fhir_endpoint: Optional[str] = None
    webhook_secret: Optional[str] = None
    provider_clinic_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Connector Factory
# ─────────────────────────────────────────────────────────────────────────────

def get_connector(provider_name: str, integration: dict):
    """Return the correct connector instance for the given provider."""
    canonical = normalize_provider(provider_name)
    if canonical == "jane":
        return JaneConnector(integration)
    elif canonical == "simplepractice":
        return SimplePracticeConnector(integration)
    elif canonical == "zapier":
        return ZapierConnector(integration)
    elif canonical == "drchrono":
        return DrChronoConnector(integration)
    elif canonical == "athenahealth":
        return AthenaHealthConnector(integration)
    elif canonical == "epic":
        return EpicConnector(integration)
    elif canonical == "cerner":
        return CernerConnector(integration)
    elif canonical == "fhir":
        return FHIRConnector(integration)
    raise ValueError(f"Unknown provider: {provider_name}")


# ─────────────────────────────────────────────────────────────────────────────
# Helper: run sync DB call in thread pool
# ─────────────────────────────────────────────────────────────────────────────

async def _run(fn):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/providers")
async def list_supported_providers(
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """List all supported EHR/EMR providers and their capabilities."""
    return {"data": list(SUPPORTED_PROVIDERS.values())}


@router.get("/integrations")
async def list_integrations(
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """List all EHR integrations for this clinic with complete configuration."""
    clinic_id = auth.clinic_id
    try:
        def _query():
            return (
                supabase.table("ehr_integrations")
                .select("*")
                .eq("clinic_id", clinic_id)
                .order("created_at", desc=True)
                .execute()
            )

        res = await _run(_query)
        rows = res.data or []
        
        # Clean sensitive fields for client response while preserving status flags
        cleaned = []
        for r in rows:
            provider = r.get("provider_name", "")
            item = dict(r)
            # Add helper status metadata
            item["has_access_token"] = bool(r.get("access_token"))
            item["has_client_secret"] = bool(r.get("client_secret"))
            item["has_refresh_token"] = bool(r.get("refresh_token"))
            item["canonical_provider"] = normalize_provider(provider)
            cleaned.append(item)

        return {"data": cleaned}
    except Exception as e:
        log.error(f"[ehr] list_integrations error clinic={clinic_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/integrations")
async def create_or_update_integration(
    body: EHRIntegrationCreate,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Create or update (upsert) an EHR integration for this clinic."""
    clinic_id = auth.clinic_id
    canonical_provider = normalize_provider(body.provider_name)
    
    if canonical_provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported EHR provider: {body.provider_name}. Supported: {', '.join(SUPPORTED_PROVIDERS.keys())}"
        )

    try:
        payload = {
            "clinic_id": clinic_id,
            "provider_name": canonical_provider,
            "is_active": body.is_active if body.is_active is not None else True,
            "sync_enabled": body.sync_enabled if body.sync_enabled is not None else True,
            "sync_frequency": body.sync_frequency or "realtime",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if body.access_token is not None:
            payload["access_token"] = body.access_token
        if body.refresh_token is not None:
            payload["refresh_token"] = body.refresh_token
        if body.client_id is not None:
            payload["client_id"] = body.client_id
        if body.client_secret is not None:
            payload["client_secret"] = body.client_secret
        if body.fhir_endpoint is not None:
            payload["fhir_endpoint"] = body.fhir_endpoint.strip()
        if body.webhook_secret is not None:
            payload["webhook_secret"] = body.webhook_secret.strip()
        if body.provider_clinic_id is not None:
            payload["provider_clinic_id"] = body.provider_clinic_id.strip()
        if body.settings is not None:
            payload["settings"] = body.settings

        def _upsert():
            return (
                supabase.table("ehr_integrations")
                .upsert(payload, on_conflict="clinic_id,provider_name")
                .execute()
            )

        res = await _run(_upsert)
        saved = res.data[0] if res.data else payload
        return {"data": saved, "message": f"{SUPPORTED_PROVIDERS.get(canonical_provider, {}).get('name', canonical_provider)} configuration saved successfully."}
    except Exception as e:
        log.error(f"[ehr] create_or_update error clinic={clinic_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/integrations/{provider_name}")
async def patch_integration(
    provider_name: str,
    body: EHRIntegrationUpdate,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Update settings (e.g. sync_frequency, sync_enabled, credentials) for an existing integration."""
    clinic_id = auth.clinic_id
    canonical_provider = normalize_provider(provider_name)

    if canonical_provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")

    try:
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if body.sync_frequency is not None:
            updates["sync_frequency"] = body.sync_frequency
        if body.sync_enabled is not None:
            updates["sync_enabled"] = body.sync_enabled
        if body.is_active is not None:
            updates["is_active"] = body.is_active
        if body.access_token is not None:
            updates["access_token"] = body.access_token
        if body.refresh_token is not None:
            updates["refresh_token"] = body.refresh_token
        if body.client_id is not None:
            updates["client_id"] = body.client_id
        if body.client_secret is not None:
            updates["client_secret"] = body.client_secret
        if body.fhir_endpoint is not None:
            updates["fhir_endpoint"] = body.fhir_endpoint.strip()
        if body.webhook_secret is not None:
            updates["webhook_secret"] = body.webhook_secret.strip()
        if body.provider_clinic_id is not None:
            updates["provider_clinic_id"] = body.provider_clinic_id.strip()
        if body.settings is not None:
            updates["settings"] = body.settings

        def _update():
            return (
                supabase.table("ehr_integrations")
                .update(updates)
                .eq("clinic_id", clinic_id)
                .eq("provider_name", canonical_provider)
                .execute()
            )

        res = await _run(_update)
        if not res.data:
            raise HTTPException(status_code=404, detail="Integration not found")

        return {"data": res.data[0], "message": f"{canonical_provider} settings updated successfully."}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[ehr] patch_integration error clinic={clinic_id} provider={canonical_provider}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/integrations/{provider_name}")
async def delete_integration(
    provider_name: str,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Remove an EHR integration for this clinic."""
    canonical_provider = normalize_provider(provider_name)
    if canonical_provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")

    clinic_id = auth.clinic_id
    try:
        def _delete():
            return (
                supabase.table("ehr_integrations")
                .delete()
                .eq("clinic_id", clinic_id)
                .eq("provider_name", canonical_provider)
                .execute()
            )

        await _run(_delete)
        return {"data": {"deleted": True, "provider_name": canonical_provider}}
    except Exception as e:
        log.error(f"[ehr] delete_integration error clinic={clinic_id} provider={canonical_provider}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/integrations/{provider_name}/verify")
async def verify_integration(
    provider_name: str,
    body: Optional[EHRVerifyRequest] = Body(default=None),
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Verify the connection to an EHR provider or FHIR endpoint."""
    canonical_provider = normalize_provider(provider_name)
    if canonical_provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")

    clinic_id = auth.clinic_id
    try:
        # Check if caller provided inline credentials to test before saving
        integration = None
        if body and (body.access_token or body.fhir_endpoint or body.webhook_secret or body.provider_clinic_id or body.client_id or body.client_secret):
            integration = {
                "clinic_id": clinic_id,
                "provider_name": canonical_provider,
                "access_token": (body.access_token or "").strip(),
                "refresh_token": (body.refresh_token or "").strip(),
                "client_id": (body.client_id or "").strip(),
                "client_secret": (body.client_secret or "").strip(),
                "fhir_endpoint": (body.fhir_endpoint or "").strip(),
                "webhook_secret": (body.webhook_secret or "").strip(),
                "provider_clinic_id": (body.provider_clinic_id or "").strip(),
            }
        else:
            def _fetch():
                return (
                    supabase.table("ehr_integrations")
                    .select("*")
                    .eq("clinic_id", clinic_id)
                    .eq("provider_name", canonical_provider)
                    .limit(1)
                    .execute()
                )

            res = await _run(_fetch)
            if not res.data:
                raise HTTPException(status_code=404, detail=f"No saved configuration found for {canonical_provider}. Please configure credentials.")
            integration = res.data[0]

        connector = get_connector(canonical_provider, integration)
        connected = await connector.verify_connection(clinic_id)
        
        msg = "Connection verified successfully! EHR endpoint is online." if connected else "Connection check failed. Please verify your API credentials and endpoint URL."
        return {
            "data": {
                "connected": connected,
                "provider_name": canonical_provider,
                "display_name": SUPPORTED_PROVIDERS.get(canonical_provider, {}).get("name", canonical_provider),
                "message": msg,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[ehr] verify_integration error clinic={clinic_id} provider={canonical_provider}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class FHIRDiagnosticRequest(BaseModel):
    fhir_endpoint: str
    access_token: Optional[str] = None
    provider_name: Optional[str] = "fhir"


@router.post("/diagnostics/fhir")
async def diagnose_fhir_endpoint(
    body: FHIRDiagnosticRequest,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Deep test & diagnose any FHIR R4 server endpoint capability statement."""
    connector = FHIRConnector({
        "fhir_endpoint": body.fhir_endpoint.strip() if body.fhir_endpoint else "",
        "access_token": (body.access_token or "").strip(),
        "provider_name": body.provider_name or "fhir"
    })
    result = await connector.diagnose_endpoint()
    return {"data": result}


@router.post("/sync/patient/{patient_id}")
async def sync_patient(
    patient_id: str,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Sync a patient to all active EHR integrations."""
    clinic_id = auth.clinic_id
    results = {}

    try:
        # Fetch patient
        def _fetch_patient():
            return (
                supabase.table("patients")
                .select("*")
                .eq("id", patient_id)
                .eq("clinic_id", clinic_id)
                .limit(1)
                .execute()
            )

        patient_res = await _run(_fetch_patient)
        if not patient_res.data:
            raise HTTPException(status_code=404, detail="Patient not found")

        patient_data = patient_res.data[0]

        # Fetch active integrations
        def _fetch_integrations():
            return (
                supabase.table("ehr_integrations")
                .select("*")
                .eq("clinic_id", clinic_id)
                .eq("is_active", True)
                .execute()
            )

        integrations_res = await _run(_fetch_integrations)
        integrations = integrations_res.data or []

        # Sync to each connector
        for integration in integrations:
            provider = integration.get("provider_name", "")
            try:
                connector = get_connector(provider, integration)
                ehr_id = await connector.create_patient(clinic_id, patient_data)
                results[provider] = {"success": ehr_id is not None, "ehr_id": ehr_id}
            except ValueError:
                results[provider] = {"success": False, "error": f"Unknown provider {provider}"}
            except Exception as e:
                log.error(f"[ehr] sync_patient provider={provider} error: {e}")
                results[provider] = {"success": False, "error": str(e)}

        # Update last_synced_at timestamp on active integrations
        def _touch_sync():
            return (
                supabase.table("ehr_integrations")
                .update({"last_synced_at": datetime.now(timezone.utc).isoformat()})
                .eq("clinic_id", clinic_id)
                .eq("is_active", True)
                .execute()
            )
        await _run(_touch_sync)

        return {"data": {"patient_id": patient_id, "results": results}}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[ehr] sync_patient error clinic={clinic_id} patient={patient_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync/appointment/{appointment_id}")
async def sync_appointment(
    appointment_id: str,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Sync an appointment to all active EHR integrations."""
    clinic_id = auth.clinic_id
    results = {}

    try:
        # Fetch appointment
        def _fetch_appt():
            return (
                supabase.table("appointments")
                .select("*")
                .eq("id", appointment_id)
                .eq("clinic_id", clinic_id)
                .limit(1)
                .execute()
            )

        appt_res = await _run(_fetch_appt)
        if not appt_res.data:
            raise HTTPException(status_code=404, detail="Appointment not found")

        appointment_data = appt_res.data[0]

        # Fetch active integrations
        def _fetch_integrations():
            return (
                supabase.table("ehr_integrations")
                .select("*")
                .eq("clinic_id", clinic_id)
                .eq("is_active", True)
                .execute()
            )

        integrations_res = await _run(_fetch_integrations)
        integrations = integrations_res.data or []

        # Sync to each connector
        for integration in integrations:
            provider = integration.get("provider_name", "")
            try:
                connector = get_connector(provider, integration)
                ehr_id = await connector.create_appointment(clinic_id, appointment_data)
                results[provider] = {"success": ehr_id is not None, "ehr_id": ehr_id}
            except ValueError:
                results[provider] = {"success": False, "error": f"Unknown provider {provider}"}
            except Exception as e:
                log.error(f"[ehr] sync_appointment provider={provider} error: {e}")
                results[provider] = {"success": False, "error": str(e)}

        # Update last_synced_at timestamp on active integrations
        def _touch_sync():
            return (
                supabase.table("ehr_integrations")
                .update({"last_synced_at": datetime.now(timezone.utc).isoformat()})
                .eq("clinic_id", clinic_id)
                .eq("is_active", True)
                .execute()
            )
        await _run(_touch_sync)

        return {"data": {"appointment_id": appointment_id, "results": results}}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[ehr] sync_appointment error clinic={clinic_id} appt={appointment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync/trigger")
@router.post("/sync/run")
async def trigger_manual_sync(
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """Trigger immediate full synchronization cycle across all active EHR endpoints."""
    clinic_id = auth.clinic_id
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

        integrations_res = await _run(_fetch_active)
        active_list = integrations_res.data or []

        if not active_list:
            return {"data": {"synced": False, "message": "No active and enabled EHR integrations configured."}}

        # Touch last_synced_at
        now_iso = datetime.now(timezone.utc).isoformat()
        def _touch():
            return (
                supabase.table("ehr_integrations")
                .update({"last_synced_at": now_iso})
                .eq("clinic_id", clinic_id)
                .eq("is_active", True)
                .execute()
            )
        await _run(_touch)

        return {
            "data": {
                "synced": True,
                "synced_at": now_iso,
                "active_providers": [i.get("provider_name") for i in active_list],
                "message": f"Sync cycle triggered for {len(active_list)} active EHR integration(s).",
            }
        }
    except Exception as e:
        log.error(f"[ehr] trigger_manual_sync error clinic={clinic_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
