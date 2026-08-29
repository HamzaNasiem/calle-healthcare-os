import asyncio
import datetime
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from src.core.cache import LocalCache, RedisOrLocalCache
from src.tools.appointments import (
    BookNewAppointmentTool,
    RescheduleAppointmentTool,
    CheckCalendarAvailabilityTool,
    _safe_zone_info,
    _invalidate_date_cache,
    _release_slot_lock
)
from src.models.appointment import Appointment
from src.models.patient import Patient
from src.models.provider import Provider
from src.models.tenant import Tenant
from src.models.tenant_settings import TenantSettings
from src.models.slot_lock import SlotLock


def test_safe_zone_info():
    """Verify timezone fallback resilience for invalid or missing timezone strings."""
    assert _safe_zone_info(None) == ZoneInfo("America/Chicago")
    assert _safe_zone_info("") == ZoneInfo("America/Chicago")
    assert _safe_zone_info("America/New_York") == ZoneInfo("America/New_York")
    assert _safe_zone_info("Invalid/NonExistent_Zone") == ZoneInfo("America/Chicago")


def test_local_cache_get_and_tuple_safety():
    """Verify local cache correctly handles set/get and expiry without tuple subscript errors."""
    cache = LocalCache(default_ttl=10)
    cache.set("lock:test:1", "call_123", ttl=60)
    assert cache.get("lock:test:1") == "call_123"
    assert cache.get("nonexistent") is None
    cache.invalidate("lock:test:1")
    assert cache.get("lock:test:1") is None


def test_timezone_conversion_utc_to_local():
    """Verify exact time calculation from clinic timezone to UTC and back."""
    clinic_tz = ZoneInfo("America/New_York") # UTC-4 (EDT) or UTC-5 (EST)
    local_dt = datetime.datetime(2026, 9, 15, 14, 30, tzinfo=clinic_tz) # 2:30 PM NY
    utc_dt = local_dt.astimezone(datetime.UTC)
    
    assert utc_dt.tzinfo == datetime.UTC
    # In September (EDT), NY is UTC-4, so 14:30 EDT == 18:30 UTC
    assert utc_dt.hour == 18
    assert utc_dt.minute == 30
    
    # Reverse check
    restored_local = utc_dt.astimezone(clinic_tz)
    assert restored_local.hour == 14
    assert restored_local.minute == 30


@pytest.mark.asyncio
async def test_book_new_appointment_redis_lock_rejection():
    """Verify that if a slot is already locked by another call_id in Redis/LocalCache, it rejects the booking."""
    tool = BookNewAppointmentTool()
    tenant_id = str(uuid.uuid4())
    call_id_1 = "call_user_a"
    call_id_2 = "call_user_b"
    slot_id = "slot_prov1_20260915_1430"
    
    from src.core.cache import local_cache
    lock_key = f"lock:slot:{tenant_id}:{slot_id}"
    
    # User A locks the slot
    local_cache.set(lock_key, call_id_1, ttl=120)
    
    db_mock = AsyncMock()
    # User B attempts to book the same slot
    args = {
        "patient_name": "Bob Smith",
        "phone": "+13125550199",
        "dob": "1985-05-12",
        "slot_id": slot_id,
        "reason": "Consultation"
    }
    
    result = await tool.execute(db=db_mock, tenant_id=tenant_id, call_id=call_id_2, args=args)
    assert result["success"] is False
    assert result["reason"] == "slot_no_longer_available"
    assert "was just taken" in result["message"]
    
    # Clean up
    local_cache.invalidate(lock_key)


@pytest.mark.asyncio
async def test_reschedule_appointment_redis_lock_rejection():
    """Verify that reschedule rejects when the new slot is locked by a concurrent call."""
    tool = RescheduleAppointmentTool()
    tenant_id = str(uuid.uuid4())
    call_id_1 = "call_user_a"
    call_id_2 = "call_user_b"
    new_slot_id = "slot_prov1_20260915_1500"
    
    from src.core.cache import local_cache
    lock_key = f"lock:slot:{tenant_id}:{new_slot_id}"
    
    # Another caller has locked this new slot
    local_cache.set(lock_key, call_id_1, ttl=120)
    
    db_mock = AsyncMock()
    
    # Setup mock patient
    mock_patient = MagicMock()
    mock_patient.id = uuid.uuid4()
    mock_patient.is_deleted = False
    from src.core.encryption import phi_crypto
    mock_patient.dob_encrypted = phi_crypto.encrypt("1985-05-12")
    
    # Mock patient lookup result
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [mock_patient]
    scalars_mock.first.return_value = mock_patient
    
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    db_mock.execute.return_value = result_mock
    
    # Mock tenant
    mock_tenant = MagicMock()
    mock_tenant.timezone = "America/Chicago"
    
    # Mock old appointment
    mock_old_apt = MagicMock()
    mock_old_apt.id = uuid.uuid4()
    mock_old_apt.patient_id = mock_patient.id
    mock_old_apt.slot_start = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=3)
    
    def side_effect_execute(stmt, *args, **kwargs):
        res = MagicMock()
        s = MagicMock()
        stmt_str = str(stmt).lower()
        if "tenants" in stmt_str:
            s.first.return_value = mock_tenant
            s.all.return_value = [mock_tenant]
        elif "appointments" in stmt_str:
            s.all.return_value = [mock_old_apt]
            s.first.return_value = mock_old_apt
        else:
            s.all.return_value = [mock_patient]
            s.first.return_value = mock_patient
        res.scalars.return_value = s
        return res
        
    db_mock.execute.side_effect = side_effect_execute
    
    args = {
        "phone": "+13125550199",
        "dob": "1985-05-12",
        "old_appointment_date": "2026-09-10",
        "new_slot_id": new_slot_id
    }
    
    result = await tool.execute(db=db_mock, tenant_id=tenant_id, call_id=call_id_2, args=args)
    assert result["success"] is False
    assert result["reason"] == "slot_no_longer_available"
    
    # Clean up
    local_cache.invalidate(lock_key)
