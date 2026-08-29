from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_current_user_with_role
from src.db.engine import get_db
from src.models.appointment import Appointment
from src.models.call_log import CallLog
from src.models.user import User
from src.schemas.dashboard import (
    AppointmentsData,
    CallsData,
    PeriodData,
    RevenueData,
    StatsData,
    StatsResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/stats", response_model=StatsResponse)
async def get_dashboard_stats(
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(UTC)
    if not date_from:
        date_from = now.strftime("%Y-%m-%d")
    if not date_to:
        date_to = now.strftime("%Y-%m-%d")

    start_date = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
    # for simplicity, end_date + 1 day to include the full day
    end_date = datetime.fromisoformat(date_to.replace("Z", "+00:00")) + timedelta(days=1)
    
    # Resolve tenant filter — supports both tenant_id and clinic_id on models
    tenant_id = getattr(user, "tenant_id", None) or getattr(user, "clinic_id", None)

    # 1. Appointments — MUST filter by tenant to prevent cross-clinic data exposure
    apt_filters = [
        Appointment.slot_start >= start_date,
        Appointment.slot_start < end_date,
        Appointment.is_deleted == False,
    ]
    if tenant_id:
        # Try clinic_id column first; fall back to tenant_id column
        if hasattr(Appointment, "clinic_id"):
            apt_filters.append(Appointment.clinic_id == tenant_id)
        elif hasattr(Appointment, "tenant_id"):
            apt_filters.append(Appointment.tenant_id == tenant_id)

    apt_stmt = select(
        Appointment.status,
        func.count(Appointment.id).label("count")
    ).where(*apt_filters).group_by(Appointment.status)
    
    apt_res = await db.execute(apt_stmt)
    apt_counts = {row.status: row.count for row in apt_res.all()}
    
    total_appts = sum(apt_counts.values())
    scheduled = apt_counts.get("scheduled", 0)
    confirmed = apt_counts.get("confirmed", 0)
    completed = apt_counts.get("completed", 0)
    cancelled = apt_counts.get("cancelled", 0)

    # 2. Calls — MUST filter by tenant to prevent cross-clinic data exposure
    call_filters = [
        CallLog.created_at >= start_date,
        CallLog.created_at < end_date,
    ]
    if tenant_id and hasattr(CallLog, "clinic_id"):
        call_filters.append(CallLog.clinic_id == tenant_id)
    elif tenant_id and hasattr(CallLog, "tenant_id"):
        call_filters.append(CallLog.tenant_id == tenant_id)

    call_stmt = select(
        CallLog.outcome,
        func.count(CallLog.id).label("count")
    ).where(*call_filters).group_by(CallLog.outcome)
    
    call_res = await db.execute(call_stmt)
    call_counts = {row.outcome: row.count for row in call_res.all()}
    
    total_calls = sum(call_counts.values())
    call_booked = call_counts.get("booked", 0)
    call_cancelled = call_counts.get("cancelled", 0)
    call_transferred = call_counts.get("transferred", 0)
    call_faq = call_counts.get("faq_answered", 0)
    call_no_action = call_counts.get("no_action", 0)
    
    # Calculate vs_yesterday_pct (calls comparison)
    period_len = end_date - start_date
    prev_start_date = start_date - period_len
    prev_end_date = start_date
    
    prev_call_filters = [
        CallLog.created_at >= prev_start_date,
        CallLog.created_at < prev_end_date,
    ]
    if tenant_id and hasattr(CallLog, "clinic_id"):
        prev_call_filters.append(CallLog.clinic_id == tenant_id)
    elif tenant_id and hasattr(CallLog, "tenant_id"):
        prev_call_filters.append(CallLog.tenant_id == tenant_id)

    prev_call_stmt = select(func.count(CallLog.id)).where(*prev_call_filters)
    prev_calls_count = await db.scalar(prev_call_stmt) or 0
    
    if prev_calls_count > 0:
        vs_yesterday_pct = round(((total_calls - prev_calls_count) / prev_calls_count) * 100, 1)
    else:
        vs_yesterday_pct = 100.0 if total_calls > 0 else 0.0

    # Calculate actual revenue recovered from appointments in the period using TenantSettings service prices
    from src.models.tenant_settings import TenantSettings
    settings_stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id)
    settings_res = await db.execute(settings_stmt)
    t_settings = settings_res.scalar_one_or_none()
    
    service_prices = {}
    if t_settings and t_settings.services:
        for svc in t_settings.services:
            if isinstance(svc, dict) and "name" in svc:
                service_prices[svc["name"].lower()] = svc.get("price_cents", 15000)
                
    appts_in_period_stmt = select(Appointment).where(
        Appointment.slot_start >= start_date,
        Appointment.slot_start < end_date,
        Appointment.is_deleted == False,
        Appointment.status.in_(["scheduled", "confirmed", "completed"])
    )
    appts_in_period_res = await db.execute(appts_in_period_stmt)
    appts_in_period = appts_in_period_res.scalars().all()
    
    total_revenue_cents = 0
    for appt in appts_in_period:
        svc_name = (appt.service_type or "").lower()
        price = service_prices.get(svc_name, 15000)
        total_revenue_cents += price
        
    revenue_appt_count = len(appts_in_period)
    avg_value_cents = int(total_revenue_cents / revenue_appt_count) if revenue_appt_count > 0 else 0

    # Calculate no-show rate for current month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = end_date
    
    noshow_stmt = select(func.count(Appointment.id)).where(
        Appointment.slot_start >= month_start,
        Appointment.slot_start < month_end,
        Appointment.is_deleted == False,
        Appointment.status == "no_show"
    )
    noshow_count = await db.scalar(noshow_stmt) or 0
    
    total_month_stmt = select(func.count(Appointment.id)).where(
        Appointment.slot_start >= month_start,
        Appointment.slot_start < month_end,
        Appointment.is_deleted == False,
        Appointment.status != "cancelled"
    )
    total_month_count = await db.scalar(total_month_stmt) or 0
    
    no_show_rate_month = 0.0
    if total_month_count > 0:
        no_show_rate_month = round((noshow_count / total_month_count) * 100, 1)

    ai_performance_rate = 0.0
    if total_calls > 0:
        ai_performance_rate = round(((call_booked + call_faq) / total_calls) * 100, 1)

    # 3. Prior Authorizations
    from src.models.prior_auth_request import PriorAuthRequest
    pa_stmt = select(
        PriorAuthRequest.auth_status,
        func.count(PriorAuthRequest.id).label("count")
    ).where(
        PriorAuthRequest.tenant_id == user.tenant_id,
        PriorAuthRequest.is_deleted == False
    ).group_by(PriorAuthRequest.auth_status)
    try:
        pa_res = await db.execute(pa_stmt)
        pa_counts = {row.auth_status: row.count for row in pa_res.all()}
    except Exception:
        pa_counts = {}
    
    pa_approved = pa_counts.get("approved", 0) + pa_counts.get("APPROVED", 0)
    pa_pending = pa_counts.get("pending", 0) + pa_counts.get("in_progress", 0)
    pa_total = sum(pa_counts.values())

    # 4. Outbound calls
    from src.models.outbound_call import OutboundCall
    out_stmt = select(
        OutboundCall.status,
        func.count(OutboundCall.id).label("count")
    ).where(
        OutboundCall.tenant_id == user.tenant_id
    ).group_by(OutboundCall.status)
    try:
        out_res = await db.execute(out_stmt)
        out_counts = {row.status: row.count for row in out_res.all()}
    except Exception:
        out_counts = {}
    
    outbound_total = sum(out_counts.values())
    outbound_confirmed = out_counts.get("completed", 0) + out_counts.get("confirmed", 0)

    # 5. Estimated Hours Saved:
    # ~12 mins (0.20 hrs) per handled call + ~15 mins (0.25 hrs) per booking + ~45 mins (0.75 hrs) per prior auth
    estimated_hours_saved = round(
        (total_calls * 0.20) + (call_booked * 0.25) + (outbound_confirmed * 0.15) + (max(pa_total, pa_approved) * 0.75),
        1
    )

    from src.schemas.dashboard import PriorAuthData

    return StatsResponse(
        success=True,
        data=StatsData(
            period=PeriodData(from_date=date_from, to_date=date_to),
            calls=CallsData(
                total=total_calls,
                booked=call_booked,
                cancelled=call_cancelled,
                transferred=call_transferred,
                faq_answered=call_faq,
                no_action=call_no_action,
                vs_yesterday_pct=vs_yesterday_pct,
                inbound_handled=total_calls - call_no_action,
                inbound_total=total_calls,
                outbound_total=outbound_total,
                outbound_confirmed=outbound_confirmed
            ),
            appointments=AppointmentsData(
                total_today=total_appts,
                scheduled=scheduled,
                confirmed=confirmed,
                completed=completed,
                cancelled=cancelled,
                ai_booked_today=scheduled,
                staff_booked_today=max(total_appts - scheduled, 0)
            ),
            revenue_recovered=RevenueData(
                amount_cents=total_revenue_cents,
                currency="USD",
                appointment_count=revenue_appt_count,
                avg_value_cents=avg_value_cents
            ),
            prior_auths=PriorAuthData(
                approved=pa_approved,
                pending=pa_pending,
                total=pa_total
            ),
            estimated_hours_saved=estimated_hours_saved,
            ai_performance_rate=ai_performance_rate,
            no_show_rate_month=no_show_rate_month
        )
    )

