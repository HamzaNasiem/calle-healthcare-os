import datetime
import random
import time
import uuid
import asyncio
from typing import Optional
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ...core.database import supabase, auth_client, supabase_read
from ...services.email_service import email_service
from ...core.config import settings

router = APIRouter(prefix="/demo", tags=["Demo"])

# Simple IP-based rate limiter (Redis-free)
# 3 demo provisions per IP per hour
class DemoRateLimiter:
    def __init__(self):
        # IP -> list of timestamps
        self.requests = defaultdict(list)
        
    def check_rate_limit(self, ip: str) -> bool:
        now = time.time()
        # Keep only last 1 hour (3600 seconds)
        self.requests[ip] = [t for t in self.requests[ip] if now - t < 3600]
        if len(self.requests[ip]) >= 3:
            return False
        self.requests[ip].append(now)
        return True

demo_limiter = DemoRateLimiter()

class DemoProvisionRequest(BaseModel):
    name: str  # User's name
    email: str  # User's email
    clinicName: str  # Clinic name


# Realistic Seed Data Generators
MOCK_PATIENTS = [
    {"name": "John Doe", "email": "john.doe@gmail.com", "phone": "+15550190001", "provider": "Blue Cross Blue Shield", "member_id": "BCB123456"},
    {"name": "Jane Smith", "email": "jane.smith@yahoo.com", "phone": "+15550190002", "provider": "Aetna", "member_id": "AET987654"},
    {"name": "Robert Johnson", "email": "robert.j@outlook.com", "phone": "+15550190003", "provider": "Cigna", "member_id": "CIG741258"},
    {"name": "Emily Davis", "email": "emily.d@gmail.com", "phone": "+15550190004", "provider": "UnitedHealthcare", "member_id": "UHC369852"},
    {"name": "Michael Wilson", "email": "michael.w@gmail.com", "phone": "+15550190005", "provider": "Humana", "member_id": "HUM159357"}
]

MOCK_TRANSCRIPTS = [
    "Patient: Hi, I'd like to book a follow-up visit for next Tuesday afternoon if possible.\nAI: Hello! Yes, I can help with that. I have an opening next Tuesday, June 9th at 2:00 PM or 3:30 PM. Which works best?\nPatient: Let's do 2:00 PM.\nAI: Perfect, I have scheduled your Follow-up Visit with Dr. Miller for June 9th at 2:00 PM.",
    "Patient: Hello, are you open on Saturdays?\nAI: Hi! Our office business hours are Monday through Friday, 8:00 AM to 6:00 PM. We are closed on Saturdays and Sundays. Can I help you schedule an appointment during the week?\nPatient: Oh okay, no thank you, I will call back later.",
    "Patient: Yes, hi. I need to cancel my appointment for tomorrow morning.\nAI: I can help you with that. Can I get your name and date of birth?\nPatient: It's Jane Smith, September 20, 1992.\nAI: Thank you Jane. I've successfully canceled your appointment for tomorrow morning. Would you like to reschedule now?\nPatient: Yes, how about Thursday morning?\nAI: Sure, I have Thursday morning at 9:00 AM available. Does that work?\nPatient: Yes, that is perfect.",
    "Patient: Hi, do you accept Cigna insurance?\nAI: Yes, we do accept Cigna, as well as Aetna, BCBS, and UnitedHealthcare. Would you like to schedule an appointment?\nPatient: Yes, please. I'm a new patient, need an initial evaluation.\nAI: Great, let me get you set up for our next available slot on Monday at 10:00 AM."
]

@router.get("/public-stats")
async def get_public_stats(response: Response):
    """
    Public endpoint to get global booking stats for social proof.
    Combines a premium baseline with the actual count of appointments from the database.
    """
    response.headers["Cache-Control"] = "public, max-age=60"
    try:
        res = supabase_read.table("appointments").select("id", count="exact").execute()
        db_count = res.count or 0
        total_booked = 14820 + db_count
        return {"appointments_count": total_booked}
    except Exception as e:
        print(f"[DemoRouter] Error fetching public stats: {e}")
        return {"appointments_count": 14829}

@router.post("/provision")
async def provision_demo_clinic(req: DemoProvisionRequest, request: Request):
    """
    Public endpoint to auto-provision a sandbox demo clinic.
    Creates a temporary authenticated user, clinic, and seeds realistic statistics.
    """
    # 1. Rate Limit Check
    x_forwarded_for = request.headers.get("x-forwarded-for")
    ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else (request.client.host if request.client else "unknown")
    
    if not demo_limiter.check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Demo limit exceeded. Maximum 3 demo accounts per hour.")
        
    print(f"[DemoRouter] Provisioning demo clinic for {req.email} ({req.clinicName})")
    
    # 2. Check if email is already registered in DB
    existing = supabase.table("clinics").select("id").eq("owner_email", req.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="This email is already associated with an account. Please log in.")

    # 3. Create Supabase Auth User with a secure temp password
    temp_password = f"Demo-{uuid.uuid4().hex[:8].capitalize()}1!"
    try:
        auth_res = supabase.auth.admin.create_user({
            "email": req.email,
            "password": temp_password,
            "email_confirm": True,
            "user_metadata": {"name": req.name}
        })
        user = auth_res.user
    except Exception as auth_err:
        print(f"[DemoRouter] Auth user creation failed: {auth_err}")
        # Clean up messaging
        err_str = str(auth_err)
        if "already registered" in err_str or "already been registered" in err_str:
            raise HTTPException(status_code=400, detail="This email is already registered. Please log in.")
        raise HTTPException(status_code=500, detail="Failed to create auth user for demo clinic.")

    # 4. Insert Demo Clinic Record
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        trial_ends = now + datetime.timedelta(days=7) # Shorter 7-day trial for demos
        
        clinic_id = str(uuid.uuid4())
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', req.clinicName)
        ref_code = f"{clean_name[:3].upper()}-{clinic_id[:6].upper()}"

        DEFAULT_HOURS = {
            "mon": {"enabled": True, "start": "08:00", "end": "18:00"},
            "tue": {"enabled": True, "start": "08:00", "end": "18:00"},
            "wed": {"enabled": True, "start": "08:00", "end": "18:00"},
            "thu": {"enabled": True, "start": "08:00", "end": "18:00"},
            "fri": {"enabled": True, "start": "08:00", "end": "18:00"},
            "sat": {"enabled": False, "start": "08:00", "end": "18:00"},
            "sun": {"enabled": False, "start": "08:00", "end": "18:00"},
        }
        DEFAULT_APPT_TYPES = [
            {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 150.0},
            {"name": "Follow-up Visit", "duration": 30, "duration_minutes": 30, "fee": 75.0},
        ]
        
        clinic_insert = {
            "id": clinic_id,
            "name": req.clinicName,
            "owner_email": req.email,
            "timezone": "America/Chicago",
            "specialty": "General Practice",
            "city": "Chicago",
            "primary_doctor_name": f"Dr. {req.name.split()[0]}",
            "primary_doctor_credentials": "MD",
            "primary_doctor_phone": "+15550190000",
            "business_hours": DEFAULT_HOURS,
            "appointment_types": DEFAULT_APPT_TYPES,
            "plan": "trial",
            "trial_ends_at": trial_ends.isoformat(),
            "stripe_subscription_status": "trialing",
            "is_active": True,
            "is_demo": True,
            "referral_code": ref_code
        }
        
        clinic_res = supabase.table("clinics").insert(clinic_insert).execute()
        if not clinic_res.data:
            raise Exception("Clinic record insert returned empty.")
        clinic = clinic_res.data[0]
        clinic_id = clinic["id"]
        
    except Exception as db_err:
        print(f"[DemoRouter] Clinic database record creation failed: {db_err}")
        # Rollback auth user
        try:
            supabase.auth.admin.delete_user(user.id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to create clinic record in database.")

    # 5. Populate Clinic User link
    try:
        supabase.table("clinic_users").insert({
            "clinic_id": clinic_id,
            "supabase_user_id": str(user.id),
            "email": req.email,
            "name": req.name,
            "role": "owner"
        }).execute()
        print(f"[DemoRouter] Linked owner user {user.id} to clinic {clinic_id} in clinic_users")
    except Exception as cu_err:
        print(f"[DemoRouter] Failed to create clinic user association: {cu_err}")

    # 6. Seed Demo Data (Patients, Appointments, Calls)
    try:
        patient_ids = []
        # A. Seed Patients
        for mp in MOCK_PATIENTS:
            p_res = supabase.table("patients").insert({
                "clinic_id": clinic_id,
                "name": mp["name"],
                "email": mp["email"],
                "phone": mp["phone"],
                "insurance_provider": mp["provider"],
                "insurance_member_id": mp["member_id"],
                "date_of_birth": "1985-06-15",
                "no_show_count": random.randint(0, 1),
                "total_visits": random.randint(1, 5)
            }).execute()
            if p_res.data:
                patient_ids.append(p_res.data[0]["id"])
                
        # B. Seed Appointments
        # Seed 8 appointments across past, today, and future
        appt_types = ["Initial Evaluation", "Follow-up Visit"]
        appt_ids = []
        
        # We need relative dates
        today = datetime.datetime.now(datetime.timezone.utc)
        
        # Past completed appointments
        for i in range(3):
            days_ago = i + 2
            appt_time = today - datetime.timedelta(days=days_ago, hours=random.randint(1, 6))
            p_index = i % len(patient_ids)
            p_name = MOCK_PATIENTS[p_index]["name"]
            p_phone = MOCK_PATIENTS[p_index]["phone"]
            
            appt_res = supabase.table("appointments").insert({
                "clinic_id": clinic_id,
                "patient_id": patient_ids[p_index],
                "patient_name": p_name,
                "patient_phone": p_phone,
                "appointment_type": random.choice(appt_types),
                "datetime": appt_time.isoformat(),
                "duration_minutes": 30 if i > 0 else 60,
                "status": "completed",
                "revenue_amount": 150.0,
                "insurance_verified": True
            }).execute()
            if appt_res.data:
                appt_ids.append(appt_res.data[0]["id"])

        # Noshow / Canceled appointments
        appt_time_noshow = today - datetime.timedelta(days=1, hours=2)
        p_index = 3 % len(patient_ids)
        noshow_res = supabase.table("appointments").insert({
            "clinic_id": clinic_id,
            "patient_id": patient_ids[p_index],
            "patient_name": MOCK_PATIENTS[p_index]["name"],
            "patient_phone": MOCK_PATIENTS[p_index]["phone"],
            "appointment_type": "Initial Evaluation",
            "datetime": appt_time_noshow.isoformat(),
            "duration_minutes": 60,
            "status": "no_show",
            "revenue_amount": 0.0,
            "noshow_risk": 0.85
        }).execute()
        
        # Scheduled upcoming appointments
        for i in range(3):
            days_ahead = i + 1
            appt_time = today + datetime.timedelta(days=days_ahead, hours=random.randint(1, 6))
            p_index = (i + 2) % len(patient_ids)
            p_name = MOCK_PATIENTS[p_index]["name"]
            p_phone = MOCK_PATIENTS[p_index]["phone"]
            
            supabase.table("appointments").insert({
                "clinic_id": clinic_id,
                "patient_id": patient_ids[p_index],
                "patient_name": p_name,
                "patient_phone": p_phone,
                "appointment_type": random.choice(appt_types),
                "datetime": appt_time.isoformat(),
                "duration_minutes": 30,
                "status": "confirmed" if i == 0 else "scheduled",
                "revenue_amount": 150.0
            }).execute()

        # C. Seed Call Logs
        # Seed 12 call records
        for i in range(12):
            hours_ago = (i * 3) + 1
            call_time = today - datetime.timedelta(hours=hours_ago)
            p_index = i % len(MOCK_PATIENTS)
            p_name = MOCK_PATIENTS[p_index]["name"]
            p_phone = MOCK_PATIENTS[p_index]["phone"]
            
            transcript = MOCK_TRANSCRIPTS[i % len(MOCK_TRANSCRIPTS)]
            duration = random.randint(45, 120)
            
            supabase.table("calls").insert({
                "clinic_id": clinic_id,
                "patient_name": p_name,
                "patient_id": patient_ids[p_index],
                "from_number": p_phone,
                "to_number": "+15559998888",
                "direction": "inbound",
                "duration_seconds": duration,
                "started_at": call_time.isoformat(),
                "ended_at": (call_time + datetime.timedelta(seconds=duration)).isoformat(),
                "status": "completed",
                "transcript": transcript,
                "outcome": "Scheduled Appointment" if "scheduled" in transcript.lower() else "Answered Hours Question" if "closed" in transcript.lower() else "Canceled Appointment",
                "call_type": "receptionist"
            }).execute()

    except Exception as seed_err:
        print(f"[DemoRouter] WARNING: Seeding demo data encountered errors: {seed_err}")
        # Keep going even if seeding fails slightly, since the clinic was created.

    # 7. Authenticate the demo user to get JWT tokens immediately
    token = None
    refresh_token = None
    try:
        login_res = await asyncio.get_event_loop().run_in_executor(
            None, lambda: auth_client.auth.sign_in_with_password({"email": req.email, "password": temp_password})
        )
        if login_res.session:
            token = login_res.session.access_token
            refresh_token = login_res.session.refresh_token
    except Exception as login_err:
        print(f"[DemoRouter] Auto-login failed: {login_err}")

    # 8. Send Demo Clinic Provisioned Welcome Email (Best effort)
    try:
        await email_service.send_demo_welcome_email(
            email=req.email,
            name=req.name,
            clinic_name=req.clinicName,
            temp_password=temp_password
        )
    except Exception as email_err:
        print(f"[DemoRouter] Demo welcome email failed to send: {email_err}")

    return {
        "success": True,
        "email": req.email,
        "password": temp_password,
        "clinicId": clinic_id,
        "clinicName": req.clinicName,
        "token": token,
        "refreshToken": refresh_token,
        "timezone": "America/Chicago",
        "role": "owner"
    }
