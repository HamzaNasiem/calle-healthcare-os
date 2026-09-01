import datetime
import io
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ...core.security import require_permission, AuthenticatedUser, require_active_subscription
from ...services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"], dependencies=[Depends(require_active_subscription)])


@router.get("/revenue")
async def get_revenue_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns 12-month historical revenue trend, filtered event breakdown, and total period savings.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_revenue_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/overview")
async def get_overview_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Consolidated executive overview: MRR, total period revenue, recovered revenue,
    average LTV, active patient count, call volume, answer rate, and show rate.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_overview_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/calls")
async def get_calls_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns 7x12 call density heatmap, peak hours distribution, answer rate, and MoM velocity.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_calls_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patients")
async def get_patients_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns patient demographics, new vs returning ratio, average LTV, VIP leaderboard, and churn risk list.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_patients_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ltv")
async def get_ltv_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Detailed Patient Lifetime Value (LTV) analytics: average LTV, VIP leaderboard,
    churn risk cohorts, and revenue distribution across patient tiers.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.calculate_ltv(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/no-shows")
async def get_noshows_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns appointment show vs no-show rate, reduction rate (% change), confirmed vs unconfirmed show rates,
    daily trend, lost revenue, 2h recovery campaign metrics, and repeat offenders list.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_noshow_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/attendance-rate")
async def get_attendance_rate_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns dedicated attendance and show rate analytics:
    Show Rate % = (Completed / (Completed + No-Shows)) * 100, no-show rate, and trend.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_noshow_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {
            "data": {
                "show_rate": data.get("show_rate", 100.0),
                "no_show_rate": data.get("no_show_rate", 0.0),
                "completed_count": data.get("completed_count", 0),
                "no_show_count": data.get("no_show_count", 0),
                "concluded_appointments": data.get("concluded_appointments", 0),
                "lost_revenue": data.get("lost_revenue", 0.0),
                "recovered_revenue": data.get("recovered_revenue", 0.0),
                "confirmed_show_rate": data.get("confirmed_show_rate", 0.0),
                "unconfirmed_show_rate": data.get("unconfirmed_show_rate", 0.0),
                "confirmed_lift_rate": data.get("confirmed_lift_rate", 0.0),
                "trend": data.get("trend", []),
                "top_offenders": data.get("top_offenders", [])
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recalls")
async def get_recalls_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns recall campaign metrics (legacy compatibility endpoint).
    """
    clinic_id = auth.clinic_id
    try:
        camp_data = await analytics_service.get_campaign_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": camp_data.get("recalls_legacy", {})}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campaign-comparison")
@router.get("/campaigns")
async def get_campaigns_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns complete multi-campaign performance comparison:
    Confirmation vs No-Show Recovery vs Patient Recall vs Post-Visit Survey vs Waitlist Backfill.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_campaign_comparison(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/roi")
async def get_roi_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    staff_wage: float = Query(25.0, ge=10.0, le=200.0),
    visit_value: float = Query(150.0, ge=20.0, le=2000.0),
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns Staff Hours Saved per Week and full economic ROI calculator values.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_roi_kpis(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset,
            staff_hourly_wage=staff_wage,
            avg_visit_value=visit_value
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/suggestions")
async def get_scheduling_suggestions(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns AI-driven operations summary and smart scheduling recommendations.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_scheduling_suggestions(clinic_id=clinic_id)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/benchmarks")
async def get_competitor_benchmarking(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns anonymous competitor benchmarking against specialty averages.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_competitor_benchmarks(clinic_id=clinic_id)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/specialty-benchmarks")
async def get_specialty_benchmarking(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns anonymous competitor benchmarking against specialty averages (APTA / MGMA / AMGA standards).
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_competitor_benchmarks(clinic_id=clinic_id)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/benchmarks/opt-in")
async def toggle_benchmarks_opt_in(
    opt_in: bool = Query(..., description="Whether to opt into anonymous benchmarking"),
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Toggles clinic participation in anonymous specialty benchmarking.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.set_benchmark_opt_in(clinic_id=clinic_id, opt_in=opt_in)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
async def export_analytics_csv(
    request: Request,
    type: str = Query("revenue", pattern="^(revenue|financials|calls|heatmap|patients|vips|no_shows|noshows|no-shows|appointments|recalls|campaigns|campaign_comparison|campaign-comparison|roi|savings|summary)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Exports analytics report as CSV and creates a HIPAA audit log entry.
    """
    clinic_id = auth.clinic_id
    try:
        csv_content = await analytics_service.generate_csv_export(
            clinic_id=clinic_id,
            report_type=type,
            start_date=start_date,
            end_date=end_date,
            preset=preset,
            user_id=auth.user_id,
            user_email=auth.email,
            user_role=getattr(auth, "role", "staff"),
            request=request
        )


        clean_type_name = type.replace("-", "_")
        filename = f"bytelytic_{clean_type_name}_report_{datetime.datetime.now().strftime('%Y%m%d')}.csv"

        return StreamingResponse(
            io.BytesIO(csv_content.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

