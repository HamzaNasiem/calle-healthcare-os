"""
Lightweight language detection from caller transcript snippets.
Used in Retell webhook to detect if caller is Spanish-speaking.
"""

SPANISH_TRIGGER_WORDS = {
    "hola", "español", "hablar", "si", "sí", "cita", "doctor", "me llamo",
    "necesito", "ayuda", "quiero", "tengo", "gracias", "por favor", "numero",
    "llamar", "hora", "dia", "mañana", "fecha", "nombre", "seguro"
}


def detect_language(transcript_snippet: str) -> str:
    """
    Detects language from transcript. Returns 'es' if Spanish detected, else 'en'.
    Uses simple keyword matching (no external API needed for MVP).
    """
    if not transcript_snippet:
        return "en"

    words = transcript_snippet.lower().split()
    spanish_count = sum(1 for w in words if w in SPANISH_TRIGGER_WORDS)

    # If >2 Spanish words found in first 50 words, classify as Spanish
    return "es" if spanish_count >= 2 else "en"


def get_bilingual_greeting() -> str:
    """Returns the bilingual opening greeting for the AI agent."""
    return (
        "Thank you for calling. "
        "Para español, diga 'español' o continúe en inglés. "
        "How can I help you today?"
    )
