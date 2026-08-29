import datetime
import anyio
from typing import Dict, Any, Optional
import stripe

from ..core.config import settings
from ..core.database import supabase, get_clinic_with_billing, update_clinic_billing
from ..core.logger import log

# Stripe Price IDs — loaded from environment variables
# Set these in .env as: STRIPE_PRICE_STARTER, STRIPE_PRICE_GROWTH, STRIPE_PRICE_PRO
# Get real Price IDs from: Stripe Dashboard → Products → Copy price_... ID
def get_plan_price_ids():
    return {
        "starter": settings.STRIPE_PRICE_STARTER or "",
        "growth":  settings.STRIPE_PRICE_GROWTH or "",
        "pro":     settings.STRIPE_PRICE_PRO or ""
    }

PLAN_LIMITS = {
    "trial": {"calls": 200, "sms": 500},
    "starter": {"calls": 200, "sms": 500},
    "growth": {"calls": 500, "sms": 1500},
    "pro": {"calls": 1000000, "sms": 1000000}
}

class BillingService:
    def __init__(self):
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY

    def _stripe_customer_create(self, **kwargs) -> Any:
        return stripe.Customer.create(**kwargs)

    def _stripe_checkout_session_create(self, **kwargs) -> Any:
        return stripe.checkout.Session.create(**kwargs)

    def _stripe_billing_portal_session_create(self, **kwargs) -> Any:
        return stripe.billing_portal.Session.create(**kwargs)

    @property
    def is_configured(self) -> bool:
        return bool(settings.STRIPE_SECRET_KEY)

    async def create_checkout_session(self, clinic_id: str, plan: str, success_url: str, cancel_url: str) -> str:
        """Create checkout session. Dynamically runs in Mock Sandbox mode if Stripe is not configured."""
        if not self.is_configured:
            if settings.is_prod:
                raise Exception("Stripe is not configured in production environment: STRIPE_SECRET_KEY is missing.")
            # Sandbox Mock mode — no Stripe key configured
            log.info(f"[BillingService] Stripe not configured. Generating Mock Checkout URL for clinic: {clinic_id}")
            # Token = first 12 chars of clinic_id (used by the callback endpoint to verify)
            mock_token = clinic_id[:12]
            mock_checkout_url = (
                f"{settings.API_BASE_URL}/api/billing/mock-checkout-success"
                f"?clinic_id={clinic_id}&plan={plan}&token={mock_token}&success_url={success_url}"
            )
            return mock_checkout_url

        try:
            # 1. Resolve clinic details
            clinic = get_clinic_with_billing(clinic_id)
            customer_id = clinic.get("stripe_customer_id")
            
            if not customer_id:
                # Create Stripe Customer
                customer = await anyio.to_thread.run_sync(
                    self._stripe_customer_create,
                    email=clinic["owner_email"],
                    name=clinic["name"],
                    metadata={"clinic_id": clinic_id}
                )
                customer_id = customer.id
                update_clinic_billing(clinic_id, {"stripe_customer_id": customer_id})

            price_id = get_plan_price_ids().get(plan)
            if not price_id:
                raise ValueError(f"Invalid or unconfigured plan: '{plan}'. Set STRIPE_PRICE_{plan.upper()} in .env")

            # 2. Build Stripe checkout session with 14-day free trial
            session = await anyio.to_thread.run_sync(
                self._stripe_checkout_session_create,
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                subscription_data={
                    "trial_period_days": 14,  # 14-day free trial — no charge at signup
                    "metadata": {"clinic_id": clinic_id, "plan": plan}
                },
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,  # allow discount codes for referrals
                metadata={"clinic_id": clinic_id, "plan": plan}
            )
            return session.url
        except Exception as e:
            log.error(f"[BillingService.create_checkout_session] Error: {str(e)}")
            raise

    async def create_portal_session(self, clinic_id: str, return_url: str) -> str:
        """Create Stripe customer self-service billing portal session."""
        if not self.is_configured:
            if settings.is_prod:
                raise Exception("Stripe is not configured in production environment: STRIPE_SECRET_KEY is missing.")
            # Sandbox Mock mode
            log.info(f"[BillingService] Stripe not configured. Generating Mock Portal Session URL for clinic: {clinic_id}")
            return f"{settings.DASHBOARD_URL}/settings?mock_portal=success"

        try:
            clinic = get_clinic_with_billing(clinic_id)
            customer_id = clinic.get("stripe_customer_id")
            if not customer_id:
                raise ValueError("No customer record exists. Initiate checkout first.")

            session = await anyio.to_thread.run_sync(
                self._stripe_billing_portal_session_create,
                customer=customer_id,
                return_url=return_url
            )
            return session.url
        except Exception as e:
            log.error(f"[BillingService.create_portal_session] Error: {str(e)}")
            raise

    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> dict:
        """Process verified Stripe webhook events safely to synchronize SaaS subscription states."""
        if not self.is_configured:
            return {"status": "skipped", "reason": "stripe_unconfigured"}

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception as sig_err:
            log.error(f"[BillingService.Webhook] Verification failed: {str(sig_err)}")
            raise ValueError(f"Invalid webhook signature: {sig_err}")

        event_type = event.type
        data_object = event.data.object

        log.info(f"[BillingService.Webhook] Received Stripe event: {event_type}")

        if event_type == "checkout.session.completed":
            clinic_id = data_object.metadata.get("clinic_id")
            plan = data_object.metadata.get("plan")
            sub_id = data_object.subscription
            cust_id = data_object.customer
            
            if clinic_id:
                # Check if clinic already has a phone number
                c_res = supabase.table("clinics").select("phone_number").eq("id", clinic_id).single().execute()
                current_phone = c_res.data.get("phone_number") if c_res.data else None
                
                assigned_phone = current_phone
                if not current_phone:
                    from .phonenumber_service import phonenumber_service
                    assigned_phone = await phonenumber_service.assign_number_to_clinic(clinic_id)
                    log.info(f"[BillingService.Webhook] Dynamic subscription checkout claimed Twilio phone line: {assigned_phone}")

                update_dict = {
                    "stripe_subscription_id": sub_id,
                    "stripe_customer_id": cust_id,
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
                log.info(f"[BillingService.Webhook] Initialized subscription for clinic: {clinic_id}")
                
                # Trigger referral reward check if referred
                try:
                    ref_check = supabase.table("referrals").select("id").eq("referred_clinic_id", clinic_id).eq("status", "pending").execute()
                    if ref_check.data:
                        from ..api.routers.referral_router import reward_referral
                        await reward_referral(ref_check.data[0]["id"])
                        log.info(f"[BillingService.Webhook] Referral reward triggered for clinic: {clinic_id}")
                except Exception as ref_err:
                    log.error(f"[BillingService.Webhook] Non-critical referral reward check failed: {ref_err}")
 
        elif event_type == "customer.subscription.updated":
            sub_id = data_object.id
            status = data_object.status
            cust_id = data_object.customer
            
            # Find the clinic associated with this subscription
            res = supabase.table("clinics").select("id").eq("stripe_subscription_id", sub_id).execute()
            
            if res.data:
                clinic_id = res.data[0]["id"]
                items = data_object.get("items", {}).get("data", [])
                plan = "starter"
                if items:
                    price_id = items[0].price.id
                    for p_name, p_id in get_plan_price_ids().items():
                        if p_id == price_id:
                            plan = p_name
                            break
                            
                is_active = status in ["active", "trialing"]
                anchor_ts = data_object.current_period_start
                anchor_iso = datetime.datetime.fromtimestamp(anchor_ts, datetime.timezone.utc).isoformat()
                
                update_clinic_billing(clinic_id, {
                    "stripe_subscription_status": status,
                    "plan": plan,
                    "is_active": is_active,
                    "billing_cycle_anchor": anchor_iso,
                    "quota_warning_sent": False,
                    "sms_warning_sent": False
                })
                log.info(f"[BillingService.Webhook] Synced subscription state for clinic: {clinic_id} ({status})")
                
                # Check for referral reward
                if is_active and plan in ["starter", "growth", "pro"]:
                    try:
                        ref_check = supabase.table("referrals").select("id").eq("referred_clinic_id", clinic_id).eq("status", "pending").execute()
                        if ref_check.data:
                            from ..api.routers.referral_router import reward_referral
                            await reward_referral(ref_check.data[0]["id"])
                            log.info(f"[BillingService.Webhook] Referral reward triggered for upgraded clinic: {clinic_id}")
                    except Exception as ref_err:
                        log.error(f"[BillingService.Webhook] Non-critical referral reward check failed: {ref_err}")

 
        elif event_type in ["customer.subscription.deleted", "invoice.payment_failed"]:
            sub_id = data_object.get("subscription") or data_object.id
            
            res = supabase.table("clinics").select("id").eq("stripe_subscription_id", sub_id).execute()
            if res.data:
                clinic_id = res.data[0]["id"]
                status = "unpaid" if event_type == "invoice.payment_failed" else "canceled"
                
                # Release phone line on permanent subscription deletion
                if event_type == "customer.subscription.deleted":
                    try:
                        from .phonenumber_service import phonenumber_service
                        await phonenumber_service.release_number(clinic_id)
                        log.info(f"[BillingService.Webhook] Released phone number for clinic: {clinic_id}")
                    except Exception as release_e:
                        log.warning(f"[BillingService.Webhook] WARNING: Failed to release number: {release_e}")
                
                update_dict = {
                    "stripe_subscription_status": status,
                    "is_active": False
                }
                if event_type == "customer.subscription.deleted":
                    update_dict["phone_number"] = None
                    update_dict["twilio_number"] = None

                update_clinic_billing(clinic_id, update_dict)
                log.info(f"[BillingService.Webhook] Suspended subscription for clinic: {clinic_id} ({status})")

        return {"status": "success", "event": event_type}

billing_service = BillingService()
