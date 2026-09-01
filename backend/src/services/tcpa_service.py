"""
TCPA & Quiet Hours Compliance Service
======================================
Enforces Telephone Consumer Protection Act (TCPA) compliance rules:
1. TCPA Permitted Window: 8:00 AM to 9:00 PM in the called party's local time zone.
   - Prohibits automated telephone calls and SMS communications before 8:00 AM or after 9:00 PM local time.
2. Clinic-Configured Quiet Hours:
   - Clinics can define custom quiet hours (e.g. 9:00 PM to 8:00 AM).
   - TCPA boundaries (8:00 AM - 9:00 PM) act as hard federal ceilings.
3. Timezone Awareness:
   - Evaluates local time based on the clinic's or recipient's IANA timezone.
"""

import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Dict, Any
from ..core.logger import log

DEFAULT_TCPA_START_HOUR = 8   # 8:00 AM local
DEFAULT_TCPA_END_HOUR = 21   # 9:00 PM local (21:00)


def parse_time_parts(time_str: str, default_hour: int, default_minute: int = 0) -> Tuple[int, int]:
    """Parses 'HH:MM' string into (hour, minute)."""
    try:
        parts = str(time_str).strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return max(0, min(23, h)), max(0, min(59, m))
    except Exception:
        return default_hour, default_minute


class TcpaComplianceService:
    def get_local_time(self, timezone_str: Optional[str] = None) -> datetime.datetime:
        """Resolves current local datetime for a clinic's timezone with safe fallbacks."""
        tz_name = timezone_str or "America/New_York"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            try:
                tz = ZoneInfo("America/New_York")
            except Exception:
                tz = datetime.timezone.utc
        return datetime.datetime.now(tz)

    def is_quiet_hours(
        self,
        timezone_str: Optional[str] = None,
        notifications_config: Optional[Dict[str, Any]] = None,
        now_override: Optional[datetime.datetime] = None,
    ) -> Tuple[bool, str]:
        """
        Determines whether the current local time falls within quiet hours.
        Returns: (is_quiet: bool, reason: str)
        If is_quiet is True, outbound calls or automated reminder SMS must be held or deferred.
        """
        conf = notifications_config or {}
        quiet_enabled = conf.get("quiet_hours_enabled", True)

        local_now = now_override or self.get_local_time(timezone_str)
        current_minute_of_day = local_now.hour * 60 + local_now.minute

        # 1. Federal TCPA Constraint: 8:00 AM (480 min) to 9:00 PM (1260 min)
        tcpa_start_min = DEFAULT_TCPA_START_HOUR * 60   # 08:00 (480)
        tcpa_end_min = DEFAULT_TCPA_END_HOUR * 60       # 21:00 (1260)

        if current_minute_of_day < tcpa_start_min or current_minute_of_day >= tcpa_end_min:
            time_formatted = local_now.strftime("%I:%M %p %Z")
            return (
                True,
                f"TCPA Quiet Hours Active: Outbound calls/SMS prohibited between 9:00 PM and 8:00 AM local time (current: {time_formatted})"
            )

        # 2. Clinic-specific quiet hours (if enabled)
        if quiet_enabled:
            start_str = str(conf.get("quiet_hours_start", "21:00"))
            end_str = str(conf.get("quiet_hours_end", "08:00"))

            s_h, s_m = parse_time_parts(start_str, 21, 0)
            e_h, e_m = parse_time_parts(end_str, 8, 0)

            start_min = s_h * 60 + s_m
            end_min = e_h * 60 + e_m

            # Overnight quiet hours window (e.g. 21:00 PM to 08:00 AM)
            if start_min > end_min:
                if current_minute_of_day >= start_min or current_minute_of_day < end_min:
                    time_formatted = local_now.strftime("%I:%M %p %Z")
                    return (
                        True,
                        f"Clinic Quiet Hours Active ({start_str} - {end_str}, current: {time_formatted})"
                    )
            else:
                # Daytime quiet hours window (e.g. 12:00 to 13:00)
                if start_min <= current_minute_of_day < end_min:
                    time_formatted = local_now.strftime("%I:%M %p %Z")
                    return (
                        True,
                        f"Clinic Quiet Hours Active ({start_str} - {end_str}, current: {time_formatted})"
                    )

        return False, "Allowed (Within permitted TCPA hours)"


tcpa_service = TcpaComplianceService()
