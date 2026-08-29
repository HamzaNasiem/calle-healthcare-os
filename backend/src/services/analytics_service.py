import datetime
import io
import csv
from typing import Optional, Dict, Any, List, Tuple
from ..core.database import supabase, supabase_read
from ..core.logger import log
from .audit_service import audit_service


class AnalyticsService:
    """
    Enterprise-grade Analytics and Practice Intelligence Service for Bytelytic OS.
    Handles aggregation, statistical calculations, KPI modeling, staff ROI, and HIPAA exports.
    """

    def parse_date_range(
        self,
        preset: Optional[Any] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[datetime.datetime, datetime.datetime, datetime.datetime, datetime.datetime, int]:
        """
        Parses date presets ('7', '30', '90', 'month', 'all') or explicit ISO date bounds.
        Returns: (start_dt, end_dt, prev_start_dt, prev_end_dt, period_days) in UTC.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        preset_str = str(preset).lower() if preset is not None else None

        if end_date:
            try:
                clean_end = end_date.replace("Z", "+00:00")
                if len(clean_end) == 10:  # "YYYY-MM-DD"
                    end_dt = datetime.datetime.fromisoformat(f"{clean_end}T23:59:59.999999+00:00")
                else:
                    end_dt = datetime.datetime.fromisoformat(clean_end)
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                end_dt = now
        else:
            end_dt = now

        if start_date:
            try:
                clean_start = start_date.replace("Z", "+00:00")
                if len(clean_start) == 10:  # "YYYY-MM-DD"
                    start_dt = datetime.datetime.fromisoformat(f"{clean_start}T00:00:00+00:00")
                else:
                    start_dt = datetime.datetime.fromisoformat(clean_start)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                start_dt = end_dt - datetime.timedelta(days=30)
        elif preset_str in ("7", "last_7_days"):
            start_dt = end_dt - datetime.timedelta(days=7)
        elif preset_str in ("30", "last_30_days"):
            start_dt = end_dt - datetime.timedelta(days=30)
        elif preset_str in ("90", "last_90_days"):
            start_dt = end_dt - datetime.timedelta(days=90)
        elif preset_str in ("month", "this_month"):
            start_dt = datetime.datetime(end_dt.year, end_dt.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        elif preset_str in ("all", "all_time", "365"):
            start_dt = end_dt - datetime.timedelta(days=365)
        else:
            start_dt = end_dt - datetime.timedelta(days=30)

        # Ensure start is strictly before end
        if start_dt > end_dt:
            start_dt, end_dt = end_dt - datetime.timedelta(days=30), start_dt

        period_seconds = max(1, int((end_dt - start_dt).total_seconds()))
        period_days = max(1, int(period_seconds / 86400))
        
        # Calculate matching previous period for period-over-period comparisons
        prev_start_dt = start_dt - datetime.timedelta(days=period_days)
        prev_end_dt = start_dt

        return start_dt, end_dt, prev_start_dt, prev_end_dt, period_days

    async def get_revenue_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates 12-month revenue trajectory, event type breakdowns, and financial pipeline impact.
        """
        start_dt, end_dt, _, _, period_days = self.parse_date_range(preset, start_date, end_date)

        # 1. 12-Month Area Chart Data
        twelve_months_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).isoformat()
        rev_res = supabase_read.table("revenue_events").select("amount_cents, created_at, event_type") \
            .eq("clinic_id", clinic_id) \
            .gte("created_at", twelve_months_ago) \
            .execute()
        
        events = rev_res.data or []

        # Pre-populate chronological last 12 calendar months with 0s
        now = datetime.datetime.now(datetime.timezone.utc)
        monthly_rev: Dict[str, Dict[str, Any]] = {}
        curr_year = now.year
        curr_month = now.month
        month_keys = []

        for _ in range(12):
            month_date = datetime.date(curr_year, curr_month, 1)
            month_str = month_date.strftime("%b %Y")
            month_keys.append((month_date, month_str))
            monthly_rev[month_str] = {"revenue": 0, "bookings": 0}
            curr_month -= 1
            if curr_month == 0:
                curr_month = 12
                curr_year -= 1

        for ev in events:
            if ev.get("created_at"):
                try:
                    dt = datetime.datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00"))
                    key = dt.strftime("%b %Y")
                    amt = ev.get("amount_cents", 0)
                    if key in monthly_rev:
                        monthly_rev[key]["revenue"] += amt
                        monthly_rev[key]["bookings"] += 1
                except Exception:
                    pass

        # Sort months chronologically ascending
        sorted_months = []
        for month_date, month_str in reversed(month_keys):
            stats = monthly_rev.get(month_str, {"revenue": 0, "bookings": 0})
            sorted_months.append({
                "month": month_str,
                "revenue": round(stats["revenue"] / 100),
                "bookings": stats["bookings"]
            })

        # 2. Filtered breakdown by event type within selected date range
        filtered_rev_res = supabase_read.table("revenue_events").select("amount_cents, event_type, created_at") \
            .eq("clinic_id", clinic_id) \
            .gte("created_at", start_dt.isoformat()) \
            .lte("created_at", end_dt.isoformat()) \
            .execute()

        filtered_events = filtered_rev_res.data or []
        breakdown_cents: Dict[str, int] = {}
        total_period_revenue_cents = 0

        for ev in filtered_events:
            e_type = ev.get("event_type") or "appointment_booked"
            amt = ev.get("amount_cents", 0)
            breakdown_cents[e_type] = breakdown_cents.get(e_type, 0) + amt
            total_period_revenue_cents += amt

        # Format breakdown list for charts
        formatted_breakdown = [
            {
                "type": k.replace("_", " ").title(),
                "value": round(v / 100),
                "raw_type": k
            }
            for k, v in sorted(breakdown_cents.items(), key=lambda x: x[1], reverse=True)
        ]

        total_period_revenue = round(total_period_revenue_cents / 100)
        projected_annual = round((total_period_revenue / max(1, period_days)) * 365)

        return {
            "trend": sorted_months,
            "breakdown": formatted_breakdown,
            "total_period_revenue": total_period_revenue,
            "projected_annual_savings": projected_annual,
            "period_days": period_days,
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat()
        }

    async def get_calls_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Aggregates inbound/outbound call load, 7x12 heatmap density matrix, peak hours distribution,
        MoM call volume velocity, and booking conversion rates.
        """
        start_dt, end_dt, prev_start_dt, prev_end_dt, period_days = self.parse_date_range(preset, start_date, end_date)

        # 1. Fetch calls in current date range
        calls_res = supabase_read.table("calls").select("id, status, outcome, direction, call_type, started_at, duration_seconds") \
            .eq("clinic_id", clinic_id) \
            .gte("started_at", start_dt.isoformat()) \
            .lte("started_at", end_dt.isoformat()) \
            .execute()
        
        calls = calls_res.data or []
        total_calls = len(calls)
        handled_calls = sum(1 for c in calls if c.get("status") == "completed" or (c.get("outcome") and c.get("outcome") != "no_answer"))
        missed_calls = total_calls - handled_calls
        total_duration_sec = sum(int(c.get("duration_seconds") or 0) for c in calls)
        avg_duration_sec = round(total_duration_sec / max(1, total_calls))

        # 2. Inbound conversion rate (appointments booked via calls)
        booked_calls = sum(
            1 for c in calls 
            if any(term in str(c.get("outcome", "")).lower() for term in ["scheduled", "booked", "confirmed", "appointment"])
        )
        inbound_calls = [c for c in calls if c.get("direction") == "inbound" or not c.get("direction")]
        inbound_count = len(inbound_calls)
        conversion_rate = round((booked_calls / max(1, inbound_count)) * 100, 1) if inbound_count > 0 else 0.0

        # 3. Heatmap Matrix (Mon-Sun x 8am-7pm = 12 slots)
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        hours = ['8am', '9am', '10am', '11am', '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm']

        heatmap_grid: Dict[str, Dict[str, Dict[str, int]]] = {
            day: {hour: {"handled": 0, "missed": 0, "total": 0} for hour in hours} 
            for day in days
        }

        # 4. Hourly Distribution (all days combined) for Peak Inbound Distribution Chart
        hourly_totals: Dict[str, Dict[str, int]] = {
            hour: {"hour": hour, "handled": 0, "missed": 0, "total": 0} 
            for hour in hours
        }

        # 5. Day of Week Distribution
        day_totals: Dict[str, Dict[str, int]] = {
            day: {"day": day, "handled": 0, "missed": 0, "total": 0} 
            for day in days
        }

        for c in calls:
            started_at_str = c.get("started_at")
            if started_at_str:
                try:
                    dt = datetime.datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                    day_idx = dt.weekday()  # 0 = Monday
                    day_name = days[day_idx]
                    hour_int = dt.hour
                    
                    if 8 <= hour_int < 20:
                        # Build key matching hours list format: '8am', '9am', '12pm', '1pm' etc.
                        ampm_hour = dt.strftime("%I%p").lower().lstrip('0') or "12pm"
                        if ampm_hour in heatmap_grid[day_name]:
                            is_handled = (c.get("status") == "completed" or (c.get("outcome") and c.get("outcome") != "no_answer"))
                            if is_handled:
                                heatmap_grid[day_name][ampm_hour]["handled"] += 1
                                hourly_totals[ampm_hour]["handled"] += 1
                                day_totals[day_name]["handled"] += 1
                            else:
                                heatmap_grid[day_name][ampm_hour]["missed"] += 1
                                hourly_totals[ampm_hour]["missed"] += 1
                                day_totals[day_name]["missed"] += 1
                            
                            heatmap_grid[day_name][ampm_hour]["total"] += 1
                            hourly_totals[ampm_hour]["total"] += 1

                            day_totals[day_name]["total"] += 1
                except Exception:
                    pass

        # 6. Calculate period-over-period change (MoM)
        prev_calls_res = supabase_read.table("calls").select("id") \
            .eq("clinic_id", clinic_id) \
            .gte("started_at", prev_start_dt.isoformat()) \
            .lt("started_at", prev_end_dt.isoformat()) \
            .execute()
        
        prev_calls_count = len(prev_calls_res.data or [])
        if prev_calls_count > 0:
            mom_change = round(((total_calls - prev_calls_count) / prev_calls_count) * 100, 1)
        else:
            mom_change = 0.0

        answer_rate = round((handled_calls / max(1, total_calls)) * 100, 1) if total_calls > 0 else 100.0

        return {
            "heatmap": heatmap_grid,
            "peak_hours_distribution": list(hourly_totals.values()),
            "day_distribution": list(day_totals.values()),
            "total_calls": total_calls,
            "handled_calls": handled_calls,
            "missed_calls": missed_calls,
            "answer_rate": answer_rate,
            "inbound_conversion_rate": conversion_rate,
            "booked_calls_count": booked_calls,
            "avg_duration_seconds": avg_duration_sec,
            "total_duration_minutes": round(total_duration_sec / 60, 1),
            "mom_change_percent": mom_change,
            "period_days": period_days
        }

    async def get_patients_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates patient demographics, new vs returning ratio, average LTV, VIP leaderboard,
        and high churn-risk watchlist.
        """
        start_dt, end_dt, _, _, _ = self.parse_date_range(preset, start_date, end_date)

        # 1. Fetch patients
        patients_res = supabase_read.table("patients").select(
            "id, name, email, phone, created_at, is_vip, churn_risk_score, total_revenue_generated, average_visit_value, last_visit_date"
        ).eq("clinic_id", clinic_id).execute()

        patients = patients_res.data or []
        total_patients = len(patients)

        # 2. Fetch completed appointments in selected date range
        appts_res = supabase_read.table("appointments").select("patient_id, status") \
            .eq("clinic_id", clinic_id) \
            .eq("status", "completed") \
            .gte("datetime", start_dt.isoformat()) \
            .lte("datetime", end_dt.isoformat()) \
            .execute()

        appts = appts_res.data or []
        active_patient_ids = set(a["patient_id"] for a in appts if a.get("patient_id"))

        # Calculate new vs returning patients
        new_count = 0
        returning_count = 0
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()

        total_revenue_acc = 0.0
        for p in patients:
            p_created = p.get("created_at")
            p_rev = float(p.get("total_revenue_generated") or 0.0)
            total_revenue_acc += p_rev

            if p_created and start_iso <= p_created <= end_iso:
                new_count += 1
            elif p.get("id") in active_patient_ids:
                returning_count += 1

        avg_ltv = round(total_revenue_acc / max(1, total_patients), 2) if total_patients > 0 else 0.0

        # Top VIP list (highest revenue generated)
        vips = [p for p in patients if p.get("is_vip") or float(p.get("total_revenue_generated") or 0.0) > 300.0]
        vips_sorted = sorted(vips, key=lambda x: float(x.get("total_revenue_generated") or 0.0), reverse=True)[:10]

        # Churn risk patients (churn_risk_score >= 0.4 or overdue)
        churn_risk_patients = [p for p in patients if float(p.get("churn_risk_score") or 0.0) >= 0.4]
        churn_sorted = sorted(churn_risk_patients, key=lambda x: float(x.get("churn_risk_score") or 0.0), reverse=True)[:10]

        return {
            "ratio": [
                {"name": "New Patients", "value": new_count},
                {"name": "Returning Patients", "value": returning_count}
            ],
            "vip_list": vips_sorted,
            "churn_risk_list": churn_sorted,
            "total_patients": total_patients,
            "new_patients_count": new_count,
            "returning_patients_count": returning_count,
            "average_ltv": avg_ltv
        }

    async def get_noshow_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates clinic no-show rates, no-show reduction rate (% change vs previous period and vs benchmark),
        confirmed vs unconfirmed show rates, daily trend data, and top offenders.
        """
        start_dt, end_dt, prev_start_dt, prev_end_dt, period_days = self.parse_date_range(preset, start_date, end_date)

        # 1. Current period appointments
        appts_res = supabase_read.table("appointments").select(
            "id, status, datetime, patient_name, patient_phone, confirmed_at, reminder_sent"
        ).eq("clinic_id", clinic_id) \
         .gte("datetime", start_dt.isoformat()) \
         .lte("datetime", end_dt.isoformat()) \
         .execute()

        appts = appts_res.data or []
        total_appts = len(appts)
        no_show_count = sum(1 for a in appts if a.get("status") == "no_show")
        attended_count = sum(1 for a in appts if a.get("status") in ("completed", "attended", "confirmed", "scheduled"))
        no_show_rate = round((no_show_count / max(1, total_appts)) * 100, 1) if total_appts > 0 else 0.0
        show_rate = round(100.0 - no_show_rate, 1) if total_appts > 0 else 100.0

        # 2. Previous period appointments for No-Show Reduction Rate calculation
        prev_appts_res = supabase_read.table("appointments").select("status") \
            .eq("clinic_id", clinic_id) \
            .gte("datetime", prev_start_dt.isoformat()) \
            .lt("datetime", prev_end_dt.isoformat()) \
            .execute()

        prev_appts = prev_appts_res.data or []
        prev_total = len(prev_appts)
        prev_noshows = sum(1 for a in prev_appts if a.get("status") == "no_show")
        prev_noshow_rate = round((prev_noshows / max(1, prev_total)) * 100, 1) if prev_total > 0 else 0.0

        # Reduction rate (% change): Positive indicates improvement (fewer no-shows)
        if prev_noshow_rate > 0 and total_appts > 0:
            noshow_reduction_rate = round(((prev_noshow_rate - no_show_rate) / prev_noshow_rate) * 100, 1)
        elif prev_total == 0 and total_appts > 0 and no_show_rate == 0:
            noshow_reduction_rate = 100.0
        else:
            noshow_reduction_rate = 0.0

        # National medical clinic benchmark is 18.0%
        benchmark_baseline = 18.0
        benchmark_savings_rate = round(benchmark_baseline - no_show_rate, 1) if total_appts > 0 else 0.0

        # 3. Confirmed vs Unconfirmed show rate efficacy analysis
        confirmed_appts = [a for a in appts if a.get("confirmed_at") or a.get("status") == "confirmed" or a.get("reminder_sent")]
        unconfirmed_appts = [a for a in appts if not (a.get("confirmed_at") or a.get("status") == "confirmed" or a.get("reminder_sent"))]

        conf_total = len(confirmed_appts)
        conf_noshows = sum(1 for a in confirmed_appts if a.get("status") == "no_show")
        conf_show_rate = round(((conf_total - conf_noshows) / max(1, conf_total)) * 100, 1) if conf_total > 0 else 0.0

        unconf_total = len(unconfirmed_appts)
        unconf_noshows = sum(1 for a in unconfirmed_appts if a.get("status") == "no_show")
        unconf_show_rate = round(((unconf_total - unconf_noshows) / max(1, unconf_total)) * 100, 1) if unconf_total > 0 else 0.0

        # 4. Daily Trend
        by_day: Dict[str, Dict[str, Any]] = {}
        curr_dt = start_dt.date()
        end_limit = end_dt.date()

        while curr_dt <= end_limit:
            day_str = curr_dt.isoformat()
            by_day[day_str] = {"date": day_str, "total": 0, "noshows": 0, "attended": 0}
            curr_dt += datetime.timedelta(days=1)

        for a in appts:
            dt_str = a.get("datetime")
            if dt_str:
                day_key = dt_str[:10]
                if day_key in by_day:
                    by_day[day_key]["total"] += 1
                    if a.get("status") == "no_show":
                        by_day[day_key]["noshows"] += 1
                    else:
                        by_day[day_key]["attended"] += 1

        trend = []
        for day_str, stats in sorted(by_day.items()):
            tot = stats["total"]
            ns = stats["noshows"]
            ns_rate = round((ns / max(1, tot)) * 100, 1) if tot > 0 else 0.0
            s_rate = round(100.0 - ns_rate, 1) if tot > 0 else 100.0
            trend.append({
                "date": day_str,
                "no_show_rate": ns_rate,
                "show_rate": s_rate,
                "total": tot,
                "no_shows": ns,
                "attended": stats["attended"]
            })

        # 5. Top No-Show Offenders
        offenders_res = supabase_read.table("patients").select("name, phone, no_show_count") \
            .eq("clinic_id", clinic_id) \
            .gt("no_show_count", 0) \
            .order("no_show_count", desc=True) \
            .limit(10) \
            .execute()

        return {
            "no_show_rate": no_show_rate,
            "show_rate": show_rate,
            "no_show_count": no_show_count,
            "attended_count": attended_count,
            "total_appointments": total_appts,
            "prev_no_show_rate": prev_noshow_rate,
            "no_show_reduction_rate": noshow_reduction_rate,
            "benchmark_baseline": benchmark_baseline,
            "benchmark_savings_rate": benchmark_savings_rate,
            "confirmed_show_rate": conf_show_rate,
            "unconfirmed_show_rate": unconf_show_rate,
            "confirmation_count": conf_total,
            "trend": trend,
            "top_offenders": offenders_res.data or []
        }

    async def get_campaign_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates side-by-side performance across all 4 healthcare voice & messaging campaigns:
        Confirmation vs No-Show Recovery vs Patient Recall vs Post-Visit Survey.
        """
        start_dt, end_dt, _, _, _ = self.parse_date_range(preset, start_date, end_date)

        # Get average visit value from clinic profile
        clinic_res = supabase_read.table("clinics").select("monthly_revenue_per_visit").eq("id", clinic_id).single().execute()
        avg_visit_val = float(clinic_res.data.get("monthly_revenue_per_visit") or 150.0) if clinic_res.data else 150.0

        # Query outbound_calls table
        outbound_res = supabase_read.table("outbound_calls").select(
            "id, campaign_type, status, task_completed, completion_score, structured_result, created_at"
        ).eq("clinic_id", clinic_id) \
         .gte("created_at", start_dt.isoformat()) \
         .lte("created_at", end_dt.isoformat()) \
         .execute()

        outbound_calls = outbound_res.data or []

        # Query calls table for legacy or inbound recall/confirm records
        calls_res = supabase_read.table("calls").select(
            "id, call_type, status, outcome, started_at"
        ).eq("clinic_id", clinic_id) \
         .gte("started_at", start_dt.isoformat()) \
         .lte("started_at", end_dt.isoformat()) \
         .execute()

        legacy_calls = calls_res.data or []

        # Campaign Aggregator
        campaign_types = ["confirmation", "no_show", "recall", "survey"]
        campaign_stats: Dict[str, Dict[str, Any]] = {
            ctype: {
                "campaign_type": ctype,
                "title": {
                    "confirmation": "Appointment Confirmations",
                    "no_show": "No-Show Recovery",
                    "recall": "Overdue Patient Recalls",
                    "survey": "Post-Visit Satisfaction"
                }.get(ctype, ctype.title()),
                "total_initiated": 0,
                "reached_count": 0,
                "converted_count": 0,
                "revenue_recovered": 0.0,
                "reached_rate": 0.0,
                "conversion_rate": 0.0
            }
            for ctype in campaign_types
        }

        # Aggregate outbound_calls
        for call in outbound_calls:
            ctype = call.get("campaign_type") or "confirmation"
            if ctype not in campaign_stats:
                continue
            
            campaign_stats[ctype]["total_initiated"] += 1
            status = call.get("status")
            task_completed = call.get("task_completed", False)
            struct = call.get("structured_result") or {}

            if status in ("completed", "answered", "success"):
                campaign_stats[ctype]["reached_count"] += 1

            # Determine goal conversion
            converted = False
            if task_completed:
                converted = True
            elif ctype == "confirmation" and struct.get("will_attend") == "yes":
                converted = True
            elif ctype == "no_show" and struct.get("rescheduled") in (True, "yes"):
                converted = True
            elif ctype == "recall" and struct.get("booked") in (True, "yes"):
                converted = True
            elif ctype == "survey" and struct.get("score") is not None:
                converted = True

            if converted:
                campaign_stats[ctype]["converted_count"] += 1
                if ctype in ("confirmation", "no_show", "recall"):
                    campaign_stats[ctype]["revenue_recovered"] += avg_visit_val

        # Blend legacy calls records if outbound_calls table is empty
        for call in legacy_calls:
            ctype = call.get("call_type") or "recall"
            if ctype in campaign_stats and campaign_stats[ctype]["total_initiated"] == 0:
                campaign_stats[ctype]["total_initiated"] += 1
                status = call.get("status")
                outcome = str(call.get("outcome", "")).lower()
                if status == "completed" or outcome != "no_answer":
                    campaign_stats[ctype]["reached_count"] += 1
                if "scheduled" in outcome or "booked" in outcome or "confirmed" in outcome:
                    campaign_stats[ctype]["converted_count"] += 1
                    campaign_stats[ctype]["revenue_recovered"] += avg_visit_val

        # Compute percentage rates
        comparison_chart = []
        total_campaign_revenue = 0.0
        total_campaign_conversions = 0

        for ctype in campaign_types:
            stat = campaign_stats[ctype]
            init = stat["total_initiated"]
            reach = stat["reached_count"]
            conv = stat["converted_count"]
            
            stat["reached_rate"] = round((reach / max(1, init)) * 100, 1) if init > 0 else 0.0
            stat["conversion_rate"] = round((conv / max(1, init)) * 100, 1) if init > 0 else 0.0
            stat["revenue_recovered"] = round(stat["revenue_recovered"])
            
            total_campaign_revenue += stat["revenue_recovered"]
            total_campaign_conversions += conv

            comparison_chart.append({
                "campaign": stat["title"].split()[0],  # "Confirmation", "No-Show", "Recall", "Survey"
                "full_title": stat["title"],
                "initiated": init,
                "reached": reach,
                "converted": conv,
                "conversion_rate": stat["conversion_rate"],
                "revenue": stat["revenue_recovered"]
            })

        # Legacy recalls compatibility object
        recall_stat = campaign_stats["recall"]
        legacy_recalls_data = {
            "called": recall_stat["total_initiated"],
            "answered": recall_stat["reached_count"],
            "booked": recall_stat["converted_count"],
            "revenue_recovered": recall_stat["revenue_recovered"],
            "conversion_rate": recall_stat["conversion_rate"]
        }

        return {
            "campaigns": campaign_stats,
            "comparison_chart": comparison_chart,
            "total_campaign_revenue": total_campaign_revenue,
            "total_campaign_conversions": total_campaign_conversions,
            "recalls_legacy": legacy_recalls_data
        }

    async def get_roi_kpis(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None,
        staff_hourly_wage: float = 25.0,
        avg_visit_value: float = 150.0
    ) -> Dict[str, Any]:
        """
        Calculates Staff Hours Saved per Week and full economic ROI for clinic practice leadership.
        """
        start_dt, end_dt, _, _, period_days = self.parse_date_range(preset, start_date, end_date)
        period_weeks = max(0.14, round(period_days / 7.0, 2))

        # 1. Total Calls Handled (Inbound)
        calls_res = supabase_read.table("calls").select("id, status") \
            .eq("clinic_id", clinic_id) \
            .gte("started_at", start_dt.isoformat()) \
            .lte("started_at", end_dt.isoformat()) \
            .execute()
        
        total_calls = len(calls_res.data or [])

        # 2. Total Outbound Campaign Calls
        outbound_res = supabase_read.table("outbound_calls").select("id, campaign_type, task_completed") \
            .eq("clinic_id", clinic_id) \
            .gte("created_at", start_dt.isoformat()) \
            .lte("created_at", end_dt.isoformat()) \
            .execute()
        
        outbound_calls = outbound_res.data or []
        confirmations_count = sum(1 for c in outbound_calls if c.get("campaign_type") == "confirmation")
        noshow_recalls_count = len(outbound_calls) - confirmations_count

        # 3. Appointments Confirmed & Saved
        appts_res = supabase_read.table("appointments").select("id, status, confirmed_at, reminder_sent") \
            .eq("clinic_id", clinic_id) \
            .gte("datetime", start_dt.isoformat()) \
            .lte("datetime", end_dt.isoformat()) \
            .execute()

        appts = appts_res.data or []
        confirmed_count = sum(1 for a in appts if a.get("confirmed_at") or a.get("status") == "confirmed" or a.get("reminder_sent"))

        # Minutes saved model:
        # - Inbound AI call handled: 4.5 minutes saved (patient triage + booking + answering questions)
        # - Outbound confirmation call / reminder: 3.0 minutes saved
        # - Recall outreach / no-show follow-up: 5.0 minutes saved
        minutes_inbound = total_calls * 4.5
        minutes_confirmations = max(confirmations_count, confirmed_count) * 3.0
        minutes_recalls = noshow_recalls_count * 5.0

        total_minutes_saved = minutes_inbound + minutes_confirmations + minutes_recalls
        total_hours_saved = round(total_minutes_saved / 60.0, 1)
        hours_saved_per_week = round(total_hours_saved / period_weeks, 1)

        # Financial savings
        staff_cost_saved = round(total_hours_saved * staff_hourly_wage, 2)
        
        # Revenue protected by reducing no-shows
        protected_appts_count = max(0, int(len(appts) * 0.08))  # estimated 8% no-show deflection
        revenue_protected = round(protected_appts_count * avg_visit_value, 2)

        total_economic_benefit = round(staff_cost_saved + revenue_protected, 2)
        monthly_software_cost = 299.0
        roi_multiplier = round((total_economic_benefit / max(1.0, (monthly_software_cost * (period_days / 30.0)))), 1)

        return {
            "staff_hours_saved_total": total_hours_saved,
            "staff_hours_saved_per_week": hours_saved_per_week,
            "total_minutes_saved": round(total_minutes_saved),
            "staff_cost_saved": staff_cost_saved,
            "revenue_protected": revenue_protected,
            "total_economic_benefit": total_economic_benefit,
            "roi_multiplier": roi_multiplier,
            "inputs": {
                "staff_hourly_wage": staff_hourly_wage,
                "avg_visit_value": avg_visit_value,
                "period_days": period_days,
                "period_weeks": period_weeks
            },
            "breakdown": {
                "inbound_calls_count": total_calls,
                "inbound_hours_saved": round(minutes_inbound / 60.0, 1),
                "confirmations_count": max(confirmations_count, confirmed_count),
                "confirmations_hours_saved": round(minutes_confirmations / 60.0, 1),
                "outreach_hours_saved": round(minutes_recalls / 60.0, 1)
            }
        }

    async def get_scheduling_suggestions(self, clinic_id: str) -> Dict[str, Any]:
        """
        Generates dynamic slot recommendations and returns executive operations insights.
        """
        # Fetch latest AI summary
        insights_res = supabase_read.table("ai_insights").select("summary, created_at") \
            .eq("clinic_id", clinic_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        now = datetime.datetime.now(datetime.timezone.utc)
        thirty_days_ago = (now - datetime.timedelta(days=30)).isoformat()

        # Call load analysis
        calls_res = supabase_read.table("calls").select("started_at, status") \
            .eq("clinic_id", clinic_id) \
            .gte("started_at", thirty_days_ago) \
            .execute()

        calls = calls_res.data or []
        missed_counts: Dict[str, int] = {}
        for c in calls:
            if c.get("status") != "completed" and c.get("started_at"):
                try:
                    dt = datetime.datetime.fromisoformat(c["started_at"].replace("Z", "+00:00"))
                    day = dt.strftime("%A")
                    hour = dt.strftime("%I %p").lstrip('0')
                    key = f"{day} {hour}"
                    missed_counts[key] = missed_counts.get(key, 0) + 1
                except Exception:
                    pass

        sorted_missed = sorted(missed_counts.items(), key=lambda x: x[1], reverse=True)

        recommendations = [
            {
                "id": "rec_no_shows",
                "type": "retention",
                "title": "Automated SMS Confirmations",
                "description": "Enabling CALL-E multi-touch 24h & 2h appointment confirmations reduces clinic no-show rates by up to 34%.",
                "action_label": "Configure Reminders",
                "action_payload": {"tab": "notifications"}
            },
            {
                "id": "rec_peak_booking",
                "type": "opportunity",
                "title": "High Patient Demand Slot",
                "description": "Patient call volume peaks between 10am - 12pm on weekdays. Expanding clinician calendar capacity during these windows maximizes billable hours.",
                "action_label": "Optimize Capacity",
                "action_payload": {"tab": "hours", "day": "fri"}
            }
        ]

        if sorted_missed:
            peak_day_hour = sorted_missed[0][0]
            recommendations.insert(0, {
                "id": "rec_peak_demand",
                "type": "opportunity",
                "title": f"High Demand on {peak_day_hour.split()[0]}s",
                "description": f"Detected {sorted_missed[0][1]} missed call inquiries around {peak_day_hour.split()[1]} in the last 30 days. Enable autonomous routing to capture this pipeline.",
                "action_label": "Optimize Slot",
                "action_payload": {"tab": "hours", "day": peak_day_hour.split()[0].lower()[:3]}
            })

        latest_summary = insights_res.data[0]["summary"] if insights_res.data else None

        return {
            "recommendations": recommendations,
            "latest_ai_insights": latest_summary
        }

    async def get_competitor_benchmarks(self, clinic_id: str) -> Dict[str, Any]:
        """
        Provides HIPAA-compliant, aggregate competitor benchmarking across specialty clinics.
        """
        clinic_res = supabase_read.table("clinics").select("benchmark_opt_in, specialty").eq("id", clinic_id).single().execute()
        if not clinic_res.data:
            clinic_info = {"benchmark_opt_in": True, "specialty": "General Practice"}
        else:
            clinic_info = clinic_res.data

        opt_in = clinic_info.get("benchmark_opt_in", True)
        specialty = clinic_info.get("specialty") or "General Practice"

        now = datetime.datetime.now(datetime.timezone.utc)
        thirty_days_ago = (now - datetime.timedelta(days=30)).isoformat()

        # Clinic call volume
        c_calls = supabase_read.table("calls").select("id").eq("clinic_id", clinic_id).gte("started_at", thirty_days_ago).execute()
        clinic_call_volume = len(c_calls.data or [])

        # Clinic no-show rate
        c_appts = supabase_read.table("appointments").select("status").eq("clinic_id", clinic_id).gte("datetime", thirty_days_ago).execute()
        appts_data = c_appts.data or []
        clinic_total = len(appts_data)
        clinic_noshows = sum(1 for a in appts_data if a.get("status") == "no_show")
        clinic_no_show_rate = round((clinic_noshows / max(1, clinic_total)) * 100, 1) if clinic_total > 0 else 0.0
        # Compute real peer specialty averages across all clinics in this specialty
        peer_call_avg = 48.0
        peer_noshow_avg = 18.0
        try:
            peer_clinics = supabase_read.table("clinics").select("id").eq("specialty", specialty).execute()
            peer_ids = [c["id"] for c in (peer_clinics.data or []) if c.get("id")]
            if len(peer_ids) > 1:
                peer_calls_res = supabase_read.table("calls").select("id").in_("clinic_id", peer_ids).gte("started_at", thirty_days_ago).execute()
                peer_call_avg = round(len(peer_calls_res.data or []) / max(1, len(peer_ids)), 1)
                
                peer_appts_res = supabase_read.table("appointments").select("status").in_("clinic_id", peer_ids).gte("datetime", thirty_days_ago).execute()
                peer_appts = peer_appts_res.data or []
                if peer_appts:
                    peer_ns = sum(1 for a in peer_appts if a.get("status") == "no_show")
                    peer_noshow_avg = round((peer_ns / len(peer_appts)) * 100, 1)
        except Exception:
            pass

        return {
            "benchmark_opt_in": bool(opt_in),
            "clinic_call_volume": clinic_call_volume,
            "clinic_no_show_rate": clinic_no_show_rate,
            "specialty_call_volume_avg": peer_call_avg,
            "specialty_no_show_rate_avg": peer_noshow_avg,
            "specialty": specialty
        }


    async def generate_csv_export(
        self,
        clinic_id: str,
        report_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = "clinician",
        request: Optional[Any] = None
    ) -> str:
        """
        Generates CSV report string with HIPAA audit logging and role-based PHI masking.
        """
        start_dt, end_dt, _, _, _ = self.parse_date_range(preset, start_date, end_date)
        clean_type = report_type.lower().replace("-", "_")
        is_privileged = (user_role or "clinician").lower() in ["owner", "clinician", "admin"]

        def _mask_name(val):
            if is_privileged or not val:
                return val
            parts = str(val).split(" ")
            return " ".join([f"{p[0]}***" if len(p) > 1 else p for p in parts if p])

        def _mask_phone(val):
            if is_privileged or not val:
                return val
            digits = "".join(filter(str.isdigit, str(val)))
            return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "****"

        def _mask_email(val):
            if is_privileged or not val or "@" not in str(val):
                return val
            n, d = str(val).split("@", 1)
            return f"{n[0]}***@{d}"

        output = io.StringIO()
        writer = csv.writer(output)

        if clean_type in ("revenue", "financials"):
            writer.writerow(["Date/Time (UTC)", "Amount ($)", "Event Type", "Clinic ID"])
            res = supabase_read.table("revenue_events").select("created_at, amount_cents, event_type") \
                .eq("clinic_id", clinic_id) \
                .gte("created_at", start_dt.isoformat()) \
                .lte("created_at", end_dt.isoformat()) \
                .execute()
            for row in (res.data or []):
                amt = round((row.get("amount_cents") or 0) / 100, 2)
                writer.writerow([row.get("created_at"), amt, row.get("event_type"), clinic_id])

        elif clean_type in ("calls", "heatmap"):
            writer.writerow(["Call ID", "Direction", "Status", "Outcome", "Call Type", "Started At", "Duration (sec)"])
            res = supabase_read.table("calls").select("id, direction, status, outcome, call_type, started_at, duration_seconds") \
                .eq("clinic_id", clinic_id) \
                .gte("started_at", start_dt.isoformat()) \
                .lte("started_at", end_dt.isoformat()) \
                .execute()
            for row in (res.data or []):
                writer.writerow([
                    row.get("id"), row.get("direction"), row.get("status"),
                    row.get("outcome"), row.get("call_type"), row.get("started_at"),
                    row.get("duration_seconds")
                ])

        elif clean_type in ("patients", "vips"):
            writer.writerow(["Patient ID", "Name", "Email", "Phone", "Created At", "Total Revenue ($)", "VIP Status", "Churn Risk Score"])
            res = supabase_read.table("patients").select("id, name, email, phone, created_at, total_revenue_generated, is_vip, churn_risk_score") \
                .eq("clinic_id", clinic_id) \
                .execute()
            for row in (res.data or []):
                writer.writerow([
                    row.get("id"), _mask_name(row.get("name")), _mask_email(row.get("email")), _mask_phone(row.get("phone")),
                    row.get("created_at"), row.get("total_revenue_generated"),
                    "Yes" if row.get("is_vip") else "No", row.get("churn_risk_score")
                ])

        elif clean_type in ("no_shows", "noshows", "appointments"):
            writer.writerow(["Appointment ID", "Patient Name", "Status", "Appointment Time", "Confirmed At", "Reminder Sent"])
            res = supabase_read.table("appointments").select("id, patient_name, status, datetime, confirmed_at, reminder_sent") \
                .eq("clinic_id", clinic_id) \
                .gte("datetime", start_dt.isoformat()) \
                .lte("datetime", end_dt.isoformat()) \
                .execute()
            for row in (res.data or []):
                writer.writerow([
                    row.get("id"), _mask_name(row.get("patient_name")), row.get("status"),
                    row.get("datetime"), row.get("confirmed_at"), row.get("reminder_sent")
                ])


        elif clean_type in ("campaigns", "recalls"):
            writer.writerow(["Call ID", "Campaign Type", "Status", "Task Completed", "Completion Score", "Created At"])
            res = supabase_read.table("outbound_calls").select("id, campaign_type, status, task_completed, completion_score, created_at") \
                .eq("clinic_id", clinic_id) \
                .gte("created_at", start_dt.isoformat()) \
                .lte("created_at", end_dt.isoformat()) \
                .execute()
            for row in (res.data or []):
                writer.writerow([
                    row.get("id"), row.get("campaign_type"), row.get("status"),
                    row.get("task_completed"), row.get("completion_score"), row.get("created_at")
                ])

        elif clean_type in ("roi", "savings"):
            roi_data = await self.get_roi_kpis(clinic_id, start_dt.isoformat(), end_dt.isoformat())
            writer.writerow(["Staff Hours & Economic ROI Report"])
            writer.writerow(["Date Range", f"{start_dt.isoformat()} to {end_dt.isoformat()}"])
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Staff Hours Saved Total", roi_data.get("staff_hours_saved_total")])
            writer.writerow(["Staff Hours Saved / Week", roi_data.get("staff_hours_saved_per_week")])
            writer.writerow(["Staff Wage Cost Saved ($)", f"${roi_data.get('staff_cost_saved')}"])
            writer.writerow(["Revenue Protected ($)", f"${roi_data.get('revenue_protected')}"])
            writer.writerow(["Total Economic Value ($)", f"${roi_data.get('total_economic_benefit')}"])
            writer.writerow(["ROI Multiplier", f"{roi_data.get('roi_multiplier')}x"])

        else:  # Executive KPI Summary
            writer.writerow(["Bytelytic Practice Intelligence KPI Summary Report"])
            writer.writerow(["Generated At", datetime.datetime.now(datetime.timezone.utc).isoformat()])
            writer.writerow(["Date Range", f"{start_dt.isoformat()} to {end_dt.isoformat()}"])
            writer.writerow([])
            writer.writerow(["Metric", "Value"])
            
            calls_data = await self.get_calls_analytics(clinic_id, start_dt.isoformat(), end_dt.isoformat())
            noshow_data = await self.get_noshow_analytics(clinic_id, start_dt.isoformat(), end_dt.isoformat())
            rev_data = await self.get_revenue_analytics(clinic_id, start_dt.isoformat(), end_dt.isoformat())
            roi_data = await self.get_roi_kpis(clinic_id, start_dt.isoformat(), end_dt.isoformat())

            writer.writerow(["Total Calls In Period", calls_data.get("total_calls")])
            writer.writerow(["Calls Handled", calls_data.get("handled_calls")])
            writer.writerow(["Answer Rate (%)", f"{calls_data.get('answer_rate')}%"])
            writer.writerow(["No-Show Rate (%)", f"{noshow_data.get('no_show_rate')}%"])
            writer.writerow(["No-Show Reduction Rate (%)", f"{noshow_data.get('no_show_reduction_rate')}%"])
            writer.writerow(["Total Period Revenue ($)", f"${rev_data.get('total_period_revenue')}"])
            writer.writerow(["Staff Hours Saved / Week", f"{roi_data.get('staff_hours_saved_per_week')} hrs"])
            writer.writerow(["Total Economic Value Generated ($)", f"${roi_data.get('total_economic_benefit')}"])

        # HIPAA Audit Log entry
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=user_id,
            user_email=user_email,
            action="analytics:exported_csv",
            resource_type="analytics_reports",
            resource_id=clean_type,
            details={
                "report_type": clean_type,
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
            },
            request=request
        )

        return output.getvalue()


analytics_service = AnalyticsService()
