"""
Seed script: Creates demo clinic (tenant), admin user, providers, patients, and appointments.
Run: python scripts/seed_demo.py
"""
import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
from src.core.encryption import phi_crypto


DB_CONFIG = dict(
    host="aws-0-ap-northeast-1.pooler.supabase.com",
    port=5432,
    user="postgres.bdkinditdmppgucsuqpg",
    password="Bytelytic@2026!",
    database="postgres",
    ssl="require",
    statement_cache_size=0,
)

TENANT_ID   = "11111111-1111-1111-1111-111111111111"
OWNER_ID    = "22222222-2222-2222-2222-222222222222"
PROVIDER_ID = "33333333-3333-3333-3333-333333333333"


async def main():
    print("Connecting to Supabase...")
    conn = await asyncpg.connect(**DB_CONFIG)
    print("Connected!\n")

    # ── 1. Tenant (Clinic) ────────────────────────────────────────────
    existing = await conn.fetchval("SELECT id FROM tenants WHERE id=$1", uuid.UUID(TENANT_ID))
    if existing:
        print("Tenant already exists -- skipping.")
    else:
        await conn.execute(
            """
            INSERT INTO tenants (id, name, slug, security_officer_email, owner_email, plan, is_active, timezone, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            uuid.UUID(TENANT_ID),
            "Sunrise Medical Clinic",
            "sunrise-medical",
            "security@sunriseclinic.com",
            "admin@sunriseclinic.com",
            "tier2",
            True,
            "America/Chicago",
            datetime.now(UTC),
            datetime.now(UTC),
        )
        print("[OK] Tenant created: Sunrise Medical Clinic")

    # ── 2. Tenant Settings ────────────────────────────────────────────
    ts_exists = await conn.fetchval(
        "SELECT tenant_id FROM tenant_settings WHERE tenant_id=$1", uuid.UUID(TENANT_ID)
    )
    if not ts_exists:
        await conn.execute(
            """
            INSERT INTO tenant_settings
                (id, tenant_id, clinic_name, clinic_phone, timezone, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            uuid.uuid4(),
            uuid.UUID(TENANT_ID),
            "Sunrise Medical Clinic",
            "+15005550006",
            "America/Chicago",
            datetime.now(UTC),
        )
        print("[OK] Tenant settings created")

    # ── 3. Admin User ─────────────────────────────────────────────────
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        HASHED_PW = pwd_context.hash("Admin@2026!")
    except Exception:
        HASHED_PW = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

    user_exists = await conn.fetchval(
        "SELECT id FROM users WHERE email=$1", "admin@sunriseclinic.com"
    )
    if user_exists:
        print("Admin user already exists -- skipping.")
    else:
        await conn.execute(
            """
            INSERT INTO users
                (id, tenant_id, email, hashed_password, full_name, role,
                 is_active, is_deleted, mfa_enabled, failed_login_count, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            uuid.UUID(OWNER_ID),
            uuid.UUID(TENANT_ID),
            "admin@sunriseclinic.com",
            HASHED_PW,
            "Dr. Sarah Johnson",
            "owner",
            True,
            False,
            False,   # MFA off for demo
            0,
            datetime.now(UTC),
            datetime.now(UTC),
        )
        print("[OK] Admin user created")
        print("    Email:    admin@sunriseclinic.com")
        print("    Password: Admin@2026!")
        print("    Role:     owner")

    # ── 4. Provider ───────────────────────────────────────────────────
    prov_exists = await conn.fetchval(
        "SELECT id FROM providers WHERE id=$1", uuid.UUID(PROVIDER_ID)
    )
    if not prov_exists:
        try:
            await conn.execute(
                """
                INSERT INTO providers
                    (id, tenant_id, user_id, display_name, specialty, is_accepting_patients, is_deleted)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                uuid.UUID(PROVIDER_ID),
                uuid.UUID(TENANT_ID),
                uuid.UUID(OWNER_ID),
                "Dr. Sarah Johnson",
                "General Practice",
                True,
                False,
            )
            print("[OK] Provider created")
        except Exception as e:
            print(f"   Provider error: {e}")
    else:
        print("Provider already exists -- skipping.")

    # ── 5. Sample Patients ────────────────────────────────────────────
    patients = [
        ("44444444-4444-4444-4444-444444444401", "Demo Patient A",   "1975-06-15", "+15005550006"),
        ("44444444-4444-4444-4444-444444444402", "Demo Patient B",  "1988-03-22", "+15005550006"),
        ("44444444-4444-4444-4444-444444444403", "Demo Patient C",    "1962-11-08", "+15005550006"),
    ]

    pat_count = 0
    for pid, full_name, dob, phone in patients:
        exists = await conn.fetchval(
            "SELECT id FROM patients WHERE id=$1", uuid.UUID(pid)
        )
        if not exists:
            try:
                phone_hash = hashlib.sha256(phone.encode()).hexdigest()
                row_hash = hashlib.sha256(f"pat_{pid}".encode()).hexdigest()
                phone_enc = phi_crypto.encrypt(phone)
                name_enc = phi_crypto.encrypt(full_name)
                dob_enc = phi_crypto.encrypt(dob)

                await conn.execute(
                    """
                    INSERT INTO patients
                        (id, tenant_id, phone_hash, phone_encrypted, full_name_encrypted, dob_encrypted,
                         is_existing_patient, visit_count, total_revenue_cents, is_vip, data_access_level,
                         is_deleted, row_hash, created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                    """,
                    uuid.UUID(pid),
                    uuid.UUID(TENANT_ID),
                    phone_hash,
                    phone_enc,
                    name_enc,
                    dob_enc,
                    True,
                    2,
                    15000,
                    False,
                    "standard",
                    False,
                    row_hash,
                    datetime.now(UTC),
                    datetime.now(UTC),
                )
                pat_count += 1
            except Exception as e:
                print(f"   Patient {full_name} error: {str(e)[:120]}")

    if pat_count:
        print(f"[OK] {pat_count} patients created")

    # ── 6. Sample Appointments ────────────────────────────────────────
    now = datetime.now(UTC)
    # Target 10 AM tomorrow
    tomorrow_10am = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    appts = [
        (
            "55555555-5555-5555-5555-555555555501",
            "44444444-4444-4444-4444-444444444401",
            tomorrow_10am,                           # Tomorrow 10am-ish
            "Annual Checkup",
            "scheduled",
            "CONF-101",
            False,                                   # call_confirmed
        ),
        (
            "55555555-5555-5555-5555-555555555502",
            "44444444-4444-4444-4444-444444444402",
            now - timedelta(minutes=20),             # 20 min ago (no-show target)
            "Follow-up Consultation",
            "scheduled",                             # Changed to scheduled to allow no-show recovery logic if needed, or leave as scheduled for logic to pick it up
            "CONF-102",
            False,
        ),
        (
            "55555555-5555-5555-5555-555555555503",
            "44444444-4444-4444-4444-444444444403",
            now + timedelta(hours=1, minutes=30),    # In 1.5 hours (pre-appt target)
            "General Consultation",
            "scheduled",
            "CONF-103",
            False,
        ),
        (
            "55555555-5555-5555-5555-555555555504",
            "44444444-4444-4444-4444-444444444401",
            now + timedelta(days=7),                 # Next week
            "Future Appointment 1",
            "scheduled",
            "CONF-104",
            False,
        ),
        (
            "55555555-5555-5555-5555-555555555505",
            "44444444-4444-4444-4444-444444444402",
            now + timedelta(days=8),                 # Next week
            "Future Appointment 2",
            "scheduled",
            "CONF-105",
            False,
        ),
    ]

    appt_count = 0
    for aid, pat_id, slot_start, service_type, status, code, call_confirmed in appts:
        exists = await conn.fetchval(
            "SELECT id FROM appointments WHERE id=$1", uuid.UUID(aid)
        )
        if not exists:
            try:
                row_hash = hashlib.sha256(f"appt_{aid}".encode()).hexdigest()
                await conn.execute(
                    """
                    INSERT INTO appointments
                        (id, tenant_id, patient_id, provider_id,
                         slot_start, slot_end, service_type, duration_minutes,
                         status, booked_by, confirmation_code, sms_confirmed, call_confirmed,
                         reminder_24h_sent, reminder_2h_sent, is_deleted, row_hash,
                         created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                    """,
                    uuid.UUID(aid),
                    uuid.UUID(TENANT_ID),
                    uuid.UUID(pat_id),
                    uuid.UUID(PROVIDER_ID),
                    slot_start,
                    slot_start + timedelta(minutes=30),
                    service_type,
                    30,
                    status,
                    "patient_online",
                    code,
                    False,
                    call_confirmed,
                    False,
                    False,
                    False,
                    row_hash,
                    datetime.now(UTC),
                    datetime.now(UTC),
                )
                appt_count += 1
            except Exception as e:
                print(f"   Appointment error: {str(e)[:120]}")

    if appt_count:
        print(f"[OK] {appt_count} appointments created")

    # ── Summary ───────────────────────────────────────────────────────
    counts = {}
    for tbl in ["tenants", "users", "patients", "appointments", "providers"]:
        try:
            c = await conn.fetchval(f'SELECT COUNT(*) FROM "{tbl}"')
            counts[tbl] = c
        except Exception:
            counts[tbl] = "?"

    print("\n" + "="*50)
    print("DATABASE SUMMARY:")
    for tbl, cnt in counts.items():
        print(f"  {tbl:<20} {cnt} rows")
    print("="*50)

    await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
