import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.insights_service import insights_service
from src.core.database import supabase

async def test_insights():
    clinic_id = "17641801-58ed-49b1-9f75-d6d46fbe78c5" # Hamza Clinic
    if len(sys.argv) > 1:
        clinic_id = sys.argv[1]
        
    print(f"=========================================")
    print(f"Testing Weekly AI Insights for Clinic: {clinic_id}")
    print(f"=========================================\n")
    
    print("Checking if target clinic exists in database...")
    res = supabase.table("clinics").select("name").eq("id", clinic_id).execute()
    if not res.data:
        print(f"[ERROR] Clinic with ID {clinic_id} does not exist.")
        print("Please check your clinic IDs using `python scratch/check_db_schema.py` and pass it as an argument.")
        sys.exit(1)
        
    clinic_name = res.data[0]["name"]
    print(f"Found Clinic: {clinic_name}")
    
    print("\nAttempting to generate weekly insights summary...")
    try:
        summary = await insights_service.generate_weekly_insights(clinic_id)
        if summary:
            print("\n[SUCCESS] Generated AI Summary:")
            print("-----------------------------------------")
            print(summary)
            print("-----------------------------------------")
        else:
            print("\n[FAILED] generate_weekly_insights returned None or empty.")
    except Exception as e:
        print(f"\n[ERROR] Generation failed: {e}")
        print("\nNote: This script will fail if you haven't executed the database migration SQL script (phase6_migrations.sql) in the Supabase SQL Editor first.")

if __name__ == "__main__":
    asyncio.run(test_insights())
