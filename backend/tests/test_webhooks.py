import pytest
import hmac
import hashlib
from fastapi import Request
from src.webhooks.retell import verify_retell_signature
from src.config.settings import settings

class MockRequest:
    def __init__(self, headers, body_bytes):
        self._headers = headers
        self._body = body_bytes
        
    @property
    def headers(self):
        return self._headers
        
    async def body(self):
        return self._body

@pytest.mark.asyncio
async def test_retell_signature_valid():
    # Setup mock secret
    old_secret = settings.retell_webhook_secret
    settings.retell_webhook_secret = "super_secret"
    
    payload = b'{"event": "call_started"}'
    
    # Calculate valid signature
    valid_sig = hmac.new(b"super_secret", payload, hashlib.sha256).hexdigest()
    
    req = MockRequest(headers={"X-Retell-Signature": valid_sig}, body_bytes=payload)
    
    # Should not raise exception
    body = await verify_retell_signature(req)
    assert body == payload
    
    # Restore
    settings.retell_webhook_secret = old_secret

@pytest.mark.asyncio
async def test_retell_signature_invalid():
    old_secret = settings.retell_webhook_secret
    settings.retell_webhook_secret = "super_secret"
    
    payload = b'{"event": "call_started"}'
    
    req = MockRequest(headers={"X-Retell-Signature": "invalid_sig_123"}, body_bytes=payload)
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await verify_retell_signature(req)
        
    assert exc.value.status_code == 401
    
    settings.retell_webhook_secret = old_secret
