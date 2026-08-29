import pytest
import uuid
import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

# Test schemas/models
from src.models.user import User
from src.models.patient import Patient
from src.models.provider import Provider
from src.models.tenant_settings import TenantSettings
from src.models.baa_registry import BaaRegistry
from src.models.incident_log import IncidentLog
from src.models.waitlist import Waitlist

# API functions
from src.api.v1.users import list_users, create_user, update_user, delete_user
from src.api.v1.patients import create_patient, reveal_phi
from src.api.v1.settings import delete_provider, create_faq, update_faq, delete_faq
from src.api.v1.compliance import get_baa_registry, get_incidents

# Service instances
from src.services.waitlist_service import waitlist_service
from src.services.breach_service import breach_service

# Mock request/schemas
from src.schemas.users import UserCreateRequest, UserUpdateRequest
from src.schemas.patient import PatientCreateRequest, PhiRevealRequest
from src.schemas.settings import CreateFaqRequest, UpdateFaqRequest

@pytest.fixture(autouse=True)
def mock_audit_service():
    with patch("src.api.v1.users.audit_service.log", new_callable=AsyncMock) as m1, \
         patch("src.api.v1.patients.audit_service.log", new_callable=AsyncMock) as m2, \
         patch("src.api.v1.settings.audit_service.log", new_callable=AsyncMock) as m3:
        m1.return_value = uuid.uuid4()
        m2.return_value = uuid.uuid4()
        m3.return_value = uuid.uuid4()
        yield (m1, m2, m3)

@pytest.mark.asyncio
async def test_users_api():
    tenant_id = uuid.uuid4()
    owner = User(id=uuid.uuid4(), email="owner@clinic.com", role="owner", tenant_id=tenant_id)
    
    db = AsyncMock()
    db.add = MagicMock()
    # Mock listing
    execute_result = MagicMock()
    mock_user = User(id=uuid.uuid4(), email="staff@clinic.com", role="staff", tenant_id=tenant_id, full_name="Staff User", is_active=True)
    execute_result.scalars.return_value.all.return_value = [mock_user]
    db.execute.return_value = execute_result
    
    # 1. GET /users
    res = await list_users(user=owner, db=db)
    assert res.success is True
    assert len(res.data.users) == 1
    assert res.data.users[0].email == "staff@clinic.com"
    
    # 2. POST /users
    # Mock no duplicate
    dup_check = MagicMock()
    dup_check.scalars.return_value.first.return_value = None
    db.execute.side_effect = [dup_check]
    
    req = UserCreateRequest(email="new@clinic.com", role="staff", full_name="New User", password="StrongPassword1!")
    request_mock = MagicMock()
    request_mock.client.host = "127.0.0.1"
    
    with patch("src.api.v1.users.get_password_hash", return_value="hashed"):
        create_res = await create_user(req=req, request=request_mock, user=owner, db=db)
        assert create_res.email == "new@clinic.com"
        assert create_res.full_name == "New User"
        
    # 3. PATCH /users/{id}
    db.execute.side_effect = None
    target_user = User(id=uuid.uuid4(), email="target@clinic.com", role="staff", tenant_id=tenant_id, full_name="Target User", is_active=True)
    target_user_mock = MagicMock()
    target_user_mock.scalars.return_value.first.return_value = target_user
    db.execute.return_value = target_user_mock
    
    update_req = UserUpdateRequest(full_name="Updated Name", role="clinician")
    update_res = await update_user(user_id=target_user.id, req=update_req, request=request_mock, user=owner, db=db)
    assert update_res.full_name == "Updated Name"
    assert update_res.role == "clinician"
    
    # 4. DELETE /users/{id}
    delete_res = await delete_user(user_id=target_user.id, request=request_mock, user=owner, db=db)
    assert delete_res.status_code == 204
    assert target_user.is_deleted is True
    assert target_user.is_active is False

@pytest.mark.asyncio
async def test_patients_api():
    tenant_id = uuid.uuid4()
    staff = User(id=uuid.uuid4(), email="staff@clinic.com", role="staff", tenant_id=tenant_id)
    owner = User(id=uuid.uuid4(), email="owner@clinic.com", role="owner", tenant_id=tenant_id)
    
    db = AsyncMock()
    db.add = MagicMock()
    request_mock = MagicMock()
    request_mock.client.host = "127.0.0.1"
    
    # POST /patients
    dup_check = MagicMock()
    dup_check.scalars.return_value.first.return_value = None
    db.execute.return_value = dup_check
    
    req = PatientCreateRequest(full_name="John Doe", phone="+15551234567", dob="1990-01-01", is_vip=True)
    res = await create_patient(req=req, request=request_mock, user=staff, db=db)
    assert res.success is True
    assert res.data.patient_id is not None
        
    # POST /patients/{id}/reveal-phi
    patient = Patient(id=uuid.uuid4(), tenant_id=tenant_id, phone_hash="hash", is_deleted=False)
    patient.full_name = "John Doe"
    patient.phone = "+15551234567"
    patient.dob = "1990-01-01"
    
    patient_mock = MagicMock()
    patient_mock.scalars.return_value.first.return_value = patient
    db.execute.return_value = patient_mock
    
    reveal_req = PhiRevealRequest(reveal_reason="Audit review")
    reveal_res = await reveal_phi(id=patient.id, req=reveal_req, request=request_mock, user=owner, db=db)
    assert reveal_res.success is True
    assert reveal_res.data.full_name == "John Doe"
    assert reveal_res.data.phone == "+15551234567"
    assert reveal_res.data.dob == "1990-01-01"

@pytest.mark.asyncio
async def test_settings_faq_and_providers():
    tenant_id = uuid.uuid4()
    owner = User(id=uuid.uuid4(), email="owner@clinic.com", role="owner", tenant_id=tenant_id)
    
    db = AsyncMock()
    db.add = MagicMock()
    
    # 1. DELETE /providers/{id}
    provider = Provider(id=uuid.uuid4(), tenant_id=tenant_id, display_name="Dr. House", is_deleted=False)
    provider_mock = MagicMock()
    provider_mock.scalar_one_or_none.return_value = provider
    db.execute.return_value = provider_mock
    
    res = await delete_provider(provider_id=provider.id, user=owner, db=db)
    assert res.status_code == 204
    assert provider.is_deleted is True
    
    # 2. FAQ CRUD
    settings = TenantSettings(tenant_id=tenant_id, faq_entries="[]")
    settings_mock = MagicMock()
    settings_mock.scalar_one_or_none.return_value = settings
    db.execute.return_value = settings_mock
    
    # Create FAQ
    faq_req = CreateFaqRequest(question_type="billing", answer="We take cards.")
    faq_res = await create_faq(req=faq_req, user=owner, db=db)
    assert faq_res.success is True
    assert faq_res.data.question_type == "billing"
    assert faq_res.data.answer == "We take cards."
    
    # Update FAQ
    faq_id = faq_res.data.id
    faq_update = UpdateFaqRequest(answer="Cards only.")
    faq_up_res = await update_faq(faq_id=faq_id, req=faq_update, user=owner, db=db)
    assert faq_up_res.success is True
    assert faq_up_res.data.answer == "Cards only."
    
    # Delete FAQ
    faq_del_res = await delete_faq(faq_id=faq_id, user=owner, db=db)
    assert faq_del_res.status_code == 204

@pytest.mark.asyncio
async def test_compliance_fixed_api():
    tenant_id = uuid.uuid4()
    owner = User(id=uuid.uuid4(), email="owner@clinic.com", role="owner", tenant_id=tenant_id)
    
    db = AsyncMock()
    db.add = MagicMock()
    
    # 1. GET /compliance/baa-registry
    baa = BaaRegistry(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        vendor_name="AWS",
        signed_date=datetime.date(2026, 1, 1),
        expiry_date=datetime.date(2027, 1, 1),
        status="active",
        phi_categories=["demographics"],
        ai_training_prohibited=True
    )
    baa_mock = MagicMock()
    baa_mock.scalars.return_value.all.return_value = [baa]
    db.execute.return_value = baa_mock
    
    res = await get_baa_registry(user=owner, db=db)
    assert res.success is True
    assert len(res.data.baas) == 1
    assert res.data.baas[0].vendor_name == "AWS"
    assert res.data.baas[0].expiry_warning is False
    
    # 2. GET /compliance/incidents
    incident = IncidentLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        severity="high",
        incident_type="brute_force",
        description="test incident",
        detected_at=datetime.datetime.now(datetime.timezone.utc),
        phi_encrypted_at_time=True,
        status="open"
    )
    inc_mock = MagicMock()
    inc_mock.scalars.return_value.all.return_value = [incident]
    db.execute.return_value = inc_mock
    
    res_inc = await get_incidents(user=owner, db=db)
    assert res_inc.success is True
    assert len(res_inc.data.incidents) == 1
    assert res_inc.data.incidents[0].severity == "high"

@pytest.mark.asyncio
async def test_waitlist_service_matching():
    tenant_id = uuid.uuid4()
    db = AsyncMock()
    db.add = MagicMock()
    
    patient = MagicMock()
    patient.phone = "+15551234567"
    patient.full_name = "Jane Doe"
    
    entry = Waitlist(
        patient_id=uuid.uuid4(),
        tenant_id=tenant_id,
        status="waiting",
        service_type="consultation",
        preferred_days=["Monday"],
        preferred_time_range="morning"
    )
    entry.patient = patient
    
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = [entry]
    db.execute.return_value = execute_result
    
    slot_time = datetime.datetime(2026, 7, 6, 9, 0, 0)
    
    with patch("src.services.waitlist_service.sms_service.send_sms") as mock_send_sms:
        matched = await waitlist_service.match_and_notify_waitlist(
            db=db,
            tenant_id=tenant_id,
            service_type="consultation",
            slot_start=slot_time
        )
        assert matched is not None
        assert matched.status == "notified"
        mock_send_sms.assert_called_once()
        
@pytest.mark.asyncio
async def test_breach_service_logs():
    tenant_id = uuid.uuid4()
    db = AsyncMock()
    db.add = MagicMock()
    
    with patch("src.services.breach_service.slack_service.alert") as mock_slack:
        incident = await breach_service.log_security_incident(
            db=db,
            tenant_id=tenant_id,
            incident_type="integrity_breach",
            severity="high",
            description="Row integrity failed",
            affected_patient_count=10
        )
        assert incident.incident_type == "integrity_breach"
        assert incident.severity == "high"
        mock_slack.assert_called_once()
