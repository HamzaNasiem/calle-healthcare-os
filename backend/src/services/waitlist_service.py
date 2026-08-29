import datetime
from typing import Dict, Any

from ..core.database import supabase, supabase_read
from .voice_service import voice_service

class WaitlistService:
    async def get_waitlist_candidates(self, clinic_id: str, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        try:
            offset = (page - 1) * limit
            res = supabase_read.table("waitlist").select(
                "id, clinic_id, patient_id, appointment_type, preferred_dates, status, created_at, patients(name, phone)",
                count="exact"
            ).eq("clinic_id", clinic_id).eq("status", "pending").order("created_at", desc=False).range(offset, offset + limit - 1).execute()
            return {"success": True, "data": res.data or [], "total": res.count or 0}
        except Exception as e:
            print(f"[waitlist.get_candidates] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def offer_slot(self, clinic_id: str, waitlist_id: str, date_str: str) -> Dict[str, Any]:
        try:
            res = supabase_read.table("waitlist").select("id, patient_id, appointment_type, patients(name, phone)")\
                .eq("id", waitlist_id).eq("clinic_id", clinic_id).single().execute()
                
            if not res.data:
                raise Exception(f"Waitlist entry {waitlist_id} not found")
                
            entry = res.data
            patient = entry.get("patients", {})
            
            job_res = supabase.table("jobs").insert({
                "clinic_id": clinic_id,
                "job_type": "waitlist_offer",
                "payload": {
                    "waitlistId": waitlist_id,
                    "patientId": entry.get("patient_id"),
                    "patientName": patient.get("name"),
                    "phone": patient.get("phone"),
                    "offeredSlot": date_str,
                    "appointmentType": entry.get("appointment_type")
                },
                "status": "pending"
            }).execute()
            
            job_id = job_res.data[0]["id"] if job_res.data else None
            
            call_res = await voice_service.make_outbound_call(
                clinic_id=clinic_id,
                phone=patient.get("phone"),
                call_type="waitlist_offer",
                data={
                    "patientId": entry.get("patient_id"),
                    "patientName": patient.get("name"),
                    "offeredSlot": date_str,
                    "appointmentType": entry.get("appointment_type"),
                    "waitlistId": waitlist_id
                }
            )
            
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            if not call_res.get("success"):
                if job_id:
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": call_res.get("error"),
                        "ran_at": now_iso
                     }).eq("id", job_id).execute()
                return {"success": False, "error": call_res.get("error")}
                
            if job_id:
                supabase.table("jobs").update({
                    "status": "done",
                    "ran_at": now_iso
                }).eq("id", job_id).execute()
            
            return {"success": True, "data": {"jobId": job_id, "callId": call_res["data"]["callId"]}}
        except Exception as e:
            print(f"[waitlist.offer_slot] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_offer_outcome(self, clinic_id: str, retell_call_id: str, outcome: str, waitlist_id: str) -> Dict[str, Any]:
        try:
            call_res = supabase_read.table("calls").select("id, appointment_id, clinic_id").eq("retell_call_id", retell_call_id).single().execute()
            if not call_res.data:
                raise Exception(f"Call {retell_call_id} not found")
                
            call = call_res.data
            resolved_clinic_id = clinic_id or call.get("clinic_id")
            
            supabase.table("calls").update({"outcome": outcome}).eq("retell_call_id", retell_call_id).execute()
            
            if outcome == "booked":
                supabase.table("waitlist").update({"status": "fulfilled"}).eq("id", waitlist_id).execute()
                
                if call.get("appointment_id") and resolved_clinic_id:
                    clinic_res = supabase_read.table("clinics").select("monthly_revenue_per_visit").eq("id", resolved_clinic_id).single().execute()
                    amount_cents = 15000  # Default $150 in cents
                    if clinic_res.data:
                        amount_cents = (clinic_res.data.get("monthly_revenue_per_visit") or 150) * 100
                    
                    from .revenue_service import revenue_service
                    await revenue_service.record_event(
                        clinic_id=resolved_clinic_id,
                        event_type="noshow_slot_filled",
                        amount_cents=amount_cents,
                        appointment_id=call.get("appointment_id"),
                        description="Waitlist slot filled via AI outbound call"
                    )
                    
            return {"success": True, "data": {"outcome": outcome}}
        except Exception as e:
            print(f"[waitlist.process_outcome] Error: {str(e)}")
            return {"success": False, "error": str(e)}

waitlist_service = WaitlistService()

