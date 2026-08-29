"""
PHI Masking Module
Role-based field masking functions.
"""

def mask_phone(phone: str) -> str:
    """Mask a phone number (e.g., +15551234567 -> +15***4567)."""
    if not phone:
        return ""
    if len(phone) <= 4:
        return "***"
    return phone[:3] + "***" + phone[-4:]

def mask_name(name: str) -> str:
    """Mask a name (e.g., John Doe -> J*** D***)."""
    if not name:
        return ""
    parts = name.split()
    masked_parts = []
    for part in parts:
        if len(part) > 1:
            masked_parts.append(part[0] + "***")
        else:
            masked_parts.append(part)
    return " ".join(masked_parts)
