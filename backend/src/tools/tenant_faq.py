from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import local_cache
from src.models.tenant_settings import TenantSettings

from .base_tool import BaseTool


class CheckServicePricingArgs(BaseModel):
    service_name: str = Field(..., description="The name of the service the patient is asking about (e.g. 'consult', 'teeth whitening', 'botox')")

class CheckServicePricingTool(BaseTool):
    @property
    def name(self) -> str:
        return "check_service_pricing"
        
    @property
    def description(self) -> str:
        return "Checks the price and duration of a specific service offered by the clinic."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return CheckServicePricingArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        service_name = args.get("service_name", "").lower()
        
        cache_key = f"t:{tenant_id}:settings"
        settings_data = local_cache.get(cache_key)
        
        if not settings_data or not settings_data.get("services"):
            stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
            settings_obj = (await db.execute(stmt)).scalars().first()
            if settings_obj and settings_obj.services:
                settings_data = {
                    "services": settings_obj.services or [],
                    "faq_entries": settings_obj.faq_entries or [],
                    "transfer_number": settings_obj.transfer_number
                }
                local_cache.set(cache_key, settings_data, ttl=3600)
            else:
                from src.core.database import supabase_read
                try:
                    c_res = supabase_read.table("clinics").select("appointment_types, services").eq("id", tenant_id).single().execute()
                    if c_res.data:
                        appts = c_res.data.get("appointment_types") or []
                        srv_list = []
                        for a in appts:
                            if isinstance(a, dict):
                                fee = a.get("fee") if a.get("fee") is not None else a.get("price")
                                fee_str = f"${float(fee):g}" if fee is not None and float(fee) > 0 else "Free"
                                srv_list.append({
                                    "name": a.get("name"),
                                    "price_display": fee_str,
                                    "price": fee,
                                    "duration_minutes": a.get("duration_minutes") or a.get("duration") or 30,
                                    "cpt_code": a.get("cpt_code")
                                })
                        for s in (c_res.data.get("services") or []):
                            if isinstance(s, dict):
                                srv_list.append(s)
                        settings_data = {
                            "services": srv_list,
                            "faq_entries": [],
                            "transfer_number": None
                        }
                        local_cache.set(cache_key, settings_data, ttl=3600)
                except Exception:
                    pass

        services = settings_data.get("services", []) if isinstance(settings_data, dict) else []
        for s in services:
            svc_n = str(s.get("name", "")).lower()
            if service_name in svc_n or svc_n in service_name:
                res_payload = {
                    "found": True,
                    "service": s.get("name"),
                    "price": s.get("price_display"),
                    "duration_minutes": s.get("duration_minutes")
                }
                if s.get("cpt_code"):
                    res_payload["cpt_code"] = s.get("cpt_code")
                return res_payload
                
        return {"found": False, "message": "I don't have pricing for that specific service. Let me transfer you to our billing team."}

class GetClinicFaqArgs(BaseModel):
    question_type: str = Field(..., description="A short keyword describing the question category (e.g., 'parking', 'location', 'insurance', 'cancellation')")

class GetClinicFaqTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_clinic_faq"

    @property
    def description(self) -> str:
        return "Gets answers to frequently asked questions about the clinic."
        
    @property
    def args_schema(self) -> type[BaseModel]:
        return GetClinicFaqArgs

    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        question_type = args.get("question_type")
        
        cache_key = f"t:{tenant_id}:settings"
        settings_data = local_cache.get(cache_key)
        
        faq_entries = []
        if settings_data and isinstance(settings_data, dict):
            faq_entries = settings_data.get("faq_entries", [])
        else:
            stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
            settings_obj = (await db.execute(stmt)).scalars().first()
            if settings_obj:
                settings_data = {
                    "services": settings_obj.services or [],
                    "faq_entries": settings_obj.faq_entries or [],
                    "transfer_number": settings_obj.transfer_number
                }
                local_cache.set(cache_key, settings_data, ttl=3600)
                faq_entries = settings_data.get("faq_entries", [])
                
        if not faq_entries:
            return {"found": False, "message": "I don't have that information right now."}
            
        for faq in faq_entries:
            faq_type = str(faq.get("question_type", "")).lower()
            if question_type and (question_type.lower() in faq_type or faq_type in question_type.lower()):
                return {"found": True, "answer": faq.get("answer")}
                
        return {"found": False, "message": "I couldn't find an answer to that."}
