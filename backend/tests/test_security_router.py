import pytest
from src.api.routers.security_router import _validate_ip_or_cidr, DEFAULT_SECURITY_CONFIG

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer demo_jwt_token_sunrise_2026"}

def test_ip_validation_unit():
    # Valid IPv4
    assert _validate_ip_or_cidr("192.168.1.1") == "192.168.1.1"
    # Valid CIDR
    assert _validate_ip_or_cidr("10.0.0.0/24") == "10.0.0.0/24"
    # Valid IPv6
    assert _validate_ip_or_cidr("2001:db8::1") == "2001:db8::1"
    # Invalid IP raises
    with pytest.raises(Exception):
        _validate_ip_or_cidr("not-an-ip")
    with pytest.raises(Exception):
        _validate_ip_or_cidr("999.999.999.999")

def test_get_security_settings(client, auth_headers):
    response = client.get("/api/v1/security/settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "idle_session_timeout_minutes" in data["data"]
    assert "phi_scrubbing_enabled" in data["data"]
    assert "ip_whitelist_enabled" in data["data"]
    assert "ip_whitelist" in data["data"]

def test_update_security_settings(client, auth_headers):
    payload = {
        "idle_session_timeout_minutes": 30,
        "phi_scrubbing_enabled": True,
        "ip_whitelist_enabled": True
    }
    response = client.patch("/api/v1/security/settings", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["idle_session_timeout_minutes"] == 30
    assert data["data"]["phi_scrubbing_enabled"] is True

def test_ip_whitelist_lifecycle(client, auth_headers):
    # 1. Get whitelist
    get_res = client.get("/api/v1/security/ip-whitelist", headers=auth_headers)
    assert get_res.status_code == 200
    assert "whitelist" in get_res.json()["data"]

    # 2. Add valid IP
    add_res = client.post(
        "/api/v1/security/ip-whitelist",
        json={"ip_or_cidr": "192.168.1.100", "label": "Reception Desk Test"},
        headers=auth_headers
    )
    assert add_res.status_code == 201
    add_data = add_res.json()
    assert add_data["success"] is True
    entry_id = add_data["data"]["entry"]["id"]

    # 3. Add invalid IP format -> 400 Bad Request
    invalid_res = client.post(
        "/api/v1/security/ip-whitelist",
        json={"ip_or_cidr": "invalid-ip-format", "label": "Invalid IP"},
        headers=auth_headers
    )
    assert invalid_res.status_code == 400

    # 4. Toggle Whitelist
    toggle_res = client.post(
        "/api/v1/security/ip-whitelist/toggle",
        json={"enabled": True},
        headers=auth_headers
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["data"]["enabled"] is True

    # 5. Delete IP entry
    del_res = client.delete(f"/api/v1/security/ip-whitelist/{entry_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

def test_mfa_flow(client, auth_headers):
    # 1. Check MFA Status
    status_res = client.get("/api/v1/security/mfa/status", headers=auth_headers)
    assert status_res.status_code == 200
    assert "is_active" in status_res.json()["data"]

    # 2. Enroll MFA
    enroll_res = client.post("/api/v1/security/mfa/enroll", headers=auth_headers)
    assert enroll_res.status_code == 200
    enroll_data = enroll_res.json()
    assert "totp" in enroll_data or "id" in enroll_data
    factor_id = enroll_data.get("id", "mock-factor-123")

    # 3. Verify MFA with 6-digit code
    verify_res = client.post(
        "/api/v1/security/mfa/verify",
        json={"factor_id": factor_id, "code": "123456"},
        headers=auth_headers
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["success"] is True

    # 4. Disable MFA
    disable_res = client.post(
        "/api/v1/security/mfa/disable",
        json={"factor_id": factor_id},
        headers=auth_headers
    )
    assert disable_res.status_code == 200
    assert disable_res.json()["success"] is True

def test_audit_logs_and_integrity(client, auth_headers):
    # 1. Get Audit Logs
    logs_res = client.get("/api/v1/security/audit-logs?limit=10", headers=auth_headers)
    assert logs_res.status_code == 200
    logs_data = logs_res.json()
    assert logs_data["success"] is True
    assert isinstance(logs_data["data"], list)

    # 2. Verify Audit Chain Integrity
    integrity_res = client.get("/api/v1/security/audit-logs/verify-integrity", headers=auth_headers)
    assert integrity_res.status_code == 200
    int_data = integrity_res.json()
    assert int_data["success"] is True
    assert int_data["data"]["status"] == "VALID"
    assert int_data["data"]["is_tamper_free"] is True

    # 3. Export Audit Logs CSV
    export_res = client.get("/api/v1/security/audit-logs/export", headers=auth_headers)
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers.get("content-type", "")
    assert "attachment" in export_res.headers.get("content-disposition", "")
    assert "Event ID" in export_res.text

def test_sessions_endpoints(client, auth_headers):
    # 1. Get Sessions
    res = client.get("/api/v1/security/sessions", headers=auth_headers)
    assert res.status_code == 200
    assert "data" in res.json()
