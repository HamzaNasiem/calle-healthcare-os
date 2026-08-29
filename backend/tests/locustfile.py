from locust import HttpUser, task, between
import json
import uuid

class BytelyticClinicOSUser(HttpUser):
    wait_time = between(0.1, 1.0) # simulate high-traffic stress load

    @task(1)
    def health_check(self):
        self.client.get("/health")

    @task(3)
    def simulate_voice_ai_webhook(self):
        # Simulate high-load concurrent voice AI extraction webhook payload
        payload = {
            "event": "call_analyzed",
            "call_id": f"call_{uuid.uuid4().hex[:12]}",
            "call_status": "completed",
            "direction": "inbound",
            "from_number": "+15551234567",
            "to_number": "+15755734355",
            "duration_ms": 45000,
            "transcript": "Hello, I would like to book an appointment with Dr. Hamza on next Monday at 10:00 AM. My name is Alice.",
            "agent_id": "agent_dummy_123"
        }
        headers = {
            "x-retell-signature": "dummy_signature_verify_bypassed_in_dev_env",
            "Content-Type": "application/json"
        }
        self.client.post("/api/v1/webhooks/retell/", json=payload, headers=headers)
