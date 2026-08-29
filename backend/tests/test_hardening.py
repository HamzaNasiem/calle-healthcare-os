import pytest
import time
from fastapi.testclient import TestClient
from src.main import app
from src.core.config import settings

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer mock_token"}

def test_detailed_health_success(client, monkeypatch):
    # Mock Twilio, Retell, and Supabase to return success
    monkeypatch.setattr("src.main.settings.TWILIO_ACCOUNT_SID", "ACmock")
    monkeypatch.setattr("src.main.settings.TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setattr("src.main.settings.RETELL_API_KEY", "key")
    
    # Mock Twilio Client
    class MockTwilioAccount:
        status = "active"
    class MockTwilioClient:
        def __init__(self, *args, **kwargs):
            self.api = type("API", (), {
                "v2010": type("V2010", (), {
                    "accounts": lambda sid: type("AccountFetch", (), {
                        "fetch": lambda: MockTwilioAccount()
                    })
                })
            })
    monkeypatch.setattr("twilio.rest.Client", MockTwilioClient)
    
    # Mock Retell Client
    class MockRetellClient:
        def __init__(self, *args, **kwargs):
            self.agent = type("Agent", (), {
                "list": lambda: []
            })
    monkeypatch.setattr("retell.Retell", MockRetellClient)
    
    # Mock Supabase
    monkeypatch.setattr("src.core.database.supabase_read", type("MockDB", (), {
        "table": lambda name: type("MockTable", (), {
            "select": lambda *args, **kwargs: type("MockSelect", (), {
                "limit": lambda n: type("MockLimit", (), {
                    "execute": lambda: type("MockData", (), {"data": [{"id": "c1"}]})()
                })
            })
        })
    }))
    
    response = client.get("/health/detailed")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "healthy"
    assert res_data["database"] == "healthy"
    assert res_data["twilio"] == "healthy"
    assert res_data["retell"] == "healthy"

def test_detailed_health_unhealthy_db(client, monkeypatch):
    # Mock Supabase to raise exception
    monkeypatch.setattr("src.core.database.supabase_read", type("MockDB", (), {
        "table": lambda name: type("MockTable", (), {
            "select": lambda *args, **kwargs: type("MockSelect", (), {
                "limit": lambda n: type("MockLimit", (), {
                    "execute": lambda: exec("raise(Exception('Connection lost'))")
                })
            })
        })
    }))
    
    # Bypass Twilio and Retell
    monkeypatch.setattr("src.main.settings.TWILIO_ACCOUNT_SID", None)
    monkeypatch.setattr("src.main.settings.RETELL_API_KEY", None)
    
    response = client.get("/health/detailed")
    assert response.status_code == 503
    res_data = response.json()
    assert res_data["status"] == "unhealthy"
    assert "unhealthy" in res_data["database"]

def test_admin_auth_api_key(client, monkeypatch):
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "super_secret_admin_key")
    
    # Request admin endpoint with valid API key
    response = client.get("/api/v1/admin/clinics", headers={"X-Admin-Key": "super_secret_admin_key"})
    # It should pass auth check, but might fail on mocked DB table logic (expected status code 200 or 500/400 but NOT 401/403)
    assert response.status_code in [200, 500, 400]

def test_admin_auth_invalid_api_key(client, monkeypatch):
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "super_secret_admin_key")
    
    # Request with wrong API key, no Authorization header
    response = client.get("/api/v1/admin/clinics", headers={"X-Admin-Key": "wrong_key"})
    assert response.status_code == 401

def test_admin_auth_ip_whitelist_allowed(client, monkeypatch):
    monkeypatch.setattr("src.core.config.settings.ADMIN_IP_WHITELIST_STR", "127.0.0.1,localhost,testserver,testclient")
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "super_secret_admin_key")
    
    response = client.get("/api/v1/admin/clinics", headers={"X-Admin-Key": "super_secret_admin_key"})
    assert response.status_code in [200, 500, 400]

def test_admin_auth_ip_whitelist_blocked(client, monkeypatch):
    # Set whitelist to other IPs
    monkeypatch.setattr("src.core.config.settings.ADMIN_IP_WHITELIST_STR", "192.168.1.1,10.0.0.1")
    monkeypatch.setattr("src.core.config.settings.ADMIN_API_KEY", "super_secret_admin_key")
    
    response = client.get("/api/v1/admin/clinics", headers={"X-Admin-Key": "super_secret_admin_key"})
    assert response.status_code == 403
    assert "not authorized" in response.json()["error"]

def test_jwt_expiry_guard_24h(client, monkeypatch):
    import base64
    import json
    
    # Create a token payload issued 25 hours ago (25 * 3600 seconds)
    expired_iat = int(time.time()) - (25 * 3600)
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode('utf-8').rstrip('=')
    payload = base64.urlsafe_b64encode(json.dumps({"iat": expired_iat, "sub": "123"}).encode('utf-8')).decode('utf-8').rstrip('=')
    expired_token = f"{header}.{payload}.signature"
    
    response = client.get("/api/v1/patients", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert "expired" in response.json()["error"]

def test_csv_export_patients(client, monkeypatch):
    from src.core.security import AuthenticatedUser, get_current_user_with_role, require_active_subscription
    mock_user = AuthenticatedUser(
        user_id="mock_user_id",
        email="test@example.com",
        role="owner",
        clinic_id="17641801-58ed-49b1-9f75-d6d46fbe78c5",
        clinic_name="Mock Clinic"
    )
    
    app.dependency_overrides[get_current_user_with_role] = lambda: mock_user
    app.dependency_overrides[require_active_subscription] = lambda: mock_user
    
    # Mock supabase_read
    monkeypatch.setattr("src.api.routers.patients_router.supabase_read", type("MockDB", (), {
        "table": lambda name: type("MockTable", (), {
            "select": lambda *args, **kwargs: type("MockSelect", (), {
                "eq": lambda *args, **kwargs: type("MockEq", (), {
                    "execute": lambda *args, **kwargs: type("MockData", (), {
                        "data": [{"id": "p1", "name": "Sarah", "phone": "+123", "email": "s@ex.com"}]
                    })()
                })()
            })()
        })
    }))
    
    try:
        response = client.get("/export/patients.csv", headers={"Authorization": "Bearer mock_token"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Sarah" in response.text
        assert "Patient ID" in response.text
    finally:
        app.dependency_overrides.clear()
