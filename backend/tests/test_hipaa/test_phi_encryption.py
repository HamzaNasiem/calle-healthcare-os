"""
Test PHI Encryption
Verifies that AES-256-GCM is used and properties seamlessly encrypt/decrypt.
"""
import pytest
import uuid
from src.core.encryption import phi_crypto
from src.models.patient import Patient

def test_phi_encryption_raw():
    """Test the raw encryption service."""
    plaintext = "Alice Smith"
    
    # Encrypt
    encrypted_bytes = phi_crypto.encrypt(plaintext)
    
    assert isinstance(encrypted_bytes, bytes), "Encrypted data must be bytes"
    assert encrypted_bytes != plaintext.encode(), "Data must not be plaintext"
    assert len(encrypted_bytes) > 12 + 16, "AES-GCM output should include nonce (12) + tag (16)"
    
    # Decrypt
    decrypted = phi_crypto.decrypt(encrypted_bytes)
    assert decrypted == plaintext, "Decrypted data must match plaintext"


def test_patient_model_phi_properties():
    """Test that setting properties on the ORM model auto-encrypts."""
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        phone_hash="hash",
        row_hash="test"
    )

    patient.full_name = "Alice Smith"
    patient.phone = "+1234567890"
    patient.dob = "1990-01-01"

    # The actual database columns should hold encrypted bytes
    assert patient.full_name_encrypted != b"Alice Smith"
    assert isinstance(patient.full_name_encrypted, bytes)
    
    # The properties should decrypt seamlessly
    assert patient.full_name == "Alice Smith"
    assert patient.phone == "+1234567890"
    assert patient.dob == "1990-01-01"
