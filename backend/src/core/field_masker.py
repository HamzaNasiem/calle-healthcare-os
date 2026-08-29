"""
Field Masker
Implements HIPAA Minimum Necessary field masking based on user role.
"""

def mask_full_name(name: str) -> str:
    if not name:
        return name
    parts = name.split()
    masked_parts = []
    for part in parts:
        if len(part) <= 1:
            masked_parts.append(part)
        else:
            masked_parts.append(part[0] + "*" * (len(part) - 1))
    return " ".join(masked_parts)

def mask_phone(phone: str) -> str:
    if not phone:
        return phone
    # Assuming E164 or similar, e.g. +15551234567
    # Mask all but last 4 digits
    if len(phone) <= 4:
        return phone
    last_4 = phone[-4:]
    return "***-***-" + last_4

def mask_dob(dob: str) -> str:
    if not dob:
        return dob
    # Assuming format YYYY-MM-DD
    parts = dob.split("-")
    if len(parts) == 3:
        return f"****-**-{parts[2]}"
    return "****-**-**"

def apply_phi_masking(data: dict, role: str) -> dict:
    """
    Applies masking to PHI fields if the role is 'staff'.
    Owner and Clinician roles get the unmasked data.
    """
    if role in ("owner", "clinician"):
        return data

    # Staff gets masked
    masked_data = data.copy()
    if "full_name" in masked_data and masked_data["full_name"]:
        masked_data["full_name"] = mask_full_name(masked_data["full_name"])
    if "phone" in masked_data and masked_data["phone"]:
        masked_data["phone"] = mask_phone(masked_data["phone"])
    if "dob" in masked_data and masked_data["dob"]:
        masked_data["dob"] = mask_dob(masked_data["dob"])

    return masked_data
