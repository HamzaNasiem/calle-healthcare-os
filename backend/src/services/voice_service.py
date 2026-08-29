"""
⚠️  DEPRECATED — DO NOT USE IN NEW CODE ⚠️
===========================================
This file (voice_service.py) is a LEGACY service that uses the old Supabase REST client
(supabase.table("clinics")) and conflicts with the current SQLAlchemy-based architecture.

PROBLEM: The real-time inbound call flow is handled by:
  - backend/src/webhooks/retell.py  (Retell webhook handler)
  - backend/src/tools/appointments.py  (AI tool calling: book, cancel, reschedule)

If voice_service.py runs alongside the retell webhook tools, DUPLICATE BOOKINGS will occur.

STATUS: This file is kept for reference only. Do NOT import VoiceService in new code.
        The outbound dialing/prompt building functionality should be migrated to
        the new SQLAlchemy-based services using the proper Tenant/Provider models.

AUDIT DATE: 2026-08-16 — Identified in 5-agent comprehensive code audit.
"""
import json
import datetime
from typing import Dict, Any, Optional
from ..core.config import settings
from ..core.database import supabase
from .ai_service import ai_service
from .calendar_service import calendar_service
from .revenue_service import revenue_service
from .sms_service import sms_service
from .connectors.voice_provider_factory import VoiceProviderFactory


class VoiceService:
    def __init__(self):
        self.provider = VoiceProviderFactory.get_provider()
    async def create_agent(self, clinic_id: str) -> Dict[str, Any]:
        """Create a personalized Voice AI agent for this clinic."""
        try:
            # Fetch full clinic data for personalized prompt
            res = supabase.table("clinics").select(
                "name, specialty, city, timezone, primary_doctor_name, "
                "primary_doctor_credentials, primary_doctor_phone, npi_number, medical_license, business_hours, appointment_types"
            ).eq("id", clinic_id).single().execute()
            clinic = res.data or {}
            
            prompt = self.build_agent_prompt(clinic)
            clinic_name = clinic.get("name", "Clinic")
            
            # Get the webhook URL for notifications
            webhook_base = settings.WEBHOOK_BASE_URL or settings.API_BASE_URL
            webhook_url = f"{webhook_base}/webhooks/retell/"
            
            # Delegate to voice provider connector
            agent_id = await self.provider.create_agent(
                clinic_name=clinic_name,
                prompt=prompt,
                webhook_url=webhook_url
            )
            
            return {"success": True, "data": {"agentId": agent_id}}
        except Exception as e:
            print(f"[voice.create_agent] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def update_agent_prompt(self, clinic_id: str) -> Dict[str, Any]:
        """Update the prompt of the AI agent for a clinic if it exists."""
        try:
            # 1. Fetch clinic details from DB
            res = supabase.table("clinics").select(
                "name, specialty, city, timezone, primary_doctor_name, "
                "primary_doctor_credentials, primary_doctor_phone, npi_number, medical_license, business_hours, appointment_types, retell_agent_id"
            ).eq("id", clinic_id).single().execute()
            
            if not res.data:
                return {"success": False, "error": "Clinic not found"}
                
            clinic = res.data
            agent_id = clinic.get("retell_agent_id")
            if not agent_id:
                # No agent has been provisioned yet.
                return {"success": True, "message": "No Retell agent provisioned yet for this clinic."}
                
            # 2. Build the new prompt
            new_prompt = self.build_agent_prompt(clinic)
            
            # 3. Update the agent prompt via voice provider connector
            await self.provider.update_agent(agent_id, new_prompt)
            
            return {"success": True, "data": {"agentId": agent_id}}
        except Exception as e:
            print(f"[voice.update_agent_prompt] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    def build_agent_prompt(self, clinic: dict) -> str:
        """Build a personalized system prompt for the Retell AI agent based on clinic data."""
        name = clinic.get("name", "the clinic")
        doctor = clinic.get("primary_doctor_name") or "our doctor"
        credentials = clinic.get("primary_doctor_credentials") or ""
        specialty = clinic.get("specialty") or "healthcare"
        city = clinic.get("city") or "your city"
        tz = clinic.get("timezone") or "America/Chicago"
        hours_raw = clinic.get("business_hours") or {}
        if isinstance(hours_raw, str):
            try:
                import json
                hours_raw = json.loads(hours_raw)
            except Exception:
                hours_raw = {}
        if not isinstance(hours_raw, dict):
            hours_raw = {}
        types_raw = clinic.get("appointment_types") or []
        
        # Format business hours
        day_names = {
            "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
            "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"
        }
        canonical_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        hours_lines = []
        
        for day_key in canonical_days:
            day_name = day_names[day_key]
            day_val = hours_raw.get(day_key)
            if day_val is None:
                day_val = hours_raw.get(day_name.lower())
                
            if day_val is None:
                continue
                
            if isinstance(day_val, dict):
                is_open = day_val.get("enabled", True) if "enabled" in day_val else day_val.get("open", True)
                if day_val.get("closed") is True:
                    is_open = False
                if is_open:
                    start_t = str(day_val.get("start") or "08:00").strip()
                    end_t = str(day_val.get("end") or "18:00").strip()
                    hours_lines.append(f"  {day_name}: {start_t} – {end_t}")
                else:
                    hours_lines.append(f"  {day_name}: Closed")
            elif isinstance(day_val, str):
                v_str = day_val.strip()
                if v_str.lower() in ["closed", "off", "none", ""] or not v_str:
                    hours_lines.append(f"  {day_name}: Closed")
                elif "-" in v_str or "–" in v_str:
                    clean_range = v_str.replace("–", "-")
                    parts = clean_range.split("-")
                    hours_lines.append(f"  {day_name}: {parts[0].strip()} – {parts[1].strip()}")
                else:
                    hours_lines.append(f"  {day_name}: {v_str}")

        hours_text = "\n".join(hours_lines) if hours_lines else "  Monday–Friday: 08:00 – 18:00\n  Saturday–Sunday: Closed"
        
        # Format appointment types
        type_lines = []
        for t in types_raw:
            if isinstance(t, dict):
                t_name = t.get("name", "General Appointment")
                t_dur = t.get("duration_minutes") or t.get("duration") or 30
                t_fee = t.get("fee") if t.get("fee") is not None else t.get("price")
                if t_fee is not None and float(t_fee) > 0:
                    type_lines.append(f"  - {t_name} ({t_dur} minutes, ${float(t_fee):g})")
                else:
                    type_lines.append(f"  - {t_name} ({t_dur} minutes)")
        types_text = "\n".join(type_lines) if type_lines else "  - Initial Evaluation (60 minutes, $150)\n  - Follow-up (30 minutes, $75)"
        
        if doctor.lower().startswith("dr."):
            dr_title = doctor
        elif doctor.lower().startswith("dr "):
            dr_title = "Dr. " + doctor[3:].strip()
        else:
            dr_title = f"Dr. {doctor}"
        if credentials:
            dr_title += f", {credentials}"
        
        return f"""# Identity & Tone
You are the elite AI Receptionist for {name}, a premium {specialty} clinic in {city}. Primary provider: {dr_title}.
Speak with warm, polite, and elite professional hospitality.
IMPORTANT: Speak like a real human. Keep every response under 15-20 words. Avoid long speeches, listing options, or repeating information.

# Business Hours ({tz})
{hours_text}

# Appointment Types Available
{types_text}

# Core Rules & Conversational Flow
1. Greet: Welcome caller to "{name}" and ask how to assist.
2. One Question at a Time: Gather booking/rescheduling details step-by-step:
   - First, get the patient's full name.
   - Second, get their phone number.
   - Third, get the preferred date and time (must be within business hours).
   NEVER ask for multiple pieces of info in one turn.
3. Be Concise: Keep responses extremely short. Never read lists or menus.
4. Confirm & Hang Up: Once a booking, rescheduling, or cancellation is finished, confirm the details (type, date, time) in a single sentence, ask "Is there anything else?", and if they say "no" or "goodbye", say a brief farewell and immediately call the 'end_call' tool to hang up.
5. Emergencies: If a medical emergency is mentioned, immediately direct them to hang up and call 911.

# Call Termination
- You MUST call the 'end_call' tool to hang up immediately when:
  - The conversation is finished and you have confirmed details.
  - The caller says "goodbye", "no thank you", "that's it", or asks to end the call (e.g. "hang up", "please end call").
"""


    async def make_outbound_call(self, clinic_id: str, phone: str, call_type: str, data: dict = {}) -> Dict[str, Any]:
        try:
            # Check active subscription and quota limits first
            from .usage_service import usage_service
            is_active = await usage_service.enforce_quota_limits(clinic_id)
            if not is_active:
                return {"success": False, "error": "Your clinic account is currently suspended due to quota exhaustion or expired trial."}

            res = supabase.table("clinics").select("retell_agent_id, twilio_number").eq("id", clinic_id).single().execute()
            clinic = res.data
            
            if not clinic or not clinic.get("retell_agent_id"):
                raise Exception("Clinic does not have a Retell agent configured")
                
            from_number = clinic.get("twilio_number", settings.TWILIO_DEFAULT_NUMBER)
            agent_id = clinic.get("retell_agent_id")
            
            dynamic_vars = {
                "patient_name": data.get("patientName", "Valued Patient"),
                **data
            }
            
            # Delegate call initiation to provider connector
            call_id = await self.provider.make_outbound_call(
                from_number=from_number,
                to_number=phone,
                agent_id=agent_id,
                call_type=call_type,
                dynamic_variables=dynamic_vars
            )
            
            # Create call record
            db_call_type = call_type if call_type in ['booking', 'recall', 'reminder', 'followup', 'insurance', 'general'] else 'general'
            if call_type == "waitlist_offer":
                db_call_type = "booking"
                
            supabase.table("calls").insert({
                "clinic_id": clinic_id,
                "patient_id": data.get("patientId"),
                "retell_call_id": call_id,
                "direction": "outbound",
                "call_type": db_call_type,
                "from_number": from_number,
                "to_number": phone,
                "status": "initiated"
            }).execute()
            
            return {"success": True, "data": {"callId": call_id}}
        except Exception as e:
            print(f"[voice.make_outbound_call] Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_call_event(self, event: dict) -> Dict[str, Any]:
        """
        Handles Retell webhooks (call_started, call_ended, call_analyzed).
        Includes logic to extract booking intent via OpenRouter and update database/calendar.
        """
        call_id = event.get("call_id")
        from ..core.lock import DistributedLock
        lock = DistributedLock(f"retell_call_{call_id}") if call_id else None
        try:
            if lock:
                await lock.__aenter__()
            call_id = event.get("call_id")
            call_status = event.get("call_status")
            call_type = event.get("call_type", "inbound") # usually retell passes direction or type
            from_number = event.get("from_number")
            to_number = event.get("to_number")
            record_only = event.get("_recordOnly", False)
            
            # 1. Resolve Clinic ID and Patient ID robustly
            clinic_id = None
            patient_id = None
            
            # Try to resolve by Retell Agent ID first (most robust, works for web calls and phone calls)
            agent_id = event.get("agent_id")
            if agent_id:
                try:
                    agent_res = supabase.table("clinics").select("id").eq("retell_agent_id", agent_id).execute()
                    if agent_res.data:
                        clinic_id = agent_res.data[0]["id"]
                except Exception as agent_res_err:
                    print(f"[voice.handle_call_event] Agent lookup error: {str(agent_res_err)}")
            
            # Fallback to phone number checks if agent_id resolution failed
            if not clinic_id:
                number_to_check = to_number if event.get("direction") == "inbound" else from_number
                if number_to_check:
                    try:
                        clinic_res = supabase.table("clinics").select("id").eq("twilio_number", number_to_check).execute()
                        if clinic_res.data:
                            clinic_id = clinic_res.data[0]["id"]
                        else:
                            # Try fallback checking both
                            clinic_res = supabase.table("clinics").select("id").or_(f"twilio_number.eq.{to_number},twilio_number.eq.{from_number}").execute()
                            if clinic_res.data:
                                clinic_id = clinic_res.data[0]["id"]
                    except Exception as phone_res_err:
                        print(f"[voice.handle_call_event] Phone lookup error: {str(phone_res_err)}")
            
            # Secondary fallback: Resolve from historical call record if webhook payload lacks detail (outbound campaigns)
            if not clinic_id and call_id:
                try:
                    call_record = supabase.table("calls").select("clinic_id, patient_id").eq("retell_call_id", call_id).execute()
                    if call_record.data:
                        clinic_id = call_record.data[0]["clinic_id"]
                        patient_id = call_record.data[0].get("patient_id")
                except Exception as call_rec_err:
                    print(f"[voice.handle_call_event] Historical call resolution error: {str(call_rec_err)}")
                    
            if not clinic_id:
                raise Exception(f"No clinic found for agent: {agent_id}, numbers: {to_number}/{from_number}, and call {call_id}")
            
            # Check if clinic account is suspended/inactive
            try:
                clinic_active_res = supabase.table("clinics").select("is_active").eq("id", clinic_id).single().execute()
                if clinic_active_res.data and not clinic_active_res.data.get("is_active", True):
                    # Only stop call if it is live
                    if call_status not in ["ended", "completed", "analyzed"]:
                        print(f"[voice.handle_call_event] Clinic {clinic_id} is suspended/inactive. Terminating live call {call_id} immediately.")
                        try:
                            await self.provider.stop_call(call_id)
                        except Exception as stop_err:
                            print(f"[voice.handle_call_event] Failed to invoke stop_call: {stop_err}")
                            
                        # Update/insert call record in DB
                        call_payload = {
                            "clinic_id": clinic_id,
                            "retell_call_id": call_id,
                            "status": "failed",
                            "outcome": "declined"
                        }
                        try:
                            existing_call = supabase.table("calls").select("id").eq("retell_call_id", call_id).execute()
                            if existing_call.data:
                                supabase.table("calls").update(call_payload).eq("retell_call_id", call_id).execute()
                            else:
                                call_payload["direction"] = event.get("direction", "inbound")
                                call_payload["from_number"] = from_number
                                call_payload["to_number"] = to_number
                                supabase.table("calls").insert(call_payload).execute()
                        except Exception as db_err:
                            print(f"[voice.handle_call_event] Failed to log failed call: {db_err}")
                            
                    return {"success": False, "error": "Clinic account is suspended/inactive."}
            except Exception as active_err:
                print(f"[voice.handle_call_event] Error verifying clinic active state: {active_err}")
            
            # 2. Resolve Patient if not already resolved
            patient_phone = from_number if event.get("direction") == "inbound" else to_number
            if not patient_id and patient_phone:
                patient_res = supabase.table("patients").select("id").eq("clinic_id", clinic_id).eq("phone", patient_phone).execute()
                patient_id = patient_res.data[0]["id"] if patient_res.data else None
            
            # Retrieve clinic settings (timezone and monthly revenue per visit)
            clinic_data = None
            try:
                clinic_data_res = supabase.table("clinics").select("timezone, monthly_revenue_per_visit, name").eq("id", clinic_id).single().execute()
                clinic_data = clinic_data_res.data if clinic_data_res else None
            except Exception as clinic_fetch_err:
                print(f"[voice.handle_call_event] Clinic fetch error: {str(clinic_fetch_err)}")
                
            clinic_tz = "America/Chicago"
            if clinic_data and isinstance(clinic_data, dict):
                clinic_tz = clinic_data.get("timezone", "America/Chicago")
            
            # 3. Upsert Call Record
            transcript = event.get("transcript", "")
            if isinstance(transcript, list):
                # Retell sometimes sends transcript as array of objects
                transcript_text = "\n".join([f"{t.get('role')}: {t.get('content')}" for t in transcript if isinstance(t, dict)])
            else:
                transcript_text = str(transcript)
                
            update_data = {
                "clinic_id": clinic_id,
                "retell_call_id": call_id,
                "status": "ended" if call_status in ["ended", "completed", "analyzed"] else "ongoing",
                "transcript": transcript_text,
                "recording_url": event.get("recording_url"),
                "duration_seconds": event.get("duration_ms", 0) // 1000
            }
            
            if event.get("start_timestamp"):
                update_data["started_at"] = datetime.datetime.fromtimestamp(event.get("start_timestamp") / 1000, tz=datetime.timezone.utc).isoformat()
            if event.get("end_timestamp"):
                update_data["ended_at"] = datetime.datetime.fromtimestamp(event.get("end_timestamp") / 1000, tz=datetime.timezone.utc).isoformat()
                
            if patient_id:
                update_data["patient_id"] = patient_id
                
            # Check if call exists
            existing_call = supabase.table("calls").select("id, outcome").eq("retell_call_id", call_id).execute()
            
            if existing_call.data:
                supabase.table("calls").update(update_data).eq("retell_call_id", call_id).execute()
            else:
                update_data["direction"] = event.get("direction", "inbound")
                update_data["from_number"] = from_number
                update_data["to_number"] = to_number
                try:
                    supabase.table("calls").insert(update_data).execute()
                except Exception as insert_err:
                    err_msg = str(insert_err)
                    if "duplicate key" in err_msg.lower() or "23505" in err_msg:
                        print(f"[voice.handle_call_event] Duplicate call key detected for {call_id}, falling back to update.")
                        supabase.table("calls").update(update_data).eq("retell_call_id", call_id).execute()
                    else:
                        raise insert_err
                
            try:
                from ..core.cache import invalidate_dashboard_stats
                invalidate_dashboard_stats(clinic_id)
            except Exception as cache_e:
                print(f"[voice.handle_call_event] Cache invalidation warning: {cache_e}")
                
            if record_only or not transcript_text or call_status not in ["ended", "completed", "analyzed"]:
                return {"success": True, "data": {"action": "recorded"}}
                
            # 4. Extract Booking Intent via OpenRouter
            prompt = f"""Analyze this call transcript:
{transcript_text}

Extract intent. Return ONLY JSON format:
{{
  "intent": "book|reschedule|cancel|general",
  "patient_name": "Extracted Name if provided",
  "date": "YYYY-MM-DD if mentioned",
  "time": "HH:MM if mentioned",
  "appointment_type": "string if mentioned"
}}"""
            
            ai_res = await ai_service.chat([{"role": "user", "content": prompt}], max_tokens=200)
            
            try:
                cleaned = ai_res.replace("```json", "").replace("```", "").strip()
                intent_data = json.loads(cleaned)
            except:
                return {"success": True, "data": {"action": "parse_failed"}}
                
            action = intent_data.get("intent")
            outcome = "completed"
            appt_id = None
            
            from zoneinfo import ZoneInfo
            
            if action == "book" and intent_data.get("patient_name") and intent_data.get("date") and intent_data.get("time"):
                # Create patient if not exists
                if not patient_id:
                    new_pat = supabase.table("patients").insert({
                        "clinic_id": clinic_id,
                        "name": intent_data.get("patient_name"),
                        "phone": patient_phone
                    }).execute()
                    patient_id = new_pat.data[0]["id"] if new_pat.data else None
                    
                # Premium Timezone Aware Datetime parsing
                try:
                    tz = ZoneInfo(clinic_tz)
                    naive_dt = datetime.datetime.strptime(f"{intent_data['date']}T{intent_data['time']}:00", "%Y-%m-%dT%H:%M:%S")
                    appt_dt = naive_dt.replace(tzinfo=tz)
                except Exception as tz_err:
                    print(f"[voice.handle_call_event] Timezone error on booking: {str(tz_err)}, falling back to naive UTC")
                    appt_dt = datetime.datetime.strptime(f"{intent_data['date']}T{intent_data['time']}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                
                # Resolve appointment type, duration, and fee dynamically from clinic settings
                requested_type = str(intent_data.get("appointment_type") or "Initial Evaluation").strip()
                types_list = clinic_data.get("appointment_types") if isinstance(clinic_data, dict) else []
                
                matched_type_name = requested_type
                matched_duration = 30
                matched_fee = None

                if types_list and isinstance(types_list, list):
                    for t in types_list:
                        if isinstance(t, dict):
                            t_name = str(t.get("name", "")).strip()
                            if t_name.lower() == requested_type.lower() or requested_type.lower() in t_name.lower() or t_name.lower() in requested_type.lower():
                                matched_type_name = t_name
                                matched_duration = int(t.get("duration_minutes") or t.get("duration") or 30)
                                fee_raw = t.get("fee") if t.get("fee") is not None else t.get("price")
                                if fee_raw is not None:
                                    try:
                                        matched_fee = float(fee_raw)
                                    except (ValueError, TypeError):
                                        pass
                                break
                    if matched_duration == 30 and any(k in requested_type.lower() for k in ["initial", "eval", "first", "new"]):
                        for t in types_list:
                            if isinstance(t, dict) and "initial" in str(t.get("name", "")).lower():
                                matched_type_name = t.get("name", "Initial Evaluation")
                                matched_duration = int(t.get("duration_minutes") or t.get("duration") or 60)
                                fee_raw = t.get("fee") if t.get("fee") is not None else t.get("price")
                                if fee_raw is not None:
                                    try:
                                        matched_fee = float(fee_raw)
                                    except (ValueError, TypeError):
                                        pass
                                break

                # Book in Google Calendar
                appt_dict = {
                    "patient_name": intent_data.get("patient_name"),
                    "appointment_type": matched_type_name,
                    "datetime": appt_dt.isoformat(),
                    "duration_minutes": matched_duration,
                    "notes": "Booked by Bytelytic AI Receptionist"
                }
                
                cal_res = await calendar_service.create_event(clinic_id, appt_dict)
                google_event_id = cal_res["data"]["googleEventId"] if (cal_res.get("success") and cal_res.get("data")) else None
                
                # Insert Appointment
                appt_res = supabase.table("appointments").insert({
                    "clinic_id": clinic_id,
                    "patient_id": patient_id,
                    "patient_name": intent_data.get("patient_name"),
                    "patient_phone": patient_phone,
                    "appointment_type": appt_dict["appointment_type"],
                    "datetime": appt_dt.isoformat(),
                    "duration_minutes": matched_duration,
                    "google_event_id": google_event_id,
                    "status": "scheduled",
                    "booked_by": "ai"
                }).execute()
                
                appt_id = appt_res.data[0]["id"] if appt_res.data else None
                outcome = "booked"
                
                # Trigger automatic background EHR sync
                if appt_id:
                    from .ehr.sync_service import ehr_sync_service
                    import asyncio
                    asyncio.create_task(ehr_sync_service.sync_appointment(clinic_id, appt_id))
                
                # Safe Revenue Event insertion
                fee_to_record = matched_fee if (matched_fee is not None and matched_fee > 0) else (clinic_data.get("monthly_revenue_per_visit") or 150 if isinstance(clinic_data, dict) else 150)
                amount = int(fee_to_record * 100)
                await revenue_service.record_event(clinic_id, "after_hours_booked", amount, appt_id, "AI Booked Appointment")
                
                # Send booking confirmation SMS if enabled
                try:
                    c_conf = clinic_data.get("notifications_config") if isinstance(clinic_data, dict) else {}
                    if not isinstance(c_conf, dict):
                        b_hrs = clinic_data.get("business_hours") or {} if isinstance(clinic_data, dict) else {}
                        c_conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
                    booking_sms_enabled = c_conf.get("booking_confirmation_enabled", True) if isinstance(c_conf, dict) else True
                    
                    if booking_sms_enabled:
                        time_str = appt_dt.strftime("%I:%M %p")
                        date_str = appt_dt.strftime("%A, %b %d")
                        date_time_formatted = f"{date_str} at {time_str}"
                        body = f"Hi {intent_data.get('patient_name')}, your appointment for {appt_dict['appointment_type']} has been booked for {date_time_formatted}. See you soon!"
                        await sms_service.send(
                            clinic_id=clinic_id,
                            to=patient_phone,
                            body=body,
                            sms_type="confirmation",
                            appointment_id=appt_id,
                            patient_id=patient_id
                        )
                    else:
                        print(f"[voice.handle_call_event] Booking confirmation SMS disabled for clinic {clinic_id}. Skipping.")
                except Exception as sms_err:
                    print(f"[voice.handle_call_event] Booking SMS confirmation error: {str(sms_err)}")
                
            elif action == "reschedule" and patient_id and intent_data.get("date") and intent_data.get("time"):
                # Find latest active appointment for this patient
                res_appt = supabase.table("appointments").select("id, google_event_id, appointment_type, patient_name, patient_phone").eq("clinic_id", clinic_id).eq("patient_id", patient_id).in_("status", ["scheduled", "confirmed"]).order("datetime", desc=True).limit(1).execute()
                
                if res_appt.data:
                    appt = res_appt.data[0]
                    appt_id = appt["id"]
                    
                    # Premium Timezone Aware Datetime parsing
                    try:
                        tz = ZoneInfo(clinic_tz)
                        naive_dt = datetime.datetime.strptime(f"{intent_data['date']}T{intent_data['time']}:00", "%Y-%m-%dT%H:%M:%S")
                        appt_dt = naive_dt.replace(tzinfo=tz)
                    except Exception as tz_err:
                        print(f"[voice.handle_call_event] Timezone error on rescheduling: {str(tz_err)}, falling back to naive UTC")
                        appt_dt = datetime.datetime.strptime(f"{intent_data['date']}T{intent_data['time']}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                    
                    # Update Google Calendar
                    new_event_id = None
                    if appt.get("google_event_id"):
                        try:
                            # We cancel the old event and create a new one to be robust
                            await calendar_service.cancel_event(clinic_id, appt["google_event_id"])
                            
                            new_cal_res = await calendar_service.create_event(clinic_id, {
                                "patient_name": appt["patient_name"],
                                "appointment_type": appt["appointment_type"],
                                "datetime": appt_dt.isoformat(),
                                "duration_minutes": 60,
                                "notes": "Rescheduled by Bytelytic AI Receptionist"
                            })
                            if new_cal_res.get("success") and new_cal_res.get("data"):
                                new_event_id = new_cal_res["data"]["googleEventId"]
                        except Exception as cal_err:
                            print(f"[voice.handle_call_event] Reschedule calendar error: {str(cal_err)}")
                        
                    # Update database appointment
                    update_payload = {
                        "datetime": appt_dt.isoformat(),
                        "status": "scheduled"
                    }
                    if new_event_id:
                        update_payload["google_event_id"] = new_event_id
                        
                    supabase.table("appointments").update(update_payload).eq("id", appt_id).execute()
                    outcome = "rescheduled"
                    
                    # Send rescheduling confirmation SMS if enabled
                    try:
                        c_conf = clinic_data.get("notifications_config") if isinstance(clinic_data, dict) else {}
                        if not isinstance(c_conf, dict):
                            b_hrs = clinic_data.get("business_hours") or {} if isinstance(clinic_data, dict) else {}
                            c_conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
                        cancel_sms_enabled = c_conf.get("cancellation_confirmation_enabled", True) if isinstance(c_conf, dict) else True
                        
                        if cancel_sms_enabled:
                            time_str = appt_dt.strftime("%I:%M %p")
                            date_str = appt_dt.strftime("%A, %b %d")
                            date_time_formatted = f"{date_str} at {time_str}"
                            body = f"Hi {appt['patient_name']}, your appointment has been rescheduled to {date_time_formatted}."
                            phone = appt.get("patient_phone") or patient_phone
                            if phone:
                                await sms_service.send(
                                    clinic_id=clinic_id,
                                    to=phone,
                                    body=body,
                                    sms_type="confirmation",
                                    appointment_id=appt_id,
                                    patient_id=patient_id
                                )
                    except Exception as sms_err:
                        print(f"[voice.handle_call_event] Reschedule SMS confirmation error: {str(sms_err)}")
                    
            elif action == "cancel" and patient_id:
                # Find latest active appointment for this patient
                res_appt = supabase.table("appointments").select("id, google_event_id, patient_name, patient_phone, datetime").eq("clinic_id", clinic_id).eq("patient_id", patient_id).in_("status", ["scheduled", "confirmed"]).order("datetime", desc=True).limit(1).execute()
                
                if res_appt.data:
                    appt = res_appt.data[0]
                    appt_id = appt["id"]
                    
                    # Cancel Google Calendar Event
                    if appt.get("google_event_id"):
                        try:
                            await calendar_service.cancel_event(clinic_id, appt["google_event_id"])
                        except Exception as cal_err:
                            print(f"[voice.handle_call_event] Cancel calendar error: {str(cal_err)}")
                            
                    # Update database appointment to cancelled
                    supabase.table("appointments").update({"status": "cancelled"}).eq("id", appt_id).execute()
                    outcome = "cancelled"
                    
                    # Send cancellation confirmation SMS if enabled
                    try:
                        c_conf = clinic_data.get("notifications_config") if isinstance(clinic_data, dict) else {}
                        if not isinstance(c_conf, dict):
                            b_hrs = clinic_data.get("business_hours") or {} if isinstance(clinic_data, dict) else {}
                            c_conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
                        cancel_sms_enabled = c_conf.get("cancellation_confirmation_enabled", True) if isinstance(c_conf, dict) else True
                        
                        if cancel_sms_enabled:
                            tz = ZoneInfo(clinic_tz)
                            raw_dt = datetime.datetime.fromisoformat(appt["datetime"].replace("Z", "+00:00"))
                            local_dt = raw_dt.astimezone(tz)
                            
                            date_str = local_dt.strftime("%A, %b %d")
                            time_str = local_dt.strftime("%I:%M %p")
                            date_time_formatted = f"{date_str} at {time_str}"
                            
                            body = f"Hi {appt['patient_name']}, your appointment on {date_time_formatted} has been successfully cancelled."
                            phone = appt.get("patient_phone") or patient_phone
                            if phone:
                                await sms_service.send(
                                    clinic_id=clinic_id,
                                    to=phone,
                                    body=body,
                                    sms_type="confirmation",
                                    appointment_id=appt_id,
                                    patient_id=patient_id
                                )
                    except Exception as sms_err:
                        print(f"[voice.handle_call_event] Cancel SMS confirmation error: {str(sms_err)}")
                    
            # Update Call Outcome
            if call_id:
                update_fields = {
                    "outcome": outcome,
                    "appointment_id": appt_id
                }
                if patient_id:
                    update_fields["patient_id"] = patient_id
                
                extracted_name = None
                try:
                    if 'intent_data' in locals() and isinstance(intent_data, dict):
                        extracted_name = intent_data.get("patient_name")
                except:
                    pass
                if extracted_name:
                    update_fields["patient_name"] = extracted_name
                    
                supabase.table("calls").update(update_fields).eq("retell_call_id", call_id).execute()
            
            # Enforce quota limits dynamically when call completes
            if clinic_id and call_status in ["ended", "completed", "analyzed"]:
                from .usage_service import usage_service
                await usage_service.enforce_quota_limits(clinic_id)
                
                # Trigger call completed or missed call notification
                try:
                    from .notification_service import notification_service
                    pat_name = "Unknown Patient"
                    if 'intent_data' in locals() and isinstance(intent_data, dict) and intent_data.get("patient_name"):
                        pat_name = intent_data.get("patient_name")
                    elif patient_id:
                        p_res = supabase.table("patients").select("name").eq("id", patient_id).execute()
                        if p_res.data:
                            pat_name = p_res.data[0].get("name", "Unknown Patient")
                            
                    direction_str = "Outbound" if event.get("direction") == "outbound" else "Inbound"
                    duration_seconds = event.get('duration_ms', 0) // 1000
                    duration_str = f"{duration_seconds}s"
                    
                    is_missed = outcome in ["missed", "abandoned", "failed"] or (event.get("direction") == "inbound" and duration_seconds < 5 and outcome != "booked")
                    n_type = "call.missed" if is_missed else "call.completed"
                    n_title = f"Missed Call from {pat_name}" if is_missed else f"{direction_str} Call Completed"
                    n_body = f"Missed call from {pat_name} ({patient_phone}). Follow-up required." if is_missed else f"Call with {pat_name} ended. Outcome: {outcome.upper()}. Duration: {duration_str}."
                    
                    await notification_service.create(
                        clinic_id=clinic_id,
                        notification_type=n_type,
                        title=n_title,
                        body=n_body,
                        metadata={
                            "retell_call_id": call_id,
                            "direction": event.get("direction"),
                            "duration_seconds": duration_seconds,
                            "outcome": outcome,
                            "phone": patient_phone,
                            "sentiment": intent_data.get("sentiment", "neutral") if 'intent_data' in locals() and isinstance(intent_data, dict) else "neutral"
                        },
                        resource_type="call",
                        resource_id=call_id
                    )
                except Exception as notif_err:
                    print(f"[voice.handle_call_event] Failed to trigger notification: {notif_err}")
            
            return {"success": True, "data": {"action": action, "appointmentId": appt_id, "clinicId": clinic_id}}
        except Exception as e:
            print(f"[voice.handle_call_event] Error: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            if lock and lock.acquired:
                await lock.__aexit__(None, None, None)

voice_service = VoiceService()
