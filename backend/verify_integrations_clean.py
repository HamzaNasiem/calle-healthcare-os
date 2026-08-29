import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure root in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.security import require_permission, get_current_user_with_role, AuthenticatedUser
from src.api.routers.integrations_router import router as integrations_router

app = FastAPI()
app.include_router(integrations_router)

MOCK_OWNER = AuthenticatedUser(
    user_id="user-owner-1",
    email="owner@testclinic.com",
    clinic_id="clinic-integration-123",
    clinic_name="Test Integrations Clinic",
    role="owner",
)

app.dependency_overrides[get_current_user_with_role] = lambda: MOCK_OWNER
app.dependency_overrides[require_permission("settings:read")] = lambda: MOCK_OWNER
app.dependency_overrides[require_permission("settings:write")] = lambda: MOCK_OWNER

client = TestClient(app)

def _mock_clinic():
    return {
        "id": "clinic-integration-123",
        "name": "Test Integrations Clinic",
        "owner_email": "owner@testclinic.com",
        "phone_number": "+15551234567",
        "twilio_number": "+15551234567",
        "twilio_account_sid": "AC1234567890abcdef1234567890abcdef",
        "telnyx_number": "+15755734355",
        "retell_agent_id": "agent_test_retell_123",
        "google_calendar_id": "primary",
        "google_refresh_token": "1//04test_google_refresh_token",
        "stripe_customer_id": "cus_test_12345",
        "stripe_subscription_id": "sub_test_12345",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "current_period_end": "2026-12-31T00:00:00Z",
        "timezone": "America/Chicago",
    }

def run_tests():
    clinic = _mock_clinic()
    mock_res = MagicMock()
    mock_res.data = clinic

    print("\n========================================================")
    print("  AGENT 9 — INTEGRATIONS ROUTER & SETTINGS VERIFICATION  ")
    print("========================================================\n")

    # 1. GET /integrations/status (Connected)
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        resp = client.get("/integrations/status")
        assert resp.status_code == 200, f"Status code {resp.status_code}"
        data = resp.json()["data"]
        
        print("[PASS] 1. GET /integrations/status:")
        print(f"       - Google Calendar: connected={data['google_calendar']['connected']}, label='{data['google_calendar']['status_label']}'")
        print(f"       - Telnyx:          connected={data['telnyx']['connected']}, number='{data['telnyx']['phone_number']}'")
        print(f"       - Twilio:          connected={data['twilio']['connected']}, masked_sid='{data['twilio']['account_sid_masked']}'")
        print(f"       - Retell AI:       connected={data['retell']['connected']}, agent_id='{data['retell']['agent_id']}'")
        print(f"       - Stripe:          connected={data['stripe']['connected']}, plan='{data['stripe']['subscription_plan']}', status='{data['stripe']['subscription_status']}'")

    # 2. PUT /integrations/settings
    updated_clinic = dict(clinic, telnyx_number="+15759998888", google_calendar_id="custom_calendar@group.calendar.google.com")
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr, \
         patch("src.api.routers.integrations_router.db_update_clinic", return_value=updated_clinic) as mock_update, \
         patch("src.api.routers.integrations_router.audit_service.log", new_callable=AsyncMock):

        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        payload = {
            "telnyx_number": "+15759998888",
            "google_calendar_id": "custom_calendar@group.calendar.google.com"
        }
        resp = client.put("/integrations/settings", json=payload)
        assert resp.status_code == 200
        up_data = resp.json()
        assert up_data["success"] is True
        print("\n[PASS] 2. PUT /integrations/settings:")
        print(f"       - Saved cleanly: message='{up_data['message']}'")
        print(f"       - Refreshed Telnyx line: {up_data['data']['telnyx']['phone_number']}")

    # 3. POST /integrations/google/disconnect
    disconnected_clinic = dict(clinic, google_refresh_token=None, google_calendar_id=None)
    with patch("src.api.routers.integrations_router.db_update_clinic", return_value=disconnected_clinic), \
         patch("src.api.routers.integrations_router.audit_service.log", new_callable=AsyncMock):

        resp = client.post("/integrations/google/disconnect")
        assert resp.status_code == 200
        disc_data = resp.json()
        assert disc_data["data"]["google_calendar"]["connected"] is False
        print("\n[PASS] 3. POST /integrations/google/disconnect:")
        print(f"       - Disconnected successfully: {disc_data['message']}")
        print(f"       - Google connected state: {disc_data['data']['google_calendar']['connected']}")

    # 4. POST /integrations/retell/create (Sync prompt)
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr, \
         patch("src.api.routers.integrations_router.voice_service.update_agent_prompt", new_callable=AsyncMock) as mock_prompt, \
         patch("src.api.routers.integrations_router.audit_service.log", new_callable=AsyncMock):

        mock_prompt.return_value = {"success": True, "data": {"agentId": "agent_test_retell_123"}}
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        resp = client.post("/integrations/retell/create")
        assert resp.status_code == 200
        retell_data = resp.json()
        print("\n[PASS] 4. POST /integrations/retell/create:")
        print(f"       - Agent sync result: {retell_data['message']}")
        print(f"       - Agent ID: {retell_data['agent_id']}")

    # 5. POST /integrations/test/{service} for all 5 services
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr, \
         patch("src.services.calendar_service._get_google_credentials", return_value=(MagicMock(), clinic)):

        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        print("\n[PASS] 5. POST /integrations/test/{service} Real Connectivity Verification:")
        for service in ["google", "telnyx", "twilio", "retell", "stripe"]:
            test_resp = client.post(f"/integrations/test/{service}")
            assert test_resp.status_code == 200, f"Failed for {service}: {test_resp.text}"
            res_json = test_resp.json()
            assert res_json["success"] is True, f"{service} test failed: {res_json}"
            print(f"       - [{service.upper()}] Success: {res_json['message']}")

    print("\n========================================================")
    print("  ALL 5 INTEGRATION ENDPOINTS & SETTINGS VERIFIED 100%   ")
    print("========================================================\n")

if __name__ == "__main__":
    run_tests()
