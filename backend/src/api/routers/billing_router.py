from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, Dict

from ...core.security import get_current_user_with_role, AuthenticatedUser
from ...core.database import get_clinic_with_billing, update_clinic_billing, supabase_read
from ...services.billing_service import billing_service
from ...services.usage_service import usage_service
from ...core.config import settings
from ...services.audit_service import audit_service

router = APIRouter(prefix="/billing", tags=["Billing"])

class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str

class PortalRequest(BaseModel):
    return_url: str

@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_with_role)
):
    """Create a secure Stripe checkout session or Mock checkout url."""
    try:
        url = await billing_service.create_checkout_session(
            clinic_id=auth.clinic_id,
            plan=req.plan,
            success_url=req.success_url,
            cancel_url=req.cancel_url
        )
        
        # Audit log checkout generation
        await audit_service.log(
            clinic_id=auth.clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="billing.create_checkout",
            resource_type="billing",
            resource_id=None,
            details={"plan": req.plan},
            request=request
        )
        return {"checkoutUrl": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/create-subscription")
async def create_subscription(
    req: CheckoutRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_with_role)
):
    """Create a Stripe checkout session for subscription onboarding (Roadmap compliant)."""
    try:
        url = await billing_service.create_checkout_session(
            clinic_id=auth.clinic_id,
            plan=req.plan,
            success_url=req.success_url,
            cancel_url=req.cancel_url
        )
        
        # Audit log subscription setup
        await audit_service.log(
            clinic_id=auth.clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="billing.create_subscription_checkout",
            resource_type="billing",
            resource_id=None,
            details={"plan": req.plan},
            request=request
        )
        return {"checkoutUrl": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/portal")
async def create_portal(
    req: PortalRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_with_role)
):
    """Create Stripe Customer Billing Portal session or Mock portal redirect."""
    try:
        url = await billing_service.create_portal_session(
            clinic_id=auth.clinic_id,
            return_url=req.return_url
        )
        
        # Audit log customer portal creation
        await audit_service.log(
            clinic_id=auth.clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="billing.create_portal",
            resource_type="billing",
            resource_id=None,
            details={"return_url": req.return_url},
            request=request
        )
        return {"portalUrl": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/portal")
async def get_portal(
    request: Request,
    return_url: Optional[str] = None,
    auth: AuthenticatedUser = Depends(get_current_user_with_role)
):
    """Get Stripe customer portal self-service redirection URL (Roadmap compliant)."""
    try:
        ret_url = return_url or f"{settings.DASHBOARD_URL}/settings?tab=billing"
        url = await billing_service.create_portal_session(
            clinic_id=auth.clinic_id,
            return_url=ret_url
        )
        
        # Audit log portal retrieval
        await audit_service.log(
            clinic_id=auth.clinic_id,
            user_id=auth.user_id,
            user_email=auth.email,
            action="billing.get_portal",
            resource_type="billing",
            resource_id=None,
            details={"return_url": ret_url},
            request=request
        )
        return {"portalUrl": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/usage")
async def get_usage(
    auth: AuthenticatedUser = Depends(get_current_user_with_role)
):
    """Fetch current month call and SMS metrics consumption vs limits."""
    try:
        usage = await usage_service.get_current_usage(auth.clinic_id)
        return {"data": usage}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    """Stripe Webhook endpoint for background synchronization."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhooks are unconfigured")
        
    payload = await request.body()
    try:
        result = await billing_service.handle_webhook(
            payload=payload,
            sig_header=stripe_signature,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mock-checkout-success")
async def mock_checkout_success(
    clinic_id: str,
    plan: str,
    success_url: str,
    request: Request,
    token: Optional[str] = None,
):
    """
    Mock Checkout Session success callback (Sandbox mode only).
    This endpoint is a BROWSER REDIRECT — JWT Authorization headers are NOT present.
    Security: uses a token = first 12 chars of clinic_id embedded in the mock URL.
    """
    from ...core.database import supabase
    import datetime

    # Lightweight token check (stateless, no DB lookup needed)
    expected_token = clinic_id[:12]
    if not token or token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid mock checkout token.")

    # Verify clinic exists (using read replica)
    clinic_check = supabase_read.table("clinics").select("id, phone_number").eq("id", clinic_id).maybe_single().execute()
    if not clinic_check.data:
        raise HTTPException(status_code=404, detail="Clinic not found.")

    try:
        from ...services.phonenumber_service import phonenumber_service
        current_phone = clinic_check.data.get("phone_number")

        assigned_phone = current_phone
        if not current_phone:
            assigned_phone = await phonenumber_service.assign_number_to_clinic(clinic_id)
            print(f"[BillingRouter] Sandbox upgrade claimed Twilio line: {assigned_phone}")

        update_dict = {
            "stripe_subscription_id": f"sub_mock_{clinic_id[:8].lower()}",
            "stripe_subscription_status": "active",
            "plan": plan,
            "is_active": True,
            "billing_cycle_anchor": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "quota_warning_sent": False,
            "sms_warning_sent": False
        }
        if assigned_phone:
            update_dict["phone_number"] = assigned_phone
            update_dict["twilio_number"] = assigned_phone

        update_clinic_billing(clinic_id, update_dict)
        print(f"[BillingRouter] Mock payment complete. plan='{plan}' clinic={clinic_id}")

        # Trigger referral reward check if referred (Mock Sandbox Mode) (using read replica)
        try:
            ref_check = supabase_read.table("referrals").select("id").eq("referred_clinic_id", clinic_id).eq("status", "pending").execute()
            if ref_check.data:
                from .referral_router import reward_referral
                await reward_referral(ref_check.data[0]["id"])
                print(f"[BillingRouter] Mock checkout success: referral reward triggered for clinic: {clinic_id}")
        except Exception as ref_err:
            print(f"[BillingRouter] Non-critical referral reward check failed in mock checkout: {ref_err}")

        # Audit log mock payment success
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=None,
            user_email=None,
            action="billing.mock_checkout_success",
            resource_type="billing",
            resource_id=None,
            details={"plan": plan},
            request=request
        )

        return RedirectResponse(url=success_url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Mock checkout failed: {str(e)}")


stripe_webhook_router = APIRouter(prefix="/webhooks/stripe", tags=["Billing Webhook"])

@stripe_webhook_router.post("")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None)
):
    """Stripe webhook processing endpoint at /webhooks/stripe."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhooks are unconfigured")
        
    payload = await request.body()
    try:
        result = await billing_service.handle_webhook(
            payload=payload,
            sig_header=stripe_signature,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

