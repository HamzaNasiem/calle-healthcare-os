import pytest
import uuid
import datetime
from src.core.encryption import phi_crypto
from src.models.patient import Patient


def test_patient_encryption_full_demographics():
    """Verify AES-256-GCM encryption on all new demographic and clinical fields."""
    p = Patient(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        phone_hash="dummy_hash"
    )

    p.full_name = "Eleanor Vance"
    p.phone = "+15551234567"
    p.dob = "1988-06-15"
    p.email = "eleanor.vance@example.com"
    p.insurance_provider = "Aetna Health"
    p.insurance_member_id = "AET-994210"
    p.notes = "Patient requires reminder calls after 5pm."

    # Assert underlying columns are raw bytes (encrypted)
    assert isinstance(p.full_name_encrypted, bytes)
    assert isinstance(p.phone_encrypted, bytes)
    assert isinstance(p.dob_encrypted, bytes)
    assert isinstance(p.email_encrypted, bytes)
    assert isinstance(p.insurance_provider_encrypted, bytes)
    assert isinstance(p.insurance_member_id_encrypted, bytes)
    assert isinstance(p.notes_encrypted, bytes)

    # Assert no plaintext is stored in raw database columns
    assert p.full_name_encrypted != b"Eleanor Vance"
    assert p.phone_encrypted != b"+15551234567"
    assert p.insurance_member_id_encrypted != b"AET-994210"

    # Assert property getters decrypt transparently
    assert p.full_name == "Eleanor Vance"
    assert p.phone == "+15551234567"
    assert p.dob == "1988-06-15"
    assert p.email == "eleanor.vance@example.com"
    assert p.insurance_provider == "Aetna Health"
    assert p.insurance_member_id == "AET-994210"
    assert p.notes == "Patient requires reminder calls after 5pm."


def test_patient_age_calculation():
    """Verify calculated age helper works correctly from encrypted DOB."""
    p = Patient(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        phone_hash="dummy_hash"
    )
    p.dob = "1990-01-01"
    assert p.age is not None
    assert p.age >= 34


def test_patient_recall_status_calculation():
    """Verify recall status tag transitions: up_to_date, due_for_recall, overdue_60d, exempt."""
    p = Patient(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        phone_hash="dummy_hash"
    )

    # 1. Opted out
    p.recall_opted_out = True
    assert p.calculate_recall_status() == "exempt"

    # 2. No last visit
    p.recall_opted_out = False
    p.last_visit_date = None
    assert p.calculate_recall_status() == "due_for_recall"

    # 3. Recent visit (10 days ago) -> Up to date
    p.last_visit_date = datetime.date.today() - datetime.timedelta(days=10)
    assert p.calculate_recall_status() == "up_to_date"

    # 4. Visit 100 days ago -> Due for recall
    p.last_visit_date = datetime.date.today() - datetime.timedelta(days=100)
    assert p.calculate_recall_status() == "due_for_recall"

    # 5. Visit 160 days ago -> Overdue 60d+
    p.last_visit_date = datetime.date.today() - datetime.timedelta(days=160)
    assert p.calculate_recall_status() == "overdue_60d"
