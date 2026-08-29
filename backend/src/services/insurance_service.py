import datetime
from typing import Dict, Any

from ..core.database import supabase
from .sms_service import sms_service

class InsuranceService:
    async def get_verification_candidates(self, clinic_id: str) -> Dict[str, Any]:
        try:
            # Fetch clinic timezone for world-class local date matching
            res_clinic = supabase.table("clinics").select("timezone").eq("id", clinic_id).single().execute()
            clinic_tz = res_clinic.data.get("timezone", "America/Chicago") if res_clinic.data else "America/Chicago"
            
            try:
                from zoneinfo import ZoneInfo
                local_now = datetime.datetime.now(ZoneInfo(clinic_tz))
            except Exception as tz_err:
                print(f"[insurance.get_candidates] ZoneInfo error: {str(tz_err)}, falling back to local time.")
                local_now = datetime.datetime.now(datetime.timezone.utc)
                
            in48h = local_now + datetime.timedelta(hours=48)
            
            res = supabase.table("appointments").select("id, patient_name, patient_phone, appointment_type, datetime, patient_id, patients(insurance_provider, insurance_member_id)")\
                .eq("clinic_id", clinic_id).in_("status", ["scheduled", "confirmed"]).eq("insurance_verified", False)\
                .gte("datetime", local_now.isoformat()).lte("datetime", in48h.isoformat()).execute()
                
            candidates = [a for a in (res.data or []) if a.get("patients", {}).get("insurance_provider")]
            return {"success": True, "data": candidates}
        except Exception as e:
            print(f"[insurance.get_verification_candidates] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def send_verification_request(self, clinic_id: str, appointment_id: str) -> Dict[str, Any]:
        try:
            res = supabase.table("appointments").select("id, patient_name, patient_phone, appointment_type, datetime, patient_id, patients(insurance_provider)")\
                .eq("id", appointment_id).eq("clinic_id", clinic_id).single().execute()
                
            if not res.data:
                raise Exception(f"Appointment {appointment_id} not found")
                
            appt = res.data
            appt_dt = datetime.datetime.fromisoformat(appt["datetime"].replace("Z", "+00:00"))
            formatted_date = appt_dt.strftime("%A, %B %d")
            
            provider = appt.get("patients", {}).get("insurance_provider", "your insurance")
            
            # World-Class specification matching message body
            body = f"Hi {appt['patient_name']}! Confirming your {provider} is active for your visit on {formatted_date}. Reply YES to confirm."
            
            sms_res = await sms_service.send(
                clinic_id=clinic_id,
                to=appt["patient_phone"],
                body=body,
                sms_type="insurance",
                appointment_id=appointment_id,
                patient_id=appt.get("patient_id")
            )
            return sms_res
        except Exception as e:
            print(f"[insurance.send_verification_request] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_verifications(self, clinic_id: str) -> Dict[str, Any]:
        try:
            # Check clinic notifications_config preference
            res_c = supabase.table("clinics").select("notifications_config, business_hours").eq("id", clinic_id).single().execute()
            if res_c.data:
                c_conf = res_c.data.get("notifications_config")
                if not isinstance(c_conf, dict):
                    b_hrs = res_c.data.get("business_hours") or {}
                    c_conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
                if isinstance(c_conf, dict) and c_conf.get("insurance_enabled") is False:
                    print(f"[insurance.process_verifications] Insurance verification SMS disabled for clinic {clinic_id}. Skipping.")
                    return {"success": True, "skipped": True, "data": {"sent": 0, "failed": 0, "reason": "insurance_disabled"}}

            candidates_res = await self.get_verification_candidates(clinic_id)
            if not candidates_res.get("success"):
                return candidates_res
                
            results = {"sent": 0, "failed": 0}
            for appt in candidates_res.get("data", []):
                res = await self.send_verification_request(clinic_id, appt["id"])
                if res.get("success"):
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    
            print(f"[insurance.process_verifications] clinicId={clinic_id} sent={results['sent']} failed={results['failed']}")
            return {"success": True, "data": results}
        except Exception as e:
            print(f"[insurance.process_verifications] Error: {str(e)}")
            return {"success": False, "error": str(e)}

insurance_service = InsuranceService()
