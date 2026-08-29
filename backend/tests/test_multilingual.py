"""
test_multilingual.py — Unit tests for Phase 8 Multilingual/Spanish Support.
All tests are pure unit tests with no real DB or API calls.
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Import modules under test
# ---------------------------------------------------------------------------
from src.services.sms_templates import get_template, TEMPLATES
from src.services.language_detection import detect_language, get_bilingual_greeting


# ===========================================================================
# Task A: SMS Templates
# ===========================================================================

class TestGetTemplateEnglish:
    """test_get_template_english — English templates return correct strings."""

    def test_appointment_reminder_en(self):
        tmpl = get_template("appointment_reminder", lang="en")
        assert "CONFIRM" in tmpl
        assert "{patient_name}" in tmpl
        assert "{clinic_name}" in tmpl
        assert "{datetime}" in tmpl

    def test_appointment_booked_en(self):
        tmpl = get_template("appointment_booked", lang="en")
        assert "{clinic_name}" in tmpl
        assert "{datetime}" in tmpl
        assert "scheduled" in tmpl.lower()

    def test_recall_message_en(self):
        tmpl = get_template("recall_message", lang="en")
        assert "{patient_name}" in tmpl
        assert "YES" in tmpl

    def test_waitlist_offer_en(self):
        tmpl = get_template("waitlist_offer", lang="en")
        assert "YES" in tmpl
        assert "{datetime}" in tmpl

    def test_followup_en(self):
        tmpl = get_template("followup", lang="en")
        assert "GREAT" in tmpl
        assert "NOTWELL" in tmpl

    def test_insurance_verification_en(self):
        tmpl = get_template("insurance_verification", lang="en")
        assert "insurance" in tmpl.lower()
        assert "{patient_name}" in tmpl


class TestGetTemplateSpanish:
    """test_get_template_spanish — Spanish templates return correct strings."""

    def test_appointment_reminder_es(self):
        tmpl = get_template("appointment_reminder", lang="es")
        assert "CONFIRMAR" in tmpl
        assert "CANCELAR" in tmpl
        assert "Hola" in tmpl

    def test_appointment_booked_es(self):
        tmpl = get_template("appointment_booked", lang="es")
        assert "programada" in tmpl

    def test_recall_message_es(self):
        tmpl = get_template("recall_message", lang="es")
        assert "Hola" in tmpl
        assert "SÍ" in tmpl

    def test_waitlist_offer_es(self):
        tmpl = get_template("waitlist_offer", lang="es")
        assert "Buenas noticias" in tmpl

    def test_followup_es(self):
        tmpl = get_template("followup", lang="es")
        assert "BIEN" in tmpl
        assert "MALESTAR" in tmpl

    def test_insurance_verification_es(self):
        tmpl = get_template("insurance_verification", lang="es")
        assert "seguro" in tmpl


class TestGetTemplateFallback:
    """test_get_template_fallback — Unknown lang defaults to English."""

    def test_unknown_lang_code_falls_back_to_en(self):
        tmpl_fr = get_template("appointment_reminder", lang="fr")
        tmpl_en = get_template("appointment_reminder", lang="en")
        assert tmpl_fr == tmpl_en

    def test_none_lang_falls_back_to_en(self):
        tmpl = get_template("appointment_reminder", lang=None)
        tmpl_en = get_template("appointment_reminder", lang="en")
        assert tmpl == tmpl_en

    def test_unknown_template_name_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("nonexistent_template", lang="en")

    def test_partial_lang_code_normalized(self):
        # e.g. "en-US" should be treated as "en"
        tmpl = get_template("appointment_reminder", lang="en-US")
        tmpl_en = get_template("appointment_reminder", lang="en")
        assert tmpl == tmpl_en

    def test_uppercase_lang_normalized(self):
        # "ES" should be treated as "es"
        tmpl_upper = get_template("appointment_reminder", lang="ES")
        tmpl_lower = get_template("appointment_reminder", lang="es")
        assert tmpl_upper == tmpl_lower


# ===========================================================================
# Task B: Language Detection
# ===========================================================================

class TestDetectLanguageEnglish:
    """test_detect_language_english — English transcript returns 'en'."""

    def test_plain_english_returns_en(self):
        transcript = "Hello I would like to schedule an appointment please thank you"
        assert detect_language(transcript) == "en"

    def test_medical_english_returns_en(self):
        transcript = "I need to see a doctor about my prescription refill next Monday"
        assert detect_language(transcript) == "en"

    def test_single_spanish_word_still_en(self):
        # Only one Spanish word — threshold not met
        transcript = "Hello I am calling hola for an appointment"
        result = detect_language(transcript)
        # 'hola' is 1 word — below threshold of 2
        assert result == "en"


class TestDetectLanguageSpanish:
    """test_detect_language_spanish — Spanish keyword-heavy transcript returns 'es'."""

    def test_spanish_greeting_returns_es(self):
        transcript = "hola necesito una cita con el doctor por favor"
        assert detect_language(transcript) == "es"

    def test_spanish_heavy_returns_es(self):
        transcript = "hola gracias tengo una cita mañana con el doctor necesito ayuda"
        assert detect_language(transcript) == "es"

    def test_mixed_majority_spanish_returns_es(self):
        transcript = "hola my name is Juan tengo una cita I need to cancel gracias"
        assert detect_language(transcript) == "es"


class TestDetectLanguageEmpty:
    """test_detect_language_empty — Empty string returns 'en'."""

    def test_empty_string_returns_en(self):
        assert detect_language("") == "en"

    def test_none_returns_en(self):
        assert detect_language(None) == "en"

    def test_whitespace_only_returns_en(self):
        result = detect_language("   ")
        # All spaces — no Spanish words found
        assert result == "en"


class TestBilingualGreeting:
    """test_bilingual_greeting_contains_both — Greeting contains English and Spanish."""

    def test_greeting_contains_english(self):
        greeting = get_bilingual_greeting()
        assert "Thank you for calling" in greeting

    def test_greeting_contains_spanish(self):
        greeting = get_bilingual_greeting()
        assert "español" in greeting

    def test_greeting_is_nonempty(self):
        greeting = get_bilingual_greeting()
        assert len(greeting) > 10


# ===========================================================================
# Task D: Language Preference API Endpoint
# ===========================================================================

class TestPatientLanguageUpdateEndpoint:
    """test_patient_language_update_endpoint — Mock DB, update to 'es', assert 200."""

    @pytest.mark.asyncio
    async def test_update_language_to_es_returns_200(self, monkeypatch):
        """PUT /patients/{id}/language with {'language': 'es'} should return 200."""
        import src.api.routers.patients_router as patients_router_mod

        # Build a fully chained mock: .update().eq().eq().execute()
        mock_patient = {"id": "pat-123", "language_preference": "es", "clinic_id": "clinic-abc"}
        mock_execute = MagicMock()
        mock_execute.data = [mock_patient]

        mock_eq2 = MagicMock()
        mock_eq2.execute.return_value = mock_execute

        mock_eq1 = MagicMock()
        mock_eq1.eq.return_value = mock_eq2

        mock_update = MagicMock()
        mock_update.eq.return_value = mock_eq1

        mock_table = MagicMock()
        mock_table.update.return_value = mock_update

        monkeypatch.setattr(patients_router_mod, "supabase", MagicMock(table=MagicMock(return_value=mock_table)))

        from src.api.routers.patients_router import update_patient_language

        # Build a mock AuthenticatedUser
        mock_auth = MagicMock()
        mock_auth.clinic_id = "clinic-abc"

        result = await update_patient_language(id="pat-123", body={"language": "es"}, auth=mock_auth)
        assert result == {"data": mock_patient}

    @pytest.mark.asyncio
    async def test_update_language_to_en_returns_data(self, monkeypatch):
        """PUT /patients/{id}/language with {'language': 'en'} should return patient data."""
        import src.api.routers.patients_router as patients_router_mod

        mock_patient = {"id": "pat-456", "language_preference": "en", "clinic_id": "clinic-abc"}
        mock_execute = MagicMock()
        mock_execute.data = [mock_patient]

        mock_eq2 = MagicMock()
        mock_eq2.execute.return_value = mock_execute

        mock_eq1 = MagicMock()
        mock_eq1.eq.return_value = mock_eq2

        mock_update = MagicMock()
        mock_update.eq.return_value = mock_eq1

        mock_table = MagicMock()
        mock_table.update.return_value = mock_update

        monkeypatch.setattr(patients_router_mod, "supabase", MagicMock(table=MagicMock(return_value=mock_table)))

        from src.api.routers.patients_router import update_patient_language

        mock_auth = MagicMock()
        mock_auth.clinic_id = "clinic-abc"

        result = await update_patient_language(id="pat-456", body={"language": "en"}, auth=mock_auth)
        assert result["data"]["language_preference"] == "en"


class TestPatientLanguageInvalid:
    """test_patient_language_invalid — 'fr' language code returns 400."""

    @pytest.mark.asyncio
    async def test_invalid_language_fr_raises_400(self, monkeypatch):
        from src.api.routers.patients_router import update_patient_language
        from fastapi import HTTPException

        mock_auth = MagicMock()
        mock_auth.clinic_id = "clinic-abc"

        with pytest.raises(HTTPException) as exc_info:
            await update_patient_language(id="pat-789", body={"language": "fr"}, auth=mock_auth)
        assert exc_info.value.status_code == 400
        assert "en" in exc_info.value.detail or "es" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_language_pt_raises_400(self, monkeypatch):
        from src.api.routers.patients_router import update_patient_language
        from fastapi import HTTPException

        mock_auth = MagicMock()
        mock_auth.clinic_id = "clinic-abc"

        with pytest.raises(HTTPException) as exc_info:
            await update_patient_language(id="pat-789", body={"language": "pt"}, auth=mock_auth)
        assert exc_info.value.status_code == 400


# ===========================================================================
# Task A (extended): Template Format Works
# ===========================================================================

class TestTemplateFormatWorks:
    """test_template_format_works — All templates format correctly with sample data."""

    SAMPLE_DATA = {
        "patient_name": "Maria Garcia",
        "clinic_name": "Sunrise Clinic",
        "datetime": "10:00 AM on Monday, Jun 15",
    }

    def test_all_templates_format_without_error(self):
        """All templates should accept sample kwargs without KeyError."""
        for name in TEMPLATES.keys():
            for lang in ["en", "es"]:
                tmpl = get_template(name, lang=lang)
                # Only format keys that are present in the template
                kwargs = {k: v for k, v in self.SAMPLE_DATA.items() if f"{{{k}}}" in tmpl}
                formatted = tmpl.format(**kwargs)
                assert isinstance(formatted, str)
                assert len(formatted) > 0

    def test_appointment_reminder_format_en(self):
        tmpl = get_template("appointment_reminder", lang="en")
        result = tmpl.format(
            patient_name="John Doe",
            clinic_name="City Clinic",
            datetime="9:00 AM on Friday, Jul 4"
        )
        assert "John Doe" in result
        assert "City Clinic" in result
        assert "9:00 AM on Friday, Jul 4" in result

    def test_appointment_reminder_format_es(self):
        tmpl = get_template("appointment_reminder", lang="es")
        result = tmpl.format(
            patient_name="Juan López",
            clinic_name="Clínica del Sol",
            datetime="9:00 AM el viernes 4 de julio"
        )
        assert "Juan López" in result
        assert "Clínica del Sol" in result
        assert "CONFIRMAR" in result

    def test_recall_message_format(self):
        tmpl = get_template("recall_message", lang="en")
        result = tmpl.format(
            patient_name="Alice Smith",
            clinic_name="Valley Health"
        )
        assert "Alice Smith" in result
        assert "Valley Health" in result

    def test_waitlist_offer_format(self):
        tmpl = get_template("waitlist_offer", lang="es")
        result = tmpl.format(
            clinic_name="Clínica Norte",
            datetime="lunes 10 de junio"
        )
        assert "Clínica Norte" in result
        assert "lunes 10 de junio" in result

    def test_followup_format(self):
        tmpl = get_template("followup", lang="en")
        result = tmpl.format(
            patient_name="Bob Jones",
            clinic_name="Central Medical"
        )
        assert "Bob Jones" in result
        assert "Central Medical" in result

    def test_insurance_verification_format(self):
        tmpl = get_template("insurance_verification", lang="es")
        result = tmpl.format(
            patient_name="Carlos Ruiz",
            datetime="el martes 12 de junio"
        )
        assert "Carlos Ruiz" in result
        assert "el martes 12 de junio" in result
