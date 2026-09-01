import pytest
import asyncio
from unittest.mock import patch, MagicMock
from src.services.analytics_service import analytics_service

@pytest.mark.asyncio
async def test_noshow_show_rate_formula():
    """Verify mathematically sound Show Rate % = (Completed / (Completed + No-Shows)) * 100"""
    mock_appts = [
        {"id": "1", "status": "completed", "datetime": "2026-08-31T09:00:00+00:00", "revenue_amount": 150},
        {"id": "2", "status": "completed", "datetime": "2026-08-31T10:00:00+00:00", "revenue_amount": 150},
        {"id": "3", "status": "confirmed", "datetime": "2026-08-31T11:00:00+00:00", "revenue_amount": 150},
        {"id": "4", "status": "no_show", "datetime": "2026-08-31T12:00:00+00:00", "revenue_amount": 150},
        {"id": "5", "status": "scheduled", "datetime": "2026-09-01T14:00:00+00:00", "revenue_amount": 150},  # pending future
    ]
    
    with patch("src.services.analytics_service.supabase_read") as mock_read:
        # Mock clinics
        mock_clinic = MagicMock()
        mock_clinic.data = {"monthly_revenue_per_visit": 150.0}
        
        # Mock appointments
        mock_appts_res = MagicMock()
        mock_appts_res.data = mock_appts
        
        # Mock previous appointments
        mock_prev_res = MagicMock()
        mock_prev_res.data = []

        # Mock outbound calls
        mock_outbound_res = MagicMock()
        mock_outbound_res.data = [
            {
                "id": "c1",
                "campaign_type": "no_show",
                "status": "completed",
                "task_completed": True,
                "structured_result": {"response_type": "rescheduled"}
            }
        ]

        # Mock patients
        mock_patients_res = MagicMock()
        mock_patients_res.data = [
            {"id": "p1", "name": "Emily Rodriguez", "phone": "+14155550102", "no_show_count": 2}
        ]

        def table_router(table_name):
            mock_tbl = MagicMock()
            if table_name == "clinics":
                mock_tbl.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_clinic
            elif table_name == "appointments":
                # select -> eq -> gte -> lte/lt -> execute
                mock_chain = MagicMock()
                mock_chain.execute.return_value = mock_appts_res
                mock_tbl.select.return_value.eq.return_value.gte.return_value.lte.return_value = mock_chain
                mock_tbl.select.return_value.eq.return_value.gte.return_value.lt.return_value = mock_chain
            elif table_name == "outbound_calls":
                mock_chain = MagicMock()
                mock_chain.execute.return_value = mock_outbound_res
                mock_tbl.select.return_value.eq.return_value.in_.return_value = mock_chain
            elif table_name == "patients":
                mock_chain = MagicMock()
                mock_chain.execute.return_value = mock_patients_res
                mock_tbl.select.return_value.eq.return_value.gt.return_value.order.return_value.limit.return_value = mock_chain
            return mock_tbl

        mock_read.table.side_effect = table_router

        res = await analytics_service.get_noshow_analytics(clinic_id="test-clinic", preset="30")
        
        # Concluded visits = 3 completed + 1 no-show = 4 visits (scheduled is excluded!)
        assert res["concluded_appointments"] == 4
        assert res["completed_count"] == 3
        assert res["no_show_count"] == 1
        assert res["show_rate"] == 75.0  # (3 / 4) * 100
        assert res["no_show_rate"] == 25.0  # (1 / 4) * 100
        assert res["lost_revenue"] == 150.0
        assert res["recovered_revenue"] == 150.0  # 1 rebooked * $150
        assert res["recovery_converted_count"] == 1
        assert len(res["top_offenders"]) >= 1
        assert res["top_offenders"][0]["policy_recommendation"] == "Mandatory Pre-Payment Deposit"

@pytest.mark.asyncio
async def test_noshow_zero_division_safety():
    """Verify zero appointments return 0.0/100.0 without throwing ZeroDivisionError"""
    with patch("src.services.analytics_service.supabase_read") as mock_read:
        mock_empty = MagicMock()
        mock_empty.data = []

        def table_router(table_name):
            mock_tbl = MagicMock()
            if table_name == "clinics":
                mock_tbl.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
            elif table_name == "appointments":
                mock_chain = MagicMock()
                mock_chain.execute.return_value = mock_empty
                mock_tbl.select.return_value.eq.return_value.gte.return_value.lte.return_value = mock_chain
                mock_tbl.select.return_value.eq.return_value.gte.return_value.lt.return_value = mock_chain
            elif table_name == "outbound_calls":
                mock_chain = MagicMock()
                mock_chain.execute.return_value = mock_empty
                mock_tbl.select.return_value.eq.return_value.in_.return_value = mock_chain
            elif table_name == "patients":
                mock_chain = MagicMock()
                mock_chain.execute.return_value = mock_empty
                mock_tbl.select.return_value.eq.return_value.gt.return_value.order.return_value.limit.return_value = mock_chain
            return mock_tbl

        mock_read.table.side_effect = table_router

        res = await analytics_service.get_noshow_analytics(clinic_id="empty-clinic", preset="30")
        assert res["show_rate"] == 0.0
        assert res["no_show_rate"] == 0.0
        assert res["concluded_appointments"] == 0
        assert res["lost_revenue"] == 0.0
        assert res["recovered_revenue"] == 0.0
        assert res["recovery_conversion_rate"] == 0.0
        assert res["top_offenders"] == []
