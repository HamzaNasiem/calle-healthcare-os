import pytest
from src.core.security import (
    validate_password_strength,
    validate_phone_format,
    mask_phone,
    mask_name,
)

def test_password_strength_valid():
    # Valid passwords should not raise an exception
    validate_password_strength("StrongPass123!")
    validate_password_strength("Another$1234")

def test_password_strength_too_short():
    with pytest.raises(ValueError, match="at least 8 characters"):
        validate_password_strength("Short1!")

def test_password_strength_too_common():
    with pytest.raises(ValueError, match="too common"):
        validate_password_strength("123456789")

def test_password_strength_no_uppercase():
    with pytest.raises(ValueError, match="uppercase letter"):
        validate_password_strength("lowercase123!")

def test_password_strength_no_number():
    with pytest.raises(ValueError, match="at least one number"):
        validate_password_strength("NoNumbers!")

def test_password_strength_no_special():
    with pytest.raises(ValueError, match="special character"):
        validate_password_strength("NoSpecial123")

def test_phone_format_valid():
    validate_phone_format("+15551234567")
    validate_phone_format("+447911123456")

def test_phone_format_invalid():
    with pytest.raises(ValueError, match="Invalid phone number format"):
        validate_phone_format("invalid-phone")
    with pytest.raises(ValueError, match="Invalid phone number format"):
        validate_phone_format("+1abc")

def test_mask_phone():
    assert mask_phone("+15551234567") == "+15***4567"
    assert mask_phone("123") == "***"
    assert mask_phone("") == ""

def test_mask_name():
    assert mask_name("John Doe") == "J*** D***"
    assert mask_name("Alice") == "A***"
    assert mask_name("") == ""
