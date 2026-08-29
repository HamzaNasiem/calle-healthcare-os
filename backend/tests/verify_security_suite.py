import asyncio
import os
import sys
import unittest

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.routers.security_router import (
    _validate_ip_or_cidr,
    _extract_ip,
    get_security_settings,
    update_security_settings,
    get_ip_whitelist,
    add_ip_whitelist,
    delete_ip_whitelist,
    toggle_ip_whitelist,
    get_mfa_status,
    enroll_mfa_factor,
    verify_mfa_factor,
    disable_mfa_factor,
    list_audit_logs,
    export_audit_logs_csv,
    verify_audit_integrity,
    get_active_sessions,
    revoke_user_session,
    revoke_all_user_sessions,
    SecuritySettingsUpdate,
    IPWhitelistEntryCreate,
    IPWhitelistToggle,
    MFAVerifyRequest,
    MFADisableRequest
)
from src.core.security import AuthenticatedUser
from src.core.logger import scrub_phi
from src.services.audit_service import audit_service


class DummyRequest:
    def __init__(self, headers=None, client_host="192.168.1.50"):
        self.headers = headers or {}
        class Client:
            def __init__(self, host):
                self.host = host
        self.client = Client(client_host)
        self.url = type("URL", (), {"path": "/security/test"})()


class TestSecurityAndAuditing(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.auth = AuthenticatedUser(
            user_id="test-sec-user-101",
            email="security_auditor@sunriseclinic.com",
            clinic_id="clinic-test-uuid-999",
            clinic_name="Sunrise Test Clinic",
            role="owner"
        )
        self.dummy_req = DummyRequest(
            headers={"x-forwarded-for": "203.0.113.195, 10.0.0.1", "user-agent": "Mozilla/5.0 Test Suite"}
        )

    def test_ip_validation(self):
        # Valid IPv4
        self.assertEqual(_validate_ip_or_cidr("192.168.1.1"), "192.168.1.1")
        # Valid CIDR IPv4
        self.assertEqual(_validate_ip_or_cidr("10.0.0.0/24"), "10.0.0.0/24")
        # Valid IPv6
        self.assertEqual(_validate_ip_or_cidr("2001:db8::1"), "2001:db8::1")
        # Valid CIDR IPv6
        self.assertEqual(_validate_ip_or_cidr("2001:db8::/32"), "2001:db8::/32")

        # Invalid formats raise HTTPException
        with self.assertRaises(Exception):
            _validate_ip_or_cidr("not-an-ip")
        with self.assertRaises(Exception):
            _validate_ip_or_cidr("256.256.256.256")
        with self.assertRaises(Exception):
            _validate_ip_or_cidr("192.168.1.1/40")

    def test_ip_extraction(self):
        req = DummyRequest(headers={"cf-connecting-ip": "198.51.100.42"})
        self.assertEqual(_extract_ip(req), "198.51.100.42")
        req2 = DummyRequest(headers={"x-forwarded-for": "203.0.113.10, 10.0.0.1"})
        self.assertEqual(_extract_ip(req2), "203.0.113.10")

    def test_phi_scrubbing(self):
        text = "Patient John Doe with email john.doe@med.org and phone (555) 234-5678, DOB 1980-04-12"
        scrubbed = scrub_phi(text)
        self.assertNotIn("john.doe@med.org", scrubbed)
        self.assertNotIn("(555) 234-5678", scrubbed)
        self.assertNotIn("1980-04-12", scrubbed)
        self.assertIn("[REDACTED_EMAIL]", scrubbed)
        self.assertIn("[REDACTED_PHONE]", scrubbed)
        self.assertIn("[REDACTED_DOB]", scrubbed)

    async def test_security_settings_lifecycle(self):
        # 1. Get Settings
        res = await get_security_settings(self.dummy_req, self.auth)
        self.assertTrue(res["success"])
        data = res["data"]
        self.assertEqual(data["clinic_id"], self.auth.clinic_id)
        self.assertIn("idle_session_timeout_minutes", data)
        self.assertIn("phi_scrubbing_enabled", data)

        # 2. Update Settings
        update_res = await update_security_settings(
            SecuritySettingsUpdate(
                idle_session_timeout_minutes=30,
                phi_scrubbing_enabled=True,
                ip_whitelist_enabled=True
            ),
            self.dummy_req,
            self.auth
        )
        self.assertTrue(update_res["success"])
        self.assertEqual(update_res["data"]["idle_session_timeout_minutes"], 30)
        self.assertTrue(update_res["data"]["phi_scrubbing_enabled"])
        self.assertTrue(update_res["data"]["ip_whitelist_enabled"])

    async def test_ip_whitelist_management(self):
        # 1. Add normal IP
        add_res1 = await add_ip_whitelist(
            IPWhitelistEntryCreate(ip_or_cidr="192.168.10.5", label="Branch Office"),
            self.dummy_req,
            self.auth
        )
        self.assertTrue(add_res1["success"])
        entry1_id = add_res1["data"]["entry"]["id"]

        # 2. Add CIDR subnet
        add_res2 = await add_ip_whitelist(
            IPWhitelistEntryCreate(ip_or_cidr="172.16.0.0/16", label="Corporate VPN"),
            self.dummy_req,
            self.auth
        )
        self.assertTrue(add_res2["success"])
        entry2_cidr = "172.16.0.0/16"

        # 3. Duplicate rejection
        with self.assertRaises(Exception):
            await add_ip_whitelist(
                IPWhitelistEntryCreate(ip_or_cidr="192.168.10.5", label="Duplicate"),
                self.dummy_req,
                self.auth
            )

        # 4. Toggle Whitelist
        tog_res = await toggle_ip_whitelist(
            IPWhitelistToggle(enabled=True),
            self.dummy_req,
            self.auth
        )
        self.assertTrue(tog_res["success"])
        self.assertTrue(tog_res["data"]["enabled"])

        # 5. Delete by ID
        del_res1 = await delete_ip_whitelist(entry1_id, self.dummy_req, self.auth)
        self.assertTrue(del_res1["success"])

        # 6. Delete by CIDR string path
        del_res2 = await delete_ip_whitelist(entry2_cidr, self.dummy_req, self.auth)
        self.assertTrue(del_res2["success"])

    async def test_mfa_flow(self):
        # 1. Check Initial MFA Status
        status1 = await get_mfa_status(self.dummy_req, self.auth)
        self.assertTrue(status1["success"])

        # 2. Enroll MFA
        enroll = await enroll_mfa_factor(self.dummy_req, self.auth)
        self.assertTrue(enroll.get("success", False) or "totp" in enroll or "id" in enroll)
        factor_id = enroll.get("id") or enroll.get("data", {}).get("id")

        # 3. Verify MFA
        verify = await verify_mfa_factor(
            MFAVerifyRequest(factor_id=factor_id, code="123456"),
            self.dummy_req,
            self.auth
        )
        self.assertTrue(verify["success"])

        # 4. Check Updated MFA Status (Should be active)
        status2 = await get_mfa_status(self.dummy_req, self.auth)
        self.assertTrue(status2["success"])
        self.assertTrue(status2["data"]["is_active"])

        # 5. Disable MFA
        disable = await disable_mfa_factor(
            MFADisableRequest(factor_id=factor_id),
            self.dummy_req,
            self.auth
        )
        self.assertTrue(disable["success"])

        # 6. Check Deactivated MFA Status
        status3 = await get_mfa_status(self.dummy_req, self.auth)
        self.assertFalse(status3["data"]["is_active"])

    async def test_audit_logs_and_cryptographic_verification(self):
        # Trigger an audit event
        await audit_service.log(
            clinic_id=self.auth.clinic_id,
            user_id=self.auth.user_id,
            user_email=self.auth.email,
            action="security.test_event_logged",
            resource_type="audit_test",
            resource_id="res-123",
            details={"patient_phone": "(555) 000-1111", "status": "ok"},
            request=self.dummy_req
        )

        # Allow background task to process
        await asyncio.sleep(0.05)

        # 1. Query Audit Logs
        logs_res = await list_audit_logs(
            action="all",
            search=None,
            resource_type=None,
            date_from=None,
            date_to=None,
            page=1,
            limit=20,
            auth=self.auth
        )
        self.assertTrue(logs_res["success"])
        self.assertGreater(len(logs_res["data"]), 0)
        self.assertIn("meta", logs_res)

        # 2. Query with Wildcard Filter
        cat_res = await list_audit_logs(
            action="security.*",
            search=None,
            resource_type=None,
            date_from=None,
            date_to=None,
            page=1,
            limit=20,
            auth=self.auth
        )
        self.assertTrue(cat_res["success"])
        for item in cat_res["data"]:
            self.assertTrue(item["action"].startswith("security."))

        # 3. Cryptographic Chain Integrity Check
        int_res = await verify_audit_integrity(self.auth)
        self.assertTrue(int_res["success"])
        self.assertEqual(int_res["data"]["status"], "VALID")
        self.assertTrue(int_res["data"]["is_tamper_free"])
        self.assertEqual(int_res["data"]["algorithm"], "SHA-256-HMAC-CHAIN")
        self.assertIn("last_hash", int_res["data"])

        # 4. CSV Export
        csv_res = await export_audit_logs_csv(
            self.dummy_req,
            action="all",
            date_from=None,
            date_to=None,
            auth=self.auth
        )
        self.assertEqual(csv_res.media_type, "text/csv")
        body_text = csv_res.body.decode("utf-8")
        self.assertIn("Event ID", body_text)
        self.assertIn("Timestamp (UTC)", body_text)
        self.assertIn("Action / Event Type", body_text)

    async def test_sessions_management(self):
        # 1. Get active sessions
        sess_res = await get_active_sessions(self.dummy_req, self.auth)
        self.assertTrue(sess_res["success"])
        self.assertIsInstance(sess_res["data"], list)

        # 2. Record a session
        mock_sess_id = "test-session-uuid-1"
        from src.services.session_service import session_service
        await session_service.create_session(
            user_id=self.auth.user_id,
            email=self.auth.email,
            clinic_id=self.auth.clinic_id,
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0 Test"
        )
        
        class MockSessionReq:
            async def json(self):
                return {"session_id": mock_sess_id}
            headers = {"user-agent": "Test"}
            client = type("Client", (), {"host": "127.0.0.1"})()

        # 3. Revoke all other sessions
        rev_all_res = await revoke_all_user_sessions(self.dummy_req, self.auth)
        self.assertTrue(rev_all_res["success"])


if __name__ == "__main__":
    unittest.main()
