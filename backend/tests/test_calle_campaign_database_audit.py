"""
test_calle_campaign_database_audit.py
Full database verification tests for CALL-E Campaign Endpoints for clinic d3b07384-d113-46a6-a719-38cf89235d54.
Verifies:
1. Zero mock data - authentic PostgreSQL queries on appointments, patients, waitlist
2. Date and timezone boundaries using America/Chicago local time with UTC bounds
3. Authentic queue counts:
   - Tomorrow's confirmations: 3
   - Today's no-shows: 2
   - Today's surveys: 2
   - Overdue recalls: 6 (30d) / 4 (60d) / 2 (90d)
   - Active waitlists: 3
4. TCPA quiet hours enforcement and force / bypass_quiet_hours override
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import BackgroundTasks

from src.core.security import AuthenticatedUser
from src.core.database import LocalPostgresClient
import src.core.database
import src.api.routers.calle_router

from src.api.routers.calle_router import (
    get_campaign_estimates,
    run_confirmation_campaign,
    run_no_show_campaign,
    run_recall_campaign,
    run_survey_campaign,
    run_waitlist_campaign,
    trigger_single_call,
    ConfirmationCampaignRequest,
    NoShowCampaignRequest,
    RecallCampaignRequest,
    SurveyCampaignRequest,
    WaitlistCampaignRequest,
    SingleCallRequest,
)

from unittest.mock import AsyncMock, patch
from src.services.calle_service import calle_service

CLINIC_ID = "d3b07384-d113-46a6-a719-38cf89235d54"

@pytest.fixture(autouse=True)
def real_postgres_db():
    """Ensure tests run against real PostgreSQL database, overriding conftest mocks."""
    real_client = LocalPostgresClient()
    src.core.database.supabase = real_client
    src.core.database.supabase_read = real_client
    src.api.routers.calle_router.supabase = real_client
    src.api.routers.calle_router.supabase_read = real_client
    
    # Mock live outbound voice API calls so the 24h plan limit does not fail unit tests,
    # while preserving 100% authentic database queries and counts.
    dummy_call_res = {
        "id": "mock_calle_call_123",
        "status": "completed",
        "task_completed": True,
        "structured_result": {"will_attend": "yes"},
        "summary": "Automated call completed.",
        "completion_confidence": {"score": 0.95, "label": "high"}
    }
    with patch.object(calle_service, "confirmation_call", new=AsyncMock(return_value=dummy_call_res)), \
         patch.object(calle_service, "no_show_recovery_call", new=AsyncMock(return_value=dummy_call_res)), \
         patch.object(calle_service, "recall_call", new=AsyncMock(return_value=dummy_call_res)), \
         patch.object(calle_service, "post_visit_survey_call", new=AsyncMock(return_value=dummy_call_res)), \
         patch.object(calle_service, "waitlist_fill_call", new=AsyncMock(return_value=dummy_call_res)), \
         patch.object(calle_service, "create_call", new=AsyncMock(return_value=dummy_call_res)):
        yield

@pytest.fixture
def auth_user():
    return AuthenticatedUser(
        user_id="e64098bc-e74f-4d3f-b889-aaef14eaef14",
        clinic_id=CLINIC_ID,
        clinic_name="Oakridge Physical Therapy & Wellness",
        email="auditor@bytelytic.com",
        role="owner",
    )


@pytest.mark.asyncio
async def test_get_campaign_estimates_authentic_counts(auth_user):
    """Verify estimates endpoint calculates authentic counts using America/Chicago timezone and UTC bounds."""
    res = await get_campaign_estimates(auth=auth_user)
    assert "counts" in res
    counts = res["counts"]
    
    # Verify exact authentic queue counts
    assert counts["confirmation"] == 3, f"Expected 3 tomorrow confirmations, got {counts['confirmation']}"
    assert counts["no_show"] == 2, f"Expected 2 today's no-shows, got {counts['no_show']}"
    assert counts["recall_30"] == 6, f"Expected 6 30-day recalls, got {counts['recall_30']}"
    assert counts["recall_60"] == 4, f"Expected 4 60-day recalls, got {counts['recall_60']}"
    assert counts["recall_90"] == 2, f"Expected 2 90-day recalls, got {counts['recall_90']}"
    assert counts["survey"] == 2, f"Expected 2 today's surveys, got {counts['survey']}"
    assert counts["waitlist"] == 3, f"Expected 3 active waitlist entries, got {counts['waitlist']}"
    
    assert res["total_queued"] == 16
    assert res["cost_per_call"] == 0.07
    assert res["estimated_total_cost"] == 1.12
    assert "campaigns" in res
    assert res["campaigns"]["confirmation"]["queue_count"] == 3
    assert res["campaigns"]["no_show"]["queue_count"] == 2
    assert res["campaigns"]["recall"]["queue_count"] == 6
    assert res["campaigns"]["survey"]["queue_count"] == 2
    assert res["campaigns"]["waitlist"]["queue_count"] == 3


@pytest.mark.asyncio
async def test_confirmation_campaign_query_and_bypass(auth_user):
    """Test confirmation campaign dispatches tomorrow's 3 scheduled visits with bypass_quiet_hours."""
    bg = BackgroundTasks()
    res = await run_confirmation_campaign(
        body=ConfirmationCampaignRequest(bypass_quiet_hours=True),
        background_tasks=bg,
        auth=auth_user
    )
    assert res["queued"] == 3
    assert "Confirmation campaign started" in res["message"]
    assert len(bg.tasks) == 1


@pytest.mark.asyncio
async def test_noshow_campaign_query_and_force(auth_user):
    """Test no-show campaign dispatches today's 2 missed visits with force override."""
    bg = BackgroundTasks()
    res = await run_no_show_campaign(
        body=NoShowCampaignRequest(force=True, lookback_hours=48),
        background_tasks=bg,
        auth=auth_user
    )
    assert res["queued"] == 2
    assert "No-show recovery campaign started" in res["message"]
    assert len(bg.tasks) == 1


@pytest.mark.asyncio
async def test_recall_campaign_query_and_bypass(auth_user):
    """Test recall campaign dispatches overdue patients with bypass_quiet_hours."""
    bg = BackgroundTasks()
    res = await run_recall_campaign(
        body=RecallCampaignRequest(bypass_quiet_hours=True, days_threshold=30, limit=10),
        background_tasks=bg,
        auth=auth_user
    )
    assert res["queued"] == 6
    assert "Recall campaign started" in res["message"]
    assert len(bg.tasks) == 1


@pytest.mark.asyncio
async def test_survey_campaign_query_and_force(auth_user):
    """Test survey campaign dispatches today's 2 completed visits with force override."""
    bg = BackgroundTasks()
    res = await run_survey_campaign(
        body=SurveyCampaignRequest(force=True),
        background_tasks=bg,
        auth=auth_user
    )
    assert res["queued"] == 2
    assert "Survey campaign started" in res["message"]
    assert len(bg.tasks) == 1


@pytest.mark.asyncio
async def test_waitlist_campaign_query_and_bypass(auth_user):
    """Test waitlist campaign dispatches 3 active waitlist entries with bypass_quiet_hours."""
    bg = BackgroundTasks()
    res = await run_waitlist_campaign(
        body=WaitlistCampaignRequest(bypass_quiet_hours=True, limit=10),
        background_tasks=bg,
        auth=auth_user
    )
    assert res["queued"] == 3
    assert "Waitlist backfill campaign started" in res["message"]
    assert len(bg.tasks) == 1


@pytest.mark.asyncio
async def test_single_call_tcpa_and_bypass(auth_user):
    """Verify trigger_single_call respects TCPA quiet hours and allows bypass_quiet_hours."""
    from src.services.tcpa_service import tcpa_service
    # If quiet hours active, without force/bypass it should hold
    bg = BackgroundTasks()
    existing_appt_id = "84fb9220-b6db-42bb-8be8-13384d924537"
    req_held = SingleCallRequest(
        phone="+14155552671",
        campaign_type="confirmation",
        appointment_id=existing_appt_id,
        force=False,
        bypass_quiet_hours=False
    )
    res_held = await trigger_single_call(body=req_held, background_tasks=bg, auth=auth_user)
    # If daytime, status is running or initiated; if nighttime, quiet_hours_active is True
    is_quiet, _ = tcpa_service.is_quiet_hours("America/Chicago")
    if is_quiet:
        assert res_held.get("quiet_hours_active") is True
        assert res_held.get("can_override") is True
    else:
        assert res_held.get("status") in ("queued", "running", "initiated", "completed")

    # With bypass_quiet_hours=True, call proceeds to CALL-E API
    req_bypass = SingleCallRequest(
        phone="+14155552671",
        campaign_type="confirmation",
        appointment_id=existing_appt_id,
        bypass_quiet_hours=True
    )
    res_bypass = await trigger_single_call(body=req_bypass, background_tasks=bg, auth=auth_user)
    assert res_bypass.get("status") in ("queued", "running", "initiated", "completed")
    assert "record_id" in res_bypass
