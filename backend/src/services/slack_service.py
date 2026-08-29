"""
Slack Alerting Service
======================
Sends structured alert payloads to a Slack webhook URL.
Configured via SLACK_WEBHOOK_URL environment variable.

Usage:
    from src.services.slack_service import slack_service
    await slack_service.alert("Cron job failed", level="error", details={"job": "reminders"})
"""

import asyncio
import httpx
import datetime
from typing import Optional
from ..core.config import settings
from ..core.logger import log


# Severity color map (Slack attachment colors)
LEVEL_COLORS = {
    "info":     "#36a64f",  # green
    "warning":  "#ffaa00",  # amber
    "error":    "#cc0000",  # red
    "critical": "#6600cc",  # purple
}


class SlackAlertService:
    def __init__(self):
        self.webhook_url: Optional[str] = getattr(settings, "SLACK_WEBHOOK_URL", None)

    async def alert(
        self,
        message: str,
        level: str = "error",
        details: Optional[dict] = None,
        clinic_id: Optional[str] = None,
    ) -> None:
        """
        Fire-and-forget Slack alert. Never raises - always fails silently.
        """
        if not self.webhook_url:
            log.debug("SLACK_WEBHOOK_URL not configured. Skipping Slack alert.")
            return

        color = LEVEL_COLORS.get(level, "#cc0000")
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        fields = [
            {"title": "Severity", "value": level.upper(), "short": True},
            {"title": "Timestamp", "value": timestamp, "short": True},
        ]

        if clinic_id:
            fields.append({"title": "Clinic ID", "value": clinic_id, "short": True})

        if details:
            for key, value in details.items():
                fields.append({"title": key.replace("_", " ").title(), "value": str(value), "short": False})

        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f":rotating_light: Bytelytic OS — {message}",
                    "fields": fields,
                    "footer": "Bytelytic OS",
                    "ts": int(datetime.datetime.now().timestamp()),
                }
            ]
        }

        asyncio.create_task(self._send(payload))

    async def _send(self, payload: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(self.webhook_url, json=payload)
                if res.status_code != 200:
                    log.warning(f"[SlackAlert] Non-200 response from Slack: {res.status_code} {res.text}")
        except Exception as e:
            log.warning(f"[SlackAlert] Failed to send Slack alert: {str(e)}")


slack_service = SlackAlertService()
