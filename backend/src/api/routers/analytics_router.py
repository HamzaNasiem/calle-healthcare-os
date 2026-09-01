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
    Returns 7-day x 24-hour call density heatmap, peak hours distribution, answer rate, and MoM velocity.
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


@router.get("/calls-heatmap")
async def get_calls_heatmap(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns 7-day x 24-hour call density heatmap matrix with clinic timezone localization.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_call_density_heatmap(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/peak-hours")
async def get_peak_hours_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns hourly peak call distribution breakdown for handled and missed calls.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_call_density_heatmap(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        return {"data": data.get("peak_hours_distribution", [])}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/call-metrics")
async def get_call_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns call KPI metrics (total volume, answer rate, conversion, duration, MoM change).
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_calls_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        metrics = {k: v for k, v in data.items() if k not in ("heatmap",)}
        return {"data": metrics}
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
    user_role = getattr(auth, "role", "clinician")
    try:
        data = await analytics_service.get_patients_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset,
            user_role=user_role
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/vip-patients")
async def get_vip_patients_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns VIP patient leaderboard with lifetime value, visits, and role-based PHI masking.
    """
    clinic_id = auth.clinic_id
    user_role = getattr(auth, "role", "clinician")
    try:
        data = await analytics_service.get_vip_patients(
            clinic_id=clinic_id,
            limit=limit,
            user_role=user_role
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patient-retention")
async def get_patient_retention_cohorts(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns patient retention cohorts, new vs returning ratio, average LTV, and churn risk analysis.
    """
    clinic_id = auth.clinic_id
    user_role = getattr(auth, "role", "clinician")
    try:
        data = await analytics_service.calculate_retention_cohorts(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset,
            user_role=user_role
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
    daily_calls: Optional[int] = Query(None, ge=0, le=500),
    avg_call_mins: float = Query(4.5, ge=1.0, le=30.0),
    clinic_days: int = Query(22, ge=1, le=31),
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns Staff Hours Saved per Week and full economic ROI calculator values.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.calculate_staff_roi(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset,
            staff_hourly_wage=staff_wage,
            avg_visit_value=visit_value,
            daily_call_volume=daily_calls,
            avg_mins_per_call=avg_call_mins,
            clinic_days_per_month=clinic_days
        )
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/staff-savings")
async def get_staff_savings_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    staff_wage: float = Query(25.0, ge=10.0, le=200.0),
    visit_value: float = Query(150.0, ge=20.0, le=2000.0),
    daily_calls: Optional[int] = Query(None, ge=0, le=500),
    avg_call_mins: float = Query(4.5, ge=1.0, le=30.0),
    clinic_days: int = Query(22, ge=1, le=31),
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Staff ROI & Labor Cost Savings Calculator endpoint.
    Calculates Hours Saved = (Total AI Calls * avg_mins_per_call) / 60
    and Dollar Savings = Hours Saved * hourly_wage.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.calculate_staff_roi(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset,
            staff_hourly_wage=staff_wage,
            avg_visit_value=visit_value,
            daily_call_volume=daily_calls,
            avg_mins_per_call=avg_call_mins,
            clinic_days_per_month=clinic_days
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


@router.get("/ai-insights")
async def get_ai_insights(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns latest autonomous CMOO AI operations insights and executive report.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_scheduling_suggestions(clinic_id=clinic_id)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/operational-suggestions")
async def get_operational_suggestions(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Returns dynamically calculated operational scheduling suggestions and staffing directives.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.get_scheduling_suggestions(clinic_id=clinic_id)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ai-insights/generate")
async def trigger_generate_ai_insights(
    auth: AuthenticatedUser = Depends(require_permission("dashboard:read"))
):
    """
    Force triggers dynamic AI insights generation based on live clinic DB stats.
    """
    clinic_id = auth.clinic_id
    try:
        data = await analytics_service.generate_ai_insights(clinic_id=clinic_id, force=True)
        return {"data": data, "status": "success"}
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

