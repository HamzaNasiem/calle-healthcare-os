import datetime
import anyio
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Any, List, Optional
from pydantic import BaseModel

from ...core.database import supabase, supabase_read
from ...core.security import AuthenticatedUser, get_current_user_with_role, require_role
from ...core.config import settings
from ...services.audit_service import audit_service

router = APIRouter(prefix="/referrals", tags=["Referrals"])

class TrackReferralRequest(BaseModel):
    ref_code: str
    referred_clinic_id: str

@router.get("/my")
async def get_my_referrals(auth: AuthenticatedUser = Depends(get_current_user_with_role)):
    """
    Get current clinic's referral code, bonus calls, and complete history of referred clinics.
    """
    try:
        # Get referrer clinic's referral code and bonus calls using read replica
        c_res = supabase_read.table("clinics").select("referral_code", "bonus_calls").eq("id", auth.clinic_id).single().execute()
        if not c_res.data:
            raise HTTPException(status_code=404, detail="Clinic not found")
        
        ref_code = c_res.data.get("referral_code")
        bonus_calls = c_res.data.get("bonus_calls", 0) or 0
        
        # If the clinic doesn't have a referral code yet, generate one on the fly and save it
        if not ref_code:
            import re
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', auth.clinic_name)
            ref_code = f"{clean_name[:3].upper()}-{auth.clinic_id[:6].upper()}"
            supabase.table("clinics").update({"referral_code": ref_code}).eq("id", auth.clinic_id).execute()
            
        # Get all referrals referred by this clinic using read replica
        ref_res = supabase_read.table("referrals").select("*").eq("referrer_clinic_id", auth.clinic_id).execute()
        referrals = ref_res.data or []
        
        # Enrich referrals with referred clinic names using read replica
        enriched_referrals = []
        if referrals:
            referred_ids = [r["referred_clinic_id"] for r in referrals if r.get("referred_clinic_id")]
            if referred_ids:
                clinics_res = supabase_read.table("clinics").select("id", "name", "plan", "created_at").in_("id", referred_ids).execute()
                clinics_map = {c["id"]: c for c in (clinics_res.data or [])}
                for r in referrals:
                    rc_id = r.get("referred_clinic_id")
                    c_info = clinics_map.get(rc_id) if rc_id else None
                    enriched_referrals.append({
                        "id": r["id"],
                        "referred_clinic_name": c_info["name"] if c_info else "Unknown Clinic",
                        "referred_clinic_plan": c_info["plan"] if c_info else "trial",
                        "status": r["status"],
                        "created_at": r["created_at"],
                        "rewarded_at": r["rewarded_at"]
                    })
            else:
                for r in referrals:
                    enriched_referrals.append({
                        "id": r["id"],
                        "referred_clinic_name": "Unknown Clinic",
                        "referred_clinic_plan": "trial",
                        "status": r["status"],
                        "created_at": r["created_at"],
                        "rewarded_at": r["rewarded_at"]
                    })
        
        total_referrals = len(enriched_referrals)
        rewarded_referrals = sum(1 for r in enriched_referrals if r["status"] == "rewarded")
        
        return {
            "referral_code": ref_code,
            "bonus_calls": bonus_calls,
            "total_referrals": total_referrals,
            "rewarded_referrals": rewarded_referrals,
            "referrals": enriched_referrals
        }
    except Exception as e:
        print(f"[Referrals] Error getting my referrals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/track")
async def track_referral(req: TrackReferralRequest, request: Request):
    """
    Public endpoint called during/after referred clinic signup.
    Links the referred clinic to the referrer via the referral code.
    """
    try:
        # Validate referral code -> looks up referrer clinic (using read replica)
        referrer_res = supabase_read.table("clinics").select("id", "name").eq("referral_code", req.ref_code).execute()
        if not referrer_res.data:
            return {"success": False, "error": "Invalid referral code"}
            
        referrer = referrer_res.data[0]
        referrer_id = referrer["id"]
        
        # Check if the referred clinic is trying to refer itself
        if referrer_id == req.referred_clinic_id:
            return {"success": False, "error": "Cannot refer your own clinic"}
            
        # Check if this referral already exists (using read replica)
        existing_res = supabase_read.table("referrals").select("id").eq("referred_clinic_id", req.referred_clinic_id).execute()
        if existing_res.data:
            return {"success": False, "error": "This clinic has already been referred"}
            
        # Insert row in referrals table
        res = supabase.table("referrals").insert({
            "ref_code": req.ref_code,
            "referrer_clinic_id": referrer_id,
            "referred_clinic_id": req.referred_clinic_id,
            "status": "pending"
        }).execute()
        
        # Audit log track referral
        await audit_service.log(
            clinic_id=req.referred_clinic_id,
            user_id=None,
            user_email=None,
            action="referral.track",
            resource_type="referrals",
            resource_id=res.data[0]["id"] if res.data else None,
            details={"ref_code": req.ref_code, "referrer_clinic_id": referrer_id},
            request=request
        )
        
        return {
            "success": True,
            "referrer_clinic_name": referrer["name"]
        }
    except Exception as e:
        print(f"[Referrals] Error tracking referral: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def reward_referral(referral_id: str, request_context: Optional[Request] = None) -> bool:
    """
    Core function to reward a referral.
    Adds +500 calls to both referrer and referred clinic, updates status, and sends confirmation emails.
    """
    try:
        # Get referral record (using read replica)
        ref_res = supabase_read.table("referrals").select("*").eq("id", referral_id).eq("status", "pending").execute()
        if not ref_res.data:
            return False
            
        ref = ref_res.data[0]
        referrer_id = ref["referrer_clinic_id"]
        referred_id = ref["referred_clinic_id"]
        
        # Fetch referrer clinic details (using read replica)
        referrer_res = supabase_read.table("clinics").select("id, name, owner_email, plan, trial_ends_at, stripe_customer_id").eq("id", referrer_id).single().execute()
        referrer_clinic = referrer_res.data
        
        # Fetch referred clinic details (using read replica)
        referred_res = supabase_read.table("clinics").select("id, name, owner_email, plan, trial_ends_at, stripe_customer_id").eq("id", referred_id).single().execute()
        referred_clinic = referred_res.data
        
        prices = {"starter": 14900, "growth": 29900, "pro": 59900}
        
        # Make sure stripe is initialized
        import stripe
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
        async def reward_single_clinic(clinic):
            if not clinic:
                return False
                
            clinic_id = clinic["id"]
            plan = clinic.get("plan", "trial") or "trial"
            cust_id = clinic.get("stripe_customer_id")
            trial_ends_str = clinic.get("trial_ends_at")
            
            # Helper to extend trial in DB
            def extend_trial_db():
                try:
                    if trial_ends_str:
                        current_ends = datetime.datetime.fromisoformat(trial_ends_str.replace("Z", "+00:00"))
                    else:
                        current_ends = datetime.datetime.now(datetime.timezone.utc)
                    new_ends = current_ends + datetime.timedelta(days=30)
                    from ...core.database import update_clinic
                    update_clinic(clinic_id, {
                        "trial_ends_at": new_ends.isoformat(),
                        "is_active": True
                    })
                    print(f"[Referral] Extended DB trial/billing cycle by 30 days for clinic {clinic_id}")
                except Exception as db_err:
                    print(f"[Referral] DB trial extension failed for clinic {clinic_id}: {db_err}")

            if plan == "trial" or not cust_id or not settings.STRIPE_SECRET_KEY:
                # Extension in DB
                extend_trial_db()
            else:
                # Stripe Credit Transaction
                plan_price = prices.get(plan, 0)
                if plan_price > 0:
                    try:
                        def _create_balance_tx():
                            return stripe.Customer.create_balance_transaction(
                                customer=cust_id,
                                amount=-plan_price, # negative = credit
                                currency="usd",
                                description="Referral reward - 1 month free"
                            )
                        await anyio.to_thread.run_sync(_create_balance_tx)
                        print(f"[Referral] Credited Stripe balance for clinic {clinic_id} (-${plan_price/100})")
                    except Exception as stripe_err:
                        print(f"[Referral] Stripe customer balance credit failed for clinic {clinic_id}: {stripe_err}. Falling back to DB extension.")
                        extend_trial_db()
                else:
                    extend_trial_db()
                    
        if referrer_clinic:
            await reward_single_clinic(referrer_clinic)
        if referred_clinic:
            await reward_single_clinic(referred_clinic)
            
        # Update referral status
        supabase.table("referrals").update({
            "status": "rewarded",
            "rewarded_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).eq("id", referral_id).execute()
        
        # Audit log reward fulfillment
        await audit_service.log(
            clinic_id=referrer_id,
            user_id=None,
            user_email=None,
            action="referral.rewarded",
            resource_type="referrals",
            resource_id=referral_id,
            details={
                "referrer_clinic_id": referrer_id,
                "referred_clinic_id": referred_id
            },
            request=request_context
        )
        
        # Send notification emails (best-effort)
        try:
            if settings.RESEND_API_KEY:
                import resend
                resend.api_key = settings.RESEND_API_KEY
                
                # Referrer email
                if referrer_clinic and referrer_clinic.get("owner_email"):
                    email_html = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
                        <h2 style="color: #396a00;">🎉 Bytelytic Referral Reward: 1 Month Free!</h2>
                        <p>Hello {referrer_clinic.get('name')},</p>
                        <p>Great news! The clinic you referred ({referred_clinic.get('name') if referred_clinic else 'A new clinic'}) has completed onboarding. As a thank you, we have credited your account with <strong>1 Month Free</strong> (applied directly to your Stripe balance or extended your trial period by 30 days).</p>
                        <p>Keep sharing Bytelytic OS to earn more free months!</p>
                        <br/>
                        <p>Cheers,<br/>The Bytelytic Team</p>
                    </div>
                    """
                    def _send_ref_email():
                        return resend.Emails.send({
                            "from": "Bytelytic Rewards <rewards@bytelytic.com>",
                            "to": [referrer_clinic.get("owner_email")],
                            "subject": "🎉 1 Month Free Credited to Your Account!",
                            "html": email_html
                        })
                    await anyio.to_thread.run_sync(_send_ref_email)
                    
                # Referred email
                if referred_clinic and referred_clinic.get("owner_email"):
                    email_html = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
                        <h2 style="color: #396a00;">🎉 Bytelytic Welcome Bonus: 1 Month Free!</h2>
                        <p>Hello {referred_clinic.get('name')},</p>
                        <p>Since you joined using a referral link, we have credited your account with <strong>1 Month Free</strong> to help you get started! This has been applied as a 30-day trial extension or credit balance.</p>
                        <br/>
                        <p>Cheers,<br/>The Bytelytic Team</p>
                    </div>
                    """
                    def _send_referred_email():
                        return resend.Emails.send({
                            "from": "Bytelytic Rewards <rewards@bytelytic.com>",
                            "to": [referred_clinic.get("owner_email")],
                            "subject": "🎉 Welcome Bonus: 1 Month Free Credited!",
                            "html": email_html
                        })
                    await anyio.to_thread.run_sync(_send_referred_email)
        except Exception as email_err:
            print(f"[Referrals] Email notification failed: {email_err}")
            
        return True
    except Exception as e:
        print(f"[Referrals] Error rewarding referral: {str(e)}")
        return False

@router.post("/reward/{referral_id}")
async def reward_referral_endpoint(referral_id: str, request: Request, auth: AuthenticatedUser = Depends(get_current_user_with_role)):
    """
    Manual override to reward a referral (restricted to Bytelytic Admin).
    """
    if auth.email not in settings.ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    success = await reward_referral(referral_id, request_context=request)
    if not success:
        raise HTTPException(status_code=400, detail="Referral could not be rewarded (already rewarded or not found)")
        
    # Audit log manual reward trigger
    await audit_service.log(
        clinic_id=auth.clinic_id,
        user_id=auth.user_id,
        user_email=auth.email,
        action="referral.manual_reward",
        resource_type="referrals",
        resource_id=referral_id,
        details={"referral_id": referral_id},
        request=request
    )
    return {"success": True, "message": "Referral rewarded with 1 Month Free to both clinics"}

