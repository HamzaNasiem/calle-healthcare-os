import sys
import os

# Set dummy env vars for Settings
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "mock_service_key"
os.environ["SUPABASE_ANON_KEY"] = "mock_anon_key"
os.environ["RETELL_API_KEY"] = "mock_retell_key"
os.environ["GOOGLE_CLIENT_ID"] = "mock_google_id"
os.environ["GOOGLE_CLIENT_SECRET"] = "mock_google_secret"
os.environ["GOOGLE_REDIRECT_URI"] = "https://mock.app/oauth"
os.environ["OPENROUTER_API_KEY"] = "mock_openrouter"
os.environ["API_BASE_URL"] = "http://localhost:3000"
os.environ["DASHBOARD_URL"] = "http://localhost:5173"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.routers.clinics_router import ClinicUpdate
from src.services.voice_service import voice_service

print("Testing appointment types validation...")
payload = {
    "appointment_types": [
        {"name": "Initial Evaluation", "duration": 60, "fee": 150},
        {"name": "Follow-up", "duration": 30, "fee": 75},
        {"name": "Massage Therapy", "duration_minutes": 45, "fee": 90.50}
    ]
}
update_obj = ClinicUpdate(**payload)
types = update_obj.appointment_types
assert len(types) == 3, f"Expected 3 types, got {len(types)}"
assert types[0] == {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 150.0}, f"Type 0 mismatch: {types[0]}"
assert types[1] == {"name": "Follow-up", "duration": 30, "duration_minutes": 30, "fee": 75.0}, f"Type 1 mismatch: {types[1]}"
assert types[2] == {"name": "Massage Therapy", "duration": 45, "duration_minutes": 45, "fee": 90.5}, f"Type 2 mismatch: {types[2]}"
print("✓ Valid appointment types verified!")

print("Testing deduplication and sanitization...")
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
assert len(types) == 2, f"Expected 2 types, got {len(types)}"
assert types[0]["name"] == "Initial Evaluation", f"Type 0 name mismatch: {types[0]}"
assert types[0]["duration"] == 60, f"Type 0 duration mismatch: {types[0]}"
assert types[1]["name"] == "Quick Check", f"Type 1 name mismatch: {types[1]}"
assert types[1]["duration"] == 5, f"Type 1 duration min mismatch: {types[1]}"
assert types[1]["fee"] == 0.0, f"Type 1 fee min mismatch: {types[1]}"
print("✓ Deduplication and sanitization verified!")

print("Testing voice prompt builder with appointment types...")
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
assert "Initial Evaluation (60 minutes, $175)" in prompt, "Initial eval prompt missing"
assert "Follow-up (30 minutes, $85)" in prompt, "Follow-up prompt missing"
assert "Free Consultation (15 minutes)" in prompt, "Free consultation prompt missing"
print("✓ Voice prompt builder verified!")

print("\nALL APPOINTMENT TYPES TESTS PASSED SUCCESSFULLY!")
