import datetime
import json
import re
from typing import Dict, Any, Optional, List, Union

from ..core.config import settings
from ..core.database import supabase
from ..core.security import mask_phone
from ..core.logger import log
from .ai_service import ai_service
from .connectors.base_connector import BaseSmsConnector
from .connectors.telnyx_sms_connector import TelnyxSmsConnector
from .connectors.twilio_sms_connector import TwilioSmsConnector
from .sms_templates import get_template

class SmsService:
    def __init__(self):
        self.telnyx_connector = TelnyxSmsConnector()
        self.twilio_connector = TwilioSmsConnector()
        # Default connector defaults to Telnyx for HIPAA compliance (free BAA)
        self.connector = self.get_connector()

    def get_connector(self, provider: Optional[str] = None) -> BaseSmsConnector:
        """
        Dynamically select the appropriate SMS connector.
        Prioritizes Telnyx for Healthcare BAA compliance, falling back to Twilio or configured provider.
        """
        if provider:
            p = provider.lower()
            if "telnyx" in p:
                return self.telnyx_connector
            elif "twilio" in p:
                return self.twilio_connector

        # Check configured settings or available credentials
        conf_provider = (
            getattr(settings, "SMS_PROVIDER", None) or 
            getattr(settings, "sms_provider", None) or 
            ""
        ).lower()

        if conf_provider == "twilio":
            return self.twilio_connector
        elif conf_provider == "telnyx":
            return self.telnyx_connector

        # If Telnyx API key is set, prefer Telnyx
        if getattr(settings, "TELNYX_API_KEY", None) or getattr(settings, "telnyx_api_key", None):
            return self.telnyx_connector
        
        # Fallback to Twilio if Twilio credentials exist
        if getattr(settings, "TWILIO_ACCOUNT_SID", None):
            return self.twilio_connector

        return self.telnyx_connector

    async def send(
        self,
        clinic_id: str,
        to: str,
        body: str,
        sms_type: str = "general",
        appointment_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Core SMS sending method. Resolves sender number, delegates to connector,
        and logs the message to the database with HIPAA-safe logging.
        """
        try:
            if not to:
                return {"success": False, "error": "Destination phone number is required"}

            # Standardize phone number (E.164 naive)
            normalized_to = to.strip().replace(" ", "").replace("-", "")
            if not normalized_to.startswith("+"):
                normalized_to = "+" + normalized_to.lstrip("0")

            # Check clinic status and sender number
            from_number = getattr(settings, "TELNYX_DEFAULT_NUMBER", None) or getattr(settings, "TWILIO_DEFAULT_NUMBER", "+18005550199")
            selected_provider = provider

            if clinic_id and clinic_id != "default":
                try:
                    clinic_res = supabase.table("clinics").select("is_active, telnyx_number, twilio_number, name").eq("id", clinic_id).execute()
                    if clinic_res.data:
                        clinic = clinic_res.data[0]
                        if not clinic.get("is_active", True):
                            return {
                                "success": False,
                                "error": "Your clinic account is currently suspended due to quota exhaustion or expired subscription."
                            }
                        if clinic.get("telnyx_number"):
                            from_number = clinic["telnyx_number"]
                            if not selected_provider:
                                selected_provider = "telnyx"
                        elif clinic.get("twilio_number"):
                            from_number = clinic["twilio_number"]
                            if not selected_provider:
                                selected_provider = "twilio"
                except Exception as c_err:
                    log.warning(f"[sms.send] Clinic lookup note for {clinic_id}: {c_err}")

            connector = self.get_connector(selected_provider)

            # Use connector to send the SMS
            message_sid = await connector.send_sms(
                from_number=from_number,
                to_number=normalized_to,
                body=body
            )

            # Log message to database
            try:
                supabase.table("sms_messages").insert({
                    "clinic_id": clinic_id,
                    "patient_id": patient_id,
                    "twilio_sid": message_sid,
                    "direction": "outbound",
                    "from_number": from_number,
                    "to_number": normalized_to,
                    "body": body,
                    "sms_type": sms_type,
                    "appointment_id": appointment_id,
                    "status": "sent"
                }).execute()
            except Exception as db_err:
                log.warning(f"[sms.send] Failed to log SMS record to DB: {db_err}")

            # Enforce quota limits dynamically after SMS is sent and logged
            try:
                from .usage_service import usage_service
                await usage_service.enforce_quota_limits(clinic_id)
            except Exception as quota_err:
                log.debug(f"[sms.send] Quota check note: {quota_err}")

            log.info(f"[sms.send] SMS sent successfully to {mask_phone(normalized_to)} (SID: {message_sid}, type: {sms_type})")
            return {
                "success": True,
                "data": {
                    "messageSid": message_sid,
                    "message_id": message_sid
                }
            }
        except Exception as e:
            log.error(f"[sms.send] clinicId={clinic_id} error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def send_booking_confirmation(
        self,
        phone: Optional[str] = None,
        time_str: str = "",
        provider_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        clinic_id: Optional[str] = None,
        patient_name: Optional[str] = None,
        confirmation_code: Optional[str] = None,
        appointment_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        clinic_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        High-level instant SMS handler for appointment confirmations.
        Used by the Transactional Outbox worker, telephony tools, and scheduler.
        """
        try:
            target_clinic_id = tenant_id or clinic_id or getattr(settings, "DEFAULT_CLINIC_ID", "default")
            target_phone = phone or kwargs.get("to_number") or kwargs.get("patient_phone") or ""

            # If phone is not directly provided but patient_id exists, look up patient
            lang_pref = "en"
            resolved_patient_name = patient_name

            if patient_id:
                try:
                    p_res = supabase.table("patients").select("name, phone, language_preference").eq("id", patient_id).execute()
                    if p_res.data:
                        p_row = p_res.data[0]
                        if not target_phone and p_row.get("phone"):
                            target_phone = p_row["phone"]
                        if not resolved_patient_name and p_row.get("name"):
                            resolved_patient_name = p_row["name"]
                        if p_row.get("language_preference"):
                            lang_pref = p_row["language_preference"]
                except Exception as p_err:
                    log.warning(f"[sms.send_booking_confirmation] Patient info lookup note: {p_err}")

            if not target_phone:
                log.error("[sms.send_booking_confirmation] No recipient phone number found.")
                return {"success": False, "error": "Recipient phone number is required"}

            resolved_clinic_name = clinic_name
            if not resolved_clinic_name and target_clinic_id and target_clinic_id != "default":
                try:
                    c_res = supabase.table("clinics").select("name").eq("id", target_clinic_id).execute()
                    if c_res.data and c_res.data[0].get("name"):
                        resolved_clinic_name = c_res.data[0]["name"]
                except Exception:
                    pass
            if not resolved_clinic_name:
                resolved_clinic_name = "our clinic"

            if not resolved_patient_name:
                resolved_patient_name = "there"

            provider_info = f" with {provider_name}" if provider_name else ""
            code_info = f" Confirmation Code: {confirmation_code}." if confirmation_code else ""

            try:
                template = get_template("booking_confirmation", lang=lang_pref)
                body = template.format(
                    patient_name=resolved_patient_name,
                    clinic_name=resolved_clinic_name,
                    datetime=time_str or "your scheduled appointment",
                    provider_info=provider_info,
                    code_info=code_info
                )
            except Exception:
                body = f"Hi {resolved_patient_name}, your appointment at {resolved_clinic_name} is confirmed for {time_str or 'your scheduled time'}{provider_info}.{code_info} Reply CANCEL to cancel or RESCHEDULE to change."

            return await self.send(
                clinic_id=target_clinic_id,
                to=target_phone,
                body=body,
                sms_type="appointment_confirmation",
                appointment_id=appointment_id,
                patient_id=patient_id
            )
        except Exception as e:
            log.error(f"[sms.send_booking_confirmation] Failed to send confirmation: {e}")
            return {"success": False, "error": str(e)}

    async def send_live_link_sms(
        self,
        phone: Optional[str] = None,
        link_type: str = "intake_form",
        url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        clinic_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Sends an instant SMS with a clickable action link (e.g. intake form, directions, payment)
        during or immediately following a live phone call.
        """
        try:
            target_clinic_id = tenant_id or clinic_id or getattr(settings, "DEFAULT_CLINIC_ID", "default")
            target_phone = phone or kwargs.get("to_number") or kwargs.get("patient_phone") or ""

            if not target_phone and patient_id:
                try:
                    p_res = supabase.table("patients").select("phone").eq("id", patient_id).execute()
                    if p_res.data and p_res.data[0].get("phone"):
                        target_phone = p_res.data[0]["phone"]
                except Exception as p_err:
                    log.warning(f"[sms.send_live_link_sms] Patient phone lookup note: {p_err}")

            if not target_phone:
                log.error("[sms.send_live_link_sms] Missing target phone number.")
                return {"success": False, "error": "Recipient phone number is required"}

            resolved_url = url
            if not resolved_url:
                resolved_url = f"https://forms.bytelytic.com/{target_clinic_id}/{link_type}"

            if link_type == "intake_form":
                body = f"Please complete your medical intake form before your visit: {resolved_url}"
            elif link_type == "payment_url":
                body = f"Here is the secure link to complete your payment: {resolved_url}"
            elif link_type in ["address_map", "directions"]:
                body = f"Here are the directions to our clinic: {resolved_url}"
            elif link_type == "confirmation_page":
                body = f"View your appointment details and confirmation here: {resolved_url}"
            else:
                body = f"Here is the link requested during your call: {resolved_url}"

            return await self.send(
                clinic_id=target_clinic_id,
                to=target_phone,
                body=body,
                sms_type="live_link",
                patient_id=patient_id
            )
        except Exception as e:
            log.error(f"[sms.send_live_link_sms] Failed to send live link: {e}")
            return {"success": False, "error": str(e)}

    async def send_sms(
        self,
        db=None,
        tenant_id: Optional[str] = None,
        to_number: str = "",
        message_body: str = "",
        sms_type: str = "general",
        patient_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        clinic_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Unified alias matching SMSOutboxWorker and legacy service calls.
        """
        target_clinic = tenant_id or clinic_id or getattr(settings, "DEFAULT_CLINIC_ID", "default")
        return await self.send(
            clinic_id=target_clinic,
            to=to_number,
            body=message_body,
            sms_type=sms_type,
            appointment_id=appointment_id,
            patient_id=patient_id
        )

    async def generate_confirmation_message(self, db, tenant_id: str, payload: dict) -> str:
        """Helper generator for appointment confirmation SMS bodies."""
        patient_name = payload.get("patient_name", "Patient")
        apt_date = payload.get("apt_date") or payload.get("date", "")
        apt_time = payload.get("apt_time") or payload.get("time", "")
        datetime_str = f"{apt_date} at {apt_time}" if apt_date and apt_time else (apt_time or apt_date or "your scheduled time")
        provider_name = payload.get("provider_name", "our clinic")
        code = payload.get("confirmation_code")
        code_str = f" Confirmation code: {code}." if code else ""
        return f"Hi {patient_name}, your appointment is confirmed for {datetime_str} with {provider_name}.{code_str} Reply CANCEL to cancel or RESCHEDULE to change."

    async def generate_reminder_message(self, db, tenant_id: str, payload: dict) -> str:
        """Helper generator for 24h reminder SMS bodies."""
        patient_name = payload.get("patient_name", "Patient")
        apt_time = payload.get("apt_time", "tomorrow")
        provider = payload.get("provider_name", "our provider")
        return f"Reminder for {patient_name}: You have an appointment at {apt_time} with {provider}. Please reply YES to confirm or call us to reschedule."

    async def generate_live_link_message(self, db, tenant_id: str, payload: dict) -> str:
        """Helper generator for live action link SMS bodies."""
        link_type = payload.get("link_type", "intake_form")
        url = payload.get("url", f"https://forms.bytelytic.com/{tenant_id}/{link_type}")
        if link_type == "intake_form":
            return f"Please complete your medical intake form: {url}"
        elif link_type == "payment_url":
            return f"Here is the secure payment link: {url}"
        return f"Here is the link requested during your call: {url}"

    async def generate_waitlist_message(self, db, tenant_id: str, payload: dict) -> str:
        """Helper generator for waitlist offer SMS bodies."""
        day = payload.get("day", "an upcoming date")
        time_slot = payload.get("time", "a slot")
        service = payload.get("service_type", "appointment")
        return f"Good news! A {service} slot opened on {day} at {time_slot}. Reply YES to claim it!"

    async def send_reminder(self, appointment_id: str) -> Dict[str, Any]:
        """
        Sends an automated appointment reminder using bilingual templates.
        """
        try:
            res = supabase.table("appointments").select("*, patients(name, phone)").eq("id", appointment_id).single().execute()
            appt = res.data
            if not appt:
                raise Exception(f"Appointment {appointment_id} not found")
                
            clinic_id = appt["clinic_id"]

            # Check clinic notifications_config preference and TCPA quiet hours
            c_conf = {}
            clinic_name = "your clinic"
            try:
                clinic_res = supabase.table("clinics").select("name, timezone, notifications_config, business_hours").eq("id", clinic_id).single().execute()
                if clinic_res.data:
                    c_data = clinic_res.data
                    clinic_name = c_data.get("name") or "your clinic"
                    c_conf = c_data.get("notifications_config")
                    if not isinstance(c_conf, dict):
                        b_hours = c_data.get("business_hours") or {}
                        c_conf = b_hours.get("_notifications_config") if isinstance(b_hours, dict) else {}
                    if not isinstance(c_conf, dict):
                        c_conf = {}

                    if c_conf.get("reminders_enabled") is False:
                        log.info(f"[sms.send_reminder] Reminders disabled for clinic {clinic_id}. Skipping.")
                        return {"success": True, "skipped": True, "reason": "reminders_disabled"}

                    # TCPA & Quiet Hours Enforcement
                    from .tcpa_service import tcpa_service
                    is_quiet, quiet_reason = tcpa_service.is_quiet_hours(
                        timezone_str=c_data.get("timezone"),
                        notifications_config=c_conf
                    )
                    if is_quiet:
                        log.info(f"[sms.send_reminder] {quiet_reason}. Deferring reminder for appt {appointment_id}.")
                        return {"success": False, "skipped": True, "reason": "quiet_hours", "detail": quiet_reason}
            except Exception as conf_err:
                log.warning(f"[sms.send_reminder] Config check warning: {conf_err}")

            patient = appt.get("patients", {})
            phone = appt.get("patient_phone") or patient.get("phone")
            
            if not phone:
                raise Exception("Patient phone number not found")
                
            dt = datetime.datetime.fromisoformat(appt["datetime"].replace("Z", "+00:00"))
            time_str = dt.strftime("%I:%M %p")
            date_str = dt.strftime("%A, %b %d")
            datetime_str = f"{time_str} on {date_str}"

            # Fetch patient language preference for bilingual SMS
            lang_pref = "en"
            patient_id = appt.get("patient_id")
            if patient_id:
                try:
                    lang_res = supabase.table("patients").select("language_preference").eq("id", patient_id).execute()
                    if lang_res.data and lang_res.data[0].get("language_preference"):
                        lang_pref = lang_res.data[0]["language_preference"]
                except Exception as lang_err:
                    log.warning(f"[sms.send_reminder] Could not fetch language preference: {lang_err}")

            # Template resolution: custom clinic template or standard bilingual template
            custom_template = c_conf.get("reminder_sms_template") if isinstance(c_conf, dict) else None
            patient_disp_name = appt.get("patient_name") or patient.get("name") or "there"
            clinic_disp_name = appt.get("clinic_name") or clinic_name

            if custom_template and str(custom_template).strip():
                # Safe replacement to avoid exceptions on user-added tags
                body = str(custom_template)\
                    .replace("{patient_name}", str(patient_disp_name))\
                    .replace("{clinic_name}", str(clinic_disp_name))\
                    .replace("{datetime}", str(datetime_str))
            else:
                template = get_template("appointment_reminder", lang=lang_pref)
                body = template.format(
                    patient_name=patient_disp_name,
                    clinic_name=clinic_disp_name,
                    datetime=datetime_str
                )

            send_res = await self.send(
                clinic_id=clinic_id,
                to=phone,
                body=body,
                sms_type="reminder",
                appointment_id=appointment_id,
                patient_id=patient_id
            )
            
            if send_res.get("success"):
                supabase.table("appointments").update({"reminder_sent": True}).eq("id", appointment_id).execute()
                
            return send_res
        except Exception as e:
            log.error(f"[sms.send_reminder] apptId={appointment_id} error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_inbound(self, from_number: str, body: str, clinic_id: str, twilio_sid: str) -> Dict[str, Any]:
        """
        Processes inbound SMS from patients (e.g. Confirmations, Cancellations, Questions)
        with distributed locking and AI sentiment/intent classification.
        """
        from ..core.lock import DistributedLock
        lock = DistributedLock(f"patient_sms_{clinic_id}_{from_number}")
        try:
            await lock.__aenter__()
            res = supabase.table("patients").select("id").eq("clinic_id", clinic_id).eq("phone", from_number).execute()
            patient_id = res.data[0]["id"] if res.data else None
            
            appt_id = None
            if patient_id:
                appt_res = supabase.table("appointments").select("id").eq("clinic_id", clinic_id).eq("patient_id", patient_id).in_("status", ["scheduled", "confirmed"]).order("datetime", desc=False).limit(1).execute()
                if appt_res.data:
                    appt_id = appt_res.data[0]["id"]

            prompt = f"""Analyze this patient SMS reply.
Message: "{body}"
Categorize intent as EXACTLY ONE of: confirm, cancel, reschedule, question, other.
Categorize sentiment as EXACTLY ONE of: positive, negative, neutral, concern.
Return ONLY JSON format: {{"intent": "...", "sentiment": "..."}}"""
            
            ai_res = await ai_service.chat([{"role": "user", "content": prompt}], max_tokens=100)
            
            try:
                cleaned = ai_res.replace("```json", "").replace("```", "").strip()
                analysis = json.loads(cleaned)
            except Exception:
                analysis = {"intent": "other", "sentiment": "neutral"}
                
            intent = analysis.get("intent", "other")
            sentiment = analysis.get("sentiment", "neutral")
            
            try:
                supabase.table("sms_messages").insert({
                    "clinic_id": clinic_id,
                    "patient_id": patient_id,
                    "twilio_sid": twilio_sid,
                    "direction": "inbound",
                    "from_number": from_number,
                    "to_number": getattr(settings, "TELNYX_DEFAULT_NUMBER", getattr(settings, "TWILIO_DEFAULT_NUMBER", "")),
                    "body": body,
                    "sms_type": "general",
                    "appointment_id": appt_id,
                    "status": "delivered",
                    "reply_sentiment": sentiment if sentiment in ["positive", "negative", "neutral", "concern"] else "neutral",
                    "patient_reply": intent
                }).execute()
            except Exception as db_err:
                err_msg = str(db_err)
                if "duplicate key" in err_msg.lower() or "23505" in err_msg:
                    log.info(f"[sms.handle_inbound] Duplicate SMS SID detected ({twilio_sid}), skipping duplicate insertion.")
                else:
                    raise db_err
            
            if appt_id:
                if intent == "confirm":
                    try:
                        last_sms = supabase.table("sms_messages").select("sms_type").eq("appointment_id", appt_id).eq("direction", "outbound").order("created_at", desc=True).limit(1).execute()
                        is_insurance = last_sms.data and last_sms.data[0].get("sms_type") == "insurance"
                    except Exception as sms_err:
                        log.warning(f"[sms.handle_inbound] Error fetching last SMS type: {str(sms_err)}")
                        is_insurance = False
                        
                    update_payload = {
                        "status": "confirmed",
                        "confirmed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }
                    if is_insurance:
                        update_payload["insurance_verified"] = True
                        
                    supabase.table("appointments").update(update_payload).eq("id", appt_id).execute()
                elif intent == "cancel":
                    supabase.table("appointments").update({"status": "cancelled"}).eq("id", appt_id).execute()
            
            # Create a real-time notification for incoming SMS
            try:
                from .notification_service import notification_service
                pat_name = "Unknown Patient"
                if patient_id:
                    p_res = supabase.table("patients").select("name").eq("id", patient_id).execute()
                    if p_res.data:
                        pat_name = p_res.data[0].get("name", "Unknown Patient")
                
                await notification_service.create(
                    clinic_id=clinic_id,
                    notification_type="sms.received",
                    title=f"SMS from {pat_name}",
                    body=body[:100] + ("..." if len(body) > 100 else ""),
                    metadata={"from_number": mask_phone(from_number), "intent": intent, "sentiment": sentiment},
                    resource_type="patient",
                    resource_id=patient_id
                )
            except Exception as notif_err:
                log.warning(f"[sms.handle_inbound] Failed to trigger notification: {notif_err}")
                     
            try:
                from ..core.cache import invalidate_dashboard_stats
                invalidate_dashboard_stats(clinic_id)
            except Exception as cache_e:
                log.warning(f"[sms.handle_inbound] Cache invalidation warning: {cache_e}")
                
            return {"success": True, "data": {"intent": intent, "sentiment": sentiment}}
        except Exception as e:
            log.error(f"[sms.handle_inbound] error: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            if lock and lock.acquired:
                await lock.__aexit__(None, None, None)

sms_service = SmsService()
