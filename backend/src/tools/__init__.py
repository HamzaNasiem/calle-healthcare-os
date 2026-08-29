from typing import Dict, Type

from .appointments import (
    AddToWaitlistTool,
    BookNewAppointmentTool,
    CancelAppointmentTool,
    CancelExistingAppointmentTool,
    CheckCalendarAvailabilityTool,
    GetAvailableSlotsTool,
    RescheduleAppointmentTool,
)
from .base_tool import BaseTool
from .clinical import CheckExistingPatientTool, LogPatientSymptomsTool
from .telephony import SendLiveSmsLinkTool, TransferCallToHumanTool
from .tenant_faq import CheckServicePricingTool, GetClinicFaqTool

# Registry of all available tools
TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    "check_calendar_availability": CheckCalendarAvailabilityTool,
    "get_available_slots": GetAvailableSlotsTool,
    "book_new_appointment": BookNewAppointmentTool,
    "cancel_existing_appointment": CancelExistingAppointmentTool,
    "cancel_appointment": CancelAppointmentTool,
    "reschedule_appointment": RescheduleAppointmentTool,
    "add_to_waitlist": AddToWaitlistTool,
    "log_patient_symptoms": LogPatientSymptomsTool,
    "check_existing_patient": CheckExistingPatientTool,
    "check_service_pricing": CheckServicePricingTool,
    "get_clinic_faq": GetClinicFaqTool,
    "send_live_sms_link": SendLiveSmsLinkTool,
    "transfer_call_to_human": TransferCallToHumanTool,
}

def get_tool(tool_name: str) -> BaseTool:
    tool_class = TOOL_REGISTRY.get(tool_name)
    if not tool_class:
        raise ValueError(f"Unknown tool: {tool_name}")
    return tool_class()
