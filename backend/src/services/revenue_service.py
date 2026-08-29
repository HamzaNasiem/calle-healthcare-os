import datetime
from typing import Dict, Any, Optional
from ..core.database import supabase, supabase_read

class RevenueService:
    async def record_event(self, clinic_id: str, event_type: str, amount_cents: int, appointment_id: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        try:
            res = supabase.table("revenue_events").insert({
                "clinic_id": clinic_id,
                "event_type": event_type,
                "amount_cents": amount_cents,
                "appointment_id": appointment_id,
                "description": description
            }).execute()
            
            print(f"[revenue.record_event] clinicId={clinic_id} type={event_type} amount={amount_cents}")
            return {"success": True, "data": {"id": res.data[0]["id"] if res.data else None}}
        except Exception as e:
            print(f"[revenue.record_event] clinicId={clinic_id} Error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_monthly_stats(self, clinic_id: str, month: int, year: int) -> Dict[str, Any]:
        try:
            # Current month bounds
            start_date = datetime.datetime(year, month, 1, tzinfo=datetime.timezone.utc)
            if month == 12:
                end_date = datetime.datetime(year + 1, 1, 1, tzinfo=datetime.timezone.utc)
            else:
                end_date = datetime.datetime(year, month + 1, 1, tzinfo=datetime.timezone.utc)
                
            res = supabase_read.table("revenue_events").select("event_type, amount_cents, created_at")\
                .eq("clinic_id", clinic_id).gte("created_at", start_date.isoformat())\
                .lt("created_at", end_date.isoformat()).execute()
                
            events = res.data or []
            
            breakdown = {}
            total_cents = 0
            
            for event in events:
                e_type = event.get("event_type")
                amount = event.get("amount_cents", 0)
                if e_type not in breakdown:
                    breakdown[e_type] = {"count": 0, "amount_cents": 0}
                breakdown[e_type]["count"] += 1
                breakdown[e_type]["amount_cents"] += amount
                total_cents += amount
                
            # Previous month bounds for MoM
            if month == 1:
                prev_start = datetime.datetime(year - 1, 12, 1, tzinfo=datetime.timezone.utc)
            else:
                prev_start = datetime.datetime(year, month - 1, 1, tzinfo=datetime.timezone.utc)
                
            prev_res = supabase_read.table("revenue_events").select("amount_cents")\
                .eq("clinic_id", clinic_id).gte("created_at", prev_start.isoformat())\
                .lt("created_at", start_date.isoformat()).execute()
                
            prev_total_cents = sum((e.get("amount_cents", 0) for e in (prev_res.data or [])))
            mom_change_percent = None
            if prev_total_cents > 0:
                mom_change_percent = round(((total_cents - prev_total_cents) / prev_total_cents) * 100)
                
            return {
                "success": True,
                "data": {
                    "totalCents": total_cents,
                    "totalDollars": round(total_cents / 100),
                    "breakdown": breakdown,
                    "momChangePercent": mom_change_percent,
                    "month": month,
                    "year": year
                }
            }
        except Exception as e:
            print(f"[revenue.get_monthly_stats] clinicId={clinic_id} Error: {str(e)}")
            return {"success": False, "error": str(e)}

revenue_service = RevenueService()
