# Bytelytic Clinic OS — Autonomous Healthcare Phone Desk

**Contribution Area:** Apps

## What it does
Bytelytic Clinic OS is a full-stack clinic management system where CALL-E is the autonomous voice engine for every outbound call workflow: appointment confirmations, no-show recovery, patient recall, waitlist management, and prior auth follow-ups.

## CALL-E Integration
- **SDK:** Python `calle-ai` SDK (v0.6.0)
- **Calls per workflow:** Appointment confirmation, no-show recovery, recall, waitlist fill, prior auth, post-visit survey
- **Languages:** English, Spanish (auto-detected)
- **Demo URL:** https://calle-healthcare-os.vercel.app

## Use Case
Healthcare clinics lose ~$150-300 per no-show appointment. Bytelytic uses CALL-E to autonomously call patients when a cancellation occurs, offer the slot to the next waitlist patient, and confirm attendance — all without a human receptionist.

## Technical Implementation
Our integration leverages the `calle-ai` Python SDK to trigger calls programmatically and process structured JSON results via webhooks. We achieved sub-second dial latency by combining CALL-E with SIP trunks. 

```python
from calle import CalleClient
from src.core.config import settings

client = CalleClient(api_key=settings.CALLE_API_KEY)

def trigger_no_show_recovery(phone: str, patient_name: str):
    return client.calls.create(
        to_phone=phone,
        goal=f"Call {patient_name} who missed their appointment 2 hours ago. Offer empathy, waive cancellation fees, and reschedule.",
        result_schema={
            "wants_rebook": "boolean",
            "preferred_time": "string",
            "reason_for_no_show": "string"
        }
    )
```

## How to run
1. Clone the repository
2. `cd backend && pip install -r requirements.txt` (Make sure `calle-ai` is installed)
3. Copy `.env.example` to `.env` and add your `CALLE_API_KEY`
4. Run `uvicorn src.main:app --reload`
5. Send a POST request to `/api/v1/calle/no-show-recovery` to trigger the agent.
