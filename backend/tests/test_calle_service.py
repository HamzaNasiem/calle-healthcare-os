import pytest
import uuid
from unittest.mock import MagicMock, patch

from src.services.calle_service import CalleService, calle_service

@pytest.fixture
def service():
    srv = CalleService()
    # Force dry run to avoid real API calls if key exists
    srv._is_dry_run = MagicMock(return_value=False)
    srv.client = MagicMock()
    return srv

def test_confirmation_call_dry_run():
    srv = CalleService()
    srv._is_dry_run = MagicMock(return_value=True)
    res = srv.place_confirmation_call("+15551234567", "Test Clinic", "10:00 AM", "key1")
    assert res["status"] == "completed"
    assert res["structured_result"]["will_attend"] == "yes"

def test_no_show_recovery_call_dry_run():
    srv = CalleService()
    srv._is_dry_run = MagicMock(return_value=True)
    res = srv.place_no_show_recovery_call("+15551234567", "Test Clinic", "10:00 AM", "key2")
    assert res["status"] == "completed"
    assert res["structured_result"]["response_type"] == "rescheduled"

def test_waitlist_fill_call_dry_run():
    srv = CalleService()
    srv._is_dry_run = MagicMock(return_value=True)
    res = srv.place_waitlist_fill_call("+15551234567", "Test Clinic", "2023-10-10", "10:00 AM", "key3")
    assert res["status"] == "completed"
    assert res["structured_result"]["accepts_slot"] is True

def test_pre_appointment_call_dry_run():
    srv = CalleService()
    srv._is_dry_run = MagicMock(return_value=True)
    res = srv.place_pre_appointment_call("+15551234567", "Test Clinic", "10:00 AM", "key4")
    assert res["status"] == "completed"
    assert res["structured_result"]["acknowledged"] is True

def test_confirmation_call_live(service):
    service.client.calls.create_and_wait.return_value = {"status": "completed", "structured_result": {"will_attend": "no"}}
    res = service.place_confirmation_call("+15551234567", "Test Clinic", "10:00 AM", "key1")
    assert res["status"] == "completed"
    service.client.calls.create_and_wait.assert_called_once()
    args, kwargs = service.client.calls.create_and_wait.call_args
    assert "will_attend" in kwargs["result_schema"]["properties"]

def test_no_show_recovery_call_live(service):
    service.client.calls.create_and_wait.return_value = {"status": "completed", "structured_result": {"response_type": "emergency"}}
    res = service.place_no_show_recovery_call("+15551234567", "Test Clinic", "10:00 AM", "key2")
    assert res["status"] == "completed"
    service.client.calls.create_and_wait.assert_called_once()

def test_waitlist_fill_call_live(service):
    service.client.calls.create_and_wait.return_value = {"status": "completed", "structured_result": {"accepts_slot": False}}
    res = service.place_waitlist_fill_call("+15551234567", "Test Clinic", "2023-10-10", "10:00 AM", "key3")
    assert res["status"] == "completed"
    service.client.calls.create_and_wait.assert_called_once()

def test_pre_appointment_call_live(service):
    service.client.calls.create_and_wait.return_value = {"status": "completed", "structured_result": {"acknowledged": False}}
    res = service.place_pre_appointment_call("+15551234567", "Test Clinic", "10:00 AM", "key4")
    assert res["status"] == "completed"
    service.client.calls.create_and_wait.assert_called_once()

def test_api_failure_handled(service):
    service.client.calls.create_and_wait.side_effect = Exception("API Timeout")
    res = service.place_confirmation_call("+15551234567", "Test Clinic", "10:00 AM", "key1")
    assert res["status"] == "failed"
    assert res["task_completed"] is False
    assert "API error" in res["summary"]
    assert res["evidence"]["error"] == "API Timeout"

@pytest.mark.asyncio
async def test_awaitable_dict_compat_async(service):
    """Verify place_* helpers can be cleanly awaited without TypeError."""
    service.client.calls.create_and_wait.return_value = {
        "id": "call_123",
        "status": "completed",
        "task_completed": True,
        "structured_result": {"will_attend": "yes", "reschedule_request": False}
    }
    # Direct await on place_confirmation_call must NOT raise TypeError: object dict can't be used in 'await' expression
    res = await service.place_confirmation_call("+15551234567", "Test Clinic", "10:00 AM", "key_async")
    assert res["status"] == "completed"
    assert res["structured_result"]["will_attend"] == "yes"
    assert isinstance(res, dict)

@pytest.mark.asyncio
async def test_confirmation_call_fire_and_forget_subsecond(service):
    """Verify sub-second fire-and-forget uses calls.create without blocking."""
    service.client.calls.create.return_value = {
        "id": "call_subsecond_abc",
        "status": "queued",
        "structured_result": None
    }
    res = await service.confirmation_call(
        phone="+15551234567",
        clinic_name="Test Clinic",
        time_str="10:00 AM",
        idempotency_key="key_fast",
        wait_for_completion=False
    )
    assert res["status"] == "queued"
    assert res["id"] == "call_subsecond_abc"
    service.client.calls.create.assert_called_once()

@pytest.mark.asyncio
async def test_list_goals_live_no_mock_fallback(service):
    """Verify live mode returns real API data without forcing mock fallback when data is empty."""
    service.client.goals.list.return_value = {"object": "list", "data": [], "next_cursor": None}
    res = await service.list_goals()
    assert res["object"] == "list"
    assert res["data"] == []  # Real empty list, not mock data!

def test_phone_normalization_e164():
    from src.services.calle_service import _normalize_phone_e164
    assert _normalize_phone_e164("(555) 123-4567") == "+15551234567"
    assert _normalize_phone_e164("5551234567") == "+15551234567"
    assert _normalize_phone_e164("+15551234567") == "+15551234567"
    assert _normalize_phone_e164("03001234567") == "+923001234567"
    assert _normalize_phone_e164("923001234567") == "+923001234567"
    assert _normalize_phone_e164("+447911123456") == "+447911123456"

def test_region_and_locale_detection():
    srv = CalleService()
    reg, _ = srv._detect_region_and_locale("+923001234567")
    assert reg == "PK"
    reg_us, _ = srv._detect_region_and_locale("+14155552671")
    assert reg_us == "US"
    reg_gb, _ = srv._detect_region_and_locale("+447911123456")
    assert reg_gb == "GB"
    reg_ovr, _ = srv._detect_region_and_locale("+14155552671", region_override="PK")
    assert reg_ovr == "PK"

def test_phi_scrubber_filter():
    import logging
    from src.services.calle_service import PHIScrubberFilter
    filt = PHIScrubberFilter()
    rec = logging.LogRecord("phi_test", logging.INFO, "test.py", 1, "Calling patient at +14155552671 or +923001234567 email patient@clinic.com", (), None)
    filt.filter(rec)
    assert "+14155552671" not in rec.msg
    assert "+923001234567" not in rec.msg
    assert "patient@clinic.com" not in rec.msg
    assert "[PHI_REDACTED]" in rec.msg

def test_hipaa_task_text_scrubbed():
    srv = CalleService()
    script = srv._build_noshow_script("10:00 AM", "Bytelytic Clinic")
    assert "John Doe" not in script
    assert "Patient" not in script
    assert "CALL-E" in script

@pytest.mark.asyncio
async def test_create_call_fire_and_forget():
    srv = CalleService()
    srv._is_dry_run = MagicMock(return_value=True)
    res = await srv.create_call(
        task="Test prompt",
        phone="+923001234567",
        wait_for_completion=False,
    )
    assert res["status"] == "queued"
    assert res["task_completed"] is False
    assert str(res["id"]).startswith("call_")

@pytest.mark.asyncio
async def test_create_call_wait_for_completion():
    srv = CalleService()
    srv._is_dry_run = MagicMock(return_value=True)
    res = await srv.create_call(
        task="Test prompt",
        phone="+923001234567",
        wait_for_completion=True,
    )
    assert res["status"] == "completed"
    assert res["task_completed"] is True
    assert str(res["id"]).startswith("call_")
    assert "structured_result" in res

def test_live_sdk_call_payload_format(service):
    from src.services.calle_service import CONFIRMATION_SCHEMA
    service.client.calls.create.return_value = {"id": "call_live_789", "status": "queued"}
    res = service._sync_create_fire_and_forget(
        task="Verify attendance.",
        phone="+923001234567",
        result_schema=CONFIRMATION_SCHEMA,
        idempotency_key="key_live_format",
        region="PK"
    )
    assert res["status"] == "queued"
    assert res["id"] == "call_live_789"
    service.client.calls.create.assert_called_once()
    _, kwargs = service.client.calls.create.call_args
    assert kwargs["task"] == "Verify attendance."
    assert kwargs["recipients"] == [{"phones": ["+923001234567"], "region": "PK"}]
    assert kwargs["idempotency_key"] == "key_live_format"
    assert kwargs["result_schema"] == CONFIRMATION_SCHEMA

