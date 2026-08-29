import pytest
import io
import json
import zipfile
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer demo_jwt_token_sunrise_2026"}

def test_export_clinic_data_json(client, auth_headers):
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    res = client.get(f"/api/v1/clinics/{clinic_id}/export?format=json", headers=auth_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/json"
    assert "attachment; filename=" in res.headers.get("content-disposition", "")
    
    data = res.json()
    assert "export_timestamp" in data
    assert "clinic_id" in data
    assert "patients" in data
    assert "appointments" in data
    assert "calls" in data
    assert "sms_messages" in data
    assert "revenue_events" in data
    assert "metadata" in data

def test_export_clinic_data_csv_zip(client, auth_headers):
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    res = client.get(f"/api/v1/clinics/{clinic_id}/export?format=csv", headers=auth_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "attachment; filename=" in res.headers.get("content-disposition", "")
    
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as z:
        file_list = z.namelist()
        assert "clinic_profile.csv" in file_list
        assert "patients.csv" in file_list
        assert "appointments.csv" in file_list
        assert "calls.csv" in file_list
        assert "sms_messages.csv" in file_list

def test_export_unauthorized_clinic_id(client, auth_headers):
    other_clinic_id = "00000000-0000-0000-0000-000000000000"
    res = client.get(f"/api/v1/clinics/{other_clinic_id}/export?format=json", headers=auth_headers)
    assert res.status_code == 403

def test_soft_delete_invalid_confirmation(client, auth_headers):
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    res = client.post(
        f"/api/v1/clinics/{clinic_id}/soft-delete",
        json={"confirmation": "WRONG CONFIRMATION", "reason": "Testing"},
        headers=auth_headers
    )
    assert res.status_code == 400
    err_body = res.json()
    err_text = err_body.get("detail") or err_body.get("error") or str(err_body)
    assert "Invalid confirmation phrase" in err_text

def test_soft_delete_valid_confirmation(client, auth_headers):
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    res = client.post(
        f"/api/v1/clinics/{clinic_id}/soft-delete",
        json={"confirmation": "DELETE ACCOUNT", "reason": "Test soft deletion"},
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

def test_factory_reset_invalid_confirmation(client, auth_headers):
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    res = client.post(
        f"/api/v1/clinics/{clinic_id}/factory-reset",
        json={"confirmation": "NOT DELETE EVERYTHING"},
        headers=auth_headers
    )
    assert res.status_code == 400
    err_body = res.json()
    err_text = err_body.get("detail") or err_body.get("error") or str(err_body)
    assert "Invalid confirmation phrase" in err_text

def test_factory_reset_valid_confirmation(client, auth_headers):
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    res = client.post(
        f"/api/v1/clinics/{clinic_id}/factory-reset",
        json={"confirmation": "DELETE EVERYTHING"},
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
