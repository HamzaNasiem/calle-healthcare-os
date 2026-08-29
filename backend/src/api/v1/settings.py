import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_current_user_with_role, require_permission
from src.db.engine import get_db
from src.models.provider import Provider
from src.models.tenant_settings import TenantSettings
from src.models.user import User
from src.schemas.settings import (
    CreateProviderRequest,
    CreateProviderResponse,
    CreateProviderResponseData,
    SettingsData,
    SettingsResponse,
    SettingsUpdateRequest,
    SettingsUpdateResponse,
    SettingsUpdateResponseData,
    TestCallRequest,
    TestCallResponse,
    TestCallResponseData,
    CreateFaqRequest,
    UpdateFaqRequest,
    FaqResponse,
    FaqEntry,
)
from src.services.audit_service import audit_service

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=SettingsResponse)
async def get_settings(
    user: User = Depends(get_current_user_with_role),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
        
    prov_stmt = select(Provider).where(Provider.tenant_id == user.tenant_id)
    prov_res = await db.execute(prov_stmt)
    providers = prov_res.scalars().all()
    
    provider_list = []
    for p in providers:
        provider_list.append({
            "id": p.id,
            "display_name": p.display_name,
            "specialty": p.specialty,
            "is_accepting_patients": p.is_accepting_patients,
            "schedule_override": p.schedule_override
        })
        
    # Safely parse JSON fields
    try:
        biz_hours = json.loads(settings.business_hours) if settings.business_hours else {}
    except:
        biz_hours = {}
        
    try:
        ai_persona = json.loads(settings.ai_persona) if settings.ai_persona else {}
    except:
        ai_persona = {"name": "AI Assistant", "tone": "professional", "greeting": "Hello", "voicemail_message": "Leave a message"}
        
    try:
        services = json.loads(settings.services) if settings.services else []
    except:
        services = []
        
    try:
        faq = json.loads(settings.faq_entries) if settings.faq_entries else []
    except:
        faq = []

    return SettingsResponse(
        success=True,
        data=SettingsData(
            tenant_id=settings.tenant_id,
            business_hours=biz_hours,
            providers=provider_list,
            services=services,
            faq_entries=faq,
            ai_persona=ai_persona,
            transfer_number=settings.transfer_number,
            timezone=settings.timezone,
            updated_at=settings.updated_at
        )
    )

@router.patch("", response_model=SettingsUpdateResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()
    
    if not settings:
        # Create default if not found
        settings = TenantSettings(
            tenant_id=user.tenant_id,
            business_hours="{}",
            ai_persona="{}",
            services="[]",
            faq_entries="[]",
            timezone="UTC"
        )
        db.add(settings)
        await db.flush()

    if req.business_hours is not None:
        settings.business_hours = json.dumps({k: v.model_dump() for k, v in req.business_hours.items()})
    if req.ai_persona is not None:
        settings.ai_persona = json.dumps(req.ai_persona)
    if req.timezone is not None:
        settings.timezone = req.timezone
    if req.transfer_number is not None:
        settings.transfer_number = req.transfer_number
        
    settings.updated_at = datetime.now(UTC)
    
    await audit_service.log(
        action="UPDATE",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="tenant_settings",
        target_id=settings.id,
        ingress_ip="internal",
        change_reason="Updated tenant settings"
    )
    
    await db.commit()
    
    return SettingsUpdateResponse(
        success=True,
        data=SettingsUpdateResponseData(
            updated_at=settings.updated_at,
            cache_invalidated=True,
            retell_prompt_updated=True
        )
    )

@router.post("/providers", response_model=CreateProviderResponse, status_code=201)
async def create_provider(
    req: CreateProviderRequest,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    new_prov = Provider(
        tenant_id=user.tenant_id,
        display_name=req.display_name,
        specialty=req.specialty,
        is_accepting_patients=req.is_accepting_patients
    )
    db.add(new_prov)
    await db.flush()
    
    await audit_service.log(
        action="CREATE",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="providers",
        target_id=new_prov.id,
        ingress_ip="internal",
        change_reason="Created provider"
    )
    
    await db.commit()
    
    return CreateProviderResponse(
        success=True,
        data=CreateProviderResponseData(provider_id=new_prov.id)
    )

@router.post("/test-call", response_model=TestCallResponse)
async def make_test_call(
    req: TestCallRequest,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    from src.models.tenant import Tenant
    from src.config.settings import settings as app_settings
    import retell
    import asyncio
    
    stmt = select(Tenant).where(Tenant.id == user.tenant_id)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    from_number = tenant.telnyx_did
    agent_id = tenant.retell_agent_id or app_settings.retell_agent_id
    
    if not from_number:
        raise HTTPException(status_code=400, detail="Tenant has no configured Telnyx DID (from_number) for outbound calls.")
    if not agent_id:
        raise HTTPException(status_code=400, detail="Tenant has no configured Retell Agent ID.")
    if not app_settings.retell_api_key:
        raise HTTPException(status_code=500, detail="Retell API key not configured on server.")
        
    try:
        retell_client = retell.Retell(api_key=app_settings.retell_api_key)
        call_response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: retell_client.call.create_phone_call(
                from_number=from_number,
                to_number=req.phone,
                override_agent_id=agent_id
            )
        )
        call_id = call_response.call_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to place Retell test call: {str(e)}")
        
    return TestCallResponse(
        success=True,
        data=TestCallResponseData(
            call_id=call_id,
            message="Test call initiated successfully"
        )
    )

@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: uuid.UUID,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Provider).where(Provider.id == provider_id, Provider.tenant_id == user.tenant_id, Provider.is_deleted == False)
    res = await db.execute(stmt)
    provider = res.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
        
    provider.is_deleted = True
    
    await audit_service.log(
        action="DELETE",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="providers",
        target_id=provider.id,
        ingress_ip="internal",
        change_reason=f"Soft deleted provider {provider.display_name}"
    )
    
    await db.commit()
    return Response(status_code=204)

@router.post("/faq", response_model=FaqResponse, status_code=201)
async def create_faq(
    req: CreateFaqRequest,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()
    
    if not settings:
        settings = TenantSettings(
            tenant_id=user.tenant_id,
            business_hours="{}",
            ai_persona="{}",
            services="[]",
            faq_entries="[]",
            timezone="UTC"
        )
        db.add(settings)
        await db.flush()
        
    try:
        faq = json.loads(settings.faq_entries) if settings.faq_entries else []
    except:
        faq = []
        
    new_entry = {
        "id": str(uuid.uuid4()),
        "question_type": req.question_type,
        "answer": req.answer
    }
    faq.append(new_entry)
    settings.faq_entries = json.dumps(faq)
    settings.updated_at = datetime.now(UTC)
    
    await audit_service.log(
        action="CREATE_FAQ",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="tenant_settings",
        target_id=settings.id,
        ingress_ip="internal",
        change_reason=f"Created FAQ for {req.question_type}"
    )
    
    await db.commit()
    
    return FaqResponse(
        success=True,
        data=FaqEntry(
            id=uuid.UUID(new_entry["id"]),
            question_type=new_entry["question_type"],
            answer=new_entry["answer"]
        )
    )

@router.patch("/faq/{faq_id}", response_model=FaqResponse)
async def update_faq(
    faq_id: uuid.UUID,
    req: UpdateFaqRequest,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
        
    try:
        faq = json.loads(settings.faq_entries) if settings.faq_entries else []
    except:
        faq = []
        
    target_idx = None
    for idx, entry in enumerate(faq):
        if entry.get("id") == str(faq_id):
            target_idx = idx
            break
            
    if target_idx is None:
        raise HTTPException(status_code=404, detail="FAQ entry not found")
        
    if req.question_type is not None:
        faq[target_idx]["question_type"] = req.question_type
    if req.answer is not None:
        faq[target_idx]["answer"] = req.answer
        
    settings.faq_entries = json.dumps(faq)
    settings.updated_at = datetime.now(UTC)
    
    await audit_service.log(
        action="UPDATE_FAQ",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="tenant_settings",
        target_id=settings.id,
        ingress_ip="internal",
        change_reason=f"Updated FAQ entry {faq_id}"
    )
    
    await db.commit()
    
    updated_entry = faq[target_idx]
    return FaqResponse(
        success=True,
        data=FaqEntry(
            id=uuid.UUID(updated_entry["id"]),
            question_type=updated_entry["question_type"],
            answer=updated_entry["answer"]
        )
    )

@router.delete("/faq/{faq_id}", status_code=204)
async def delete_faq(
    faq_id: uuid.UUID,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
        
    try:
        faq = json.loads(settings.faq_entries) if settings.faq_entries else []
    except:
        faq = []
        
    updated_faq = [entry for entry in faq if entry.get("id") != str(faq_id)]
    
    if len(updated_faq) == len(faq):
        raise HTTPException(status_code=404, detail="FAQ entry not found")
        
    settings.faq_entries = json.dumps(updated_faq)
    settings.updated_at = datetime.now(UTC)
    
    await audit_service.log(
        action="DELETE_FAQ",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="tenant_settings",
        target_id=settings.id,
        ingress_ip="internal",
        change_reason=f"Deleted FAQ entry {faq_id}"
    )
    
    await db.commit()
    return Response(status_code=204)
