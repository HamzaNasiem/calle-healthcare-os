import pytest
import asyncio
from src.services.analytics_service import analytics_service


@pytest.mark.asyncio
async def test_generate_ai_insights_with_real_clinic():
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    result = await analytics_service.generate_ai_insights(clinic_id=clinic_id, force=True)
    
    assert "recommendations" in result
    assert "latest_ai_insights" in result
    assert "metadata" in result
    assert len(result["recommendations"]) > 0
    assert result["latest_ai_insights"] is not None
    assert len(result["latest_ai_insights"]) > 100

    # Ensure markdown headers exist
    assert "### Executive Operations Summary" in result["latest_ai_insights"]
    assert "### Attendance & Patient Retention Leakage" in result["latest_ai_insights"]
    assert "### Capacity & Front Desk Workflow" in result["latest_ai_insights"]
    assert "### Actionable Staff Directives" in result["latest_ai_insights"]

    # Check recommendations structure
    for rec in result["recommendations"]:
        assert "id" in rec
        assert "type" in rec
        assert "title" in rec
        assert "description" in rec
        assert "action_label" in rec
        assert "action_payload" in rec
        assert ("route" in rec["action_payload"] or "tab" in rec["action_payload"])


@pytest.mark.asyncio
async def test_get_scheduling_suggestions():
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    result = await analytics_service.get_scheduling_suggestions(clinic_id=clinic_id)
    
    assert "recommendations" in result
    assert "latest_ai_insights" in result
    assert result["latest_ai_insights"] is not None
    assert len(result["recommendations"]) >= 2


@pytest.mark.asyncio
async def test_zero_data_clinic_graceful_handling():
    # Test with non-existent clinic UUID to verify zero-data / division-by-zero resilience
    dummy_clinic_id = "00000000-0000-0000-0000-000000000000"
    result = await analytics_service.generate_ai_insights(clinic_id=dummy_clinic_id, force=True)
    
    assert "recommendations" in result
    assert "latest_ai_insights" in result
    assert result["latest_ai_insights"] is not None
    # Ensure zero data doesn't produce NaN or crash
    assert "NaN" not in result["latest_ai_insights"]
