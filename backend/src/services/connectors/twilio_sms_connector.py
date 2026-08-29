from twilio.rest import Client
import anyio
from typing import Any
from .base_connector import BaseSmsConnector
from ...core.config import settings
from ...core.resilience import CircuitBreaker

# Share a single circuit breaker across all SMS connector instances
twilio_breaker = CircuitBreaker("TwilioSMS", failure_threshold=5, recovery_timeout_seconds=60.0)

class TwilioSmsConnector(BaseSmsConnector):
    def __init__(self):
        # Initialize Twilio Client dynamically from settings
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        else:
            self.client = None

    def _send_sms_sync(self, **kwargs) -> Any:
        if not self.client:
            raise ValueError("Twilio credentials not configured")
        return self.client.messages.create(**kwargs)

    async def send_sms(self, from_number: str, to_number: str, body: str) -> str:
        async def _execute():
            return await anyio.to_thread.run_sync(
                lambda: self._send_sms_sync(
                    body=body,
                    from_=from_number,
                    to=to_number
                )
            )

        # Execute using the circuit breaker
        message = await twilio_breaker.call(_execute)
        return message.sid
