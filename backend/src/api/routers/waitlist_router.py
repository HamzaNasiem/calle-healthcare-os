from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import List, Optional

from ...core.database import supabase
from ...core.security import require_permission, AuthenticatedUser, require_active_subscription
from ...services.waitlist_service import waitlist_service
from ...services.audit_service import audit_service

router = APIRouter(prefix="/waitlist", tags=["Waitlist"], dependencies=[Depends(require_active_subscription)])

class WaitlistCreate(BaseModel):
    patient_id: str
    appointment_type: str
    preferred_dates: Optional[List[str]] = []

class WaitlistOffer(BaseModel):
    waitlistId: str
    dateStr: str

@router.get("")
async def get_waitlist(
    auth: AuthenticatedUser = Depends(require_permission("appointments:read")),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500)
):
    clinic_id = auth.clinic_id
    try:
        res = await waitlist_service.get_waitlist_candidates(clinic_id, page=page, limit=limit)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error"))
        return {
            "data": res.get("data"),
            "meta": {
                "page": page,
                "limit": limit,
                "total": res.get("total", 0)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("")
async def create_waitlist_entry(entry: WaitlistCreate, request: Request, auth: AuthenticatedUser = Depends(require_permission("appointments:write"))):
    clinic_id = auth.clinic_id
    try:
        insert_data = {
            "clinic_id": clinic_id,
            "patient_id": entry.patient_id,
            "appointment_type": entry.appointment_type,
            "preferred_dates": entry.preferred_dates
        }
        res = supabase.table("waitlist").insert(insert_data).execute()
        created_entry = res.data[0]
        
        # Audit log creation
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="waitlist.create",
            resource_type="waitlist",
            resource_id=created_entry.get("id"),
            details=insert_data,
            request=request
        )
        return {"data": created_entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/offer")
async def offer_waitlist_slot(offer: WaitlistOffer, request: Request, auth: AuthenticatedUser = Depends(require_permission("appointments:write"))):
    clinic_id = auth.clinic_id
    try:
        res = await waitlist_service.offer_slot(clinic_id, offer.waitlistId, offer.dateStr)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error"))
            
        # Audit log slot offer
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="waitlist.offer_slot",
            resource_type="waitlist",
            resource_id=offer.waitlistId,
            details={"offered_slot": offer.dateStr},
            request=request
        )
        return {"data": res.get("data")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

