import asyncio
import datetime
import traceback
import sys
import os
import gc

# Add parent directory to path to support running as script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.core.database import supabase
from src.core.logger import log

# Initialize Sentry APM Performance Monitoring
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=1.0,
        )
        log.info("[Sentry] Performance monitoring initialized successfully on Job Worker.")
    except ImportError:
        log.warning("[Sentry] WARNING: sentry-sdk package not installed. Skipping Sentry initialization on Job Worker.")
from src.jobs.scheduler import start_jobs, scheduler
from src.services.voice_service import voice_service
from src.services.sms_service import sms_service
from src.services.waitlist_service import waitlist_service
from src.services.recall_service import recall_service

async def process_next_job() -> bool:
    """
    Fetch and atomically process a single pending async job from the queue.
    Returns True if a job was found (and either claimed or processed), False if queue is empty.
    """
    try:
        # 1. Fetch one pending async job
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        res = supabase.table("jobs").select("*") \
            .eq("status", "pending") \
            .lte("run_at", now_iso) \
            .in_("job_type", ["process_retell_webhook", "process_twilio_sms", "process_telnyx_sms"]) \
            .order("created_at") \
            .limit(1) \
            .execute()
        if not res.data:
            return False
            
        job = res.data[0]
        job_id = job["id"]
        current_attempts = job.get("attempts", 0)
        max_attempts = job.get("max_attempts", 3)
        new_attempts = current_attempts + 1
        
        # 2. Atomically lock/claim the job
        claim_res = supabase.table("jobs").update({
            "status": "processing",
            "attempts": new_attempts
        }).eq("id", job_id).eq("status", "pending").execute()
        
        # If claim_res.data is empty, another worker process claimed it first
        if not claim_res.data:
            return True
            
        job_type = job["job_type"]
        payload = job["payload"]
        clinic_id = job["clinic_id"]
        
        log.info(f"Claimed job {job_id} of type {job_type} for clinic {clinic_id} (Attempt {new_attempts}/{max_attempts})")
        
        success = False
        error_msg = None
        
        # 3. Execute job task
        try:
            if job_type == "process_retell_webhook":
                call_info = payload.get("call_info")
                call_type = payload.get("call_type", "inbound")
                dynamic_vars = payload.get("dynamic_vars", {})
                
                # Execute transcript/call extraction logic
                process_res = await voice_service.handle_call_event(call_info)
                
                if process_res.get("success"):
                    outcome = process_res["data"].get("action")
                    
                    # Run post-call waitlist or recall campaigns
                    if call_type == "waitlist_offer" and dynamic_vars.get("waitlistId"):
                        await waitlist_service.process_offer_outcome(
                            clinic_id=clinic_id,
                            retell_call_id=call_info.get("call_id"),
                            outcome=outcome,
                            waitlist_id=dynamic_vars.get("waitlistId")
                        )
                    elif call_type == "recall":
                        await recall_service.process_recall_outcome(
                            clinic_id=clinic_id,
                            retell_call_id=call_info.get("call_id"),
                            outcome=outcome
                        )
                    success = True
                else:
                    error_msg = process_res.get("error", "Failed to handle Retell call event.")
                    
            elif job_type == "process_twilio_sms":
                from_number = payload.get("from_number")
                body = payload.get("body", "")
                twilio_sid = payload.get("twilio_sid")
                
                sms_res = await sms_service.handle_inbound(
                    from_number=from_number,
                    body=body,
                    clinic_id=clinic_id,
                    twilio_sid=twilio_sid
                )
                
                if sms_res.get("success"):
                    success = True
                else:
                    error_msg = sms_res.get("error", "Failed to handle inbound SMS.")
                    
            elif job_type == "process_telnyx_sms":
                from_number = payload.get("from_number")
                body = payload.get("body", "")
                message_sid = payload.get("message_sid")
                
                sms_res = await sms_service.handle_inbound(
                    from_number=from_number,
                    body=body,
                    clinic_id=clinic_id,
                    twilio_sid=message_sid
                )
                
                if sms_res.get("success"):
                    success = True
                else:
                    error_msg = sms_res.get("error", "Failed to handle inbound SMS.")
                    
            else:
                error_msg = f"Unknown job type: {job_type}"
                
        except Exception as e:
            error_msg = f"Exception: {str(e)}\n{traceback.format_exc()}"
            log.error(f"Exception in job {job_id}: {error_msg}")
            
        # 4. Update job status
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if success:
            supabase.table("jobs").update({
                "status": "done",
                "ran_at": now_iso,
                "error_message": None
            }).eq("id", job_id).execute()
            log.info(f"Job {job_id} completed successfully.")
        else:
            # Retry or fail depending on attempts
            if new_attempts >= max_attempts:
                # Dead Letter Queue: Move job to DLQ table (or mark as DLQ)
                try:
                    supabase.table("dead_letter_jobs").insert({
                        "original_job_id": job_id,
                        "clinic_id": clinic_id,
                        "job_type": job_type,
                        "payload": payload,
                        "error_message": error_msg,
                        "failed_at": now_iso
                    }).execute()
                    supabase.table("jobs").delete().eq("id", job_id).execute()
                    log.error(f"Job {job_id} failed permanently after {new_attempts} attempts. Moved to Dead Letter Queue.")
                except Exception as dlq_err:
                    # Fallback if table doesn't exist
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": error_msg,
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
                    log.error(f"Job {job_id} failed permanently. DLQ insert failed, marked as failed: {str(dlq_err)}")
            else:
                # Calculate exponential backoff delay (e.g. 10s, 30s, 90s)
                delay_seconds = 10 * (3 ** (new_attempts - 1))
                next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delay_seconds)
                
                supabase.table("jobs").update({
                    "status": "pending",  # release back to queue for retry
                    "run_at": next_run.isoformat(),
                    "error_message": f"Retry {new_attempts}: {error_msg}",
                    "ran_at": now_iso
                }).eq("id", job_id).execute()
                log.warning(f"Job {job_id} failed temporarily. Scheduled for retry at {next_run.isoformat()} (delay {delay_seconds}s).")
                
        # Run active garbage collection to free memory
        gc.collect()
        return True
    except Exception as general_err:
        log.error(f"Failed processing loop step: {general_err}")
        return False

async def queue_polling_loop():
    """Infinite loop to poll the database jobs table."""
    print("[worker] Starting async jobs queue polling loop (polling interval = 2s)...")
    while True:
        try:
            # Keep processing jobs until queue is empty, then sleep
            has_more = True
            while has_more:
                has_more = await process_next_job()
                # Yield control briefly to event loop
                await asyncio.sleep(0.01)
        except Exception as e:
            log.error(f"Exception in polling loop: {str(e)}")
            
        await asyncio.sleep(2.0)

async def main():
    log.info("=========================================")
    log.info("Bytelytic OS - Background Job Worker")
    log.info("=========================================")
    
    # 1. Start APScheduler for cron jobs (Reminders, Followups, etc.)
    try:
        start_jobs()
    except Exception as e:
        log.error(f"Failed to start APScheduler: {e}")
        
    # 2. Run the async queue polling loop alongside APScheduler
    try:
        await queue_polling_loop()
    except asyncio.CancelledError:
        log.info("Received stop signal, shutting down...")
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=True)
            log.info("APScheduler shut down gracefully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Terminated by user.")
