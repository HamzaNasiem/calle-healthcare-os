import datetime
import anyio
from typing import Any, List
from googleapiclient.discovery import build
from .base_connector import BaseCalendarConnector
from ...core.resilience import CircuitBreaker

# Share a single circuit breaker across all Google Calendar connector instances
google_breaker = CircuitBreaker("GoogleCalendar", failure_threshold=5, recovery_timeout_seconds=60.0)

class GoogleCalendarConnector(BaseCalendarConnector):
    def _build_service(self, credentials) -> Any:
        return build('calendar', 'v3', credentials=credentials)

    def _list_events(self, service, **kwargs) -> Any:
        return service.events().list(**kwargs).execute()

    def _insert_event(self, service, **kwargs) -> Any:
        return service.events().insert(**kwargs).execute()

    def _delete_event(self, service, **kwargs) -> Any:
        return service.events().delete(**kwargs).execute()

    async def get_busy_windows(self, credentials: Any, calendar_id: str, start_time: datetime.datetime, end_time: datetime.datetime) -> List[dict]:
        async def _execute():
            service = await anyio.to_thread.run_sync(self._build_service, credentials)
            events_res = await anyio.to_thread.run_sync(
                lambda: self._list_events(
                    service,
                    calendarId=calendar_id,
                    timeMin=start_time.isoformat(),
                    timeMax=end_time.isoformat(),
                    singleEvents=True,
                    orderBy="startTime"
                )
            )
            
            busy = []
            for item in events_res.get("items", []):
                start_dt = item.get("start", {}).get("dateTime")
                end_dt = item.get("end", {}).get("dateTime")
                if start_dt and end_dt:
                    s = datetime.datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                    e = datetime.datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
                    busy.append({"start": s, "end": e})
            return busy

        return await google_breaker.call(_execute)

    async def create_event(self, credentials: Any, calendar_id: str, event_data: dict) -> str:
        async def _execute():
            service = await anyio.to_thread.run_sync(self._build_service, credentials)
            res = await anyio.to_thread.run_sync(
                lambda: self._insert_event(
                    service,
                    calendarId=calendar_id,
                    sendUpdates="none",
                    body=event_data
                )
            )
            return res["id"]

        return await google_breaker.call(_execute)

    async def delete_event(self, credentials: Any, calendar_id: str, event_id: str) -> None:
        async def _execute():
            service = await anyio.to_thread.run_sync(self._build_service, credentials)
            await anyio.to_thread.run_sync(
                lambda: self._delete_event(
                    service,
                    calendarId=calendar_id,
                    eventId=event_id,
                    sendUpdates="none"
                )
            )

        await google_breaker.call(_execute)
