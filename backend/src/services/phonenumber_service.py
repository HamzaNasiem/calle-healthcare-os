import datetime
from typing import Dict, Any

from ..core.database import supabase

class PhoneNumberService:
    async def assign_number_to_clinic(self, clinic_id: str) -> str:
        try:
            res = supabase.table("phone_pool").select("*").eq("is_assigned", False).limit(1).execute()
            if not res.data:
                raise Exception("No Twilio numbers available in the pool. Please add more numbers.")
                
            selected_number = res.data[0]
            
            update_res = supabase.table("phone_pool").update({
                "is_assigned": True,
                "assigned_to": clinic_id,
                "assigned_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).eq("id", selected_number["id"]).execute()
            
            # Check if pool level is low and alert
            await self.check_pool_level()
            return update_res.data[0]["phone_number"]
        except Exception as e:
            print(f"[PhoneNumberService] Error assigning number: {str(e)}")
            return None

    async def check_pool_level(self) -> None:
        """Alert admin if phone pool is running low (< 3 available)."""
        try:
            res = supabase.table("phone_pool").select("id").eq("is_assigned", False).execute()
            count = len(res.data)
            if count < 3:
                print(f"[PhonePool] ⚠️ WARNING: Only {count} unassigned numbers in pool. Add more Twilio numbers!")
                # Import here to avoid circular import
                from .email_service import email_service
                await email_service.send_alert_email(
                    f"⚠️ Phone Pool LOW: Only {count} numbers available. Please add more Twilio numbers to the phone_pool table in Supabase."
                )
        except Exception as e:
            print(f"[PhonePool] Error checking pool level: {e}")

    async def release_number(self, clinic_id: str) -> bool:
        try:
            supabase.table("phone_pool").update({
                "is_assigned": False,
                "assigned_to": None,
                "assigned_at": None
            }).eq("assigned_to", clinic_id).execute()
            return True
        except Exception as e:
            print(f"[PhoneNumberService] Error releasing number: {str(e)}")
            raise e

phonenumber_service = PhoneNumberService()
