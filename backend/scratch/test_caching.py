import os
import sys
import time
import asyncio

# Setup path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import get_clinic_with_billing, update_clinic_billing, invalidate_clinic_cache
from src.core.cache import local_cache

async def run_cache_test():
    print("=======================================")
    print("Starting Cache Hit & Invalidation Test")
    print("=======================================")

    # 1. Clear any existing cache
    local_cache.clear()
    
    # 2. Pick a clinic from database
    from src.core.database import supabase
    res = supabase.table("clinics").select("id, name, owner_email").limit(1).execute()
    if not res.data:
        print("[FAIL] No clinics found in database to run tests.")
        return
        
    clinic_record = res.data[0]
    clinic_id = clinic_record["id"]
    owner_email = clinic_record["owner_email"]
    print(f"[INFO] Testing on clinic: {clinic_record['name']} (ID: {clinic_id})")

    # 3. Test Cache Miss (First Read)
    print("\n[Step 1] Querying clinic (should be a Cache Miss)...")
    start_time = time.perf_counter()
    clinic_miss = get_clinic_with_billing(clinic_id)
    miss_duration = time.perf_counter() - start_time
    print(f"Cache Miss Duration: {miss_duration*1000:.2f} ms")
    assert clinic_miss is not None
    assert clinic_miss["id"] == clinic_id

    # 4. Test Cache Hit (Second Read)
    print("\n[Step 2] Querying clinic again (should be a Cache Hit)...")
    start_time = time.perf_counter()
    clinic_hit = get_clinic_with_billing(clinic_id)
    hit_duration = time.perf_counter() - start_time
    print(f"Cache Hit Duration: {hit_duration*1000:.2f} ms")
    assert clinic_hit is not None
    assert clinic_hit["id"] == clinic_id
    
    # Latency should be significantly lower (usually sub-1ms)
    latency_reduction = (miss_duration - hit_duration) / miss_duration * 100
    print(f"Latency Reduction: {latency_reduction:.1f}%")
    assert hit_duration < miss_duration, "Cache hit should be faster than cache miss"

    # 5. Verify email mapping cache
    print("\n[Step 3] Verifying clinic lookup by owner_email cache...")
    cached_owner = local_cache.get(f"clinic_owner_{owner_email}")
    assert cached_owner is not None
    assert cached_owner["id"] == clinic_id
    print("[PASS] Owner email cache is correctly primed.")

    # 6. Test Cache Invalidation on Update
    print("\n[Step 4] Updating clinic billing (should invalidate cache)...")
    original_plan = clinic_miss.get("plan", "trial")
    temp_plan = "starter" if original_plan != "starter" else "growth"
    
    # Perform update
    update_clinic_billing(clinic_id, {"plan": temp_plan})
    
    # Cache should be invalidated and primed with new value
    cached_billing_after_update = local_cache.get(f"clinic_billing_{clinic_id}")
    assert cached_billing_after_update is not None, "Cache should be primed with updated value"
    assert cached_billing_after_update["plan"] == temp_plan, "Cache should hold the updated plan"
    print(f"[PASS] Clinic billing cache updated directly: {cached_billing_after_update['plan']}")

    # Restore original plan
    update_clinic_billing(clinic_id, {"plan": original_plan})
    print("[PASS] Clinic billing restored.")

    print("\n=======================================")
    print("[PASS] All Caching Verification Tests Passed!")
    print("=======================================")

if __name__ == "__main__":
    asyncio.run(run_cache_test())
