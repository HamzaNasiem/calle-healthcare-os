"""
Tests for EHR/EMR Integrations — ehr_router.py and connectors.
Supports DrChrono, AthenaHealth, Epic Systems, Cerner / Oracle Health, FHIR R4, Jane App, SimplePractice, Zapier.
All endpoints require owner role.
DB and external API calls are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from fastapi.testclient import TestClient

from src.main import app
from src.core.security import get_current_user_with_role, AuthenticatedUser
from src.services.ehr.jane_connector import JaneConnector
from src.services.ehr.simplepractice_connector import SimplePracticeConnector
from src.services.ehr.zapier_connector import ZapierConnector
from src.services.ehr.drchrono_connector import DrChronoConnector
from src.services.ehr.athena_connector import AthenaHealthConnector
from src.services.ehr.fhir_connector import FHIRConnector, EpicConnector, CernerConnector

# ------------------------------------------------------------------------------
# Shared fixtures and overrides
# ------------------------------------------------------------------------------

MOCK_AUTH = AuthenticatedUser(
    user_id="user-owner",
    email="owner@clinic.com",
    clinic_id="clinic-001",
    clinic_name="Integrations Clinic",
    role="owner",
)


def _make_dep_override():
    async def _override():
        return MOCK_AUTH
    return _override


@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False) as c:
        yield c


def _mock_supabase(data=None):
    mock = MagicMock()
    result = MagicMock()
    result.data = data if data is not None else []
    
    chain = MagicMock()
    chain.execute.return_value = result
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.upsert.return_value = chain
    chain.delete.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    
    mock.table.return_value = chain
    return mock, result


# ------------------------------------------------------------------------------
# Endpoints tests
# ------------------------------------------------------------------------------

def test_list_supported_providers(client):
    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.get("/api/v1/ehr/providers")
        assert r.status_code == 200
        providers = r.json().get("data", [])
        provider_ids = [p["id"] for p in providers]
        assert "drchrono" in provider_ids
        assert "athenahealth" in provider_ids
        assert "epic" in provider_ids
        assert "cerner" in provider_ids
        assert "fhir" in provider_ids
        assert "jane" in provider_ids
        assert "simplepractice" in provider_ids
        assert "zapier" in provider_ids
    finally:
        app.dependency_overrides.clear()


def test_list_integrations(client, monkeypatch):
    mock_data = [
        {
            "id": "int-1",
            "provider_name": "drchrono",
            "access_token": "token123",
            "client_id": "cid-drchrono",
            "sync_frequency": "15m",
            "sync_enabled": True,
            "is_active": True,
        }
    ]
    mock_sb, _ = _mock_supabase(mock_data)
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.get("/api/v1/ehr/integrations")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["provider_name"] == "drchrono"
        assert data[0]["has_access_token"] is True
        assert data[0]["sync_frequency"] == "15m"
    finally:
        app.dependency_overrides.clear()


def test_create_or_update_integration(client, monkeypatch):
    mock_sb, _ = _mock_supabase([{"provider_name": "drchrono", "is_active": True}])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.post(
            "/api/v1/ehr/integrations",
            json={
                "provider_name": "drchrono",
                "client_id": "drchrono_client",
                "client_secret": "drchrono_secret",
                "access_token": "token",
                "sync_frequency": "1h",
                "sync_enabled": True,
            }
        )
        assert r.status_code == 200
        assert "data" in r.json()
    finally:
        app.dependency_overrides.clear()


def test_create_or_update_fhir_integration(client, monkeypatch):
    mock_sb, _ = _mock_supabase([{"provider_name": "epic", "is_active": True}])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.post(
            "/api/v1/ehr/integrations",
            json={
                "provider_name": "epic",
                "fhir_endpoint": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
                "access_token": "epic_bearer_token",
                "sync_frequency": "realtime",
                "sync_enabled": True,
            }
        )
        assert r.status_code == 200
        assert "data" in r.json()
    finally:
        app.dependency_overrides.clear()


def test_patch_integration(client, monkeypatch):
    mock_sb, _ = _mock_supabase([{"provider_name": "athenahealth", "sync_frequency": "daily", "sync_enabled": False}])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.patch(
            "/api/v1/ehr/integrations/athenahealth",
            json={"sync_frequency": "daily", "sync_enabled": False}
        )
        assert r.status_code == 200
        assert r.json()["data"]["sync_frequency"] == "daily"
    finally:
        app.dependency_overrides.clear()


def test_delete_integration(client, monkeypatch):
    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.delete("/api/v1/ehr/integrations/drchrono")
        assert r.status_code == 200
        assert r.json()["data"]["deleted"] is True
    finally:
        app.dependency_overrides.clear()


def test_delete_integration_invalid_provider(client):
    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.delete("/api/v1/ehr/integrations/invalid_provider")
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_verify_integration_not_found(client, monkeypatch):
    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.post("/api/v1/ehr/integrations/epic/verify")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_verify_integration_success(client, monkeypatch):
    mock_sb, _ = _mock_supabase([{"provider_name": "jane", "access_token": "tok"}])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        with patch.object(JaneConnector, "verify_connection", return_value=True) as mock_verify:
            r = client.post("/api/v1/ehr/integrations/jane/verify")
            assert r.status_code == 200
            assert r.json()["data"]["connected"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_verify_integration_inline_payload(client, monkeypatch):
    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        with patch.object(FHIRConnector, "verify_connection", return_value=True) as mock_verify:
            r = client.post(
                "/api/v1/ehr/integrations/epic/verify",
                json={"fhir_endpoint": "https://fhir.epic.com/test", "access_token": "temp_tok"}
            )
            assert r.status_code == 200
            assert r.json()["data"]["connected"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_manual_sync(client, monkeypatch):
    mock_sb, _ = _mock_supabase([{"provider_name": "drchrono", "is_active": True, "sync_enabled": True}])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.post("/api/v1/ehr/sync/run")
        assert r.status_code == 200
        assert r.json()["data"]["synced"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_patient_not_found(client, monkeypatch):
    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.post("/api/v1/ehr/sync/patient/pat-not-exist")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_patient_success(client, monkeypatch):
    mock_patient = {"id": "pat-1", "name": "Alice Smith"}
    mock_integrations = [{"provider_name": "zapier", "webhook_secret": "http://zapier.com"}]
    
    mock_sb = MagicMock()
    mock_pat_res = MagicMock(data=[mock_patient])
    mock_int_res = MagicMock(data=mock_integrations)
    
    pat_chain = MagicMock()
    pat_chain.execute.return_value = mock_pat_res
    pat_chain.eq.return_value = pat_chain
    pat_chain.select.return_value = pat_chain
    pat_chain.limit.return_value = pat_chain
    
    int_chain = MagicMock()
    int_chain.execute.return_value = mock_int_res
    int_chain.eq.return_value = int_chain
    int_chain.select.return_value = int_chain
    int_chain.update.return_value = int_chain
    
    def table_route(name):
        if name == "patients":
            return pat_chain
        return int_chain
        
    mock_sb.table.side_effect = table_route
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        with patch.object(ZapierConnector, "create_patient", return_value="zap-id-123") as mock_create:
            r = client.post("/api/v1/ehr/sync/patient/pat-1")
            assert r.status_code == 200
            assert r.json()["data"]["results"]["zapier"]["success"] is True
            assert r.json()["data"]["results"]["zapier"]["ehr_id"] == "zap-id-123"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_appointment_success(client, monkeypatch):
    mock_appt = {"id": "appt-1", "patient_id": "pat-1", "datetime": "2026-06-15T10:00:00Z"}
    mock_integrations = [{"provider_name": "zapier", "webhook_secret": "http://zapier.com"}]
    
    mock_sb = MagicMock()
    mock_appt_res = MagicMock(data=[mock_appt])
    mock_int_res = MagicMock(data=mock_integrations)
    
    appt_chain = MagicMock()
    appt_chain.execute.return_value = mock_appt_res
    appt_chain.eq.return_value = appt_chain
    appt_chain.select.return_value = appt_chain
    appt_chain.limit.return_value = appt_chain
    
    int_chain = MagicMock()
    int_chain.execute.return_value = mock_int_res
    int_chain.eq.return_value = int_chain
    int_chain.select.return_value = int_chain
    int_chain.update.return_value = int_chain
    
    def table_route(name):
        if name == "appointments":
            return appt_chain
        return int_chain
        
    mock_sb.table.side_effect = table_route
    monkeypatch.setattr("src.api.routers.ehr_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        with patch.object(ZapierConnector, "create_appointment", return_value="zap-appt-123") as mock_create:
            r = client.post("/api/v1/ehr/sync/appointment/appt-1")
            assert r.status_code == 200
            assert r.json()["data"]["results"]["zapier"]["success"] is True
            assert r.json()["data"]["results"]["zapier"]["ehr_id"] == "zap-appt-123"
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Connectors tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drchrono_connector(monkeypatch):
    integration = {
        "access_token": "drchrono_token",
        "provider_clinic_id": "12345",
        "provider_name": "drchrono",
    }
    conn = DrChronoConnector(integration)
    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.services.ehr.drchrono_connector.supabase", mock_sb)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 7777}
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    async def mock_get(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post), patch("httpx.AsyncClient.get", side_effect=mock_get):
        pat_id = await conn.create_patient("clinic-1", {"name": "John Doe", "email": "j@doe.com"})
        assert pat_id == "7777"

        appt_id = await conn.create_appointment("clinic-1", {"patient_id": "7777", "scheduled_time": "2026-06-15T10:00:00Z"})
        assert appt_id == "7777"

        connected = await conn.verify_connection("clinic-1")
        assert connected is True


@pytest.mark.asyncio
async def test_athena_connector(monkeypatch):
    integration = {
        "access_token": "athena_token",
        "provider_clinic_id": "195900",
        "provider_name": "athenahealth",
    }
    conn = AthenaHealthConnector(integration)
    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.services.ehr.athena_connector.supabase", mock_sb)

    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"patientid": "5555"}]
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    async def mock_get(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post), patch("httpx.AsyncClient.get", side_effect=mock_get):
        pat_id = await conn.create_patient("clinic-1", {"name": "Jane Smith", "email": "jane@smith.com"})
        assert pat_id == "5555"

        connected = await conn.verify_connection("clinic-1")
        assert connected is True


@pytest.mark.asyncio
async def test_fhir_connector(monkeypatch):
    integration = {
        "fhir_endpoint": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        "access_token": "epic_tok",
        "provider_name": "epic",
    }
    conn = EpicConnector(integration)
    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.services.ehr.fhir_connector.supabase", mock_sb)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"resourceType": "CapabilityStatement", "id": "epic-patient-1"}
    mock_resp.status_code = 200
    mock_resp.headers = {"location": "https://fhir.epic.com/Patient/epic-patient-1"}
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    async def mock_get(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post), patch("httpx.AsyncClient.get", side_effect=mock_get):
        pat_id = await conn.create_patient("clinic-1", {"name": "FHIR Patient", "email": "fhir@test.com"})
        assert pat_id == "epic-patient-1"

        appt_id = await conn.create_appointment("clinic-1", {"patient_id": pat_id, "start_at": "2026-06-15T10:00:00Z"})
        assert appt_id == "epic-patient-1"

        connected = await conn.verify_connection("clinic-1")
        assert connected is True


@pytest.mark.asyncio
async def test_jane_connector_create_patient(monkeypatch):
    integration = {"access_token": "jane_token", "provider_clinic_id": "jane-c1"}
    conn = JaneConnector(integration)
    
    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.services.ehr.jane_connector.supabase", mock_sb)

    patient_data = {"id": "local-pat-1", "name": "Bob Miller", "email": "bob@miller.com"}
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 9999}
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    
    async def mock_post(*args, **kwargs):
        return mock_resp
        
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await conn.create_patient("clinic-1", patient_data)
        assert res == "9999"


@pytest.mark.asyncio
async def test_jane_connector_verify_connection(monkeypatch):
    integration = {"access_token": "jane_token", "provider_clinic_id": "jane-c1"}
    conn = JaneConnector(integration)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    async def mock_get(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        res = await conn.verify_connection("clinic-1")
        assert res is True


@pytest.mark.asyncio
async def test_simplepractice_connector_create_patient(monkeypatch):
    integration = {"access_token": "sp_token"}
    conn = SimplePracticeConnector(integration)

    mock_sb, _ = _mock_supabase([])
    monkeypatch.setattr("src.services.ehr.simplepractice_connector.supabase", mock_sb)

    patient_data = {"id": "local-pat-2", "name": "Sara Connor", "email": "sara@sky.net"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 8888}
    mock_resp.status_code = 201
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await conn.create_patient("clinic-1", patient_data)
        assert res == "8888"


@pytest.mark.asyncio
async def test_zapier_connector_create_patient():
    integration = {"webhook_secret": "https://hooks.zapier.com/hooks/catch/12345/abc"}
    conn = ZapierConnector(integration)

    mock_resp = MagicMock()
    mock_resp.text = "success"
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await conn.create_patient("clinic-1", {"name": "Zap Test"})
        assert res == "success"


def test_diagnose_fhir_endpoint(client):
    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "resourceType": "CapabilityStatement",
            "fhirVersion": "4.0.1",
            "software": {"name": "HAPI FHIR Server"},
            "rest": [{"resource": [{"type": "Patient"}, {"type": "Appointment"}]}],
        }
        mock_resp.raise_for_status = MagicMock()

        async def mock_get(*args, **kwargs):
            return mock_resp

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            r = client.post(
                "/api/v1/ehr/diagnostics/fhir",
                json={"fhir_endpoint": "https://hapi.fhir.org/baseR4", "access_token": "token123"}
            )
            assert r.status_code == 200
            data = r.json()["data"]
            assert data["online"] is True
            assert data["fhir_version"] == "4.0.1"
            assert data["software_name"] == "HAPI FHIR Server"
            assert "Patient" in data["supported_resources"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_fhir_connector_diagnose():
    conn = FHIRConnector({"fhir_endpoint": "https://hapi.fhir.org/baseR4", "access_token": "test_token"})
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "resourceType": "CapabilityStatement",
        "fhirVersion": "4.0.1",
        "software": {"name": "Epic Interconnect FHIR Server"},
        "rest": [{"resource": [{"type": "Patient"}]}],
    }

    async def mock_get(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        diag = await conn.diagnose_endpoint()
        assert diag["online"] is True
        assert diag["software_name"] == "Epic Interconnect FHIR Server"
        assert diag["latency_ms"] >= 0

