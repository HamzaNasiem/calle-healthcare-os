import datetime
from typing import Dict, Any, Optional
from ..core.database import supabase, supabase_read
from .ai_service import ai_service
from .email_service import email_service
from ..core.config import settings

class InsightsService:
    async def generate_weekly_insights(self, clinic_id: str) -> Optional[str]:
        """
        Gathers last week's raw metrics (Monday to Sunday), prompts OpenRouter (AI)
        to write a structured executive report, caches the report in the `ai_insights` table,
        and returns the markdown summary.
        """
        try:
            # 1. Calculate the start and end of last week (Mon 00:00:00 to Sun 23:59:59)
            now = datetime.datetime.now(datetime.timezone.utc)
            days_since_monday = now.weekday()
            last_monday = (now - datetime.timedelta(days=days_since_monday + 7)).date()
            last_sunday = (now - datetime.timedelta(days=days_since_monday + 1)).date()

            start_dt = datetime.datetime.combine(last_monday, datetime.time.min, tzinfo=datetime.timezone.utc)
            end_dt = datetime.datetime.combine(last_sunday, datetime.time.max, tzinfo=datetime.timezone.utc)

            # Fetch clinic details (using read replica)
            clinic_res = supabase_read.table("clinics").select("name, specialty, monthly_revenue_per_visit").eq("id", clinic_id).maybe_single().execute()
            if not clinic_res.data:
                print(f"[InsightsService] Clinic {clinic_id} not found.")
                return None
            clinic_info = clinic_res.data
            clinic_name = clinic_info.get("name", "Your Clinic")
            specialty = clinic_info.get("specialty", "Healthcare")
            rev_per_visit = float(clinic_info.get("monthly_revenue_per_visit") or 150.0)

            # 2. Gather last week's database metrics (using read replica)
            # A. Inbound Calls
            calls_res = supabase_read.table("calls").select("id", "status", "started_at") \
                .eq("clinic_id", clinic_id) \
                .gte("started_at", start_dt.isoformat()) \
                .lte("started_at", end_dt.isoformat()) \
                .execute()
            
            calls_data = calls_res.data or []
            total_calls = len(calls_data)
            missed_calls = sum(1 for c in calls_data if c.get("status") != "completed")

            # Calculate busiest missed hours
            hourly_missed = {}
            for c in calls_data:
                if c.get("status") != "completed" and c.get("started_at"):
                    try:
                        # Parse time to find day + hour
                        dt = datetime.datetime.fromisoformat(c["started_at"].replace("Z", "+00:00"))
                        hour_str = dt.strftime("%I %p").lstrip('0')
                        day_str = dt.strftime("%A")
                        key = f"{day_str} {hour_str}"
                        hourly_missed[key] = hourly_missed.get(key, 0) + 1
                    except Exception:
                        pass
            
            sorted_missed = sorted(hourly_missed.items(), key=lambda x: x[1], reverse=True)
            busiest_missed_hours = ", ".join(f"{k} ({v} calls)" for k, v in sorted_missed[:2]) or "None"

            # B. Appointments Booked (created last week)
            appts_created_res = supabase_read.table("appointments").select("id", "status") \
                .eq("clinic_id", clinic_id) \
                .gte("created_at", start_dt.isoformat()) \
                .lte("created_at", end_dt.isoformat()) \
                .execute()
            appts_created = appts_created_res.data or []
            appts_booked = len(appts_created)

            # C. Appointments Occurred (happened last week) and No-shows
            appts_occurred_res = supabase_read.table("appointments").select("id", "status") \
                .eq("clinic_id", clinic_id) \
                .gte("datetime", start_dt.isoformat()) \
                .lte("datetime", end_dt.isoformat()) \
                .execute()
            appts_occurred = appts_occurred_res.data or []
            total_occurred = len(appts_occurred)
            no_shows = sum(1 for a in appts_occurred if a.get("status") == "no_show")
            noshow_rate = round((no_shows / total_occurred * 100), 1) if total_occurred > 0 else 0.0

            # D. Recalls
            recall_res = supabase_read.table("calls").select("id", "status", "outcome") \
                .eq("clinic_id", clinic_id) \
                .eq("call_type", "recall") \
                .gte("started_at", start_dt.isoformat()) \
                .lte("started_at", end_dt.isoformat()) \
                .execute()
            recalls_data = recall_res.data or []
            recall_calls = len(recalls_data)
            recall_answered = sum(1 for r in recalls_data if r.get("status") == "completed")
            recall_booked = sum(1 for r in recalls_data if "scheduled" in (r.get("outcome") or "").lower() or "booked" in (r.get("outcome") or "").lower())
            recall_revenue = recall_booked * rev_per_visit

            # E. Referrals (rewarded last week)
            referrals_res = supabase_read.table("referrals").select("id") \
                .eq("referrer_clinic_id", clinic_id) \
                .eq("status", "rewarded") \
                .gte("rewarded_at", start_dt.isoformat()) \
                .lte("rewarded_at", end_dt.isoformat()) \
                .execute()
            referral_conversions = len(referrals_res.data or [])

            # 3. Call OpenRouter to generate natural-language AI insights
            system_prompt = (
                "You are the Bytelytic Chief Medical Operations Officer (CMOO) Assistant. Your job is to analyze "
                "the raw weekly metrics of a healthcare clinic and provide a highly engaging, actionable executive summary "
                "styled in markdown. Write in a supportive, professional, and revenue-maximizing tone.\n\n"
                "Highlight three major sections using standard headers:\n"
                "### 📈 Weekly Successes\n"
                "### ⚠️ Operational Leakages\n"
                "### 💡 Proactive Recommendations\n\n"
                "Provide actual numbers where appropriate, highlighting areas where scheduling could be optimized or "
                "revenue could be recovered. Keep the summary under 280 words."
            )

            user_prompt = f"""
Clinic Name: {clinic_name}
Specialty: {specialty}
Period: {last_monday.isoformat()} to {last_sunday.isoformat()}

RAW WEEKLY METRICS:
- Total Calls Handled: {total_calls} (Missed calls: {missed_calls})
- Busiest hours with missed calls: {busiest_missed_hours}
- Total Appointments Booked: {appts_booked}
- Appointments Occurred/Scheduled: {total_occurred} (No-shows: {no_shows}, No-show rate: {noshow_rate}%)
- Recall Campaigns: Called={recall_calls}, Answered={recall_answered}, Booked={recall_booked}
- Recall Revenue Recovered: ${recall_revenue}
- Referral conversions this week: {referral_conversions}
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            print(f"[InsightsService] Prompting OpenRouter for clinic: {clinic_id}")
            try:
                ai_summary = await ai_service.chat(messages, max_tokens=600, temperature=0.3)
            except Exception as ai_err:
                print(f"[InsightsService] OpenRouter failed: {ai_err}. Falling back to default summary.")
                ai_summary = (
                    f"### 📈 Weekly Successes\n"
                    f"- Handled {total_calls} patient inquiries successfully.\n"
                    f"- Managed {appts_booked} new appointments booked this week.\n"
                    f"- Recall campaign successfully recovered ${recall_revenue} from patients.\n\n"
                    f"### ⚠️ Operational Leakages\n"
                    f"- {missed_calls} missed calls recorded. Peak missed slots: {busiest_missed_hours}.\n"
                    f"- Clinic experienced a {noshow_rate}% no-show rate ({no_shows} patients did not attend).\n\n"
                    f"### 💡 Proactive Recommendations\n"
                    f"- Consider opening calendar slots during peak missed hours: {busiest_missed_hours}.\n"
                    f"- Send SMS confirmations 24 hours prior to appointments to reduce no-show percentages."
                )

            # 4. Cache generated summary in ai_insights table
            db_insert = {
                "clinic_id": clinic_id,
                "period_start": last_monday.isoformat(),
                "period_end": last_sunday.isoformat(),
                "summary": ai_summary,
                "metadata": {
                    "total_calls": total_calls,
                    "missed_calls": missed_calls,
                    "busiest_missed_hours": busiest_missed_hours,
                    "appts_booked": appts_booked,
                    "noshow_rate": noshow_rate,
                    "no_shows": no_shows,
                    "recall_calls": recall_calls,
                    "recall_answered": recall_answered,
                    "recall_booked": recall_booked,
                    "recall_revenue": recall_revenue,
                    "referral_conversions": referral_conversions
                }
            }
            supabase.table("ai_insights").insert(db_insert).execute()
            print(f"[InsightsService] Weekly cached insights for clinic: {clinic_id}")
            return ai_summary

        except Exception as e:
            print(f"[InsightsService.generate_weekly_insights] Error: {e}")
            return None

    async def generate_and_email_weekly_insights(self, clinic_id: str) -> bool:
        """
        Generates insights and dispatches them directly to the clinic owner's inbox.
        """
        try:
            # Generate markdown report
            summary = await self.generate_weekly_insights(clinic_id)
            if not summary:
                return False

            # Get owner email
            res = supabase.table("clinics").select("name, owner_email").eq("id", clinic_id).single().execute()
            if not res.data or not res.data.get("owner_email"):
                return False
            
            clinic_name = res.data["name"]
            owner_email = res.data["owner_email"]

            # Convert basic markdown summary to HTML for email body
            import markdown
            html_content = markdown.markdown(summary)

            email_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
                <div style="background-color: #1a3a2e; padding: 25px; border-radius: 12px 12px 0 0; text-align: center; color: white;">
                    <h1 style="margin: 0; font-size: 22px;">Bytelytic OS</h1>
                    <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.85;">Your Weekly Operations & AI Insights Report</p>
                </div>
                
                <div style="padding: 25px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px; line-height: 1.6;">
                    <p>Hello {clinic_name} Admin,</p>
                    <p>Here are your automated operational insights and AI recommendations for the previous week:</p>
                    
                    <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #396a00;">
                        {html_content}
                    </div>
                    
                    <p>To view detailed analytics charts, heatmaps, and schedule optimization controls, log in to your dashboard.</p>
                    
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{settings.DASHBOARD_URL or 'https://dashboard-two-jade-54.vercel.app'}" style="display: inline-block; background-color: #396a00; color: white; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: bold;">Access Analytics Dashboard</a>
                    </div>
                </div>
                
                <p style="color: #9ca3af; font-size: 11px; text-align: center; margin-top: 20px;">Bytelytic OS · Answering calls, booking patients 24/7</p>
            </div>
            """

            await email_service._send_email_async(
                from_email="Bytelytic AI <insights@bytelytic.com>",
                to_emails=[owner_email],
                subject="📊 Weekly AI Insights & Operational Report",
                html_body=email_body
            )
            print(f"[InsightsService] Emailed weekly insights to {owner_email}")
            return True
        except Exception as e:
            print(f"[InsightsService.generate_and_email_weekly_insights] Email failed: {e}")
            return False

insights_service = InsightsService()
