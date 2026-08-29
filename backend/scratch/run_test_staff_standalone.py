import os
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock_service_key")
os.environ.setdefault("SUPABASE_ANON_KEY", "mock_anon_key")
os.environ.setdefault("RETELL_API_KEY", "mock_retell_key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "mock_google_id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "mock_google_secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/google/callback")
os.environ.setdefault("OPENROUTER_API_KEY", "mock_openrouter_key")
os.environ.setdefault("API_BASE_URL", "http://localhost:3000")
os.environ.setdefault("DASHBOARD_URL", "http://localhost:5173")

# Mock database before importing app
mock_db = MagicMock()
mock_db_read = MagicMock()

import src.core.database
src.core.database.supabase = mock_db
src.core.database.supabase_read = mock_db_read
src.core.database.auth_client = mock_db

import src.core.security
src.core.security.auth_client = mock_db
src.core.security.supabase = mock_db

from fastapi.testclient import TestClient
from src.main import app
from src.core.security import AuthenticatedUser, get_current_user_with_role

OWNER_AUTH = AuthenticatedUser(
    user_id="user-owner-123",
    email="owner@sunriseclinic.com",
    clinic_id="clinic-test-uuid",
    clinic_name="Sunrise Medical Clinic",
    role="owner",
)

DOCTOR_AUTH = AuthenticatedUser(
    user_id="user-doctor-456",
    email="doctor@sunriseclinic.com",
    clinic_id="clinic-test-uuid",
    clinic_name="Sunrise Medical Clinic",
    role="doctor",
)

FRONT_DESK_AUTH = AuthenticatedUser(
    user_id="user-frontdesk-789",
    email="frontdesk@sunriseclinic.com",
    clinic_id="clinic-test-uuid",
    clinic_name="Sunrise Medical Clinic",
    role="front_desk",
)

READ_ONLY_AUTH = AuthenticatedUser(
    user_id="user-readonly-999",
    email="readonly@sunriseclinic.com",
    clinic_id="clinic-test-uuid",
    clinic_name="Sunrise Medical Clinic",
    role="read_only",
)

client = TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False)

def _override_as_owner():
    app.dependency_overrides[get_current_user_with_role] = lambda: OWNER_AUTH

def _override_as_doctor():
    app.dependency_overrides[get_current_user_with_role] = lambda: DOCTOR_AUTH

def _clear_overrides():
    app.dependency_overrides.clear()

def run_all_tests():
    print("================================================================")
    print("STARTING TEST CLIENT RUN ON /api/v1/staff ENDPOINTS")
    print("================================================================")
    
    # 1. test_list_staff_as_owner
    _override_as_owner()
    try:
        mock_records = [
            {
                "id": "cu-1",
                "clinic_id": OWNER_AUTH.clinic_id,
                "supabase_user_id": "user-doctor-456",
                "email": "doctor@sunriseclinic.com",
                "name": "Dr. Sarah Jenkins",
                "role": "doctor",
                "is_active": True,
                "created_at": "2026-01-10T12:00:00Z"
            }
        ]
        with patch("src.api.routers.staff_router.supabase_read") as mock_sr, \
             patch("src.api.routers.staff_router.supabase") as mock_sb:
            mock_sr.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_records)
            mock_sb.auth.admin.list_users.return_value = []

            resp = client.get("/api/v1/staff")
            assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
            data = resp.json().get("data", [])
            emails = [u["email"] for u in data]
            assert "doctor@sunriseclinic.com" in emails
            assert "owner@sunriseclinic.com" in emails
            print("[PASS] 1. test_list_staff_as_owner (Owner list returned & enriched with owner)")
    finally:
        _clear_overrides()

    # 2. test_list_staff_as_doctor_forbidden
    _override_as_doctor()
    try:
        resp = client.get("/api/v1/staff")
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}"
        print("[PASS] 2. test_list_staff_as_doctor_forbidden (Doctor blocked with 403)")
    finally:
        _clear_overrides()

    # 3. test_invite_staff_valid_roles
    _override_as_owner()
    try:
        for role in ["doctor", "front_desk", "read_only", "owner"]:
            with patch("src.api.routers.staff_router.supabase_read") as mock_sr, \
                 patch("src.api.routers.staff_router.supabase") as mock_sb, \
                 patch("src.api.routers.staff_router.email_service.send_staff_invite_email", new_callable=AsyncMock) as mock_email, \
                 patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:

                mock_sr.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                mock_sb.auth.admin.list_users.return_value = []
                mock_sb.auth.admin.create_user.return_value = MagicMock(user=MagicMock(id="new-user-id-99"))
                mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": "new-cu-id",
                        "clinic_id": OWNER_AUTH.clinic_id,
                        "supabase_user_id": "new-user-id-99",
                        "email": f"new_{role}@clinic.com",
                        "name": f"New {role.title()}",
                        "role": role,
                        "created_at": "2026-08-15T09:00:00Z"
                    }]
                )

                payload = {
                    "email": f"new_{role}@clinic.com",
                    "name": f"New {role.title()}",
                    "role": role
                }

                resp = client.post("/api/v1/staff/invite", json=payload)
                assert resp.status_code == 200, f"Expected 200 for {role}, got {resp.status_code}: {resp.text}"
                res_data = resp.json()
                assert res_data.get("success") is True
                assert res_data["data"]["role"] == role
                assert mock_email.called
                assert mock_audit.called
        print("[PASS] 3. test_invite_staff_valid_roles (All roles: doctor, front_desk, read_only, owner invited)")
    finally:
        _clear_overrides()

    # 4. test_invite_staff_invalid_role
    _override_as_owner()
    try:
        payload = {
            "email": "invalid_role@clinic.com",
            "name": "Invalid Role User",
            "role": "superadmin"
        }
        resp = client.post("/api/v1/staff/invite", json=payload)
        assert resp.status_code == 400
        assert "Invalid role" in resp.text
        print("[PASS] 4. test_invite_staff_invalid_role (superadmin rejected with 400)")
    finally:
        _clear_overrides()

    # 5. test_invite_staff_invalid_email
    _override_as_owner()
    try:
        payload = {
            "email": "not-an-email",
            "name": "Invalid Email",
            "role": "doctor"
        }
        resp = client.post("/api/v1/staff/invite", json=payload)
        assert resp.status_code == 400
        assert "valid email" in resp.text
        print("[PASS] 5. test_invite_staff_invalid_email (bad email rejected with 400)")
    finally:
        _clear_overrides()

    # 6. test_invite_staff_duplicate
    _override_as_owner()
    try:
        with patch("src.api.routers.staff_router.supabase_read") as mock_sr:
            mock_sr.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "existing-id", "email": "doctor@sunriseclinic.com"}]
            )

            payload = {
                "email": "doctor@sunriseclinic.com",
                "name": "Dr. Sarah",
                "role": "doctor"
            }
            resp = client.post("/api/v1/staff/invite", json=payload)
            assert resp.status_code == 400
            assert "already a member" in resp.text
            print("[PASS] 6. test_invite_staff_duplicate (Duplicate email rejected with 400)")
    finally:
        _clear_overrides()

    # 7. test_invite_staff_non_owner_forbidden
    _override_as_doctor()
    try:
        payload = {
            "email": "test@clinic.com",
            "name": "Test User",
            "role": "front_desk"
        }
        resp = client.post("/api/v1/staff/invite", json=payload)
        assert resp.status_code == 403
        print("[PASS] 7. test_invite_staff_non_owner_forbidden (Doctor cannot invite staff - 403)")
    finally:
        _clear_overrides()

    # 8. test_update_staff_role_success
    _override_as_owner()
    try:
        with patch("src.api.routers.staff_router.supabase") as mock_sb, \
             patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:
            
            mock_sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "cu-1", "supabase_user_id": "user-doctor-456", "role": "owner"}]
            )

            resp = client.put("/api/v1/staff/user-doctor-456/role", json={"role": "owner"})
            assert resp.status_code == 200
            assert resp.json().get("success") is True
            assert mock_audit.called
            print("[PASS] 8. test_update_staff_role_success (Owner updated staff role)")
    finally:
        _clear_overrides()

    # 9. test_update_staff_role_self_demotion_prevented
    _override_as_owner()
    try:
        resp = client.put(f"/api/v1/staff/{OWNER_AUTH.user_id}/role", json={"role": "doctor"})
        assert resp.status_code == 400
        assert "demote" in resp.text.lower()
        print("[PASS] 9. test_update_staff_role_self_demotion_prevented (Self-demotion blocked with 400)")
    finally:
        _clear_overrides()

    # 10. test_update_staff_role_invalid_role
    _override_as_owner()
    try:
        resp = client.put("/api/v1/staff/user-doctor-456/role", json={"role": "invalid_role"})
        assert resp.status_code == 400
        assert "Invalid role" in resp.text
        print("[PASS] 10. test_update_staff_role_invalid_role (Invalid role update rejected with 400)")
    finally:
        _clear_overrides()

    # 11. test_remove_staff_success
    _override_as_owner()
    try:
        with patch("src.api.routers.staff_router.supabase") as mock_sb, \
             patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:

            mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "cu-1"}])

            resp = client.delete("/api/v1/staff/user-doctor-456")
            assert resp.status_code == 200
            assert resp.json().get("success") is True
            assert mock_audit.called
            print("[PASS] 11. test_remove_staff_success (Owner removed staff member)")
    finally:
        _clear_overrides()

    # 12. test_remove_staff_self_removal_prevented
    _override_as_owner()
    try:
        resp = client.delete(f"/api/v1/staff/{OWNER_AUTH.user_id}")
        assert resp.status_code == 400
        assert "cannot remove yourself" in resp.text.lower()
        print("[PASS] 12. test_remove_staff_self_removal_prevented (Self removal blocked with 400)")
    finally:
        _clear_overrides()

    # 13. test_remove_staff_non_owner_forbidden
    _override_as_doctor()
    try:
        resp = client.delete("/api/v1/staff/user-frontdesk-789")
        assert resp.status_code == 403
        print("[PASS] 13. test_remove_staff_non_owner_forbidden (Doctor cannot delete staff - 403)")
    finally:
        _clear_overrides()

    print("================================================================")
    print("ALL 13 FASTAPI /api/v1/staff ENDPOINT AND RBAC TESTS PASSED 100%!")
    print("================================================================")

if __name__ == "__main__":
    run_all_tests()
