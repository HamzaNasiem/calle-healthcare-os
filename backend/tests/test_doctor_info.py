from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from src.api.routers.clinics_router import ClinicCreate, ClinicUpdate
from src.services.voice_service import voice_service

def test_clinic_update_model_valid_doctor_fields():
    """Verify ClinicUpdate model accepts and normalizes valid doctor fields."""
    update = ClinicUpdate(
        primary_doctor_name="  Dr. Hamza Nasiem  ",
        primary_doctor_credentials="  MD, DO, PT  ",
        primary_doctor_phone="  +1 (555) 999-8888  ",
        npi_number="1234567890",
        medical_license="CA-PT-048291"
    )
    assert update.primary_doctor_name == "Dr. Hamza Nasiem"
    assert update.primary_doctor_credentials == "MD, DO, PT"
    assert update.primary_doctor_phone == "+1 (555) 999-8888"
    assert update.npi_number == "1234567890"
    assert update.medical_license == "CA-PT-048291"

def test_clinic_create_model_valid_doctor_fields():
    """Verify ClinicCreate model accepts doctor fields."""
    create = ClinicCreate(
        name="Sunrise Wellness",
        owner_email="admin@sunrisewellness.com",
        primary_doctor_name="Dr. Jane Smith",
        primary_doctor_credentials="DO, MD",
        primary_doctor_phone="+15551234567",
        npi_number="9876543210",
        medical_license="NY-123456"
    )
    assert create.primary_doctor_name == "Dr. Jane Smith"
    assert create.primary_doctor_credentials == "DO, MD"
    assert create.npi_number == "9876543210"

def test_clinic_update_model_invalid_npi():
    """Verify ClinicUpdate rejects NPI that is not 10 digits."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(npi_number="12345")
    assert "NPI Number must be a valid 10-digit National Provider Identifier." in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(npi_number="1234567890123")
    assert "NPI Number must be a valid 10-digit National Provider Identifier." in str(exc.value)

def test_clinic_update_model_invalid_phone():
    """Verify ClinicUpdate rejects invalid phone format."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(primary_doctor_phone="123")
    assert "Doctor phone must contain a valid 10-15 digit phone number." in str(exc.value)

def test_clinic_update_model_invalid_license():
    """Verify ClinicUpdate rejects invalid medical license characters."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(medical_license="INVALID*LIC#$$$")
    assert "Medical License contains invalid characters" in str(exc.value)

def test_clinic_update_model_excessive_name_length():
    """Verify ClinicUpdate rejects doctor name exceeding 120 chars."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(primary_doctor_name="A" * 125)
    assert "Doctor name cannot exceed 120 characters." in str(exc.value)

def test_clinic_update_model_excessive_credentials_length():
    """Verify ClinicUpdate rejects doctor credentials exceeding 60 chars."""
    with pytest.raises(ValidationError) as exc:
        ClinicUpdate(primary_doctor_credentials="A" * 65)
    assert "Doctor credentials cannot exceed 60 characters." in str(exc.value)

def test_voice_prompt_includes_doctor_info_and_credentials():
    """Verify voice prompt builds clean provider name without duplicate Dr. prefix."""
    clinic_data_with_prefix = {
        "name": "Apex Physical Therapy",
        "specialty": "Physical Therapy",
        "city": "Dallas",
        "timezone": "America/Chicago",
        "primary_doctor_name": "Dr. Hamza Nasiem",
        "primary_doctor_credentials": "PT, DPT, OCS",
        "business_hours": {"mon": "08:00-18:00"}
    }
    prompt = voice_service.build_agent_prompt(clinic_data_with_prefix)
    assert "Primary provider: Dr. Hamza Nasiem, PT, DPT, OCS." in prompt
    assert "Dr. Dr." not in prompt

    clinic_data_without_prefix = {
        "name": "Apex Physical Therapy",
        "specialty": "Physical Therapy",
        "city": "Dallas",
        "timezone": "America/Chicago",
        "primary_doctor_name": "Hamza Nasiem",
        "primary_doctor_credentials": "MD",
        "business_hours": {"mon": "08:00-18:00"}
    }
    prompt2 = voice_service.build_agent_prompt(clinic_data_without_prefix)
    assert "Primary provider: Dr. Hamza Nasiem, MD." in prompt2
