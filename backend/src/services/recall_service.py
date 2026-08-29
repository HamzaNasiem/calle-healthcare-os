import datetime
from typing import Dict, Any

from ..core.database import supabase
from ..core.config import settings
from .voice_service import voice_service

class RecallService:
    async def get_recall_candidates(self, clinic_id: str) -> Dict[str, Any]:
        try:
            res = supabase.table("clinics").select("recall_days, timezone, notifications_config, business_hours").eq("id", clinic_id).single().execute()
            if not res.data:
                raise Exception(f"Clinic {clinic_id} not found")
                
            # Check clinic notifications_config preference
            c_conf = res.data.get("notifications_config")
            if not isinstance(c_conf, dict):
                b_hrs = res.data.get("business_hours") or {}
                c_conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
            if isinstance(c_conf, dict) and c_conf.get("recall_enabled") is False:
                print(f"[recall.get_candidates] Recall outbound disabled for clinic {clinic_id}. Skipping.")
                return {"success": True, "data": []}

            recall_days = res.data.get("recall_days") or [30, 60, 90]
            clinic_tz = res.data.get("timezone", "America/Chicago")
            
            # Premium Timezone Aware Date Calculation
            try:
                from zoneinfo import ZoneInfo
                today = datetime.datetime.now(ZoneInfo(clinic_tz))
            except Exception as tz_err:
                print(f"[recall.get_candidates] ZoneInfo error: {str(tz_err)}, falling back to local system time.")
                today = datetime.datetime.now()
                
            candidates = []
            
            for days in recall_days:
                target_date = today - datetime.timedelta(days=days)
                date_str = target_date.strftime("%Y-%m-%d")
                
                pat_res = supabase.table("patients").select("id, name, phone, last_visit_date, churn_risk_score, is_vip").eq("clinic_id", clinic_id).eq("last_visit_date", date_str).eq("recall_opted_out", False).execute()
                
                if pat_res.data:
                    for p in pat_res.data:
                        candidates.append({**p, "daysSinceVisit": days})
                        
            # Sort candidates: VIPs first, then by churn_risk_score descending
            candidates.sort(key=lambda x: (1 if x.get("is_vip") else 0, x.get("churn_risk_score") or 0.0), reverse=True)
            
            print(f"[recall.get_candidates] clinicId={clinic_id} found={len(candidates)}")
            return {"success": True, "data": candidates}
        except Exception as e:
            print(f"[recall.get_candidates] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def initiate_recall(self, clinic_id: str, patient_id: str) -> Dict[str, Any]:
        try:
            res = supabase.table("patients").select("name, phone").eq("id", patient_id).eq("clinic_id", clinic_id).execute()
            if not res.data:
                raise Exception(f"Patient {patient_id} not found for clinic {clinic_id}")
                
            if isinstance(res.data, list):
                patient = res.data[0] if len(res.data) > 0 else {}
            elif isinstance(res.data, dict):
                patient = res.data
            else:
                patient = {}

            if not patient.get("phone"):
                raise Exception(f"Patient {patient_id} has no valid phone number on file.")
            
            job_res = supabase.table("jobs").insert({
                "clinic_id": clinic_id,
                "job_type": "recall_call",
                "payload": {"patientId": patient_id, "patientName": patient.get("name", "Patient"), "phone": patient.get("phone")},
                "status": "pending"
            }).execute()
            
            if isinstance(job_res.data, list) and len(job_res.data) > 0:
                job_id = job_res.data[0].get("id")
            elif isinstance(job_res.data, dict):
                job_id = job_res.data.get("id")
            else:
                job_id = None
            
            from .calle_service import calle_service
            import uuid
            idem_key = f"recall_{patient_id}_{uuid.uuid4().hex[:8]}"
            webhook_url = f"{getattr(settings, 'BASE_URL', 'http://127.0.0.1:8000')}/api/v1/calle/webhook"

            clinic_name = "Medical Clinic"
            try:
                c_res = supabase.table("clinics").select("name").eq("id", clinic_id).execute()
                if c_res.data:
                    if isinstance(c_res.data, list) and len(c_res.data) > 0:
                        clinic_name = c_res.data[0].get("name") or clinic_name
                    elif isinstance(c_res.data, dict):
                        clinic_name = c_res.data.get("name") or clinic_name
            except Exception:
                pass

            call_res = await calle_service.recall_call(
                phone=patient["phone"],
                clinic_name=clinic_name,
                days_since_last_visit=90,
                recall_type="preventive care",
                idempotency_key=idem_key,
                webhook_url=webhook_url,
                wait_for_completion=False
            )
            
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            if not call_res:
                if job_id:
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": "CALL-E recall dispatch failed",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
                return {"success": False, "error": "CALL-E recall dispatch failed"}
                
            call_id = call_res.get("id") or call_res.get("call_id") or "calle_recall_active"
            if job_id:
                supabase.table("jobs").update({
                    "status": "done",
                    "ran_at": now_iso
                }).eq("id", job_id).execute()
            
            return {"success": True, "data": {"jobId": job_id, "callId": call_id, "calle": call_res}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_recall_outcome(self, clinic_id: str, retell_call_id: str, outcome: str) -> Dict[str, Any]:
        try:
            res = supabase.table("calls").select("id, appointment_id, patient_id, clinic_id").eq("retell_call_id", retell_call_id).single().execute()
            call = res.data
            if not call:
                raise Exception(f"Call {retell_call_id} not found")
                
            resolved_clinic_id = clinic_id or call.get("clinic_id")
            
            supabase.table("calls").update({"outcome": outcome}).eq("retell_call_id", retell_call_id).execute()
            
            if outcome == "booked" and call.get("appointment_id") and resolved_clinic_id:
                clinic_res = supabase.table("clinics").select("monthly_revenue_per_visit").eq("id", resolved_clinic_id).single().execute()
                amount = 15000  # Default $150 in cents
                if clinic_res.data:
                    amount = (clinic_res.data.get("monthly_revenue_per_visit") or 150) * 100
                
                from .revenue_service import revenue_service
                await revenue_service.record_event(
                    clinic_id=resolved_clinic_id,
                    event_type="recall_booked",
                    amount_cents=amount,
                    appointment_id=call["appointment_id"],
                    description="Patient recalled via AI outbound call"
                )
                
            return {"success": True, "data": {"outcome": outcome}}
        except Exception as e:
            print(f"[recall.process_outcome] Error: {str(e)}")
            return {"success": False, "error": str(e)}

recall_service = RecallService()
