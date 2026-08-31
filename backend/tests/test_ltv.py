import pytest
from unittest.mock import MagicMock, patch
import asyncio
import datetime
from src.jobs.scheduler import sync_patient_ltv_stats

@pytest.mark.asyncio
async def test_sync_patient_ltv_stats():
    # Mock clinics
    mock_clinics_res = MagicMock()
    mock_clinics_res.data = [
        {"id": "clinic-1", "monthly_revenue_per_visit": 200.0}
    ]

    # Mock appointments
    mock_appts_res = MagicMock()
    mock_appts_res.data = [
        # Patient 1 has 3 completed appointments
        {"patient_id": "patient-1", "status": "completed", "datetime": "2026-06-01T10:00:00Z"},
        {"patient_id": "patient-1", "status": "completed", "datetime": "2026-06-05T10:00:00Z"},
        {"patient_id": "patient-1", "status": "completed", "datetime": "2026-06-09T10:00:00Z"},
        # Patient 2 has 1 completed appointment
        {"patient_id": "patient-2", "status": "completed", "datetime": "2026-06-08T10:00:00Z"},
        # Patient 3 has no completed appointments
        {"patient_id": "patient-3", "status": "scheduled", "datetime": "2026-06-12T10:00:00Z"}
    ]

    # Mock patients
    mock_patients_res = MagicMock()
    mock_patients_res.data = [
        {"id": "patient-1"},
        {"id": "patient-2"},
        {"id": "patient-3"}
    ]

    # Mock updates tracking
    updates = {}
    def mock_update(payload):
        mock_builder = MagicMock()
        def mock_eq(col, val):
            updates[val] = payload
            mock_exec_res = MagicMock()
            mock_exec_res.data = []
            mock_builder.execute.return_value = mock_exec_res
            return mock_builder
        mock_builder.eq.side_effect = mock_eq
        return mock_builder

    # We mock supabase table calls
    with patch("src.jobs.scheduler.supabase") as mock_supabase:
        def table_selector(table_name):
            mock_table = MagicMock()
            if table_name == "clinics":
                mock_select = MagicMock()
                mock_select.execute.return_value = mock_clinics_res
                mock_table.select.return_value = mock_select
            elif table_name == "appointments":
                mock_select = MagicMock()
                mock_select.eq.return_value.execute.return_value = mock_appts_res
                mock_table.select.return_value = mock_select
            elif table_name == "patients":
                mock_select = MagicMock()
                mock_select.eq.return_value.execute.return_value = mock_patients_res
                mock_table.select.return_value = mock_select
                mock_table.update.side_effect = mock_update
            return mock_table

        mock_supabase.table.side_effect = table_selector

        # Run the sync function
        await sync_patient_ltv_stats()

        # Check results
        assert "patient-1" in updates
        assert "patient-2" in updates
        assert "patient-3" in updates

        # Patient 1: 3 completed appointments, LTV = 3 * 200 = 600
        p1_data = updates["patient-1"]
        assert p1_data["total_revenue_generated"] == 600.0
        assert p1_data["average_visit_value"] == 200.0
        # consecutive diffs in days: Jun 5 - Jun 1 = 4 days; Jun 9 - Jun 5 = 4 days. Avg = 4
        assert p1_data["visit_frequency_days"] == 4
        assert p1_data["last_visit_date"] == "2026-06-09"
        assert p1_data["is_vip"] is True # top 15% revenue in clinic or completed_count > 10

        # Patient 2: 1 completed appointment, LTV = 1 * 200 = 200
        p2_data = updates["patient-2"]
        assert p2_data["total_revenue_generated"] == 200.0
        assert p2_data["average_visit_value"] == 200.0
        assert p2_data["visit_frequency_days"] is None
        assert p2_data["last_visit_date"] == "2026-06-08"

        # Patient 3: 0 completed appointments
        p3_data = updates["patient-3"]
        assert p3_data["total_revenue_generated"] == 0.0
        assert p3_data["average_visit_value"] == 0.0
        assert p3_data["visit_frequency_days"] is None
        assert p3_data["last_visit_date"] is None
        assert p3_data["is_vip"] is False

@pytest.mark.asyncio
async def test_competitor_benchmarking_api(client):
    from src.main import app
    from src.core.security import get_current_user_with_role, require_active_subscription, AuthenticatedUser

    # Setup dummy user
    dummy_user = AuthenticatedUser(
        user_id="mock-user-id",
        email="owner@example.com",
        clinic_id="clinic-123",
        clinic_name="Test Clinic",
        role="owner"
    )

    # Dependency override
    app.dependency_overrides[get_current_user_with_role] = lambda: dummy_user
    app.dependency_overrides[require_active_subscription] = lambda: dummy_user

    # Mock DB response for the clinic
    mock_clinic_res = MagicMock()
    mock_clinic_res.data = {
        "benchmark_opt_in": True,
        "specialty": "Dental Clinic"
    }

    # Mock DB responses for calls & appointments
    mock_calls_res = MagicMock()
    mock_calls_res.data = []

    mock_appts_res = MagicMock()
    mock_appts_res.data = []

    # Mock other clinics query
    mock_others_res = MagicMock()
    mock_others_res.data = []

    with patch("src.services.analytics_service.supabase_read") as mock_supabase:
        def table_selector(table_name):
            mock_table = MagicMock()
            if table_name == "clinics":
                mock_select = MagicMock()
                mock_select.eq.return_value.single.return_value.execute.return_value = mock_clinic_res
                # Also mock specialty queries
                mock_select.eq.return_value.eq.return_value.execute.return_value = mock_others_res
                mock_table.select.return_value = mock_select
            elif table_name == "calls":
                mock_select = MagicMock()
                mock_select.eq.return_value.gte.return_value.execute.return_value = mock_calls_res
                mock_table.select.return_value = mock_select
            elif table_name == "appointments":
                mock_select = MagicMock()
                mock_select.eq.return_value.gte.return_value.execute.return_value = mock_appts_res
                mock_table.select.return_value = mock_select
            return mock_table

        mock_supabase.table.side_effect = table_selector

        # Make the request
        r = client.get("/api/v1/analytics/benchmarks")
        
        # Clean overrides
        app.dependency_overrides.clear()

        # Assertions
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["benchmark_opt_in"] is True
        assert data["specialty"] == "Dental Clinic"
        assert "clinic_call_volume" in data
        assert "clinic_no_show_rate" in data

