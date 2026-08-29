import pytest
from src.api.routers.clinics_router import ClinicUpdate
from src.services.calendar_service import _parse_business_hours
from src.services.voice_service import voice_service

def test_clinic_update_business_hours_dict_conversion():
    # Test standard dictionary format with enabled, start, end
    payload = {
        "business_hours": {
            "mon": {"enabled": True, "start": "08:00", "end": "17:00"},
            "tue": {"enabled": True, "start": "09:00", "end": "18:00"},
            "wed": {"enabled": True, "start": "08:00", "end": "12:00"},
            "thu": {"enabled": False, "start": "08:00", "end": "18:00"},
            "fri": {"open": True, "start": "08:30", "end": "16:30"},
            "sat": {"closed": True},
            "sun": {"enabled": False}
        }
    }
    update_obj = ClinicUpdate(**payload)
    hours = update_obj.business_hours
    assert hours is not None
    assert hours["mon"] == "08:00-17:00"
    assert hours["tue"] == "09:00-18:00"
    assert hours["wed"] == "08:00-12:00"
    assert hours["thu"] == "closed"
    assert hours["fri"] == "08:30-16:30"
    assert hours["sat"] == "closed"
    assert hours["sun"] == "closed"

def test_clinic_update_business_hours_string_format_and_json():
    # Test string format and JSON string input
    payload = {
        "business_hours": '{"mon": "08:00-18:00", "tue": "08:00 - 18:00", "wed": "closed", "sat": "off"}'
    }
    update_obj = ClinicUpdate(**payload)
    hours = update_obj.business_hours
    assert hours["mon"] == "08:00-18:00"
    assert hours["tue"] == "08:00-18:00"
    assert hours["wed"] == "closed"
    assert hours["sat"] == "closed"
    assert hours["sun"] == "closed"  # missing days default appropriately

def test_clinic_update_business_hours_preserves_notifications_config():
    payload = {
        "business_hours": {
            "mon": "08:00-18:00",
            "tue": "08:00-18:00",
            "_notifications_config": {"booking_confirmation_enabled": True}
        }
    }
    update_obj = ClinicUpdate(**payload)
    hours = update_obj.business_hours
    assert "_notifications_config" in hours
    assert hours["_notifications_config"]["booking_confirmation_enabled"] is True

def test_calendar_service_parse_business_hours_formats():
    # Dict enabled
    parsed_dict = _parse_business_hours({"enabled": True, "start": "08:30", "end": "17:45"})
    assert parsed_dict == {"start_hour": 8, "start_min": 30, "end_hour": 17, "end_min": 45}

    # Dict closed
    assert _parse_business_hours({"enabled": False, "start": "08:00", "end": "18:00"}) is None
    assert _parse_business_hours({"closed": True}) is None
    assert _parse_business_hours({"open": False}) is None

    # String ranges
    parsed_str = _parse_business_hours("08:00-18:00")
    assert parsed_str == {"start_hour": 8, "start_min": 0, "end_hour": 18, "end_min": 0}

    # String range with dash variations and whitespace
    parsed_dash = _parse_business_hours(" 09:15 – 17:30 ")
    assert parsed_dash == {"start_hour": 9, "start_min": 15, "end_hour": 17, "end_min": 30}

    # 12-hour AM/PM support
    parsed_ampm = _parse_business_hours("8:00 AM - 5:30 PM")
    assert parsed_ampm == {"start_hour": 8, "start_min": 0, "end_hour": 17, "end_min": 30}

    # Closed strings
    assert _parse_business_hours("closed") is None
    assert _parse_business_hours("CLOSED") is None
    assert _parse_business_hours("off") is None
    assert _parse_business_hours("") is None
    assert _parse_business_hours(None) is None

    # Invalid range (start >= end)
    assert _parse_business_hours("18:00-08:00") is None
    assert _parse_business_hours("12:00-12:00") is None

def test_voice_prompt_builder_with_business_hours():
    clinic = {
        "name": "Sunrise Spine Clinic",
        "primary_doctor_name": "James Wilson",
        "primary_doctor_credentials": "DC, PT",
        "specialty": "Chiropractic",
        "city": "Chicago",
        "timezone": "America/Chicago",
        "business_hours": {
            "mon": "08:00-17:00",
            "tue": "08:00-17:00",
            "wed": "08:00-12:00",
            "thu": "08:00-17:00",
            "fri": "08:00-16:00",
            "sat": "closed",
            "sun": "closed"
        },
        "appointment_types": [
            {"name": "Spinal Adjustment", "duration": 30, "fee": 90}
        ]
    }
    prompt = voice_service.build_agent_prompt(clinic)
    assert "Monday: 08:00 – 17:00" in prompt
    assert "Wednesday: 08:00 – 12:00" in prompt
    assert "Friday: 08:00 – 16:00" in prompt
    assert "Saturday: Closed" in prompt
    assert "Sunday: Closed" in prompt
