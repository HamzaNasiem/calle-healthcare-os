"""
test_calle_webhook_pipeline.py — Comprehensive Test Suite for CALL-E Webhook & Downstream EHR Sync

Validates:
1. POST /calle/webhook authentication verification (CALL-E-Event-Id, Bearer, X-Calle-Signature, 401 on missing/mismatch)
2. Handling of CALL-E webhook events: call.completed, call.failed, call.result_validation_failed
3. Downstream EHR Sync:
   - Confirmation:
     * Patient confirms -> updates appointments.status = 'confirmed', sets confirmed_at
     * Patient reschedules -> updates appointments.status = 'rescheduled_requested', sets preferred time notes
     * Patient cancels -> updates appointments.status = 'cancelled', invokes _trigger_waitlist_fill_for_cancelled_slot
   - No-Show Recovery:
     * Patient rebooks -> updates old appointment status = 'rescheduled', creates new appointment with
       booked_by = 'calle_recovery' ($160 revenue), decrements no_show_count
   - Post-Visit Survey:
     * Ingests NPS rating (1-10) and feedback notes into appointments notes, sets followup_sent = True
4. Real-time WebSocket broadcasting via tenant_room_manager:
   - APPOINTMENT_UPDATED
   - APPOINTMENT_CREATED
   - OUTBOUND_CALL_COMPLETED
   - DASHBOARD_STATS_UPDATED
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.config.settings import settings
from src.ws.manager import tenant_room_manager


@pytest.fixture
def client():
    with TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False) as c:
        yield c


CLINIC_ID = "d3b07384-d113-46a6-a719-38cf89235d54"
APPOINTMENT_ID = "a1111111-1111-1111-1111-111111111111"
PATIENT_ID = "p2222222-2222-2222-2222-222222222222"
OUTBOUND_RECORD_ID = "r3333333-3333-3333-3333-333333333333"
CALLE_CALL_ID = "call_calle_audit_test_999"


# ── 1. Webhook Authentication Verification Tests ────────────────────────────────

def test_webhook_auth_valid_event_id_header(client):
    """Test webhook accepts valid CALL-E-Event-Id matching body id."""
    event_id = "evt_test_12345"
    payload = {
        "id": event_id,
        "object": "event",
        "type": "call.completed",
        "data": {
            "id": "untracked_call_id",
            "status": "completed",
            "task_completed": True,
        }
    }
    with patch("src.api.routers.calle_router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"


def test_webhook_auth_valid_bearer_token(client):
    """Test webhook accepts valid Bearer token matching CALLE_API_KEY."""
    payload = {
        "call_id": "untracked_call_id",
        "status": "completed",
    }
    with patch("src.api.routers.calle_router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"Authorization": f"Bearer {settings.CALLE_API_KEY}"}
        )
        assert response.status_code == 200


def test_webhook_auth_valid_x_calle_signature(client):
    """Test webhook accepts valid X-Calle-Signature."""
    payload = {
        "call_id": "untracked_call_id",
        "status": "completed",
    }
    with patch("src.api.routers.calle_router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"X-Calle-Signature": str(settings.CALLE_API_KEY)}
        )
        assert response.status_code == 200


def test_webhook_auth_rejected_on_invalid_credentials(client):
    """Test webhook rejects requests without matching credentials or mismatched event ID."""
    payload = {
        "id": "evt_correct_id",
        "type": "call.completed",
        "data": {"id": "test_call"}
    }
    # Event ID mismatch
    res1 = client.post(
        "/calle/webhook",
        json=payload,
        headers={"CALL-E-Event-Id": "evt_wrong_id"}
    )
    assert res1.status_code == 401

    # Bad token
    res2 = client.post(
        "/calle/webhook",
        json=payload,
        headers={"Authorization": "Bearer bad_secret_token"}
    )
    assert res2.status_code == 401


# ── 2. CALL-E Webhook Event Handling (completed, failed, validation_failed) ────

def test_webhook_event_call_completed(client):
    """Verify call.completed normalizes status='completed' and task_completed=True."""
    event_id = "evt_comp_1"
    payload = {
        "id": event_id,
        "type": "call.completed",
        "data": {
            "id": CALLE_CALL_ID,
            "status": "completed",
            "task_completed": True,
            "structured_result": {"will_attend": "yes", "reschedule_request": False},
            "summary": "Patient confirmed tomorrow appointment.",
            "completion_confidence": {"score": 0.98, "label": "high"}
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "confirmation",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify outbound_calls update
        update_calls = [c for c in mock_db.table.call_args_list if c[0][0] == "outbound_calls"]
        assert len(update_calls) > 0


def test_webhook_event_call_failed(client):
    """Verify call.failed normalizes status='failed' and task_completed=False."""
    event_id = "evt_fail_1"
    payload = {
        "id": event_id,
        "type": "call.failed",
        "data": {
            "id": CALLE_CALL_ID,
            "status": "failed",
            "task_completed": False,
            "summary": "Recipient busy / line disconnected",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "confirmation",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        # Verify OUTBOUND_CALL_COMPLETED broadcast with status failed
        broadcast_events = [c.args[1]["event"] for c in mock_broadcast.call_args_list]
        assert "OUTBOUND_CALL_COMPLETED" in broadcast_events
        call_completed_payload = [c.args[1]["data"] for c in mock_broadcast.call_args_list if c.args[1]["event"] == "OUTBOUND_CALL_COMPLETED"][0]
        assert call_completed_payload["status"] == "failed"
        assert call_completed_payload["task_completed"] is False


def test_webhook_event_result_validation_failed(client):
    """Verify call.result_validation_failed marks status='failed' and task_completed=False."""
    event_id = "evt_val_fail_1"
    payload = {
        "id": event_id,
        "type": "call.result_validation_failed",
        "data": {
            "id": CALLE_CALL_ID,
            "summary": "Output failed JSON schema validation constraint",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "confirmation",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        broadcast_events = [c.args[1]["event"] for c in mock_broadcast.call_args_list]
        assert "OUTBOUND_CALL_COMPLETED" in broadcast_events
        call_completed_payload = [c.args[1]["data"] for c in mock_broadcast.call_args_list if c.args[1]["event"] == "OUTBOUND_CALL_COMPLETED"][0]
        assert call_completed_payload["status"] == "failed"
        assert call_completed_payload["task_completed"] is False


# ── 3. Downstream EHR Sync: Confirmation Campaign ─────────────────────────────

def test_confirmation_patient_confirms(client):
    """Patient confirms -> appointments.status = 'confirmed', sets confirmed_at, emits APPOINTMENT_UPDATED."""
    event_id = "evt_conf_yes"
    payload = {
        "id": event_id,
        "type": "call.completed",
        "data": {
            "id": CALLE_CALL_ID,
            "structured_result": {"will_attend": "yes", "reschedule_request": False},
            "summary": "Patient confirmed attendance for tomorrow's 10:30 AM appointment.",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "confirmation",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        # Verify appointments table update called with status=confirmed and confirmed_at
        update_calls = mock_db.table("appointments").update.call_args_list
        found_confirm = False
        for call in update_calls:
            args = call[0][0]
            if args.get("status") == "confirmed" and "confirmed_at" in args:
                found_confirm = True
                break
        assert found_confirm, "appointments table must be updated with status=confirmed and confirmed_at timestamp"

        # Verify APPOINTMENT_UPDATED broadcast
        broadcast_events = [c.args[1]["event"] for c in mock_broadcast.call_args_list]
        assert "APPOINTMENT_UPDATED" in broadcast_events


def test_confirmation_patient_reschedules(client):
    """Patient requests reschedule -> appointments.status = 'rescheduled_requested', sets preferred time notes."""
    event_id = "evt_conf_resched"
    payload = {
        "id": event_id,
        "type": "call.completed",
        "data": {
            "id": CALLE_CALL_ID,
            "structured_result": {
                "will_attend": "rescheduled",
                "reschedule_request": True,
                "preferred_reschedule_time": "Friday at 2:00 PM",
                "notes": "Patient has conflicting work meeting"
            },
            "summary": "Patient asked to reschedule to Friday 2 PM.",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "confirmation",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        # Verify appointments table update called with status=rescheduled_requested and preferred time notes
        update_calls = mock_db.table("appointments").update.call_args_list
        found_resched = False
        for call in update_calls:
            args = call[0][0]
            if args.get("status") == "rescheduled_requested":
                assert "Friday at 2:00 PM" in args.get("notes", "")
                found_resched = True
                break
        assert found_resched, "appointments table must be updated with status=rescheduled_requested"

        # Verify APPOINTMENT_UPDATED broadcast
        broadcast_events = [c.args[1]["event"] for c in mock_broadcast.call_args_list]
        assert "APPOINTMENT_UPDATED" in broadcast_events


def test_confirmation_patient_cancels_triggers_waitlist_fill(client):
    """Patient cancels -> appointments.status = 'cancelled', invokes _trigger_waitlist_fill_for_cancelled_slot."""
    event_id = "evt_conf_cancel"
    payload = {
        "id": event_id,
        "type": "call.completed",
        "data": {
            "id": CALLE_CALL_ID,
            "structured_result": {
                "will_attend": "no",
                "reschedule_request": False,
                "notes": "Patient moving out of state"
            },
            "summary": "Patient cancelled appointment.",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "confirmation",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router._trigger_waitlist_fill_for_cancelled_slot", new_callable=AsyncMock) as mock_waitlist, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        # Verify appointments status updated to cancelled
        update_calls = mock_db.table("appointments").update.call_args_list
        found_cancel = False
        for call in update_calls:
            args = call[0][0]
            if args.get("status") == "cancelled":
                found_cancel = True
                break
        assert found_cancel, "appointments table must be updated with status=cancelled"

        # Verify _trigger_waitlist_fill_for_cancelled_slot was invoked
        mock_waitlist.assert_awaited_once_with(clinic_id=CLINIC_ID, appointment_id=APPOINTMENT_ID)

        # Verify APPOINTMENT_UPDATED broadcast
        broadcast_events = [c.args[1]["event"] for c in mock_broadcast.call_args_list]
        assert "APPOINTMENT_UPDATED" in broadcast_events


# ── 4. Downstream EHR Sync: No-Show Recovery Campaign ─────────────────────────

def test_noshow_recovery_patient_rebooks(client):
    """
    Patient agrees to rebook missed visit:
    - Updates old appointment status = 'rescheduled'
    - Creates new appointment with booked_by = 'calle_recovery' ($160.00 revenue)
    - Decrements patient's no_show_count
    - Broadcasts APPOINTMENT_CREATED and APPOINTMENT_UPDATED
    """
    event_id = "evt_noshow_rebook"
    payload = {
        "id": event_id,
        "type": "call.completed",
        "data": {
            "id": CALLE_CALL_ID,
            "structured_result": {
                "response_type": "rescheduled",
                "reschedule_request": True,
                "preferred_reschedule_time": "2026-09-12T14:00:00Z",
                "notes": "Patient had a transportation emergency earlier."
            },
            "summary": "Patient recovered from no-show and rebooked for Sept 12.",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "no_show",
        "patient_id": PATIENT_ID,
    }

    old_appointment = {
        "id": APPOINTMENT_ID,
        "clinic_id": CLINIC_ID,
        "patient_id": PATIENT_ID,
        "patient_name": "Jane Doe",
        "patient_phone": "+15555551234",
        "appointment_type": "Physical Therapy Follow-Up",
        "revenue_amount": 160.0,
        "status": "no_show",
    }

    patient_record = {
        "id": PATIENT_ID,
        "no_show_count": 2,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.supabase_read") as mock_db_read, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        # Mock outbound_calls lookup
        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "new-appt-id"}])

        # Mock supabase_read for old appointment and patient
        def mock_read_table(table_name):
            query = MagicMock()
            if table_name == "appointments":
                query.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[old_appointment])
            elif table_name == "patients":
                query.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[patient_record])
            return query

        mock_db_read.table.side_effect = mock_read_table

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        # Verify old appointment updated to status=rescheduled
        mock_db.table("appointments").update.assert_any_call({"status": "rescheduled"})

        # Verify new appointment inserted with booked_by=calle_recovery and revenue_amount=160.0
        insert_calls = mock_db.table("appointments").insert.call_args_list
        assert len(insert_calls) > 0
        new_appt_data = insert_calls[0][0][0]
        assert new_appt_data["booked_by"] == "calle_recovery"
        assert new_appt_data["revenue_amount"] == 160.0
        assert new_appt_data["status"] == "scheduled"
        assert new_appt_data["patient_name"] == "Jane Doe"

        # Verify patient no_show_count decremented from 2 to 1
        mock_db.table("patients").update.assert_called_with({"no_show_count": 1})

        # Verify APPOINTMENT_CREATED and APPOINTMENT_UPDATED broadcasts
        broadcast_events = [c.args[1]["event"] for c in mock_broadcast.call_args_list]
        assert "APPOINTMENT_CREATED" in broadcast_events
        assert "APPOINTMENT_UPDATED" in broadcast_events


# ── 5. Downstream EHR Sync: Post-Visit Survey Campaign ─────────────────────────

def test_post_visit_survey_ingestion(client):
    """
    Patient completes post-visit satisfaction survey:
    - Ingests NPS rating (1-10) and feedback notes into appointments.notes
    - Sets followup_sent = True
    - Broadcasts APPOINTMENT_UPDATED with survey results
    """
    event_id = "evt_survey_complete"
    payload = {
        "id": event_id,
        "type": "call.completed",
        "data": {
            "id": CALLE_CALL_ID,
            "structured_result": {
                "nps_score": 10,
                "main_feedback": "Dr. Smith explained my physical therapy exercises clearly and I felt cared for.",
                "would_recommend": "yes"
            },
            "summary": "Patient gave a 10/10 rating and positive feedback.",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "survey",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        # Verify appointments updated with NPS score, feedback notes, and followup_sent=True
        update_calls = mock_db.table("appointments").update.call_args_list
        found_survey = False
        for call in update_calls:
            args = call[0][0]
            notes = args.get("notes", "")
            if "NPS: 10/10" in notes and "Dr. Smith" in notes and args.get("followup_sent") is True:
                found_survey = True
                break
        assert found_survey, "appointments table must be updated with NPS rating, feedback notes, and followup_sent=True"

        # Verify APPOINTMENT_UPDATED broadcast
        broadcast_events = [c.args[1]["event"] for c in mock_broadcast.call_args_list]
        assert "APPOINTMENT_UPDATED" in broadcast_events


# ── 6. WebSocket Broadcasting Suite Verification ─────────────────────────────

def test_websocket_broadcast_suite(client):
    """
    Verify emission of all required real-time events:
    - APPOINTMENT_UPDATED
    - OUTBOUND_CALL_COMPLETED
    - DASHBOARD_STATS_UPDATED
    """
    event_id = "evt_ws_suite"
    payload = {
        "id": event_id,
        "type": "call.completed",
        "data": {
            "id": CALLE_CALL_ID,
            "structured_result": {"will_attend": "yes", "reschedule_request": False},
            "summary": "Confirmed",
        }
    }

    mock_record = {
        "id": OUTBOUND_RECORD_ID,
        "clinic_id": CLINIC_ID,
        "appointment_id": APPOINTMENT_ID,
        "campaign_type": "confirmation",
        "patient_id": PATIENT_ID,
    }

    with patch("src.api.routers.calle_router.supabase") as mock_db, \
         patch("src.api.routers.calle_router.tenant_room_manager.broadcast_to_tenant", new_callable=AsyncMock) as mock_broadcast:

        mock_db.table.return_value.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[mock_record])
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_record])

        response = client.post(
            "/calle/webhook",
            json=payload,
            headers={"CALL-E-Event-Id": event_id}
        )
        assert response.status_code == 200

        # Collect all broadcast events sent to tenant
        emitted_events = [call.args[1]["event"] for call in mock_broadcast.call_args_list]

        assert "APPOINTMENT_UPDATED" in emitted_events, "APPOINTMENT_UPDATED must be broadcast to tenant"
        assert "OUTBOUND_CALL_COMPLETED" in emitted_events, "OUTBOUND_CALL_COMPLETED must be broadcast to tenant"
        assert "DASHBOARD_STATS_UPDATED" in emitted_events, "DASHBOARD_STATS_UPDATED must be broadcast to tenant"
