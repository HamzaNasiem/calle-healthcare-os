"""
test_real_call.py - Make a real CALL-E test call
Run this script to verify your API key works and make a real phone call.
Replace PHONE_NUMBER with your own phone number.

Usage:
    python test_real_call.py
"""
import os
import sys

# Set env vars
os.environ["CALLE_API_KEY"] = "iams_live_oemQTmEoVgpE8l1MfOci_e1723eec26e016fb1c91e165ee7664c11f9f3f440f24f7a8c74f2ef91563418b"

PHONE_NUMBER = "+1XXXXXXXXXX"   # << REPLACE WITH YOUR PHONE NUMBER (US number recommended)
REGION = "US"                   # US, GB, AU, IN etc.

from calle import CalleClient

client = CalleClient(api_key=os.environ["CALLE_API_KEY"])

print(f"[TEST] Placing test call to region={REGION}")
print(f"[TEST] Available methods: {[m for m in dir(client.calls) if not m.startswith('_')]}")

result_schema = {
    "type": "object",
    "required": ["heard_clearly"],
    "properties": {
        "heard_clearly": {
            "type": "string",
            "enum": ["yes", "no", "unknown"],
            "description": "Did the person say they can hear clearly?"
        },
        "notes": {
            "type": "string",
            "description": "Any other remarks from the call."
        }
    },
    "additionalProperties": False
}

print("[TEST] Creating call with create_and_wait (blocking, up to 5 min)...")
print("[TEST] Your phone will ring shortly!")

try:
    result = client.calls.create_and_wait(
        task="Call this person and say: Hello! This is a test call from Bytelytic Clinic OS. Can you hear me clearly? Please say yes or no.",
        recipients=[{"phones": [PHONE_NUMBER], "region": REGION, "locale": "en-US"}],
        result_schema=result_schema,
        idempotency_key=f"test_call_bytelytic_001",
    )
    print(f"[TEST] Call completed!")
    print(f"  status: {result.get('status')}")
    print(f"  task_completed: {result.get('task_completed')}")
    print(f"  structured_result: {result.get('structured_result')}")
    print(f"  summary: {result.get('summary', '')[:200]}")
    print(f"  call_id: {result.get('id')}")
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
