import datetime
import asyncio
import uuid
import re
from typing import Dict, Any

from ..core.database import supabase
from .voice_service import voice_service
from .phonenumber_service import phonenumber_service
from .email_service import email_service

class OnboardingService:
    async def process_signup(
        self,
        owner_email: str,
        password: str,
        clinic_name: str,
        specialty: str = None,
        city: str = None,
        timezone: str = "America/Chicago",
        doctor_name: str = None,
        doctor_credentials: str = None,
        doctor_phone: str = None,
        business_hours: dict = None,
        appointment_types: list = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates the Zero-Touch SaaS Onboarding Flow.
        1. Create Auth User (sign_up + auto-confirm via admin)
        2. Create Clinic Record with ALL fields
        3. Attempt Provisioning (Best-effort — phone number + Retell agent)
        4. Send Welcome Email (non-blocking)
        """
        DEFAULT_HOURS = {
            "mon": {"enabled": True, "start": "08:00", "end": "18:00"},
            "tue": {"enabled": True, "start": "08:00", "end": "18:00"},
            "wed": {"enabled": True, "start": "08:00", "end": "18:00"},
            "thu": {"enabled": True, "start": "08:00", "end": "18:00"},
            "fri": {"enabled": True, "start": "08:00", "end": "18:00"},
            "sat": {"enabled": False, "start": "08:00", "end": "18:00"},
            "sun": {"enabled": False, "start": "08:00", "end": "18:00"},
        }
        DEFAULT_APPT_TYPES = [
            {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 150.0},
            {"name": "Follow-up Visit", "duration": 30, "duration_minutes": 30, "fee": 75.0},
        ]
        try:
            # ── Step 1: Create Supabase Auth user ──────────────────────────
            user = None
            last_err = None
            for attempt in range(3):
                try:
                    auth_res = supabase.auth.admin.create_user({
                        "email": owner_email,
                        "password": password,
                        "email_confirm": True,
                    })
                    user = auth_res.user
                    break
                except Exception as ce:
                    last_err = ce
                    err_str = str(ce)
                    if "already registered" in err_str or "already been registered" in err_str:
                        raise Exception("This email is already registered. Please sign in instead.")
                    print(f"[onboarding] admin.create_user attempt {attempt+1} failed: {err_str} — retrying...")
                    await asyncio.sleep(2)

            if not user:
                raise Exception(f"Could not create auth user after 3 attempts: {last_err}")

            print(f"[onboarding] auth user created & confirmed: {user.id}")

            # ── Step 2: Create Clinic record with ALL fields ───────────────
            clinic_id = str(uuid.uuid4())
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', clinic_name)
            ref_code = f"{clean_name[:3].upper()}-{clinic_id[:6].upper()}"
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            trial_ends_dt = now_dt + datetime.timedelta(days=14)

            clinic_insert = {
                "id": clinic_id,
                "name": clinic_name,
                "owner_email": owner_email,
                "timezone": timezone or "America/Chicago",
                "referral_code": ref_code,
                "plan": "trial",
                "stripe_subscription_status": "trialing",
                "trial_ends_at": trial_ends_dt.isoformat(),
                "billing_cycle_anchor": now_dt.isoformat()
            }
            if specialty:
                clinic_insert["specialty"] = specialty
            if city:
                clinic_insert["city"] = city
            if doctor_name:
                clinic_insert["primary_doctor_name"] = doctor_name
            if doctor_credentials:
                clinic_insert["primary_doctor_credentials"] = doctor_credentials
            if doctor_phone:
                clinic_insert["primary_doctor_phone"] = doctor_phone
            if business_hours:
                clinic_insert["business_hours"] = business_hours
            else:
                clinic_insert["business_hours"] = DEFAULT_HOURS
            if appointment_types and isinstance(appointment_types, list):
                cleaned_appts = []
                for a in appointment_types:
                    if isinstance(a, dict) and a.get("name"):
                        dur = a.get("duration_minutes") or a.get("duration") or 30
                        try:
                            dur = max(5, int(dur))
                        except (ValueError, TypeError):
                            dur = 30
                        fee_v = a.get("fee") if a.get("fee") is not None else a.get("price", 0)
                        try:
                            fee_v = max(0.0, float(fee_v))
                        except (ValueError, TypeError):
                            fee_v = 0.0
                        cleaned_appts.append({
                            "name": str(a.get("name")).strip(),
                            "duration": dur,
                            "duration_minutes": dur,
                            "fee": fee_v
                        })
                clinic_insert["appointment_types"] = cleaned_appts if cleaned_appts else DEFAULT_APPT_TYPES
            else:
                clinic_insert["appointment_types"] = DEFAULT_APPT_TYPES

            clinic_res = supabase.table("clinics").insert(clinic_insert).execute()
            clinic = clinic_res.data[0]
            clinic_id = clinic["id"]
            print(f"[onboarding] clinic record created with full data: {clinic_id}")

            # ── Step 2.5: Link clinic owner to clinic_users table ──────────
            try:
                supabase.table("clinic_users").insert({
                    "clinic_id": clinic_id,
                    "supabase_user_id": str(user.id),
                    "email": owner_email,
                    "name": clinic_name,
                    "role": "owner"
                }).execute()
                print(f"[onboarding] Linked owner user {user.id} to clinic {clinic_id} in clinic_users")
            except Exception as cu_err:
                print(f"[onboarding] WARNING: Failed to insert clinic_users owner mapping: {cu_err}")

            # ── Step 3: Provisioning (Deferred under Lazy Model A) ────
            clinic["phone_number"] = None
            clinic["retell_agent_id"] = None

            # ── Step 4: Welcome email (best-effort) ────────────────────────
            try:
                await email_service.send_welcome_email(clinic, password)
            except Exception as email_e:
                print(f"[onboarding] WARNING: Welcome email failed (non-critical): {email_e}")

            print(f"[onboarding] signup complete for clinicId={clinic_id}")
            return {"success": True, "data": {"clinicId": clinic_id}}

        except Exception as e:
            err_msg = str(e)
            # Give the user a friendly message for common cases
            if "already registered" in err_msg or "already been registered" in err_msg:
                err_msg = "This email is already registered. Please sign in instead."
            print(f"[onboarding.process_signup] Error: {err_msg}")
            return {"success": False, "error": err_msg}


onboarding_service = OnboardingService()
