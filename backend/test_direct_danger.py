import asyncio
import io
import json
import zipfile
import sys
import os

sys.path.insert(0, r"D:\projects\bytelytic-os-single\backend")
os.chdir(r"D:\projects\bytelytic-os-single\backend")

from src.api.routers.clinics_router import export_clinic_data, soft_delete_clinic, factory_reset, SoftDeleteRequest, FactoryReset
from src.core.security import AuthenticatedUser

async def main():
    print("=== STARTING DANGER ZONE INTEGRATION TESTS ===")
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    auth_owner = AuthenticatedUser(
        user_id="demo-user-001",
        email="admin@sunriseclinic.com",
        clinic_id=clinic_id,
        clinic_name="Sunrise Medical Clinic",
        role="owner"
    )
    auth_doctor = AuthenticatedUser(
        user_id="demo-user-002",
        email="doctor@sunriseclinic.com",
        clinic_id=clinic_id,
        clinic_name="Sunrise Medical Clinic",
        role="doctor"
    )

    # Mock Request
    class MockRequest:
        client = None
        headers = {}
    mock_req = MockRequest()

    # TEST 1: Full Clinic Data Export (JSON)
    print("\n[TEST 1] Full Clinic Data Export (JSON)...")
    res_json = await export_clinic_data(
        id=clinic_id,
        request=mock_req,
        format="json",
        auth=auth_owner
    )
    assert res_json.media_type == "application/json"
    assert "attachment; filename=" in res_json.headers["Content-Disposition"]
    payload = json.loads(res_json.body.decode("utf-8"))
    assert payload["clinic_id"] == clinic_id
    assert "patients" in payload
    assert "appointments" in payload
    assert "calls" in payload
    assert "sms_messages" in payload
    assert "revenue_events" in payload
    assert "staff" in payload
    print(f"[PASS] JSON Export passed! Metadata: {payload.get('metadata')}")

    # TEST 2: Full Clinic Data Export (CSV ZIP)
    print("\n[TEST 2] Full Clinic Data Export (CSV ZIP)...")
    res_csv = await export_clinic_data(
        id=clinic_id,
        request=mock_req,
        format="csv",
        auth=auth_owner
    )
    assert res_csv.media_type == "application/zip"
    assert "attachment; filename=" in res_csv.headers["Content-Disposition"]
    zip_bytes = io.BytesIO(res_csv.body)
    with zipfile.ZipFile(zip_bytes, "r") as z:
        files = z.namelist()
        assert "clinic_profile.csv" in files
        assert "patients.csv" in files
        assert "appointments.csv" in files
        assert "calls.csv" in files
        assert "sms_messages.csv" in files
    print(f"[PASS] CSV Zip Export passed! Archived files: {files}")

    # TEST 3: Unauthorized Export Attempt by Doctor role
    print("\n[TEST 3] Role Authorization Guard on Export...")
    try:
        await export_clinic_data(
            id=clinic_id,
            request=mock_req,
            format="json",
            auth=auth_doctor
        )
        assert False, "Should have raised 403 Forbidden"
    except Exception as e:
        assert getattr(e, "status_code", None) == 403
        print(f"[PASS] Doctor export correctly blocked with 403: {e.detail}")

    # TEST 4: Soft Delete with Invalid Confirmation
    print("\n[TEST 4] Soft Delete Invalid Confirmation...")
    try:
        await soft_delete_clinic(
            id=clinic_id,
            req=SoftDeleteRequest(confirmation="INVALID", reason="Testing"),
            request=mock_req,
            auth=auth_owner
        )
        assert False, "Should have raised 400"
    except Exception as e:
        assert getattr(e, "status_code", None) == 400
        print(f"[PASS] Soft delete invalid confirmation rejected with 400: {e.detail}")

    # TEST 5: Soft Delete with Valid Confirmation
    print("\n[TEST 5] Soft Delete with Valid Confirmation...")
    res_soft = await soft_delete_clinic(
        id=clinic_id,
        req=SoftDeleteRequest(confirmation="DELETE ACCOUNT", reason="Practice restructuring"),
        request=mock_req,
        auth=auth_owner
    )
    assert res_soft["success"] is True
    print(f"[PASS] Soft delete succeeded: {res_soft['message']}")

    # TEST 6: Factory Reset with Invalid Confirmation
    print("\n[TEST 6] Factory Reset Invalid Confirmation...")
    try:
        await factory_reset(
            id=clinic_id,
            reset=FactoryReset(confirmation="WRONG TEXT"),
            request=mock_req,
            auth=auth_owner
        )
        assert False, "Should have raised 400"
    except Exception as e:
        assert getattr(e, "status_code", None) == 400
        print(f"[PASS] Factory reset invalid confirmation rejected with 400: {e.detail}")

    # TEST 7: Factory Reset with Valid Confirmation
    print("\n[TEST 7] Factory Reset with Valid Confirmation...")
    res_wipe = await factory_reset(
        id=clinic_id,
        reset=FactoryReset(confirmation="DELETE EVERYTHING"),
        request=mock_req,
        auth=auth_owner
    )
    assert res_wipe["success"] is True
    print(f"[PASS] Factory reset succeeded: {res_wipe['message']}")

    print("\n" + "="*60)
    print("ALL DANGER ZONE BACKEND UNIT & INTEGRATION TESTS PASSED 100%!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
