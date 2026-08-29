import pytest
import uuid
import secrets
from datetime import datetime, timezone

from src.core.encryption import phi_crypto
from src.models.prior_auth_request import PriorAuthRequest
from src.services.prior_auth_service import prior_auth_service, build_calle_goal


def test_prior_auth_model_phi_encryption():
    """Verify that patient member ID, group number, and authorization code are encrypted with AES-256-GCM."""
    pa = PriorAuthRequest(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        cpt_code="70551",
        icd10_code="G43.909"
    )

    member_id = "MEM-8273941"
    auth_code = "AUTH-992104"
    group_num = "GRP-4029"

    pa.patient_member_id = member_id
    pa.authorization_number = auth_code
    pa.patient_group_number = group_num

    # The raw database columns must be encrypted bytes, not plaintext
    assert isinstance(pa.patient_member_id_encrypted, bytes)
    assert pa.patient_member_id_encrypted != member_id.encode()
    assert isinstance(pa.authorization_number_encrypted, bytes)
    assert pa.authorization_number_encrypted != auth_code.encode()
    assert isinstance(pa.patient_group_number_encrypted, bytes)

    # Properties must decrypt seamlessly
    assert pa.patient_member_id == member_id
    assert pa.authorization_number == auth_code
    assert pa.patient_group_number == group_num


def test_build_calle_goal_contains_all_protocols():
    """Verify that CALL-E goal prompt contains NPI, CPT, ICD-10, IVR navigation instructions and protocols."""
    req = {
        "cpt_code": "72148",
        "cpt_description": "MRI Lumbar Spine",
        "icd10_code": "M54.50",
        "icd10_description": "Low back pain",
        "urgency": "urgent",
        "patient_member_id": "MEM-123456",
        "ivr_hints": "Press 2 for Provider Services, then press 1 for Prior Auth."
    }
    clinic = {
        "name": "Metro Health Clinic",
        "provider_npi": "1992837465",
        "tax_id": "12-3456789"
    }
    patient = {
        "name": "Jane Doe",
        "dob": "1978-11-23",
        "member_id": "MEM-123456"
    }

    goal = build_calle_goal(req, clinic, patient)

    assert "Metro Health Clinic" in goal
    assert "1992837465" in goal
    assert "Jane Doe" in goal
    assert "MEM-123456" in goal
    assert "72148" in goal
    assert "M54.50" in goal
    assert "Press 2 for Provider Services" in goal
    assert "URGENT" in goal
    assert "Authorization Number" in goal
    assert "Call Reference Number" in goal


@pytest.mark.asyncio
async def test_initiate_prior_auth_call_simulation():
    """Verify that prior_auth_service runs simulation and returns structured auth numbers."""
    req_id = str(uuid.uuid4())
    payload = {
        "cpt_code": "70551",
        "cpt_description": "MRI Brain",
        "icd10_code": "G43.909",
        "insurance_provider_name": "Aetna",
        "insurance_prior_auth_phone": "+18006240756",
        "patient_member_id": "MEM-778899"
    }

    result = await prior_auth_service.initiate_prior_auth_call(
        request_id=req_id,
        db=None,
        request_payload=payload
    )

    assert result["status"] == "completed"
    assert "auth_number" in result
    assert result["auth_number"].startswith("AUTH-")
    assert result["call_result"]["task_completed"] is True
    assert result["call_result"]["structured_result"]["status"] == "approved"
