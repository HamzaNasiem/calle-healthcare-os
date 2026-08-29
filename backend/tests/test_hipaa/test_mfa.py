import pytest
from src.core.security import generate_mfa_secret, get_mfa_uri, verify_mfa_code

def test_mfa_secret_generation():
    secret = generate_mfa_secret()
    assert len(secret) == 32  # base32 encoding is 32 chars long
    assert secret.isupper()

def test_mfa_uri_generation():
    secret = generate_mfa_secret()
    email = "test@clinic.com"
    uri = get_mfa_uri(secret, email)
    
    assert "otpauth://totp/" in uri
    assert secret in uri
    import urllib.parse
    assert urllib.parse.quote(email) in uri
    assert "ByteLyticOS" in uri

def test_mfa_verification():
    secret = generate_mfa_secret()
    import pyotp
    
    # Generate a valid code for this exact moment
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    
    assert verify_mfa_code(secret, valid_code) is True
    
    # Invalid code
    assert verify_mfa_code(secret, "000000") is False
