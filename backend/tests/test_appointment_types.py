import pytest
from src.api.routers.clinics_router import ClinicUpdate
from src.services.voice_service import voice_service

def test_clinic_update_appointment_types_validation():
    # Test valid appointment types with duration and fee
    payload = {
        "appointment_types": [
            {"name": "Initial Evaluation", "duration": 60, "fee": 150},
            {"name": "Follow-up", "duration": 30, "fee": 75},
            {"name": "Massage Therapy", "duration_minutes": 45, "fee": 90.50}
        ]
    }
    update_obj = ClinicUpdate(**payload)
    types = update_obj.appointment_types
    assert len(types) == 3
    assert types[0] == {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 150.0}
    assert types[1] == {"name": "Follow-up", "duration": 30, "duration_minutes": 30, "fee": 75.0}
    assert types[2] == {"name": "Massage Therapy", "duration": 45, "duration_minutes": 45, "fee": 90.5}

def test_clinic_update_appointment_types_deduplication_and_sanitization():
    payload = {
        "appointment_types": [
            {"name": "  Initial Evaluation  ", "duration": 60, "fee": 150},
            {"name": "initial evaluation", "duration": 45, "fee": 200},  # Duplicate case-insensitive
            {"name": "", "duration": 30},  # Empty name
            {"name": "Quick Check", "duration": -10, "fee": -50},  # Negative duration and fee
        ]
    }
    update_obj = ClinicUpdate(**payload)
    types = update_obj.appointment_types
    assert len(types) == 2
    assert types[0]["name"] == "Initial Evaluation"
    assert types[0]["duration"] == 60
    assert types[1]["name"] == "Quick Check"
    assert types[1]["duration"] == 5  # minimum 5 min
    assert types[1]["fee"] == 0.0     # non-negative

def test_clinic_update_appointment_types_fallback_and_types_matching():
    # Test fallback to defaults if list contains no valid dicts
    payload = {
        "appointment_types": [
            {"name": ""},
            "invalid_string"
        ]
    }
    update_obj = ClinicUpdate(**payload)
    types = update_obj.appointment_types
    assert len(types) == 0

def test_voice_prompt_builder_with_appointment_types():
    clinic = {
        "name": "Oakridge Health",
        "primary_doctor_name": "Sarah Connor",
        "primary_doctor_credentials": "MD, PT",
        "specialty": "Physical Therapy",
        "city": "Chicago",
        "timezone": "America/Chicago",
        "business_hours": {
            "mon": {"enabled": True, "start": "08:00", "end": "17:00"},
            "tue": {"enabled": True, "start": "08:00", "end": "17:00"}
        },
        "appointment_types": [
            {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 175},
            {"name": "Follow-up", "duration": 30, "duration_minutes": 30, "fee": 85},
            {"name": "Free Consultation", "duration": 15, "duration_minutes": 15, "fee": 0}
        ]
    }
    prompt = voice_service.build_agent_prompt(clinic)
    assert "Initial Evaluation (60 minutes, $175)" in prompt
    assert "Follow-up (30 minutes, $85)" in prompt
    assert "Free Consultation (15 minutes)" in prompt

def test_voice_prompt_builder_without_appointment_types_fallback():
    clinic = {
        "name": "Oakridge Health",
        "appointment_types": []
    }
    prompt = voice_service.build_agent_prompt(clinic)
    assert "Initial Evaluation (60 minutes, $150)" in prompt
    assert "Follow-up (30 minutes, $75)" in prompt
