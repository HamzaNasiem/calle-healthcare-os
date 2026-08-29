import resend
import anyio
from typing import List, Any
from .base_connector import BaseEmailConnector
from ...core.config import settings
from ...core.resilience import CircuitBreaker

# Share a single circuit breaker across all Email connector instances
resend_breaker = CircuitBreaker("ResendEmail", failure_threshold=5, recovery_timeout_seconds=60.0)

class ResendEmailConnector(BaseEmailConnector):
    def __init__(self):
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY

    def _send_email_sync(self, **kwargs) -> Any:
        params = {}
        for k, v in kwargs.items():
            if k == "from_":
                params["from"] = v
            else:
                params[k] = v
        return resend.Emails.send(params)

    async def send_email(self, from_email: str, to_emails: List[str], subject: str, html_body: str) -> str:
        if not settings.RESEND_API_KEY:
            if settings.is_prod:
                raise Exception("Resend email client is not initialized: RESEND_API_KEY is missing in production environment.")
            from ...core.logger import log
            log.warning(f"[ResendEmailConnector] WARNING: RESEND_API_KEY not set. Cannot send email to {to_emails}.")
            return "mock_resend_email_id"
        
        # Ensure API key is set before sending
        resend.api_key = settings.RESEND_API_KEY
        
        async def _execute():
            email = await anyio.to_thread.run_sync(
                lambda: self._send_email_sync(
                    from_=from_email,
                    to=to_emails,
                    subject=subject,
                    html=html_body
                )
            )
            if hasattr(email, 'id'):
                return email.id
            elif isinstance(email, dict):
                return email.get('id', '')
            return str(email)

        return await resend_breaker.call(_execute)
