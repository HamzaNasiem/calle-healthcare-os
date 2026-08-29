import telnyx
from typing import Optional, Any
import anyio
from .base_connector import BaseSmsConnector
from ...core.config import settings
from ...core.resilience import CircuitBreaker

# Share a single circuit breaker across all Telnyx SMS connector instances
telnyx_breaker = CircuitBreaker("TelnyxSMS", failure_threshold=5, recovery_timeout_seconds=60.0)

class TelnyxSmsConnector(BaseSmsConnector):
    """
    Telnyx SMS Connector
    Uses the Telnyx SDK (v4+) to send SMS messages. Telnyx provides a free BAA,
    making this completely HIPAA compliant without the Twilio $10k fee.
    """
    def __init__(self):
        self.api_key = (
            getattr(settings, "TELNYX_API_KEY", "") or 
            getattr(settings, "telnyx_api_key", "") or 
            ""
        )
        if self.api_key:
            self.client = telnyx.Telnyx(api_key=self.api_key)
        else:
            self.client = None

    async def send_sms(self, from_number: str, to_number: str, body: str) -> str:
        """
        Send an SMS message via Telnyx.
        Returns the Telnyx message ID.
        """
        if not self.api_key or not self.client:
            if getattr(settings, "is_prod", False):
                raise Exception("Telnyx SMS client is not initialized: TELNYX_API_KEY is missing in production environment.")
            import uuid
            from ...core.logger import log
            from ...core.security import mask_phone
            mock_id = f"mock_telnyx_id_{uuid.uuid4().hex[:12]}"
            log.info(f"[Telnyx Mock] Sending SMS to {mask_phone(to_number)} (ID: {mock_id})")
            return mock_id

        def _execute_telnyx():
            response = self.client.messages.send(
                from_=from_number,
                to=to_number,
                text=body
            )
            if hasattr(response, "data") and response.data:
                return getattr(response.data, "id", None) or getattr(response.data, "message_id", "no_id")
            elif hasattr(response, "id"):
                return response.id
            return "no_id"

        async def _execute():
            return await anyio.to_thread.run_sync(_execute_telnyx)

        try:
            # Execute using the circuit breaker for extra resilience
            return await telnyx_breaker.call(_execute)
        except Exception as e:
            raise Exception(f"Telnyx SMS failed: {str(e)}")

