"""
Tests for Integrations Router — backend/src/api/routers/integrations_router.py.
Covers Google Calendar, Telnyx, Twilio, Retell AI, and Stripe connection statuses,
settings updates, disconnect flows, and connectivity tests.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from src.main import app
from src.core.security import require_permission, get_current_user_with_role, AuthenticatedUser

# ------------------------------------------------------------------------------
# Fixtures and overrides
# ------------------------------------------------------------------------------

MOCK_OWNER = AuthenticatedUser(
    user_id="user-owner-1",
    email="owner@testclinic.com",
    clinic_id="clinic-integration-123",
    clinic_name="Test Integrations Clinic",
    role="owner",
)

def _override_auth():
    return MOCK_OWNER


@pytest.fixture(autouse=True)
def setup_auth_overrides():
    app.dependency_overrides[get_current_user_with_role] = _override_auth
    app.dependency_overrides[require_permission("settings:read")] = _override_auth
    app.dependency_overrides[require_permission("settings:write")] = _override_auth
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False) as c:
        yield c


def _mock_clinic_data(
    google_refresh_token="mock_refresh_token",
    telnyx_number="+15755734355",
    twilio_number="+15551234567",
    retell_agent_id="agent_1234567890",
    stripe_customer_id="cus_test123",
    subscription_status="active",
    subscription_plan="growth"
):
    return {
        "id": "clinic-integration-123",
        "name": "Test Integrations Clinic",
        "owner_email": "owner@testclinic.com",
        "phone_number": "+15551234567",
        "twilio_number": twilio_number,
        "telnyx_number": telnyx_number,
        "retell_agent_id": retell_agent_id,
        "google_calendar_id": "primary",
        "google_refresh_token": google_refresh_token,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": "sub_test123",
        "subscription_status": subscription_status,
        "subscription_plan": subscription_plan,
        "timezone": "America/Chicago",
        "business_hours": {"mon": "08:00-18:00"},
        "appointment_types": [{"name": "Initial Eval", "duration": 60}],
        "is_active": True,
    }


# ------------------------------------------------------------------------------
# Test Cases
# ------------------------------------------------------------------------------

def test_get_integrations_status_connected(client):
    """Test GET /api/v1/integrations/status returns all connected services correctly."""
    clinic = _mock_clinic_data()
    mock_res = MagicMock()
    mock_res.data = clinic
    
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        resp = client.get("/api/v1/integrations/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["clinic_id"] == "clinic-integration-123"
        
        # Check Google
        assert data["data"]["google_calendar"]["connected"] is True
        assert data["data"]["google_calendar"]["calendar_id"] == "primary"
        
        # Check Telnyx
        assert data["data"]["telnyx"]["connected"] is True
        assert data["data"]["telnyx"]["phone_number"] == "+15755734355"
        
        # Check Twilio
        assert data["data"]["twilio"]["connected"] is True
        
        # Check Retell
        assert data["data"]["retell"]["connected"] is True
        assert data["data"]["retell"]["agent_id"] == "agent_1234567890"
        
        # Check Stripe
        assert data["data"]["stripe"]["connected"] is True
        assert data["data"]["stripe"]["subscription_status"] == "active"
        assert data["data"]["stripe"]["subscription_plan"] == "growth"


def test_get_integrations_status_disconnected(client):
    """Test GET /api/v1/integrations/status handles unconfigured/disconnected services."""
    clinic = _mock_clinic_data(
        google_refresh_token=None,
        telnyx_number=None,
        twilio_number=None,
        retell_agent_id=None,
        stripe_customer_id=None,
        subscription_status="trial",
        subscription_plan="starter"
    )
    mock_res = MagicMock()
    mock_res.data = clinic
    
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        resp = client.get("/api/v1/integrations/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["google_calendar"]["connected"] is False
        assert data["data"]["telnyx"]["connected"] is False
        assert data["data"]["retell"]["connected"] is False


def test_update_integrations_settings(client):
    """Test PUT /api/v1/integrations/settings updates Telnyx number and Google Calendar ID."""
    existing = _mock_clinic_data()
    updated = _mock_clinic_data(telnyx_number="+15759998888")
    
    mock_existing_res = MagicMock()
    mock_existing_res.data = existing
    
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr, \
         patch("src.api.routers.integrations_router.db_update_clinic", return_value=updated) as mock_update, \
         patch("src.api.routers.integrations_router.audit_service.log", new_callable=AsyncMock):
        
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_existing_res
        mock_sr.table.return_value = chain

        payload = {
            "telnyx_number": "+15759998888",
            "google_calendar_id": "clinic-calendar@group.calendar.google.com"
        }
        resp = client.put("/api/v1/integrations/settings", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["telnyx"]["phone_number"] == "+15759998888"


def test_disconnect_google_calendar(client):
    """Test POST /api/v1/integrations/google/disconnect clears refresh token and calendar ID."""
    disconnected = _mock_clinic_data(google_refresh_token=None)
    disconnected["google_calendar_id"] = None
    
    with patch("src.api.routers.integrations_router.db_update_clinic", return_value=disconnected) as mock_update, \
         patch("src.api.routers.integrations_router.audit_service.log", new_callable=AsyncMock):
        
        resp = client.post("/api/v1/integrations/google/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["google_calendar"]["connected"] is False
        assert "Google Calendar disconnected" in data["message"]


def test_retell_sync_or_create(client):
    """Test POST /api/v1/integrations/retell/create synchronizes agent prompt."""
    clinic = _mock_clinic_data()
    mock_res = MagicMock()
    mock_res.data = clinic
    
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr, \
         patch("src.api.routers.integrations_router.voice_service.update_agent_prompt", new_callable=AsyncMock) as mock_prompt, \
         patch("src.api.routers.integrations_router.audit_service.log", new_callable=AsyncMock):
        
        mock_prompt.return_value = {"success": True, "data": {"agentId": "agent_1234567890"}}
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        resp = client.post("/api/v1/integrations/retell/create")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["agent_id"] == "agent_1234567890"


def test_integration_connectivity_checks(client):
    """Test POST /api/v1/integrations/test/{service} for all supported services."""
    clinic = _mock_clinic_data()
    mock_res = MagicMock()
    mock_res.data = clinic
    
    with patch("src.api.routers.integrations_router.supabase_read") as mock_sr, \
         patch("src.services.calendar_service._get_google_credentials", return_value=(MagicMock(), clinic)):
        
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = mock_res
        mock_sr.table.return_value = chain

        # 1. Google Test
        resp_google = client.post("/api/v1/integrations/test/google")
        assert resp_google.status_code == 200
        assert resp_google.json()["success"] is True

        # 2. Telnyx Test
        resp_telnyx = client.post("/api/v1/integrations/test/telnyx")
        assert resp_telnyx.status_code == 200
        assert resp_telnyx.json()["success"] is True

        # 3. Twilio Test
        resp_twilio = client.post("/api/v1/integrations/test/twilio")
        assert resp_twilio.status_code == 200
        assert resp_twilio.json()["success"] is True

        # 4. Retell Test
        resp_retell = client.post("/api/v1/integrations/test/retell")
        assert resp_retell.status_code == 200
        assert resp_retell.json()["success"] is True

        # 5. Stripe Test
        resp_stripe = client.post("/api/v1/integrations/test/stripe")
        assert resp_stripe.status_code == 200
        assert resp_stripe.json()["success"] is True
