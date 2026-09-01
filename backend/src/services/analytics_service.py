import datetime
import io
import csv
import uuid
from typing import Optional, Dict, Any, List, Tuple
from zoneinfo import ZoneInfo
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
        Seamlessly aggregates both clinical appointments (revenue_amount) and revenue_events.
        """
        start_dt, end_dt, _, _, period_days = self.parse_date_range(preset, start_date, end_date)

        # 1. Fetch clinic profile default visit revenue
        try:
            clinic_res = supabase_read.table("clinics").select("monthly_revenue_per_visit").eq("id", clinic_id).single().execute()
            default_visit_val = float(clinic_res.data.get("monthly_revenue_per_visit") or 150.0) if clinic_res.data else 150.0
        except Exception:
            default_visit_val = 150.0

        # 2. Fetch revenue events
        twelve_months_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).isoformat()
        try:
            rev_res = supabase_read.table("revenue_events").select("id, amount_cents, created_at, event_type, appointment_id") \
                .eq("clinic_id", clinic_id) \
                .gte("created_at", twelve_months_ago) \
                .execute()
            events = rev_res.data or []
        except Exception:
            events = []

        # 3. Fetch appointments
        try:
            appts_res = supabase_read.table("appointments").select(
                "id, patient_name, appointment_type, datetime, status, revenue_amount, booked_by, reminder_sent, confirmed_at, created_at"
            ).eq("clinic_id", clinic_id).execute()
            appts = appts_res.data or []
        except Exception:
            appts = []

        event_appt_ids = set(str(ev["appointment_id"]) for ev in events if ev.get("appointment_id"))

        # 4. Pre-populate chronological last 12 calendar months with 0s
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

        # Populate trajectory from revenue_events
        for ev in events:
            if ev.get("created_at"):
                try:
                    dt = datetime.datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00"))
                    key = dt.strftime("%b %Y")
                    amt = round((ev.get("amount_cents") or 0) / 100)
                    if key in monthly_rev:
                        monthly_rev[key]["revenue"] += amt
                        monthly_rev[key]["bookings"] += 1
                except Exception:
                    pass

        # Populate trajectory from appointments (excluding any already captured in revenue_events)
        for a in appts:
            if str(a.get("id")) in event_appt_ids:
                continue
            status = a.get("status")
            if status in ("completed", "confirmed", "scheduled"):
                target_dt_str = a.get("datetime") or a.get("created_at")
                if target_dt_str:
                    try:
                        dt = datetime.datetime.fromisoformat(target_dt_str.replace("Z", "+00:00"))
                        key = dt.strftime("%b %Y")
                        amt = round(float(a.get("revenue_amount") if a.get("revenue_amount") is not None else default_visit_val))
                        if key in monthly_rev:
                            monthly_rev[key]["revenue"] += amt
                            monthly_rev[key]["bookings"] += 1
                    except Exception:
                        pass

        sorted_months = []
        for month_date, month_str in reversed(month_keys):
            stats = monthly_rev.get(month_str, {"revenue": 0, "bookings": 0})
            sorted_months.append({
                "month": month_str,
                "revenue": stats["revenue"],
                "bookings": stats["bookings"]
            })

        # 5. Period Aggregation and Workflow Category Breakdown
        breakdown_map: Dict[str, Dict[str, Any]] = {}
        total_period_revenue = 0
        realized_revenue = 0
        confirmed_revenue = 0
        pipeline_revenue = 0
        recovered_revenue = 0
        total_bookings_count = 0

        # Aggregate period revenue events
        for ev in events:
            c_at = ev.get("created_at")
            if c_at:
                try:
                    dt = datetime.datetime.fromisoformat(c_at.replace("Z", "+00:00"))
                    if start_dt <= dt <= end_dt:
                        e_type = ev.get("event_type") or "automated_booking"
                        amt = round((ev.get("amount_cents") or 0) / 100)
                        cat = e_type.replace("_", " ").title()
                        if cat not in breakdown_map:
                            breakdown_map[cat] = {"type": cat, "value": 0, "raw_type": e_type}
                        breakdown_map[cat]["value"] += amt
                        total_period_revenue += amt
                        total_bookings_count += 1
                        recovered_revenue += amt
                except Exception:
                    pass

        # Aggregate period appointments
        for a in appts:
            if str(a.get("id")) in event_appt_ids:
                continue
            status = a.get("status")
            if status in ("completed", "confirmed", "scheduled"):
                target_dt_str = a.get("datetime") or a.get("created_at")
                if target_dt_str:
                    try:
                        dt = datetime.datetime.fromisoformat(target_dt_str.replace("Z", "+00:00"))
                        if start_dt <= dt <= end_dt:
                            amt = round(float(a.get("revenue_amount") if a.get("revenue_amount") is not None else default_visit_val))
                            cat = (a.get("appointment_type") or "General Consultation").replace("_", " ").title()
                            if cat not in breakdown_map:
                                breakdown_map[cat] = {"type": cat, "value": 0, "raw_type": a.get("appointment_type") or "general"}
                            breakdown_map[cat]["value"] += amt
                            total_period_revenue += amt
                            total_bookings_count += 1
                            if status == "completed":
                                realized_revenue += amt
                            elif status == "confirmed":
                                confirmed_revenue += amt
                            elif status == "scheduled":
                                pipeline_revenue += amt
                            
                            is_ai_recovered = (a.get("booked_by") == "ai" or a.get("reminder_sent") or a.get("confirmed_at"))
                            if is_ai_recovered:
                                recovered_revenue += amt
                    except Exception:
                        pass

        formatted_breakdown = sorted(breakdown_map.values(), key=lambda x: x["value"], reverse=True)
        projected_annual = round((total_period_revenue / max(1, period_days)) * 365)
        mrr = round((total_period_revenue / max(1, period_days)) * 30)
        avg_booking_value = round(total_period_revenue / max(1, total_bookings_count)) if total_bookings_count > 0 else round(default_visit_val)

        return {
            "trend": sorted_months,
            "breakdown": formatted_breakdown,
            "total_period_revenue": total_period_revenue,
            "projected_annual_savings": projected_annual,
            "mrr": mrr,
            "recovered_revenue": recovered_revenue,
            "avg_booking_value": avg_booking_value,
            "total_bookings_count": total_bookings_count,
            "realized_revenue": realized_revenue,
            "confirmed_revenue": confirmed_revenue,
            "pipeline_revenue": pipeline_revenue,
            "period_days": period_days,
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat()
        }

    # Alias for router/service compatibility
    get_revenue_metrics = get_revenue_analytics

    async def get_clinic_timezone(self, clinic_id: str) -> str:
        """Fetches clinic's configured timezone or defaults to America/New_York."""
        try:
            res = supabase_read.table("clinics").select("timezone").eq("id", clinic_id).maybe_single().execute()
            if res.data and isinstance(res.data, dict) and res.data.get("timezone"):
                return res.data["timezone"].strip()
        except Exception:
            pass
        return "America/New_York"

    async def get_call_density_heatmap(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Builds the 7-day x 24-hour call density heatmap matrix and peak hours distribution,
        correctly mapped to the clinic's local timezone.
        """
        start_dt, end_dt, _, _, period_days = self.parse_date_range(preset, start_date, end_date)
        clinic_tz_name = await self.get_clinic_timezone(clinic_id)
        try:
            tz = ZoneInfo(clinic_tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        # Fetch calls in buffer range using created_at (which is non-null for all calls)
        buffer_start = (start_dt - datetime.timedelta(days=1)).isoformat()
        buffer_end = (end_dt + datetime.timedelta(days=1)).isoformat()

        calls_res = supabase_read.table("calls").select(
            "id, status, outcome, direction, call_type, started_at, created_at, duration_seconds"
        ).eq("clinic_id", clinic_id).gte("created_at", buffer_start).lte("created_at", buffer_end).execute()

        raw_calls = calls_res.data or []

        # Days of week (Mon-Sun)
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        # All 24 hours of the day
        hours = [
            '12am', '1am', '2am', '3am', '4am', '5am', '6am', '7am', '8am', '9am', '10am', '11am',
            '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm', '9pm', '10pm', '11pm'
        ]

        heatmap_grid: Dict[str, Dict[str, Dict[str, int]]] = {
            day: {h: {"handled": 0, "missed": 0, "total": 0} for h in hours}
            for day in days
        }

        hourly_totals: Dict[str, Dict[str, Any]] = {
            h: {"hour": h, "handled": 0, "missed": 0, "total": 0}
            for h in hours
        }

        day_totals: Dict[str, Dict[str, Any]] = {
            d: {"day": d, "handled": 0, "missed": 0, "total": 0}
            for d in days
        }

        filtered_calls = []
        handled_calls = 0
        missed_calls = 0

        for c in raw_calls:
            ts_str = c.get("started_at") or c.get("created_at")
            if not ts_str:
                continue
            try:
                clean_ts = ts_str.replace("Z", "+00:00")
                utc_dt = datetime.datetime.fromisoformat(clean_ts)
                if utc_dt.tzinfo is None:
                    utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                continue

            # Strict bounds check in UTC
            if not (start_dt <= utc_dt <= end_dt):
                continue

            filtered_calls.append(c)

            # Determine handled vs missed
            st = str(c.get("status") or "").lower()
            outc = str(c.get("outcome") or "").lower()
            is_handled = (st in ("completed", "ended") and outc not in ("no_answer", "missed", "failed", "busy", "abandoned")) or (outc in ("booked", "completed", "rescheduled", "confirmed", "attended"))

            if is_handled:
                handled_calls += 1
            else:
                missed_calls += 1

            # Convert to clinic local timezone
            local_dt = utc_dt.astimezone(tz)
            day_name = days[local_dt.weekday()]
            hour_str = local_dt.strftime("%I%p").lower().lstrip("0") or "12am"

            if day_name in heatmap_grid and hour_str in heatmap_grid[day_name]:
                if is_handled:
                    heatmap_grid[day_name][hour_str]["handled"] += 1
                    hourly_totals[hour_str]["handled"] += 1
                    day_totals[day_name]["handled"] += 1
                else:
                    heatmap_grid[day_name][hour_str]["missed"] += 1
                    hourly_totals[hour_str]["missed"] += 1
                    day_totals[day_name]["missed"] += 1

                heatmap_grid[day_name][hour_str]["total"] += 1
                hourly_totals[hour_str]["total"] += 1
                day_totals[day_name]["total"] += 1

        total_calls = len(filtered_calls)

        return {
            "heatmap": heatmap_grid,
            "peak_hours_distribution": list(hourly_totals.values()),
            "day_distribution": list(day_totals.values()),
            "timezone": clinic_tz_name,
            "total_calls": total_calls,
            "handled_calls": handled_calls,
            "missed_calls": missed_calls,
            "period_days": period_days,
            "_filtered_calls": filtered_calls
        }

    async def get_calls_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Aggregates inbound/outbound call load, 7-day x 24-hour heatmap density matrix, peak hours distribution,
        MoM call volume velocity, and booking conversion rates with clinic timezone localization.
        """
        start_dt, end_dt, prev_start_dt, prev_end_dt, period_days = self.parse_date_range(preset, start_date, end_date)

        heatmap_res = await self.get_call_density_heatmap(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )

        calls = heatmap_res.get("_filtered_calls", [])
        total_calls = heatmap_res.get("total_calls", 0)
        handled_calls = heatmap_res.get("handled_calls", 0)
        missed_calls = heatmap_res.get("missed_calls", 0)

        total_duration_sec = sum(int(c.get("duration_seconds") or 0) for c in calls)
        avg_duration_sec = round(total_duration_sec / max(1, total_calls))

        # Inbound conversion rate (appointments booked via inbound calls)
        inbound_calls = [c for c in calls if c.get("direction") == "inbound" or not c.get("direction")]
        inbound_count = len(inbound_calls)
        booked_calls = sum(
            1 for c in inbound_calls 
            if any(term in str(c.get("outcome", "")).lower() for term in ["scheduled", "booked", "confirmed", "appointment"])
        )
        conversion_rate = min(100.0, round((booked_calls / max(1, inbound_count)) * 100, 1)) if inbound_count > 0 else 0.0

        # Calculate period-over-period change (MoM)
        prev_buffer_start = (prev_start_dt - datetime.timedelta(days=1)).isoformat()
        prev_buffer_end = (prev_end_dt + datetime.timedelta(days=1)).isoformat()
        prev_calls_res = supabase_read.table("calls").select("id, started_at, created_at") \
            .eq("clinic_id", clinic_id) \
            .gte("created_at", prev_buffer_start) \
            .lte("created_at", prev_buffer_end) \
            .execute()
        
        prev_raw = prev_calls_res.data or []
        prev_calls_count = 0
        for pc in prev_raw:
            ts_str = pc.get("started_at") or pc.get("created_at")
            if not ts_str:
                continue
            try:
                clean_ts = ts_str.replace("Z", "+00:00")
                p_dt = datetime.datetime.fromisoformat(clean_ts)
                if p_dt.tzinfo is None:
                    p_dt = p_dt.replace(tzinfo=datetime.timezone.utc)
                if prev_start_dt <= p_dt < prev_end_dt:
                    prev_calls_count += 1
            except Exception:
                pass

        if prev_calls_count > 0:
            mom_change = round(((total_calls - prev_calls_count) / prev_calls_count) * 100, 1)
        else:
            mom_change = 0.0

        answer_rate = round((handled_calls / max(1, total_calls)) * 100, 1) if total_calls > 0 else 100.0

        return {
            "heatmap": heatmap_res.get("heatmap", {}),
            "peak_hours_distribution": heatmap_res.get("peak_hours_distribution", []),
            "day_distribution": heatmap_res.get("day_distribution", []),
            "timezone": heatmap_res.get("timezone", "UTC"),
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

    # Compatibility aliases
    get_peak_hours_distribution = get_call_density_heatmap
    get_call_metrics = get_calls_analytics

    def _mask_phi_patient(self, patient: Dict[str, Any], is_privileged: bool) -> Dict[str, Any]:
        """
        Masks patient PHI (name, phone, email) if user role is not privileged.
        Privileged roles: owner, clinician, admin.
        """
        if is_privileged:
            return patient
        
        masked = dict(patient)
        name = patient.get("name")
        if name:
            parts = str(name).split(" ")
            masked["name"] = " ".join([f"{p[0]}***" if len(p) > 1 else p for p in parts if p])
        
        phone = patient.get("phone")
        if phone:
            digits = "".join(filter(str.isdigit, str(phone)))
            masked["phone"] = f"***-***-{digits[-4:]}" if len(digits) >= 4 else "****"
            
        email = patient.get("email")
        if email and "@" in str(email):
            n, d = str(email).split("@", 1)
            masked["email"] = f"{n[0]}***@{d}" if len(n) > 0 else f"***@{d}"
            
        return masked

    async def get_patients_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None,
        user_role: Optional[str] = "clinician"
    ) -> Dict[str, Any]:
        """
        Calculates patient demographics, new vs returning ratio, average LTV, VIP leaderboard,
        and high churn-risk watchlist with role-based PHI masking.
        """
        start_dt, end_dt, _, _, _ = self.parse_date_range(preset, start_date, end_date)
        is_privileged = (user_role or "clinician").lower() in ["owner", "clinician", "admin"]

        # 1. Fetch patients with lifetime stats
        patients_res = supabase_read.table("patients").select(
            "id, name, email, phone, created_at, is_vip, churn_risk_score, total_revenue_generated, average_visit_value, total_visits, last_visit_date, no_show_count"
        ).eq("clinic_id", clinic_id).execute()

        patients = patients_res.data or []
        total_patients = len(patients)

        # 2. Fetch completed appointments in selected date range
        appts_res = supabase_read.table("appointments").select("patient_id, status, datetime, revenue_amount") \
            .eq("clinic_id", clinic_id) \
            .eq("status", "completed") \
            .gte("datetime", start_dt.isoformat()) \
            .lte("datetime", end_dt.isoformat()) \
            .execute()

        appts = appts_res.data or []
        active_patient_ids = set(a["patient_id"] for a in appts if a.get("patient_id"))

        # Build map of appointment revenue per patient
        appt_rev_map: Dict[str, float] = {}
        for a in appts:
            pid = a.get("patient_id")
            if pid:
                appt_rev_map[pid] = appt_rev_map.get(pid, 0.0) + float(a.get("revenue_amount") or 0.0)

        # Calculate new vs returning patients
        new_count = 0
        returning_count = 0
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()

        total_revenue_acc = 0.0
        processed_patients = []
        today = datetime.datetime.now(datetime.timezone.utc).date()

        for p in patients:
            pid = p.get("id")
            p_created = p.get("created_at")
            
            # Base lifetime revenue from patient record, supplemented by completed appointment revenue if zero
            stored_rev = float(p.get("total_revenue_generated") or 0.0)
            completed_appt_rev = appt_rev_map.get(pid, 0.0)
            p_rev = stored_rev if stored_rev > 0 else completed_appt_rev
            total_revenue_acc += p_rev

            p_copy = dict(p)
            p_copy["total_revenue_generated"] = p_rev

            if p_created and start_iso <= p_created <= end_iso:
                new_count += 1
            elif pid in active_patient_ids:
                returning_count += 1

            # Dynamic Churn Risk calculation if stored score is 0.0 or missing
            current_churn = float(p.get("churn_risk_score") or 0.0)
            if current_churn <= 0.0 and p.get("last_visit_date"):
                try:
                    last_v_date = datetime.date.fromisoformat(str(p["last_visit_date"]))
                    days_since = (today - last_v_date).days
                    v_count = int(p.get("total_visits") or 1)
                    
                    if v_count >= 5 and days_since >= 90:
                        current_churn = min(1.0, 0.65 + (days_since - 90) / 100.0)
                    elif v_count >= 2 and days_since >= 60:
                        current_churn = min(1.0, 0.40 + (days_since - 60) / 120.0)
                    elif days_since >= 180:
                        current_churn = min(1.0, days_since / 365.0)
                except Exception:
                    pass
            
            # Elevate churn risk if no-show history is high
            if int(p.get("no_show_count") or 0) >= 2:
                current_churn = max(current_churn, 0.60)

            p_copy["churn_risk_score"] = float(round(max(0.0, min(1.0, current_churn)), 2))
            processed_patients.append(p_copy)

        avg_ltv = round(total_revenue_acc / max(1, total_patients), 2) if total_patients > 0 else 0.0

        # Top VIP list: patients marked as VIP or with revenue > 300, sorted descending
        vips = [p for p in processed_patients if p.get("is_vip") or float(p.get("total_revenue_generated") or 0.0) > 300.0]
        if not vips:
            vips = [p for p in processed_patients if float(p.get("total_revenue_generated") or 0.0) > 0]
        vips_sorted = sorted(vips, key=lambda x: float(x.get("total_revenue_generated") or 0.0), reverse=True)[:10]

        # Churn risk patients (churn_risk_score >= 0.40)
        churn_risk_patients = [p for p in processed_patients if float(p.get("churn_risk_score") or 0.0) >= 0.40]
        churn_sorted = sorted(churn_risk_patients, key=lambda x: float(x.get("churn_risk_score") or 0.0), reverse=True)[:10]

        # Apply PHI masking
        masked_vips = [self._mask_phi_patient(p, is_privileged) for p in vips_sorted]
        masked_churn = [self._mask_phi_patient(p, is_privileged) for p in churn_sorted]

        return {
            "ratio": [
                {"name": "New Patients", "value": new_count},
                {"name": "Returning Patients", "value": returning_count}
            ],
            "vip_list": masked_vips,
            "churn_risk_list": masked_churn,
            "total_patients": total_patients,
            "new_patients_count": new_count,
            "returning_patients_count": returning_count,
            "average_ltv": avg_ltv
        }

    async def get_vip_patients(
        self,
        clinic_id: str,
        limit: int = 10,
        user_role: Optional[str] = "clinician"
    ) -> List[Dict[str, Any]]:
        """
        Returns VIP patient leaderboard with lifetime value, visits, and role-based PHI masking.
        """
        data = await self.get_patients_analytics(clinic_id=clinic_id, user_role=user_role)
        vip_list = data.get("vip_list", [])
        return vip_list[:limit]

    async def calculate_retention_cohorts(
        self,
        clinic_id: str,
        preset: Optional[Any] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_role: Optional[str] = "clinician"
    ) -> Dict[str, Any]:
        """
        Calculates patient retention cohorts, new vs returning ratio, average LTV,
        and high churn-risk watchlist.
        """
        return await self.get_patients_analytics(
            clinic_id=clinic_id,
            preset=preset,
            start_date=start_date,
            end_date=end_date,
            user_role=user_role
        )

    async def calculate_ltv(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates patient lifetime value (LTV), cohort distributions, VIP leaderboard,
        and high churn-risk revenue exposure.
        """
        pat_data = await self.get_patients_analytics(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset
        )
        
        # Calculate total lifetime revenue & tiers from live patient database
        try:
            patients_res = supabase_read.table("patients").select(
                "id, name, total_revenue_generated, total_visits, is_vip, churn_risk_score"
            ).eq("clinic_id", clinic_id).execute()
            patients = patients_res.data or []
        except Exception:
            patients = []

        total_lifetime_rev = sum(float(p.get("total_revenue_generated") or 0.0) for p in patients)
        
        tiers = {"under_200": 0, "200_to_400": 0, "400_to_600": 0, "vip_600_plus": 0}
        for p in patients:
            rev = float(p.get("total_revenue_generated") or 0.0)
            if rev < 200:
                tiers["under_200"] += 1
            elif rev < 400:
                tiers["200_to_400"] += 1
            elif rev < 600:
                tiers["400_to_600"] += 1
            else:
                tiers["vip_600_plus"] += 1

        return {
            **pat_data,
            "total_lifetime_revenue": round(total_lifetime_rev, 2),
            "tiers": tiers
        }

    async def get_overview_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Consolidates core executive KPIs: Revenue, MRR, AI Recovered Value, LTV, Calls, and Show Rate.
        """
        rev = await self.get_revenue_analytics(clinic_id=clinic_id, start_date=start_date, end_date=end_date, preset=preset)
        pat = await self.get_patients_analytics(clinic_id=clinic_id, start_date=start_date, end_date=end_date, preset=preset)
        calls = await self.get_calls_analytics(clinic_id=clinic_id, start_date=start_date, end_date=end_date, preset=preset)
        noshow = await self.get_noshow_analytics(clinic_id=clinic_id, start_date=start_date, end_date=end_date, preset=preset)
        roi = await self.get_roi_kpis(clinic_id=clinic_id, start_date=start_date, end_date=end_date, preset=preset)

        return {
            "total_period_revenue": rev.get("total_period_revenue", 0),
            "mrr": rev.get("mrr", 0),
            "annual_run_rate": rev.get("projected_annual_savings", 0),
            "recovered_revenue": rev.get("recovered_revenue", 0),
            "avg_booking_value": rev.get("avg_booking_value", 150),
            "total_bookings_count": rev.get("total_bookings_count", 0),
            "average_ltv": pat.get("average_ltv", 0.0),
            "total_patients": pat.get("total_patients", 0),
            "total_calls": calls.get("total_calls", 0),
            "answer_rate": calls.get("answer_rate", 100.0),
            "inbound_conversion_rate": calls.get("inbound_conversion_rate", 0.0),
            "show_rate": noshow.get("show_rate", 100.0),
            "no_show_rate": noshow.get("no_show_rate", 0.0),
            "staff_hours_saved_total": roi.get("staff_hours_saved_total", 0.0),
            "staff_cost_saved": roi.get("staff_cost_saved", 0.0),
            "roi_multiplier": roi.get("roi_multiplier", 1.0)
        }

    async def get_noshow_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates clinic no-show rates, mathematically sound Show Rate % = (Completed / (Completed + No-Shows)) * 100,
        no-show reduction rate (% change vs previous period and vs benchmark),
        confirmed vs unconfirmed show rates, lost revenue, CALL-E 2-hour no-show campaign recovery stats,
        daily trend data, and repeat offenders watchlist.
        """
        start_dt, end_dt, prev_start_dt, prev_end_dt, period_days = self.parse_date_range(preset, start_date, end_date)

        # Average visit value from clinic profile
        try:
            clinic_res = supabase_read.table("clinics").select("monthly_revenue_per_visit").eq("id", clinic_id).single().execute()
            avg_visit_val = float(clinic_res.data.get("monthly_revenue_per_visit") or 150.0) if clinic_res.data else 150.0
        except Exception:
            avg_visit_val = 150.0

        # 1. Current period appointments
        appts_res = supabase_read.table("appointments").select(
            "id, status, datetime, patient_name, patient_phone, confirmed_at, reminder_sent, revenue_amount"
        ).eq("clinic_id", clinic_id) \
         .gte("datetime", start_dt.isoformat()) \
         .lte("datetime", end_dt.isoformat()) \
         .execute()

        appts = appts_res.data or []
        total_appts = len(appts)

        # Concluded appointments: completed/attended/confirmed vs no_show
        # Note: scheduled appointments are upcoming/pending and not yet concluded
        completed_count = sum(1 for a in appts if a.get("status") in ("completed", "attended", "confirmed"))
        no_show_count = sum(1 for a in appts if a.get("status") == "no_show")
        scheduled_count = sum(1 for a in appts if a.get("status") == "scheduled")
        concluded_appts = completed_count + no_show_count

        # Show Rate % = (Completed / (Completed + No-Shows)) * 100
        if concluded_appts > 0:
            show_rate = round((completed_count / concluded_appts) * 100, 1)
            no_show_rate = round((no_show_count / concluded_appts) * 100, 1)
        else:
            show_rate = 100.0 if total_appts > 0 else 0.0
            no_show_rate = 0.0

        # Lost revenue: calculated from specific appointment revenue_amount or clinic avg visit value
        lost_revenue = sum(
            float(a.get("revenue_amount") or avg_visit_val)
            for a in appts
            if a.get("status") == "no_show"
        )
        lost_revenue = round(lost_revenue, 2)

        # 2. Previous period appointments for No-Show Reduction Rate calculation
        prev_appts_res = supabase_read.table("appointments").select("status") \
            .eq("clinic_id", clinic_id) \
            .gte("datetime", prev_start_dt.isoformat()) \
            .lt("datetime", prev_end_dt.isoformat()) \
            .execute()

        prev_appts = prev_appts_res.data or []
        prev_completed = sum(1 for a in prev_appts if a.get("status") in ("completed", "attended", "confirmed"))
        prev_noshows = sum(1 for a in prev_appts if a.get("status") == "no_show")
        prev_concluded = prev_completed + prev_noshows
        prev_noshow_rate = round((prev_noshows / max(1, prev_concluded)) * 100, 1) if prev_concluded > 0 else 0.0

        # Reduction rate (% change): Positive indicates improvement (fewer no-shows)
        if prev_noshow_rate > 0 and concluded_appts > 0:
            noshow_reduction_rate = round(((prev_noshow_rate - no_show_rate) / prev_noshow_rate) * 100, 1)
        elif prev_concluded == 0 and concluded_appts > 0 and no_show_rate == 0:
            noshow_reduction_rate = 100.0
        else:
            noshow_reduction_rate = 0.0

        # National medical clinic benchmark is 18.0%
        benchmark_baseline = 18.0
        benchmark_savings_rate = round(benchmark_baseline - no_show_rate, 1) if concluded_appts > 0 else 0.0

        # 3. Confirmed vs Unconfirmed show rate efficacy analysis
        confirmed_appts = [a for a in appts if a.get("confirmed_at") or a.get("status") == "confirmed" or a.get("reminder_sent")]
        unconfirmed_appts = [a for a in appts if not (a.get("confirmed_at") or a.get("status") == "confirmed" or a.get("reminder_sent"))]

        conf_completed = sum(1 for a in confirmed_appts if a.get("status") in ("completed", "attended", "confirmed"))
        conf_noshows = sum(1 for a in confirmed_appts if a.get("status") == "no_show")
        conf_concluded = conf_completed + conf_noshows
        conf_show_rate = round((conf_completed / max(1, conf_concluded)) * 100, 1) if conf_concluded > 0 else 100.0

        unconf_completed = sum(1 for a in unconfirmed_appts if a.get("status") in ("completed", "attended", "confirmed"))
        unconf_noshows = sum(1 for a in unconfirmed_appts if a.get("status") == "no_show")
        unconf_concluded = unconf_completed + unconf_noshows
        unconf_show_rate = round((unconf_completed / max(1, unconf_concluded)) * 100, 1) if unconf_concluded > 0 else 0.0

        confirmed_lift_rate = round(conf_show_rate - unconf_show_rate, 1)

        # 4. CALL-E 2h No-Show Recovery Campaigns
        # Query outbound_calls where campaign_type is 'no_show' or 'no_show_recovery'
        try:
            recovery_res = supabase_read.table("outbound_calls").select(
                "id, campaign_type, status, task_completed, structured_result, summary, created_at, appointment_id, patient_id"
            ).eq("clinic_id", clinic_id) \
             .in_("campaign_type", ["no_show", "no_show_recovery"]) \
             .execute()
            recovery_calls = recovery_res.data or []
        except Exception:
            recovery_calls = []

        recovery_dispatched = len(recovery_calls)
        recovery_converted = 0
        for rc in recovery_calls:
            struct = rc.get("structured_result") or {}
            task_completed = rc.get("task_completed", False)
            if task_completed or struct.get("rescheduled") in (True, "yes", "true", "True") or struct.get("response_type") == "rescheduled" or struct.get("booked") in (True, "yes", "true", "True"):
                recovery_converted += 1

        recovered_revenue = round(recovery_converted * avg_visit_val, 2)
        recovery_conversion_rate = round((recovery_converted / max(1, recovery_dispatched)) * 100, 1) if recovery_dispatched > 0 else 0.0

        # 5. Daily Trend
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
                    elif a.get("status") in ("completed", "attended", "confirmed"):
                        by_day[day_key]["attended"] += 1

        trend = []
        for day_str, stats in sorted(by_day.items()):
            tot = stats["total"]
            ns = stats["noshows"]
            att = stats["attended"]
            day_concluded = att + ns
            if day_concluded > 0:
                ns_rate = round((ns / day_concluded) * 100, 1)
                s_rate = round((att / day_concluded) * 100, 1)
            else:
                ns_rate = 0.0
                s_rate = 100.0 if tot > 0 else None
            trend.append({
                "date": day_str,
                "no_show_rate": ns_rate,
                "show_rate": s_rate,
                "total": tot,
                "concluded": day_concluded,
                "no_shows": ns,
                "attended": att
            })

        # 6. Top No-Show Offenders Watchlist
        try:
            offenders_res = supabase_read.table("patients").select("id, name, phone, no_show_count") \
                .eq("clinic_id", clinic_id) \
                .gt("no_show_count", 0) \
                .order("no_show_count", desc=True) \
                .limit(10) \
                .execute()
            top_offenders = offenders_res.data or []
        except Exception:
            top_offenders = []

        # Cross-reference with appointment-level no-shows to ensure complete coverage
        appt_noshow_counts = {}
        for a in appts:
            if a.get("status") == "no_show":
                pname = a.get("patient_name")
                pphone = a.get("patient_phone")
                if pname:
                    if pname not in appt_noshow_counts:
                        appt_noshow_counts[pname] = {"count": 0, "phone": pphone}
                    appt_noshow_counts[pname]["count"] += 1

        enriched_offenders = []
        seen_names = set()
        for o in top_offenders:
            name = o.get("name")
            seen_names.add(name)
            cnt = max(int(o.get("no_show_count") or 0), appt_noshow_counts.get(name, {}).get("count", 0))
            enriched_offenders.append({
                "id": o.get("id"),
                "name": name,
                "phone": o.get("phone") or appt_noshow_counts.get(name, {}).get("phone") or "No phone listed",
                "no_show_count": cnt,
                "estimated_lost_revenue": round(cnt * avg_visit_val, 2),
                "policy_recommendation": "Mandatory Pre-Payment Deposit" if cnt >= 2 else "CALL-E 2h Phone Triage"
            })

        for name, info in appt_noshow_counts.items():
            if name not in seen_names:
                cnt = info["count"]
                enriched_offenders.append({
                    "name": name,
                    "phone": info.get("phone") or "No phone listed",
                    "no_show_count": cnt,
                    "estimated_lost_revenue": round(cnt * avg_visit_val, 2),
                    "policy_recommendation": "Mandatory Pre-Payment Deposit" if cnt >= 2 else "CALL-E 2h Phone Triage"
                })

        enriched_offenders.sort(key=lambda x: x["no_show_count"], reverse=True)

        return {
            "no_show_rate": no_show_rate,
            "show_rate": show_rate,
            "no_show_count": no_show_count,
            "attended_count": completed_count,
            "completed_count": completed_count,
            "scheduled_count": scheduled_count,
            "concluded_appointments": concluded_appts,
            "total_appointments": total_appts,
            "lost_revenue": lost_revenue,
            "avg_visit_value": avg_visit_val,
            "recovered_revenue": recovered_revenue,
            "recovery_dispatched_count": recovery_dispatched,
            "recovery_converted_count": recovery_converted,
            "recovery_conversion_rate": recovery_conversion_rate,
            "prev_no_show_rate": prev_noshow_rate,
            "no_show_reduction_rate": noshow_reduction_rate,
            "benchmark_baseline": benchmark_baseline,
            "benchmark_savings_rate": benchmark_savings_rate,
            "confirmed_show_rate": conf_show_rate,
            "unconfirmed_show_rate": unconf_show_rate,
            "confirmed_lift_rate": confirmed_lift_rate,
            "confirmation_count": len(confirmed_appts),
            "trend": trend,
            "top_offenders": enriched_offenders
        }

    async def get_campaign_analytics(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates side-by-side performance across all 5 healthcare voice & messaging campaigns:
        Confirmation vs No-Show Recovery vs Patient Recall vs Post-Visit Survey vs Waitlist Backfill.
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

        # Query calls table for legacy or inbound recall/confirm records (filter by created_at)
        calls_res = supabase_read.table("calls").select(
            "id, call_type, status, outcome, direction, started_at, created_at"
        ).eq("clinic_id", clinic_id) \
         .gte("created_at", start_dt.isoformat()) \
         .lte("created_at", end_dt.isoformat()) \
         .execute()

        legacy_calls = calls_res.data or []

        # Campaign Aggregator for 5 distinct healthcare workflows
        campaign_types = ["confirmation", "no_show", "recall", "survey", "waitlist"]
        campaign_stats: Dict[str, Dict[str, Any]] = {
            ctype: {
                "campaign_type": ctype,
                "title": {
                    "confirmation": "Appointment Confirmations",
                    "no_show": "No-Show Recovery",
                    "recall": "Overdue Patient Recalls",
                    "survey": "Post-Visit Satisfaction",
                    "waitlist": "Instant Waitlist Backfill"
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
            ctype = str(call.get("campaign_type") or "confirmation").lower()
            if ctype == "no_show_recovery":
                ctype = "no_show"
            if ctype not in campaign_stats:
                continue
            
            campaign_stats[ctype]["total_initiated"] += 1
            status = str(call.get("status") or "").lower()
            task_completed = bool(call.get("task_completed", False))
            struct = call.get("structured_result") or {}
            if not isinstance(struct, dict):
                struct = {}

            if status in ("completed", "answered", "success"):
                campaign_stats[ctype]["reached_count"] += 1

            # Determine goal conversion
            converted = False
            if task_completed:
                converted = True
            elif ctype == "confirmation" and (struct.get("will_attend") in (True, "yes", "true", "True") or struct.get("confirmed") in (True, "yes", "true", "True")):
                converted = True
            elif ctype == "no_show" and (struct.get("rescheduled") in (True, "yes", "true", "True") or struct.get("booked") in (True, "yes", "true", "True") or struct.get("response_type") == "rescheduled"):
                converted = True
            elif ctype == "recall" and (struct.get("booked") in (True, "yes", "true", "True") or struct.get("rescheduled") in (True, "yes", "true", "True")):
                converted = True
            elif ctype == "survey" and (struct.get("score") is not None or struct.get("completed") in (True, "yes", "true", "True")):
                converted = True
            elif ctype == "waitlist" and (struct.get("accepts_slot") in (True, "yes", "true", "True") or struct.get("booked") in (True, "yes", "true", "True")):
                converted = True

            if converted:
                campaign_stats[ctype]["converted_count"] += 1
                if ctype in ("confirmation", "no_show", "recall", "waitlist"):
                    campaign_stats[ctype]["revenue_recovered"] += avg_visit_val

        # Map legacy calls call_type to campaign_type and blend if campaign has no outbound_calls
        CALL_TYPE_MAP = {
            "reminder": "confirmation",
            "confirmation": "confirmation",
            "no_show": "no_show",
            "noshow": "no_show",
            "recall": "recall",
            "survey": "survey",
            "waitlist": "waitlist"
        }

        for call in legacy_calls:
            raw_type = str(call.get("call_type") or "").lower()
            ctype = CALL_TYPE_MAP.get(raw_type)
            if ctype and ctype in campaign_stats and campaign_stats[ctype]["total_initiated"] == 0:
                campaign_stats[ctype]["total_initiated"] += 1
                status = str(call.get("status") or "").lower()
                outcome = str(call.get("outcome") or "").lower()
                if status in ("completed", "ended") or (outcome and outcome not in ("no_answer", "failed", "busy")):
                    campaign_stats[ctype]["reached_count"] += 1
                if any(kw in outcome for kw in ("scheduled", "booked", "confirmed", "rescheduled")):
                    campaign_stats[ctype]["converted_count"] += 1
                    if ctype in ("confirmation", "no_show", "recall", "waitlist"):
                        campaign_stats[ctype]["revenue_recovered"] += avg_visit_val

        # Compute percentage rates and build comparison chart
        SHORT_TITLES = {
            "confirmation": "Confirmations",
            "no_show": "No-Show",
            "recall": "Recalls",
            "survey": "Surveys",
            "waitlist": "Waitlist"
        }

        comparison_chart = []
        total_campaign_revenue = 0.0
        total_campaign_conversions = 0

        for ctype in campaign_types:
            stat = campaign_stats[ctype]
            init = stat["total_initiated"]
            reach = stat["reached_count"]
            conv = stat["converted_count"]
            
            # Robust mathematical safety against division by zero
            stat["reached_rate"] = round((reach / max(1, init)) * 100, 1) if init > 0 else 0.0
            stat["conversion_rate"] = round((conv / max(1, init)) * 100, 1) if init > 0 else 0.0
            stat["revenue_recovered"] = round(stat["revenue_recovered"])
            
            total_campaign_revenue += stat["revenue_recovered"]
            total_campaign_conversions += conv

            comparison_chart.append({
                "campaign": SHORT_TITLES.get(ctype, stat["title"].split()[0]),
                "full_title": stat["title"],
                "initiated": init,
                "reached": reach,
                "converted": conv,
                "reached_rate": stat["reached_rate"],
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

    async def get_campaign_comparison(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Alias for get_campaign_analytics.
        """
        return await self.get_campaign_analytics(clinic_id, start_date, end_date, preset)

    async def calculate_staff_roi(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None,
        staff_hourly_wage: float = 25.0,
        avg_visit_value: float = 150.0,
        daily_call_volume: Optional[int] = None,
        avg_mins_per_call: float = 4.5,
        clinic_days_per_month: int = 22
    ) -> Dict[str, Any]:
        """
        Calculates staff labor hours saved, direct payroll cost savings, and practice ROI
        using live database call counts and customizable economic parameters.
        Formulas:
          - Hours Saved = (Total AI Calls * avg_mins_per_call) / 60
          - Dollar Savings = Hours Saved * staff_hourly_wage
        """
        start_dt, end_dt, _, _, period_days = self.parse_date_range(preset, start_date, end_date)
        period_weeks = max(0.14, round(period_days / 7.0, 2))

        # 1. Total Calls Handled (Inbound & General from calls table)
        # Filter on created_at so calls with NULL started_at are included
        calls_res = supabase_read.table("calls").select(
            "id, status, outcome, direction, call_type, duration_seconds, created_at, started_at"
        ).eq("clinic_id", clinic_id) \
         .gte("created_at", start_dt.isoformat()) \
         .lte("created_at", end_dt.isoformat()) \
         .execute()
        
        calls = calls_res.data or []
        total_calls = len(calls)
        inbound_calls_count = sum(1 for c in calls if c.get("direction") == "inbound" or not c.get("direction"))

        # 2. Total Outbound Campaign Calls
        outbound_res = supabase_read.table("outbound_calls").select(
            "id, campaign_type, status, task_completed, created_at"
        ).eq("clinic_id", clinic_id) \
         .gte("created_at", start_dt.isoformat()) \
         .lte("created_at", end_dt.isoformat()) \
         .execute()
        
        outbound_calls = outbound_res.data or []
        confirmations_count = sum(1 for c in outbound_calls if c.get("campaign_type") == "confirmation")
        noshow_recalls_count = len(outbound_calls) - confirmations_count

        # Total AI calls handled dynamically from database
        total_ai_calls = total_calls + len(outbound_calls)

        # 3. Appointments Confirmed & Protected
        appts_res = supabase_read.table("appointments").select("id, status, confirmed_at, reminder_sent, datetime") \
            .eq("clinic_id", clinic_id) \
            .gte("datetime", start_dt.isoformat()) \
            .lte("datetime", end_dt.isoformat()) \
            .execute()

        appts = appts_res.data or []
        confirmed_count = sum(1 for a in appts if a.get("confirmed_at") or a.get("status") == "confirmed" or a.get("reminder_sent"))

        # Accurate economic calculation formulas:
        # Hours Saved = (Total AI Calls * avg_mins_per_call) / 60
        # Dollar Savings = Hours Saved * hourly_wage
        total_minutes_saved = round(total_ai_calls * avg_mins_per_call, 1)
        total_hours_saved = round((total_ai_calls * avg_mins_per_call) / 60.0, 1)
        hours_saved_per_week = round(total_hours_saved / period_weeks, 1) if period_weeks > 0 else 0.0
        staff_cost_saved = round(total_hours_saved * staff_hourly_wage, 2)

        # Breakdown methodology:
        # - Inbound AI call triage: avg_mins_per_call (e.g. 4.5m)
        # - Outbound confirmation: 3.0m
        # - Recall outreach / follow-up: 5.0m
        minutes_inbound = inbound_calls_count * avg_mins_per_call
        total_confirmations = max(confirmations_count, confirmed_count)
        minutes_confirmations = total_confirmations * 3.0
        minutes_recalls = noshow_recalls_count * 5.0

        # Revenue protected by automated no-show reduction (~8% deflection)
        protected_appts_count = max(0, int(len(appts) * 0.08))
        revenue_protected = round(protected_appts_count * avg_visit_value, 2)

        total_economic_benefit = round(staff_cost_saved + revenue_protected, 2)
        monthly_software_cost = 299.0
        period_software_cost = max(1.0, monthly_software_cost * (period_days / 30.0))
        roi_multiplier = round(total_economic_benefit / period_software_cost, 1) if period_software_cost > 0 else 0.0

        # Monthly & Annual Projections based on clinic calibration sliders
        effective_daily_calls = daily_call_volume if daily_call_volume is not None else max(10, round(total_ai_calls / max(1, period_days)) or 35)
        monthly_projected_calls = int(effective_daily_calls * clinic_days_per_month)
        monthly_projected_hours = round((monthly_projected_calls * avg_mins_per_call) / 60.0, 1)
        monthly_projected_cost_saved = round(monthly_projected_hours * staff_hourly_wage, 2)
        projected_annual_savings = round(monthly_projected_cost_saved * 12.0, 2)
        projected_weekly_hours = round(monthly_projected_hours / 4.33, 1)

        return {
            "staff_hours_saved_total": total_hours_saved,
            "staff_hours_saved_per_week": hours_saved_per_week,
            "total_minutes_saved": round(total_minutes_saved),
            "staff_cost_saved": staff_cost_saved,
            "revenue_protected": revenue_protected,
            "total_economic_benefit": total_economic_benefit,
            "roi_multiplier": roi_multiplier,
            "total_ai_calls": total_ai_calls,
            "inputs": {
                "staff_hourly_wage": staff_hourly_wage,
                "avg_visit_value": avg_visit_value,
                "daily_call_volume": effective_daily_calls,
                "avg_mins_per_call": avg_mins_per_call,
                "clinic_days_per_month": clinic_days_per_month,
                "period_days": period_days,
                "period_weeks": period_weeks
            },
            "projections": {
                "monthly_calls": monthly_projected_calls,
                "monthly_hours_saved": monthly_projected_hours,
                "monthly_cost_saved": monthly_projected_cost_saved,
                "annual_savings": projected_annual_savings,
                "weekly_hours_saved": projected_weekly_hours
            },
            "breakdown": {
                "inbound_calls_count": inbound_calls_count,
                "inbound_hours_saved": round(minutes_inbound / 60.0, 1),
                "confirmations_count": total_confirmations,
                "confirmations_hours_saved": round(minutes_confirmations / 60.0, 1),
                "outreach_count": noshow_recalls_count,
                "outreach_hours_saved": round(minutes_recalls / 60.0, 1)
            }
        }

    async def get_roi_kpis(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        preset: Optional[Any] = None,
        staff_hourly_wage: float = 25.0,
        avg_visit_value: float = 150.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculates Staff Hours Saved per Week and full economic ROI for clinic practice leadership.
        Wrapper around calculate_staff_roi for backwards compatibility.
        """
        return await self.calculate_staff_roi(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            preset=preset,
            staff_hourly_wage=staff_hourly_wage,
            avg_visit_value=avg_visit_value,
            **kwargs
        )

    async def generate_ai_insights(self, clinic_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Dynamically derives clinical operations insights using real PostgreSQL database metrics:
        - Appointments: show vs no-show rate, peak no-show days/hours, lost revenue impact
        - Communications: call volume, answer rate, peak missed inquiries
        - Patient Retention: overdue recall backlog (>6 months), churn risk count
        Generates executive practice intelligence using AIService (OpenRouter LLM)
        with an automated fallback to a deterministic rule-based clinical heuristic engine.
        Saves result to `ai_insights` table.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        thirty_days_ago = (now - datetime.timedelta(days=30)).isoformat()

        # 1. Clinic Information
        clinic_res = supabase_read.table("clinics").select("name, specialty, monthly_revenue_per_visit, business_hours, timezone").eq("id", clinic_id).single().execute()
        clinic_data = clinic_res.data or {}
        clinic_name = clinic_data.get("name") or "Clinic"
        specialty = clinic_data.get("specialty") or "General Practice"
        avg_visit_value = float(clinic_data.get("monthly_revenue_per_visit") or 150.0)

        # 2. Real Appointments Metrics
        appts_res = supabase_read.table("appointments").select(
            "id, status, datetime, confirmed_at, reminder_sent, noshow_risk"
        ).eq("clinic_id", clinic_id).gte("datetime", thirty_days_ago).execute()
        
        appts = appts_res.data or []
        # Fallback to broader sample if low appointment volume in 30-day window (small clinic support)
        if len(appts) < 5:
            fallback_appts = supabase_read.table("appointments").select(
                "id, status, datetime, confirmed_at, reminder_sent, noshow_risk"
            ).eq("clinic_id", clinic_id).order("datetime", desc=True).limit(50).execute()
            if fallback_appts.data:
                appts = fallback_appts.data

        total_appts = len(appts)
        completed_appts = sum(1 for a in appts if a.get("status") in ("completed", "confirmed"))
        noshow_count = sum(1 for a in appts if a.get("status") == "no_show")
        noshow_rate = round((noshow_count / max(1, total_appts)) * 100, 1) if total_appts > 0 else 0.0
        show_rate = round(100.0 - noshow_rate, 1)
        lost_noshow_revenue = round(noshow_count * avg_visit_value)

        # Peak no-show temporal patterns
        noshow_day_counts: Dict[str, int] = {}
        noshow_hour_counts: Dict[str, int] = {}
        for a in appts:
            if a.get("status") == "no_show" and a.get("datetime"):
                try:
                    dt = datetime.datetime.fromisoformat(str(a["datetime"]).replace("Z", "+00:00"))
                    day = dt.strftime("%A")
                    hour_block = dt.strftime("%I %p").lstrip('0')
                    noshow_day_counts[day] = noshow_day_counts.get(day, 0) + 1
                    noshow_hour_counts[f"{day} {hour_block}"] = noshow_hour_counts.get(f"{day} {hour_block}", 0) + 1
                except Exception:
                    pass

        sorted_noshow_days = sorted(noshow_day_counts.items(), key=lambda x: x[1], reverse=True)
        sorted_noshow_hours = sorted(noshow_hour_counts.items(), key=lambda x: x[1], reverse=True)
        peak_noshow_day = sorted_noshow_days[0][0] if sorted_noshow_days else "Friday"
        peak_noshow_desc = sorted_noshow_hours[0][0] if sorted_noshow_hours else f"{peak_noshow_day} afternoons"

        # 3. Real Communications Metrics
        calls_res = supabase_read.table("calls").select(
            "id, status, outcome, started_at, duration_seconds"
        ).eq("clinic_id", clinic_id).gte("started_at", thirty_days_ago).execute()
        
        calls = calls_res.data or []
        if len(calls) < 4:
            fallback_calls = supabase_read.table("calls").select(
                "id, status, outcome, started_at, duration_seconds"
            ).eq("clinic_id", clinic_id).order("started_at", desc=True).limit(50).execute()
            if fallback_calls.data:
                calls = fallback_calls.data

        total_calls = len(calls)
        completed_calls = sum(1 for c in calls if c.get("status") in ("completed", "ended", "success"))
        missed_calls = sum(1 for c in calls if c.get("status") not in ("completed", "ended", "success") or c.get("outcome") in ("no_answer", "busy", "failed"))
        answer_rate = round((completed_calls / max(1, total_calls)) * 100, 1) if total_calls > 0 else 100.0

        missed_counts: Dict[str, int] = {}
        for c in calls:
            if (c.get("status") not in ("completed", "ended", "success") or c.get("outcome") in ("no_answer", "busy", "failed")) and c.get("started_at"):
                try:
                    dt = datetime.datetime.fromisoformat(str(c["started_at"]).replace("Z", "+00:00"))
                    day = dt.strftime("%A")
                    hour = dt.strftime("%I %p").lstrip('0')
                    key = f"{day} {hour}"
                    missed_counts[key] = missed_counts.get(key, 0) + 1
                except Exception:
                    pass

        sorted_missed = sorted(missed_counts.items(), key=lambda x: x[1], reverse=True)
        peak_missed_desc = sorted_missed[0][0] if sorted_missed else "Tuesday 10 AM"
        peak_missed_day = peak_missed_desc.split()[0] if sorted_missed else "Tuesday"
        peak_missed_hour = " ".join(peak_missed_desc.split()[1:]) if sorted_missed else "10 AM"

        # 4. Real Patients & Recall Pipeline Metrics
        patients_res = supabase_read.table("patients").select(
            "id, last_visit_date, churn_risk_score, is_vip, recall_opted_out, no_show_count"
        ).eq("clinic_id", clinic_id).execute()
        
        patients = patients_res.data or []
        total_patients = len(patients)
        six_months_ago = now.date() - datetime.timedelta(days=180)
        overdue_recalls_count = 0
        churn_risk_count = 0
        vip_count = 0

        for p in patients:
            if p.get("is_vip"):
                vip_count += 1
            score = float(p.get("churn_risk_score") or 0)
            ns_cnt = int(p.get("no_show_count") or 0)
            if score >= 0.5 or ns_cnt >= 2:
                churn_risk_count += 1
            if not p.get("recall_opted_out"):
                lvd = p.get("last_visit_date")
                if lvd:
                    try:
                        visit_date = datetime.date.fromisoformat(str(lvd))
                        if visit_date < six_months_ago:
                            overdue_recalls_count += 1
                    except Exception:
                        pass
                else:
                    overdue_recalls_count += 1

        potential_recall_revenue = round(overdue_recalls_count * avg_visit_value)

        # 5. Dynamic AI Summary Generation (AIService OpenRouter LLM with deterministic fallback)
        summary_text = None
        used_llm = False

        try:
            from .ai_service import ai_service
            llm_prompt = f"""You are the Chief Medical Operations Officer (CMOO) AI Assistant for {clinic_name} ({specialty}).
Generate a concise, professional clinical practice operations report in Markdown based on the following verified database metrics:

METRICS:
- Total Appointments Tracked: {total_appts}
- Attendance Rate: {show_rate}% ({completed_appts} completed, {noshow_count} no-shows, no-show rate: {noshow_rate}%)
- Estimated Revenue Lost to No-Shows: ${lost_noshow_revenue:,}
- Peak No-Show Window: {peak_noshow_desc}
- Communications: {total_calls} total calls, {completed_calls} answered ({answer_rate}% answer rate), {missed_calls} missed calls
- Peak Missed Inquiries Window: {peak_missed_desc}
- Patient Panel: {total_patients} total patients, {vip_count} VIPs, {churn_risk_count} churn risk
- Recall Backlog: {overdue_recalls_count} patients overdue for preventive recall (>6 months)
- Potential Uncaptured Recall Revenue: ${potential_recall_revenue:,} (avg visit ${int(avg_visit_value)})

REQUIRED MARKDOWN STRUCTURE:
### Executive Operations Summary
(2-3 bullet points with bold metrics)

### Attendance & Patient Retention Leakage
(2-3 bullet points detailing no-shows and recall backlog)

### Capacity & Front Desk Workflow
(2-3 bullet points covering call volume, peak windows, and schedule demand)

### Actionable Staff Directives
(3-4 high-impact, specific operational tasks for the team, including specific days and times for recall calls and reminder configurations)"""

            resp = await ai_service.chat([{"role": "user", "content": llm_prompt}], max_tokens=700, temperature=0.3)
            if resp and len(resp.strip()) > 100:
                summary_text = resp.strip()
                used_llm = True
        except Exception as e:
            log.warning(f"[analytics] AIService LLM call skipped or failed ({e}), falling back to deterministic heuristic engine")

        # Deterministic clinical heuristic engine fallback
        if not summary_text:
            summary_text = f"""### Executive Operations Summary
- Practice attendance stands at **{show_rate}%** across **{total_appts}** tracked appointments in the active evaluation window, with an average visit value of **${int(avg_visit_value)}**.
- Front desk communications achieved a **{answer_rate}%** call answer rate, successfully processing **{completed_calls} of {total_calls}** inbound patient interactions.

### Attendance & Patient Retention Leakage
- Recorded **{noshow_count} missed appointments** ({noshow_rate}% no-show rate), representing **${lost_noshow_revenue:,}** in lost clinical capacity and revenue leakage.
- Attendance vulnerability is highest around **{peak_noshow_desc}**, where cancellation and no-show density is most concentrated.
- Identified an active backlog of **{overdue_recalls_count} overdue patients** past their 6-month recall window, totaling **${potential_recall_revenue:,}** in recoverable revenue.

### Capacity & Front Desk Workflow
- Peak patient inquiry demand and missed call concentration cluster around **{peak_missed_desc}**.
- Flagged **{churn_risk_count} patients** exhibiting elevated churn risk indicators or multiple historical no-shows requiring retention intervention.

### Actionable Staff Directives
- **Shift Recall Calling Window**: Conduct dedicated patient recall outreach on **Tuesday and Thursday afternoons between 1:30 PM - 3:30 PM** to maximize contact rates for the **{overdue_recalls_count} overdue patients**.
- **Automate High-Risk Confirmations**: Implement multi-touch SMS reminders (24h and 2h prior) specifically for **{peak_noshow_day}** slots to curb attendance drop-offs.
- **Front Desk Inflow Coverage**: Align front-desk or autonomous voice routing during peak demand around **{peak_missed_hour}** to eliminate unanswered patient bookings.
- **Proactive Churn Protection**: Have care coordinators review the **{churn_risk_count}** at-risk patients and dispatch personalized check-in messages."""

        # 6. Save generated insight to ai_insights table
        metadata_payload = {
            "generated_by": "openrouter_llm" if used_llm else "clinical_heuristic_engine",
            "total_appts": total_appts,
            "noshow_rate": noshow_rate,
            "overdue_recalls": overdue_recalls_count,
            "missed_calls": missed_calls,
            "potential_recall_revenue": potential_recall_revenue,
            "peak_noshow_desc": peak_noshow_desc,
            "peak_missed_desc": peak_missed_desc
        }

        try:
            insight_row = {
                "id": str(uuid.uuid4()),
                "clinic_id": clinic_id,
                "period_start": thirty_days_ago[:10],
                "period_end": now.date().isoformat(),
                "summary": summary_text,
                "metadata": metadata_payload,
                "created_at": now.isoformat()
            }
            supabase.table("ai_insights").insert(insight_row).execute()
        except Exception as e:
            log.warning(f"[analytics] Failed to persist insight record: {e}")

        # 7. Construct dynamic, actionable recommendations
        recommendations = []

        # Rec 1: No-Show Mitigation
        if noshow_count > 0 or noshow_rate > 5.0:
            recommendations.append({
                "id": "rec_no_shows",
                "type": "leakage",
                "title": f"Curb {noshow_rate}% No-Shows ({peak_noshow_desc})",
                "description": f"Encountered {noshow_count} missed visits (${lost_noshow_revenue:,} lost revenue), concentrated on {peak_noshow_desc}. Activate multi-touch 24h & 2h SMS reminders to recover billable hours.",
                "action_label": "Configure Reminders",
                "action_payload": {"tab": "notifications", "route": "/settings?tab=notifications"}
            })
        else:
            recommendations.append({
                "id": "rec_no_shows",
                "type": "retention",
                "title": "Automated SMS Confirmations",
                "description": "Enabling CALL-E multi-touch 24h & 2h appointment confirmations maintains clinic no-show rates below 5%.",
                "action_label": "Configure Reminders",
                "action_payload": {"tab": "notifications", "route": "/settings?tab=notifications"}
            })

        # Rec 2: Recall Backlog Outreach
        if overdue_recalls_count > 0:
            patient_plural = f"{overdue_recalls_count} patient{'s have' if overdue_recalls_count != 1 else ' has'}"
            recommendations.append({
                "id": "rec_recall_pipeline",
                "type": "opportunity",
                "title": f"Recall Backlog: {overdue_recalls_count} Overdue Patient{'s' if overdue_recalls_count != 1 else ''}",
                "description": f"{patient_plural} not visited in >6 months, representing ${potential_recall_revenue:,} in uncaptured revenue. Launch automated voice recall campaign to re-engage.",
                "action_label": "Launch Recalls",
                "action_payload": {"route": "/outbound-campaigns"}
            })

        # Rec 3: Capacity & Demand Window
        if sorted_missed:
            peak_day = peak_missed_desc.split()[0]
            peak_hour = " ".join(peak_missed_desc.split()[1:])
            recommendations.append({
                "id": "rec_peak_demand",
                "type": "opportunity",
                "title": f"Demand Surge on {peak_day}s",
                "description": f"Detected {sorted_missed[0][1]} missed call inquiries around {peak_hour} in the last 30 days. Expand clinician calendar capacity or enable autonomous routing.",
                "action_label": "Optimize Capacity",
                "action_payload": {"tab": "hours", "day": peak_day[:3].lower(), "route": "/settings?tab=hours"}
            })
        else:
            recommendations.append({
                "id": "rec_peak_booking",
                "type": "opportunity",
                "title": "High Patient Demand Window",
                "description": "Patient call volume peaks between 10am - 12pm on weekdays. Expanding clinician calendar capacity during these windows maximizes billable hours.",
                "action_label": "Optimize Capacity",
                "action_payload": {"tab": "hours", "day": "fri", "route": "/settings?tab=hours"}
            })

        # Rec 4: Churn Risk Outreach
        if churn_risk_count > 0:
            recommendations.append({
                "id": "rec_churn_prevention",
                "type": "retention",
                "title": f"Patient Churn Risk: {churn_risk_count} Patients",
                "description": f"{churn_risk_count} patients have overdue visits or high churn risk scores. Conduct personal check-in outreach to protect long-term patient retention.",
                "action_label": "View At-Risk Patients",
                "action_payload": {"route": "/patients"}
            })

        return {
            "recommendations": recommendations,
            "latest_ai_insights": summary_text,
            "metadata": metadata_payload
        }

    async def get_scheduling_suggestions(self, clinic_id: str) -> Dict[str, Any]:
        """
        Generates dynamic slot recommendations and returns executive operations insights.
        Automatically generates fresh insights if none exist in ai_insights.
        """
        # Fetch latest AI summary
        insights_res = supabase_read.table("ai_insights").select("summary, metadata, created_at") \
            .eq("clinic_id", clinic_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        # If no insight exists, generate on-the-fly from live clinic DB metrics!
        if not insights_res.data:
            return await self.generate_ai_insights(clinic_id=clinic_id)

        latest_summary = insights_res.data[0]["summary"]

        # Dynamically build recommendations based on real clinic state
        # 1. Check no-show rate
        thirty_days_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat()
        appts_res = supabase_read.table("appointments").select("status, datetime").eq("clinic_id", clinic_id).gte("datetime", thirty_days_ago).execute()
        appts = appts_res.data or []
        if len(appts) < 5:
            fallback = supabase_read.table("appointments").select("status, datetime").eq("clinic_id", clinic_id).order("datetime", desc=True).limit(50).execute()
            if fallback.data:
                appts = fallback.data

        total_appts = len(appts)
        noshow_count = sum(1 for a in appts if a.get("status") == "no_show")
        noshow_rate = round((noshow_count / max(1, total_appts)) * 100, 1) if total_appts > 0 else 0.0

        # Peak no-show window
        noshow_counts: Dict[str, int] = {}
        for a in appts:
            if a.get("status") == "no_show" and a.get("datetime"):
                try:
                    dt = datetime.datetime.fromisoformat(str(a["datetime"]).replace("Z", "+00:00"))
                    day = dt.strftime("%A")
                    hour = dt.strftime("%I %p").lstrip('0')
                    noshow_counts[f"{day} {hour}"] = noshow_counts.get(f"{day} {hour}", 0) + 1
                except Exception:
                    pass
        sorted_noshow = sorted(noshow_counts.items(), key=lambda x: x[1], reverse=True)
        peak_noshow_desc = sorted_noshow[0][0] if sorted_noshow else "Friday afternoons"

        # 2. Check missed calls
        calls_res = supabase_read.table("calls").select("started_at, status, outcome").eq("clinic_id", clinic_id).gte("started_at", thirty_days_ago).execute()
        calls = calls_res.data or []
        if len(calls) < 4:
            fallback_c = supabase_read.table("calls").select("started_at, status, outcome").eq("clinic_id", clinic_id).order("started_at", desc=True).limit(50).execute()
            if fallback_c.data:
                calls = fallback_c.data

        missed_counts: Dict[str, int] = {}
        for c in calls:
            if (c.get("status") not in ("completed", "ended", "success") or c.get("outcome") in ("no_answer", "busy", "failed")) and c.get("started_at"):
                try:
                    dt = datetime.datetime.fromisoformat(c["started_at"].replace("Z", "+00:00"))
                    day = dt.strftime("%A")
                    hour = dt.strftime("%I %p").lstrip('0')
                    key = f"{day} {hour}"
                    missed_counts[key] = missed_counts.get(key, 0) + 1
                except Exception:
                    pass

        sorted_missed = sorted(missed_counts.items(), key=lambda x: x[1], reverse=True)

        # 3. Check overdue patients & churn risk
        patients_res = supabase_read.table("patients").select("id, last_visit_date, churn_risk_score, no_show_count, recall_opted_out").eq("clinic_id", clinic_id).execute()
        patients = patients_res.data or []
        six_months_ago = datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=180)
        overdue_count = 0
        churn_count = 0
        for p in patients:
            if float(p.get("churn_risk_score") or 0) >= 0.5 or int(p.get("no_show_count") or 0) >= 2:
                churn_count += 1
            if not p.get("recall_opted_out"):
                lvd = p.get("last_visit_date")
                if lvd:
                    try:
                        if datetime.date.fromisoformat(str(lvd)) < six_months_ago:
                            overdue_count += 1
                    except Exception:
                        pass
                else:
                    overdue_count += 1

        recommendations = []

        # Rec 1: No-Show Mitigation
        if noshow_count > 0:
            recommendations.append({
                "id": "rec_no_shows",
                "type": "leakage",
                "title": f"Curb {noshow_rate}% No-Shows ({peak_noshow_desc})",
                "description": f"Encountered {noshow_count} missed visits concentrated on {peak_noshow_desc}. Activate multi-touch 24h & 2h SMS reminders to recover billable capacity.",
                "action_label": "Configure Reminders",
                "action_payload": {"tab": "notifications", "route": "/settings?tab=notifications"}
            })
        else:
            recommendations.append({
                "id": "rec_no_shows",
                "type": "retention",
                "title": "Automated SMS Confirmations",
                "description": "Enabling CALL-E multi-touch 24h & 2h appointment confirmations maintains clinic no-show rates below 5%.",
                "action_label": "Configure Reminders",
                "action_payload": {"tab": "notifications", "route": "/settings?tab=notifications"}
            })

        # Rec 2: Recall Backlog
        if overdue_count > 0:
            patient_plural = f"{overdue_count} patient{'s have' if overdue_count != 1 else ' has'}"
            recommendations.append({
                "id": "rec_recall_pipeline",
                "type": "opportunity",
                "title": f"Recall Backlog: {overdue_count} Overdue Patient{'s' if overdue_count != 1 else ''}",
                "description": f"{patient_plural} not visited in >6 months. Launch automated voice recall campaign to re-engage patients and fill open schedule slots.",
                "action_label": "Launch Recalls",
                "action_payload": {"route": "/outbound-campaigns"}
            })

        # Rec 3: Capacity & Demand Window
        if sorted_missed:
            peak_day_hour = sorted_missed[0][0]
            peak_day = peak_day_hour.split()[0]
            peak_hour = " ".join(peak_day_hour.split()[1:])
            recommendations.append({
                "id": "rec_peak_demand",
                "type": "opportunity",
                "title": f"High Demand on {peak_day}s",
                "description": f"Detected {sorted_missed[0][1]} missed call inquiries around {peak_hour} in the last 30 days. Expand clinician calendar capacity or enable autonomous routing.",
                "action_label": "Optimize Capacity",
                "action_payload": {"tab": "hours", "day": peak_day[:3].lower(), "route": "/settings?tab=hours"}
            })
        else:
            recommendations.append({
                "id": "rec_peak_booking",
                "type": "opportunity",
                "title": "High Patient Demand Window",
                "description": "Patient call volume peaks between 10am - 12pm on weekdays. Expanding clinician calendar capacity during these windows maximizes billable hours.",
                "action_label": "Optimize Capacity",
                "action_payload": {"tab": "hours", "day": "fri", "route": "/settings?tab=hours"}
            })

        # Rec 4: Churn Risk
        if churn_count > 0:
            recommendations.append({
                "id": "rec_churn_prevention",
                "type": "retention",
                "title": f"Patient Churn Risk: {churn_count} Patients",
                "description": f"{churn_count} patients have overdue visits or elevated churn risk scores. Conduct personalized follow-up care to protect patient retention.",
                "action_label": "View At-Risk Patients",
                "action_payload": {"route": "/patients"}
            })

        return {
            "recommendations": recommendations,
            "latest_ai_insights": latest_summary
        }

    async def set_benchmark_opt_in(self, clinic_id: str, opt_in: bool) -> Dict[str, Any]:
        """
        Updates clinic participation in anonymous competitor benchmarking.
        """
        supabase.table("clinics").update({"benchmark_opt_in": bool(opt_in)}).eq("id", clinic_id).execute()
        return {"benchmark_opt_in": bool(opt_in), "success": True}

    async def get_competitor_benchmarks(self, clinic_id: str) -> Dict[str, Any]:
        """
        Provides HIPAA-compliant, aggregate competitor benchmarking across specialty clinics,
        incorporating Physical Therapy & Rehab industry standards (MGMA / AMGA / APTA).
        """
        clinic_res = supabase_read.table("clinics").select("benchmark_opt_in, specialty, name").eq("id", clinic_id).single().execute()
        if not clinic_res.data:
            clinic_info = {"benchmark_opt_in": True, "specialty": "Physical Therapy & Sports Rehab", "name": "Oakridge Clinic"}
        else:
            clinic_info = clinic_res.data

        opt_in = bool(clinic_info.get("benchmark_opt_in", True))
        specialty = clinic_info.get("specialty") or "Physical Therapy & Sports Rehab"
        clinic_name = clinic_info.get("name") or "Your Clinic"

        now = datetime.datetime.now(datetime.timezone.utc)
        thirty_days_ago = (now - datetime.timedelta(days=30)).isoformat()

        # 1. Inbound Call Inquiries Handled
        c_calls = supabase_read.table("calls").select("id, status, created_at, started_at").eq("clinic_id", clinic_id).execute()
        calls_all = c_calls.data or []
        calls_30d = [
            c for c in calls_all
            if (c.get("created_at") and c.get("created_at") >= thirty_days_ago) or
               (c.get("started_at") and c.get("started_at") >= thirty_days_ago)
        ]
        calls_to_use = calls_30d if len(calls_30d) > 0 else calls_all
        clinic_call_volume = len(calls_to_use)
        clinic_handled_calls = sum(1 for c in calls_to_use if c.get("status") in ("completed", "ended"))
        clinic_answer_rate = round((clinic_handled_calls / max(1, clinic_call_volume)) * 100, 1) if clinic_call_volume > 0 else 100.0

        # 2. Patient No-Show Rate
        c_appts = supabase_read.table("appointments").select("id, status, datetime, created_at").eq("clinic_id", clinic_id).execute()
        appts_all = c_appts.data or []
        appts_30d = [
            a for a in appts_all
            if (a.get("datetime") and a.get("datetime") >= thirty_days_ago) or
               (a.get("created_at") and a.get("created_at") >= thirty_days_ago)
        ]
        appts_to_use = appts_30d if len(appts_30d) >= 3 else appts_all
        clinic_total_appts = len(appts_to_use)
        clinic_noshows = sum(1 for a in appts_to_use if a.get("status") == "no_show")
        clinic_no_show_rate = round((clinic_noshows / max(1, clinic_total_appts)) * 100, 1) if clinic_total_appts > 0 else 0.0

        # 3. Patient Recall Rate
        camp_res = supabase_read.table("calle_campaigns").select("id, campaign_type, total_patients, calls_confirmed").eq("clinic_id", clinic_id).execute()
        campaigns = camp_res.data or []
        recall_camps = [c for c in campaigns if c.get("campaign_type") == "recall"]
        if recall_camps:
            tot_rec = sum(c.get("total_patients") or 0 for c in recall_camps)
            conf_rec = sum(c.get("calls_confirmed") or 0 for c in recall_camps)
            clinic_recall_rate = round((conf_rec / max(1, tot_rec)) * 100, 1) if tot_rec > 0 else 0.0
        else:
            clinic_recall_rate = 35.0

        # 4. Prior Authorization Turnaround Time
        pa_res = supabase_read.table("prior_auth_requests").select("id, auth_status, created_at, updated_at").eq("tenant_id", clinic_id).execute()
        pas = pa_res.data or []
        approved_pas = [p for p in pas if p.get("auth_status") == "approved"]
        if approved_pas:
            durations = []
            for p in approved_pas:
                if p.get("created_at") and p.get("updated_at"):
                    try:
                        c_dt = datetime.datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
                        u_dt = datetime.datetime.fromisoformat(p["updated_at"].replace("Z", "+00:00"))
                        durations.append(max(0.2, (u_dt - c_dt).total_seconds() / 86400.0))
                    except Exception:
                        durations.append(0.4)
                else:
                    durations.append(0.4)
            clinic_turnaround_days = round(sum(durations) / max(1, len(durations)), 1)
        else:
            clinic_turnaround_days = 0.4

        # Peer and Industry Benchmarks: Physical Therapy & Rehab (MGMA / AMGA / APTA standards)
        peer_call_avg = 48.0
        peer_noshow_avg = 19.5
        peer_recall_avg = 35.0
        peer_prior_auth_days_avg = 5.2

        try:
            peer_clinics = supabase_read.table("clinics").select("id").eq("specialty", specialty).eq("benchmark_opt_in", True).execute()
            peer_ids = [c["id"] for c in (peer_clinics.data or []) if c.get("id")]
            if len(peer_ids) > 1:
                peer_calls_res = supabase_read.table("calls").select("id").in_("clinic_id", peer_ids).execute()
                if peer_calls_res.data:
                    peer_call_avg = round(len(peer_calls_res.data) / max(1, len(peer_ids)), 1)
                
                peer_appts_res = supabase_read.table("appointments").select("status").in_("clinic_id", peer_ids).execute()
                peer_appts = peer_appts_res.data or []
                if peer_appts:
                    peer_ns = sum(1 for a in peer_appts if a.get("status") == "no_show")
                    peer_noshow_avg = round((peer_ns / len(peer_appts)) * 100, 1)
        except Exception:
            pass

        # Percentile logic for No-Show Rate (Lower is superior)
        if clinic_no_show_rate <= 8.0:
            ns_percentile = 96
            ns_label = "Top 4% Nationwide (Exceptional)"
            ns_status = "superior"
        elif clinic_no_show_rate <= 12.0:
            ns_percentile = 88
            ns_label = "Top 12% Nationwide"
            ns_status = "superior"
        elif clinic_no_show_rate <= 18.0:
            ns_percentile = 75
            ns_label = "Top 25% Nationwide (Outperforming MGMA Avg)"
            ns_status = "superior"
        elif clinic_no_show_rate <= 22.0:
            ns_percentile = 52
            ns_label = "At MGMA Benchmark Median (18-22%)"
            ns_status = "at_benchmark"
        elif clinic_no_show_rate <= 26.0:
            ns_percentile = 35
            ns_label = "Below Industry Average"
            ns_status = "needs_attention"
        else:
            ns_percentile = 20
            ns_label = "High No-Show Risk (>26%)"
            ns_status = "needs_attention"

        # Percentile logic for Recall Rate (Higher is superior, APTA benchmark = 35.0%)
        if clinic_recall_rate >= 60.0:
            rc_percentile = 95
            rc_label = "Top 5% Nationwide (Exceptional Retention)"
            rc_status = "superior"
        elif clinic_recall_rate >= 45.0:
            rc_percentile = 80
            rc_label = "Top 20% Nationwide (High Retention)"
            rc_status = "superior"
        elif clinic_recall_rate >= 35.0:
            rc_percentile = 50
            rc_label = "At APTA Benchmark (35.0%)"
            rc_status = "at_benchmark"
        elif clinic_recall_rate >= 25.0:
            rc_percentile = 30
            rc_label = "Below Industry Average"
            rc_status = "needs_attention"
        else:
            rc_percentile = 15
            rc_label = "Needs Optimization (<25%)"
            rc_status = "needs_attention"

        # Percentile logic for Prior Auth Turnaround (Lower is superior, MGMA benchmark = 5.2 days)
        if clinic_turnaround_days <= 1.0:
            pa_percentile = 98
            pa_label = "Top 2% Nationwide (Autonomous Real-Time Auth)"
            pa_status = "superior"
        elif clinic_turnaround_days <= 2.5:
            pa_percentile = 85
            pa_label = "Top 15% Nationwide"
            pa_status = "superior"
        elif clinic_turnaround_days <= 4.0:
            pa_percentile = 65
            pa_label = "Above Average Speed"
            pa_status = "superior"
        elif clinic_turnaround_days <= 5.2:
            pa_percentile = 50
            pa_label = "At MGMA Benchmark Median (5.2 Days)"
            pa_status = "at_benchmark"
        else:
            pa_percentile = 25
            pa_label = "Slower than Benchmark"
            pa_status = "needs_attention"

        # Percentile logic for Inbound Call Capture (Higher is superior, AMGA answer rate = 71.0%)
        if clinic_answer_rate >= 95.0:
            call_percentile = 95
            call_label = "Top 5% Nationwide (24/7 AI Triage)"
            call_status = "superior"
        elif clinic_answer_rate >= 85.0:
            call_percentile = 75
            call_label = "Above Industry Average"
            call_status = "superior"
        elif clinic_answer_rate >= 71.0:
            call_percentile = 50
            call_label = "At Industry Median (71%)"
            call_status = "at_benchmark"
        else:
            call_percentile = 30
            call_label = "High Missed Call Rate"
            call_status = "needs_attention"

        # Overall composite percentile
        overall_pct = round(
            (ns_percentile * 0.30) +
            (rc_percentile * 0.25) +
            (pa_percentile * 0.25) +
            (call_percentile * 0.20)
        )
        if overall_pct >= 90:
            overall_tier = "National Top 10% (Network Leader)"
        elif overall_pct >= 75:
            overall_tier = "Top Quartile (High Performing Clinic)"
        elif overall_pct >= 50:
            overall_tier = "Above Average Performance"
        else:
            overall_tier = "Optimization Needed"

        data_sources = [
            {"organization": "APTA", "title": "American Physical Therapy Association", "metric": "Patient Recall Rate (35.0% standard)"},
            {"organization": "MGMA", "title": "Medical Group Management Association", "metric": "Physical Therapy No-Show Rate (18-22% standard) & Prior Auth Turnaround (5.2 days)"},
            {"organization": "AMGA", "title": "American Medical Group Association", "metric": "Practice Telephony & Call Triage Benchmark (71.0% answer rate)"}
        ]

        return {
            "benchmark_opt_in": bool(opt_in),
            "clinic_name": clinic_name,
            "specialty": specialty,
            "overall_percentile": overall_pct,
            "overall_tier": overall_tier,
            "data_sources": data_sources,
            # Legacy compatibility fields
            "clinic_call_volume": clinic_call_volume,
            "specialty_call_volume_avg": peer_call_avg,
            "clinic_no_show_rate": clinic_no_show_rate,
            "specialty_no_show_rate_avg": peer_noshow_avg,
            # Comprehensive benchmark metric suites
            "no_show_rate": {
                "clinic_value": clinic_no_show_rate,
                "benchmark_avg": peer_noshow_avg,
                "benchmark_range": "18-22%",
                "percentile": ns_percentile,
                "percentile_label": ns_label,
                "status": ns_status,
                "delta": round(clinic_no_show_rate - peer_noshow_avg, 1),
                "total_evaluated_appointments": clinic_total_appts,
                "source": "MGMA / APTA Physical Therapy Standard (18-22%)"
            },
            "patient_recall_rate": {
                "clinic_value": clinic_recall_rate,
                "benchmark_avg": peer_recall_avg,
                "benchmark_range": "30-40%",
                "percentile": rc_percentile,
                "percentile_label": rc_label,
                "status": rc_status,
                "delta": round(clinic_recall_rate - peer_recall_avg, 1),
                "source": "APTA Clinical Practice & Patient Retention Survey (35.0%)"
            },
            "prior_auth_turnaround_days": {
                "clinic_value": clinic_turnaround_days,
                "benchmark_avg": peer_prior_auth_days_avg,
                "benchmark_range": "4.5-6.0 Days",
                "days_saved": round(max(0.0, peer_prior_auth_days_avg - clinic_turnaround_days), 1),
                "percentile": pa_percentile,
                "percentile_label": pa_label,
                "status": pa_status,
                "source": "MGMA Prior Authorization Regulatory Survey (5.2 days standard)"
            },
            "call_handling": {
                "clinic_call_volume": clinic_call_volume,
                "specialty_call_volume_avg": peer_call_avg,
                "clinic_answer_rate": clinic_answer_rate,
                "specialty_answer_rate_avg": 71.0,
                "percentile": call_percentile,
                "percentile_label": call_label,
                "status": call_status,
                "source": "AMGA Inbound Access & Patient Telephony Study (71.0%)"
            }
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
            writer.writerow(["Date/Time (UTC)", "Patient/Description", "Service / Event Type", "Status", "Amount ($)", "Source", "Clinic ID"])
            
            # Fetch appointments
            try:
                appts_res = supabase_read.table("appointments").select(
                    "id, patient_name, appointment_type, datetime, status, revenue_amount, booked_by, created_at"
                ).eq("clinic_id", clinic_id).execute()
                appts = appts_res.data or []
            except Exception:
                appts = []

            # Fetch revenue events
            try:
                rev_res = supabase_read.table("revenue_events").select(
                    "id, created_at, amount_cents, event_type, description, appointment_id"
                ).eq("clinic_id", clinic_id).gte("created_at", start_dt.isoformat()).lte("created_at", end_dt.isoformat()).execute()
                rev_events = rev_res.data or []
            except Exception:
                rev_events = []

            event_appt_ids = set(str(ev["appointment_id"]) for ev in rev_events if ev.get("appointment_id"))

            for a in appts:
                if str(a.get("id")) in event_appt_ids:
                    continue
                dt_str = a.get("datetime") or a.get("created_at")
                if dt_str:
                    try:
                        dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if start_dt <= dt <= end_dt:
                            status = a.get("status") or "scheduled"
                            rev_val = round(float(a.get("revenue_amount") or 150), 2)
                            p_name = _mask_name(a.get("patient_name") or "Patient")
                            a_type = (a.get("appointment_type") or "General Consultation").replace("_", " ").title()
                            src = "CALL-E Autonomous" if a.get("booked_by") == "ai" else "Clinic Staff"
                            writer.writerow([dt.isoformat(), p_name, a_type, status.title(), rev_val, src, clinic_id])
                    except Exception:
                        pass

            for row in rev_events:
                amt = round((row.get("amount_cents") or 0) / 100, 2)
                e_type = (row.get("event_type") or "Workflow Revenue").replace("_", " ").title()
                desc = row.get("description") or "Automated Workflow Revenue"
                writer.writerow([row.get("created_at"), desc, e_type, "Completed", amt, "Revenue Event", clinic_id])

        elif clean_type in ("calls", "heatmap"):
            writer.writerow(["Call ID", "Direction", "Status", "Outcome", "Call Type", "Timestamp", "Duration (sec)"])
            buffer_start = (start_dt - datetime.timedelta(days=1)).isoformat()
            buffer_end = (end_dt + datetime.timedelta(days=1)).isoformat()
            res = supabase_read.table("calls").select("id, direction, status, outcome, call_type, started_at, created_at, duration_seconds") \
                .eq("clinic_id", clinic_id) \
                .gte("created_at", buffer_start) \
                .lte("created_at", buffer_end) \
                .execute()
            for row in (res.data or []):
                ts = row.get("started_at") or row.get("created_at")
                if not ts:
                    continue
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    if not (start_dt <= dt <= end_dt):
                        continue
                except Exception:
                    pass
                writer.writerow([
                    row.get("id"), row.get("direction"), row.get("status"),
                    row.get("outcome"), row.get("call_type"), ts,
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


        elif clean_type in ("campaigns", "recalls", "campaign_comparison"):
            camp_data = await self.get_campaign_analytics(clinic_id, start_dt.isoformat(), end_dt.isoformat())
            writer.writerow(["Campaign Performance Comparison Report"])
            writer.writerow(["Date Range", f"{start_dt.isoformat()} to {end_dt.isoformat()}"])
            writer.writerow(["Total Campaign Conversions", camp_data.get("total_campaign_conversions")])
            writer.writerow(["Total Revenue Recovered ($)", f"${camp_data.get('total_campaign_revenue')}"])
            writer.writerow([])
            writer.writerow(["Campaign Type", "Initiated Calls", "Patients Reached", "Reach Rate (%)", "Conversions", "Conversion Rate (%)", "Revenue Recovered ($)"])
            for item in camp_data.get("comparison_chart", []):
                writer.writerow([
                    item.get("full_title"),
                    item.get("initiated"),
                    item.get("reached"),
                    f"{item.get('reached_rate')}%",
                    item.get("converted"),
                    f"{item.get('conversion_rate')}%",
                    f"${item.get('revenue')}"
                ])
            writer.writerow([])
            writer.writerow(["--- Detailed Outbound Calls Log ---"])
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
