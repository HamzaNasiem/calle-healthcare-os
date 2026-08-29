import datetime
from typing import Dict, Any, List, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ..core.database import supabase
from ..core.config import settings

from google.oauth2.credentials import Credentials
from ..core.database import supabase
from ..core.config import settings
from .connectors.google_calendar_connector import GoogleCalendarConnector

def _get_google_credentials(clinic_id: str) -> tuple[Credentials, dict]:
    res = supabase.table("clinics").select("google_refresh_token, google_calendar_id, timezone, business_hours").eq("id", clinic_id).execute()
    
    if not res.data or len(res.data) == 0:
        raise Exception(f"Clinic {clinic_id} not found")
        
    clinic = res.data[0]
    refresh_token = clinic.get("google_refresh_token")
    
    if not refresh_token:
        raise Exception(f"Clinic {clinic_id} has no Google refresh token")
        
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET
    )
    return creds, clinic

def _parse_time_parts(t_str: str) -> Optional[tuple[int, int]]:
    """Helper to parse time string like '08:00', '8:00 AM', '6:00 PM', '18:00' into (hour, minute)."""
    try:
        t_clean = t_str.strip().upper()
        is_pm = "PM" in t_clean
        is_am = "AM" in t_clean
        t_clean = t_clean.replace("AM", "").replace("PM", "").strip()
        parts = t_clean.split(":")
        hour = int(parts[0].strip())
        minute = int(parts[1].strip()) if len(parts) > 1 else 0

        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)
        return None
    except Exception:
        return None

def _parse_business_hours(day_val: Any) -> Optional[dict]:
    """
    Parse business hours for a single day from either:
    - dict: {"enabled": True, "start": "08:00", "end": "18:00"} or {"open": True, ...}
    - str: "08:00-18:00" or "closed"
    Returns dict with start_hour, start_min, end_hour, end_min if open, or None if closed/invalid.
    """
    if not day_val:
        return None

    start_str = "08:00"
    end_str = "18:00"

    if isinstance(day_val, dict):
        if day_val.get("closed") is True:
            return None
        is_open = day_val.get("enabled", True) if "enabled" in day_val else day_val.get("open", True)
        if not is_open:
            return None
        start_str = str(day_val.get("start") or "08:00").strip()
        end_str = str(day_val.get("end") or "18:00").strip()
    elif isinstance(day_val, str):
        val_str = day_val.strip().lower()
        if val_str in ["closed", "off", "none", ""] or not val_str:
            return None
        cleaned_str = val_str.replace("–", "-").replace("—", "-")
        if "-" in cleaned_str:
            parts = cleaned_str.split("-")
            start_str = parts[0].strip()
            end_str = parts[1].strip()
        else:
            return None
    else:
        return None

    start_t = _parse_time_parts(start_str)
    end_t = _parse_time_parts(end_str)

    if not start_t or not end_t:
        return None

    start_hour, start_min = start_t
    end_hour, end_min = end_t

    if (start_hour * 60 + start_min) >= (end_hour * 60 + end_min):
        return None

    return {
        "start_hour": start_hour,
        "start_min": start_min,
        "end_hour": end_hour,
        "end_min": end_min
    }

def _get_day_key(date_obj: datetime.datetime) -> str:
    # return "mon", "tue", etc
    return date_obj.strftime("%a").lower()

class CalendarService:
    def __init__(self):
        self.connector = GoogleCalendarConnector()
    
    async def get_available_slots(self, clinic_id: str, date_str: str, duration_minutes: int = 30) -> Dict[str, Any]:
        try:
            creds, clinic = _get_google_credentials(clinic_id)
            
            # Note: timezone handling is simplified. In a robust setup, use pytz or zoneinfo
            # We assume date_str is "YYYY-MM-DD"
            day_date = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
            day_key = _get_day_key(day_date)
            full_day_name = day_date.strftime("%A").lower()
            
            biz_hours = clinic.get("business_hours") or {}
            if not isinstance(biz_hours, dict):
                biz_hours = {}
                
            day_val = biz_hours.get(day_key) or biz_hours.get(full_day_name)
            parsed_hours = _parse_business_hours(day_val)
            if not parsed_hours:
                return {"success": True, "data": []}
            
            # Create local time bounds without strict timezone object for API parameters
            day_start_str = f"{date_str[:10]}T{parsed_hours['start_hour']:02d}:{parsed_hours['start_min']:02d}:00"
            day_end_str = f"{date_str[:10]}T{parsed_hours['end_hour']:02d}:{parsed_hours['end_min']:02d}:00"
            
            # Assume clinic timezone matches local bounds for Google API formatting
            import pytz
            tz = pytz.timezone(clinic.get("timezone", "America/Chicago"))
            
            day_start = tz.localize(datetime.datetime.strptime(day_start_str, "%Y-%m-%dT%H:%M:%S"))
            day_end = tz.localize(datetime.datetime.strptime(day_end_str, "%Y-%m-%dT%H:%M:%S"))
            
            calendar_id = clinic.get("google_calendar_id") or "primary"
            busy = await self.connector.get_busy_windows(creds, calendar_id, day_start, day_end)
                
            slots = []
            slot_delta = datetime.timedelta(minutes=duration_minutes)
            cursor = day_start
            
            while cursor + slot_delta <= day_end:
                slot_end = cursor + slot_delta
                overlaps = any((cursor < b["end"] and slot_end > b["start"]) for b in busy)
                if not overlaps:
                    slots.append(cursor.isoformat())
                cursor += slot_delta
                
            return {"success": True, "data": slots}
        except Exception as e:
            print(f"[calendar.getAvailableSlots] clinicId={clinic_id} Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_event(self, clinic_id: str, appointment: dict) -> Dict[str, Any]:
        try:
            creds, clinic = _get_google_credentials(clinic_id)
            
            start_time = datetime.datetime.fromisoformat(appointment["datetime"].replace("Z", "+00:00"))
            end_time = start_time + datetime.timedelta(minutes=appointment.get("duration_minutes", 30))
            
            tz_str = clinic.get("timezone", "America/Chicago")
            
            event = {
                "summary": f"{appointment.get('appointment_type', 'Appointment')} — {appointment['patient_name']}",
                "description": appointment.get("notes", "Booked by Bytelytic OS AI"),
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": tz_str
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": tz_str
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": 30}]
                }
            }
            
            calendar_id = clinic.get("google_calendar_id") or "primary"
            event_id = await self.connector.create_event(creds, calendar_id, event)
            
            print(f"[calendar.createEvent] clinicId={clinic_id} eventId={event_id}")
            return {"success": True, "data": {"googleEventId": event_id}}
        except Exception as e:
            print(f"[calendar.createEvent] clinicId={clinic_id} Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def cancel_event(self, clinic_id: str, google_event_id: str) -> Dict[str, Any]:
        try:
            creds, clinic = _get_google_credentials(clinic_id)
            calendar_id = clinic.get("google_calendar_id") or "primary"
            
            from googleapiclient.errors import HttpError
            try:
                await self.connector.delete_event(creds, calendar_id, google_event_id)
            except HttpError as e:
                if e.resp.status in [404, 410]:
                    print(f"[calendar.cancelEvent] clinicId={clinic_id} event already gone eventId={google_event_id}")
                    return {"success": True}
                raise e
            
            print(f"[calendar.cancelEvent] clinicId={clinic_id} eventId={google_event_id} deleted")
            return {"success": True}
        except Exception as e:
            print(f"[calendar.cancelEvent] clinicId={clinic_id} Error: {str(e)}")
            return {"success": False, "error": str(e)}

calendar_service = CalendarService()
