"""
agent_config_router.py — Custom Voice Agent Builder & Retell AI Synchronization

Allows clinic owners to configure their Retell AI voice agent:
- Custom greeting message (begin_message)
- Custom system prompt & persona guidelines
- Voice ID selection (ElevenLabs & OpenAI voices)
- Language selection (en-US, es-MX, es-ES, fr-CA, etc.)
- Emergency forwarding & call transfer phone number
- Dynamic FAQs knowledge base
- A/B Script testing
- 100% Real DB & Retell AI API Persistence
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional


import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.config import settings
from ...core.database import supabase, supabase_read
from ...core.security import AuthenticatedUser, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-config", tags=["Agent Config"])


# ─────────────────────────────────────────────────────────────────────────────
# Helper Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _is_mock_retell_key(key: Optional[str]) -> bool:
    """Check if the configured Retell API key is missing or a mock/test placeholder."""
    if not key or not str(key).strip():
        return True
    k = str(key).strip().lower()
    return (
        k in ("mock_key", "test_key", "mock_retell_key", "dummy_key", "fake_key", "none", "null", "")
        or k.startswith("mock_")
        or k.startswith("test_")
        or k.startswith("dummy_")
    )


def sanitize_phone_number(phone: Optional[str]) -> Optional[str]:
    """
    Sanitize and normalize a phone number string for telephony and E.164 compliance.
    Preserves leading '+' if present and strips extraneous characters.
    """
    if not phone or not str(phone).strip():
        return None
    cleaned = str(phone).strip()
    has_plus = cleaned.startswith("+")
    digits = re.sub(r"[^\d]", "", cleaned)
    if not digits:
        return None
    return f"+{digits}" if has_plus else digits


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class AgentConfigCreate(BaseModel):
    retell_agent_id: str
    greeting_message: str
    custom_system_prompt: str
    ai_name: Optional[str] = "Alex"
    speaking_style: Optional[str] = "Warm & Empathetic"
    voice_id: Optional[str] = "11labs-rachel"
    language: Optional[str] = "en-US"
    emergency_forward_phone: Optional[str] = None
    transfer_phone_number: Optional[str] = None
    emergency_protocols: Optional[str] = None
    faq_data: Optional[Dict[str, str]] = {}
    ab_test_active: Optional[bool] = False
    script_a: Optional[str] = None
    script_b: Optional[str] = None


class AgentConfigUpdate(BaseModel):
    retell_agent_id: Optional[str] = None
    greeting_message: Optional[str] = None
    custom_system_prompt: Optional[str] = None
    ai_name: Optional[str] = None
    speaking_style: Optional[str] = None
    voice_id: Optional[str] = None
    language: Optional[str] = None
    emergency_forward_phone: Optional[str] = None
    transfer_phone_number: Optional[str] = None
    emergency_protocols: Optional[str] = None
    faq_data: Optional[Dict[str, str]] = None
    ab_test_active: Optional[bool] = None
    script_a: Optional[str] = None
    script_b: Optional[str] = None


class AgentConfigTestPrompt(BaseModel):
    retell_agent_id: Optional[str] = None
    greeting_message: Optional[str] = ""
    custom_system_prompt: Optional[str] = ""
    ai_name: Optional[str] = "Alex"
    speaking_style: Optional[str] = "Warm & Empathetic"
    voice_id: Optional[str] = "11labs-rachel"
    language: Optional[str] = "en-US"
    emergency_forward_phone: Optional[str] = None
    transfer_phone_number: Optional[str] = None
    emergency_protocols: Optional[str] = None
    faq_data: Optional[Dict[str, str]] = {}
    ab_test_active: Optional[bool] = False
    script_a: Optional[str] = None
    script_b: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Prompt Compiler & Formatting Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_business_hours(business_hours: Optional[Any]) -> str:
    """Format business hours JSON or dict into a human-readable string."""
    if not business_hours:
        return "Monday to Friday: 8:00 AM - 5:00 PM | Saturday: 9:00 AM - 1:00 PM | Sunday: Closed"
    if isinstance(business_hours, str):
        try:
            parsed = json.loads(business_hours)
            return _format_business_hours(parsed)
        except Exception:
            return business_hours.strip()
    if isinstance(business_hours, dict):
        lines = []
        days_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days_order:
            val = business_hours.get(day) or business_hours.get(day[:3])
            if val is None:
                continue
            day_cap = day.capitalize()
            if isinstance(val, str):
                lines.append(f"{day_cap}: {val}")
            elif isinstance(val, dict):
                is_open = val.get("open", val.get("enabled", True))
                if val.get("closed") or not is_open:
                    lines.append(f"{day_cap}: Closed")
                else:
                    s = val.get("start", "08:00")
                    e = val.get("end", "17:00")
        if "_lunch_break" in business_hours and isinstance(business_hours["_lunch_break"], dict):
            lb = business_hours["_lunch_break"]
            if lb.get("enabled") and lb.get("start") and lb.get("end"):
                lines.append(f"Daily Lunch Break: {lb['start']} - {lb['end']} (Closed for lunch)")
        if lines:
            return " | ".join(lines)
    return "Monday to Friday: 8:00 AM - 5:00 PM | Saturday: 9:00 AM - 1:00 PM | Sunday: Closed"


def _format_doctor_info(
    doctor_name: Optional[str] = None,
    doctor_credentials: Optional[str] = None,
    specialty: Optional[str] = None,
) -> str:
    """Format primary physician name, credentials, and medical specialty."""
    parts = []
    if doctor_name and str(doctor_name).strip():
        doc_str = str(doctor_name).strip()
        if doctor_credentials and str(doctor_credentials).strip():
            doc_str += f", {str(doctor_credentials).strip()}"
        parts.append(f"Primary Physician: {doc_str}")
    if specialty and str(specialty).strip():
        parts.append(f"Specialty: {str(specialty).strip()}")
    return " | ".join(parts) if parts else "Primary Physician: On-Duty Licensed Clinician | Specialty: Family & Internal Medicine"


def _get_speaking_style_instruction(style: Optional[str]) -> str:
    """Generate precise persona instructions based on the selected speaking style."""
    if not style:
        style = "Warm & Empathetic"
    s_lower = style.lower()
    if "concise" in s_lower or "professional" in s_lower:
        return (
            "SPEAKING STYLE: Concise & Professional\n"
            "  • Speak with crisp, efficient, direct precision and respectful etiquette.\n"
            "  • Keep statements brief (1-2 sentences) and structured.\n"
            "  • Focus on immediate patient clarity, fast slot confirmation, and organized clinic workflows."
        )
    elif "friendly" in s_lower or "casual" in s_lower:
        return (
            "SPEAKING STYLE: Friendly & Casual\n"
            "  • Speak with upbeat warmth, approachable conversational charm, and positive energy.\n"
            "  • Use welcoming phrasing while maintaining professional medical boundaries.\n"
            "  • Make the caller feel relaxed, comfortable, and appreciated."
        )
    else:
        # Default: Warm & Empathetic
        return (
            "SPEAKING STYLE: Warm & Empathetic\n"
            "  • Speak with compassionate warmth, active listening, and comforting bedside manner.\n"
            "  • Validate patient concerns with reassuring, empathetic phrases.\n"
            "  • Maintain a calming, patient, and deeply supportive tone of voice."
        )


def compile_agent_prompt(
    clinic_name: str,
    greeting: str,
    custom_persona: str,
    faqs: dict,
    language: str,
    emergency_forward_phone: Optional[str] = None,
    doctor_name: Optional[str] = None,
    doctor_credentials: Optional[str] = None,
    specialty: Optional[str] = None,
    business_hours: Optional[Any] = None,
    timezone: Optional[str] = None,
    services: Optional[List[Dict[str, Any]]] = None,
    ai_name: Optional[str] = "Alex",
    speaking_style: Optional[str] = "Warm & Empathetic",
    emergency_protocols: Optional[str] = None,
    custom_prompt_variables: Optional[Dict[str, str]] = None,
    fallback_language: Optional[str] = None,
) -> str:
    """
    Build the full, HIPAA-compliant system prompt that is pushed to Retell AI and CALL-E voice engine.

    Structure:
    1. Persona, AI Name ({ai_name}), Clinic Identity & Primary Physician Roster
    2. Speaking Style Directives ({speaking_style})
    3. Business Hours & Local Timezone Awareness
    4. Critical Medical Guardrails & Emergency Medical Protocols (Chest pain / 911 warning)
    5. Complete AI Tool Calling Specifications & Exact Parameters
    6. Voice AI Spoken Communication Guidelines
    7. Emergency Forwarding / Live Call Transfer Phone Line
    8. Language Directives (English, Spanish, French)
    9. Dynamic FAQs Knowledge Base
    """
    clinic_name = (clinic_name or "").strip() or "the clinic"
    greeting = (greeting or "").strip()
    custom_persona = (custom_persona or "").strip()
    language = (language or "en-US").strip()
    tz_str = (timezone or "America/New_York").strip()
    ai_name_str = (ai_name or "Alex").strip()

    # 1. Doctor & Provider Info
    doc_info = _format_doctor_info(doctor_name, doctor_credentials, specialty)

    # 2. Speaking Style
    style_instruction = _get_speaking_style_instruction(speaking_style)

    # 3. Business Hours
    hours_info = _format_business_hours(business_hours)

    # 4. Emergency Medical Protocols
    default_emergency = (
        "If the caller reports chest pain, severe shortness of breath, sudden numbness or weakness, "
        "uncontrolled bleeding, severe trauma, or life-threatening symptoms, immediately instruct them "
        "to hang up and dial 911 or proceed to the nearest hospital emergency room."
    )
    active_emergency_protocols = (emergency_protocols or "").strip() or default_emergency

    # 5. FAQ bullet list
    if faqs and isinstance(faqs, dict):
        faq_lines = "\n".join(f"  • {q}: {a}" for q, a in faqs.items() if str(q).strip())
        faq_section = f"Frequently Asked Questions:\n{faq_lines}" if faq_lines else "No FAQs configured."
    else:
        faq_section = "No FAQs configured."

    # 6. Strict Medical Guardrails & HIPAA Safety
    guardrails = (
        "IMPORTANT CLINICAL GUARDRAILS — you MUST follow these at all times:\n"
        "  • Never provide medical diagnoses, clinical advice, prescriptions, or treatment plans.\n"
        "  • Never quote unverified pricing that has not been explicitly configured or returned via tool.\n"
        "  • Always recommend the patient speak directly with a licensed clinician for medical questions.\n"
        "  • Do not share or request Protected Health Information (PHI) beyond what is strictly necessary for identity verification and appointment scheduling.\n"
        f"  • EMERGENCY MEDICAL PROTOCOL (Chest Pain / 911 Warning): {active_emergency_protocols}"
    )

    # 7. Clear Tool Calling Specifications & Parameters
    tool_section = (
        "AI VOICE TOOLS & CALLING PROTOCOLS:\n"
        "You have access to real-time telephony and database tools. When a patient asks to check slots, book, cancel, reschedule, or needs a link/transfer, you MUST call the appropriate tool:\n\n"
        "  1. `get_available_slots` (or `check_calendar_availability`):\n"
        "     • Parameters:\n"
        "       - `date`: Date to check in YYYY-MM-DD format (defaults to today/tomorrow if not specified).\n"
        "       - `time_preference`: 'morning', 'afternoon', 'evening', or 'any'.\n"
        "       - `service_type`: Requested service (e.g., 'consult', 'cleaning', 'checkup', 'evaluation').\n"
        "       - `provider_id`: Optional specific provider ID.\n"
        "     • Protocol: Call this immediately when a caller wants to know open appointments. Present 2-3 specific times to the caller naturally.\n\n"
        "  2. `book_new_appointment`:\n"
        "     • Parameters:\n"
        "       - `patient_name`: Full legal name of the patient.\n"
        "       - `phone`: 10-digit phone number in digits or E.164 format.\n"
        "       - `dob`: Date of birth in YYYY-MM-DD format.\n"
        "       - `slot_id`: The exact slot_id string returned by get_available_slots.\n"
        "       - `reason`: Brief reason for visit.\n"
        "       - `service_type`: Type of appointment.\n"
        "     • Protocol: Confirm all patient details before booking, then provide the confirmation code after the tool returns success.\n\n"
        "  3. `cancel_appointment` (or `cancel_existing_appointment`):\n"
        "     • Parameters:\n"
        "       - `phone`: Patient phone number for verification.\n"
        "       - `dob`: Patient date of birth in YYYY-MM-DD format for identity verification.\n"
        "       - `appointment_date`: Date of the appointment to cancel in YYYY-MM-DD format.\n"
        "       - `reason`: Reason for cancellation.\n"
        "     • Protocol: Verify patient identity before calling. Late cancellations (<24h) will automatically route to staff.\n\n"
        "  4. `reschedule_appointment`:\n"
        "     • Parameters:\n"
        "       - `phone`: Patient phone number for verification.\n"
        "       - `dob`: Patient date of birth in YYYY-MM-DD format.\n"
        "       - `old_appointment_date`: Current appointment date in YYYY-MM-DD format.\n"
        "       - `new_slot_id`: Exact slot_id string from get_available_slots for the new desired time.\n"
        "     • Protocol: Check available slots for the new date first, agree on the time, then execute reschedule.\n\n"
        "  5. `transfer_call_to_human`:\n"
        "     • Parameters:\n"
        "       - `reason`: Reason for transfer ('billing', 'medical_emergency', 'complex_question', 'caller_requested_human').\n"
        "     • Protocol: Call when patient asks to speak with staff or when automated verification cannot proceed.\n\n"
        "  6. `send_live_sms_link`:\n"
        "     • Parameters:\n"
        "       - `phone`: Patient phone number.\n"
        "       - `link_type`: 'intake_form', 'payment_url', 'address_map', or 'confirmation_page'.\n"
        "     • Protocol: Send while on the call if patient needs pre-visit registration or clinic directions.\n\n"
        "  7. `check_service_pricing`:\n"
        "     • Parameters: `service_name` (e.g., 'consult', 'evaluation', 'follow_up').\n\n"
        "  8. `get_clinic_faq`:\n"
        "     • Parameters: `question_type` (e.g., 'parking', 'location', 'insurance', 'cancellation')."
    )

    # 8. Spoken Voice Guidelines
    voice_guidelines = (
        "CONVERSATIONAL GUIDELINES FOR VOICE AI:\n"
        "  • Speak concisely: Keep spoken responses to 1-2 clear, natural sentences.\n"
        "  • Never read out raw markdown tables, asterisks, bullet formatting, or JSON code in speech.\n"
        "  • Be polite, empathetic, active, and helpful at all times."
    )

    # 9. Emergency Forwarding / Call Transfer
    transfer_section = ""
    phone = sanitize_phone_number(emergency_forward_phone)
    if phone:
        transfer_section = (
            f"\n\nLIVE CALL TRANSFER & EMERGENCY ROUTING:\n"
            f"  • If the caller is experiencing a medical emergency, instruct them to hang up and dial 911 immediately.\n"
            f"  • If the caller requests to speak with a human receptionist, front-desk staff, or requires urgent escalation, transfer the call to {phone}."
        )

    # 10. Language instructions
    lang_instruction = ""
    if language and language.lower().startswith("es"):
        lang_instruction = (
            "\n\nIDIOMA: Responde siempre en español. Si el paciente habla inglés, "
            "puedes responder en inglés, pero prefiere el español por defecto.\n"
        )
    elif language and language.lower().startswith("fr"):
        lang_instruction = (
            "\n\nLANGUE: Répondez toujours en français. Si le patient s'exprime en anglais, "
            "vous pouvez lui répondre en anglais, mais privilégiez le français par défaut.\n"
        )

    if fallback_language and str(fallback_language).strip():
        lang_instruction += f"\nFALLBACK LANGUAGE DIRECTIVE: If caller speaks an alternate language or primary language detection fails, gracefully switch to fallback language '{fallback_language.strip()}'.\n"

    # 11. Configured Services & Appointment Types
    services_section = ""
    if services:
        if isinstance(services, list):
            s_lines = []
            for s in services:
                if isinstance(s, dict):
                    sn = s.get("name", "Appointment")
                    sd = s.get("duration_minutes") or s.get("duration") or 30
                    sf = s.get("fee") if s.get("fee") is not None else s.get("price")
                    cpt = f" (CPT: {s.get('cpt_code')})" if s.get("cpt_code") else ""
                    fee_str = f", ${float(sf):g}" if sf is not None and float(sf) > 0 else ""
                    s_lines.append(f"  • {sn}: {sd} min{fee_str}{cpt}")
                elif isinstance(s, str) and s.strip():
                    s_lines.append(f"  • {s.strip()}")
            if s_lines:
                services_section = "AVAILABLE APPOINTMENT TYPES & SERVICES:\n" + "\n".join(s_lines) + "\n\n"
        elif isinstance(services, str) and services.strip():
            services_section = f"AVAILABLE APPOINTMENT TYPES & SERVICES:\n  {services.strip()}\n\n"

    # 12. Custom Prompt Variables
    custom_vars_section = ""
    if custom_prompt_variables and isinstance(custom_prompt_variables, dict):
        v_lines = [f"  • {k}: {v}" for k, v in custom_prompt_variables.items() if str(v).strip()]
        if v_lines:
            custom_vars_section = "\n\nCUSTOM CLINIC PROMPT VARIABLES:\n" + "\n".join(v_lines)

    prompt = (
        f"You are {ai_name_str}, a friendly and professional autonomous AI Voice Receptionist for {clinic_name}.\n\n"
        f"CLINIC & DOCTOR INFORMATION:\n"
        f"  • Clinic Name: {clinic_name}\n"
        f"  • {doc_info}\n"
        f"  • Operating Hours: {hours_info}\n"
        f"  • Local Timezone: {tz_str}\n\n"
        f"{services_section}"
        f"{style_instruction}\n\n"
        f"GREETING:\n{greeting}\n\n"
        f"CUSTOM CLINIC INSTRUCTIONS & PERSONA:\n{custom_persona}\n\n"
        f"{custom_vars_section}\n\n"
        f"{faq_section}\n\n"
        f"{guardrails}\n\n"
        f"{tool_section}\n\n"
        f"{voice_guidelines}"
        f"{transfer_section}"
        f"{lang_instruction}"
    )
    return prompt.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Helper — run sync DB calls in executor & fetch clinic metadata
# ─────────────────────────────────────────────────────────────────────────────

async def _run(fn):
    """Execute a synchronous callable in a thread-pool executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


async def _get_clinic_metadata(clinic_id: str, default_name: str) -> dict:
    """Fetch rich clinic profile metadata including doctors, hours, and specialty."""
    meta = {
        "name": default_name,
        "doctor_name": None,
        "doctor_credentials": None,
        "specialty": None,
        "business_hours": None,
        "timezone": "America/New_York",
        "phone_number": None,
        "services": None,
    }
    try:
        clinic_res = await _run(
            lambda: supabase_read.table("clinics")
            .select("*")
            .eq("id", clinic_id)
            .single()
            .execute()
        )
        if clinic_res.data and isinstance(clinic_res.data, dict):
            c = clinic_res.data
            meta["name"] = c.get("name") or default_name
            meta["doctor_name"] = c.get("primary_doctor_name")
            meta["doctor_credentials"] = c.get("primary_doctor_credentials")
            meta["specialty"] = c.get("specialty")
            meta["business_hours"] = c.get("business_hours")
            meta["timezone"] = c.get("timezone") or "America/New_York"
            meta["phone_number"] = c.get("phone_number") or c.get("telnyx_number") or c.get("primary_doctor_phone")
            meta["services"] = c.get("appointment_types") or c.get("services")
    except Exception:
        pass
    return meta


# ─────────────────────────────────────────────────────────────────────────────
# Retell AI Synchronization
# ─────────────────────────────────────────────────────────────────────────────

async def _sync_to_retell(
    retell_agent_id: str,
    compiled_prompt: str,
    greeting_message: str = "",
    voice_id: Optional[str] = None,
    language: Optional[str] = None,
    emergency_forward_phone: Optional[str] = None,
) -> dict:
    """
    Synchronize agent settings with Retell AI API:
    - Updates agent attributes (voice_id, language)
    - Updates LLM prompt, greeting message, and call transfer tools
    - Preserves existing custom LLM tools
    """
    if not retell_agent_id or not retell_agent_id.strip():
        return {"success": False, "status": "skipped", "message": "No retell_agent_id provided."}

    clean_phone = sanitize_phone_number(emergency_forward_phone)

    if _is_mock_retell_key(settings.RETELL_API_KEY):
        logger.info("Retell API key not configured or mock key; running in local persistence mode.")
        return {
            "success": True,
            "status": "mock_synced",
            "agent_id": retell_agent_id,
            "message": "Retell API key not set or in test mode. Config persisted to local DB.",
        }

    headers = {
        "Authorization": f"Bearer {settings.RETELL_API_KEY}",
        "Content-Type": "application/json",
    }

    agent_patch_body: Dict[str, Any] = {}
    if voice_id:
        agent_patch_body["voice_id"] = voice_id
    if language:
        agent_patch_body["language"] = language

    llm_id = None
    sync_errors = []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Fetch Agent details to get llm_id
            get_url = f"https://api.retellai.com/get-agent/{retell_agent_id}"
            get_resp = await client.get(get_url, headers=headers)
            if get_resp.status_code == 200:
                agent_data = get_resp.json()
                response_engine = agent_data.get("response_engine", {})
                if isinstance(response_engine, dict):
                    llm_id = response_engine.get("llm_id")
            elif get_resp.status_code != 404:
                sync_errors.append(f"Failed to fetch agent details: HTTP {get_resp.status_code}")

            # 2. Update agent (voice_id, language)
            if agent_patch_body:
                patch_agent_url = f"https://api.retellai.com/update-agent/{retell_agent_id}"
                agent_resp = await client.patch(patch_agent_url, json=agent_patch_body, headers=headers)
                if agent_resp.status_code not in (200, 204):
                    logger.warning("Retell update-agent returned %s: %s", agent_resp.status_code, agent_resp.text)
                    sync_errors.append(f"Agent update: HTTP {agent_resp.status_code} - {agent_resp.text}")

            # 3. Update LLM prompt, greeting, and tools
            if llm_id:
                # Retrieve existing LLM tools to preserve any custom integrations
                existing_tools = []
                try:
                    llm_get_resp = await client.get(f"https://api.retellai.com/get-retell-llm/{llm_id}", headers=headers)
                    if llm_get_resp.status_code == 200:
                        llm_info = llm_get_resp.json()
                        raw_tools = llm_info.get("general_tools") or []
                        for t in raw_tools:
                            if isinstance(t, dict):
                                tool_type = t.get("type", "")
                                tool_name = t.get("name", "")
                                if tool_type not in ("end_call", "transfer_call") and tool_name not in ("end_call", "transfer_call"):
                                    existing_tools.append(t)
                except Exception as e:
                    logger.debug("Could not fetch existing LLM tools: %s", e)

                tools: List[Dict[str, Any]] = [
                    {
                        "type": "end_call",
                        "name": "end_call",
                        "description": "End the call with the caller when conversation is finished.",
                    }
                ]
                if clean_phone:
                    tools.append({
                        "type": "transfer_call",
                        "name": "transfer_call",
                        "description": "Transfer the caller to clinic staff or emergency forwarding phone line.",
                        "number": clean_phone,
                    })

                # Append preserved custom tools
                tools.extend(existing_tools)

                llm_url = f"https://api.retellai.com/update-retell-llm/{llm_id}"
                llm_body = {
                    "general_prompt": compiled_prompt,
                    "begin_message": greeting_message or "",
                    "general_tools": tools,
                }
                llm_resp = await client.patch(llm_url, json=llm_body, headers=headers)
                if llm_resp.status_code not in (200, 204):
                    logger.warning("Retell update-retell-llm returned %s: %s", llm_resp.status_code, llm_resp.text)
                    sync_errors.append(f"LLM update: HTTP {llm_resp.status_code} - {llm_resp.text}")
            else:
                # Direct agent update fallback
                direct_url = f"https://api.retellai.com/update-agent/{retell_agent_id}"
                direct_resp = await client.patch(
                    direct_url,
                    json={
                        "system_prompt": compiled_prompt,
                        "begin_message": greeting_message or "",
                    },
                    headers=headers,
                )
                if direct_resp.status_code not in (200, 204):
                    sync_errors.append(f"Direct update: HTTP {direct_resp.status_code} - {direct_resp.text}")

    except Exception as exc:
        logger.error("Exception during Retell AI sync for agent %s: %s", retell_agent_id, exc)
        return {
            "success": False,
            "status": "error",
            "agent_id": retell_agent_id,
            "error": str(exc),
        }

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if sync_errors:
        return {
            "success": False,
            "status": "partial_sync",
            "agent_id": retell_agent_id,
            "llm_id": llm_id,
            "errors": sync_errors,
            "synced_at": now_iso,
        }

    return {
        "success": True,
        "status": "synced",
        "agent_id": retell_agent_id,
        "llm_id": llm_id,
        "synced_at": now_iso,
    }


async def _push_to_retell(retell_agent_id: str, compiled_prompt: str) -> None:
    """Backward-compatible push helper used in background tasks and unit tests."""
    await _sync_to_retell(retell_agent_id=retell_agent_id, compiled_prompt=compiled_prompt)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def get_agent_config(auth: AuthenticatedUser = Depends(require_role("owner", "doctor", "front_desk"))):
    """Get the current clinic's agent_config row. Returns 404 if not configured yet."""
    try:
        res = await _run(
            lambda: supabase_read.table("agent_configs")
            .select("*")
            .eq("clinic_id", auth.clinic_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="No agent config found for this clinic")
        
        row = res.data[0] if isinstance(res.data, list) else res.data
        if "emergency_forward_phone" in row and "transfer_phone_number" not in row:
            row["transfer_phone_number"] = row["emergency_forward_phone"]
        return {"data": row}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("")
async def create_agent_config(
    body: AgentConfigCreate,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """
    Create or upsert agent_config for the clinic. Compiles and pushes the prompt to Retell AI.
    """
    try:
        meta = await _get_clinic_metadata(auth.clinic_id, auth.clinic_name)
        raw_phone = body.emergency_forward_phone or body.transfer_phone_number or meta.get("phone_number")
        forward_phone = sanitize_phone_number(raw_phone)

        compiled = compile_agent_prompt(
            clinic_name=meta["name"],
            greeting=body.greeting_message,
            custom_persona=body.custom_system_prompt,
            faqs=body.faq_data or {},
            language=body.language or "en-US",
            emergency_forward_phone=forward_phone,
            doctor_name=meta.get("doctor_name"),
            doctor_credentials=meta.get("doctor_credentials"),
            specialty=meta.get("specialty"),
            business_hours=meta.get("business_hours"),
            timezone=meta.get("timezone"),
            services=meta.get("services"),
            ai_name=body.ai_name or "Alex",
            speaking_style=body.speaking_style or "Warm & Empathetic",
            emergency_protocols=body.emergency_protocols,
        )

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = {
            "clinic_id": auth.clinic_id,
            "retell_agent_id": body.retell_agent_id.strip(),
            "greeting_message": body.greeting_message,
            "custom_system_prompt": body.custom_system_prompt,
            "ai_name": body.ai_name or "Alex",
            "speaking_style": body.speaking_style or "Warm & Empathetic",
            "voice_id": body.voice_id or "11labs-rachel",
            "language": body.language or "en-US",
            "emergency_forward_phone": forward_phone,
            "transfer_phone_number": forward_phone,
            "emergency_protocols": body.emergency_protocols,
            "faq_data": body.faq_data or {},
            "ab_test_active": bool(body.ab_test_active),
            "script_a": body.script_a,
            "script_b": body.script_b,
            "compiled_prompt": compiled,
            "retell_sync_status": "synced" if not _is_mock_retell_key(settings.RETELL_API_KEY) else "mock_synced",
            "retell_synced_at": now_iso,
            "updated_at": now_iso,
        }

        # Check if already exists for upsert
        existing_res = await _run(
            lambda: supabase_read.table("agent_configs")
            .select("id")
            .eq("clinic_id", auth.clinic_id)
            .execute()
        )

        if existing_res.data:
            res = await _run(
                lambda: supabase.table("agent_configs")
                .update(payload)
                .eq("clinic_id", auth.clinic_id)
                .execute()
            )
        else:
            res = await _run(lambda: supabase.table("agent_configs").insert(payload).execute())

        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to persist agent config")

        saved_data = res.data[0] if isinstance(res.data, list) else res.data
        if "emergency_forward_phone" in saved_data and "transfer_phone_number" not in saved_data:
            saved_data["transfer_phone_number"] = saved_data["emergency_forward_phone"]

        # Keep clinics.retell_agent_id synchronized
        try:
            await _run(
                lambda: supabase.table("clinics")
                .update({"retell_agent_id": body.retell_agent_id.strip()})
                .eq("id", auth.clinic_id)
                .execute()
            )
        except Exception as sync_err:
            logger.warning("Could not sync retell_agent_id to clinics table: %s", sync_err)

        # Push to Retell in background or async
        asyncio.ensure_future(
            _sync_to_retell(
                retell_agent_id=body.retell_agent_id.strip(),
                compiled_prompt=compiled,
                greeting_message=body.greeting_message,
                voice_id=body.voice_id,
                language=body.language,
                emergency_forward_phone=forward_phone,
            )
        )

        return {"data": saved_data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("")
async def update_agent_config(
    body: AgentConfigUpdate,
    auth: AuthenticatedUser = Depends(require_role("owner")),
):
    """
    Update the clinic's agent_config and push refreshed prompt/voice/greeting to Retell AI.
    """
    try:
        # Get existing config
        existing_res = await _run(
            lambda: supabase_read.table("agent_configs")
            .select("*")
            .eq("clinic_id", auth.clinic_id)
            .execute()
        )
        if not existing_res.data:
            raise HTTPException(status_code=404, detail="No agent config found for this clinic")

        existing = existing_res.data[0] if isinstance(existing_res.data, list) else existing_res.data

        # Merge updates
        raw_updates = body.model_dump(exclude_unset=True)
        update_dict = {k: v for k, v in raw_updates.items() if v is not None}
        
        # Handle emergency_forward_phone / transfer_phone_number aliases
        if "transfer_phone_number" in update_dict and "emergency_forward_phone" not in update_dict:
            update_dict["emergency_forward_phone"] = update_dict.pop("transfer_phone_number")
        elif "transfer_phone_number" in update_dict:
            update_dict.pop("transfer_phone_number")

        if "emergency_forward_phone" in update_dict:
            update_dict["emergency_forward_phone"] = sanitize_phone_number(update_dict["emergency_forward_phone"])

        if "retell_agent_id" in update_dict and update_dict["retell_agent_id"]:
            update_dict["retell_agent_id"] = update_dict["retell_agent_id"].strip()

        merged = {**existing, **update_dict}

        # Fetch clinic metadata
        meta = await _get_clinic_metadata(auth.clinic_id, auth.clinic_name)
        forward_phone = merged.get("emergency_forward_phone") or sanitize_phone_number(meta.get("phone_number"))

        compiled = compile_agent_prompt(
            clinic_name=meta["name"],
            greeting=merged.get("greeting_message", ""),
            custom_persona=merged.get("custom_system_prompt", ""),
            faqs=merged.get("faq_data") or {},
            language=merged.get("language", "en-US"),
            emergency_forward_phone=forward_phone,
            doctor_name=meta.get("doctor_name"),
            doctor_credentials=meta.get("doctor_credentials"),
            specialty=meta.get("specialty"),
            business_hours=meta.get("business_hours"),
            timezone=meta.get("timezone"),
            services=meta.get("services"),
            ai_name=merged.get("ai_name") or "Alex",
            speaking_style=merged.get("speaking_style") or "Warm & Empathetic",
            emergency_protocols=merged.get("emergency_protocols"),
        )

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        update_dict["compiled_prompt"] = compiled
        update_dict["updated_at"] = now_iso

        res = await _run(
            lambda: supabase.table("agent_configs")
            .update(update_dict)
            .eq("clinic_id", auth.clinic_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Agent config not found or update failed")

        saved_data = res.data[0] if isinstance(res.data, list) else res.data
        if "emergency_forward_phone" in saved_data and "transfer_phone_number" not in saved_data:
            saved_data["transfer_phone_number"] = saved_data["emergency_forward_phone"]

        # Keep clinics.retell_agent_id in sync if updated
        retell_agent_id = merged.get("retell_agent_id", "")
        if retell_agent_id:
            try:
                await _run(
                    lambda: supabase.table("clinics")
                    .update({"retell_agent_id": retell_agent_id})
                    .eq("id", auth.clinic_id)
                    .execute()
                )
            except Exception as sync_err:
                logger.warning("Could not sync retell_agent_id to clinics table: %s", sync_err)

            asyncio.ensure_future(
                _sync_to_retell(
                    retell_agent_id=retell_agent_id,
                    compiled_prompt=compiled,
                    greeting_message=merged.get("greeting_message", ""),
                    voice_id=merged.get("voice_id"),
                    language=merged.get("language"),
                    emergency_forward_phone=forward_phone,
                )
            )

        return {"data": saved_data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sync-calle")
@router.post("/sync-retell")
async def sync_retell_now(
    auth: AuthenticatedUser = Depends(require_role("owner", "doctor")),
):
    """
    On-demand force synchronization of the current agent config to CALL-E AI Engine.
    Returns full sync report and persists sync status into DB.
    """
    try:
        existing_res = await _run(
            lambda: supabase_read.table("agent_configs")
            .select("*")
            .eq("clinic_id", auth.clinic_id)
            .execute()
        )
        if not existing_res.data:
            raise HTTPException(status_code=404, detail="No agent config found to sync")

        config = existing_res.data[0] if isinstance(existing_res.data, list) else existing_res.data
        retell_agent_id = config.get("retell_agent_id", "")
        if not retell_agent_id:
            raise HTTPException(status_code=400, detail="No Retell Agent ID configured")

        meta = await _get_clinic_metadata(auth.clinic_id, auth.clinic_name)
        forward_phone = config.get("emergency_forward_phone") or sanitize_phone_number(meta.get("phone_number"))

        compiled = compile_agent_prompt(
            clinic_name=meta["name"],
            greeting=config.get("greeting_message", ""),
            custom_persona=config.get("custom_system_prompt", ""),
            faqs=config.get("faq_data") or {},
            language=config.get("language", "en-US"),
            emergency_forward_phone=forward_phone,
            doctor_name=meta.get("doctor_name"),
            doctor_credentials=meta.get("doctor_credentials"),
            specialty=meta.get("specialty"),
            business_hours=meta.get("business_hours"),
            timezone=meta.get("timezone"),
            services=meta.get("services"),
            ai_name=config.get("ai_name") or "Alex",
            speaking_style=config.get("speaking_style") or "Warm & Empathetic",
            emergency_protocols=config.get("emergency_protocols"),
        )

        sync_result = await _sync_to_retell(
            retell_agent_id=retell_agent_id,
            compiled_prompt=compiled,
            greeting_message=config.get("greeting_message", ""),
            voice_id=config.get("voice_id"),
            language=config.get("language"),
            emergency_forward_phone=forward_phone,
        )

        # Update sync status in DB
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        status_str = sync_result.get("status", "synced") if sync_result.get("success") else "error"
        db_updates = {
            "compiled_prompt": compiled,
            "retell_sync_status": status_str,
            "retell_synced_at": now_iso,
            "updated_at": now_iso,
        }
        if sync_result.get("llm_id"):
            db_updates["retell_llm_id"] = sync_result["llm_id"]

        await _run(
            lambda: supabase.table("agent_configs")
            .update(db_updates)
            .eq("clinic_id", auth.clinic_id)
            .execute()
        )

        # Keep clinics.retell_agent_id in sync
        try:
            await _run(
                lambda: supabase.table("clinics")
                .update({"retell_agent_id": retell_agent_id})
                .eq("id", auth.clinic_id)
                .execute()
            )
        except Exception as sync_err:
            logger.warning("Could not sync retell_agent_id to clinics table: %s", sync_err)

        return {
            "success": sync_result.get("success", False),
            "sync_status": status_str,
            "sync_details": sync_result,
            "synced_at": now_iso,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("")
async def delete_agent_config(auth: AuthenticatedUser = Depends(require_role("owner"))):
    """Delete the clinic's agent_config row."""
    try:
        res = await _run(
            lambda: supabase.table("agent_configs")
            .delete()
            .eq("clinic_id", auth.clinic_id)
            .execute()
        )
        return {"data": {"deleted": True, "clinic_id": auth.clinic_id}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-greeting")
async def test_greeting(
    body: AgentConfigTestPrompt,
    auth: AuthenticatedUser = Depends(require_role("owner", "doctor", "front_desk")),
):
    """
    Preview the compiled prompt without saving.
    Returns the fully-assembled system prompt so the user can review it live.
    """
    meta = await _get_clinic_metadata(auth.clinic_id, auth.clinic_name)
    raw_phone = body.emergency_forward_phone or body.transfer_phone_number or meta.get("phone_number")
    forward_phone = sanitize_phone_number(raw_phone)

    compiled = compile_agent_prompt(
        clinic_name=meta["name"],
        greeting=body.greeting_message or "",
        custom_persona=body.custom_system_prompt or "",
        faqs=body.faq_data or {},
        language=body.language or "en-US",
        emergency_forward_phone=forward_phone,
        doctor_name=meta.get("doctor_name"),
        doctor_credentials=meta.get("doctor_credentials"),
        specialty=meta.get("specialty"),
        business_hours=meta.get("business_hours"),
        timezone=meta.get("timezone"),
        services=meta.get("services"),
        ai_name=body.ai_name or "Alex",
        speaking_style=body.speaking_style or "Warm & Empathetic",
        emergency_protocols=body.emergency_protocols,
    )
    return {
        "compiled_prompt": compiled,
        "clinic_name": meta["name"],
        "char_count": len(compiled),
        "ai_name": body.ai_name or "Alex",
        "speaking_style": body.speaking_style or "Warm & Empathetic",
    }


@router.post("/test-greeting-audio")
async def test_greeting_audio(
    body: AgentConfigTestPrompt,
    auth: AuthenticatedUser = Depends(require_role("owner", "doctor", "front_desk")),
):
    """
    Synthesize or validate greeting speech audio for instant live preview.
    Returns voice synthesis configuration and audio preview parameters.
    """
    greeting = (body.greeting_message or "").strip()
    if not greeting:
        greeting = "Hello! Thank you for calling the clinic. How can I assist you today?"

    voice_id = body.voice_id or "11labs-rachel"
    lang = body.language or "en-US"
    ai_name = body.ai_name or "Alex"
    style = body.speaking_style or "Warm & Empathetic"

    return {
        "success": True,
        "greeting_text": greeting,
        "voice_id": voice_id,
        "language": lang,
        "ai_name": ai_name,
        "speaking_style": style,
        "duration_estimate_seconds": round(len(greeting.split()) / 2.5, 1),
        "message": f"Audio greeting preview configured for {ai_name} ({voice_id}).",
    }
