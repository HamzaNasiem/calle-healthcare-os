from __future__ import annotations
import pytest
from pydantic import ValidationError
from src.api.routers.clinics_router import ClinicCreate, ClinicUpdate

def test_clinic_update_profile_valid_fields():
    """Verify ClinicUpdate accepts and normalizes all 6 Clinic Profile fields."""
    update = ClinicUpdate(
        name="  Oakridge Physical Therapy & Wellness  ",
        specialty="  Physical Therapy & Sports Rehab  ",
        city="  Chicago  ",
        timezone="  America/Chicago  ",
        phone_number="  +1 (555) 234-5678  ",
        owner_email="  Owner@OakRidgeClinic.COM  "
    )
    assert update.name == "Oakridge Physical Therapy & Wellness"
    assert update.specialty == "Physical Therapy & Sports Rehab"
    assert update.city == "Chicago"
    assert update.timezone == "America/Chicago"
    assert update.phone_number == "+1 (555) 234-5678"
    assert update.owner_email == "owner@oakridgeclinic.com"

def test_clinic_create_profile_valid_fields():
    """Verify ClinicCreate accepts and normalizes required profile fields."""
    create = ClinicCreate(
        name="  Sunrise Medical Clinic  ",
        owner_email="  Admin@SunriseClinic.com  ",
        phone_number="+1 (555) 123-4567",
        city="Chicago",
        specialty="General Practice",
        timezone="America/Chicago"
    )
    assert create.name == "Sunrise Medical Clinic"
    assert create.owner_email == "admin@sunriseclinic.com"
    assert create.phone_number == "+1 (555) 123-4567"

def test_clinic_update_empty_name_rejected():
    """Verify ClinicUpdate rejects empty clinic name."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(name="   ")
    assert "Clinic name cannot be empty." in str(exc.value)

def test_clinic_update_excessive_name_rejected():
    """Verify ClinicUpdate rejects clinic name exceeding 150 characters."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(name="A" * 155)
    assert "Clinic name cannot exceed 150 characters." in str(exc.value)

def test_clinic_update_invalid_owner_email_rejected():
    """Verify ClinicUpdate rejects malformed email address."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(owner_email="not-an-email")
    assert "Invalid owner email address format." in str(exc.value)

def test_clinic_update_invalid_phone_rejected():
    """Verify ClinicUpdate rejects phone number with fewer than 10 digits."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(phone_number="12345")
    assert "Patient Direct Phone Line must contain a valid 10-15 digit phone number." in str(exc.value)

def test_clinic_update_excessive_specialty_rejected():
    """Verify ClinicUpdate rejects specialty exceeding 100 characters."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(specialty="S" * 105)
    assert "Medical specialty cannot exceed 100 characters." in str(exc.value)

def test_clinic_update_excessive_city_rejected():
    """Verify ClinicUpdate rejects city exceeding 100 characters."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(city="C" * 105)
    assert "City cannot exceed 100 characters." in str(exc.value)

def test_clinic_update_excessive_timezone_rejected():
    """Verify ClinicUpdate rejects timezone exceeding 80 characters."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(timezone="T" * 85)
    assert "Timezone cannot exceed 80 characters." in str(exc.value)
