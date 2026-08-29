"""
test_voice_tools_and_persona.py — Comprehensive Unit Tests for Voice Persona, Medical Guardrails & Tool Calling
"""
import pytest
from src.tools import TOOL_REGISTRY, get_tool
from src.tools.appointments import (
    CheckCalendarAvailabilityTool,
    GetAvailableSlotsTool,
    BookNewAppointmentTool,
    CancelExistingAppointmentTool,
    CancelAppointmentTool,
    RescheduleAppointmentTool,
)
from src.tools.telephony import TransferCallToHumanTool
from src.api.routers.agent_config_router import (
    compile_agent_prompt,
    _format_business_hours,
    _format_doctor_info,
)


def test_tool_registry_and_names():
    """Verify all 5 primary tools and their Retell/CALL-E aliases are registered and instantiable."""
    required_tools = [
        "get_available_slots",
        "check_calendar_availability",
        "book_new_appointment",
        "cancel_appointment",
        "cancel_existing_appointment",
        "reschedule_appointment",
        "transfer_call_to_human",
    ]
    for tool_name in required_tools:
        assert tool_name in TOOL_REGISTRY, f"Missing tool in TOOL_REGISTRY: {tool_name}"
        tool = get_tool(tool_name)
        assert tool is not None
        assert tool.name == tool_name
        assert tool.description
        assert tool.args_schema is not None


def test_book_new_appointment_args_schema():
    """Ensure book_new_appointment args schema accepts all required and optional fields including service_type."""
    tool = get_tool("book_new_appointment")
    schema = tool.args_schema
    fields = schema.model_fields
    assert "patient_name" in fields
    assert "phone" in fields
    assert "dob" in fields
    assert "slot_id" in fields
    assert "reason" in fields
    assert "service_type" in fields


def test_get_available_slots_args_schema():
    """Ensure get_available_slots / check_calendar_availability args schema accepts date, time_preference, provider_id, service_type."""
    for name in ["get_available_slots", "check_calendar_availability"]:
        tool = get_tool(name)
        fields = tool.args_schema.model_fields
        assert "date" in fields
        assert "time_preference" in fields
        assert "provider_id" in fields
        assert "service_type" in fields


def test_cancel_appointment_args_schema():
    """Ensure cancel_appointment / cancel_existing_appointment args schema accepts phone, dob, appointment_date, reason."""
    for name in ["cancel_appointment", "cancel_existing_appointment"]:
        tool = get_tool(name)
        fields = tool.args_schema.model_fields
        assert "phone" in fields
        assert "dob" in fields
        assert "appointment_date" in fields
        assert "reason" in fields


def test_reschedule_appointment_args_schema():
    """Ensure reschedule_appointment args schema accepts phone, dob, old_appointment_date, new_slot_id."""
    tool = get_tool("reschedule_appointment")
    fields = tool.args_schema.model_fields
    assert "phone" in fields
    assert "dob" in fields
    assert "old_appointment_date" in fields
    assert "new_slot_id" in fields


def test_transfer_call_to_human_args_schema():
    """Ensure transfer_call_to_human args schema accepts reason."""
    tool = get_tool("transfer_call_to_human")
    fields = tool.args_schema.model_fields
    assert "reason" in fields


def test_compile_agent_prompt_full_metadata():
    """Ensure system prompt compilation includes medical guardrails, doctor info, business hours, and tool calling parameters."""
    prompt = compile_agent_prompt(
        clinic_name="Sunrise Family Health Center",
        greeting="Hello! Thank you for calling Sunrise Family Health Center.",
        custom_persona="You are Alex, an attentive, polite AI receptionist.",
        faqs={"What insurance do you accept?": "We accept Medicare, BCBS, and Aetna."},
        language="en-US",
        emergency_forward_phone="+1 (555) 234-5678",
        doctor_name="Dr. Gregory House",
        doctor_credentials="MD, PhD",
        specialty="Diagnostic Medicine & Infectious Disease",
        business_hours={
            "monday": {"open": True, "start": "08:30", "end": "17:30"},
            "friday": {"open": True, "start": "08:30", "end": "16:00"},
            "saturday": {"open": False, "closed": True},
        },
        timezone="America/Chicago",
    )

    # 1. Clinic & Doctor Info
    assert "Sunrise Family Health Center" in prompt
    assert "Dr. Gregory House, MD, PhD" in prompt
    assert "Diagnostic Medicine & Infectious Disease" in prompt
    assert "America/Chicago" in prompt
    assert "Monday: 08:30 - 17:30" in prompt
    assert "Friday: 08:30 - 16:00" in prompt
    assert "Saturday: Closed" in prompt

    # 2. Medical Guardrails
    assert "Never provide medical diagnoses" in prompt
    assert "Never quote pricing" in prompt
    assert "dial 911 immediately" in prompt
    assert "Protected Health Information" in prompt

    # 3. Tool Calling Parameters
    assert "get_available_slots" in prompt
    assert "book_new_appointment" in prompt
    assert "cancel_appointment" in prompt
    assert "reschedule_appointment" in prompt
    assert "transfer_call_to_human" in prompt
    assert "YYYY-MM-DD" in prompt
    assert "slot_id" in prompt

    # 4. Spoken Voice Guidelines
    assert "Speak concisely" in prompt
    assert "Never read out raw markdown" in prompt

    # 5. Routing & FAQs
    assert "+15552345678" in prompt
    assert "What insurance do you accept?: We accept Medicare, BCBS, and Aetna." in prompt
