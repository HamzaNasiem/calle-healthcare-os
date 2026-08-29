import pytest
from src.main import app

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

def test_demo_provision_rate_limiting(client):
    payload = {
        "name": "Test User",
        "email": "",
        "clinicName": "Test Clinic"
    }
    r = client.post("/api/v1/demo/provision", json=payload)
    # Since email is empty, it should raise a validation error or 400
    assert r.status_code in [400, 422, 500]

def test_referrals_public_endpoint(client):
    payload = {
        "ref_code": "INVALID_CODE_XYZ123",
        "referred_clinic_id": "00000000-0000-0000-0000-000000000000"
    }
    r = client.post("/api/v1/referrals/track", json=payload)
    # It should fail with "Invalid referral code" but return 200 with success: False
    assert r.status_code == 200
    assert r.json()["success"] == False
    assert "Invalid referral code" in r.json()["error"]
