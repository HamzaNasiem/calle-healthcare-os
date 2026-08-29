import datetime
from typing import Dict, Any

from ..core.database import supabase, get_clinic_with_billing, update_clinic_billing
from .billing_service import PLAN_LIMITS
from .email_service import email_service

class UsageService:
    async def get_current_usage(self, clinic_id: str) -> Dict[str, Any]:
        """
        Calculate call and SMS consumptions for current 30-day billing cycle.
        Accounts transparently for self-healing JSONB database fallbacks.
        """
        try:
            # 1. Fetch clinic details via self-healing billing wrapper
            clinic = get_clinic_with_billing(clinic_id)
            
            plan = clinic.get("plan", "trial") or "trial"
            status = clinic.get("stripe_subscription_status", "trialing") or "trialing"
            anchor_str = clinic.get("billing_cycle_anchor")
            owner_email = clinic.get("owner_email")
            
            # 2. Parse billing cycle anchor and compute current period boundaries
            if anchor_str:
                try:
                    cycle_start = datetime.datetime.fromisoformat(anchor_str.replace("Z", "+00:00"))
                except Exception:
                    cycle_start = datetime.datetime.now(datetime.timezone.utc)
            else:
                created_at_str = clinic.get("created_at")
                if created_at_str:
                    cycle_start = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                else:
                    cycle_start = datetime.datetime.now(datetime.timezone.utc)

            now = datetime.datetime.now(datetime.timezone.utc)
            
            # Project anchor forward by 30-day increments to calculate current billing period
            current_cycle_start = cycle_start
            delta = now - cycle_start
            if delta.days >= 30:
                periods = delta.days // 30
                current_cycle_start = cycle_start + datetime.timedelta(days=30 * periods)
                
                # SELF-HEALING: Since we have entered a new billing period, update the anchor
                # in the DB and reset warning flags so warnings can be sent for the new cycle
                try:
                    update_clinic_billing(clinic_id, {
                        "billing_cycle_anchor": current_cycle_start.isoformat(),
                        "quota_warning_sent": False,
                        "sms_warning_sent": False
                    })
                    print(f"[UsageService] Self-healed billing cycle reset for clinic {clinic_id}. New start: {current_cycle_start.isoformat()}")
                except Exception as db_reset_err:
                    print(f"[UsageService] Failed to auto-reset billing cycle in DB: {db_reset_err}")
                
            current_cycle_end = current_cycle_start + datetime.timedelta(days=30)
            
            # 3. Query active calls answered during current billing period
            calls_res = supabase.table("calls").select("id", count="exact") \
                .eq("clinic_id", clinic_id) \
                .gte("created_at", current_cycle_start.isoformat()) \
                .execute()
            calls_count = calls_res.count or 0
            
            # 4. Query SMS notifications dispatched during current billing period
            sms_res = supabase.table("sms_messages").select("id", count="exact") \
                .eq("clinic_id", clinic_id) \
                .gte("created_at", current_cycle_start.isoformat()) \
                .execute()
            sms_count = sms_res.count or 0
            is_active = clinic.get("is_active", True)
            if not is_active:
                status = "suspended"

            # Get plan allocations
            limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])
            calls_limit = limits["calls"]
            sms_limit = limits["sms"]
            
            return {
                "calls_count": calls_count,
                "calls_limit": calls_limit,
                "calls_percentage": min(100.0, round((calls_count / calls_limit) * 100, 1)) if calls_limit > 0 else 0.0,
                "sms_count": sms_count,
                "sms_limit": sms_limit,
                "sms_percentage": min(100.0, round((sms_count / sms_limit) * 100, 1)) if sms_limit > 0 else 0.0,
                "billing_cycle_start": current_cycle_start.isoformat(),
                "billing_cycle_end": current_cycle_end.isoformat(),
                "trial_ends_at": clinic.get("trial_ends_at"),  # actual trial expiry date
                "plan": plan,
                "status": status,
                "is_active": is_active,
                "owner_email": owner_email,
                "referral_code": clinic.get("referral_code") or f"REF-{clinic_id[:6].upper()}"
            }
        except Exception as e:
            print(f"[UsageService.get_current_usage] Error: {str(e)}")
            # Safety fallback returns default trial metrics
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            future_iso = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
            return {
                "calls_count": 0,
                "calls_limit": 200,
                "calls_percentage": 0.0,
                "sms_count": 0,
                "sms_limit": 500,
                "sms_percentage": 0.0,
                "billing_cycle_start": now_iso,
                "billing_cycle_end": future_iso,
                "plan": "trial",
                "status": "trailing",
                "is_active": True,
                "owner_email": "",
                "referral_code": f"REF-{clinic_id[:6].upper()}"
            }


    async def enforce_quota_limits(self, clinic_id: str) -> bool:
        """
        Enforce active call and SMS capacity restrictions. 
        Deactivates account state immediately when monthly call or SMS limits are fully exhausted.
        """
        try:
            clinic = get_clinic_with_billing(clinic_id)
            if not clinic.get("is_active", True):
                return False
                
            usage = await self.get_current_usage(clinic_id)
            
            calls_count = usage["calls_count"]
            calls_limit = usage["calls_limit"]
            sms_count = usage["sms_count"]
            sms_limit = usage["sms_limit"]
            owner_email = usage["owner_email"]
            
            quota_warning_sent = clinic.get("quota_warning_sent")
            sms_warning_sent = clinic.get("sms_warning_sent")
            
            updates = {}
            is_active = True
            
            # 1. Hard threshold enforcement (100% capacity)
            if calls_count >= calls_limit:
                print(f"[UsageService] Clinic {clinic_id} reached 100% call quota limit ({calls_count}/{calls_limit}). Deactivating account.")
                updates["is_active"] = False
                is_active = False
                
                try:
                    if owner_email:
                        await email_service.send_quota_exhausted_email(owner_email, clinic_id, calls_count, calls_limit)
                        await email_service.send_alert_email(
                            f"🚨 Quota Exhausted alert: Clinic {clinic_id} answered call limit has been reached ({calls_count}/{calls_limit}). Account suspended."
                        )
                except Exception as email_err:
                    print(f"[UsageService.enforce] Call quota exhausted alert dispatch failed: {str(email_err)}")
                    
            elif sms_count >= sms_limit:
                print(f"[UsageService] Clinic {clinic_id} reached 100% SMS quota limit ({sms_count}/{sms_limit}). Deactivating account.")
                updates["is_active"] = False
                is_active = False
                
                try:
                    if owner_email:
                        await email_service.send_sms_quota_exhausted_email(owner_email, clinic_id, sms_count, sms_limit)
                        await email_service.send_alert_email(
                            f"🚨 SMS Quota Exhausted alert: Clinic {clinic_id} SMS limit has been reached ({sms_count}/{sms_limit}). Account suspended."
                        )
                except Exception as email_err:
                    print(f"[UsageService.enforce] SMS quota exhausted alert dispatch failed: {str(email_err)}")
            
            # 2. Soft threshold warnings (80% capacity)
            if calls_count >= int(calls_limit * 0.8) and not quota_warning_sent:
                print(f"[UsageService.WARNING] Clinic {clinic_id} reached 80% soft call quota capacity ({calls_count}/{calls_limit}). Dispatching warning alert.")
                updates["quota_warning_sent"] = True
                try:
                    if owner_email:
                        await email_service.send_quota_warning_email(owner_email, clinic_id, calls_count, calls_limit)
                except Exception as email_err:
                    print(f"[UsageService.enforce] Soft warning alert dispatch failed: {str(email_err)}")
                    
            if sms_count >= int(sms_limit * 0.8) and not sms_warning_sent:
                print(f"[UsageService.WARNING] Clinic {clinic_id} reached 80% soft SMS quota capacity ({sms_count}/{sms_limit}). Dispatching warning alert.")
                updates["sms_warning_sent"] = True
                try:
                    if owner_email:
                        await email_service.send_sms_quota_warning_email(owner_email, clinic_id, sms_count, sms_limit)
                except Exception as email_err:
                    print(f"[UsageService.enforce] Soft SMS warning alert dispatch failed: {str(email_err)}")
            
            if updates:
                update_clinic_billing(clinic_id, updates)
                
            return is_active
        except Exception as e:
            print(f"[UsageService.enforce_quota_limits] Error (suppressed): {str(e)}")
            return True

usage_service = UsageService()
