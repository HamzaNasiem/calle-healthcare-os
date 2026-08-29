"""
Zapier Webhook Bridge Connector
---------------------------------
Push-only integration: fires clinic-configured Zapier webhook URLs for patient and
appointment events. No EHR read capability (get_patient returns None).
Never raises — logs errors and returns None on failure.
"""

import httpx
from typing import Optional

from ...core.logger import log
from .base import EMRIntegrationBase


class ZapierConnector(EMRIntegrationBase):
    """Connector for Zapier webhook-based integrations."""

    def __init__(self, integration: dict):
        """
        Args:
            integration: Row from `ehr_integrations` table for this clinic/provider.
                         `webhook_secret` field is used as the webhook URL.
        """
        self._integration = integration
        # webhook_secret stores the target Zapier webhook URL
        self._webhook_url: str = integration.get("webhook_secret", "")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fire(self, payload: dict) -> Optional[str]:
        """POST payload to the configured Zapier webhook URL."""
        if not self._webhook_url:
            log.error("[zapier] webhook URL not configured (webhook_secret is empty)")
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
                # Zapier webhooks return 200 with a simple JSON; use request ID as synthetic ehr_id
                body = resp.text.strip()
                return body[:64] if body else "ok"
        except Exception as e:
            log.error(f"[zapier] webhook POST failed: {e}")
            return None

    # ------------------------------------------------------------------
    # EMRIntegrationBase implementation
    # ------------------------------------------------------------------

    async def create_patient(self, clinic_id: str, patient_data: dict) -> Optional[str]:
        """Fire patient.created event to Zapier webhook."""
        log.info(f"[zapier] firing patient.created for clinic={clinic_id}")
        return await self._fire({"event": "patient.created", "data": patient_data})

    async def create_appointment(self, clinic_id: str, appointment_data: dict) -> Optional[str]:
        """Fire appointment.created event to Zapier webhook."""
        log.info(f"[zapier] firing appointment.created for clinic={clinic_id}")
        return await self._fire({"event": "appointment.created", "data": appointment_data})

    async def get_patient(self, clinic_id: str, ehr_patient_id: str) -> Optional[dict]:
        """Zapier is push-only; read operations are not supported."""
        log.info("[zapier] get_patient not supported — Zapier is push-only")
        return None

    async def verify_connection(self, clinic_id: str) -> bool:
        """Fire a ping event to the webhook URL. Returns True if 200 received."""
        if not self._webhook_url:
            log.warning("[zapier] verify_connection: webhook URL not configured")
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._webhook_url, json={"event": "ping"})
                return resp.status_code == 200
        except Exception as e:
            log.warning(f"[zapier] verify_connection error: {e}")
            return False
