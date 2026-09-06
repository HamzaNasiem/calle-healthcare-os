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

