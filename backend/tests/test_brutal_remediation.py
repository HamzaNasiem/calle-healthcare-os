import json
import pytest
from src.services.intent_parser import intent_parser
from src.models.user import User

@pytest.mark.asyncio
async def test_tcpa_intent_parsing():
    # Test that STOP and other TCPA keywords resolve to OPT_OUT
    assert await intent_parser.parse_intent("STOP") == "OPT_OUT"
    assert await intent_parser.parse_intent("unsubscribe") == "OPT_OUT"
    assert await intent_parser.parse_intent("please opt-out") == "OPT_OUT"
    assert await intent_parser.parse_intent("cancel_sms") == "OPT_OUT"
    
    # Test that standard cancels still return CANCEL
    assert await intent_parser.parse_intent("cancel appointment") == "CANCEL"
    assert await intent_parser.parse_intent("no, don't do it") == "CANCEL"
    
    # Test that confirms return CONFIRM
    assert await intent_parser.parse_intent("yes please") == "CONFIRM"

def test_backup_codes_encryption():
    user = User()
    codes = ["CODE1", "CODE2", "CODE3"]
    codes_json = json.dumps(codes)
    
    # Set the backup codes (triggers GCM encryption)
    user.mfa_backup_codes = codes_json
    
    # Assert that the raw database field is encrypted (should not be equal to plain JSON)
    assert user.mfa_backup_codes_encrypted != codes_json
    assert "CODE1" not in user.mfa_backup_codes_encrypted
    
    # Read property (triggers GCM decryption)
    decrypted_json = user.mfa_backup_codes
    assert decrypted_json == codes_json
    assert json.loads(decrypted_json) == codes

def test_backup_codes_plaintext_fallback():
    user = User()
    codes = ["CODE1", "CODE2", "CODE3"]
    codes_json = json.dumps(codes)
    
    # Manually store unencrypted plaintext in the raw field (simulating legacy data)
    user.mfa_backup_codes_encrypted = codes_json
    
    # Assert that the property getter successfully falls back and reads the plaintext
    assert user.mfa_backup_codes == codes_json
    assert json.loads(user.mfa_backup_codes) == codes
