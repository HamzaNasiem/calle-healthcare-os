import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

# Add backend directory to sys.path
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

async def run_tests():
    print("==================================================")
    print("STARTING NOTIFICATION SERVICE & ROUTING AUDIT")
    print("==================================================")

    from src.services.notification_service import notification_service

    mock_clinic_data = {
        "id": "clinic-test-uuid",
        "name": "Sunrise Medical Clinic",
        "owner_email": "owner@sunrisemedical.com",
        "primary_doctor_phone": "+15551112233",
        "notifications_config": {
            "booking_confirmation_enabled": True,
            "cancellation_confirmation_enabled": True,
            "reminders_enabled": True,
            "recall_enabled": True,
            "followup_enabled": True,
            "insurance_enabled": True,
            "email_daily_report_enabled": True,
            "email_quota_alerts_enabled": True,
            "email_staff_alerts_enabled": True,
            "staff_alert_email": "urgent-staff@sunrisemedical.com",
            "staff_alert_phone": "+15559998877",
            "alert_on_negative_sentiment": True,
            "alert_on_missed_calls": True,
            "alert_on_noshow": True,
            "sound_alerts_enabled": True,
            "browser_notifications_enabled": True,
        }
    }

    # Test 1: Negative Sentiment Escalation Routing
    print("\n[TEST 1] Testing Negative Sentiment Escalation...")
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-test-uuid",
            notification_type="call.completed",
            title="Patient Call Negative Sentiment",
            body="Patient frustrated with wait time",
            metadata={"sentiment": "frustrated", "patient_phone": "+15550001111"}
        )

        assert routing_res["routed"] is True, "Expected routed to be True"
        assert routing_res["routed_to_email"] == "urgent-staff@sunrisemedical.com"
        assert routing_res["routed_to_phone"] == "+15559998877"
        assert "Negative Patient Sentiment" in routing_res["reason"]
        assert mock_email.await_count == 1, "Expected email alert sent"
        assert mock_sms.await_count == 1, "Expected SMS alert sent"
        print("  [OK] Negative Sentiment correctly routed to email and SMS!")

    # Test 2: Missed Call Escalation Routing
    print("\n[TEST 2] Testing Missed Call Alert Escalation...")
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-test-uuid",
            notification_type="call.missed",
            title="Missed Patient Call",
            body="Dropped call from +15554443322",
            metadata={"from_number": "+15554443322"}
        )

        assert routing_res["routed"] is True
        assert "Missed / Dropped Patient Call" in routing_res["reason"]
        assert mock_email.await_count == 1
        assert mock_sms.await_count == 1
        print("  [OK] Missed Call alert correctly routed to email and SMS!")

    # Test 3: No-Show Escalation Routing
    print("\n[TEST 3] Testing No-Show Alert Escalation...")
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-test-uuid",
            notification_type="noshow.detected",
            title="Patient No-Show Detected",
            body="Patient missed 2:00 PM appointment",
            metadata={"appointment_id": "appt-123"}
        )

        assert routing_res["routed"] is True
        assert "Patient No-Show Detected" in routing_res["reason"]
        assert mock_email.await_count == 1
        assert mock_sms.await_count == 1
        print("  [OK] No-Show alert correctly routed to email and SMS!")

    # Test 4: Trigger Test Alert (Simulated Dispatch)
    print("\n[TEST 4] Testing trigger_test_alert Dispatcher...")
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data
        mock_sup.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-test-id"}]

        routing_res = await notification_service.trigger_test_alert(
            clinic_id="clinic-test-uuid",
            alert_type="staff.alert",
            title="Manual Staff Escalation Test",
            body="Simulated alert from settings",
            metadata={"test": True}
        )

        assert routing_res["routed"] is True
        assert routing_res["routed_to_email"] == "urgent-staff@sunrisemedical.com"
        assert routing_res["routed_to_phone"] == "+15559998877"
        print("  [OK] trigger_test_alert returned accurate routing outcome!")

    # Test 5: Fallback to Clinic Defaults when custom staff fields are empty
    print("\n[TEST 5] Testing Default Fallback when staff fields are blank...")
    fallback_clinic_data = {
        "id": "clinic-test-uuid",
        "name": "Sunrise Medical Clinic",
        "owner_email": "primary-owner@sunrisemedical.com",
        "primary_doctor_phone": "+15557778899",
        "notifications_config": {
            "staff_alert_email": "",
            "staff_alert_phone": "",
            "email_staff_alerts_enabled": True,
            "alert_on_negative_sentiment": True,
            "alert_on_missed_calls": True,
            "alert_on_noshow": True,
        }
    }
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = fallback_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-test-uuid",
            notification_type="staff.alert",
            title="Staff Alert",
            body="Urgent notice",
            metadata={}
        )

        assert routing_res["routed"] is True
        assert routing_res["routed_to_email"] == "primary-owner@sunrisemedical.com"
        assert routing_res["routed_to_phone"] == "+15557778899"
        print("  [OK] Fallbacks correctly used owner_email and primary_doctor_phone!")

    # Test 6: Disabled Toggles (No Alerts Sent)
    print("\n[TEST 6] Testing Disabled Alert Toggles...")
    disabled_clinic_data = {
        "id": "clinic-test-uuid",
        "name": "Sunrise Medical Clinic",
        "owner_email": "owner@sunrisemedical.com",
        "primary_doctor_phone": "+15551112233",
        "notifications_config": {
            "staff_alert_email": "urgent@sunrisemedical.com",
            "staff_alert_phone": "+15559998877",
            "email_staff_alerts_enabled": False,
            "alert_on_negative_sentiment": False,
            "alert_on_missed_calls": False,
            "alert_on_noshow": False,
        }
    }
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = disabled_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-test-uuid",
            notification_type="noshow.detected",
            title="No-Show",
            body="Missed visit",
            metadata={}
        )

        assert routing_res["routed"] is False
        assert mock_email.await_count == 0
        assert mock_sms.await_count == 0
        print("  [OK] Disabled toggles correctly suppress all alerts!")

    # Test 7: Router Endpoint Test Alert (API test)
    print("\n[TEST 7] Testing Notifications Router Endpoints...")
    from fastapi import FastAPI
    from src.api.routers.notifications_router import router as notif_router
    from src.core.security import AuthenticatedUser, get_current_user_with_role, require_active_subscription

    test_app = FastAPI()
    test_app.include_router(notif_router)

    mock_auth_user = AuthenticatedUser(
        user_id="user-123",
        email="test@clinic.com",
        clinic_id="clinic-test-uuid",
        clinic_name="Sunrise Medical Clinic",
        role="owner"
    )

    test_app.dependency_overrides[require_active_subscription] = lambda: True
    test_app.dependency_overrides[get_current_user_with_role] = lambda: mock_auth_user

    client = TestClient(test_app)

    # 7.1 POST /notifications/test-alert
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock), \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock):
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data
        mock_sup.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-test"}]

        resp = client.post("/notifications/test-alert", json={
            "alert_type": "staff.alert",
            "title": "API Test Alert",
            "body": "Testing via test client"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["routed"] is True
        assert data["routed_to_email"] == "urgent-staff@sunrisemedical.com"
        print("  [OK] POST /notifications/test-alert verified 100%!")

    # 7.2 GET /notifications/config
    with patch("src.api.routers.notifications_router.supabase_read") as mock_read:
        mock_read.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data
        resp = client.get("/notifications/config")
        assert resp.status_code == 200
        conf_data = resp.json()["data"]
        assert conf_data["booking_confirmation_enabled"] is True
        assert conf_data["staff_alert_email"] == "urgent-staff@sunrisemedical.com"
        print("  [OK] GET /notifications/config verified 100%!")

    # 7.3 PUT /notifications/config
    with patch("src.api.routers.notifications_router.supabase") as mock_write:
        mock_write.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "clinic-test-uuid"}]
        new_conf = {**mock_clinic_data["notifications_config"], "reminders_enabled": False}
        resp = client.put("/notifications/config", json={"notifications_config": new_conf})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        print("  [OK] PUT /notifications/config verified 100%!")

    # 7.4 POST /notifications/read-all
    with patch("src.services.notification_service.supabase") as mock_sup:
        mock_sup.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        resp = client.post("/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        print("  [OK] POST /notifications/read-all verified 100%!")

    # 7.5 POST /notifications/{id}/read
    with patch("src.services.notification_service.supabase") as mock_sup:
        mock_sup.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "n-1"}]
        resp = client.post("/notifications/n-1/read")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        print("  [OK] POST /notifications/{id}/read verified 100%!")

    # Test 8: TCPA Quiet Hours Compliance
    print("\n[TEST 8] Testing TCPA Quiet Hours Compliance Engine...")
    from src.services.tcpa_service import tcpa_service
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    ny_tz = ZoneInfo("America/New_York")
    
    # 8.1 Late night: 11:30 PM EDT (TCPA curfew)
    night_time = datetime(2026, 9, 1, 23, 30, tzinfo=ny_tz)
    is_quiet, reason = tcpa_service.is_quiet_hours("America/New_York", now_override=night_time)
    assert is_quiet is True, "Expected 11:30 PM to be quiet hours"
    assert "TCPA Quiet Hours" in reason
    print("  [OK] 11:30 PM correctly identified as TCPA quiet hours!")

    # 8.2 Early morning: 6:30 AM EDT (TCPA curfew)
    morning_time = datetime(2026, 9, 1, 6, 30, tzinfo=ny_tz)
    is_quiet, reason = tcpa_service.is_quiet_hours("America/New_York", now_override=morning_time)
    assert is_quiet is True, "Expected 6:30 AM to be quiet hours"
    assert "TCPA Quiet Hours" in reason
    print("  [OK] 6:30 AM correctly identified as TCPA quiet hours!")

    # 8.3 Permitted business hours: 2:15 PM EDT (Allowed)
    day_time = datetime(2026, 9, 1, 14, 15, tzinfo=ny_tz)
    is_quiet, reason = tcpa_service.is_quiet_hours("America/New_York", now_override=day_time)
    assert is_quiet is False, "Expected 2:15 PM to be permitted"
    print("  [OK] 2:15 PM correctly allowed under TCPA!")

    # 8.4 Custom clinic quiet hours (e.g. 20:00 to 08:30)
    custom_conf = {
        "quiet_hours_enabled": True,
        "quiet_hours_start": "20:00",
        "quiet_hours_end": "08:30"
    }
    # 8:15 PM (20:15) with custom start 20:00
    evening_time = datetime(2026, 9, 1, 20, 15, tzinfo=ny_tz)
    is_quiet, reason = tcpa_service.is_quiet_hours("America/New_York", notifications_config=custom_conf, now_override=evening_time)
    assert is_quiet is True, "Expected 8:15 PM to be quiet hours under custom config"
    assert "Clinic Quiet Hours Active" in reason
    print("  [OK] Custom clinic quiet hours (20:00-08:30) enforced correctly!")

    # Test 9: Reminder Lead Time & Custom SMS Template Rendering
    print("\n[TEST 9] Testing Reminder Lead Time & Custom Template Rendering...")
    from src.services.sms_service import sms_service

    mock_appt = {
        "id": "appt-test-lead",
        "clinic_id": "clinic-test-uuid",
        "datetime": "2026-09-02T10:00:00Z",
        "patient_name": "Emma Watson",
        "patient_phone": "+15552223344",
        "clinic_name": "Sunrise Medical Care",
        "patients": {"name": "Emma Watson", "phone": "+15552223344"}
    }
    custom_clinic_notifs = {
        **mock_clinic_data,
        "notifications_config": {
            **mock_clinic_data["notifications_config"],
            "reminder_lead_time_hours": 48,
            "reminder_sms_template": "Hello {patient_name}! Reminder from {clinic_name} for your visit at {datetime}. Reply YES to confirm.",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "21:00",
            "quiet_hours_end": "08:00",
        }
    }

    with patch("src.services.sms_service.supabase") as mock_sup, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_send, \
         patch("src.services.tcpa_service.tcpa_service.is_quiet_hours", return_value=(False, "Allowed")):
        
        # Configure select responses: first appt, second clinic
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = [
            MagicMock(data=mock_appt),
            MagicMock(data=custom_clinic_notifs),
        ]
        mock_sup.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_appt])
        mock_send.return_value = {"success": True, "data": {"message_id": "msg-123"}}

        send_res = await sms_service.send_reminder("appt-test-lead")
        assert send_res["success"] is True
        
        # Verify that custom template was populated accurately
        call_kwargs = mock_send.call_args.kwargs
        rendered_body = call_kwargs.get("body", "")
        assert "Hello Emma Watson!" in rendered_body
        assert "Sunrise Medical Care" in rendered_body
        assert "Reply YES to confirm." in rendered_body
        print("  [OK] Custom SMS template rendered successfully with patient tokens!")

    print("\n==================================================")
    print("ALL 9 NOTIFICATION, TCPA & TEMPLATE AUDIT TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
