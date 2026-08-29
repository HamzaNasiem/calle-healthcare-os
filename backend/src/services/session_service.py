import asyncio
from typing import Optional, List, Dict, Any
import datetime
from ..core.database import supabase

class SessionService:
    async def create_session(
        self,
        user_id: str,
        email: str,
        clinic_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> None:
        """
        Track a new login session.
        """
        try:
            insert_data = {
                "user_id": user_id,
                "email": email,
                "clinic_id": clinic_id if clinic_id else None,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "is_active": True
            }
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("user_sessions").insert(insert_data).execute()
            )
        except Exception as e:
            print(f"[SessionService.WARNING] Failed to create session log: {str(e)}")

    async def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a specific user.
        """
        try:
            res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("user_sessions")
                .select("id, ip_address, user_agent, last_active, created_at")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .order("last_active", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[SessionService.WARNING] Failed to fetch active sessions: {str(e)}")
            return []

    async def revoke_session(self, session_id: str, user_id: str) -> bool:
        """
        Terminate a specific login session.
        """
        try:
            res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("user_sessions")
                .update({"is_active": False})
                .eq("id", session_id)
                .eq("user_id", user_id)
                .execute()
            )
            return bool(res.data)
        except Exception as e:
            print(f"[SessionService.WARNING] Failed to revoke session: {str(e)}")
            return False

    async def revoke_all_sessions(self, user_id: str, exclude_session_id: Optional[str] = None) -> bool:
        """
        Force-logout a user from all other devices.
        """
        try:
            query = supabase.table("user_sessions").update({"is_active": False}).eq("user_id", user_id)
            if exclude_session_id:
                query = query.neq("id", exclude_session_id)
                
            res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: query.execute()
            )
            return bool(res.data)
        except Exception as e:
            print(f"[SessionService.WARNING] Failed to revoke all sessions: {str(e)}")
            return False

    async def update_last_active(self, user_id: str, ip_address: Optional[str] = None) -> None:
        """
        Update the last_active timestamp of the user's latest session.
        """
        try:
            # Asynchronously update in background
            async def _update():
                try:
                    # Get the most recent active session
                    recent_res = supabase.table("user_sessions").select("id").eq("user_id", user_id).eq("is_active", True).order("last_active", desc=True).limit(1).execute()
                    if recent_res.data:
                        session_id = recent_res.data[0]["id"]
                        update_data = {"last_active": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                        if ip_address:
                            update_data["ip_address"] = ip_address
                        supabase.table("user_sessions").update(update_data).eq("id", session_id).execute()
                except Exception:
                    pass
            asyncio.create_task(_update())
        except Exception:
            pass

session_service = SessionService()
