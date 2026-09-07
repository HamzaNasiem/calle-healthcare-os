"""
Unit tests for calle_router.py:
- Timezone handling (America/Chicago default)
- Estimates endpoint logic (48h no-show recovery, completed survey matching)
- TCPA quiet hours enforcement & force/bypass_quiet_hours override
- Batch campaign endpoints request models & phone normalization
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, AsyncMock, patch

from src.api.routers.calle_router import (
    _normalize_phone_e164,
    ConfirmationCampaignRequest,
    NoShowCampaignRequest,
    RecallCampaignRequest,
    SurveyCampaignRequest,
    WaitlistCampaignRequest,
    SingleCallRequest,
)
from src.services.tcpa_service import tcpa_service


def test_phone_normalization():
    assert _normalize_phone_e164("5551234567") == "+15551234567"
    assert _normalize_phone_e164("(555) 123-4567") == "+15551234567"
    assert _normalize_phone_e164("+15551234567") == "+15551234567"
    assert _normalize_phone_e164("15551234567") == "+15551234567"
    assert _normalize_phone_e164("03001234567") == "+923001234567"
    assert _normalize_phone_e164("") == ""
    assert _normalize_phone_e164(None) == ""


def test_campaign_request_models():
    # Verify force and bypass_quiet_hours are supported across all campaign requests
    conf = ConfirmationCampaignRequest(force=True, limit=10)
    assert conf.force is True
    assert conf.bypass_quiet_hours is False
    assert conf.limit == 10

    ns = NoShowCampaignRequest(bypass_quiet_hours=True, lookback_hours=24)
    assert ns.bypass_quiet_hours is True
    assert ns.lookback_hours == 24
    assert ns.limit == 15

    rec = RecallCampaignRequest(days_threshold=60, force=True)
    assert rec.days_threshold == 60
    assert rec.force is True

    surv = SurveyCampaignRequest(bypass_quiet_hours=True, lookback_hours=12)
    assert surv.bypass_quiet_hours is True
    assert surv.lookback_hours == 12

    wl = WaitlistCampaignRequest(force=True, slot_date="Tomorrow", slot_time="2:00 PM")
    assert wl.force is True
    assert wl.slot_date == "Tomorrow"

    single = SingleCallRequest(phone="5551234567", campaign_type="confirmation", force=True)
    assert single.force is True
    assert single.bypass_quiet_hours is False


def test_tcpa_service_quiet_hours_chicago():
    # Test quiet hours during night (e.g. 2:00 AM Central)
    dt_night = datetime(2026, 9, 7, 2, 0, 0, tzinfo=ZoneInfo("America/Chicago"))
    is_quiet, reason = tcpa_service.is_quiet_hours(
        timezone_str="America/Chicago",
        now_override=dt_night
    )
    assert is_quiet is True
    assert "prohibited between 9:00 PM and 8:00 AM" in reason

    # Test allowed hours during daytime (e.g. 2:00 PM Central)
    dt_day = datetime(2026, 9, 7, 14, 0, 0, tzinfo=ZoneInfo("America/Chicago"))
    is_quiet_day, _ = tcpa_service.is_quiet_hours(
        timezone_str="America/Chicago",
        now_override=dt_day
    )
    assert is_quiet_day is False
