"""
test_staff.py
Comprehensive test suite for Team & Staff settings and RBAC guards.
Tests /api/v1/staff endpoints:
- GET /staff (List staff, RBAC owner vs non-owner)
- POST /staff/invite (Invite staff, role validation, duplicate checks, auth creation)
- PUT /staff/{user_id}/role (Role update, invalid role checks, self-demotion prevention)
- DELETE /staff/{user_id} (Remove staff, self-removal prevention)
"""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from src.main import app
from src.core.security import AuthenticatedUser, require_role, get_current_user_with_role

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


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False)


def _override_as_owner():
    app.dependency_overrides[get_current_user_with_role] = lambda: OWNER_AUTH


def _override_as_doctor():
    app.dependency_overrides[get_current_user_with_role] = lambda: DOCTOR_AUTH


def _clear_overrides():
    app.dependency_overrides.clear()


# =============================================================================
# 1. Staff List Tests (GET /api/v1/staff)
# =============================================================================

def test_list_staff_as_owner(client):
    """Owner should be able to view staff list and include enriched data."""
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
            assert resp.status_code == 200
            data = resp.json().get("data", [])
            
            # Should have the doctor and the owner included
            emails = [u["email"] for u in data]
            assert "doctor@sunriseclinic.com" in emails
            assert "owner@sunriseclinic.com" in emails
    finally:
        _clear_overrides()


def test_list_staff_as_doctor_forbidden(client):
    """Doctor should be rejected with 403 Forbidden on staff settings."""
    _override_as_doctor()
    try:
        resp = client.get("/api/v1/staff")
        assert resp.status_code == 403
    finally:
        _clear_overrides()


# =============================================================================
# 2. Staff Invite Tests (POST /api/v1/staff/invite)
# =============================================================================

def test_invite_staff_valid_roles(client):
    """Owner can invite staff with valid roles: doctor, front_desk, read_only, owner."""
    _override_as_owner()
    try:
        for role in ["doctor", "front_desk", "read_only", "owner"]:
            with patch("src.api.routers.staff_router.supabase_read") as mock_sr, \
                 patch("src.api.routers.staff_router.supabase") as mock_sb, \
                 patch("src.api.routers.staff_router.email_service.send_staff_invite_email", new_callable=AsyncMock) as mock_email, \
                 patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:

                # No duplicate in clinic_users
                mock_sr.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                # No existing user in auth
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
                assert resp.status_code == 200
                res_data = resp.json()
                assert res_data.get("success") is True
                assert res_data["data"]["role"] == role
                assert mock_email.called
                assert mock_audit.called
    finally:
        _clear_overrides()


def test_invite_staff_invalid_role(client):
    """Inviting with an invalid role (e.g. 'superadmin') must return 400."""
    _override_as_owner()
    try:
        payload = {
            "email": "invalid_role@clinic.com",
            "name": "Invalid Role User",
            "role": "superadmin"
        }
        resp = client.post("/api/v1/staff/invite", json=payload)
        assert resp.status_code == 400
        assert "Invalid role" in resp.json().get("detail", "")
    finally:
        _clear_overrides()


def test_invite_staff_invalid_email(client):
    """Inviting with an invalid email address must return 400."""
    _override_as_owner()
    try:
        payload = {
            "email": "not-an-email",
            "name": "Invalid Email",
            "role": "doctor"
        }
        resp = client.post("/api/v1/staff/invite", json=payload)
        assert resp.status_code == 400
        assert "valid email" in resp.json().get("detail", "")
    finally:
        _clear_overrides()


def test_invite_staff_duplicate(client):
    """Inviting an existing clinic member must return 400."""
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
            assert "already a member" in resp.json().get("detail", "")
    finally:
        _clear_overrides()


def test_invite_staff_non_owner_forbidden(client):
    """Non-owner roles cannot invite staff members."""
    _override_as_doctor()
    try:
        payload = {
            "email": "test@clinic.com",
            "name": "Test User",
            "role": "front_desk"
        }
        resp = client.post("/api/v1/staff/invite", json=payload)
        assert resp.status_code == 403
    finally:
        _clear_overrides()


# =============================================================================
# 3. Staff Role Update Tests (PUT /api/v1/staff/{user_id}/role)
# =============================================================================

def test_update_staff_role_success(client):
    """Owner can update staff member's role."""
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
    finally:
        _clear_overrides()


def test_update_staff_role_self_demotion_prevented(client):
    """Owner cannot demote themselves from the owner role."""
    _override_as_owner()
    try:
        resp = client.put(f"/api/v1/staff/{OWNER_AUTH.user_id}/role", json={"role": "doctor"})
        assert resp.status_code == 400
        assert "demote" in resp.json().get("detail", "").lower()
    finally:
        _clear_overrides()


def test_update_staff_role_invalid_role(client):
    """Updating to an invalid role returns 400."""
    _override_as_owner()
    try:
        resp = client.put("/api/v1/staff/user-doctor-456/role", json={"role": "invalid_role"})
        assert resp.status_code == 400
        assert "Invalid role" in resp.json().get("detail", "")
    finally:
        _clear_overrides()


# =============================================================================
# 4. Staff Remove Tests (DELETE /api/v1/staff/{user_id})
# =============================================================================

def test_remove_staff_success(client):
    """Owner can remove a staff member."""
    _override_as_owner()
    try:
        with patch("src.api.routers.staff_router.supabase") as mock_sb, \
             patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:

            mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "cu-1"}])

            resp = client.delete("/api/v1/staff/user-doctor-456")
            assert resp.status_code == 200
            assert resp.json().get("success") is True
            assert mock_audit.called
    finally:
        _clear_overrides()


def test_remove_staff_self_removal_prevented(client):
    """Owner cannot delete their own account."""
    _override_as_owner()
    try:
        resp = client.delete(f"/api/v1/staff/{OWNER_AUTH.user_id}")
        assert resp.status_code == 400
        assert "cannot remove yourself" in resp.json().get("detail", "").lower()
    finally:
        _clear_overrides()


def test_remove_staff_non_owner_forbidden(client):
    """Non-owner cannot remove staff members."""
    _override_as_doctor()
    try:
        resp = client.delete("/api/v1/staff/user-frontdesk-789")
        assert resp.status_code == 403
    finally:
        _clear_overrides()
