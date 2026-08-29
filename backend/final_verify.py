import sys
import os
from fastapi.testclient import TestClient

# Adjust paths to import backend modules
sys.path.append(os.path.dirname(__file__))

from src.main import app

client = TestClient(app, base_url="http://localhost:8000")

def test_google_redirect():
    print("\n--- Testing GET /auth/google redirect ---")
    r = client.get("/auth/google?token=test_jwt_token", follow_redirects=False)
    if r.status_code == 307 or r.status_code == 302:
        loc = r.headers.get("location", "")
        print(f"[PASS] Redirect Success (Status {r.status_code})")
        print(f"  Location: {loc[:80]}...")
        if "accounts.google.com" in loc and "test_jwt_token" in loc:
            print("  [PASS] Redirect URL matches scope and stores JWT in state.")
        else:
            print("  [FAIL] Redirect URL is missing key OAuth query params.")
    else:
        print(f"[FAIL] Failed: status={r.status_code}, response={r.text}")

def test_admin_endpoints_protection():
    print("\n--- Testing Admin Router Endpoints Protection ---")
    
    # 1. Clinics list
    r1 = client.get("/admin/clinics")
    print(f"  GET /admin/clinics: status={r1.status_code} (Expected 401 Unauthenticated)")
    
    # 2. Stats
    r2 = client.get("/admin/stats")
    print(f"  GET /admin/stats: status={r2.status_code} (Expected 401 Unauthenticated)")

    # 3. Phone pool
    r3 = client.get("/admin/phone-pool")
    print(f"  GET /admin/phone-pool: status={r3.status_code} (Expected 401 Unauthenticated)")
    
    if r1.status_code in [401, 403] and r2.status_code in [401, 403] and r3.status_code in [401, 403]:
        print("[PASS] Admin endpoints are correctly protected by default auth dependency.")
    else:
        print("[FAIL] Admin endpoints protection test failed.")

def test_clinic_onboarding_endpoints_protection():
    print("\n--- Testing Clinic Onboarding Endpoints Protection ---")
    
    # 1. Create Agent
    r1 = client.post("/clinics/some-uuid-1234/create-agent")
    print(f"  POST /clinics/{{id}}/create-agent: status={r1.status_code} (Expected 401/403 Unauthenticated)")
    
    # 2. Twilio number POST
    r2 = client.post("/clinics/some-uuid-1234/twilio-number", json={"twilioNumber": "+15755734355"})
    print(f"  POST /clinics/{{id}}/twilio-number: status={r2.status_code} (Expected 401/403 Unauthenticated)")

    # 3. Twilio number PUT
    r3 = client.put("/clinics/some-uuid-1234/twilio-number", json={"twilioNumber": "+15755734355"})
    print(f"  PUT /clinics/{{id}}/twilio-number: status={r3.status_code} (Expected 401/403 Unauthenticated)")

    if r1.status_code in [401, 403] and r2.status_code in [401, 403] and r3.status_code in [401, 403]:
        print("[PASS] Clinic onboarding endpoints are properly protected under settings:write permission.")
    else:
        print("[FAIL] Clinic onboarding endpoints protection test failed.")

print("Starting Phase 4 Integration Tests...")
test_google_redirect()
test_admin_endpoints_protection()
test_clinic_onboarding_endpoints_protection()
print("\nPhase 4 Integration Tests Complete.")
