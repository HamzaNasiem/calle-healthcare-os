import requests
import json
from src.core.database import supabase

BASE_URL = "http://127.0.0.1:8000/api"

def cleanup(email, clinic_id=None):
    if clinic_id:
        supabase.table("clinics").delete().eq("id", clinic_id).execute()
    users = supabase.auth.admin.list_users()
    for u in users:
        if u.email == email:
            supabase.auth.admin.delete_user(u.id)
            break

def test_signup(email, clinic_name="Test Clinic"):
    print(f"\n--- Testing: {email} ---")
    try:
        r = requests.post(f"{BASE_URL}/auth/signup", json={
            "email": email,
            "password": "SecurePass123!",
            "clinicName": clinic_name,
            "timezone": "America/Chicago"
        }, timeout=30)
        data = r.json()
        if r.status_code == 200 and data.get("token"):
            print(f"  PASS: token received, clinicId={data['clinicId']}")
            cleanup(email, data["clinicId"])
            print(f"  Cleaned up.")
        else:
            print(f"  FAIL: status={r.status_code}, response={data}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Test the exact emails the user tried from the browser
test_signup("subnextopoa@gmail.com", "Hamza Clinic")
test_signup("zia@zia.com", "Zia Clinic")
test_signup("softpioneers.com@gmail.com", "Softpioneers Clinic")

print("\nDone.")
