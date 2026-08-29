import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

log_lines = []

try:
    from src.api.routers.clinics_router import ClinicUpdate
    from src.services.voice_service import voice_service

    log_lines.append("Testing appointment types validation...")

    payload = {
        "appointment_types": [
            {"name": "Initial Evaluation", "duration": 60, "fee": 150},
            {"name": "Follow-up", "duration": 30, "fee": 75},
            {"name": "Massage Therapy", "duration_minutes": 45, "fee": 90.50}
        ]
    }
    update_obj = ClinicUpdate(**payload)
    types = update_obj.appointment_types
    assert len(types) == 3, f"Expected 3, got {len(types)}"
    assert types[0] == {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 150.0}
    assert types[1] == {"name": "Follow-up", "duration": 30, "duration_minutes": 30, "fee": 75.0}
    assert types[2] == {"name": "Massage Therapy", "duration": 45, "duration_minutes": 45, "fee": 90.5}
    log_lines.append("Test 1 passed!")

    # Deduplication & Sanitization
    payload2 = {
        "appointment_types": [
            {"name": "  Initial Evaluation  ", "duration": 60, "fee": 150},
            {"name": "initial evaluation", "duration": 45, "fee": 200},
            {"name": "", "duration": 30},
            {"name": "Quick Check", "duration": -10, "fee": -50},
        ]
    }
    update_obj2 = ClinicUpdate(**payload2)
    types2 = update_obj2.appointment_types
    assert len(types2) == 2, f"Expected 2, got {len(types2)}"
    assert types2[0]["name"] == "Initial Evaluation"
    assert types2[0]["duration"] == 60
    assert types2[0]["fee"] == 150.0
    assert types2[1]["name"] == "Quick Check"
    assert types2[1]["duration"] == 5
    assert types2[1]["fee"] == 0.0
    log_lines.append("Test 2 passed!")

    # Voice Prompt Builder
    clinic = {
        "name": "Oakridge Health",
        "primary_doctor_name": "Sarah Connor",
        "primary_doctor_credentials": "MD, PT",
        "specialty": "Physical Therapy",
        "city": "Chicago",
        "timezone": "America/Chicago",
        "business_hours": {
            "mon": {"enabled": True, "start": "08:00", "end": "17:00"}
        },
        "appointment_types": [
            {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 175},
            {"name": "Follow-up", "duration": 30, "duration_minutes": 30, "fee": 85},
            {"name": "Free Consultation", "duration": 15, "duration_minutes": 15, "fee": 0}
        ]
    }
    prompt = voice_service.build_agent_prompt(clinic)
    assert "Initial Evaluation (60 minutes, $175)" in prompt, "Initial Evaluation not formatted in prompt"
    assert "Follow-up (30 minutes, $85)" in prompt, "Follow-up not formatted in prompt"
    assert "Free Consultation (15 minutes)" in prompt, "Free Consultation not formatted in prompt"
    log_lines.append("Test 3 passed!")
    log_lines.append("ALL APPOINTMENT TYPES BACKEND TESTS PASSED SUCCESSFULLY!")
except Exception as e:
    import traceback
    log_lines.append(f"ERROR: {e}")
    log_lines.append(traceback.format_exc())

with open(os.path.join(os.path.dirname(__file__), "test_output.txt"), "w") as f:
    f.write("\n".join(log_lines))

print("\n".join(log_lines))
