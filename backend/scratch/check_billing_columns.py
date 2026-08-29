import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.database import supabase

print("Checking if Phase 5 billing columns exist in 'clinics' table...")
try:
    res = supabase.table("clinics").select("id, plan, stripe_customer_id, stripe_subscription_status").limit(1).execute()
    print("  SUCCESS: Phase 5 billing columns exist!")
    print("  Data sample:", res.data)
except Exception as e:
    print(f"  FAILED: billing columns check failed: {e}")
