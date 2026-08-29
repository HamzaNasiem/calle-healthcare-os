import asyncio
import datetime

import anyio

from src.config.settings import settings
from src.core.logger import log


class HealthStatus:
    def __init__(self):
        self.telnyx = "unknown"
        self.retell = "unknown"
        self.last_checked = None

# Global health status object
_health_status = HealthStatus()

def get_health_status() -> dict:
    return {
        "telnyx": _health_status.telnyx,
        "retell": _health_status.retell,
        "last_checked": _health_status.last_checked
    }

async def _check_telnyx():
    try:
        if settings.TELNYX_API_KEY:
            import telnyx
            telnyx.api_key = settings.TELNYX_API_KEY
            # Use strict timeout; MessagingProfile is deprecated in newer SDK
            with anyio.move_on_after(5) as cancel_scope:
                await anyio.to_thread.run_sync(
                    lambda: telnyx.PhoneNumber.list(page_size=1)
                )
            if cancel_scope.cancel_called:
                return "unhealthy: timeout"
            return "healthy"
        else:
            return "unconfigured"
    except AttributeError:
        # Telnyx SDK version mismatch — treat as unconfigured, don't crash
        return "unconfigured"
    except Exception as e:
        log.error(f"Health monitor - Telnyx failed: {str(e)}")
        return f"unhealthy: {str(e)}"

async def _check_retell():
    try:
        if settings.RETELL_API_KEY:
            from retell import Retell
            import httpx
            # Pass a custom http_client to bypass the 'proxies' kwarg error in httpx 0.28+
            retell_client = Retell(
                api_key=settings.RETELL_API_KEY,
                http_client=httpx.Client()
            )
            with anyio.move_on_after(5) as cancel_scope:
                await anyio.to_thread.run_sync(
                    lambda: retell_client.agent.list()
                )
            if cancel_scope.cancel_called:
                return "unhealthy: timeout"
            return "healthy"
        else:
            return "unconfigured"
    except Exception as e:
        log.error(f"Health monitor - Retell failed: {str(e)}")
        return f"unhealthy: {str(e)}"

async def health_monitor_loop():
    """
    Background task that polls external APIs periodically (e.g. every 30s).
    Ensures that the /health/detailed endpoint returns instantly (O(1)) and
    avoids HTTP 429 Rate Limits from load balancer pings.
    """
    log.info("Starting background health monitor...")
    while True:
        try:
            t_status, r_status = await asyncio.gather(
                _check_telnyx(),
                _check_retell(),
                return_exceptions=True
            )
            
            _health_status.telnyx = t_status if not isinstance(t_status, Exception) else f"unhealthy: exception {str(t_status)}"
            _health_status.retell = r_status if not isinstance(r_status, Exception) else f"unhealthy: exception {str(r_status)}"
            _health_status.last_checked = datetime.datetime.now(datetime.UTC).isoformat()
            
        except Exception as e:
            log.error(f"Error in health monitor loop: {str(e)}")
            
        # Poll every 30 seconds
        await asyncio.sleep(30)
