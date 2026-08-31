from fastapi import APIRouter

from .routers.auth_router import router as auth_router
from .routers.appointments_router import router as appointments_router
from .routers.calls_router import router as calls_router
from .routers.clinics_router import router as clinics_router
from .routers.dashboard_router import router as dashboard_router
from .routers.patients_router import router as patients_router
from .routers.waitlist_router import router as waitlist_router
from .routers.admin_router import router as admin_router
from .routers.billing_router import router as billing_router, stripe_webhook_router
from .routers.staff_router import router as staff_router
from .routers.demo_router import router as demo_router
from .routers.referral_router import router as referral_router
from .routers.notifications_router import router as notifications_router
from .routers.analytics_router import router as analytics_router
from .routers.groups_router import router as groups_router
from .routers.agency_router import router as agency_router
from .routers.agent_config_router import router as agent_config_router
from .webhooks.twilio_webhook import router as twilio_webhook
from .routers.ehr_router import router as ehr_router
from .webhooks.telnyx_webhook import router as telnyx_webhook
from .webhooks.retell_webhook import router as retell_webhook
from .routers.security_router import router as security_router
from .routers.calle_router import router as calle_router
from .v1.outbound_calls import router as outbound_calls_router, webhook_router as outbound_webhook_router
from .v1.prior_auth import router as prior_auth_router
from .v1.compliance import router as compliance_router
from src.ws.router import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(appointments_router)
api_router.include_router(calls_router)
api_router.include_router(clinics_router)
api_router.include_router(dashboard_router)
api_router.include_router(patients_router)
api_router.include_router(waitlist_router)
api_router.include_router(admin_router)
api_router.include_router(staff_router)
api_router.include_router(billing_router)
api_router.include_router(stripe_webhook_router)
api_router.include_router(demo_router)
api_router.include_router(referral_router)
api_router.include_router(notifications_router)
api_router.include_router(analytics_router)
api_router.include_router(groups_router)
api_router.include_router(agency_router)
api_router.include_router(agent_config_router)
api_router.include_router(twilio_webhook)
api_router.include_router(telnyx_webhook)
api_router.include_router(retell_webhook)
api_router.include_router(ehr_router)
api_router.include_router(integrations_router)
api_router.include_router(security_router)
api_router.include_router(calle_router)
api_router.include_router(prior_auth_router)
api_router.include_router(compliance_router)
api_router.include_router(outbound_calls_router)
api_router.include_router(outbound_webhook_router)
api_router.include_router(ws_router)

# Root-level router (no /api prefix) — supports /auth/login, /patients etc
root_api_router = APIRouter()
root_api_router.include_router(auth_router)
root_api_router.include_router(appointments_router)
root_api_router.include_router(calls_router)
root_api_router.include_router(clinics_router)
root_api_router.include_router(dashboard_router)
root_api_router.include_router(patients_router)
root_api_router.include_router(waitlist_router)
root_api_router.include_router(admin_router)
root_api_router.include_router(staff_router)
root_api_router.include_router(billing_router)
root_api_router.include_router(stripe_webhook_router)
root_api_router.include_router(demo_router)
root_api_router.include_router(referral_router)
root_api_router.include_router(notifications_router)
root_api_router.include_router(analytics_router)
root_api_router.include_router(groups_router)
root_api_router.include_router(agency_router)
root_api_router.include_router(agent_config_router)
root_api_router.include_router(twilio_webhook)
root_api_router.include_router(telnyx_webhook)
root_api_router.include_router(ehr_router)
root_api_router.include_router(integrations_router)
root_api_router.include_router(security_router)
root_api_router.include_router(calle_router)
root_api_router.include_router(prior_auth_router)
root_api_router.include_router(compliance_router)
root_api_router.include_router(outbound_calls_router)
root_api_router.include_router(outbound_webhook_router)
root_api_router.include_router(ws_router)

