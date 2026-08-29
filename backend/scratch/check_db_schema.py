import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.database import supabase

print("Checking if 'ai_insights' table exists...")
try:
    res = supabase.table("ai_insights").select("id").limit(1).execute()
    print("  SUCCESS: 'ai_insights' table exists in the database!")
except Exception as e:
    print(f"  FAILED: 'ai_insights' table check failed: {e}")

print("\nChecking if patient LTV columns exist...")
try:
    res = supabase.table("patients").select("id, total_revenue_generated, churn_risk_score, is_vip").limit(1).execute()
    print("  SUCCESS: LTV columns exist in the 'patients' table!")
except Exception as e:
    print(f"  FAILED: LTV columns check failed: {e}")

print("\nChecking if benchmark_opt_in column exists...")
try:
    res = supabase.table("clinics").select("id, benchmark_opt_in").limit(1).execute()
    print("  SUCCESS: benchmark_opt_in column exists in the 'clinics' table!")
except Exception as e:
    print(f"  FAILED: benchmark_opt_in column check failed: {e}")
