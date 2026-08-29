from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.security import get_current_user
from src.db.engine import get_db
from src.models.user import User
from src.models.waitlist import Waitlist
from src.schemas.waitlist import PaginationMeta, WaitlistListData, WaitlistListResponse

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

@router.get("", response_model=WaitlistListResponse)
async def get_waitlist(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(Waitlist).options(selectinload(Waitlist.patient)).where(
        Waitlist.tenant_id == user.tenant_id,
        Waitlist.status == 'waiting'
    ).order_by(Waitlist.created_at.asc())
    
    res = await db.execute(stmt)
    entries = res.scalars().all()
    
    mapped_entries = []
    for e in entries:
        mapped_entries.append({
            "id": e.id,
            "patient": {
                "id": e.patient_id,
                "name": e.patient.full_name if e.patient else "Unknown"
            },
            "preferred_days": e.preferred_days,
            "preferred_time_range": e.preferred_time_range,
            "service_type": e.service_type,
            "notes": e.notes,
            "status": e.status,
            "created_at": e.created_at
        })
        
    return WaitlistListResponse(
        success=True,
        data=WaitlistListData(
            entries=mapped_entries,
            meta=PaginationMeta(page=1, per_page=100, total=len(mapped_entries), total_pages=1)
        )
    )
