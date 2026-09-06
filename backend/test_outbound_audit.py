import sys
import asyncio
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from src.core.security import AuthenticatedUser
from src.api.routers.calle_router import (
    get_calle_status,
    get_campaign_estimates,
    run_confirmation_campaign,
    run_no_show_campaign,
    run_recall_campaign,
    run_survey_campaign,
    run_waitlist_campaign,
    trigger_single_call,
    SingleCallRequest,
    RecallCampaignRequest,
    WaitlistCampaignRequest,
)
from src.api.routers.calls_router import get_calls
from fastapi import BackgroundTasks

async def run_audit_tests():
    print("=== STARTING REAL OUTBOUND ENDPOINT AUDIT TEST ===")
    
    # 1. Mock AuthenticatedUser for Oakridge Physical Therapy clinic
    clinic_id = "d3b07384-d113-46a6-a719-38cf89235d54"
    auth = AuthenticatedUser(
        user_id="e64098bc-e74f-4d3f-b889-aaef14eaef14",
        clinic_id=clinic_id,
        clinic_name="Oakridge Physical Therapy & Wellness",
        email="auditor@bytelytic.com",
        role="owner",
    )
    
    # 2. Test GET /calle/status
    print("\n--- 1. Testing GET /calle/status ---")
    status = await get_calle_status(auth=auth)
    print("Status Result:", status)
    assert status["sdk_available"] is True, "SDK should be available"
    assert status["live_mode"] is True, "Live mode should be True"

    # 3. Test GET /calle/campaigns/estimates
    print("\n--- 2. Testing GET /calle/campaigns/estimates ---")
    est = await get_campaign_estimates(auth=auth)
    print("Estimates Result:", est)
    assert "counts" in est
    print(f"Queue Counts: Confirmation={est['counts']['confirmation']}, NoShow={est['counts']['no_show']}, Recall30={est['counts']['recall_30']}, Survey={est['counts']['survey']}, Waitlist={est['counts']['waitlist']}")

    # 4. Test POST /calle/campaigns/confirmation
    print("\n--- 3. Testing POST /calle/campaigns/confirmation ---")
    bg1 = BackgroundTasks()
    res_conf = await run_confirmation_campaign(background_tasks=bg1, auth=auth)
    print("Confirmation Campaign Response:", res_conf)
    print(f"Tasks queued in background: {len(bg1.tasks)}")
    # Run the background tasks to verify they execute without errors
    for task in bg1.tasks:
        await task()
    print("Background confirmation task executed successfully without exceptions!")

    # 5. Test POST /calle/campaigns/no-show
    print("\n--- 4. Testing POST /calle/campaigns/no-show ---")
    bg2 = BackgroundTasks()
    res_ns = await run_no_show_campaign(background_tasks=bg2, auth=auth)
    print("No-Show Campaign Response:", res_ns)
    print(f"Tasks queued in background: {len(bg2.tasks)}")
    for task in bg2.tasks:
        await task()
    print("Background no-show task executed successfully without exceptions!")

    # 6. Test POST /calle/campaigns/recall
    print("\n--- 5. Testing POST /calle/campaigns/recall ---")
    bg3 = BackgroundTasks()
    res_rec = await run_recall_campaign(body=RecallCampaignRequest(days_threshold=30, limit=5), background_tasks=bg3, auth=auth)
    print("Recall Campaign Response:", res_rec)
    print(f"Tasks queued in background: {len(bg3.tasks)}")
    for task in bg3.tasks:
        await task()
    print("Background recall task executed successfully without exceptions!")

    # 7. Test POST /calle/campaigns/survey
    print("\n--- 6. Testing POST /calle/campaigns/survey ---")
    bg4 = BackgroundTasks()
    res_surv = await run_survey_campaign(background_tasks=bg4, auth=auth)
    print("Survey Campaign Response:", res_surv)
    print(f"Tasks queued in background: {len(bg4.tasks)}")
    for task in bg4.tasks:
        await task()
    print("Background survey task executed successfully without exceptions!")

    # 8. Test POST /calle/campaigns/waitlist
    print("\n--- 7. Testing POST /calle/campaigns/waitlist ---")
    bg5 = BackgroundTasks()
    res_wl = await run_waitlist_campaign(body=WaitlistCampaignRequest(limit=5), background_tasks=bg5, auth=auth)
    print("Waitlist Campaign Response:", res_wl)
    print(f"Tasks queued in background: {len(bg5.tasks)}")
    for task in bg5.tasks:
        await task()
    print("Background waitlist task executed successfully without exceptions!")

    # 9. Test POST /calle/calls/single
    print("\n--- 8. Testing POST /calle/calls/single ---")
    single_req = SingleCallRequest(
        phone="+14155550106",
        campaign_type="confirmation",
        clinic_name="Oakridge Physical Therapy & Wellness",
        wait_for_completion=False,
        engine="calle",
    )
    bg6 = BackgroundTasks()
    single_res = await trigger_single_call(body=single_req, background_tasks=bg6, auth=auth)
    print("Single Call Trigger Response:", single_res)
    assert single_res.get("record_id") is not None, "Single call must return record_id"
    print("Single call executed successfully!")

    # 10. Test GET /calls
    print("\n--- 9. Testing GET /calls ---")
    calls_res = await get_calls(auth=auth, limit=10)
    print(f"Total calls returned: {len(calls_res['data'])}")
    if calls_res['data']:
        c0 = calls_res['data'][0]
        print(f"Sample Call Record: ID={c0.get('id')}, type={c0.get('call_type')}, to={c0.get('to_number')}, status={c0.get('status')}")

    print("\n=== ALL 6 OUTBOUND PIPELINE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(run_audit_tests())
