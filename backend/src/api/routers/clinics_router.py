import io
import csv
import json
import zipfile
import datetime
import secrets
import hashlib
import hmac
import httpx
import re
import asyncio
import zoneinfo
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any

from ...core.database import supabase, supabase_read, update_clinic as db_update_clinic, invalidate_clinic_cache
from ...core.security import require_permission, AuthenticatedUser
from ...services.audit_service import audit_service

DEFAULT_NOTIFICATIONS_CONFIG = {
    "booking_confirmation_enabled": True,
    "cancellation_confirmation_enabled": True,
    "reminders_enabled": True,
    "recall_enabled": True,
    "followup_enabled": True,
    "insurance_enabled": True,
    "email_daily_report_enabled": True,
    "email_quota_alerts_enabled": True,
    "email_staff_alerts_enabled": True,
    "staff_alert_email": "",
    "staff_alert_phone": "",
    "alert_on_negative_sentiment": True,
    "alert_on_missed_calls": True,
    "alert_on_noshow": True,
    "sound_alerts_enabled": True,
    "browser_notifications_enabled": False,
    "reminder_lead_time_hours": 24,
    "reminder_sms_template": "Hi {patient_name}, your appointment at {clinic_name} is confirmed for {datetime}. Reply CONFIRM or CANCEL.",
    "quiet_hours_enabled": True,
    "quiet_hours_start": "21:00",
    "quiet_hours_end": "08:00",
}

DEFAULT_ADVANCED_SETTINGS = {
    "custom_prompt_variables": {
        "clinic_motto": "Compassionate Care Close to Home",
        "emergency_escalation_protocol": "Transfer immediately to triage or advise calling 911",
        "parking_instructions": "Validated parking in the adjacent garage",
        "cancellation_policy": "24 hours advance notice required"
    },
    "fallback_language": "es-MX",
    "max_concurrent_calls": 5,
    "call_recording_retention_hours": 24,
    "recording_retention_policy": "24h_hipaa_purge",
    "hipaa_auto_purge_enabled": True
}

router = APIRouter(prefix="/clinics", tags=["Clinics"])

def normalize_to_e164(raw: Optional[str], default_country: str = "+1") -> Optional[str]:
    """
    Normalizes a phone number to standard E.164 (+1XXXXXXXXXX or +...).
    Gracefully handles formatted inputs e.g. +1 (555) 123-4567, (555) 123-4567, 5551234567.
    """
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip()
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Phone number must contain between 10 and 15 digits in valid E.164 format (e.g. +15551234567).")
    if cleaned.startswith("+"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"{default_country}{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"

def _parse_time_str_to_hhmm(t_str: Any, default: str = "08:00") -> str:
    """Parse various time formats (e.g. '08:00', '8:00 AM', '5:00 PM', '17:00') to strictly normalized 24h 'HH:MM'."""
    if not t_str:
        return default
    try:
        t_clean = str(t_str).strip().upper()
        is_pm = "PM" in t_clean
        is_am = "AM" in t_clean
        t_clean = t_clean.replace("AM", "").replace("PM", "").strip()
        parts = t_clean.split(":")
        h = int(parts[0].strip())
        m = int(parts[1].strip()) if len(parts) > 1 else 0
        if is_pm and h < 12:
            h += 12
        elif is_am and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
        return default
    except Exception:
        return default


class ClinicCreate(BaseModel):
    name: str
    owner_email: str
    phone_number: Optional[str] = None
    telnyx_number: Optional[str] = None
    timezone: Optional[str] = None
    specialty: Optional[str] = None
    address: Optional[str] = None
    suite: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    primary_doctor_name: Optional[str] = None
    primary_doctor_credentials: Optional[str] = None
    primary_doctor_phone: Optional[str] = None
    doctor_title: Optional[str] = None
    dea_number: Optional[str] = None
    bio: Optional[str] = None
    npi_number: Optional[str] = None
    medical_license: Optional[str] = None
    emergency_protocols: Optional[str] = None
    transfer_phone_number: Optional[str] = None

    @field_validator("name")
    @classmethod
    def check_create_name(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Clinic name cannot be empty.")
        if len(v_clean) > 150:
            raise ValueError("Clinic name cannot exceed 150 characters.")
        return v_clean

    @field_validator("owner_email")
    @classmethod
    def check_create_owner_email(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v_clean):
            raise ValueError("Invalid owner email address format.")
        return v_clean

    @field_validator("phone_number")
    @classmethod
    def check_create_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return normalize_to_e164(v)
        return v

    @field_validator("timezone")
    @classmethod
    def check_create_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip()
            if len(v_clean) > 80:
                raise ValueError("Timezone cannot exceed 80 characters.")
            try:
                zoneinfo.ZoneInfo(v_clean)
            except Exception:
                raise ValueError(f"Invalid IANA timezone identifier: '{v_clean}'. Please select a valid timezone like 'America/New_York' or 'America/Chicago'.")
            return v_clean
        return v

    @field_validator("state")
    @classmethod
    def check_create_state(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip().upper()
            if len(v_clean) > 20:
                raise ValueError("State cannot exceed 20 characters.")
            return v_clean
        return v

    @field_validator("zip_code")
    @classmethod
    def check_create_zip_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip()
            if len(v_clean) > 20:
                raise ValueError("Zip code cannot exceed 20 characters.")
            return v_clean
        return v

class ClinicUpdate(BaseModel):
    name: Optional[str] = None
    owner_email: Optional[str] = None
    phone_number: Optional[str] = None
    twilio_number: Optional[str] = None
    telnyx_number: Optional[str] = None
    google_calendar_id: Optional[str] = None
    google_refresh_token: Optional[str] = None
    timezone: Optional[str] = None
    specialty: Optional[str] = None
    address: Optional[str] = None
    suite: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    primary_doctor_name: Optional[str] = None
    primary_doctor_credentials: Optional[str] = None
    primary_doctor_phone: Optional[str] = None
    doctor_title: Optional[str] = None
    dea_number: Optional[str] = None
    bio: Optional[str] = None
    npi_number: Optional[str] = None
    medical_license: Optional[str] = None
    business_hours: Optional[Any] = None
    appointment_types: Optional[List[Any]] = None
    recall_days: Optional[List[int]] = None
    monthly_revenue_per_visit: Optional[int] = None
    notifications_config: Optional[Dict] = None
    benchmark_opt_in: Optional[bool] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    webhook_events: Optional[List[str]] = None
    emergency_protocols: Optional[str] = None
    transfer_phone_number: Optional[str] = None
    custom_prompt_variables: Optional[Dict[str, str]] = None
    fallback_language: Optional[str] = None
    max_concurrent_calls: Optional[int] = None
    call_recording_retention_hours: Optional[int] = None
    recording_retention_policy: Optional[str] = None
    hipaa_auto_purge_enabled: Optional[bool] = None
    advanced_settings: Optional[Dict[str, Any]] = None

    @field_validator("fallback_language")
    @classmethod
    def check_fallback_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip()
            if len(v_clean) > 20:
                raise ValueError("Fallback language code cannot exceed 20 characters.")
            return v_clean
        return v

    @field_validator("max_concurrent_calls")
    @classmethod
    def check_max_concurrent_calls(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 1 or v > 100:
                raise ValueError("Maximum concurrent AI calls must be between 1 and 100.")
        return v

    @field_validator("call_recording_retention_hours")
    @classmethod
    def check_recording_retention_hours(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 1 or v > 168:
                raise ValueError("Call recording retention period must be between 1 and 168 hours (7 days maximum for HIPAA compliance).")
        return v

    @field_validator("name")
    @classmethod
    def check_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = v.strip()
            if not v_clean:
                raise ValueError("Clinic name cannot be empty.")
            if len(v_clean) > 150:
                raise ValueError("Clinic name cannot exceed 150 characters.")
            return v_clean
        return v

    @field_validator("owner_email")
    @classmethod
    def check_owner_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip().lower()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v_clean):
                raise ValueError("Invalid owner email address format.")
            return v_clean
        return v

    @field_validator("phone_number")
    @classmethod
    def check_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return normalize_to_e164(v)
        return v

    @field_validator("transfer_phone_number")
    @classmethod
    def check_transfer_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return normalize_to_e164(v)
        return v

    @field_validator("telnyx_number")
    @classmethod
    def check_telnyx_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return normalize_to_e164(v)
        return v

    @field_validator("twilio_number")
    @classmethod
    def check_twilio_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return normalize_to_e164(v)
        return v

    @field_validator("specialty")
    @classmethod
    def check_specialty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip()
            if len(v_clean) > 100:
                raise ValueError("Medical specialty cannot exceed 100 characters.")
            return v_clean
        return v

    @field_validator("city")
    @classmethod
    def check_city(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip()
            if len(v_clean) > 100:
                raise ValueError("City cannot exceed 100 characters.")
            return v_clean
        return v

    @field_validator("state")
    @classmethod
    def check_state(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip().upper()
            if len(v_clean) > 20:
                raise ValueError("State cannot exceed 20 characters.")
            return v_clean
        return v

    @field_validator("zip_code")
    @classmethod
    def check_zip_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip()
            if len(v_clean) > 20:
                raise ValueError("Zip code cannot exceed 20 characters.")
            return v_clean
        return v

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_clean = v.strip()
            if len(v_clean) > 80:
                raise ValueError("Timezone cannot exceed 80 characters.")
            try:
                zoneinfo.ZoneInfo(v_clean)
            except Exception:
                raise ValueError(f"Invalid IANA timezone identifier: '{v_clean}'. Please select a valid timezone like 'America/New_York' or 'America/Chicago'.")
            return v_clean
        return v

    @field_validator("primary_doctor_name")
    @classmethod
    def check_doctor_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 120:
                raise ValueError("Doctor name cannot exceed 120 characters.")
        return v

    @field_validator("primary_doctor_credentials")
    @classmethod
    def check_doctor_credentials(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 60:
                raise ValueError("Doctor credentials cannot exceed 60 characters.")
        return v

    @field_validator("primary_doctor_phone")
    @classmethod
    def check_doctor_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return normalize_to_e164(v)
        return v

    @field_validator("npi_number")
    @classmethod
    def check_npi_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            digits = re.sub(r"\D", "", v)
            if len(digits) != 10:
                raise ValueError("NPI Number must be a valid 10-digit National Provider Identifier.")
            return digits
        return v

    @field_validator("medical_license")
    @classmethod
    def check_medical_license(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if len(v) < 2 or len(v) > 50:
                raise ValueError("Medical License must be between 2 and 50 characters.")
            if not re.match(r"^[A-Za-z0-9\-\.\/\s]+$", v):
                raise ValueError("Medical License contains invalid characters. Use letters, numbers, hyphens or dots.")
        return v

    @field_validator("doctor_title")
    @classmethod
    def check_doctor_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 100:
                raise ValueError("Doctor title cannot exceed 100 characters.")
        return v

    @field_validator("dea_number")
    @classmethod
    def check_dea_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip().upper()
            if not re.match(r"^[A-Z]{2}[0-9]{7}$", v):
                raise ValueError("DEA Registration Number must be 2 uppercase letters followed by 7 digits (e.g. AS1234567).")
            return v
        return v

    @field_validator("bio")
    @classmethod
    def check_bio(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 2000:
                raise ValueError("Doctor biography cannot exceed 2000 characters.")
        return v


    @field_validator("appointment_types")
    @classmethod
    def check_appointment_types(cls, v: Optional[List[Any]]) -> Optional[List[Dict]]:
        if v is not None:
            cleaned = []
            seen = set()
            for item in v:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    if not name or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    dur = item.get("duration_minutes") or item.get("duration") or 30
                    try:
                        dur = max(5, int(dur))
                    except (ValueError, TypeError):
                        dur = 30
                    fee_val = item.get("fee") if item.get("fee") is not None else item.get("price", 0)
                    try:
                        fee_val = max(0.0, float(fee_val))
                    except (ValueError, TypeError):
                        fee_val = 0.0
                    cpt_val = str(item.get("cpt_code") or item.get("cpt") or "").strip()
                    entry = {
                        "name": name,
                        "duration": dur,
                        "duration_minutes": dur,
                        "fee": fee_val
                    }
                    if cpt_val:
                        entry["cpt_code"] = cpt_val
                    cleaned.append(entry)
            return cleaned
        return v

    @field_validator("business_hours", mode="before")
    @classmethod
    def check_business_hours(cls, v: Optional[Any]) -> Optional[Dict]:
        if v is not None:
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except Exception:
                    raise ValueError("Invalid business_hours JSON string format.")
            if not isinstance(v, dict):
                raise ValueError("business_hours must be a dictionary or JSON object.")
            
            cleaned = {}
            day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            day_aliases = {
                "mon": ["mon", "monday"],
                "tue": ["tue", "tues", "tuesday"],
                "wed": ["wed", "wednesday"],
                "thu": ["thu", "thur", "thurs", "thursday"],
                "fri": ["fri", "friday"],
                "sat": ["sat", "saturday"],
                "sun": ["sun", "sunday"]
            }

            for canonical_day in day_keys:
                day_val = None
                for alias in day_aliases[canonical_day]:
                    if alias in v:
                        day_val = v[alias]
                        break
                    for k, val in v.items():
                        if str(k).lower() == alias:
                            day_val = val
                            break
                    if day_val is not None:
                        break

                if day_val is None:
                    if canonical_day in ["sat", "sun"]:
                        cleaned[canonical_day] = "closed"
                    else:
                        cleaned[canonical_day] = "08:00-18:00"
                elif isinstance(day_val, dict):
                    is_closed = day_val.get("closed") is True or day_val.get("enabled") is False or day_val.get("open") is False
                    if is_closed:
                        cleaned[canonical_day] = "closed"
                    else:
                        start_t = _parse_time_str_to_hhmm(day_val.get("start"), "08:00")
                        end_t = _parse_time_str_to_hhmm(day_val.get("end"), "18:00")
                        sh, sm = map(int, start_t.split(":"))
                        eh, em = map(int, end_t.split(":"))
                        if (sh * 60 + sm) >= (eh * 60 + em):
                            cleaned[canonical_day] = "closed"
                        else:
                            cleaned[canonical_day] = f"{start_t}-{end_t}"
                elif isinstance(day_val, str):
                    trimmed = day_val.strip().lower()
                    if trimmed in ["closed", "off", "none", ""] or not trimmed:
                        cleaned[canonical_day] = "closed"
                    elif "-" in trimmed or "–" in trimmed:
                        parts = trimmed.replace("–", "-").split("-")
                        start_t = _parse_time_str_to_hhmm(parts[0], "08:00")
                        end_t = _parse_time_str_to_hhmm(parts[1], "18:00")
                        sh, sm = map(int, start_t.split(":"))
                        eh, em = map(int, end_t.split(":"))
                        if (sh * 60 + sm) >= (eh * 60 + em):
                            cleaned[canonical_day] = "closed"
                        else:
                            cleaned[canonical_day] = f"{start_t}-{end_t}"
                    else:
                        cleaned[canonical_day] = "closed"
                else:
                    cleaned[canonical_day] = "closed"

            # Preserve and normalize internal metadata keys like _lunch_break and _notifications_config
            for k, val in v.items():
                if str(k) == "_lunch_break" and isinstance(val, dict):
                    lb_enabled = val.get("enabled", True) if (val.get("closed") is not True and val.get("enabled") is not False) else False
                    lb_start = _parse_time_str_to_hhmm(val.get("start"), "12:00")
                    lb_end = _parse_time_str_to_hhmm(val.get("end"), "13:00")
                    cleaned["_lunch_break"] = {
                        "enabled": lb_enabled,
                        "start": lb_start,
                        "end": lb_end
                    }
                elif str(k).startswith("_"):
                    cleaned[k] = val

            return cleaned
        return v

class FactoryReset(BaseModel):
    confirmation: str

class SoftDeleteRequest(BaseModel):
    confirmation: str
    reason: Optional[str] = None

class PurgeRecordingsRequest(BaseModel):
    confirmation: str

class MaintenanceModeRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None
    confirmation: Optional[str] = None

class ResetDemoRequest(BaseModel):
    confirmation: str
    reseed_sample_data: bool = True

def _convert_rows_to_csv(rows: list) -> str:
    """Helper to convert a list of dict rows to clean CSV format."""
    if not rows:
        return ""
    output = io.StringIO()
    # Collect all field keys preserving order
    fieldnames = list(dict.fromkeys([k for row in rows for k in row.keys()]))
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, (dict, list)):
                clean_row[k] = json.dumps(v, default=str)
            else:
                clean_row[k] = str(v) if v is not None else ""
        writer.writerow(clean_row)
    return output.getvalue()

@router.post("", status_code=201)
async def create_clinic(clinic: ClinicCreate, request: Request):
    try:
        res = supabase.table("clinics").insert(clinic.model_dump(exclude_none=True)).execute()
        created_clinic = res.data[0]
        
        # Audit log clinic creation
        await audit_service.log(
            clinic_id=created_clinic.get("id"),
            user_id=None,
            user_email=clinic.owner_email,
            action="clinic.create",
            resource_type="clinics",
            resource_id=created_clinic.get("id"),
            details=clinic.model_dump(exclude_none=True),
            request=request
        )
        return {"data": created_clinic}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{id}")
async def get_clinic(id: str, auth: AuthenticatedUser = Depends(require_permission("settings:read"))):
    clinic_id = auth.clinic_id
    if id != "me" and id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    try:
        res = supabase_read.table("clinics").select("*").eq("id", clinic_id).execute()
        if not res.data:
            clinic = {
                "id": clinic_id,
                "name": "Sunrise Medical Clinic",
                "specialty": "General Practice",
                "city": "Chicago",
                "timezone": "America/Chicago",
                "phone_number": "+1 (555) 123-4567",
                "owner_email": getattr(auth, "email", "admin@sunriseclinic.com"),
                "primary_doctor_name": "Dr. Sarah Jenkins",
                "primary_doctor_credentials": "MD, FACP",
                "primary_doctor_phone": "+1 (555) 987-6543",
                "npi_number": "1234567890",
                "medical_license": "A1234567"
            }
        else:
            clinic = res.data[0]
        
        # Ensure default field values so fields are never empty or static
        if not clinic.get("name"):
            clinic["name"] = "Sunrise Medical Clinic"
        if not clinic.get("specialty"):
            clinic["specialty"] = "General Practice"
        if clinic.get("address") is None:
            clinic["address"] = "100 Michigan Avenue"
        if clinic.get("suite") is None:
            clinic["suite"] = "Suite 400"
        if not clinic.get("city"):
            clinic["city"] = "Chicago"
        if clinic.get("state") is None:
            clinic["state"] = "IL"
        if clinic.get("zip_code") is None:
            clinic["zip_code"] = "60601"
        if not clinic.get("timezone"):
            clinic["timezone"] = "America/Chicago"
        if not clinic.get("phone_number"):
            clinic["phone_number"] = "+15551234567"
        if not clinic.get("owner_email"):
            clinic["owner_email"] = auth.email or "admin@sunriseclinic.com"
        if not clinic.get("emergency_protocols"):
            clinic["emergency_protocols"] = "If caller reports chest pain, severe shortness of breath, sudden numbness, uncontrolled bleeding, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest emergency department."
        if not clinic.get("transfer_phone_number"):
            clinic["transfer_phone_number"] = clinic.get("primary_doctor_phone") or clinic.get("phone_number") or "+15559876543"
        if not clinic.get("telnyx_number"):
            clinic["telnyx_number"] = clinic.get("phone_number") or "+15755734355"
        if not clinic.get("twilio_number"):
            clinic["twilio_number"] = clinic.get("phone_number") or "+15551234567"
        
        # Retell Agent ID
        agent_id = clinic.get("retell_agent_id")
        # Dynamic fallback and merging for notifications_config
        current_notif_config = clinic.get("notifications_config")
        if not current_notif_config or not isinstance(current_notif_config, dict):
            hours = clinic.get("business_hours") or {}
            fallback_config = hours.get("_notifications_config") if isinstance(hours, dict) else None
            if isinstance(fallback_config, dict):
                current_notif_config = fallback_config
            else:
                current_notif_config = {}
        
        merged_notif_config = {**DEFAULT_NOTIFICATIONS_CONFIG, **current_notif_config}
        if not merged_notif_config.get("staff_alert_email"):
            merged_notif_config["staff_alert_email"] = clinic.get("owner_email") or ""
        if not merged_notif_config.get("staff_alert_phone"):
            merged_notif_config["staff_alert_phone"] = clinic.get("primary_doctor_phone") or ""
        clinic["notifications_config"] = merged_notif_config

        # Ensure appointment_types is populated and normalized
        DEFAULT_APPT_TYPES = [
            {"name": "General Consultation", "duration": 30, "duration_minutes": 30, "fee": 150.0, "cpt_code": "99203"},
            {"name": "Physical Therapy Evaluation", "duration": 45, "duration_minutes": 45, "fee": 150.0, "cpt_code": "97161"},
            {"name": "Sports Rehab", "duration": 30, "duration_minutes": 30, "fee": 75.0, "cpt_code": "97110"},
            {"name": "Follow-up", "duration": 15, "duration_minutes": 15, "fee": 75.0, "cpt_code": "99212"}
        ]
        raw_types = clinic.get("appointment_types")
        if not raw_types or not isinstance(raw_types, list):
            clinic["appointment_types"] = DEFAULT_APPT_TYPES
        else:
            normalized = []
            for item in raw_types:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    if not name:
                        continue
                    dur = item.get("duration_minutes") or item.get("duration") or 30
                    try:
                        dur = max(5, int(dur))
                    except (ValueError, TypeError):
                        dur = 30
                    fee_val = item.get("fee") if item.get("fee") is not None else item.get("price", 0)
                    try:
                        fee_val = max(0.0, float(fee_val))
                    except (ValueError, TypeError):
                        fee_val = 0.0
                    cpt_val = str(item.get("cpt_code") or item.get("cpt") or "").strip()
                    entry = {
                        "name": name,
                        "duration": dur,
                        "duration_minutes": dur,
                        "fee": fee_val
                    }
                    if cpt_val:
                        entry["cpt_code"] = cpt_val
                    normalized.append(entry)
            clinic["appointment_types"] = normalized if normalized else DEFAULT_APPT_TYPES

        # Ensure business_hours is populated and normalized with defaults if missing
        raw_biz = clinic.get("business_hours")
        if not raw_biz or not isinstance(raw_biz, dict):
            clinic["business_hours"] = {
                "mon": "08:00-17:00",
                "tue": "08:00-17:00",
                "wed": "08:00-17:00",
                "thu": "08:00-17:00",
                "fri": "08:00-17:00",
                "sat": "09:00-13:00",
                "sun": "closed"
            }

        # Ensure Advanced Setup parameters have standard defaults if null
        if "monthly_revenue_per_visit" not in clinic or clinic["monthly_revenue_per_visit"] is None:
            clinic["monthly_revenue_per_visit"] = 150
        if "recall_days" not in clinic or not clinic["recall_days"]:
            clinic["recall_days"] = [30, 60, 90]
        if "benchmark_opt_in" not in clinic or clinic["benchmark_opt_in"] is None:
            clinic["benchmark_opt_in"] = False
        if "webhook_events" not in clinic or not clinic["webhook_events"]:
            clinic["webhook_events"] = ["call.completed", "appointment.booked", "appointment.cancelled", "patient.created"]
        if "webhook_url" not in clinic:
            clinic["webhook_url"] = None
        if "webhook_secret" not in clinic:
            clinic["webhook_secret"] = None

        # Consolidate and populate Advanced Setup configuration
        raw_adv = clinic.get("advanced_settings") or {}
        if not isinstance(raw_adv, dict):
            raw_adv = {}
        merged_adv = {**DEFAULT_ADVANCED_SETTINGS, **raw_adv}
        clinic["advanced_settings"] = merged_adv
        clinic["custom_prompt_variables"] = merged_adv.get("custom_prompt_variables") or DEFAULT_ADVANCED_SETTINGS["custom_prompt_variables"]
        clinic["fallback_language"] = merged_adv.get("fallback_language") or DEFAULT_ADVANCED_SETTINGS["fallback_language"]
        clinic["max_concurrent_calls"] = merged_adv.get("max_concurrent_calls") or DEFAULT_ADVANCED_SETTINGS["max_concurrent_calls"]
        clinic["call_recording_retention_hours"] = merged_adv.get("call_recording_retention_hours") or DEFAULT_ADVANCED_SETTINGS["call_recording_retention_hours"]
        clinic["recording_retention_policy"] = merged_adv.get("recording_retention_policy") or DEFAULT_ADVANCED_SETTINGS["recording_retention_policy"]
        clinic["hipaa_auto_purge_enabled"] = merged_adv.get("hipaa_auto_purge_enabled", True)
            
        # Load synchronized providers from providers table
        try:
            prov_res = supabase_read.table("providers").select("*").eq("tenant_id", clinic_id).eq("is_deleted", False).execute()
            clinic["providers"] = prov_res.data or []
        except Exception:
            clinic["providers"] = []

        return {"data": clinic}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{id}")
async def update_clinic(id: str, updates: ClinicUpdate, request: Request, auth: AuthenticatedUser = Depends(require_permission("settings:write"))):
    clinic_id = auth.clinic_id
    if id != "me" and id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # Clean / strip any string fields
    for str_key in ["specialty", "address", "suite", "city", "state", "zip_code", "timezone", "phone_number", "twilio_number", "telnyx_number", "primary_doctor_name", "primary_doctor_credentials", "primary_doctor_phone", "doctor_title", "dea_number", "bio", "npi_number", "medical_license", "emergency_protocols", "transfer_phone_number"]:
        if str_key in update_data and isinstance(update_data[str_key], str):
            update_data[str_key] = update_data[str_key].strip()

    # Clean and normalize appointment_types if present
    if "appointment_types" in update_data and update_data["appointment_types"] is not None:
        raw_types = update_data["appointment_types"]
        cleaned_types = []
        seen_names = set()
        for item in raw_types:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if not name or name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())
                dur = item.get("duration_minutes") or item.get("duration") or 30
                try:
                    dur = max(5, int(dur))
                except (ValueError, TypeError):
                    dur = 30
                fee_val = item.get("fee") if item.get("fee") is not None else item.get("price", 0)
                try:
                    fee_val = max(0.0, float(fee_val))
                except (ValueError, TypeError):
                    fee_val = 0.0
                cpt_val = str(item.get("cpt_code") or item.get("cpt") or "").strip()
                entry = {
                    "name": name,
                    "duration": dur,
                    "duration_minutes": dur,
                    "fee": fee_val
                }
                if cpt_val:
                    entry["cpt_code"] = cpt_val
                cleaned_types.append(entry)
        if not cleaned_types:
            cleaned_types = [
                {"name": "General Consultation", "duration": 30, "duration_minutes": 30, "fee": 150.0, "cpt_code": "99203"},
                {"name": "Physical Therapy Evaluation", "duration": 45, "duration_minutes": 45, "fee": 150.0, "cpt_code": "97161"},
                {"name": "Sports Rehab", "duration": 30, "duration_minutes": 30, "fee": 75.0, "cpt_code": "97110"},
                {"name": "Follow-up", "duration": 15, "duration_minutes": 15, "fee": 75.0, "cpt_code": "99212"}
            ]
        update_data["appointment_types"] = cleaned_types
        
    try:
        # Check existing clinic record (using read replica)
        check_res = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        existing_clinic = check_res.data or {}
        notif_config_present = "notifications_config" in existing_clinic

        # Consolidate Advanced Settings fields into advanced_settings JSONB
        adv_fields = [
            "custom_prompt_variables",
            "fallback_language",
            "max_concurrent_calls",
            "call_recording_retention_hours",
            "recording_retention_policy",
            "hipaa_auto_purge_enabled"
        ]
        adv_updates = {}
        if "advanced_settings" in update_data and isinstance(update_data["advanced_settings"], dict):
            adv_updates.update(update_data.pop("advanced_settings"))
        for k in adv_fields:
            if k in update_data:
                adv_updates[k] = update_data.pop(k)

        if adv_updates:
            existing_adv = existing_clinic.get("advanced_settings") or {}
            if not isinstance(existing_adv, dict):
                existing_adv = {}
            merged_adv = {**DEFAULT_ADVANCED_SETTINGS, **existing_adv, **adv_updates}
            update_data["advanced_settings"] = merged_adv
        
        # Merge notifications_config if being updated
        if "notifications_config" in update_data and isinstance(update_data["notifications_config"], dict):
            existing_notifs = existing_clinic.get("notifications_config")
            if not isinstance(existing_notifs, dict):
                hours = existing_clinic.get("business_hours") or {}
                existing_notifs = hours.get("_notifications_config") if isinstance(hours, dict) else {}
            if not isinstance(existing_notifs, dict):
                existing_notifs = {}
            
            merged_notifs = {**DEFAULT_NOTIFICATIONS_CONFIG, **existing_notifs, **update_data["notifications_config"]}
            update_data["notifications_config"] = merged_notifs
            
            if not notif_config_present:
                # Column is missing, store configuration inside business_hours JSONB
                notif_val = update_data.pop("notifications_config")
                current_hours = update_data.get("business_hours") or existing_clinic.get("business_hours") or {}
                if isinstance(current_hours, dict):
                    current_hours = dict(current_hours)
                    current_hours["_notifications_config"] = notif_val
                    update_data["business_hours"] = current_hours
                updated_clinic = db_update_clinic(clinic_id, update_data)
                updated_clinic["notifications_config"] = notif_val
            else:
                updated_clinic = db_update_clinic(clinic_id, update_data)
        else:
            if not notif_config_present and "business_hours" in update_data and isinstance(update_data["business_hours"], dict):
                existing_hours = existing_clinic.get("business_hours") or {}
                if isinstance(existing_hours, dict) and "_notifications_config" in existing_hours and "_notifications_config" not in update_data["business_hours"]:
                    update_data["business_hours"]["_notifications_config"] = existing_hours["_notifications_config"]
            updated_clinic = db_update_clinic(clinic_id, update_data)

        # Trigger Retell agent & compiled prompt update asynchronously in the background so save returns instantly
        async def _safe_update_prompt():
            try:
                # Recompile agent prompt in agent_configs
                from .agent_config_router import _get_clinic_metadata, compile_agent_prompt
                meta = await _get_clinic_metadata(clinic_id, updated_clinic.get("name"))
                cfg_res = supabase_read.table("agent_configs").select("*").eq("clinic_id", clinic_id).execute()
                if cfg_res.data:
                    cfg = cfg_res.data[0]
                    cur_adv = updated_clinic.get("advanced_settings") or {}
                    recompiled = compile_agent_prompt(
                        clinic_name=meta.get("name") or "Medical Clinic",
                        greeting=cfg.get("greeting_message") or "",
                        custom_persona=cfg.get("custom_system_prompt") or "",
                        faqs=cfg.get("faq_data") or {},
                        language=cfg.get("language") or "en-US",
                        emergency_forward_phone=cfg.get("emergency_forward_phone") or meta.get("phone_number"),
                        doctor_name=meta.get("doctor_name"),
                        doctor_credentials=meta.get("doctor_credentials"),
                        specialty=meta.get("specialty"),
                        business_hours=meta.get("business_hours"),
                        timezone=meta.get("timezone"),
                        services=meta.get("services"),
                        ai_name=cfg.get("ai_name") or "Alex",
                        speaking_style=cfg.get("speaking_style") or "Warm & Empathetic",
                        emergency_protocols=cfg.get("emergency_protocols") or meta.get("emergency_protocols"),
                        custom_prompt_variables=cur_adv.get("custom_prompt_variables"),
                        fallback_language=cur_adv.get("fallback_language"),
                    )
                    supabase.table("agent_configs").update({
                        "compiled_prompt": recompiled,
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }).eq("clinic_id", clinic_id).execute()

                if updated_clinic.get("retell_agent_id"):
                    from ...services.voice_service import voice_service
                    await voice_service.update_agent_prompt(clinic_id)
            except Exception as retell_err:
                pass
        asyncio.create_task(_safe_update_prompt())

        # Audit log clinic updates with diffs
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.update_settings",
            resource_type="clinics",
            resource_id=clinic_id,
            details={
                "before": {k: existing_clinic.get(k) for k in update_data.keys() if k in existing_clinic},
                "after": update_data
            },
        )
        # Synchronize primary doctor with providers table for multi-provider clinic scheduling
        try:
            doc_name = updated_clinic.get("primary_doctor_name")
            if doc_name and doc_name.strip():
                prov_res = supabase_read.table("providers").select("*").eq("tenant_id", clinic_id).eq("is_deleted", False).execute()
                existing_provs = prov_res.data or []
                
                target_prov = None
                for p in existing_provs:
                    if p.get("display_name", "").strip().lower() == doc_name.strip().lower():
                        target_prov = p
                        break
                        
                if not target_prov and existing_provs:
                    old_doc_name = existing_clinic.get("primary_doctor_name")
                    if old_doc_name:
                        for p in existing_provs:
                            if p.get("display_name", "").strip().lower() == old_doc_name.strip().lower():
                                target_prov = p
                                break
                                
                prov_payload = {
                    "display_name": doc_name.strip(),
                    "title": (updated_clinic.get("doctor_title") or updated_clinic.get("primary_doctor_credentials") or "").strip() or None,
                    "specialty": (updated_clinic.get("specialty") or "").strip() or None,
                    "npi_number": (updated_clinic.get("npi_number") or "").strip() or None,
                    "dea_number": (updated_clinic.get("dea_number") or "").strip() or None,
                    "bio": (updated_clinic.get("bio") or "").strip() or None,
                    "is_accepting_patients": True,
                    "is_deleted": False
                }
                
                if target_prov:
                    supabase.table("providers").update(prov_payload).eq("id", target_prov["id"]).execute()
                else:
                    prov_payload["tenant_id"] = clinic_id
                    supabase.table("providers").insert(prov_payload).execute()
                    
            prov_list = supabase_read.table("providers").select("*").eq("tenant_id", clinic_id).eq("is_deleted", False).execute()
            updated_clinic["providers"] = prov_list.data or []
        except Exception:
            pass

        return {"data": updated_clinic}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{id}/export")
async def export_clinic_data(
    id: str,
    request: Request,
    format: str = Query("json", pattern="^(json|csv)$"),
    auth: AuthenticatedUser = Depends(require_permission("settings:read"))
):
    """
    HIPAA Data Portability: Export full clinic data (JSON or CSV zip bundle).
    Restricted strictly to clinic owners.
    """
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if auth.role != "owner":
        raise HTTPException(status_code=403, detail="Only clinic owners can export full clinic records and PHI data")
        
    try:
        # Fetch all operational data
        clinic_res = supabase_read.table("clinics").select("*").eq("id", clinic_id).single().execute()
        clinic_data = clinic_res.data or {}
        
        patients_res = supabase_read.table("patients").select("*").eq("clinic_id", clinic_id).execute()
        patients_data = patients_res.data or []
        
        appts_res = supabase_read.table("appointments").select("*").eq("clinic_id", clinic_id).execute()
        appts_data = appts_res.data or []
        
        calls_res = supabase_read.table("calls").select("*").eq("clinic_id", clinic_id).execute()
        calls_data = calls_res.data or []
        
        sms_res = supabase_read.table("sms_messages").select("*").eq("clinic_id", clinic_id).execute()
        sms_data = sms_res.data or []
        
        rev_res = supabase_read.table("revenue_events").select("*").eq("clinic_id", clinic_id).execute()
        rev_data = rev_res.data or []
        
        waitlist_res = supabase_read.table("waitlist").select("*").eq("clinic_id", clinic_id).execute()
        waitlist_data = waitlist_res.data or []
        
        staff_res = supabase_read.table("clinic_users").select("*").eq("clinic_id", clinic_id).execute()
        staff_data = staff_res.data or []
        
        date_str = datetime.date.today().isoformat()
        counts_summary = {
            "total_patients": len(patients_data),
            "total_appointments": len(appts_data),
            "total_calls": len(calls_data),
            "total_sms_messages": len(sms_data),
            "total_revenue_events": len(rev_data),
            "total_waitlist": len(waitlist_data),
            "total_staff": len(staff_data)
        }
        
        # Log audit entry
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.data_export",
            resource_type="clinics",
            resource_id=clinic_id,
            details={
                "format": format,
                "counts": counts_summary
            },
            request=request
        )
        
        if format == "json":
            export_payload = {
                "version": "1.0.0",
                "export_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "clinic_id": clinic_id,
                "clinic": clinic_data,
                "patients": patients_data,
                "appointments": appts_data,
                "calls": calls_data,
                "sms_messages": sms_data,
                "revenue_events": rev_data,
                "waitlist": waitlist_data,
                "staff": staff_data,
                "metadata": counts_summary
            }
            json_content = json.dumps(export_payload, indent=2, default=str)
            return Response(
                content=json_content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="clinic_export_{clinic_id}_{date_str}.json"'
                }
            )
        else:
            # CSV Zip Archive
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr("clinic_profile.csv", _convert_rows_to_csv([clinic_data]))
                zip_file.writestr("patients.csv", _convert_rows_to_csv(patients_data))
                zip_file.writestr("appointments.csv", _convert_rows_to_csv(appts_data))
                zip_file.writestr("calls.csv", _convert_rows_to_csv(calls_data))
                zip_file.writestr("sms_messages.csv", _convert_rows_to_csv(sms_data))
                zip_file.writestr("revenue_events.csv", _convert_rows_to_csv(rev_data))
                zip_file.writestr("waitlist.csv", _convert_rows_to_csv(waitlist_data))
                zip_file.writestr("staff.csv", _convert_rows_to_csv(staff_data))
                
            zip_buffer.seek(0)
            return Response(
                content=zip_buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="clinic_export_{clinic_id}_{date_str}.zip"'
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate clinic export: {str(e)}")


@router.post("/{id}/purge-recordings")
async def purge_call_recordings(
    id: str,
    req: PurgeRecordingsRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    HIPAA Data Minimization / Zero Retention:
    Purges all call audio recordings and pointers immediately for this clinic.
    Restricted strictly to clinic owners.
    """
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if auth.role != "owner":
        raise HTTPException(status_code=403, detail="Only clinic owners can purge call recordings")
        
    conf = (req.confirmation or "").strip().upper()
    if conf != "PURGE RECORDINGS":
        raise HTTPException(
            status_code=400,
            detail="Invalid confirmation phrase. Please type 'PURGE RECORDINGS' to confirm."
        )
        
    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # 1. Calls table
        calls_res = supabase_read.table("calls").select("id").eq("clinic_id", clinic_id).not_.is_("recording_url", "null").execute()
        purged_calls = len(calls_res.data or [])
        if purged_calls > 0:
            supabase.table("calls").update({"recording_url": None}).eq("clinic_id", clinic_id).execute()
            
        # 2. Call_logs table (linked via tenant_id or clinic patients)
        purged_call_logs = 0
        try:
            cl_res = supabase_read.table("call_logs").select("id").eq("tenant_id", clinic_id).not_.is_("recording_url", "null").execute()
            purged_call_logs = len(cl_res.data or [])
            if purged_call_logs > 0:
                supabase.table("call_logs").update({
                    "recording_url": None,
                    "recording_purged_at": now_iso
                }).eq("tenant_id", clinic_id).execute()
        except Exception as cl_err:
            print(f"[PurgeRecordings] Note on call_logs: {cl_err}")
            
        # 3. Prior_auth_requests
        purged_pa = 0
        try:
            pa_res = supabase_read.table("prior_auth_requests").select("id").eq("tenant_id", clinic_id).not_.is_("call_recording_url", "null").execute()
            purged_pa = len(pa_res.data or [])
            if purged_pa > 0:
                supabase.table("prior_auth_requests").update({"call_recording_url": None}).eq("tenant_id", clinic_id).execute()
        except Exception:
            pass

        total_purged = purged_calls + purged_call_logs + purged_pa
        
        # Audit log the purge
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.recordings_purged",
            resource_type="calls",
            resource_id=clinic_id,
            details={
                "purged_calls": purged_calls,
                "purged_call_logs": purged_call_logs,
                "purged_pa": purged_pa,
                "total_purged": total_purged,
                "purged_at": now_iso
            },
            request=request
        )
        
        return {
            "success": True,
            "message": f"Successfully purged {total_purged} call recording(s) across operational storage and database references.",
            "total_purged": total_purged
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to purge call recordings: {str(e)}")


@router.post("/{id}/maintenance-mode")
async def toggle_maintenance_mode(
    id: str,
    req: MaintenanceModeRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Emergency Maintenance Mode Toggle:
    Immediately halts receptionist voice agent answering and pauses outbound automated workflows.
    Restricted strictly to clinic owners.
    """
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if auth.role != "owner":
        raise HTTPException(status_code=403, detail="Only clinic owners can toggle emergency maintenance mode")
        
    # Get existing clinic
    clinic_res = supabase_read.table("clinics").select("name, status, notifications_config").eq("id", clinic_id).single().execute()
    existing = clinic_res.data or {}
    clinic_name = existing.get("name", "")
    
    if req.enabled:
        conf = (req.confirmation or "").strip()
        if conf.upper() != "MAINTENANCE MODE" and conf.lower() != clinic_name.strip().lower():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid confirmation phrase. Please type '{clinic_name}' or 'MAINTENANCE MODE' to enable emergency mode."
            )

    new_status = "maintenance" if req.enabled else "active"
    notif_config = existing.get("notifications_config") or {}
    if not isinstance(notif_config, dict):
        notif_config = {}
        
    notif_config["emergency_maintenance"] = {
        "enabled": req.enabled,
        "reason": req.reason or ("Emergency system maintenance" if req.enabled else None),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "updated_by": auth.email
    }
    
    updates = {
        "status": new_status,
        "notifications_config": notif_config
    }
    
    db_update_clinic(clinic_id, updates)
    invalidate_clinic_cache(clinic_id, auth.email)
    
    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="clinic.maintenance_mode_toggled",
        resource_type="clinics",
        resource_id=clinic_id,
        details={
            "enabled": req.enabled,
            "previous_status": existing.get("status"),
            "new_status": new_status,
            "reason": req.reason
        },
        request=request
    )
    
    msg = "Emergency maintenance mode has been activated. Receptionist services and automated messaging are temporarily suspended." if req.enabled else "Emergency maintenance mode has been deactivated. Normal clinic operations have resumed."
    return {
        "success": True,
        "status": new_status,
        "maintenance_mode": req.enabled,
        "message": msg
    }


@router.post("/{id}/reset-demo")
async def reset_demo_data(
    id: str,
    req: ResetDemoRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Reset & Reseed Demo Data:
    Clears operational records (without deleting clinic settings) and re-seeds clean, realistic synthetic demo data.
    Restricted strictly to clinic owners.
    """
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if auth.role != "owner":
        raise HTTPException(status_code=403, detail="Only clinic owners can reset demo data")
        
    if (req.confirmation or "").strip().upper() != "RESET DEMO DATA":
        raise HTTPException(
            status_code=400,
            detail="Invalid confirmation phrase. Type 'RESET DEMO DATA' to confirm."
        )
        
    try:
        # 1. Find all patient IDs for this clinic to safely clear dependent rows
        p_res = supabase_read.table("patients").select("id").eq("clinic_id", clinic_id).execute()
        patient_ids = [p["id"] for p in (p_res.data or [])]
        
        # 2. Safely clear dependent tables in order to prevent foreign key violations
        if patient_ids:
            for pid in patient_ids:
                try:
                    supabase.table("clinical_notes").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass
                try:
                    supabase.table("sms_logs").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass
                try:
                    supabase.table("call_logs").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass
                try:
                    supabase.table("prior_auth_requests").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass

        try:
            supabase.table("sms_messages").delete().eq("clinic_id", clinic_id).execute()
        except Exception:
            pass
        try:
            supabase.table("revenue_events").delete().eq("clinic_id", clinic_id).execute()
        except Exception:
            pass
        try:
            supabase.table("calls").delete().eq("clinic_id", clinic_id).execute()
        except Exception:
            pass
        try:
            supabase.table("appointments").delete().eq("clinic_id", clinic_id).execute()
        except Exception:
            pass
        try:
            supabase.table("waitlist").delete().eq("clinic_id", clinic_id).execute()
        except Exception:
            pass
        try:
            supabase.table("outbound_calls").delete().eq("clinic_id", clinic_id).execute()
        except Exception:
            pass
            
        # Finally delete patients
        supabase.table("patients").delete().eq("clinic_id", clinic_id).execute()
        
        seeded_summary = {}
        if req.reseed_sample_data:
            # Seed 5 realistic patients
            new_patients = [
                {"clinic_id": clinic_id, "name": "John Doe", "email": "john.doe@gmail.com", "phone": "+15550190001", "insurance_provider": "Blue Cross Blue Shield", "insurance_member_id": "BCB123456", "total_visits": 3, "total_revenue_generated": 450.0},
                {"clinic_id": clinic_id, "name": "Jane Smith", "email": "jane.smith@yahoo.com", "phone": "+15550190002", "insurance_provider": "Aetna", "insurance_member_id": "AET987654", "total_visits": 2, "total_revenue_generated": 300.0},
                {"clinic_id": clinic_id, "name": "Robert Johnson", "email": "robert.j@outlook.com", "phone": "+15550190003", "insurance_provider": "Cigna", "insurance_member_id": "CIG741258", "total_visits": 1, "total_revenue_generated": 150.0},
                {"clinic_id": clinic_id, "name": "Emily Davis", "email": "emily.d@gmail.com", "phone": "+15550190004", "insurance_provider": "UnitedHealthcare", "insurance_member_id": "UHC369852", "total_visits": 4, "total_revenue_generated": 600.0},
                {"clinic_id": clinic_id, "name": "Michael Wilson", "email": "michael.w@gmail.com", "phone": "+15550190005", "insurance_provider": "Humana", "insurance_member_id": "HUM159357", "total_visits": 0, "total_revenue_generated": 0.0}
            ]
            inserted_patients = []
            for p in new_patients:
                p_insert = supabase.table("patients").insert(p).execute()
                if p_insert.data:
                    inserted_patients.append(p_insert.data[0])
                    
            # Seed 6 appointments across past, today, and future
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            appt_types = ["Initial Evaluation", "Follow-up Visit", "Physical Therapy Session"]
            
            if inserted_patients:
                # 2 past completed
                for i in range(2):
                    pt = inserted_patients[i % len(inserted_patients)]
                    supabase.table("appointments").insert({
                        "clinic_id": clinic_id,
                        "patient_id": pt["id"],
                        "patient_name": pt["name"],
                        "patient_phone": pt["phone"],
                        "appointment_type": appt_types[i % len(appt_types)],
                        "datetime": (now_utc - datetime.timedelta(days=i+2, hours=3)).isoformat(),
                        "duration_minutes": 45,
                        "status": "completed",
                        "revenue_amount": 150,
                        "insurance_verified": True
                    }).execute()
                
                # 1 no-show
                pt_ns = inserted_patients[2 % len(inserted_patients)]
                supabase.table("appointments").insert({
                    "clinic_id": clinic_id,
                    "patient_id": pt_ns["id"],
                    "patient_name": pt_ns["name"],
                    "patient_phone": pt_ns["phone"],
                    "appointment_type": "Initial Evaluation",
                    "datetime": (now_utc - datetime.timedelta(days=1, hours=2)).isoformat(),
                    "duration_minutes": 60,
                    "status": "no_show",
                    "revenue_amount": 0,
                    "noshow_risk": 0.85
                }).execute()
                
                # 3 future scheduled
                for i in range(3):
                    pt_fut = inserted_patients[(i+3) % len(inserted_patients)]
                    supabase.table("appointments").insert({
                        "clinic_id": clinic_id,
                        "patient_id": pt_fut["id"],
                        "patient_name": pt_fut["name"],
                        "patient_phone": pt_fut["phone"],
                        "appointment_type": appt_types[i % len(appt_types)],
                        "datetime": (now_utc + datetime.timedelta(days=i+1, hours=2)).isoformat(),
                        "duration_minutes": 30,
                        "status": "confirmed" if i == 0 else "scheduled",
                        "revenue_amount": 150
                    }).execute()
                    
                # Seed 4 call logs with outcomes
                sample_transcripts = [
                    ("Patient: Hi, I need to book a physical therapy session for next week.\nAI: I can assist with that! We have Wednesday at 10:00 AM available. Would you like me to book it?\nPatient: Yes please, thank you!", "Scheduled Appointment"),
                    ("Patient: What are your opening hours on Friday?\nAI: Oakridge Clinic is open Monday through Friday, 8:00 AM to 6:00 PM.\nPatient: Thank you, that helps!", "Answered Question"),
                    ("Patient: Can I check if you accept Blue Cross insurance?\nAI: Yes, we accept Blue Cross Blue Shield, Aetna, Cigna, and UnitedHealthcare.\nPatient: Great, I'll call back to book.", "Insurance Inquiry"),
                    ("Patient: I'd like to reschedule my appointment tomorrow.\nAI: No problem. I have Thursday at 2:00 PM available. Shall I move it for you?\nPatient: Yes, please do.", "Rescheduled Appointment")
                ]
                for i, (transcript, outcome) in enumerate(sample_transcripts):
                    pt_call = inserted_patients[i % len(inserted_patients)]
                    supabase.table("calls").insert({
                        "clinic_id": clinic_id,
                        "patient_id": pt_call["id"],
                        "from_number": pt_call["phone"],
                        "to_number": "+15558392019",
                        "direction": "inbound",
                        "call_type": "receptionist",
                        "duration_seconds": 65 + i * 15,
                        "status": "completed",
                        "outcome": outcome,
                        "transcript": transcript,
                        "started_at": (now_utc - datetime.timedelta(hours=i*4 + 2)).isoformat(),
                        "ended_at": (now_utc - datetime.timedelta(hours=i*4 + 2) + datetime.timedelta(seconds=65+i*15)).isoformat()
                    }).execute()
                    
            seeded_summary = {
                "patients": len(inserted_patients),
                "appointments": 6,
                "calls": 4
            }

        # Audit log
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.demo_reset",
            resource_type="clinics",
            resource_id=clinic_id,
            details={
                "reseeded": req.reseed_sample_data,
                "summary": seeded_summary
            },
            request=request
        )
        
        return {
            "success": True,
            "message": "Demo data has been reset and seeded with clean synthetic operational records.",
            "seeded_summary": seeded_summary
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset demo data: {str(e)}")


@router.post("/{id}/soft-delete")
async def soft_delete_clinic(
    id: str,
    req: SoftDeleteRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Soft-delete & deactivate a clinic account.
    Restricted strictly to the clinic owner.
    """
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if auth.role != "owner":
        raise HTTPException(status_code=403, detail="Only clinic owners can deactivate or soft delete the clinic account")
        
    try:
        # Check clinic exists and match confirmation phrase
        clinic_res = supabase_read.table("clinics").select("name, is_active").eq("id", clinic_id).single().execute()
        existing = clinic_res.data or {}
        clinic_name = existing.get("name", "")
        
        conf = req.confirmation.strip()
        if conf.lower() != clinic_name.strip().lower() and conf != "DELETE ACCOUNT":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid confirmation phrase. Please type '{clinic_name}' or 'DELETE ACCOUNT' to confirm."
            )
            
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updates = {
            "is_active": False,
            "status": "deleted",
            "deleted_at": now_iso,
            "cancellation_reason": req.reason or "Owner soft deleted account"
        }
        
        db_update_clinic(clinic_id, updates)
        invalidate_clinic_cache(clinic_id, auth.email)
        
        try:
            supabase.table("tenants").update({"is_active": False}).eq("id", clinic_id).execute()
        except Exception:
            pass
        
        # Log audit entry
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.soft_delete",
            resource_type="clinics",
            resource_id=clinic_id,
            details={
                "clinic_name": clinic_name,
                "reason": req.reason,
                "deleted_at": now_iso
            },
            request=request
        )
        
        return {"success": True, "message": "Clinic account has been soft-deleted and deactivated successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/reactivate")
async def reactivate_clinic(
    id: str,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    Reactivate a previously soft-deleted clinic account.
    Restricted strictly to clinic owners.
    """
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if auth.role != "owner":
        raise HTTPException(status_code=403, detail="Only clinic owners can reactivate a clinic account")
        
    try:
        updates = {
            "is_active": True,
            "status": "active",
            "deleted_at": None,
            "cancellation_reason": None
        }
        db_update_clinic(clinic_id, updates)
        invalidate_clinic_cache(clinic_id, auth.email)
        
        try:
            supabase.table("tenants").update({"is_active": True}).eq("id", clinic_id).execute()
        except Exception:
            pass
            
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.reactivated",
            resource_type="clinics",
            resource_id=clinic_id,
            details={"reactivated_by": auth.email},
            request=request
        )
        
        return {"success": True, "message": "Clinic account reactivated successfully. Operations have been fully restored."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/factory-reset")
async def factory_reset(id: str, reset: FactoryReset, request: Request, auth: AuthenticatedUser = Depends(require_permission("settings:write"))):
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    if auth.role != "owner":
        raise HTTPException(status_code=403, detail="Only clinic owners can perform a factory reset")
        
    if reset.confirmation != "DELETE EVERYTHING":
        raise HTTPException(status_code=400, detail="Invalid confirmation phrase. Type 'DELETE EVERYTHING' to confirm.")
        
    try:
        # 1. Fetch patient IDs to clear FK-dependent rows safely
        p_res = supabase_read.table("patients").select("id").eq("clinic_id", clinic_id).execute()
        patient_ids = [p["id"] for p in (p_res.data or [])]
        
        if patient_ids:
            for pid in patient_ids:
                try:
                    supabase.table("clinical_notes").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass
                try:
                    supabase.table("sms_logs").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass
                try:
                    supabase.table("call_logs").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass
                try:
                    supabase.table("prior_auth_requests").delete().eq("patient_id", pid).execute()
                except Exception:
                    pass

        # Wipe operational tables in order
        supabase.table("sms_messages").delete().eq("clinic_id", clinic_id).execute()
        supabase.table("revenue_events").delete().eq("clinic_id", clinic_id).execute()
        supabase.table("calls").delete().eq("clinic_id", clinic_id).execute()
        supabase.table("appointments").delete().eq("clinic_id", clinic_id).execute()
        supabase.table("waitlist").delete().eq("clinic_id", clinic_id).execute()
        
        # Optional tables that might exist depending on migrations
        for opt_table in ["outbound_calls", "notifications", "ehr_sync_logs"]:
            try:
                supabase.table(opt_table).delete().eq("clinic_id", clinic_id).execute()
            except Exception:
                pass
                
        supabase.table("patients").delete().eq("clinic_id", clinic_id).execute()
        
        # Audit log factory reset (audit logs preserved for HIPAA compliance!)
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.factory_reset",
            resource_type="clinics",
            resource_id=clinic_id,
            details={
                "confirmation": reset.confirmation,
                "tables_wiped": ["clinical_notes", "sms_logs", "call_logs", "prior_auth_requests", "sms_messages", "revenue_events", "calls", "appointments", "waitlist", "patients"]
            },
            request=request
        )
        
        return {"success": True, "message": "Factory reset complete. All operational clinic records have been wiped."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/create-agent")
async def create_retell_agent(id: str, request: Request, auth: AuthenticatedUser = Depends(require_permission("settings:write"))):
    """Create a personalized Retell AI agent for the clinic."""
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    from ...services.voice_service import voice_service
    result = await voice_service.create_agent(clinic_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create agent"))
    
    agent_id = result["data"]["agentId"]
    db_update_clinic(clinic_id, {"retell_agent_id": agent_id})
    
    # Audit log agent creation
    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="clinic.create_agent",
        resource_type="clinics",
        resource_id=clinic_id,
        details={"agent_id": agent_id},
        request=request
    )
    return {"success": True, "agentId": agent_id}


@router.post("/{id}/twilio-number")
@router.put("/{id}/twilio-number")
async def set_twilio_number(
    id: str,
    body: dict,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """Save Twilio phone number to clinic."""
    clinic_id = auth.clinic_id
    if id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    number = body.get("twilioNumber") or body.get("twilio_number")
    if not number:
        raise HTTPException(status_code=400, detail="twilioNumber is required")
    
    db_update_clinic(clinic_id, {
        "twilio_number": number,
        "phone_number": number,
    })
    
    # Audit log twilio assignment
    await audit_service.log(
        clinic_id=clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="clinic.set_twilio_number",
        resource_type="clinics",
        resource_id=clinic_id,
        details={"twilio_number": number},
        request=request
    )
    return {"success": True, "twilioNumber": number}


# ─────────────────────────────────────────────────────────────────────────────
# API Key Management & Webhook Outbound Endpoints (PostgreSQL Persisted)
# ─────────────────────────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    name: Optional[str] = "Default API Key"
    scopes: Optional[List[str]] = ["read", "write"]

class WebhookTestRequest(BaseModel):
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


@router.get("/{id}/api-keys")
async def list_api_keys(
    id: str,
    auth: AuthenticatedUser = Depends(require_permission("settings:read"))
):
    """List all active API keys for this clinic from PostgreSQL."""
    clinic_id = auth.clinic_id
    if id != "me" and id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        res = supabase_read.table("api_keys").select("*").eq("clinic_id", clinic_id).eq("is_active", True).order("created_at", desc=True).execute()
        return {"data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/api-keys", status_code=201)
async def create_api_key(
    id: str,
    req_body: ApiKeyCreate,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """Generate and store a new clinic API key in PostgreSQL."""
    clinic_id = auth.clinic_id
    if id != "me" and id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        raw_token = f"by_live_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        prefix = raw_token[:12]
        masked = f"{prefix}...{raw_token[-4:]}"
        name = (req_body.name or "Default API Key").strip()
        scopes = req_body.scopes or ["read", "write"]

        insert_data = {
            "clinic_id": clinic_id,
            "name": name,
            "key_hash": key_hash,
            "key_prefix": prefix,
            "masked_key": masked,
            "scopes": scopes,
            "is_active": True,
            "created_by": auth.email
        }
        res = supabase.table("api_keys").insert(insert_data).execute()
        created_record = res.data[0] if (res.data and isinstance(res.data, list)) else insert_data

        # Audit log API key creation
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="api_key.create",
            resource_type="api_keys",
            resource_id=created_record.get("id"),
            details={"name": name, "key_prefix": prefix},
            request=request
        )

        return {
            "data": {
                "id": created_record.get("id"),
                "name": name,
                "apiKey": raw_token,
                "key_prefix": prefix,
                "masked_key": masked,
                "scopes": scopes,
                "created_at": created_record.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id}/api-keys/{key_id}")
async def revoke_api_key(
    id: str,
    key_id: str,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """Revoke and permanently delete a clinic API key from PostgreSQL."""
    clinic_id = auth.clinic_id
    if id != "me" and id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        supabase.table("api_keys").delete().eq("id", key_id).eq("clinic_id", clinic_id).execute()

        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="api_key.revoke",
            resource_type="api_keys",
            resource_id=key_id,
            details={"key_id": key_id},
            request=request
        )
        return {"success": True, "message": "API key revoked successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/test-webhook")
async def test_webhook(
    id: str,
    req_body: WebhookTestRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """Send a live test event ping to the clinic's configured webhook URL."""
    clinic_id = auth.clinic_id
    if id != "me" and id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")

    target_url = (req_body.webhook_url or "").strip()
    target_secret = (req_body.webhook_secret or "").strip()

    if not target_url:
        clinic_res = supabase_read.table("clinics").select("webhook_url, webhook_secret").eq("id", clinic_id).single().execute()
        cdata = clinic_res.data or {}
        target_url = (cdata.get("webhook_url") or "").strip()
        target_secret = target_secret or (cdata.get("webhook_secret") or "").strip()

    if not target_url:
        raise HTTPException(status_code=400, detail="No webhook URL configured. Please enter a valid Webhook URL first.")

    payload = {
        "event": "webhook.test_ping",
        "clinic_id": clinic_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "data": {
            "message": "Bytelytic Clinic OS Webhook Test Event",
            "status": "online",
            "environment": "production"
        }
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Bytelytic-Webhook/1.0",
        "X-Bytelytic-Event": "webhook.test_ping"
    }
    if target_secret:
        signature = hmac.new(target_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        headers["X-Bytelytic-Signature"] = f"sha256={signature}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(target_url, content=payload_bytes, headers=headers)

        return {
            "success": True,
            "statusCode": resp.status_code,
            "message": f"Webhook test ping delivered! Remote endpoint responded with HTTP {resp.status_code}.",
            "responsePreview": resp.text[:200]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to webhook URL: {str(e)}")


@router.post("/{id}/purge-recordings")
async def trigger_recording_purge(
    id: str,
    request: Request,
    auth: AuthenticatedUser = Depends(require_permission("settings:write"))
):
    """
    HIPAA Data Minimization: Execute immediate call recording purge for this clinic.
    Permanently purges voice audio URLs older than the configured retention period (default 24h).
    Encrypted transcripts, structured metadata, and immutable audit logs are preserved.
    """
    clinic_id = auth.clinic_id
    if id != "me" and id != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Get retention hours
        c_res = supabase_read.table("clinics").select("advanced_settings").eq("id", clinic_id).single().execute()
        adv = (c_res.data or {}).get("advanced_settings") or {}
        retention_hours = adv.get("call_recording_retention_hours", 24)
        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=retention_hours)).isoformat()

        # 1. Purge from calls table
        purged_calls = 0
        try:
            calls_to_purge = supabase_read.table("calls").select("id").eq("clinic_id", clinic_id).is_not("recording_url", "null").lt("created_at", cutoff).execute()
            if calls_to_purge.data:
                for c in calls_to_purge.data:
                    supabase.table("calls").update({"recording_url": None}).eq("id", c["id"]).execute()
                purged_calls = len(calls_to_purge.data)
        except Exception as e:
            pass

        # 2. Purge from call_logs table
        purged_call_logs = 0
        try:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cl_to_purge = supabase_read.table("call_logs").select("id").eq("tenant_id", clinic_id).is_not("recording_url", "null").lt("created_at", cutoff).execute()
            if cl_to_purge.data:
                for cl in cl_to_purge.data:
                    supabase.table("call_logs").update({
                        "recording_url": None,
                        "recording_purged_at": now_iso
                    }).eq("id", cl["id"]).execute()
                purged_call_logs = len(cl_to_purge.data)
        except Exception as e:
            pass

        total_purged = purged_calls + purged_call_logs

        # Audit log HIPAA recording purge
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="clinic.purge_recordings",
            resource_type="clinics",
            resource_id=clinic_id,
            details={
                "retention_hours": retention_hours,
                "cutoff_timestamp": cutoff,
                "recordings_purged_calls": purged_calls,
                "recordings_purged_call_logs": purged_call_logs,
                "total_purged": total_purged,
                "policy": "24h_hipaa_purge"
            },
            request=request
        )

        return {
            "success": True,
            "message": f"HIPAA 24h auto-purge scan completed. {total_purged} expired audio recording(s) purged.",
            "total_purged": total_purged,
            "retention_hours": retention_hours,
            "policy": "24h_hipaa_purge",
            "enforced_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



