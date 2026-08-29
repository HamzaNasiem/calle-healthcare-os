import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone, timedelta
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.engine import engine
from src.models.user import User
from src.models.tenant import Tenant
from src.models.patient import Patient
from src.models.provider import Provider
from src.models.appointment import Appointment
from src.models.call_log import CallLog
from src.models.clinical_note import ClinicalNote
from src.models.tenant_settings import TenantSettings
from src.core.security import get_password_hash
from src.core.encryption import phi_crypto
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from src.models.waitlist import Waitlist

async def seed_db():
    print("Starting DB seed...")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Create a tenant if not exists
        stmt = select(Tenant).limit(1)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(name="ByteLytic Demo Clinic", is_active=True)
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            print(f"Created Tenant: {tenant.id}")
        else:
            print(f"Found Tenant: {tenant.id}")
            
        # Create an owner user if not exists
        email = "demo@bytelytic.com"
        stmt = select(User).where(User.email == email)
        res = await session.execute(stmt)
        owner = res.scalar_one_or_none()
        
        if not owner:
            owner = User(
                tenant_id=tenant.id,
                email=email,
                full_name="Dr. Demo Owner",
                hashed_password=get_password_hash("Password123!"),
                role="owner",
                is_active=True,
                mfa_enabled=False
            )
            session.add(owner)
            await session.commit()
            await session.refresh(owner)
            print(f"Created Owner User: {owner.id}")
        else:
            print(f"Found Owner User: {owner.id}")
            
        # Create Settings
        stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        res = await session.execute(stmt)
        if not res.scalar_one_or_none():
            settings = TenantSettings(
                tenant_id=tenant.id,
                business_hours='{"mon":{"open":true,"start":"09:00","end":"17:00"}}',
                ai_persona='{"name":"ByteLytic AI","tone":"friendly","greeting":"Hi!","voicemail_message":"Leave a message"}',
                services='[{"id":"'+str(uuid.uuid4())+'","name":"General Checkup","duration_minutes":30}]',
                faq_entries='[]',
                timezone="UTC"
            )
            session.add(settings)
            await session.commit()
            print("Created Tenant Settings")

        # Create Provider
        stmt = select(Provider).where(Provider.tenant_id == tenant.id)
        res = await session.execute(stmt)
        provider = res.scalar_one_or_none()
        if not provider:
            provider = Provider(
                tenant_id=tenant.id,
                display_name="Dr. Smith",
                specialty="General Practice",
                is_accepting_patients=True
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)
            print(f"Created Provider: {provider.id}")

        # Seed Patients
        stmt = select(Patient).where(Patient.tenant_id == tenant.id)
        res = await session.execute(stmt)
        print("Seeding Patients...")
        patients = []
        for i in range(10):
            phone_str = f"+155500010{i:02d}"
            import hashlib
            phone_hash = hashlib.sha256(phone_str.encode('utf-8')).hexdigest()
            p = Patient(
                tenant_id=tenant.id,
                phone_hash=phone_hash,
                full_name=f"Demo Patient {i+1}",
                phone=phone_str,
                is_existing_patient=random.choice([True, False]),
                visit_count=random.randint(0, 5),
                is_vip=random.choice([True, False, False])
            )
            patients.append(p)
        session.add_all(patients)
        await session.commit()
        print(f"Added 10 patients")
        
        # Fetch them back to add appointments
        res = await session.execute(select(Patient).where(Patient.tenant_id == tenant.id))
        patients = res.scalars().all()
        
        print("Seeding Appointments & Calls...")
        now = datetime.now(timezone.utc)
        appts = []
        calls = []
        notes = []
        
        for i, p in enumerate(patients):
            # 1-2 appointments per patient
            for j in range(random.randint(1, 2)):
                slot_start = now + timedelta(days=random.randint(-5, 5), hours=random.randint(9, 16))
                slot_start = slot_start.replace(minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=30)
                
                status = random.choice(["scheduled", "confirmed", "completed"])
                if slot_start < now:
                    status = "completed" if random.random() > 0.2 else "cancelled"
                    
                appt = Appointment(
                    tenant_id=tenant.id,
                    patient_id=p.id,
                    provider_id=owner.id,
                    slot_start=slot_start,
                    slot_end=slot_end,
                    service_type="General Checkup",
                    duration_minutes=30,
                    status=status,
                    booked_by="ai_agent",
                    sms_confirmed=True if status == "confirmed" else False
                )
                appts.append(appt)
                
            # Call logs
            c = CallLog(
                tenant_id=tenant.id,
                patient_id=p.id,
                duration_seconds=random.randint(60, 300),
                outcome=random.choice(["booked", "faq_answered", "transferred"]),
                transcript_encrypted=phi_crypto.encrypt('[{"role":"user","content":"Hello I want to book"},{"role":"agent","content":"Sure I can help"}]'),
                retell_call_id=f"retell_mock_{uuid.uuid4()}"
            )
            calls.append(c)
            
        session.add_all(appts)
        session.add_all(calls)
        await session.commit()
        print("Added appointments, calls!")
        
        # Add Waitlist entries
        print("Seeding Waitlist...")
        waitlists = []
        for i in range(3):
            w = Waitlist(
                tenant_id=tenant.id,
                patient_id=patients[i].id,
                preferred_time_range="Tuesday morning",
                notes="Patient wants early slot if possible",
                status="waiting"
            )
            waitlists.append(w)
        session.add_all(waitlists)
        await session.commit()
        print("Added waitlist entries!")
            
    print("Seed complete.")

if __name__ == "__main__":
    asyncio.run(seed_db())
