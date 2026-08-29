import datetime
from typing import Dict, Any

from ..core.database import supabase
from .sms_service import sms_service

class FollowupService:
    async def get_followup_candidates(self, clinic_id: str) -> Dict[str, Any]:
        try:
            # Fetch clinic timezone for world-class local date matching
            res_clinic = supabase.table("clinics").select("timezone").eq("id", clinic_id).single().execute()
            clinic_tz = res_clinic.data.get("timezone", "America/Chicago") if res_clinic.data else "America/Chicago"
            
            try:
                from zoneinfo import ZoneInfo
                local_now = datetime.datetime.now(ZoneInfo(clinic_tz))
            except Exception as tz_err:
                print(f"[followup.get_candidates] ZoneInfo error: {str(tz_err)}, falling back to local time.")
                local_now = datetime.datetime.now()
                
            two_days_ago = local_now - datetime.timedelta(days=2)
            local_start = datetime.datetime(two_days_ago.year, two_days_ago.month, two_days_ago.day, 0, 0, 0, tzinfo=local_now.tzinfo)
            local_end = datetime.datetime(two_days_ago.year, two_days_ago.month, two_days_ago.day, 23, 59, 59, 999999, tzinfo=local_now.tzinfo)
            day_start = local_start.astimezone(datetime.timezone.utc).isoformat()
            day_end = local_end.astimezone(datetime.timezone.utc).isoformat()
            
            res = supabase.table("appointments").select("id, patient_name, patient_phone, appointment_type, datetime")\
                .eq("clinic_id", clinic_id).eq("status", "completed").eq("followup_sent", False)\
                .gte("datetime", day_start).lte("datetime", day_end).execute()
                
            appointments = res.data or []
            return {"success": True, "data": appointments}
        except Exception as e:
            print(f"[followup.get_followup_candidates] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_followups(self, clinic_id: str) -> Dict[str, Any]:
        try:
            # Check clinic notifications_config preference
            res_c = supabase.table("clinics").select("notifications_config, business_hours").eq("id", clinic_id).single().execute()
            if res_c.data:
                c_conf = res_c.data.get("notifications_config")
                if not isinstance(c_conf, dict):
                    b_hrs = res_c.data.get("business_hours") or {}
                    c_conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
                if isinstance(c_conf, dict) and c_conf.get("followup_enabled") is False:
                    print(f"[followup.process_followups] Follow-ups disabled for clinic {clinic_id}. Skipping.")
                    return {"success": True, "skipped": True, "data": {"sent": 0, "failed": 0, "reason": "followup_disabled"}}

            candidates_res = await self.get_followup_candidates(clinic_id)
            if not candidates_res.get("success"):
                return candidates_res
                
            results = {"sent": 0, "failed": 0}
            for appt in candidates_res.get("data", []):
                # World-Class specification matching message body
                body = f"Hi {appt['patient_name']}! Checking in after your {appt['appointment_type']}. How are you feeling? Reply anytime."
                
                sms_res = await sms_service.send(
                    clinic_id=clinic_id,
                    to=appt["patient_phone"],
                    body=body,
                    sms_type="followup",
                    appointment_id=appt["id"]
                )
                
                if sms_res.get("success"):
                    supabase.table("appointments").update({"followup_sent": True}).eq("id", appt["id"]).execute()
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    print(f"[followup.process_followups] clinicId={clinic_id} apptId={appt['id']} Error: {sms_res.get('error')}")
                    
            print(f"[followup.process_followups] clinicId={clinic_id} sent={results['sent']} failed={results['failed']}")
            return {"success": True, "data": results}
        except Exception as e:
            print(f"[followup.process_followups] Error: {str(e)}")
            return {"success": False, "error": str(e)}

followup_service = FollowupService()
