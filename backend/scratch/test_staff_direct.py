import asyncio
import uuid
import sys
import os

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

from unittest.mock import MagicMock, patch, AsyncMock
from src.core.security import AuthenticatedUser
from src.api.routers.staff_router import (
    list_staff,
    invite_staff,
    update_staff_role,
    remove_staff,
    InviteStaffRequest,
    UpdateStaffRoleRequest
)
from fastapi import HTTPException

async def main():
    print("=== Testing staff_router.py directly ===")
    
    owner = AuthenticatedUser(
        user_id="owner-uuid-1",
        email="owner@sunriseclinic.com",
        clinic_id="clinic-uuid-1",
        clinic_name="Sunrise Medical Clinic",
        role="owner"
    )

    # 1. Test list_staff with owner
    with patch("src.api.routers.staff_router.supabase_read") as mock_sr, \
         patch("src.api.routers.staff_router.supabase") as mock_sb:
        mock_sr.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "cu-1",
                    "clinic_id": "clinic-uuid-1",
                    "supabase_user_id": "doc-uuid-1",
                    "email": "doc@sunriseclinic.com",
                    "name": "Dr. Sarah",
                    "role": "doctor",
                    "is_active": True,
                    "created_at": "2026-01-01T00:00:00Z"
                }
            ]
        )
        mock_sb.auth.admin.list_users.return_value = []
        res = await list_staff(auth=owner)
        assert len(res["data"]) == 2  # Doc + Owner auto-injected
        assert any(m["role"] == "owner" for m in res["data"])
        assert any(m["role"] == "doctor" for m in res["data"])
        print("[PASS] list_staff passed (owner auto-injected + DB staff returned)")

    # 2. Test invite_staff with valid roles
    for r in ["doctor", "front_desk", "read_only", "owner"]:
        with patch("src.api.routers.staff_router.supabase_read") as mock_sr, \
             patch("src.api.routers.staff_router.supabase") as mock_sb, \
             patch("src.api.routers.staff_router.email_service.send_staff_invite_email", new_callable=AsyncMock) as mock_email, \
             patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:
            
            mock_sr.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.auth.admin.list_users.return_value = []
            mock_sb.auth.admin.create_user.return_value = MagicMock(user=MagicMock(id="new-uid"))
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
                data=[{
                    "id": "cu-new",
                    "clinic_id": "clinic-uuid-1",
                    "supabase_user_id": "new-uid",
                    "email": f"test_{r}@clinic.com",
                    "name": f"Test {r.title()}",
                    "role": r,
                    "is_active": True,
                    "created_at": "2026-08-15T09:00:00Z"
                }]
            )
            req = InviteStaffRequest(email=f"test_{r}@clinic.com", name=f"Test {r.title()}", role=r)
            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.1"
            
            invite_res = await invite_staff(body=req, request=mock_request, auth=owner)
            assert invite_res["success"] is True
            assert invite_res["data"]["role"] == r
            assert mock_email.called
            assert mock_audit.called
    print("[PASS] invite_staff passed for all 4 roles (doctor, front_desk, read_only, owner)")

    # 3. Test invite_staff invalid role
    try:
        req = InviteStaffRequest(email="invalid@clinic.com", name="Invalid", role="superadmin")
        await invite_staff(body=req, request=MagicMock(), auth=owner)
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 400
        print("[PASS] invite_staff rejected invalid role with 400")

    # 4. Test invite_staff duplicate email
    with patch("src.api.routers.staff_router.supabase_read") as mock_sr:
        mock_sr.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "existing-1"}]
        )
        try:
            req = InviteStaffRequest(email="existing@clinic.com", name="Existing", role="doctor")
            await invite_staff(body=req, request=MagicMock(), auth=owner)
            assert False, "Should have raised duplicate HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert "already a member" in e.detail
            print("[PASS] invite_staff duplicate check passed with 400")

    # 5. Test update_staff_role
    with patch("src.api.routers.staff_router.supabase") as mock_sb, \
         patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:
        mock_sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "cu-1", "supabase_user_id": "doc-uuid-1", "role": "owner"}]
        )
        body = UpdateStaffRoleRequest(role="owner")
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        res = await update_staff_role(user_id="doc-uuid-1", body=body, request=mock_request, auth=owner)
        assert res["success"] is True
        assert mock_audit.called
        print("[PASS] update_staff_role passed")

    # 6. Test update_staff_role self demotion prevention
    try:
        body = UpdateStaffRoleRequest(role="doctor")
        await update_staff_role(user_id="owner-uuid-1", body=body, request=MagicMock(), auth=owner)
        assert False, "Should have prevented self demotion"
    except HTTPException as e:
        assert e.status_code == 400
        assert "demote" in e.detail
        print("[PASS] update_staff_role prevented owner self-demotion")

    # 7. Test remove_staff
    with patch("src.api.routers.staff_router.supabase") as mock_sb, \
         patch("src.api.routers.staff_router.audit_service.log", new_callable=AsyncMock) as mock_audit:
        mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "cu-1"}]
        )
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        res = await remove_staff(user_id="doc-uuid-1", request=mock_request, auth=owner)
        assert res["success"] is True
        assert mock_audit.called
        print("[PASS] remove_staff passed")

    # 8. Test remove_staff self-removal prevention
    try:
        await remove_staff(user_id="owner-uuid-1", request=MagicMock(), auth=owner)
        assert False, "Should have prevented self removal"
    except HTTPException as e:
        assert e.status_code == 400
        assert "cannot remove yourself" in e.detail
        print("[PASS] remove_staff prevented owner self-removal")

    print("\nALL BACKEND STAFF ROUTER TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(main())
