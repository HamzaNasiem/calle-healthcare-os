"""
Test script for CALL-E Outbound Calling Integration.

Usage:
    cd backend
    python scripts/test_calle_call.py

This tests all 4 CALL-E workflows in dry-run mode (no real calls placed).
To test LIVE calls, set CALLE_DRY_RUN=false in .env and use your real phone number.
"""
import asyncio
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load env before importing settings
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.services.calle_service import calle_service


async def main():
    print("=" * 60)
    print("CALL-E INTEGRATION TEST SCRIPT")
    print(f"  DRY_RUN mode: {calle_service._is_dry_run()}")
    print(f"  LIVE client:  {calle_service.client is not None}")
    print("=" * 60)

    phone = "+12015550199"   # <-- Replace with your real phone to test LIVE
    clinic = "Sunrise Medical Clinic"

    # ── Test 1: 24h Appointment Confirmation ─────────────────────────────────
    print("\n[1/4] Testing Confirmation Call Workflow (24h before appointment)...")
    res1 = await calle_service.place_confirmation_call(
        phone=phone,
        clinic_name=clinic,
        time_str="10:30 AM",
        idempotency_key="test_conf_001"
    )
    print(f"  Call ID:         {res1.get('id')}")
    print(f"  Status:          {res1.get('status')}")
    print(f"  Task Completed:  {res1.get('task_completed')}")
    print(f"  Structured:      {res1.get('structured_result')}")
    print(f"  Confidence:      {res1.get('completion_confidence')}")
    print(f"  Summary:         {res1.get('summary')}")

    # ── Test 2: No-Show Recovery ──────────────────────────────────────────────
    print("\n[2/4] Testing No-Show Recovery Call Workflow (15min after missed appt)...")
    res2 = await calle_service.place_no_show_recovery_call(
        phone=phone,
        clinic_name=clinic,
        time_str="09:00 AM",
        idempotency_key="test_noshow_002"
    )
    print(f"  Call ID:         {res2.get('id')}")
    print(f"  Status:          {res2.get('status')}")
    print(f"  Structured:      {res2.get('structured_result')}")

    # ── Test 3: Waitlist Fill-In ──────────────────────────────────────────────
    print("\n[3/4] Testing Waitlist Fill-In Call Workflow (slot opened up)...")
    res3 = await calle_service.place_waitlist_fill_call(
        phone=phone,
        clinic_name=clinic,
        slot_date="Tomorrow, August 4",
        slot_time="02:00 PM",
        idempotency_key="test_waitlist_003"
    )
    print(f"  Call ID:         {res3.get('id')}")
    print(f"  Status:          {res3.get('status')}")
    print(f"  Structured:      {res3.get('structured_result')}")

    # ── Test 4: Pre-Appointment Prep ─────────────────────────────────────────
    print("\n[4/4] Testing Pre-Appointment Prep Call Workflow (2h before)...")
    res4 = await calle_service.place_pre_appointment_call(
        phone=phone,
        clinic_name=clinic,
        time_str="03:00 PM",
        idempotency_key="test_prep_004"
    )
    print(f"  Call ID:         {res4.get('id')}")
    print(f"  Status:          {res4.get('status')}")
    print(f"  Structured:      {res4.get('structured_result')}")

    print("\n" + "=" * 60)
    print("[OK] ALL 4 CALL-E WORKFLOWS VERIFIED OK!")
    print("=" * 60)

    if calle_service._is_dry_run():
        print("\n⚠️  NOTE: Running in DRY-RUN mode.")
        print("   Set CALLE_DRY_RUN=false in .env to test real CALL-E API calls.")
        print("   Replace phone='+12015550199' with your actual phone number.")


if __name__ == "__main__":
    asyncio.run(main())
