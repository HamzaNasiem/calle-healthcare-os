import json
import datetime
from typing import Dict, Any

from ..core.database import supabase
from .ai_service import ai_service
from .voice_service import voice_service
from .sms_service import sms_service

class NoshowService:
    async def predict_noshows(self, clinic_id: str, date_str: str) -> Dict[str, Any]:
        try:
            date_obj = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            tz = date_obj.tzinfo or datetime.timezone.utc
            local_start = datetime.datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0, tzinfo=tz)
            local_end = datetime.datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59, 999999, tzinfo=tz)
            day_start = local_start.astimezone(datetime.timezone.utc).isoformat()
            day_end = local_end.astimezone(datetime.timezone.utc).isoformat()
            
            res = supabase.table("appointments").select("id, patient_name, patient_phone, appointment_type, datetime, status, patients(no_show_count, total_visits, preferred_time)").eq("clinic_id", clinic_id).in_("status", ["scheduled", "confirmed"]).gte("datetime", day_start).lte("datetime", day_end).execute()
            
            appointments = res.data or []
            if not appointments:
                return {"success": True, "data": []}
                
            # Add day_of_week and time_of_day helper attributes for world-class AI scoring
            for appt in appointments:
                try:
                    dt = datetime.datetime.fromisoformat(appt["datetime"].replace("Z", "+00:00"))
                    appt["day_of_week"] = dt.strftime("%A")
                    appt["time_of_day"] = dt.strftime("%I:%M %p")
                except Exception:
                    pass
                
            prompt = f"""You are predicting no-show risk for a physical therapy clinic.

Appointments:
{json.dumps(appointments, indent=2)}

Score each appointment's no-show risk from 0.0 to 1.0 based on:
- Patient no_show_count vs total_visits ratio (higher ratio = more risk)
- Early morning slots before 9am local time have higher risk
- Patients with 0 prior visits (new patients) have moderate-high risk
- Discrepancy between appointment time and patient's preferred_time has moderate risk

Return a JSON array only (no markdown):
[
  {{ "appointmentId": "<uuid>", "riskScore": 0.0, "reason": "<brief>" }}
]"""

            ai_res = await ai_service.chat([{"role": "user", "content": prompt}], max_tokens=800)
            
            try:
                cleaned = ai_res.replace("```json", "").replace("```", "").strip()
                scores = json.loads(cleaned)
            except:
                scores = []
                
            scores.sort(key=lambda x: x.get("riskScore", 0), reverse=True)
            
            print(f"[noshow.predict_noshows] clinicId={clinic_id} scored={len(scores)}")
            return {"success": True, "data": scores}
        except Exception as e:
            print(f"[noshow.predict_noshows] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_noshow_confirmations(self, clinic_id: str, date_str: str) -> Dict[str, Any]:
        try:
            # 1. Run predictions
            pred_res = await self.predict_noshows(clinic_id, date_str)
            if not pred_res.get("success"):
                return pred_res
                
            scores = pred_res.get("data", [])
            if not scores:
                return {"success": True, "data": {"processed": 0, "confirmations": {"sent": 0, "failed": 0}}}
                
            # 2. Update scores in DB
            for score in scores:
                supabase.table("appointments").update({
                    "noshow_risk": score["riskScore"]
                }).eq("id", score["appointmentId"]).eq("clinic_id", clinic_id).execute()
                
            # 3. Filter top 3 high-risk (riskScore >= 0.5)
            high_risk_scores = [s for s in scores if s.get("riskScore", 0) >= 0.5]
            top_3 = high_risk_scores[:3]
            
            results = {"sent": 0, "failed": 0}
            
            for candidate in top_3:
                appt_id = candidate["appointmentId"]
                risk = candidate["riskScore"]
                
                # Fetch appointment info
                appt_res = supabase.table("appointments").select("*, patients(name, phone)").eq("id", appt_id).eq("clinic_id", clinic_id).single().execute()
                if not appt_res.data:
                    continue
                    
                appt = appt_res.data
                patient = appt.get("patients", {})
                phone = appt.get("patient_phone") or patient.get("phone")
                
                if not phone:
                    continue
                    
                dt = datetime.datetime.fromisoformat(appt["datetime"].replace("Z", "+00:00"))
                time_str = dt.strftime("%I:%M %p")
                date_str_formatted = dt.strftime("%A, %b %d")
                
                # Log job record before action (crash-safe!)
                job_res = supabase.table("jobs").insert({
                    "clinic_id": clinic_id,
                    "job_type": "noshow_confirmation_sms",
                    "payload": {
                        "appointmentId": appt_id,
                        "patientName": appt["patient_name"],
                        "phone": phone,
                        "riskScore": risk,
                        "datetime": appt["datetime"]
                    },
                    "status": "pending"
                }).execute()
                
                job_id = job_res.data[0]["id"] if job_res.data else None
                
                body = (f"Hi {appt['patient_name']}, this is an urgent confirmation for your appointment "
                        f"at {time_str} on {date_str_formatted}. As this is a high-demand slot, please "
                        f"reply YES to confirm you will attend. Thank you!")
                
                # Send SMS
                sms_res = await sms_service.send(
                    clinic_id=clinic_id,
                    to=phone,
                    body=body,
                    sms_type="confirmation",
                    appointment_id=appt_id,
                    patient_id=appt.get("patient_id")
                )
                
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                if sms_res.get("success"):
                    results["sent"] += 1
                    if job_id:
                        supabase.table("jobs").update({
                            "status": "done",
                            "ran_at": now_iso
                        }).eq("id", job_id).execute()
                else:
                    results["failed"] += 1
                    if job_id:
                        supabase.table("jobs").update({
                            "status": "failed",
                            "error_message": sms_res.get("error"),
                            "ran_at": now_iso
                        }).eq("id", job_id).execute()
                        
            return {"success": True, "data": {"processed": len(scores), "confirmations": results}}
        except Exception as e:
            print(f"[noshow.process_confirmations] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def fill_from_waitlist(self, clinic_id: str, slot: str) -> Dict[str, Any]:
        try:
            res = supabase.table("patients").select("id, name, phone").eq("clinic_id", clinic_id).eq("recall_opted_out", False).not_.is_("last_visit_date", "null").order("last_visit_date", desc=False).limit(5).execute()
            
            patients = res.data or []
            if not patients:
                return {"success": True, "data": {"filled": False, "reason": "no_waitlist_candidates"}}
                
            for patient in patients:
                call_res = await voice_service.make_outbound_call(
                    clinic_id=clinic_id,
                    phone=patient["phone"],
                    call_type="recall",
                    data={
                        "patientId": patient["id"],
                        "patientName": patient["name"],
                        "slotDatetime": slot,
                        "message": "slot_available"
                    }
                )
                
                if call_res.get("success"):
                    print(f"[noshow.fill_from_waitlist] clinicId={clinic_id} patientId={patient['id']} callId={call_res['data']['callId']}")
                    return {
                        "success": True,
                        "data": {
                            "filled": True,
                            "patientId": patient["id"],
                            "callId": call_res["data"]["callId"]
                        }
                    }
            
            return {"success": True, "data": {"filled": False, "reason": "all_calls_failed"}}
        except Exception as e:
            print(f"[noshow.fill_from_waitlist] Error: {str(e)}")
            return {"success": False, "error": str(e)}

noshow_service = NoshowService()
