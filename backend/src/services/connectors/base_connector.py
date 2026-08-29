from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import datetime

class BaseCalendarConnector(ABC):
    @abstractmethod
    async def get_busy_windows(self, credentials: Any, calendar_id: str, start_time: datetime.datetime, end_time: datetime.datetime) -> List[dict]:
        """Fetch list of busy time intervals containing 'start' and 'end' datetime objects."""
        pass

    @abstractmethod
    async def create_event(self, credentials: Any, calendar_id: str, event_data: dict) -> str:
        """Create a calendar event and return the unique event ID."""
        pass

    @abstractmethod
    async def delete_event(self, credentials: Any, calendar_id: str, event_id: str) -> None:
        """Delete a calendar event."""
        pass


class BaseSmsConnector(ABC):
    @abstractmethod
    async def send_sms(self, from_number: str, to_number: str, body: str) -> str:
        """Send an SMS message and return a message SID/identifier."""
        pass


class BaseVoiceConnector(ABC):
    @abstractmethod
    async def create_agent(self, clinic_name: str, prompt: str, webhook_url: str) -> str:
        """Create a voice receptionist agent and return the agent ID."""
        pass

    @abstractmethod
    async def update_agent(self, agent_id: str, prompt: str) -> None:
        """Update the agent prompt."""
        pass

    @abstractmethod
    async def make_outbound_call(self, from_number: str, to_number: str, agent_id: str, call_type: str, dynamic_variables: dict) -> str:
        """Initiate an outbound AI call and return the unique call ID."""
        pass

    @abstractmethod
    async def stop_call(self, call_id: str) -> None:
        """Terminate a live phone call."""
        pass


class BaseEmailConnector(ABC):
    @abstractmethod
    async def send_email(self, from_email: str, to_emails: List[str], subject: str, html_body: str) -> str:
        """Send an email and return the message ID/identifier."""
        pass
