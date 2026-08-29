import asyncio
import io
import json
import zipfile
import sys
from fastapi.testclient import TestClient

from src.main import app

def run_tests():
    client = TestClient(app, base_url="http://localhost:8000")
    auth_headers = {"Authorization": "Bearer demo_jwt_token_sunrise_2026"}
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    
    print("Testing 1: GET /clinics/{id}/export?format=json...")
    res1 = client.get(f"/api/v1/clinics/{clinic_id}/export?format=json", headers=auth_headers)
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
    assert "attachment; filename=" in res1.headers.get("content-disposition", "")
    data1 = res1.json()
    assert "export_timestamp" in data1
    assert "clinic_id" in data1
    assert "patients" in data1
    assert "appointments" in data1
    print("[PASS] JSON export passed. Patients count:", len(data1.get("patients", [])))

    print("Testing 2: GET /clinics/{id}/export?format=csv...")
    res2 = client.get(f"/api/v1/clinics/{clinic_id}/export?format=csv", headers=auth_headers)
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
    assert res2.headers["content-type"] == "application/zip"
    zip_bytes = io.BytesIO(res2.content)
    with zipfile.ZipFile(zip_bytes, "r") as z:
        files = z.namelist()
        assert "clinic_profile.csv" in files
        assert "patients.csv" in files
        assert "appointments.csv" in files
    print("[PASS] CSV zip export passed. Files inside archive:", files)

    print("Testing 3: Soft-delete invalid confirmation...")
    res3 = client.post(
        f"/api/v1/clinics/{clinic_id}/soft-delete",
        json={"confirmation": "WRONG_PHRASE", "reason": "Testing"},
        headers=auth_headers
    )
    assert res3.status_code == 400, f"Expected 400, got {res3.status_code}: {res3.text}"
    print("[PASS] Soft-delete invalid confirmation properly rejected with 400.")

    print("Testing 4: Soft-delete valid confirmation...")
    res4 = client.post(
        f"/api/v1/clinics/{clinic_id}/soft-delete",
        json={"confirmation": "DELETE ACCOUNT", "reason": "Testing soft delete"},
        headers=auth_headers
    )
    assert res4.status_code == 200, f"Expected 200, got {res4.status_code}: {res4.text}"
    assert res4.json()["success"] is True
    print("[PASS] Soft-delete valid confirmation passed.")

    print("Testing 5: Factory reset invalid confirmation...")
    res5 = client.post(
        f"/api/v1/clinics/{clinic_id}/factory-reset",
        json={"confirmation": "INCORRECT"},
        headers=auth_headers
    )
    assert res5.status_code == 400, f"Expected 400, got {res5.status_code}: {res5.text}"
    print("[PASS] Factory reset invalid confirmation properly rejected with 400.")

    print("Testing 6: Factory reset valid confirmation...")
    res6 = client.post(
        f"/api/v1/clinics/{clinic_id}/factory-reset",
        json={"confirmation": "DELETE EVERYTHING"},
        headers=auth_headers
    )
    assert res6.status_code == 200, f"Expected 200, got {res6.status_code}: {res6.text}"
    assert res6.json()["success"] is True
    print("[PASS] Factory reset valid confirmation passed.")

    print("\n=======================================================")
    print("ALL DANGER ZONE AUDIT & FUNCTIONALITY TESTS PASSED 100%!")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
