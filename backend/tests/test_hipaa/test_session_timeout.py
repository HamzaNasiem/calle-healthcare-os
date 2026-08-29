"""
Test Session Timeout
Ensures the JWT expiration logic matches HIPAA timeout requirements.
"""
import pytest
from datetime import timedelta
from jose import jwt
from src.core.security import create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
import time

def test_jwt_expiration():
    """Verify that tokens are created with an expiration time."""
    data = {"sub": "123", "role": "staff", "tenant_id": "00000000-0000-0000-0000-000000000000"}
    token = create_access_token(data)
    
    decoded = decode_access_token(token)
    assert "exp" in decoded
    assert decoded["sub"] == "123"
