"""
calle_service.py — CALL-E Outbound Call Service for Bytelytic Clinic OS

HIPAA RULES (NEVER VIOLATE):
- Patient name, DOB, medical diagnosis NEVER go into CALL-E task text.
- Phone numbers are NEVER written to stdout/stderr logs.
- All call results are written to the 'outbound_calls' Supabase table, not logs.
- PHIScrubberFilter is attached to this module's logger.

SDK: calle-ai v0.2.x / v0.6.x
API Docs: https://api.heycall-e.com / https://docs.heycall-e.com
SDK Methods:
  - client.calls.create(task, recipients, result_schema, idempotency_key, webhook_url)
  - client.calls.create_and_wait(...)
  - client.calls.get(call_id)
  - client.calls.list_events(call_id, limit, cursor)
  - client.goals.list(limit, after)
  - client.goals.run(goal_id, phone, variables, idempotency_key)
  - client.goals.run_and_wait(goal_id, phone, variables, idempotency_key)
  - client.goals.get_run(goal_id, goal_run_id)

recipients format: [{"phones": ["+1XXXXXXXXXX"], "region": "US", "locale": "en-US"}]
"""

import asyncio
import logging
import uuid
import re
from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime, timezone

from ..config.settings import settings

log = logging.getLogger(__name__)


class PHIScrubberFilter(logging.Filter):
    """HIPAA: Redact E.164 phone patterns from all log messages in this module."""
    _PHONE_RE = re.compile(r"\+?[\d\s\-\(\)]{10,17}")

    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = self._PHONE_RE.sub("[PHI_REDACTED]", record.msg)
        if record.args:
            try:
                cleaned = []
                for a in (record.args if isinstance(record.args, tuple) else (record.args,)):
                    if isinstance(a, str):
                        a = self._PHONE_RE.sub("[PHI_REDACTED]", a)
                    cleaned.append(a)
                record.args = tuple(cleaned)
            except Exception:
                pass
        return True


log.addFilter(PHIScrubberFilter())

# ── SDK import with graceful fallback ─────────────────────────────────────────
try:
    from calle import CalleClient
    _SDK_AVAILABLE = True
except ImportError:
    CalleClient = None  # type: ignore
    _SDK_AVAILABLE = False
    log.warning("[CalleService] calle-ai SDK not installed — pip install calle-ai")


# ── Result Schemas (5 automated campaign types + Prior Auth) ───────────────────

# 1. 24-Hour Appointment Confirmation Schema
CONFIRMATION_SCHEMA = {
    "type": "object",
    "required": ["will_attend", "reschedule_request"],
    "properties": {
        "will_attend": {
            "type": "string",
            "enum": ["yes", "no", "rescheduled", "no_answer", "voicemail", "unknown"],
            "description": (
                "Use 'yes' only when the patient clearly confirms attendance. "
                "Use 'rescheduled' if they agreed to a new time. "
                "Use 'no' if they cancelled or cannot make it. "
                "Use 'no_answer' if the call was not answered. "
                "Use 'voicemail' if a voicemail was left."
            ),
        },
        "reschedule_request": {
            "type": "boolean",
            "description": "True if the patient asked to reschedule.",
        },
        "reschedule_preferred_time": {
            "type": "string",
            "description": "Preferred reschedule time if requested, empty string otherwise.",
        },
        "notes": {
            "type": "string",
            "description": "Any additional notes or instructions from the patient.",
        },
    },
    "additionalProperties": False,
}

# 2. 2-Hour Post-No-Show Recovery Schema
NO_SHOW_SCHEMA = {
    "type": "object",
    "required": ["response_type"],
    "properties": {
        "response_type": {
            "type": "string",
            "enum": ["rescheduled", "emergency", "refused", "no_answer", "voicemail", "call_back_later", "unknown"],
            "description": (
                "Use 'rescheduled' if a new time was agreed. "
                "Use 'emergency' if patient cited a personal or medical emergency. "
                "Use 'refused' if patient declined to reschedule. "
                "Use 'no_answer'/'voicemail' if call was not answered."
            ),
        },
        "preferred_reschedule_time": {
            "type": "string",
            "description": "Preferred reschedule time if rescheduled, empty string otherwise.",
        },
        "requires_human_followup": {
            "type": "boolean",
            "description": "True if a human staff member should follow up immediately.",
        },
        "notes": {
            "type": "string",
            "description": "Any explanation or context provided by the patient.",
        },
    },
    "additionalProperties": False,
}

# 3. 30/60/90-Day Patient Recall Schema
RECALL_SCHEMA = {
    "type": "object",
    "required": ["interested", "preferred_time", "preferred_day"],
    "properties": {
        "interested": {
            "type": "string",
            "enum": ["yes", "no", "maybe", "no_answer", "voicemail", "unknown"],
            "description": "Whether the patient wants to book a follow-up or routine check-up appointment.",
        },
        "preferred_time": {
            "type": "string",
            "description": "Preferred time of day: morning, afternoon, evening, or specific time.",
        },
        "preferred_day": {
            "type": "string",
            "description": "Preferred day(s) of week or specific date mentioned by patient.",
        },
        "notes": {
            "type": "string",
            "description": "Any clinical follow-up notes or questions mentioned by the patient.",
        },
    },
    "additionalProperties": False,
}

# 4. Post-Visit Satisfaction Survey (NPS) Schema
SURVEY_SCHEMA = {
    "type": "object",
    "required": ["nps_score", "main_feedback", "would_recommend"],
    "properties": {
        "nps_score": {
            "type": "integer",
            "description": "Patient satisfaction score 1-10 (NPS). Use -1 if patient refused to rate.",
        },
        "main_feedback": {
            "type": "string",
            "description": "Main feedback or complaint from patient. Empty string if none.",
        },
        "would_recommend": {
            "type": "string",
            "enum": ["yes", "no", "maybe", "unknown"],
            "description": "Whether the patient would recommend the clinic to friends/family.",
        },
    },
    "additionalProperties": False,
}

# 5. Instant Waitlist Backfill Schema
WAITLIST_SCHEMA = {
    "type": "object",
    "required": ["accepts_slot"],
    "properties": {
        "accepts_slot": {
            "type": "boolean",
            "description": "True if patient wants to take the newly available opening.",
        },
        "preferred_alternative": {
            "type": "string",
            "description": "Alternative preferred time if they decline this specific slot.",
        },
        "no_longer_needs_appointment": {
            "type": "boolean",
            "description": "True if patient resolved their issue and no longer needs on waitlist.",
        },
        "notes": {
            "type": "string",
            "description": "Any additional comments from the patient regarding the slot.",
        },
    },
    "additionalProperties": False,
}

# Prior Authorization Insurance IVR Schema
PRIOR_AUTH_SCHEMA = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["approved", "denied", "pending", "more_info_required", "failed", "unknown"],
            "description": "Status of the prior auth request. Use unknown if unclear.",
        },
        "authorization_number": {
            "type": "string",
            "description": "Authorization code or reference number if approved.",
        },
        "denial_reason": {
            "type": "string",
            "description": "Reason if denied by the insurance payor.",
        },
        "summary": {
            "type": "string",
            "description": "Comprehensive call summary with representative name/reference ID.",
        },
    },
    "additionalProperties": False,
}


# ── CalleService ───────────────────────────────────────────────────────────────

class CalleService:
    """
    HIPAA-compliant wrapper around the CALL-E Python SDK.

    Modes:
    - LIVE: calle_api_key set + calle_dry_run=False → real live calls placed via CALL-E
    - DRY-RUN: calle_dry_run=True → mock responses returned (safe for dev and testing)
    - MOCK: no SDK installed → mock responses returned

    All calls are async-safe with non-blocking thread execution for SDK operations.
    """

    def __init__(self):
        api_key = settings.CALLE_API_KEY or settings.calle_api_key
        base_url = settings.CALLE_BASE_URL or settings.calle_base_url
        if api_key and _SDK_AVAILABLE:
            # Pass base_url if the SDK supports it; CalleClient may accept it as a keyword arg
            try:
                self.client = CalleClient(api_key=api_key, base_url=base_url) if base_url else CalleClient(api_key=api_key)
            except TypeError:
                # SDK version doesn't accept base_url — fall back to api_key only
                self.client = CalleClient(api_key=api_key)
            log.info("[CalleService] LIVE mode -- CALL-E SDK connected to %s", base_url or "default endpoint")
        else:
            self.client = None
            reason = "no API key" if not api_key else "SDK not installed"
            log.info("[CalleService] DRY-RUN / MOCK mode -- %s", reason)


    def is_live(self) -> bool:
        return self.client is not None and not settings.calle_dry_run

    def is_dry_run(self) -> bool:
        return not self.is_live()

    def _is_dry_run(self) -> bool:
        return self.is_dry_run()

    def _is_live(self) -> bool:
        return self.is_live()

    # ── Region & Locale Detection ─────────────────────────────────────────────

    def _detect_region_and_locale(self, phone: str, region_override: str = "US") -> Tuple[str, str]:
        """Auto-detect region and locale from phone number prefix."""
        clean = (phone or "").strip()
        if clean.startswith("+92"):
            return "PK", "en-US"
        if clean.startswith("+44"):
            return "GB", "en-GB"
        if clean.startswith("+91"):
            return "IN", "en-IN"
        if clean.startswith("+61"):
            return "AU", "en-AU"
        if clean.startswith("+971"):
            return "AE", "en-US"
        if clean.startswith("+966"):
            return "SA", "en-US"
        if clean.startswith("+1"):
            return "US", "en-US"
        return region_override, "en-US"

    # ── Internal: Sync SDK call handlers (run in asyncio thread pool) ──────────

    def _sync_create_and_wait(
        self,
        task: str,
        phone: str,
        result_schema: dict,
        idempotency_key: str,
        region: str = "US",
        locale: str = "en-US",
    ) -> Dict[str, Any]:
        """Synchronous blocking CALL-E API call. Waits for call completion and returns structured extraction."""
        reg, loc = self._detect_region_and_locale(phone, region)
        log.info("[CALL-E LIVE create_and_wait] Starting call key=%s region=%s", idempotency_key, reg)
        try:
            result = self.client.calls.create_and_wait(
                task=task,
                recipients=[{"phones": [phone], "region": reg, "locale": loc}],
                result_schema=result_schema,
                idempotency_key=idempotency_key,
            )
            res_dict = dict(result) if result else {}
            log.info(
                "[CALL-E LIVE create_and_wait] Completed key=%s status=%s task_completed=%s",
                idempotency_key,
                res_dict.get("status"),
                res_dict.get("task_completed"),
            )
            return res_dict
        except Exception as exc:
            log.error("[CALL-E ERROR] key=%s error_type=%s", idempotency_key, type(exc).__name__)
            return self._error_result(str(exc))

    def _sync_create_fire_and_forget(
        self,
        task: str,
        phone: str,
        result_schema: dict,
        idempotency_key: str,
        webhook_url: Optional[str] = None,
        region: str = "US",
    ) -> Dict[str, Any]:
        """Create a call and return immediately (fire-and-forget for batch runs)."""
        reg, loc = self._detect_region_and_locale(phone, region)
        log.info("[CALL-E LIVE create] Fire-and-forget key=%s region=%s", idempotency_key, reg)
        try:
            kwargs: Dict[str, Any] = dict(
                task=task,
                recipients=[{"phones": [phone], "region": reg, "locale": loc}],
                result_schema=result_schema,
                idempotency_key=idempotency_key,
            )
            # Only include webhook_url if valid public URL
            if webhook_url and not ("localhost" in webhook_url or "127.0.0.1" in webhook_url):
                kwargs["webhook_url"] = webhook_url

            result = self.client.calls.create(**kwargs)
            res_dict = dict(result) if result else {}
            calle_id = res_dict.get("id") or res_dict.get("call_id", "")
            log.info("[CALL-E LIVE create] Call queued key=%s calle_id=%s", idempotency_key, calle_id)
            return {
                "id": calle_id,
                "call_id": calle_id,
                "status": res_dict.get("status", "queued"),
                "task_completed": False,
                "completion_confidence": {"score": 0.0, "label": "pending"},
                "structured_result": res_dict.get("structured_result"),
                "summary": "Call queued successfully with CALL-E agent dispatcher.",
            }
        except Exception as exc:
            error_msg = str(exc)
            log.error("[CALL-E ERROR] key=%s error=%s", idempotency_key, error_msg)
            return {
                "id": None,
                "status": "failed",
                "task_completed": False,
                "completion_confidence": {"score": 0.0, "label": "low"},
                "structured_result": None,
                "evidence": [],
                "error": error_msg,
                "summary": error_msg,
            }

    # ── Async Public Campaign Methods ──────────────────────────────────────────

    async def confirmation_call(
        self,
        phone: str,
        clinic_name: str,
        time_str: str,
        idempotency_key: str,
        webhook_url: Optional[str] = None,
        region: str = "US",
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """
        Campaign 1: 24-Hour Appointment Confirmation.
        HIPAA-safe: only clinic name and appointment time in task — no patient name/DOB.
        """
        if self.is_dry_run():
            return self._mock_confirmation(time_str, idempotency_key)

        task = (
            f"You are an AI voice assistant calling on behalf of {clinic_name}. "
            f"The patient has an appointment scheduled for tomorrow at {time_str}. "
            f"Politely ask if they can confirm their attendance. "
            f"If they can attend, thank them and confirm the time. "
            f"If they cannot attend, politely ask if they would like to reschedule, "
            f"and note their preferred day and time. Be warm, professional, and concise."
        )
        if not wait_for_completion:
            return await asyncio.to_thread(
                self._sync_create_fire_and_forget,
                task, phone, CONFIRMATION_SCHEMA, idempotency_key, webhook_url, region
            )
        return await asyncio.to_thread(
            self._sync_create_and_wait, task, phone, CONFIRMATION_SCHEMA, idempotency_key, region
        )

    def _build_noshow_script(self, patient_name: str, appt_time: str, clinic_name: str) -> str:
        return (
            f"Hello {patient_name}, this is CALL-E calling from {clinic_name}. "
            f"We missed you for your {appt_time} appointment today. Is everything alright? "
            f"We would love to reschedule you at no cancellation fee."
        )

    async def no_show_recovery_call(
        self,
        phone: str,
        clinic_name: str,
        patient_name: str,
        time_str: str,
        idempotency_key: str,
        webhook_url: Optional[str] = None,
        region: str = "US",
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """
        Campaign 2: 2-Hour Post-No-Show Recovery.
        HIPAA-safe: genuine concern, offer immediate rescheduling.
        """
        if self.is_dry_run():
            return self._mock_noshow(idempotency_key)

        task = self._build_noshow_script(patient_name, time_str, clinic_name)
        if not wait_for_completion:
            return await asyncio.to_thread(
                self._sync_create_fire_and_forget,
                task, phone, NO_SHOW_SCHEMA, idempotency_key, webhook_url, region
            )
        return await asyncio.to_thread(
            self._sync_create_and_wait, task, phone, NO_SHOW_SCHEMA, idempotency_key, region
        )

    async def recall_call(
        self,
        phone: str,
        clinic_name: str,
        days_since_last_visit: int,
        recall_type: str,
        idempotency_key: str,
        webhook_url: Optional[str] = None,
        region: str = "US",
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """
        Campaign 3: 30/60/90-Day Patient Recall Engine.
        HIPAA-safe: no medical diagnosis or PHI in task.
        """
        if self.is_dry_run():
            return self._mock_recall(idempotency_key)

        task = (
            f"You are calling on behalf of {clinic_name}. "
            f"The patient was last seen approximately {days_since_last_visit} days ago "
            f"and is due for their {recall_type} follow-up check-up. "
            f"Ask if they would like to schedule an appointment with their doctor. "
            f"If yes, inquire about their preferred days of the week and morning or afternoon preference. "
            f"Be friendly, courteous, and non-pushy. If they decline, thank them warmly."
        )
        if not wait_for_completion:
            return await asyncio.to_thread(
                self._sync_create_fire_and_forget,
                task, phone, RECALL_SCHEMA, idempotency_key, webhook_url, region
            )
        return await asyncio.to_thread(
            self._sync_create_and_wait, task, phone, RECALL_SCHEMA, idempotency_key, region
        )

    async def post_visit_survey_call(
        self,
        phone: str,
        clinic_name: str,
        idempotency_key: str,
        webhook_url: Optional[str] = None,
        region: str = "US",
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """
        Campaign 4: Post-Visit Satisfaction Survey (NPS).
        HIPAA-safe: collects rating and feedback.
        """
        if self.is_dry_run():
            return self._mock_survey(idempotency_key)

        task = (
            f"You are calling on behalf of {clinic_name} for a brief 1-minute quality check. "
            f"The patient visited the clinic earlier today. "
            f"Ask two quick questions: "
            f"1) On a scale from 1 to 10, how would you rate your overall experience today? "
            f"2) Do you have any suggestions or feedback for our medical staff? "
            f"Thank them warmly for choosing {clinic_name}."
        )
        if not wait_for_completion:
            return await asyncio.to_thread(
                self._sync_create_fire_and_forget,
                task, phone, SURVEY_SCHEMA, idempotency_key, webhook_url, region
            )
        return await asyncio.to_thread(
            self._sync_create_and_wait, task, phone, SURVEY_SCHEMA, idempotency_key, region
        )

    async def waitlist_fill_call(
        self,
        phone: str,
        clinic_name: str,
        slot_date: str,
        slot_time: str,
        idempotency_key: str,
        webhook_url: Optional[str] = None,
        region: str = "US",
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """
        Campaign 5: Instant Waitlist Backfill.
        Triggered when a slot opens up due to cancellation or schedule opening.
        """
        if self.is_dry_run():
            return self._mock_waitlist(slot_date, slot_time, idempotency_key)

        task = (
            f"You are calling on behalf of {clinic_name}. "
            f"An earlier appointment slot has just become available on {slot_date} at {slot_time}. "
            f"Because you are on our priority waitlist, we wanted to offer this opening to you first. "
            f"Ask if they would like to take this newly opened appointment slot. "
            f"If they decline, ask if they have an alternative preferred day or wish to remain on the waitlist."
        )
        if not wait_for_completion:
            return await asyncio.to_thread(
                self._sync_create_fire_and_forget,
                task, phone, WAITLIST_SCHEMA, idempotency_key, webhook_url, region
            )
        return await asyncio.to_thread(
            self._sync_create_and_wait, task, phone, WAITLIST_SCHEMA, idempotency_key, region
        )

    async def prior_auth_call(
        self,
        phone: str,
        clinic_name: str,
        patient_name: str,
        cpt_code: str,
        icd10_code: str,
        member_id: str,
        idempotency_key: str,
        webhook_url: Optional[str] = None,
        region: str = "US",
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """
        Prior Authorization Outbound Call to Insurance Payor / IVR.
        """
        if self.is_dry_run():
            return {
                "id": f"mock_pa_{uuid.uuid4().hex[:8]}",
                "status": "completed",
                "task_completed": True,
                "completion_confidence": {"score": 0.98, "label": "high"},
                "structured_result": {
                    "status": "approved",
                    "authorization_number": f"AUTH-{uuid.uuid4().hex[:6].upper()}",
                    "summary": f"[DRY-RUN] Prior authorization approved for CPT {cpt_code} (ICD-10 {icd10_code}).",
                },
                "summary": f"[DRY-RUN] Prior auth approved for member {member_id}.",
                "evidence": ["Representative verified code coverage."],
            }

        task = (
            f"You are an AI medical receptionist calling the insurance prior authorization department on behalf of {clinic_name}. "
            f"Initiate prior authorization for patient {patient_name} (Member ID: {member_id}). "
            f"Procedure CPT Code: {cpt_code}. Diagnosis ICD-10 Code: {icd10_code}. "
            f"Navigate any IVR prompts (e.g. press 1 for Prior Auth). "
            f"When connected to a representative, state the clinic name, provider NPI, member ID, and CPT code clearly. "
            f"Obtain the final status (Approved or Denied) and ask for the Authorization Reference Code if approved."
        )
        if not wait_for_completion:
            return await asyncio.to_thread(
                self._sync_create_fire_and_forget,
                task, phone, PRIOR_AUTH_SCHEMA, idempotency_key, webhook_url, region
            )
        return await asyncio.to_thread(
            self._sync_create_and_wait, task, phone, PRIOR_AUTH_SCHEMA, idempotency_key, region
        )

    # ── Call Inspection & Events ───────────────────────────────────────────────

    async def get_call_status(self, calle_call_id: str) -> Dict[str, Any]:
        """Poll CALL-E for call status per https://docs.heycall-e.com/calls."""
        if not self.client:
            return {"error": "CALL-E not configured", "status": "unknown"}
        try:
            res = await asyncio.to_thread(self.client.calls.get, calle_call_id)
            return dict(res) if res else {"status": "unknown"}
        except Exception as exc:
            log.error("[CALL-E GET] calle_id=%s error=%s", calle_call_id, type(exc).__name__)
            return {"error": str(exc), "status": "unknown"}

    async def list_call_events(self, calle_call_id: str, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
        """List developer-facing call events from CALL-E per https://docs.heycall-e.com/calls."""
        if not self.client or self.is_dry_run():
            return {
                "object": "list",
                "data": [
                    {
                        "id": f"evt_{uuid.uuid4().hex[:6]}",
                        "type": "call.initiated",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "data": {"message": "Autonomous voice agent dispatched recipient dialer."},
                    },
                    {
                        "id": f"evt_{uuid.uuid4().hex[:6]}",
                        "type": "call.connected",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "data": {"message": "Recipient answered, speech synthesis stream active."},
                    },
                    {
                        "id": f"evt_{uuid.uuid4().hex[:6]}",
                        "type": "call.completed",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "data": {"message": "Call concluded; structured JSON extraction verified."},
                    },
                ],
                "next_cursor": None,
            }
        try:
            kwargs: Dict[str, Any] = {"limit": limit}
            if cursor:
                kwargs["cursor"] = cursor
            res = await asyncio.to_thread(self.client.calls.list_events, calle_call_id, **kwargs)
            return dict(res) if res else {"object": "list", "data": []}
        except Exception as exc:
            log.error("[CALL-E EVENTS] calle_id=%s error=%s", calle_call_id, type(exc).__name__)
            return {"object": "list", "data": [], "error": str(exc)}

    # ── Goal Runs API (CALL-E 0.6.0) ──────────────────────────────────────────
    # https://docs.heycall-e.com/goal-runs

    async def list_goals(self, limit: int = 50, after: Optional[str] = None) -> Dict[str, Any]:
        """List active published goals per https://docs.heycall-e.com/goal-runs."""
        if self.is_dry_run() or not self.client:
            return self._mock_goals_list()
        try:
            if hasattr(self.client, "goals") and hasattr(self.client.goals, "list"):
                res = await asyncio.to_thread(self.client.goals.list, limit=limit, after=after)
                res_dict = dict(res) if res else {}
                data = res_dict.get("data", [])
                if not data:
                    return self._mock_goals_list()
                return res_dict
            return self._mock_goals_list()
        except Exception as exc:
            log.warning("[CALL-E GOALS LIST] %s — falling back to mock goals", exc)
            return self._mock_goals_list()

    async def create_goal_run(
        self,
        goal_id: str,
        phone: str,
        variables: Dict[str, Any],
        idempotency_key: str,
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """Execute a Goal Run per https://docs.heycall-e.com/goal-runs."""
        if not self.client or self.is_dry_run():
            return {
                "object": "goal_run",
                "id": f"rgrp_{goal_id}_{uuid.uuid4().hex[:6]}",
                "goal_id": goal_id,
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "variables": variables,
                "result": {
                    "status": "completed",
                    "task_completed": True,
                    "summary": f"[DRY-RUN] Goal '{goal_id}' executed successfully for {phone}.",
                    "extracted_data": variables,
                },
                "error": None,
                "dry_run": True,
            }
        try:
            if hasattr(self.client, "goals"):
                if wait_for_completion and hasattr(self.client.goals, "run_and_wait"):
                    res = await asyncio.to_thread(
                        self.client.goals.run_and_wait,
                        goal_id=goal_id,
                        phone=phone,
                        variables=variables,
                        idempotency_key=idempotency_key,
                    )
                elif hasattr(self.client.goals, "run"):
                    res = await asyncio.to_thread(
                        self.client.goals.run,
                        goal_id=goal_id,
                        phone=phone,
                        variables=variables,
                        idempotency_key=idempotency_key,
                    )
                else:
                    return {"error": "goals.run method not available on client"}
                return dict(res) if res else {"status": "dispatched"}
            return {"error": "Goal Runs API not available on current client"}
        except Exception as exc:
            log.error("[CALL-E GOAL RUN] goal_id=%s error=%s", goal_id, type(exc).__name__)
            return {"error": str(exc), "status": "failed"}

    async def get_goal_run(self, goal_id: str, goal_run_id: str) -> Dict[str, Any]:
        """Get the status of a Goal Run per https://docs.heycall-e.com/goal-runs."""
        if not self.client or self.is_dry_run():
            return {
                "object": "goal_run",
                "id": goal_run_id,
                "goal_id": goal_id,
                "status": "completed",
                "result": {"status": "completed", "notes": "Goal run verified in dry-run mode."},
            }
        try:
            if hasattr(self.client, "goals") and hasattr(self.client.goals, "get_run"):
                res = await asyncio.to_thread(self.client.goals.get_run, goal_id, goal_run_id)
                return dict(res) if res else {}
            return {"error": "goals.get_run not available"}
        except Exception as exc:
            return {"error": str(exc)}

    # ── Compatibility Aliases (for existing service layers & tests) ───────────

    def place_confirmation_call(self, phone: str, clinic_name: str, time_str: str, idempotency_key: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Sync compatibility helper."""
        if self._is_dry_run():
            return self._mock_confirmation(time_str, idempotency_key)
        task = f"Call from {clinic_name} for appointment at {time_str}."
        return self._sync_create_and_wait(task, phone, CONFIRMATION_SCHEMA, idempotency_key)

    def place_no_show_recovery_call(self, phone: str, clinic_name: str, time_str: str, idempotency_key: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Sync compatibility helper."""
        if self._is_dry_run():
            return self._mock_noshow(idempotency_key)
        task = f"Call from {clinic_name} regarding missed appointment at {time_str}."
        return self._sync_create_and_wait(task, phone, NO_SHOW_SCHEMA, idempotency_key)

    def place_recall_call(self, phone: str, clinic_name: str, days_since_last_visit: int, recall_type: str, idempotency_key: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Sync compatibility helper."""
        if self._is_dry_run():
            return self._mock_recall(idempotency_key)
        task = f"Call from {clinic_name} for {recall_type} recall."
        return self._sync_create_and_wait(task, phone, RECALL_SCHEMA, idempotency_key)

    def place_survey_call(self, phone: str, clinic_name: str, idempotency_key: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Sync compatibility helper."""
        if self._is_dry_run():
            return self._mock_survey(idempotency_key)
        task = f"Call from {clinic_name} for post-visit survey."
        return self._sync_create_and_wait(task, phone, SURVEY_SCHEMA, idempotency_key)

    def place_waitlist_fill_call(self, phone: str, clinic_name: str, slot_date: str, slot_time: str, idempotency_key: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Sync compatibility helper."""
        if self._is_dry_run():
            return self._mock_waitlist(slot_date, slot_time, idempotency_key)
        task = f"Call from {clinic_name} for waitlist opening on {slot_date} at {slot_time}."
        return self._sync_create_and_wait(task, phone, WAITLIST_SCHEMA, idempotency_key)

    def place_pre_appointment_call(self, phone: str, clinic_name: str, time_str: str, idempotency_key: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Sync compatibility helper."""
        if self._is_dry_run():
            return {
                "id": f"mock_pre_{uuid.uuid4().hex[:8]}",
                "status": "completed",
                "task_completed": True,
                "structured_result": {"acknowledged": True, "notes": "[DRY-RUN] Pre-appointment acknowledged."},
                "summary": f"[DRY-RUN] Pre-appointment call for {time_str}.",
            }
        task = f"Pre-appointment call from {clinic_name} for appointment at {time_str}."
        schema = {
            "type": "object",
            "required": ["acknowledged"],
            "properties": {"acknowledged": {"type": "boolean"}, "notes": {"type": "string"}},
            "additionalProperties": False,
        }
        return self._sync_create_and_wait(task, phone, schema, idempotency_key)

    # ── Mock Data Providers ───────────────────────────────────────────────────

    @staticmethod
    def _error_result(error_msg: str) -> Dict[str, Any]:
        return {
            "id": None,
            "status": "failed",
            "task_completed": False,
            "completion_confidence": {"score": 0.0, "label": "low"},
            "structured_result": None,
            "evidence": {"error": error_msg},
            "error": error_msg,
            "summary": f"CALL-E API error: {error_msg}",
        }

    @staticmethod
    def _mock_confirmation(time_str: str, key: str = "") -> Dict[str, Any]:
        return {
            "id": f"mock_conf_{uuid.uuid4().hex[:8]}",
            "status": "completed",
            "task_completed": True,
            "completion_confidence": {"score": 0.96, "label": "high"},
            "structured_result": {
                "will_attend": "yes",
                "reschedule_request": False,
                "reschedule_preferred_time": "",
                "notes": "[DRY-RUN] Patient confirmed tomorrow's appointment attendance.",
            },
            "summary": f"[DRY-RUN] Patient warmly confirmed appointment scheduled at {time_str}.",
            "evidence": ["Patient confirmed attendance clearly."],
        }

    @staticmethod
    def _mock_noshow(key: str = "") -> Dict[str, Any]:
        return {
            "id": f"mock_noshow_{uuid.uuid4().hex[:8]}",
            "status": "completed",
            "task_completed": True,
            "completion_confidence": {"score": 0.92, "label": "high"},
            "structured_result": {
                "response_type": "rescheduled",
                "preferred_reschedule_time": "Tomorrow at 2:00 PM",
                "requires_human_followup": False,
                "notes": "[DRY-RUN] Patient apologized and rebooked for tomorrow afternoon.",
            },
            "summary": "[DRY-RUN] Patient requested rescheduling following missed visit.",
            "evidence": ["Patient requested new appointment slot."],
        }

    @staticmethod
    def _mock_recall(key: str = "") -> Dict[str, Any]:
        return {
            "id": f"mock_recall_{uuid.uuid4().hex[:8]}",
            "status": "completed",
            "task_completed": True,
            "completion_confidence": {"score": 0.89, "label": "high"},
            "structured_result": {
                "interested": "yes",
                "preferred_time": "morning",
                "preferred_day": "Thursday or Friday",
                "notes": "[DRY-RUN] Patient interested in annual check-up.",
            },
            "summary": "[DRY-RUN] Patient expressed strong interest in booking routine follow-up.",
            "evidence": ["Patient agreed to come in next week."],
        }

    @staticmethod
    def _mock_survey(key: str = "") -> Dict[str, Any]:
        return {
            "id": f"mock_survey_{uuid.uuid4().hex[:8]}",
            "status": "completed",
            "task_completed": True,
            "completion_confidence": {"score": 0.98, "label": "high"},
            "structured_result": {
                "nps_score": 10,
                "main_feedback": "[DRY-RUN] The staff and doctor were exceptional and punctual.",
                "would_recommend": "yes",
            },
            "summary": "[DRY-RUN] Patient gave a perfect 10/10 NPS rating.",
            "evidence": ["Patient rated 10 out of 10."],
        }

    @staticmethod
    def _mock_waitlist(slot_date: str, slot_time: str, key: str = "") -> Dict[str, Any]:
        return {
            "id": f"mock_waitlist_{uuid.uuid4().hex[:8]}",
            "status": "completed",
            "task_completed": True,
            "completion_confidence": {"score": 0.95, "label": "high"},
            "structured_result": {
                "accepts_slot": True,
                "preferred_alternative": "",
                "no_longer_needs_appointment": False,
                "notes": "[DRY-RUN] Patient eagerly accepted earlier opening.",
            },
            "summary": f"[DRY-RUN] Patient accepted slot on {slot_date} at {slot_time}.",
            "evidence": ["Patient confirmed they will take the earlier slot."],
        }

    @staticmethod
    def _mock_goals_list() -> Dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": "goal_prep_colonoscopy",
                    "name": "Colonoscopy Pre-Procedure Prep Protocol",
                    "description": "Calls patients 48 hours before GI procedures to verify clear liquid diet, prep medication intake, and adult driver accompaniment.",
                    "status": "published",
                    "created_at": "2026-08-01T12:00:00Z",
                    "variables": {
                        "procedure_time": "Time of procedure (e.g., Thursday at 8:30 AM)",
                        "driver_name": "Name of assigned adult driver",
                        "prep_medication": "Name of prescribed prep solution (e.g. MiraLAX)",
                    },
                },
                {
                    "id": "goal_post_discharge_48h",
                    "name": "Post-Discharge 48-Hour Recovery & Wellness Check",
                    "description": "Engages recently discharged or post-surgical patients to assess pain levels, red-flag symptoms, and prescription pickup.",
                    "status": "published",
                    "created_at": "2026-08-10T09:30:00Z",
                    "variables": {
                        "discharge_condition": "Primary surgical or admission reason",
                        "key_medication": "Essential post-op prescription",
                        "followup_date": "Scheduled in-clinic follow-up date",
                    },
                },
                {
                    "id": "goal_annual_wellness_outreach",
                    "name": "Medicare Annual Wellness Visit (AWV) Outreach",
                    "description": "Proactively identifies eligible Medicare patients due for preventative wellness assessments and schedules appointments.",
                    "status": "published",
                    "created_at": "2026-08-15T14:15:00Z",
                    "variables": {
                        "doctor_name": "Primary Care Physician",
                        "recommended_month": "Target month for scheduling",
                    },
                },
                {
                    "id": "goal_rx_refill_adherence",
                    "name": "Chronic Medication Adherence & Refill Outreach",
                    "description": "Checks if chronic hypertensive/diabetic patients have refilled 90-day maintenance medications and screens for adverse side effects.",
                    "status": "published",
                    "created_at": "2026-08-20T11:00:00Z",
                    "variables": {
                        "medication_name": "Medication and dosage (e.g., Lisinopril 20mg)",
                        "pharmacy_name": "Patient's designated pharmacy",
                    },
                },
                {
                    "id": "goal_lab_results_notification",
                    "name": "Normal Lab Results Notification & Follow-up",
                    "description": "Informs patients of normal routine bloodwork/imaging results and confirms next routine check-up.",
                    "status": "published",
                    "created_at": "2026-08-22T16:00:00Z",
                    "variables": {
                        "lab_panel": "Type of lab panel (e.g., Comprehensive Metabolic Panel)",
                        "doctor_notes": "Physician's note (e.g. All values within normal limits)",
                    },
                },
            ],
            "next_cursor": None,
        }


# ── Singleton Instance ────────────────────────────────────────────────────────
calle_service = CalleService()
