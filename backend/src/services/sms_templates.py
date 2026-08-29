"""
Bilingual SMS templates for English (en) and Spanish (es).
Usage: get_template("appointment_reminder", lang="es").format(...)
"""

TEMPLATES = {
    "appointment_reminder": {
        "en": "Hi {patient_name}, your appointment at {clinic_name} is confirmed for {datetime}. Reply CONFIRM or CANCEL.",
        "es": "Hola {patient_name}, su cita en {clinic_name} está confirmada para {datetime}. Responda CONFIRMAR o CANCELAR.",
    },
    "appointment_booked": {
        "en": "Your appointment at {clinic_name} has been scheduled for {datetime}. We look forward to seeing you!",
        "es": "Su cita en {clinic_name} ha sido programada para {datetime}. ¡Esperamos verle pronto!",
    },
    "recall_message": {
        "en": "Hi {patient_name}, it's been a while since your last visit to {clinic_name}. Would you like to schedule an appointment? Reply YES to book.",
        "es": "Hola {patient_name}, ha pasado un tiempo desde su última visita a {clinic_name}. ¿Le gustaría programar una cita? Responda SÍ para reservar.",
    },
    "waitlist_offer": {
        "en": "Good news! A slot opened at {clinic_name} on {datetime}. Reply YES to claim it!",
        "es": "¡Buenas noticias! Se abrió un espacio en {clinic_name} el {datetime}. ¡Responda SÍ para reservarlo!",
    },
    "followup": {
        "en": "Hi {patient_name}, thank you for visiting {clinic_name}. How are you feeling? Reply GREAT, OK, or NOTWELL.",
        "es": "Hola {patient_name}, gracias por visitar {clinic_name}. ¿Cómo se siente? Responda BIEN, REGULAR o MALESTAR.",
    },
    "insurance_verification": {
        "en": "Hi {patient_name}, your insurance verification for your appointment on {datetime} is complete. See you soon!",
        "es": "Hola {patient_name}, la verificación de su seguro para su cita el {datetime} está completa. ¡Hasta pronto!",
    },
    "booking_confirmation": {
        "en": "Hi {patient_name}, your appointment at {clinic_name} is confirmed for {datetime}{provider_info}.{code_info} Reply CANCEL to cancel or RESCHEDULE to change.",
        "es": "Hola {patient_name}, su cita en {clinic_name} está confirmada para {datetime}{provider_info}.{code_info} Responda CANCELAR o REPROGRAMAR para cambiar.",
    },
    "live_link": {
        "en": "Here is the link requested during your call with {clinic_name}: {url}",
        "es": "Aquí tiene el enlace solicitado durante su llamada con {clinic_name}: {url}",
    },
}


def get_template(template_name: str, lang: str = "en") -> str:
    """Returns the SMS template string for the given name and language."""
    lang_code = lang[:2].lower() if lang else "en"
    if lang_code not in ["en", "es"]:
        lang_code = "en"
    template_group = TEMPLATES.get(template_name)
    if not template_group:
        raise ValueError(f"Unknown template: {template_name}")
    return template_group.get(lang_code, template_group["en"])
