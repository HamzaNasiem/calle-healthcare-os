import sys
import os

# Set dummy env vars for test environment
os.environ.setdefault("GOOGLE_CLIENT_ID", "dummy_google_id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dummy_google_secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth2callback")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy_service_key")
os.environ.setdefault("SUPABASE_ANON_KEY", "dummy_anon_key")
os.environ.setdefault("RETELL_API_KEY", "dummy_retell_key")
os.environ.setdefault("OPENROUTER_API_KEY", "dummy_openrouter_key")
os.environ.setdefault("API_BASE_URL", "http://localhost:3000")
os.environ.setdefault("DASHBOARD_URL", "http://localhost:5173")

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.src.services.calendar_service import _parse_business_hours
from backend.src.schemas.settings import BusinessDay
from backend.src.services.voice_service import VoiceService

def test_business_hours_parsing():
    print("Testing _parse_business_hours...")
    
    # 1. Dict format (enabled: True)
    res = _parse_business_hours({"enabled": True, "start": "08:30", "end": "17:30"})
    assert res == {"start_hour": 8, "start_min": 30, "end_hour": 17, "end_min": 30}, f"Failed dict enabled: {res}"
    
    # 2. Dict format (open: True)
    res = _parse_business_hours({"open": True, "start": "09:00", "end": "18:00"})
    assert res == {"start_hour": 9, "start_min": 0, "end_hour": 18, "end_min": 0}, f"Failed dict open: {res}"
    
    # 3. Dict format (enabled: False)
    res = _parse_business_hours({"enabled": False, "start": "08:00", "end": "18:00"})
    assert res is None, f"Failed dict disabled: {res}"
    
    # 4. Dict format (closed: True)
    res = _parse_business_hours({"closed": True, "start": "08:00", "end": "18:00"})
    assert res is None, f"Failed dict closed: {res}"
    
    # 5. String format ("08:00-18:00")
    res = _parse_business_hours("08:00-18:00")
    assert res == {"start_hour": 8, "start_min": 0, "end_hour": 18, "end_min": 0}, f"Failed str: {res}"
    
    # 6. String format ("closed")
    res = _parse_business_hours("closed")
    assert res is None, f"Failed str closed: {res}"
    
    # 7. None / Empty
    assert _parse_business_hours(None) is None
    assert _parse_business_hours("") is None
    assert _parse_business_hours({}) is None

    print("✓ _parse_business_hours passed all tests!")

def test_voice_prompt_building():
    print("Testing voice prompt generation with business hours...")
    clinic = {
        "name": "Acme Health",
        "primary_doctor_name": "Hamza Nasiem",
        "primary_doctor_credentials": "MD",
        "specialty": "Physical Therapy",
        "city": "Chicago",
        "timezone": "America/Chicago",
        "business_hours": {
            "mon": {"enabled": True, "start": "08:00", "end": "18:00"},
            "tue": {"enabled": True, "start": "08:00", "end": "18:00"},
            "wed": {"enabled": True, "start": "08:00", "end": "18:00"},
            "thu": {"enabled": True, "start": "08:00", "end": "18:00"},
            "fri": {"enabled": True, "start": "08:00", "end": "18:00"},
            "sat": {"enabled": False, "start": "08:00", "end": "18:00"},
            "sun": "closed",
            "_notifications_config": {"reminders_enabled": True}
        }
    }
    prompt = VoiceService.build_agent_prompt(None, clinic)
    assert "Monday: 08:00 – 18:00" in prompt
    assert "Tuesday: 08:00 – 18:00" in prompt
    assert "Saturday: Closed" in prompt
    assert "Sunday: Closed" in prompt
    assert "_notifications_config" not in prompt
    print("✓ voice prompt generation passed all tests!")

def test_pydantic_business_day_schema():
    print("Testing BusinessDay pydantic schema...")
    b1 = BusinessDay(enabled=True, start="08:00", end="18:00")
    assert b1.open is True
    assert b1.enabled is True
    
    b2 = BusinessDay(open=False)
    assert b2.open is False
    assert b2.enabled is False
    
    print("✓ BusinessDay schema passed all tests!")

if __name__ == "__main__":
    test_business_hours_parsing()
    test_voice_prompt_building()
    test_pydantic_business_day_schema()
    print("\nALL BUSINESS HOURS TESTS PASSED SUCCESSFULLY!")
