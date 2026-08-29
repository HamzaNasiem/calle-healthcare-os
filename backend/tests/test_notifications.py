import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

def test_notifications_route_protection(client):
    # Unauthenticated requests should be blocked with 401 or 403
    r = client.get("/api/v1/notifications")
    assert r.status_code in [401, 403]

def test_notifications_read_all_protection(client):
    r = client.post("/api/v1/notifications/read-all")
    assert r.status_code in [401, 403]

def test_notifications_read_one_protection(client):
    r = client.post("/api/v1/notifications/some-id/read")
    assert r.status_code in [401, 403]

def test_notifications_test_alert_protection(client):
    r = client.post("/api/v1/notifications/test-alert", json={"alert_type": "staff.alert"})
    assert r.status_code in [401, 403]

def test_notifications_config_protection(client):
    r = client.get("/api/v1/notifications/config")
    assert r.status_code in [401, 403]


@pytest.mark.asyncio
async def test_notification_service_routing_logic():
    """Verify staff alert routing logic for various triggers directly."""
    from src.services.notification_service import notification_service

    mock_clinic_data = {
        "id": "clinic-123",
        "name": "Sunrise Health Clinic",
        "owner_email": "owner@sunrisehealth.com",
        "primary_doctor_phone": "+15551234567",
        "notifications_config": {
            "staff_alert_email": "urgent-staff@sunrisehealth.com",
            "staff_alert_phone": "+15559876543",
            "email_staff_alerts_enabled": True,
            "alert_on_negative_sentiment": True,
            "alert_on_missed_calls": True,
            "alert_on_noshow": True,
        }
    }

    # 1. Test Negative Sentiment Trigger
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-123",
            notification_type="call.completed",
            title="Patient Call with Negative Sentiment",
            body="Patient expressed severe dissatisfaction with waiting times",
            metadata={"sentiment": "frustrated"}
        )

        assert routing_res["routed"] is True
        assert routing_res["routed_to_email"] == "urgent-staff@sunrisehealth.com"
        assert routing_res["routed_to_phone"] == "+15559876543"
        assert "Negative Patient Sentiment" in routing_res["reason"]
        mock_email.assert_awaited_once()
        mock_sms.assert_awaited_once()

    # 2. Test Missed Call Trigger
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-123",
            notification_type="call.missed",
            title="Missed Patient Call",
            body="Inbound call from +15550001122 was dropped",
            metadata={"from_number": "+15550001122"}
        )

        assert routing_res["routed"] is True
        assert "Missed / Dropped Patient Call" in routing_res["reason"]
        mock_email.assert_awaited_once()
        mock_sms.assert_awaited_once()

    # 3. Test Patient No-Show Trigger
    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_clinic_data

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-123",
            notification_type="noshow.detected",
            title="Patient No-Show",
            body="Patient Alex Smith missed scheduled visit",
            metadata={"patient_id": "p-1"}
        )

        assert routing_res["routed"] is True
        assert "Patient No-Show Detected" in routing_res["reason"]
        mock_email.assert_awaited_once()
        mock_sms.assert_awaited_once()

    # 4. Test Disabled Alert Preference (Should Not Alert)
    disabled_config = dict(mock_clinic_data)
    disabled_config["notifications_config"] = {
        **mock_clinic_data["notifications_config"],
        "alert_on_missed_calls": False,
    }

    with patch("src.services.notification_service.supabase") as mock_sup, \
         patch("src.services.email_service.email_service.send_staff_urgent_alert", new_callable=AsyncMock) as mock_email, \
         patch("src.services.sms_service.sms_service.send", new_callable=AsyncMock) as mock_sms:
        
        mock_sup.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = disabled_config

        routing_res = await notification_service._check_staff_alert_routing(
            clinic_id="clinic-123",
            notification_type="call.missed",
            title="Missed Call",
            body="Dropped call",
            metadata={}
        )

        assert routing_res["routed"] is False
        mock_email.assert_not_called()
        mock_sms.assert_not_called()
